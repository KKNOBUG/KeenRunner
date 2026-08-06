# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_project_crud
@DateTime: 2026/1/2 18:01
"""
import traceback
from typing import Optional, Dict, Any, List, Tuple

from tortoise.exceptions import IntegrityError, FieldError, DoesNotExist
from tortoise.expressions import Q

from backend.applications.aotutest.models.autotest_model import AutoTestApiProjectInfo, AutoTestApiEnvConfigInfo
from backend.applications.aotutest.schemas.autotest_project_schema import (
    AutoTestApiProjectCreate,
    AutoTestApiProjectUpdate,
    AutoTestApiProjectDelete,
)
from backend.applications.aotutest.services.autotest_case_crud import AutoTestApiCaseCrud
from backend.applications.aotutest.services.autotest_tag_crud import AutoTestApiTagCrud
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)


class AutoTestApiProjectCrud(ScaffoldCrud[AutoTestApiProjectInfo, AutoTestApiProjectCreate, AutoTestApiProjectUpdate]):

    def __init__(self):
        super().__init__(model=AutoTestApiProjectInfo)

    async def get_by_id(self, project_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestApiProjectInfo]:
        """
        根据主键ID查询应用。

        :param project_id: 应用主键ID
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 应用实例或None
        :raises ParameterException: project_id为空
        :raises NotFoundException: on_error为True且记录不存在
        """
        if not project_id:
            error_message: str = "查询应用信息失败, 参数[project_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(id=project_id, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询应用信息失败, 记录[id={project_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, project_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestApiProjectInfo]:
        """
        根据应用标识代码查询应用。

        :param project_code: 应用标识代码
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 应用实例或None
        :raises ParameterException: project_code为空
        :raises NotFoundException: on_error为True且记录不存在
        """
        if not project_code:
            error_message: str = "查询应用信息失败, 参数[project_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(project_code=project_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询应用信息失败, 记录[code={project_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_name(self, project_name: str, on_error: bool = False, **kwargs) -> Optional[AutoTestApiProjectInfo]:
        """
        根据应用名称查询应用。

        :param project_name: 应用名称
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 应用实例或None
        :raises ParameterException: project_name为空
        :raises NotFoundException: on_error为True且记录不存在
        """
        if not project_name:
            error_message: str = "查询应用信息失败, 参数[project_name]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(project_name=project_name, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询应用信息失败, 记录[name={project_name}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def create_project(self, project_in: AutoTestApiProjectCreate) -> AutoTestApiProjectInfo:
        """
        创建应用；若同名记录已存在则恢复并更新。

        :param project_in: 应用创建schema
        :return: 创建或恢复后的应用实例
        :raises DataBaseStorageException: 违反数据库约束
        """
        project_name: str = project_in.project_name

        # 业务层验证：检查应用名称是否存在
        existing_project: Optional[AutoTestApiProjectInfo] = await self.model.filter(project_name=project_name).first()
        if project_in.project_dev_owners is not None:
            project_in.project_dev_owners = sorted(project_in.project_dev_owners, key=str.lower)
        if project_in.project_developers is not None:
            project_in.project_developers = sorted(project_in.project_developers, key=str.lower)
        if project_in.project_test_owners is not None:
            project_in.project_test_owners = sorted(project_in.project_test_owners, key=str.lower)
        if project_in.project_testers is not None:
            project_in.project_testers = sorted(project_in.project_testers, key=str.lower)
        project_dict: Dict[str, Any] = project_in.model_dump(exclude_none=True, exclude_unset=True)
        if not existing_project:
            try:
                instance: AutoTestApiProjectInfo = await self.create(obj_in=project_dict)
                return instance
            except IntegrityError as e:
                error_message: str = f"新增应用信息异常, 违反约束规则: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise DataBaseStorageException(message=error_message) from e

        try:
            project_dict["state"] = 0
            instance: AutoTestApiProjectInfo = await self.update(id=existing_project.id, obj_in=project_dict)
            return instance
        except (DoesNotExist, IntegrityError) as e:
            error_message: str = f"更新应用信息异常, 违反约束规则或空指针异常: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_project(self, project_in: AutoTestApiProjectUpdate) -> AutoTestApiProjectInfo:
        """
        更新应用，根据project_id或project_code定位并校验名称唯一。

        :param project_in: 应用更新schema
        :return: 更新后的应用实例
        :raises NotFoundException: 应用不存在
        :raises DataAlreadyExistsException: 应用名重复
        :raises DataBaseStorageException: 违反约束
        """
        project_id: Optional[int] = project_in.project_id
        project_code: Optional[str] = project_in.project_code
        # 业务层验证：检查应用是否存在
        if project_id:
            instance = await self.get_by_id(project_id=project_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(project_code=project_code, on_error=True, state__not=1)
            project_id: int = instance.id

        update_dict: Dict[str, Any] = project_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"project_id", "project_code"}
        )
        for owner_key in ("project_dev_owners", "project_developers", "project_test_owners", "project_testers"):
            if owner_key in update_dict and update_dict[owner_key] is not None:
                update_dict[owner_key] = sorted(update_dict[owner_key], key=str.lower)

        # 业务层验证：检查应用名称是否重复
        if "project_name" in update_dict:
            project_name: str = update_dict.get("project_name", instance.project_name)
            existing_project = await self.model.filter(project_name=project_name, state__not=1).exclude(id=project_id).first()
            if existing_project:
                error_message: str = f"应用名称不允许重复, 查询条件: [project_name={project_name}]"
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)

        try:
            instance = await self.update(id=project_id, obj_in=update_dict)
            return instance
        except IntegrityError as e:
            error_message: str = f"更新应用信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_project(self, project_id: Optional[int] = None, project_code: Optional[str] = None) -> AutoTestApiProjectInfo:
        """
        软删除应用；需无关联用例、环境配置明细、标签。

        :param project_id: 应用主键ID，与project_code二选一
        :param project_code: 应用标识代码，与project_id二选一
        :return: 软删除后的应用实例
        :raises ParameterException: project_id与project_code均未传
        :raises NotFoundException: 应用不存在
        :raises DataBaseStorageException: 存在关联数据
        """
        # 业务层验证：检查应用是否存在, project_id与project_code二选一，不能都为空
        if not project_id and not project_code:
            error_message: str = "删除应用信息失败, 参数[project_id]或[project_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if project_id:
            instance = await self.get_by_id(project_id=project_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(project_code=project_code, on_error=True, state__not=1)

        pid: int = instance.id
        # 业务层验证：检查是否存在关联用例
        cases_count = await AutoTestApiCaseCrud().model.filter(case_project=pid, state__not=1).count()
        if cases_count > 0:
            msg = f"应用[name={instance.project_name}]存在{cases_count}个用例, 无法直接删除"
            LOGGER.error(msg)
            raise DataBaseStorageException(message=msg)

        # 业务层验证：检查是否存在关联环境配置明细（应用+环境枚举下的配置）
        config_count = await AutoTestApiEnvConfigInfo.filter(project_id=pid, state__not=1).count()
        if config_count > 0:
            msg = f"应用[name={instance.project_name}]存在{config_count}条环境配置, 无法直接删除"
            LOGGER.error(msg)
            raise DataBaseStorageException(message=msg)

        # 业务层验证：检查是否存在关联标签
        tag_count = await AutoTestApiTagCrud().model.filter(tag_project=pid, state__not=1).count()
        if tag_count > 0:
            msg = f"应用[name={instance.project_name}]存在{tag_count}个标签信息, 无法直接删除"
            LOGGER.error(msg)
            raise DataBaseStorageException(message=msg)

        instance.state = 1
        await instance.save()
        return instance

    async def delete_projects(self, project_in: AutoTestApiProjectDelete) -> int:
        """
        根据ID或code列表批量软删除应用；逐条复用单删关联校验。

        :param project_in: 应用删除schema
        :return: 更新条数
        :raises ParameterException: project_ids与project_codes均未传
        :raises NotFoundException: 应用不存在
        :raises DataBaseStorageException: 存在关联数据
        """
        project_ids: Optional[List[int]] = project_in.project_ids
        project_codes: Optional[List[str]] = project_in.project_codes
        if not project_ids and not project_codes:
            error_message: str = "删除应用信息失败, 参数[project_ids]或[project_codes]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        targets: List[AutoTestApiProjectInfo] = []
        if project_ids:
            for pid in project_ids:
                targets.append(await self.get_by_id(project_id=pid, on_error=True, state__not=1))
        else:
            for pcode in project_codes:
                targets.append(await self.get_by_code(project_code=pcode, on_error=True, state__not=1))

        for instance in targets:
            await self.delete_project(project_id=instance.id)

        return len(targets)

    async def select_projects(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestApiProjectInfo]]:
        """
        根据条件分页查询应用列表。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)
        :raises ParameterException: 查询字段非法
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询应用信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
