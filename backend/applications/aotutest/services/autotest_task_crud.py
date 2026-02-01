# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_task_crud
@DateTime: 2026/1/31 12:42
"""
import traceback
from typing import Optional, Dict, Any, List
from typing import Union

from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.exceptions import FieldError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from backend import LOGGER
from backend.applications.aotutest.models.autotest_model import AutoTestApiTaskInfo
from backend.applications.aotutest.schemas.autotest_task_schema import AutoTestApiTaskCreate, AutoTestApiTaskUpdate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)
from backend.core.exceptions.base_exceptions import ParameterException


class AutoTestApiTaskCrud(ScaffoldCrud[AutoTestApiTaskInfo, AutoTestApiTaskCreate, AutoTestApiTaskUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestApiTaskInfo)

    async def get_by_id(self, task_id: int, on_error: bool = False) -> Optional[AutoTestApiTaskInfo]:
        if not task_id:
            error_message: str = "查询任务信息失败, 参数(task_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(id=task_id, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询任务信息失败, 任务(id={task_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, task_code: str, on_error: bool = False) -> Optional[AutoTestApiTaskInfo]:
        if not task_code:
            error_message: str = "查询任务信息失败, 参数(task_code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(task_code=task_code, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询任务信息失败, 任务(code={task_code})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True,
            on_error: bool = False
    ) -> Optional[Union[AutoTestApiTaskInfo, List[AutoTestApiTaskInfo]]]:
        try:
            stmt: QuerySet = self.model.filter(**conditions, state__not=1)
            instances = await (stmt.first() if only_one else stmt.all())
        except FieldError as e:
            error_message: str = f"查询任务信息异常, 错误描述: {e}"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        except Exception as e:
            error_message: str = f"查询任务信息发生未知异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

        if not instances and on_error:
            error_message: str = f"查询任务信息失败, 条件{conditions}不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instances

    async def create_task(self, task_in: AutoTestApiTaskCreate) -> AutoTestApiTaskInfo:
        task_env: str = task_in.task_env
        task_name: str = task_in.task_name
        task_project: int = task_in.task_project

        # 业务层验证：检查应用是否存在
        from backend.applications.aotutest.services.autotest_project_crud import AUTOTEST_API_PROJECT_CRUD
        await AUTOTEST_API_PROJECT_CRUD.get_by_id(project_id=task_project, on_error=True)

        # 业务层验证：检查 (task_env, task_name, task_project) 唯一
        existing_task = await self.model.filter(
            task_env=task_env,
            task_name=task_name,
            task_project=task_project,
            state__not=1
        ).first()
        if existing_task:
            error_message: str = f"任务(task_env={task_env}, task_name={task_name}, task_project={task_project})已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        try:
            task_dict: Dict[str, Any] = task_in.model_dump(exclude_none=True, exclude_unset=True)
            if "task_scheduler" in task_dict and task_dict["task_scheduler"] is not None:
                task_dict["task_scheduler"] = task_dict["task_scheduler"].value
            instance = await self.create(task_dict)
            return instance
        except IntegrityError as e:
            error_message: str = f"新增任务信息失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_task(self, task_in: AutoTestApiTaskUpdate) -> AutoTestApiTaskInfo:
        task_id: Optional[int] = task_in.task_id
        task_code: Optional[str] = task_in.task_code
        if task_id:
            instance = await self.get_by_id(task_id=task_id, on_error=True)
        else:
            instance = await self.get_by_code(task_code=task_code, on_error=True)
            task_id = instance.id

        update_dict: Dict[str, Any] = task_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"task_id", "task_code"}
        )
        if "task_scheduler" in update_dict and update_dict["task_scheduler"] is not None:
            update_dict["task_scheduler"] = update_dict["task_scheduler"].value

        task_env = update_dict.get("task_env", instance.task_env)
        task_name = update_dict.get("task_name", instance.task_name)
        task_project = update_dict.get("task_project", instance.task_project)
        existing_task = await self.model.filter(
            task_env=task_env,
            task_name=task_name,
            task_project=task_project,
            state__not=1
        ).exclude(id=task_id).first()
        if existing_task:
            error_message: str = f"任务(task_env={task_env}, task_name={task_name}, task_project={task_project})已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        try:
            instance = await self.update(id=task_id, obj_in=update_dict)
            return instance
        except DoesNotExist as e:
            error_message: str = f"更新任务信息失败, 任务(id={task_id}或code={task_code})不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = f"更新任务信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_task(self, task_id: Optional[int] = None, task_code: Optional[str] = None) -> AutoTestApiTaskInfo:
        if task_id:
            instance = await self.get_by_id(task_id=task_id, on_error=True)
        else:
            instance = await self.get_by_code(task_code=task_code, on_error=True)

        instance.state = 1
        await instance.save()
        return instance

    async def set_task_enabled(self, task_id: int, enabled: bool = True) -> AutoTestApiTaskInfo:
        """设置是否启动调度（仅改 task_enabled，state 保留为软删除）。"""
        instance = await self.get_by_id(task_id=task_id, on_error=True)
        instance.task_enabled = enabled
        await instance.save(update_fields=["task_enabled"])
        return instance

    async def select_tasks(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询任务信息失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e


AUTOTEST_API_TASK_CRUD = AutoTestApiTaskCrud()
