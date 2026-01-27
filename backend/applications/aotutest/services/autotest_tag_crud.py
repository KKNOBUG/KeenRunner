# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_tag_crud
@DateTime: 2026/1/16 16:35
"""
import traceback
from typing import Optional, Dict, Any, List, Union

from tortoise.exceptions import DoesNotExist, IntegrityError, FieldError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from backend import LOGGER
from backend.applications.aotutest.models.autotest_model import AutoTestApiTagInfo
from backend.applications.aotutest.schemas.autotest_tag_schema import AutoTestApiTagCreate, AutoTestApiTagUpdate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)


class AutoTestApiTagCrud(ScaffoldCrud[AutoTestApiTagInfo, AutoTestApiTagCreate, AutoTestApiTagUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestApiTagInfo)

    async def get_by_id(self, tag_id: int, on_error: bool = False) -> Optional[AutoTestApiTagInfo]:
        if not tag_id:
            error_message: str = "查询标签信息失败, 参数(tag_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(id=tag_id, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询标签信息失败, 用例(id={tag_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_ids(
            self, tag_ids: List[int], on_error: bool = False, return_obj: bool = False
    ) -> Optional[Union[bool, List[AutoTestApiTagInfo]]]:
        if not tag_ids or not isinstance(tag_ids, list):
            error_message: str = "查询标签信息失败, 参数(tag_id)不允许为空且必须是List[int]类型"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        existing_tags = await self.model.filter(id__in=tag_ids, state__not=1).values_list("id", flat=True)
        missing_tags: set = set(tag_ids) - set(existing_tags)
        if missing_tags:
            error_message: str = f"查询标签信息失败, 标签({missing_tags})不存在"
            LOGGER.error(error_message)
            if on_error:
                raise NotFoundException(message=error_message)
            return False
        if return_obj:
            return await self.model.filter(id__in=tag_ids, state__not=1).all()
        return True

    async def get_by_code(self, tag_code: str, on_error: bool = False) -> Optional[AutoTestApiTagInfo]:
        if not tag_code:
            error_message: str = "查询标签信息失败, 参数(tag_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(tag_code=tag_code, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询标签信息失败, 用例(code={tag_code})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True,
            on_error: bool = False
    ) -> Optional[Union[AutoTestApiTagInfo, List[AutoTestApiTagInfo]]]:
        try:
            stmt: QuerySet = self.model.filter(**conditions, state__not=1)
            instances = await (stmt.first() if only_one else stmt.all())
        except FieldError as e:
            error_message: str = f"查询标签信息异常, 错误描述: {e}"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        except Exception as e:
            error_message: str = f"查询标签信息发生未知异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

        if not instances and on_error:
            error_message: str = f"查询标签信息失败, 条件{conditions}不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instances

    async def create_tag(self, tag_in: AutoTestApiTagCreate) -> AutoTestApiTagInfo:
        tag_type: str = tag_in.tag_type.value
        tag_mode: str = tag_in.tag_mode
        tag_name: str = tag_in.tag_name
        tag_project: int = tag_in.tag_project

        # 业务层验证：检查应用是否存在
        from backend.applications.aotutest.services.autotest_project_crud import AUTOTEST_API_PROJECT_CRUD
        await AUTOTEST_API_PROJECT_CRUD.get_by_id(project_id=tag_project, on_error=True)

        # 业务层验证: 检查标签类型是否存在
        existing_tag = await self.model.filter(
            tag_type=tag_type,
            tag_mode=tag_mode,
            tag_name=tag_name,
            state__not=1
        ).first()
        if existing_tag:
            error_message: str = f"标签(tag_type={tag_type}, tag_mode={tag_mode}, tag_name={tag_name})已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        try:
            tag_dict: Dict[str, Any] = tag_in.model_dump(exclude_none=True, exclude_unset=True)
            instance = await self.create(tag_dict)
            return instance
        except IntegrityError as e:
            error_message: str = f"新增标签信息失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_tag(self, tag_in: AutoTestApiTagUpdate) -> AutoTestApiTagInfo:
        tag_id: Optional[int] = tag_in.tag_id
        tag_code: Optional[str] = tag_in.tag_code
        if tag_id:
            instance = await self.get_by_id(tag_id=tag_id, on_error=True)
        else:
            instance = await self.get_by_code(tag_code=tag_code, on_error=True)
            tag_id = instance.id

        update_dict: Dict[str, Any] = tag_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"tag_id", "tag_code"}
        )
        if "tag_name" in update_dict or "tag_mode" in update_dict or "tag_name" in update_dict:
            tag_type: str = update_dict.get("tag_type", instance.tag_type)
            tag_mode: str = update_dict.get("tag_mode", instance.tag_mode)
            tag_name: str = update_dict.get("tag_name", instance.tag_name)
            existing_tag = await self.model.filter(
                tag_type=tag_type,
                tag_mode=tag_mode,
                tag_name=tag_name,
                state__not=1
            ).exclude(id=tag_id).first()
            if existing_tag:
                error_message: str = f"标签(tag_type={tag_type}, tag_mode={tag_mode}, tag_name={tag_name})已存在"
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)

        try:
            instance = await self.update(id=tag_id, obj_in=update_dict)
            return instance
        except DoesNotExist as e:
            error_message: str = f"更新标签信息失败, 标签(id={tag_id}或code={tag_code})不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message)
        except IntegrityError as e:
            error_message: str = f"更新标签信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_tag(self, tag_id: Optional[int] = None, tag_code: Optional[str] = None) -> AutoTestApiTagInfo:
        if tag_id:
            instance = await self.get_by_id(tag_id=tag_id, on_error=True)
        else:
            instance = await self.get_by_code(tag_code=tag_code, on_error=True)

        from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
        cases_count = await AUTOTEST_API_CASE_CRUD.model.filter(case_tags__in=tag_id, state__not=1).count()
        if cases_count > 0:
            error_message: str = f"删除标签信息失败, 标签(id={instance.id})被{cases_count}个用例关联"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        instance.state = 1
        await instance.save()
        return instance

    async def select_tags(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询标签信息失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e


AUTOTEST_API_TAG_CRUD = AutoTestApiTagCrud()
