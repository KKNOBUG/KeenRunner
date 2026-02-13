# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_project_crud
@DateTime: 2026/1/2 18:01
"""
import traceback
from typing import Optional, Dict, Any, Union, List

from tortoise.exceptions import IntegrityError, FieldError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from backend import LOGGER
from backend.applications.aotutest.models.autotest_model import AutoTestApiProjectInfo
from backend.applications.aotutest.schemas.autotest_project_schema import (
    AutoTestApiProjectCreate,
    AutoTestApiProjectUpdate
)
from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)


class AutoTestApiProjectCrud(ScaffoldCrud[AutoTestApiProjectInfo, AutoTestApiProjectCreate, AutoTestApiProjectUpdate]):
    """自动化测试应用（项目）的 CRUD 服务，负责项目的增删改查。"""

    def __init__(self):
        """初始化 CRUD，绑定模型 AutoTestApiProjectInfo。"""
        super().__init__(model=AutoTestApiProjectInfo)

    async def get_by_id(self, project_id: int, on_error: bool = False) -> Optional[AutoTestApiProjectInfo]:
        """根据项目主键 ID 查询单条项目（排除已删除）。

        :param project_id: 项目主键 ID。
        :param on_error: 为 True 时若未找到则抛出 NotFoundException。
        :returns: 项目实例或 None。
        :raises ParameterException: 当 project_id 为空时。
        :raises NotFoundException: 当 on_error 为 True 且记录不存在时。
        """
        if not project_id:
            error_message: str = "查询应用信息失败, 参数(project_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(id=project_id, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询应用信息失败, 应用(id={project_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, project_code: str, on_error: bool = False) -> Optional[AutoTestApiProjectInfo]:
        """根据项目标识代码查询单条项目（排除已删除）。

        :param project_code: 项目标识代码。
        :param on_error: 为 True 时若未找到则抛出 NotFoundException。
        :returns: 项目实例或 None。
        :raises ParameterException: 当 project_code 为空时。
        :raises NotFoundException: 当 on_error 为 True 且记录不存在时。
        """
        if not project_code:
            error_message: str = "查询应用信息失败, 参数(project_code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(project_code=project_code, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询应用信息失败, 应用(code={project_code})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_name(self, project_name: str, on_error: bool = False) -> Optional[AutoTestApiProjectInfo]:
        """根据项目名称查询单条项目（排除已删除）。

        :param project_name: 项目名称。
        :param on_error: 为 True 时若未找到则抛出 NotFoundException。
        :returns: 项目实例或 None。
        :raises ParameterException: 当 project_name 为空时。
        :raises NotFoundException: 当 on_error 为 True 且记录不存在时。
        """
        if not project_name:
            error_message: str = "查询应用信息失败, 参数(project_name)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(project_name=project_name, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询应用信息失败, 应用(name={project_name})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True,
            on_error: bool = False
    ) -> Optional[Union[AutoTestApiProjectInfo, List[AutoTestApiProjectInfo]]]:
        """根据条件查询项目（排除已删除）。

        :param conditions: 查询条件字典。
        :param only_one: 为 True 时返回单条记录，否则返回列表。
        :param on_error: 为 True 时若未找到则抛出 NotFoundException。
        :returns: 单条项目、项目列表或 None。
        :raises ParameterException: 条件非法或查询异常时。
        :raises NotFoundException: 当 on_error 为 True 且无匹配记录时。
        """
        try:
            stmt: QuerySet = self.model.filter(**conditions, state__not=1)
            instances = await (stmt.first() if only_one else stmt.all())
        except FieldError as e:
            error_message: str = f"查询应用信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
        except Exception as e:
            error_message: str = f"查询应用信息发生未知异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

        if not instances and on_error:
            error_message: str = f"查询应用信息失败, 条件{conditions}不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instances

    async def create_project(self, project_in: AutoTestApiProjectCreate) -> AutoTestApiProjectInfo:
        """创建项目，校验项目名称全局唯一。

        :param project_in: 项目创建 schema。
        :returns: 创建后的项目实例。
        :raises DataAlreadyExistsException: 项目名已存在时。
        :raises DataBaseStorageException: 违反数据库约束时。
        """
        project_name: str = project_in.project_name

        # 业务层验证：检查应用名称是否重复
        project_instance = await self.get_by_name(project_name=project_name, on_error=False)
        if project_instance:
            error_message: str = f"根据(project_name={project_name})条件检查应用信息失败, 应用名称不允许重复"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

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
            error_message: str = f"新增应用信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_project(self, project_in: AutoTestApiProjectUpdate) -> AutoTestApiProjectInfo:
        """更新项目，支持按 project_id 或 project_code 定位，并校验项目名唯一。

        :param project_in: 项目更新 schema。
        :returns: 更新后的项目实例。
        :raises NotFoundException: 项目不存在时。
        :raises DataAlreadyExistsException: 项目名重复时。
        :raises DataBaseStorageException: 违反约束时。
        """
        project_id: Optional[int] = project_in.project_id
        project_code: Optional[str] = project_in.project_code
        # 业务层验证：检查应用是否存在
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

        # 业务层验证：检查应用名称是否重复
        if "project_name" in update_dict:
            project_name: str = update_dict.get("project_name", instance.project_name)
            existing_project = await self.model.filter(
                project_name=project_name,
                state__not=1
            ).exclude(id=project_id).first()
            if existing_project:
                error_message: str = f"根据(project_name={project_name})条件检查应用信息失败, 应用名称不允许重复"
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)

        try:
            instance = await self.update(id=project_id, obj_in=update_dict)
            return instance
        except IntegrityError as e:
            error_message: str = f"更新应用信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_project(
            self,
            project_id: Optional[int] = None,
            project_code: Optional[str] = None
    ) -> AutoTestApiProjectInfo:
        """软删除项目（state=1），需无关联用例。

        :param project_id: 项目主键 ID，与 project_code 二选一。
        :param project_code: 项目标识代码，与 project_id 二选一。
        :returns: 软删除后的项目实例。
        :raises NotFoundException: 项目不存在时。
        :raises DataBaseStorageException: 存在关联用例时。
        """
        # 业务层验证：检查应用是否存在
        if project_id:
            instance = await self.get_by_id(project_id=project_id, on_error=True)
        else:
            instance = await self.get_by_code(project_code=project_code, on_error=True)

        # 业务层验证：检查应用信息是否存在关联
        project_id = instance.id
        cases_count = await AUTOTEST_API_CASE_CRUD.model.filter(case_project=project_id, state__not=1).count()
        if cases_count > 0:
            error_message: str = (
                f"根据(case_project={project_id})条件检查用例信息失败, "
                f"应用(name={instance.project_name})存在{cases_count}个用例, 无法直接删除"
            )
            LOGGER.error(error_message)
            raise DataBaseStorageException(message=error_message)

        instance.state = 1
        await instance.save()
        return instance

    async def select_projects(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        """分页查询项目列表。

        :param search: Tortoise Q 查询条件。
        :param page: 页码。
        :param page_size: 每页条数。
        :param order: 排序字段列表。
        :returns: 由 (总条数, 当前页记录列表) 组成的元组。
        :raises ParameterException: 查询条件非法导致 FieldError 时。
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询应用信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e


AUTOTEST_API_PROJECT_CRUD = AutoTestApiProjectCrud()
