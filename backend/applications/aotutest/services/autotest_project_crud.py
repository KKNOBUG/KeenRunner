# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_project_crud
@DateTime: 2026/1/2 18:01
"""
from typing import Optional, Dict, Any

from tortoise.exceptions import IntegrityError, FieldError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from backend.applications.aotutest.models.autotest_model import AutoTestApiProjectInfo
from backend.applications.aotutest.schemas.autotest_project_schema import (
    AutoTestApiProjectCreate,
    AutoTestApiProjectUpdate
)
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)


class AutoTestApiProjectCrud(ScaffoldCrud[AutoTestApiProjectInfo, AutoTestApiProjectCreate, AutoTestApiProjectUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestApiProjectInfo)

    async def get_by_id(self, project_id: int, on_error: bool = False) -> Optional[AutoTestApiProjectInfo]:
        if not project_id:
            raise ParameterException(message="参数(project_id)不允许为空")
        instance = await self.model.filter(id=project_id, state__not=1).first()
        if not instance and on_error:
            raise NotFoundException(message=f"应用(id={project_id})不存在")
        return instance

    async def get_by_code(self, project_code: str, on_error: bool = False) -> Optional[AutoTestApiProjectInfo]:
        if not project_code:
            raise ParameterException(message="参数(project_code)不允许为空")
        instance = await self.model.filter(project_code=project_code, state__not=1).first()
        if not instance and on_error:
            raise NotFoundException(message=f"应用(code={project_code})不存在")
        return instance

    async def get_by_name(self, project_name: str, on_error: bool = False) -> Optional[AutoTestApiProjectInfo]:
        if not project_name:
            raise ParameterException(message="参数(project_name)不允许为空")
        instance = await self.model.filter(project_name=project_name, state__not=1).first()
        if not instance and on_error:
            raise NotFoundException(message=f"应用(name={project_name})不存在")
        return instance

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True,
            on_error: bool = False
    ) -> Optional[AutoTestApiProjectInfo]:
        try:
            stmt: QuerySet = self.model.filter(**conditions, state__not=1)
            instances = await (stmt.first() if only_one else stmt.all())
        except FieldError as e:
            raise ParameterException(message=f"查询'应用'异常, 错误描述: {e}")

        if not instances and on_error:
            raise NotFoundException(message=f"按条件{conditions}查询'应用'无记录")
        return instances

    async def create_project(self, project_in: AutoTestApiProjectCreate) -> AutoTestApiProjectInfo:
        project_name: str = project_in.project_name
        project_instance = await self.get_by_name(project_name=project_name, on_error=False)
        if project_instance:
            raise DataAlreadyExistsException(message=f"应用(name={project_name})已存在")
        try:
            if project_in.project_dev_owners is not None:
                project_in.project_dev_owners = sorted(project_in.project_dev_owners, key=str.lower)
            if project_in.project_developers is not None:
                project_in.project_developers = sorted(project_in.project_developers, key=str.lower)
            if project_in.project_test_owners is not None:
                project_in.project_test_owners = sorted(project_in.project_test_owners, key=str.lower)
            if project_in.project_testers is not None:
                project_in.project_testers = sorted(project_in.project_testers, key=str.lower)
            project_dict: Dict[str, Any] = project_in.model_dump(exclude_none=True, exclude_unset=True)
            instance = await self.create(obj_in=project_dict)
            return instance
        except IntegrityError as e:
            raise DataBaseStorageException(message=f"创建应用失败, 违法约束规则: {e}")

    async def update_project(self, project_in: AutoTestApiProjectUpdate) -> AutoTestApiProjectInfo:
        project_id: Optional[int] = project_in.project_id
        project_code: Optional[str] = project_in.project_code
        if project_id:
            instance = await self.get_by_id(project_id=project_id, on_error=True)
        else:
            instance = await self.get_by_code(project_code=project_code, on_error=True)
            project_id: int = instance.id

        update_dict: Dict[str, Any] = project_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"project_id", "project_code"}
        )
        if "project_name" in update_dict:
            project_name: str = update_dict.get("project_name", instance.project_name)
            existing_project = await self.model.filter(
                project_name=project_name,
                state__not=1
            ).exclude(id=project_id).first()
            if existing_project:
                raise DataAlreadyExistsException(message=f"应用(name={project_name})已存在")
        try:
            instance = await self.update(id=project_id, obj_in=update_dict)
            return instance
        except IntegrityError as e:
            raise DataBaseStorageException(message=f"更新应用失败, 违反约束规则: {e}")

    async def delete_project(
            self,
            project_id: Optional[int] = None,
            project_code: Optional[str] = None
    ) -> AutoTestApiProjectInfo:
        if project_id:
            instance = await self.get_by_id(project_id=project_id, on_error=True)
        else:
            instance = await self.get_by_code(project_code=project_code, on_error=True)

        # todo: 是否需要一键删除应用所关联的用例

        instance.state = 1
        await instance.save()
        return instance

    async def select_projects(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            raise ParameterException(message=f"查询'应用'异常, 错误描述: {e}")


AUTOTEST_API_PROJECT_CRUD = AutoTestApiProjectCrud()
