# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_env_crud
@DateTime: 2026/1/2 17:42
"""
from typing import Optional, Dict, Any

from tortoise.exceptions import IntegrityError, FieldError, DoesNotExist
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from backend.applications.aotutest.models.autotest_model import AutoTestApiEnvInfo
from backend.applications.aotutest.schemas.autotest_env_schema import (
    AutoTestApiEnvCreate,
    AutoTestApiEnvUpdate
)
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)


class AutoTestApiEnvCrud(ScaffoldCrud[AutoTestApiEnvInfo, AutoTestApiEnvCreate, AutoTestApiEnvUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestApiEnvInfo)

    async def get_by_id(self, env_id: int, on_error: bool = False) -> Optional[AutoTestApiEnvInfo]:
        if not env_id:
            raise ParameterException(message="参数(env_id)不允许为空")
        instance = await self.model.filter(id=env_id, state__not=1).first()
        if not instance and on_error:
            raise NotFoundException(message=f"环境(id={env_id})不存在")
        return instance

    async def get_by_code(self, env_code: str, on_error: bool = False) -> Optional[AutoTestApiEnvInfo]:
        if not env_code:
            raise ParameterException(message="参数(env_code)不允许为空")
        instance = await self.model.filter(env_code=env_code, state__not=1).first()
        if not instance and on_error:
            raise NotFoundException(message=f"环境(code={env_code})不存在")
        return instance

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True,
            on_error: bool = False
    ) -> Optional[AutoTestApiEnvInfo]:
        try:
            stmt: QuerySet = self.model.filter(**conditions, state__not=1)
            instances = await (stmt.first() if only_one else stmt.all())
        except FieldError as e:
            raise ParameterException(message=f"查询'环境'异常, 错误描述: {e}")

        if not instances and on_error:
            raise NotFoundException(message=f"按条件{conditions}查询'环境'无记录")
        return instances

    async def create_env(self, env_in: AutoTestApiEnvCreate) -> AutoTestApiEnvInfo:
        env_name: str = env_in.env_name
        project_id: int = env_in.project_id
        # todo: 是否需要强制关联应用，应用不存在时不可以新增环境？
        existing_env = await self.model.filter(env_name=env_name, project_id=project_id, state__not=1).first()
        if existing_env:
            raise DataAlreadyExistsException(message=f"应用(id={project_id})下环境(name={env_name})已存在")

        try:
            env_dict: Dict[str, Any] = env_in.model_dump(exclude_none=True, exclude_unset=True)
            instance = await self.create(obj_in=env_dict)
            return instance
        except IntegrityError as e:
            raise DataBaseStorageException(message=f"创建环境失败, 违法约束规则: {e}")

    async def update_env(self, env_in: AutoTestApiEnvUpdate) -> AutoTestApiEnvInfo:
        env_id: Optional[int] = env_in.env_id
        env_code: Optional[str] = env_in.env_code
        if env_id:
            instance = await self.get_by_id(env_id=env_id, on_error=True)
        else:
            instance = await self.get_by_code(env_code=env_code, on_error=True)
            env_id: int = instance.id

        update_dict: Dict[str, Any] = env_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"env_id", "env_code"}
        )
        if "env_name" in update_dict or "project_id" in update_dict:
            env_name: str = update_dict.get("env_name", instance.env_name)
            project_id: int = update_dict.get("project_id", instance.project_id)
            existing_env = await self.model.filter(
                env_name=env_name,
                project_id=project_id,
                state__not=1
            ).exclude(id=env_id).first()
            if existing_env:
                raise DataAlreadyExistsException(message=f"应用(id={project_id})下环境(name={env_name})已存在")
        try:
            instance = await self.update(id=env_id, obj_in=update_dict)
            return instance
        except DoesNotExist:
            raise NotFoundException(message=f"环境(id={env_id}或code={env_code})不存在")
        except IntegrityError as e:
            raise DataBaseStorageException(message=f"更新环境失败, 违反约束规则: {e}")

    async def delete_env(self, env_id: Optional[int] = None, env_code: Optional[str] = None) -> AutoTestApiEnvInfo:
        if env_id:
            instance = await self.get_by_id(env_id=env_id, on_error=True)
        else:
            instance = await self.get_by_code(env_code=env_code, on_error=True)

        # todo: 是否同步删除引用该环境的用例

        instance.state = 1
        await instance.save()
        return instance

    async def select_envs(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            raise ParameterException(message=f"查询'环境'异常, 错误描述: {e}")


AUTOTEST_API_ENV_CRUD = AutoTestApiEnvCrud()
