# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_source2_crud
@DateTime: 2026/4/10 15:44
"""
import os
import traceback
from typing import List, Optional, Dict, Any

import aiofiles.os as aos
from tortoise.exceptions import FieldError
from tortoise.expressions import Q

from backend.applications.aotutest.models.autotest_model import AutoTestApiDataCreateInfo, AutoTestApiDataSourceInfo
from backend.applications.aotutest.schemas.autotest_data_generate_schema import AutoTestApiDataCreateCreate, AutoTestApiDataCreateUpdate
from backend.applications.aotutest.schemas.autotest_data_source_schema import AutoTestDataSourceCreate, AutoTestDataSourceUpdate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER, PROJECT_CONFIG
from backend.core.exceptions import DataAlreadyExistsException, NotFoundException, ParameterException


class AutoTestApiDataSourceCrud(ScaffoldCrud[AutoTestApiDataSourceInfo, AutoTestDataSourceCreate, AutoTestDataSourceUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestApiDataSourceInfo)

    async def get_by_code(self, step_code: str, on_error: bool = False) -> Optional[AutoTestApiDataSourceInfo]:
        if not step_code:
            error_message: str = "查询数据源信息失败, 参数(step_code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(step_code=step_code, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询数据源信息失败, 数据源(step_code={step_code})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_case(self, case_id: int, on_error: bool = False) -> Optional[AutoTestApiDataSourceInfo]:
        if not case_id:
            error_message: str = "查询数据源信息失败, 参数(case_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(case_id=case_id, file_hash__not='', state__not=1).order_by("-id").first()
        if not instance and on_error:
            error_message: str = f"查询数据源信息失败, 数据源(case_id={case_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_hash(self, file_hash: str, on_error: bool = False) -> Optional[AutoTestApiDataSourceInfo]:
        if not file_hash:
            error_message: str = "查询数据源信息失败, 参数(file_hash)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(file_hash=file_hash, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询数据源信息失败, 数据源(file_hash={file_hash})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def create_data_source(self, data_in: AutoTestDataSourceCreate) -> AutoTestApiDataSourceInfo:
        try:
            instance = await  AUTOTEST_API_DATA_SOURCE_CRUD.get_by_code(data_in.step_code)
            if instance:
                instance = await self.update_data_source(
                    data_in=AutoTestDataSourceUpdate(
                        id=instance.id,
                        case_id=data_in.case_id,
                        step_code=data_in.step_code,
                        file_name=data_in.file_name,
                        file_hash=data_in.file_hash,
                        file_path=data_in.file_path,
                        file_code=data_in.file_code,
                        dataset=data_in.dataset,
                        dataset_names=data_in.dataset_names,
                        cache_key=data_in.cache_key,
                    )
                )
                return instance
            data_dict = data_in.model_dump(exclude_none=True, exclude_unset=True)
            instance = await self.create(data_dict)
            return instance
        except Exception as e:
            error_message: str = f"新增数据源明细信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataAlreadyExistsException(message=error_message) from e

    async def update_data_source(self, data_in: AutoTestDataSourceUpdate) -> AutoTestApiDataSourceInfo:

        try:
            data_dict = data_in.model_dump(exclude_none=True, exclude_unset=True)
            instance = await self.update(id=data_in.id, obj_in=data_dict)
            return instance
        except Exception as e:
            error_message: str = f"更新数据源明细信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataAlreadyExistsException(message=error_message) from e

    async def delete_data_source(self, step_code: Optional[str] = None) -> AutoTestApiDataSourceInfo:
        if not step_code:
            error_message: str = f"参数缺失, 删除数据源信息时必须传递step_code"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 业务层验证：检查明细信息是否存在
        instance = await self.get_by_code(step_code=step_code, on_error=False)

        if not instance:
            error_message: str = (
                f"根据(step_code={step_code})条件检查失败, "
                f"数据源信息不存在"
            )
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)

        instance.state = 1
        await instance.save()
        return instance

    async def select_data_source(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询数据源信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def query_dataset(self, case_id: str, step_code: str, dataset_name: Optional[str] = None) -> Dict[str, Any]:
        if not case_id or not step_code:
            error_message: str = "查询数据源信息失败, 参数(case_id、step_code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        dataset_name: str = dataset_name.strip()
        condition: Dict[str, Any] = {"case_id": case_id, "step_code": step_code}
        LOGGER.info(f"查询数据源信息条件(此时不判断dataset_name是否存在于dataset中)：{condition}")
        source_instance: AutoTestApiDataSourceInfo = await self.model.filter(**condition, state__not=1).first()
        if not source_instance:
            error_message: str = f"查询数据源信息失败, 暂无满足({condition})查询条件的记录"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)

        source_dict: Dict[str, Any] = await source_instance.to_dict(include_fields=["dataset"])
        if not dataset_name:
            return source_dict

        dataset: Dict[str, Any] = source_dict.get("dataset") or {}
        if dataset:
            single_dataset = dataset.get(dataset_name)
            if not single_dataset:
                error_message: str = f"查询数据源信息失败, 指定场景名称({dataset_name})下数据为空"
                raise NotFoundException(message=error_message)
            source_dict["dataset"] = single_dataset

        return source_dict


class AutoTestApiDataCreateCrud(
    ScaffoldCrud[AutoTestApiDataCreateInfo, AutoTestApiDataCreateCreate, AutoTestApiDataCreateUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestApiDataCreateInfo)

    async def get_by_code(self, create_code: str, on_error: bool = False) -> Optional[AutoTestApiDataCreateInfo]:
        if not create_code:
            error_message: str = "查询数据源生成信息失败, 参数(create_code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(create_code=create_code, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询数据源生成信息失败, 数据源(create_code={create_code})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_step(self, step_code: str, on_error: bool = False) -> List[Optional[AutoTestApiDataCreateInfo]]:
        if not step_code:
            error_message: str = "查询数据源生成信息失败, 参数(step_code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(step_code=step_code, state__not=1).order_by("-id").limit(3)
        if not instance and on_error:
            error_message: str = f"查询数据源生成信息失败, 数据源(step_code={step_code})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_hash(self, file_hash: str, on_error: bool = False) -> Optional[AutoTestApiDataCreateInfo]:
        if not file_hash:
            error_message: str = "查询数据源生成信息失败, 参数(file_hash)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(file_hash=file_hash, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询数据源生成信息失败, 数据源(file_hash={file_hash})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def create_data_create(self, data_in: AutoTestApiDataCreateCreate) -> AutoTestApiDataCreateInfo:
        try:
            instance = await self.get_by_hash(file_hash=data_in.file_hash)
            if instance:
                instance = await self.update_data_create(
                    data_in=AutoTestApiDataCreateUpdate(
                        id=instance.id,
                        create_status="0",
                        file_path=data_in.file_path,
                    )
                )
                return instance
            data_dict = data_in.model_dump(exclude_none=True, exclude_unset=True)
            instance = await self.create(data_dict)
            return instance
        except Exception as e:
            error_message: str = f"新增数据源生成信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataAlreadyExistsException(message=error_message) from e

    async def update_data_create(self, data_in: AutoTestApiDataCreateUpdate) -> AutoTestApiDataCreateInfo:
        try:
            data_dict = data_in.model_dump(exclude_none=True, exclude_unset=True)
            instance = await self.update(id=data_in.id, obj_in=data_dict)
            return instance
        except Exception as e:
            error_message: str = f"新增明细信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataAlreadyExistsException(message=error_message) from e

    async def delete_data_create(
            self,
            create_code: Optional[str] = None,
    ) -> AutoTestApiDataCreateInfo:
        if not id:
            error_message: str = f"参数缺失, 删除数据源生成信息时必须传递id"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 业务层验证：检查明细信息是否存在
        instance = await self.get_by_code(create_code=create_code, on_error=False)

        if not instance:
            error_message: str = (
                f"根据(create_code={create_code})条件检查失败, "
                f"数据源信息不存在"
            )
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)

        instance.state = 1
        await instance.save()
        return instance

    async def select_data_source(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询数据源生成信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e


async def delete_step_create(case_id, step_code_list):
    await AUTOTEST_API_DATA_SOURCE_CRUD.model.filter(step_code__in=step_code_list).update(state=1)
    await AUTOTEST_API_DATA_CREATE_CRUD.model.filter(step_code__in=step_code_list, state__not=1).update(state=1)
    instance_list = await AUTOTEST_API_DATA_SOURCE_CRUD.model.filter(step_code__in=step_code_list).all()
    for instance in instance_list:
        if not instance.file_hash.endswith("X"):
            if await aos.path.exists(instance.file_hash):
                await aos.remove(instance.file_hash)
    LOGGER.warning(
        f"AUTOTEST_API_DATA_SOURCE_CRUD 删除更新后多余步骤: "
        f"步骤(case_id={case_id}, step_code__in={list(step_code_list)})已被清理"
    )
    steps_info = await AUTOTEST_API_DATA_CREATE_CRUD.model.filter(step_code__in=step_code_list).all()
    for step_info in steps_info:
        if step_info:
            file_path = os.path.join(PROJECT_CONFIG.OUTPUT_UPLOAD_DIR, "autotest", str(case_id), step_info.file_name)
            if await aos.path.exists(file_path):
                await aos.remove(file_path)
            if await aos.path.exists(step_info.file_path):
                await aos.remove(step_info.file_path)
    LOGGER.warning(
        f"AUTOTEST_API_DATA_CREATE_CRUD 删除更新后多余步骤: "
        f"步骤(case_id={case_id}, step_code__in={list(step_code_list)})已被清理"
    )


AUTOTEST_API_DATA_SOURCE_CRUD = AutoTestApiDataSourceCrud()
AUTOTEST_API_DATA_CREATE_CRUD = AutoTestApiDataCreateCrud()
