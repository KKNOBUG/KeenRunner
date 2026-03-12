# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_source_crud.py
@DateTime: 2026/3/6
"""
import traceback
from typing import Optional, Dict, Any, List

from tortoise.exceptions import IntegrityError, FieldError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from backend import LOGGER
from backend.applications.aotutest.models.autotest_model import AutoTestApiDataSourceInfo, unique_identify
from backend.applications.aotutest.schemas.autotest_data_source_schema import (
    AutoTestDataSourceCreate,
    AutoTestDataSourceUpdate,
)
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import (
    ParameterException,
    NotFoundException,
    DataBaseStorageException,
)


# 数据集名称列名（xlsx 表头），支持中英文
DATASET_NAME_COLUMN_ALIASES = ("数据集名称", "dataset_name", "场景", "场景名称")


def make_cache_key(case_id: int, step_code: str) -> str:
    """生成 Redis 缓存键：dataset_{case_id}_{step_code}。"""
    return f"dataset_{case_id}_{step_code}"


class AutoTestDataSourceCrud(ScaffoldCrud[AutoTestApiDataSourceInfo, AutoTestDataSourceCreate, AutoTestDataSourceUpdate]):
    """数据源 CRUD：唯一 (case_id, step_code)；同一文件多条记录共享 file_code。"""

    def __init__(self):
        super().__init__(model=AutoTestApiDataSourceInfo)

    async def get_by_id(self, data_source_id: int, on_error: bool = False) -> Optional[AutoTestApiDataSourceInfo]:
        if not data_source_id:
            raise ParameterException(message="参数(data_source_id)不能为空")
        instance = await self.model.filter(id=data_source_id, state__not=1).first()
        if not instance and on_error:
            raise NotFoundException(message=f"数据源(id={data_source_id})不存在")
        return instance

    async def get_list_by_file_code(
        self,
        file_code: str,
        state: int = 0,
    ) -> List[AutoTestApiDataSourceInfo]:
        """按文件标识代码查询该文件下所有步骤记录，按 step_code 排序。"""
        if not (file_code or "").strip():
            raise ParameterException(message="参数 file_code 不能为空")
        return await self.model.filter(
            file_code=file_code.strip(),
            state=state,
        ).order_by("step_code").all()

    async def get_by_case_step(
        self,
        case_id: int,
        step_code: str,
        on_error: bool = False,
    ) -> Optional[AutoTestApiDataSourceInfo]:
        """按 case_id + step_code 查询单条（用于按步骤取数）。"""
        if not case_id or not (step_code or "").strip():
            raise ParameterException(message="参数 case_id、step_code 不能为空")
        instance = await self.model.filter(
            case_id=case_id,
            step_code=step_code.strip(),
            state__not=1,
        ).first()
        if not instance and on_error:
            raise NotFoundException(message=f"数据源(case_id={case_id}, step_code={step_code})不存在")
        return instance

    async def get_dataset_scenario(
        self,
        case_id: int,
        step_code: str,
        dataset_name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        根据 case_id、step_code、数据集名称从 AutoTestApiDataSourceInfo 表获取该步骤下该场景的数据。
        供 HTTP 请求步骤执行器在参数化执行时按数据集名称取数。
        :return: 该场景的 { "head": {...}, "body": {...}, "assert": {...} }，不存在则返回 None。
        """
        if not (dataset_name or "").strip():
            return None
        record = await self.get_by_case_step(
            case_id=case_id,
            step_code=(step_code or "").strip(),
            on_error=False,
        )
        if not record or not isinstance(record.dataset, dict):
            return None
        return record.dataset.get((dataset_name or "").strip())

    async def create_data_sources_from_parsed(
        self,
        case_id: int,
        step_code: str,
        file_name: Optional[str] = None,
        file_path: Optional[str] = None,
        file_hash: Optional[str] = None,
        file_desc: Optional[str] = None,
        parsed_data: Optional[Dict[str, Any]] = None,
        dataset_names: Optional[List[str]] = None,
        created_user: Optional[str] = None,
    ) -> AutoTestApiDataSourceInfo:
        """上传时按 (case_id, step_code) 不存在则创建，存在则覆盖更新。"""
        if not case_id:
            raise ParameterException(message="参数 case_id 不能为空")
        if parsed_data is None:
            raise ParameterException(message="参数 parsed_data 不能为空")
        cache_key = make_cache_key(case_id, step_code)
        step_code = (step_code or "").strip()
        existing = await self.get_by_case_step(case_id=case_id, step_code=step_code, on_error=False)
        if existing:
            update_kw = {
                "file_name": file_name,
                "file_path": file_path,
                "file_hash": file_hash,
                "file_desc": file_desc,
                "cache_key": cache_key,
                "dataset": parsed_data,
                "dataset_names": dataset_names if dataset_names is not None else (existing.dataset_names or []),
                "updated_user": created_user,
            }
            update_kw = {k: v for k, v in update_kw.items() if v is not None or k in ("dataset", "dataset_names")}
            if update_kw:
                await self.model.filter(id=existing.id).update(**update_kw)
            await existing.refresh_from_db()
            return existing
        try:
            return await self.model.create(
                case_id=case_id,
                step_code=step_code,
                cache_key=cache_key,
                file_name=file_name or "",
                file_path=file_path or "",
                file_hash=file_hash or "",
                file_desc=file_desc,
                dataset=parsed_data,
                dataset_names=dataset_names or [],
                state=0,
                created_user=created_user,
            )
        except IntegrityError as e:
            LOGGER.error(f"数据源创建失败 step_code={step_code}: {e}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=f"数据源保存失败: {e}") from e

    async def list_by_case(
        self,
        case_id: int,
        state: int = 0,
    ) -> List[AutoTestApiDataSourceInfo]:
        """按用例查询该用例下所有数据源记录（可能多文件、每文件多步骤），按 file_code、step_code 排序。"""
        return await self.model.filter(case_id=case_id, state=state).order_by("-updated_time", "step_code").all()


AUTOTEST_DATA_SOURCE_CRUD = AutoTestDataSourceCrud()
