# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_project_crud
@DateTime: 2026/1/2 18:01
"""
import traceback
from typing import Optional, Dict, Any, List, Tuple, Union, Set

from tortoise.exceptions import IntegrityError, FieldError, DoesNotExist
from tortoise.expressions import Q

from backend.applications.autotest.models.autotest_env_config_model import AutoTestEnvBindModel, AutoTestEnvConfigModel
from backend.applications.autotest.models.autotest_project_model import AutoTestProjectModel
from backend.applications.autotest.schemas.autotest_project_schema import (
    AutoTestProjectCreate,
    AutoTestProjectUpdate,
    AutoTestProjectDelete,
)
from backend.applications.autotest.services.autotest_case_crud import AutoTestCaseCrud
from backend.applications.autotest.services.autotest_tag_crud import AutoTestTagCrud
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
    NoPermissionException,
)
from backend.services import DataScope


class AutoTestProjectCrud(ScaffoldCrud[AutoTestProjectModel, AutoTestProjectCreate, AutoTestProjectUpdate]):
    """
    应用（项目）CRUD：autotest 的根容器，用例/环境/标签/任务均挂在其下。

    唯一口径：(project_name, project_mark) 联合唯一，数据库索引不区分 state，
    因此软删行同样占用名称；同组合的软删记录在写权限内直接复用复活。
    project_code 为系统生成的全局唯一标识代码，与用户填写的 project_mark 是两个不同字段。
    归属口径：以 created_user 为归属人；删除前须确认用例/环境配置/环境绑定/标签/任务均无引用。
    """

    def __init__(self):
        """绑定应用模型（krun_autotest_project），供基类通用CRUD复用。"""
        super().__init__(model=AutoTestProjectModel)

    async def get_by_id(self, project_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestProjectModel]:
        """
        根据主键ID查询应用。

        :param project_id: 应用主键ID
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 应用实例或None
        :raises ParameterException: project_id 为空
        :raises NotFoundException: on_error=True 且记录不存在
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

    async def get_by_ids(
            self,
            project_ids: List[int],
            on_error: bool = False,
            **kwargs
    ) -> Optional[Union[bool, List[AutoTestProjectModel]]]:
        """
        根据主键ID列表批量查询应用；用于列表回显时批量取回关联应用。

        先只查一次主键判断缺失：有缺失且 on_error=False 时直接返回 False（而非空列表，
        历史契约，调用方须按真值判断），全部存在才二次查询返回完整实例列表。

        :param project_ids: 应用主键ID列表
        :param on_error: 存在缺失ID时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 应用列表；存在缺失且on_error为False时返回False
        :raises ParameterException: 列表为空或元素不是int
        :raises NotFoundException: on_error=True 且存在缺失ID
        """
        if not project_ids:
            error_message: str = "查询应用信息失败, 参数[project_ids]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if not isinstance(project_ids, list) or any(type(pid) is not int for pid in project_ids):
            error_message: str = "查询应用信息失败, 参数[project_ids]必须是List[int]类型"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        existing_project_ids = await self.model.filter(id__in=project_ids, **kwargs).values_list("id", flat=True)
        missing_project_ids: Set[int] = set(project_ids) - set(existing_project_ids)
        if missing_project_ids:
            error_message: str = f"查询应用信息失败, 记录[id_in={missing_project_ids}]不存在"
            LOGGER.error(error_message)
            if on_error:
                raise NotFoundException(message=error_message)
            return False
        return await self.model.filter(id__in=project_ids, **kwargs).all()

    async def get_by_code(self, project_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestProjectModel]:
        """
        根据应用标识代码查询应用。

        :param project_code: 应用标识代码（系统生成的唯一代码，非 project_mark）
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 应用实例或None
        :raises ParameterException: project_code 为空
        :raises NotFoundException: on_error=True 且记录不存在
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

    async def get_by_name(self, project_name: str, on_error: bool = False, **kwargs) -> Optional[AutoTestProjectModel]:
        """
        根据应用名称查询应用。

        :param project_name: 应用名称
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 应用实例或None
        :raises ParameterException: project_name 为空
        :raises NotFoundException: on_error=True 且记录不存在
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

    async def create_project(self, project_in: AutoTestProjectCreate, scope: DataScope) -> AutoTestProjectModel:
        """
        创建应用；同名称+标识的软删记录在写权限内恢复并覆盖，活跃记录直接报错。

        project_mark 去首尾空白后落库（与唯一索引口径一致）；四个负责人列表统一按小写排序，
        保证同一组人员的存储顺序稳定。

        :param project_in: 应用创建schema
        :param scope: 数据权限上下文，恢复软删应用时要求创建人允许当前用户写入
        :return: 创建或恢复后的应用实例
        :raises DataAlreadyExistsException: 名称+标识组合已存在，或并发写入撞唯一索引
        :raises NoPermissionException: 待恢复的软删应用归属人不在当前用户可写范围
        :raises NotFoundException: 恢复时目标记录已不存在
        """
        project_name: str = project_in.project_name
        project_mark: str = (project_in.project_mark or "").strip()
        # 联合唯一键(project_name, project_mark)才能判重：软删恢复与活跃校验都按该组合定位
        existing_project: Optional[AutoTestProjectModel] = await self.model.filter(
            project_name=project_name, project_mark=project_mark
        ).first()
        project_dict: Dict[str, Any] = project_in.model_dump(exclude_none=True, exclude_unset=True)
        project_dict["project_mark"] = project_mark
        for owner_field in (
                "project_dev_owners",
                "project_developers",
                "project_test_owners",
                "project_testers",
        ):
            owners = project_dict.get(owner_field)
            if owners is not None:
                project_dict[owner_field] = sorted(owners, key=str.lower)
        if not existing_project:
            try:
                instance: AutoTestProjectModel = await self.create(obj_in=project_dict)
                return instance
            except IntegrityError as e:
                # 并发写入会在这里被联合唯一索引拦下，语义等同已存在，不能落成服务异常
                error_message: str = f"应用[project_name={project_name}, project_mark={project_mark}]已存在"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise DataAlreadyExistsException(message=error_message) from e

        # 仅软删同名可启用并覆盖；活跃同名报错，禁止静默覆盖已有应用
        if existing_project.state != 1:
            error_message: str = f"应用[project_name={project_name}, project_mark={project_mark}]已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        # 软删恢复不得跨写范围接管他人应用，且不覆盖原创建人
        await scope.load_owners([existing_project.created_user])
        if not scope.can_write(existing_project.created_user):
            error_message: str = f"新增应用信息失败, 应用[{project_name}]创建人[{existing_project.created_user}]不在当前用户可操作范围内, 无权操作"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)

        try:
            project_dict.pop("created_user", None)
            project_dict["state"] = 0
            instance: AutoTestProjectModel = await self.update(id=existing_project.id, obj_in=project_dict)
            return instance
        except IntegrityError as e:
            error_message: str = f"应用[project_name={project_name}, project_mark={project_mark}]已存在"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataAlreadyExistsException(message=error_message) from e
        except DoesNotExist as e:
            error_message: str = f"恢复应用信息失败, 记录[id={existing_project.id}]不存在"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e

    async def update_project(self, project_in: AutoTestProjectUpdate, scope: DataScope) -> AutoTestProjectModel:
        """
        更新应用，根据project_id或project_code定位并校验名称+标识唯一。

        仅在入参触及 project_name/project_mark 时重做组合判重，比对包含软删行（与库内索引同口径）。

        :param project_in: 应用更新schema
        :param scope: 数据权限上下文，仅允许修改归属人在当前用户可操作范围内的应用
        :return: 更新后的应用实例
        :raises ParameterException: 两个定位参数同时为空
        :raises NotFoundException: 应用不存在或已软删
        :raises NoPermissionException: 归属人不在当前用户可写范围
        :raises DataAlreadyExistsException: 改名/改标识后与库内组合重复（含软删行）
        """
        project_id: Optional[int] = project_in.project_id
        project_code: Optional[str] = project_in.project_code
        if not project_id and not project_code:
            error_message: str = "更新应用信息失败, 参数[project_id, project_code]不允许同时为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if project_id:
            instance = await self.get_by_id(project_id=project_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(project_code=project_code, on_error=True, state__not=1)
            project_id = instance.id

        await scope.load_owners([instance.created_user])
        if not scope.can_write(instance.created_user):
            error_message: str = f"更新应用信息失败, 应用[{instance.project_name}]创建人[{instance.created_user}]不在当前用户可操作范围内, 无权操作"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)

        update_dict: Dict[str, Any] = project_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"project_id", "project_code"}
        )
        for owner_field in (
                "project_dev_owners",
                "project_developers",
                "project_test_owners",
                "project_testers",
        ):
            owners = update_dict.get(owner_field)
            if owners is not None:
                update_dict[owner_field] = sorted(owners, key=str.lower)

        if "project_name" in update_dict or "project_mark" in update_dict:
            project_name: str = (update_dict.get("project_name", instance.project_name) or "").strip()
            project_mark: str = (update_dict.get("project_mark", instance.project_mark) or "").strip()
            update_dict["project_name"] = project_name
            update_dict["project_mark"] = project_mark
            # 与库内联合唯一索引同口径：名称+标识组合不允许重复（含软删记录，索引不区分state）
            existing_project = await self.model.filter(
                project_name=project_name, project_mark=project_mark
            ).exclude(id=project_id).first()
            if existing_project:
                error_message: str = (
                    f"应用名称或标识不允许重复, 查询条件: "
                    f"[project_name={project_name}, project_mark={project_mark}]"
                )
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)

        try:
            instance = await self.update(id=project_id, obj_in=update_dict)
            return instance
        except IntegrityError as e:
            error_message: str = "应用名称或标识不允许重复"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataAlreadyExistsException(message=error_message) from e

    async def assert_project_deletable(self, instance: AutoTestProjectModel) -> None:
        """
        校验应用不存在引用关系：用例 → 环境配置 → 环境绑定 → 标签 → 任务，逐项短路。

        环境部分先查该应用下启用中的配置数：有配置报配置数；无配置但仍存在环境绑定时报绑定数。

        :param instance: 待删除应用实例
        :return: None
        :raises DataBaseStorageException: 任一引用存在即拒绝删除
        """
        from backend.applications.autotest.models.autotest_task_model import AutoTestTaskModel

        pid: int = instance.id
        cases_count = await AutoTestCaseCrud().model.filter(case_project=pid, state__not=1).count()
        if cases_count > 0:
            msg = f"应用[name={instance.project_name}]存在{cases_count}个用例, 无法直接删除"
            LOGGER.error(msg)
            raise DataBaseStorageException(message=msg)
        env_bind_ids = await AutoTestEnvBindModel.filter(project_id=pid, state__not=1).values_list("id", flat=True)
        if env_bind_ids:
            config_count = await AutoTestEnvConfigModel.filter(
                env_bind_id__in=list(env_bind_ids), state__not=1
            ).count()
            if config_count > 0:
                msg = f"应用[name={instance.project_name}]存在{config_count}条环境配置, 无法直接删除"
                LOGGER.error(msg)
                raise DataBaseStorageException(message=msg)
            msg = f"应用[name={instance.project_name}]存在{len(env_bind_ids)}条环境绑定, 无法直接删除"
            LOGGER.error(msg)
            raise DataBaseStorageException(message=msg)
        tag_count = await AutoTestTagCrud().model.filter(tag_project=pid, state__not=1).count()
        if tag_count > 0:
            msg = f"应用[name={instance.project_name}]存在{tag_count}个标签信息, 无法直接删除"
            LOGGER.error(msg)
            raise DataBaseStorageException(message=msg)
        task_count = await AutoTestTaskModel.filter(task_project=pid, state__not=1).count()
        if task_count > 0:
            msg = f"应用[name={instance.project_name}]存在{task_count}个任务, 无法直接删除"
            LOGGER.error(msg)
            raise DataBaseStorageException(message=msg)

    async def delete_project(
            self,
            scope: DataScope,
            project_id: Optional[int] = None,
            project_code: Optional[str] = None
    ) -> AutoTestProjectModel:
        """
        物理删除应用；删除前校验无引用（用例/环境配置/环境绑定/标签/任务）。

        :param scope: 数据权限上下文，仅允许删除归属人在当前用户可删除范围内的应用
        :param project_id: 应用主键ID，与project_code二选一
        :param project_code: 应用标识代码，与project_id二选一
        :return: 删除后的应用实例快照
        :raises ParameterException: 两个定位参数同时为空
        :raises NotFoundException: 应用不存在或已软删
        :raises NoPermissionException: 归属人不在当前用户可删范围
        :raises DataBaseStorageException: 存在引用关系
        """
        if not project_id and not project_code:
            error_message: str = "删除应用信息失败, 参数[project_id, project_code]不允许同时为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if project_id:
            instance = await self.get_by_id(project_id=project_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(project_code=project_code, on_error=True, state__not=1)

        await scope.load_owners([instance.created_user])
        if not scope.can_delete(instance.created_user):
            error_message: str = f"删除应用信息失败, 应用[{instance.project_name}]创建人[{instance.created_user}]不在当前用户可删除范围内, 无权操作"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)

        await self.assert_project_deletable(instance)
        await instance.delete()
        return instance

    async def delete_projects(self, project_in: AutoTestProjectDelete, scope: DataScope) -> int:
        """
        根据ID或code列表批量软删除应用；软删与物理删同样拒绝存在引用关系的应用。

        先一次性批量定位并批量校验行级权限与引用关系，全部通过后再单次批量软删，
        因此中途失败不会落库，具备全有或全无语义。

        :param project_in: 应用删除schema
        :param scope: 数据权限上下文，仅允许删除归属人在当前用户可删除范围内的应用
        :return: 实际软删条数
        :raises ParameterException: 两个ID/code列表同时为空，或列表内存在空值
        :raises NotFoundException: 列表内存在不存在或已软删的应用
        :raises NoPermissionException: 任一归属人不在当前用户可删范围
        :raises DataBaseStorageException: 任一应用存在引用关系
        """
        project_ids: Optional[List[int]] = project_in.project_ids
        project_codes: Optional[List[str]] = project_in.project_codes
        if not project_ids and not project_codes:
            error_message: str = "删除应用信息失败, 参数[project_ids, project_codes]不允许同时为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 单次批量定位并按入参顺序收集，首个缺失(或空参)按单条查询原文案抛出，替代循环逐条查询
        targets: List[AutoTestProjectModel] = []
        if project_ids:
            id_map: Dict[int, AutoTestProjectModel] = {
                obj.id: obj for obj in await self.model.filter(id__in=project_ids, state__not=1)
            }
            for pid in project_ids:
                if not pid:
                    error_message: str = "查询应用信息失败, 参数[project_id]不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)
                instance = id_map.get(pid)
                if not instance:
                    error_message: str = f"查询应用信息失败, 记录[id={pid}]不存在"
                    LOGGER.error(error_message)
                    raise NotFoundException(message=error_message)
                targets.append(instance)
        else:
            code_map: Dict[str, AutoTestProjectModel] = {
                obj.project_code: obj for obj in await self.model.filter(project_code__in=project_codes, state__not=1)
            }
            for pcode in project_codes:
                if not pcode:
                    error_message: str = "查询应用信息失败, 参数[project_code]不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)
                instance = code_map.get(pcode)
                if not instance:
                    error_message: str = f"查询应用信息失败, 记录[code={pcode}]不存在"
                    LOGGER.error(error_message)
                    raise NotFoundException(message=error_message)
                targets.append(instance)

        await scope.load_owners([instance.created_user for instance in targets])
        if not all(scope.can_delete(instance.created_user) for instance in targets):
            error_message: str = "删除应用信息失败, 存在不在当前用户可删除范围内的应用, 无权操作"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)
        # 软删同样受引用关系约束：先全量校验再落库，保证批量操作全有或全无
        for instance in targets:
            await self.assert_project_deletable(instance)
        await self.soft_delete_batch(ids=[instance.id for instance in targets])
        return len(targets)

    async def select_projects(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestProjectModel]]:
        """
        根据条件分页查询应用列表。

        :param search: Tortoise Q查询条件（归属过滤由视图层拼接）
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)
        :raises ParameterException: 查询或排序字段不被ORM支持
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = "查询应用信息失败，查询或排序条件包含不支持的字段，请调整筛选或排序条件"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def get_all_project(
            self,
            page: int = 1,
            page_size: int = 10000,
            scope: Optional[DataScope] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        分页查询全部启用应用，供下拉/选择器使用。

        返回项中的 project_mark 实际回填 project_code：前端历史字段沿用 mark 命名，
        值为系统唯一标识代码，与库内用户填写的 project_mark 字段不是同一含义，不要混用。

        :param page: 页码
        :param page_size: 每页条数
        :param scope: 数据权限上下文，传入时仅返回可见范围内的应用
        :return: ([{project_id, project_name, project_mark}], total)；project_id为应用主键id，project_mark取project_code
        """
        query = self.model.filter(state=0)
        owner_q = scope.read_q("created_user") if scope is not None else None
        if owner_q is not None:
            query = query.filter(owner_q)
        total = await query.count()
        rows = await query.offset((page - 1) * page_size).limit(page_size).values(
            "id", "project_name", "project_code"
        )
        data = [
            {
                "project_id": row["id"],
                "project_name": row["project_name"],
                "project_mark": row["project_code"],
            }
            for row in rows
        ]
        return data, total
