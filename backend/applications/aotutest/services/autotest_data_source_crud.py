# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_source_crud.py
@DateTime: 2026/3/6
"""
import os
import traceback
from typing import List, Optional, Dict, Any, Tuple
from typing import Union

import aiofiles.os as aos
from tortoise.exceptions import FieldError
from tortoise.exceptions import IntegrityError, DoesNotExist
from tortoise.expressions import Q

from backend.applications.aotutest.models.autotest_data_create_model import AutoTestDataCreateModel
from backend.applications.aotutest.models.autotest_data_source_model import AutoTestDataSourceModel
from backend.applications.aotutest.schemas.autotest_data_source_schema import AutoTestDataSourceCreate, AutoTestDataSourceUpdate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER, PROJECT_CONFIG
from backend.core.exceptions import DataAlreadyExistsException, NotFoundException, ParameterException
from backend.core.exceptions import DataBaseStorageException


def make_cache_key(case_id: int, step_code: str) -> str:
    """
    生成Redis等使用的缓存键名。

    :param case_id: 用例主键
    :param step_code: 步骤标识代码
    :return: 缓存键字符串
    """
    return f"dataset_{case_id}_{step_code}"


class AutoTestDataSourceCrud(ScaffoldCrud[AutoTestDataSourceModel, AutoTestDataSourceCreate, AutoTestDataSourceUpdate]):

    def __init__(self):
        super().__init__(model=AutoTestDataSourceModel)

    async def get_by_id(self, data_source_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestDataSourceModel]:
        """
        根据主键ID查询数据源。

        :param data_source_id: 数据源主键ID
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 数据源实例或None
        """
        if not data_source_id:
            error_message: str = "查询数据源失败, 参数[data_source_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.get_or_none(id=data_source_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询数据源失败, 记录[id={data_source_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, data_source_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestDataSourceModel]:
        """
        根据data_source_code查询数据源。

        :param data_source_code: 数据驱动标识代码
        :param on_error: 为True时若未找到则抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 数据源实例或None
        """
        if not (data_source_code or "").strip():
            error_message: str = "查询数据源失败, 参数[data_source_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(data_source_code=data_source_code.strip(), **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询数据源失败, 记录[data_source_code={data_source_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_case_step(
            self,
            case_id: Optional[int] = None,
            case_code: Optional[str] = None,
            step_id: Optional[int] = None,
            step_code: Optional[str] = None,
            on_error: bool = False,
            **kwargs
    ) -> Optional[Union[AutoTestDataSourceModel, List[AutoTestDataSourceModel]]]:
        """
        根据用例与步骤标识查询数据源，可返回单条或列表。

        :param case_id: 用例主键
        :param case_code: 用例标识代码
        :param step_id: 步骤主键
        :param step_code: 步骤标识代码
        :param on_error: 为True时若未找到则抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 单条实例、列表或None
        """
        if not case_id and not (case_code or "").strip():
            error_message: str = "查询数据源失败, 参数[case_id | case_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        conditions: Dict[str, Any] = {**kwargs}
        if case_id:
            conditions["case_id"] = case_id
        if case_code:
            conditions["case_code"] = case_code

        has_step_condition = False
        if step_id:
            conditions["step_id"] = step_id
            has_step_condition = True
        if step_code:
            conditions["step_code"] = step_code
            has_step_condition = True

        if has_step_condition:
            instance = await self.model.filter(**conditions).first()
            if not instance and on_error:
                error_message: str = "根据条件查询数据源暂无匹配记录"
                LOGGER.error(f"{error_message}, 条件明细: {conditions}")
                raise NotFoundException(message=error_message, data=conditions)
            return instance

        instances = await self.model.filter(**conditions).order_by("step_id", "step_code").all()
        if not instances and on_error:
            error_message: str = f"根据条件查询数据源暂无匹配记录"
            LOGGER.error(f"{error_message}, 条件明细: {conditions}")
            raise NotFoundException(message=error_message, data=conditions)
        return instances

    async def get_dataset_scenario(self, case_id: int, step_code: str, dataset_name: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        根据用例、步骤、数据集名称取该步骤下单个场景的结构化数据。

        :param case_id: 用例主键
        :param step_code: 步骤标识代码
        :param dataset_name: 场景/数据集名称
        :param kwargs: 额外过滤条件
        :return: 形如{"head", "body", "assert_head", "assert_body"}的场景字典；无数据时返回None
        """
        if not (dataset_name or "").strip():
            return None
        record = await self.get_by_case_step(
            case_id=case_id,
            step_code=(step_code or "").strip(),
            on_error=False,
            **kwargs
        )
        if not record or not isinstance(record.dataset, dict):
            return None
        return record.dataset.get((dataset_name or "").strip())

    async def create_data_source(self, data_source_in: AutoTestDataSourceCreate) -> AutoTestDataSourceModel:
        """
        创建数据源，根据用例与步骤定位，已删除则恢复，已启用则拒绝。

        :param data_source_in: 创建schema(data_source_code由模型默认值生成，无需传入)
        :return: 新建或恢复后的数据源实例
        """
        data_dict: Dict[str, Any] = data_source_in.model_dump(exclude_none=True, exclude_unset=True)
        case_id = data_dict.get("case_id")
        step_code = data_dict.get("step_code")
        if not case_id or not str(step_code or "").strip():
            error_message: str = "新增数据源失败, 参数[case_id, step_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 模型非空字段兜底：cache_key/dataset/dataset_names
        if not str(data_dict.get("cache_key") or "").strip():
            data_dict["cache_key"] = make_cache_key(int(case_id), str(step_code or "").strip())
        if data_dict.get("dataset") is None:
            data_dict["dataset"] = {}
        if data_dict.get("dataset_names") is None:
            data_dict["dataset_names"] = []

        existing = await self.model.filter(case_id=case_id, step_code=step_code).first()

        if not existing:
            try:
                return await self.create(obj_in=data_dict)
            except IntegrityError as e:
                error_message: str = f"新增数据源异常, 违反约束规则: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise DataBaseStorageException(message=error_message) from e

        if existing.state == 1:
            update_dict: Dict[str, Any] = dict(data_dict)
            update_dict["state"] = 0
            if "created_user" in update_dict:
                update_dict["updated_user"] = update_dict.pop("created_user")
            try:
                return await self.update(id=existing.id, obj_in=update_dict)
            except DoesNotExist as e:
                error_message: str = f"恢复数据源失败, 记录[id={existing.id}]不存在, 错误描述: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise NotFoundException(message=error_message) from e
            except IntegrityError as e:
                error_message: str = f"恢复数据源异常, 违反约束规则: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise DataBaseStorageException(message=error_message) from e

        error_message: str = (
            f"新增数据源失败, 该步骤已绑定启用中的数据源, "
            f"查询条件: [case_id={case_id}, step_code={step_code}]"
        )
        LOGGER.error(error_message)
        raise DataAlreadyExistsException(message=error_message)

    async def update_data_source(self, data_source_in: AutoTestDataSourceUpdate) -> AutoTestDataSourceModel:
        """
        更新数据源，根据id/code或用例步骤组合定位。

        :param data_source_in: 更新schema
        :return: 更新后的数据源实例
        """
        case_id: Optional[int] = data_source_in.case_id
        step_id: Optional[int] = data_source_in.step_id
        case_code: Optional[str] = data_source_in.case_code
        step_code: Optional[str] = data_source_in.step_code
        data_source_id: Optional[int] = data_source_in.data_source_id
        data_source_code: Optional[str] = data_source_in.data_source_code

        if data_source_id:
            instance: Optional[AutoTestDataSourceModel] = await self.get_by_id(
                data_source_id=data_source_id,
                on_error=True,
                state__not=1
            )
        elif (data_source_code or "").strip():
            instance: Optional[AutoTestDataSourceModel] = await self.get_by_code(
                data_source_code=data_source_code.strip(),
                on_error=True,
                state__not=1
            )
        elif (case_id or (case_code or "").strip()) and (step_id or (step_code or "").strip()):
            instance: Optional[AutoTestDataSourceModel] = await self.get_by_case_step(
                case_id=case_id,
                case_code=case_code,
                step_id=step_id,
                step_code=step_code,
                on_error=True,
                state__not=1
            )
        else:
            error_message: str = "更新数据源失败, 参数[data_source_id]或[data_source_code]或[case_id, case_code, step_id, step_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        update_dict: Dict[str, Any] = data_source_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"cache_key", "case_id", "case_code", "step_id", "step_code", "data_source_id", "data_source_code"}
        )
        if not update_dict:
            return instance

        try:
            return await self.update(id=instance.id, obj_in=update_dict)
        except DoesNotExist as e:
            error_message: str = f"更新数据源失败, 记录[id={instance.id}]不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = f"更新数据源异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def select_data_sources(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestDataSourceModel]]:
        """
        根据条件分页查询数据源列表。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)元组
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询数据源异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def create_data_sources_from_parsed(
            self,
            case_id: int,
            case_code: str,
            step_id: int,
            step_code: str,
            file_name: Optional[str] = None,
            file_path: Optional[str] = None,
            file_hash: Optional[str] = None,
            file_desc: Optional[str] = None,
            parsed_data: Optional[Dict[str, Any]] = None,
            dataset_names: Optional[List[str]] = None,
            dataframe: Optional[List[Any]] = None,
            axis: int = 0,
            created_user: Optional[str] = None,
    ) -> AutoTestDataSourceModel:
        """
        上传解析场景：根据case_id+step_id+step_code若已存在则更新，否则创建。

        :param case_id: 用例主键
        :param case_code: 用例标识代码
        :param step_id: 步骤主键
        :param step_code: 步骤标识代码
        :param file_name: 存储文件名
        :param file_path: 存储路径
        :param file_hash: 文件哈希
        :param file_desc: 描述
        :param parsed_data: 解析后的dataset字典
        :param dataset_names: 场景名称列表
        :param dataframe: 原始二维矩阵
        :param axis: 数据矩阵方向(0:水平模式, 1:垂直模式)
        :param created_user: 创建人(更新路径会映射为updated_user)
        :return: 数据源实例
        """
        if not parsed_data:
            error_message: str = "参数[parsed_data]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        from backend.applications.aotutest.services.autotest_data_source_parser import normalize_dataset_record

        # 每个场景强制补齐 head/body/assert_head/assert_body 四键
        normalized_dataset = {
            str(scene_name): normalize_dataset_record(scene_data if isinstance(scene_data, dict) else {})
            for scene_name, scene_data in parsed_data.items()
        }

        existing = await self.get_by_case_step(
            case_id=case_id,
            step_id=step_id,
            step_code=step_code,
            on_error=False,
            state__not=1
        )
        cache_key = make_cache_key(case_id, step_code)
        if existing:
            return await self.update_data_source(
                AutoTestDataSourceUpdate(
                    data_source_id=existing.id,
                    case_id=case_id,
                    case_code=case_code,
                    step_id=step_id,
                    step_code=step_code,
                    file_name=file_name,
                    file_path=file_path,
                    file_hash=file_hash,
                    file_desc=file_desc,
                    cache_key=cache_key,
                    dataset=normalized_dataset,
                    dataset_names=dataset_names if dataset_names is not None else (existing.dataset_names or []),
                    dataframe=dataframe if dataframe is not None else (existing.dataframe or []),
                    axis=axis,
                    updated_user=created_user,
                ),
            )

        return await self.create_data_source(
            AutoTestDataSourceCreate(
                case_id=case_id,
                case_code=case_code,
                step_id=step_id,
                step_code=step_code,
                file_name=file_name or "",
                file_path=file_path or "",
                file_hash=file_hash or "",
                file_desc=file_desc,
                cache_key=cache_key,
                dataset=normalized_dataset,
                dataset_names=dataset_names or [],
                dataframe=dataframe or [],
                axis=axis,
                created_user=created_user,
            )
        )

    async def copy_data_source_for_step(
            self,
            case_id: int,
            case_code: str,
            step_id: int,
            step_code: str,
            source_data_source_id: int,
    ) -> Optional[int]:
        """
        将源数据源复制为新步骤的独立数据源，仅复制解析数据(dataset/dataframe/dataset_names/axis)，文件字段全部置空。

        :param case_id: 新步骤所属用例主键
        :param case_code: 新步骤所属用例标识代码
        :param step_id: 新步骤主键
        :param step_code: 新步骤标识代码
        :param source_data_source_id: 源数据源主键ID
        :return: 新数据源主键ID；源数据源不存在时返回None
        """
        if not case_id or not (step_code or "").strip():
            error_message: str = "复制数据源失败, 参数[case_id, step_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        source = await self.get_by_id(data_source_id=source_data_source_id, on_error=False, state__not=1)
        if not source:
            return None
        new_record = await self.create(
            {
                "case_id": case_id,
                "case_code": case_code,
                "step_id": step_id,
                "step_code": step_code,
                "cache_key": make_cache_key(case_id, step_code),
                "dataset": source.dataset,
                "dataset_names": source.dataset_names or [],
                "dataframe": source.dataframe or [],
                "axis": source.axis,
                "file_name": None,
                "file_desc": None,
                "file_path": None,
                "file_hash": None,
            }
        )
        return new_record.id


async def delete_step_create(case_id: int, step_code_list: List[str]) -> None:
    """
    硬删除指定步骤的数据源与生成记录，并清理关联本地文件。

    :param case_id: 用例主键(用于定位上传目录)
    :param step_code_list: 待清理的步骤标识列表
    :return: None
    """
    instance_list = await AutoTestDataSourceModel.filter(step_code__in=step_code_list).all()
    steps_info = await AutoTestDataCreateModel.filter(step_code__in=step_code_list).all()
    await AutoTestDataSourceModel.filter(step_code__in=step_code_list).delete()
    await AutoTestDataCreateModel.filter(step_code__in=step_code_list).delete()
    for instance in instance_list:
        if instance.file_path and await aos.path.exists(instance.file_path):
            await aos.remove(instance.file_path)
    LOGGER.warning(f"删除更新后多余步骤: [case_id={case_id}, step_code__in={list(step_code_list)}]关联数据已被清理")
    for step_info in steps_info:
        if step_info and step_info.file_name:
            file_path = os.path.join(PROJECT_CONFIG.OUTPUT_UPLOAD_DIR, "autotest", str(case_id), step_info.file_name)
            if await aos.path.exists(file_path):
                await aos.remove(file_path)
        if step_info and step_info.file_path and await aos.path.exists(step_info.file_path):
            await aos.remove(step_info.file_path)
