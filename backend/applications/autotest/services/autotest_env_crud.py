# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_env_crud
@DateTime: 2026/1/2 17:42
"""
import traceback
from collections import defaultdict
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Union

from tortoise.exceptions import IntegrityError, FieldError, DoesNotExist
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from backend.applications.autotest.models.autotest_env_config_model import AutoTestEnvBindModel, AutoTestEnvConfigModel
from backend.applications.autotest.models.autotest_env_model import AutoTestEnvModel
from backend.applications.autotest.models.autotest_project_model import AutoTestProjectModel
from backend.applications.autotest.schemas.autotest_env_schema import (
    AutoTestEnvCreate,
    AutoTestEnvUpdate,
    AutoTestEnvDelete,
    AutoTestEnvPageSelect,
)
from backend.applications.autotest.services.autotest_scope_guard import load_readable_project
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import GLOBAL_CONFIG, LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
    NoPermissionException,
)
from backend.enums import AutoTestConfigNodeType
from backend.services import DataScope, get_current_username


class AutoTestEnvCrud(ScaffoldCrud[AutoTestEnvBindModel, AutoTestEnvCreate, AutoTestEnvUpdate]):
    """
    环境绑定CRUD：应用维度的环境绑定（krun_autotest_env_bind）及其全局环境名字典。

    两层结构：
    - 环境字典（AutoTestEnvModel）为全局共享的环境枚举；
    - 环境绑定 = 应用 + 环境字典 + 节点类型(env_type)，唯一性由三键共同保证。

    引用约束：删除/软删前必须确认无环境配置引用，且无任务以环境名称字符串引用该环境。
    归属口径：绑定以 created_user 为归属人；环境字典为纯词典，无归属与状态字段。
    """

    def __init__(self):
        """绑定环境绑定模型（krun_autotest_env_bind），供基类通用CRUD复用。"""
        super().__init__(model=AutoTestEnvBindModel)

    async def get_by_id(self, env_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestEnvBindModel]:
        """
        根据主键ID查询环境绑定。

        :param env_id: 环境绑定主键，必填
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 环境绑定实例或None
        :raises ParameterException: env_id 为空
        :raises NotFoundException: on_error=True 且记录不存在
        """
        if not env_id:
            error_message: str = "查询环境绑定信息失败, 参数[env_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.get_or_none(id=env_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询环境绑定信息失败, 记录[id={env_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, env_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestEnvBindModel]:
        """
        根据标识代码查询环境绑定。

        :param env_code: 绑定标识代码，必填
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 环境绑定实例或None
        :raises ParameterException: env_code 为空
        :raises NotFoundException: on_error=True 且记录不存在
        """
        if not env_code:
            error_message: str = "查询环境绑定信息失败, 参数[env_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(env_code=env_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询环境绑定信息失败, 记录[code={env_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_bind_by_env_name(
            self,
            project_id: int,
            env_name: str,
            env_type: Optional[Union[AutoTestConfigNodeType, str]] = None,
            on_error: bool = False,
    ) -> Optional[AutoTestEnvBindModel]:
        """
        按应用+环境名称解析环境绑定；指定env_type时仅匹配该类型。

        先在全局字典里按名称（忽略大小写）取所有同名字典ID，再到绑定表按应用+类型取首条启用记录；
        同名环境可能存在多条绑定（不同节点类型），因此不传 env_type 时结果依赖存储顺序，仅用于“取任一条”场景。

        :param project_id: 应用主键ID
        :param env_name: 环境名称(忽略大小写)
        :param env_type: 节点类型(app/file/database/redis)，为空则取首条启用绑定
        :param on_error: 未找到时是否抛出异常
        :return: 环境绑定实例或None
        :raises ParameterException: env_name 为空
        :raises NotFoundException: on_error=True 且无匹配绑定
        """
        name = (env_name or "").strip()
        if not name:
            error_message: str = "查询环境绑定信息失败, 参数[env_name]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        dict_ids = await AutoTestEnvModel.filter(env_name__iexact=name).values_list("id", flat=True)
        instance: Optional[AutoTestEnvBindModel] = None
        if dict_ids:
            filters: Dict[str, Any] = {
                "project_id": int(project_id),
                "env_enum_id__in": list(dict_ids),
                "state__not": 1,
            }
            if env_type is not None:
                filters["env_type"] = env_type
            instance = await self.model.filter(**filters).first()
        if not instance and on_error:
            type_hint = f", env_type={env_type}" if env_type is not None else ""
            error_message: str = f"查询环境绑定信息失败, 记录[project_id={project_id}, env_name={name}{type_hint}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_dict_ids_by_name(self, env_name: str, exact: bool = False) -> List[int]:
        """
        按环境名称查询字典主键ID列表。

        :param env_name: 环境名称
        :param exact: True=精确匹配(忽略大小写)，False=模糊包含
        :return: 字典主键ID列表；名称空白时返回空列表
        """
        name = (env_name or "").strip()
        if not name:
            return []
        query = AutoTestEnvModel.all()
        if exact:
            query = query.filter(env_name__iexact=name)
        else:
            query = query.filter(env_name__icontains=name)
        return await query.values_list("id", flat=True)

    async def get_env_name_map(self, env_bind_ids: List[int]) -> Dict[int, str]:
        """
        批量解析环境绑定ID到环境名称的映射，已删除的绑定不解析。

        :param env_bind_ids: 环境绑定主键ID列表
        :return: {绑定ID: 环境名称}；已软删绑定与字典缺失名称不返回/降为空串
        """
        if not env_bind_ids:
            return {}
        bind_rows = await self.model.filter(
            id__in=list(set(env_bind_ids)), state__not=1
        ).values("id", "env_enum_id")
        dict_ids = {row["env_enum_id"] for row in bind_rows}
        if not dict_ids:
            return {}
        dict_name_map = dict(
            await AutoTestEnvModel.filter(id__in=list(dict_ids)).values_list("id", "env_name")
        )
        return {row["id"]: dict_name_map.get(row["env_enum_id"], "") for row in bind_rows}

    async def get_bind_map(self, env_bind_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """
        批量查询绑定维度字段。

        :param env_bind_ids: 环境绑定主键ID列表
        :return: {绑定ID: {project_id, env_type, env_enum_id}}；env_type 统一转为原始值字符串
        """
        if not env_bind_ids:
            return {}
        rows = await self.model.filter(id__in=list(set(env_bind_ids))).values(
            "id", "project_id", "env_type", "env_enum_id"
        )
        return {
            row["id"]: {
                "project_id": row["project_id"],
                "env_type": row["env_type"].value if hasattr(row["env_type"], "value") else row["env_type"],
                "env_enum_id": row["env_enum_id"],
            }
            for row in rows
        }

    async def list_bind_ids(
            self,
            *,
            project_id: Optional[int] = None,
            env_type: Optional[Union[AutoTestConfigNodeType, str]] = None,
            env_enum_ids: Optional[List[int]] = None,
            state_not: int = 1,
    ) -> List[int]:
        """
        按维度条件查询绑定主键列表。

        :param project_id: 应用ID
        :param env_type: 节点类型
        :param env_enum_ids: 环境字典ID列表；传空列表直接返回空结果
        :param state_not: 排除的状态值（默认排除软删行 state=1）
        :return: 绑定主键列表
        """
        query = self.model.filter(state__not=state_not)
        if project_id is not None:
            query = query.filter(project_id=project_id)
        if env_type is not None:
            query = query.filter(env_type=env_type)
        if env_enum_ids is not None:
            if not env_enum_ids:
                return []
            query = query.filter(env_enum_id__in=list(env_enum_ids))
        return await query.values_list("id", flat=True)

    async def get_or_create_env(self, env_name: str) -> AutoTestEnvModel:
        """
        按环境名称获取或创建全局环境枚举记录。

        名称统一规范为大写；字典为纯词典，无归属与状态；并发创建撞唯一索引时回查既有行。

        :param env_name: 环境名称(规范化为大写)
        :return: 环境枚举实例
        :raises ParameterException: env_name 为空
        :raises DataBaseStorageException: 并发冲突后仍无法回查到既有记录
        """
        name = (env_name or "").strip().upper()
        if not name:
            error_message: str = "参数[env_name]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        dict_row = await AutoTestEnvModel.filter(env_name=name).first()
        if dict_row:
            return dict_row
        try:
            return await AutoTestEnvModel.create(env_name=name)
        except IntegrityError as e:
            # 并发创建触发唯一约束时回查既有记录
            dict_row = await AutoTestEnvModel.filter(env_name=name).first()
            if dict_row:
                return dict_row
            error_message: str = "新增环境枚举信息失败，环境名称与现有记录冲突，请刷新后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [env_name={name}]\n"
                f"{traceback.format_exc()}"
            )
            raise DataBaseStorageException(message=error_message) from e

    async def create_env(self, env_in: AutoTestEnvCreate, scope: DataScope, strict_duplicate: bool = False) -> AutoTestEnvBindModel:
        """
        创建环境绑定；同应用+环境+类型已存在则恢复启用（软删恢复需写权限）。

        :param env_in: 环境创建schema定义
        :param strict_duplicate: 为True时，命中启用态绑定直接判重报错，为False时幂等复用已存在绑定
        :param scope: 数据权限上下文
        :return: 创建或恢复后的环境绑定实例
        :raises ParameterException: 环境名称为空
        :raises NotFoundException: 所属应用不存在或已软删
        :raises NoPermissionException: 所属应用不可读，或软删绑定创建人不可写
        :raises DataAlreadyExistsException: strict_duplicate=True 且启用态绑定已存在
        :raises DataBaseStorageException: 落库失败（唯一索引冲突或字典创建失败）
        """
        await load_readable_project(scope, env_in.project_id)
        # 绑定表保留归属人，取登录态，忽略请求体回传，防止伪造创建人
        operator: Optional[str] = scope.username or get_current_username() or env_in.created_user
        # 环境字典为全局共享的纯词典，无归属与状态，直接复用或创建
        dict_row = await self.get_or_create_env(env_name=env_in.env_name)
        bind_filter: Dict[str, Any] = {
            "env_enum_id": dict_row.id,
            "project_id": env_in.project_id,
            "env_type": env_in.env_type,
        }
        existing_bind: Optional[AutoTestEnvBindModel] = await self.model.filter(**bind_filter).first()
        if not existing_bind:
            payload = env_in.model_dump(
                exclude_none=True,
                exclude_unset=True,
                exclude={"env_name"},
            )
            payload["env_enum_id"] = dict_row.id
            payload["created_user"] = operator
            try:
                return await self.create(obj_in=payload)
            except IntegrityError as e:
                # 并发插入撞唯一键：回查另一事务已提交的绑定，按相同语义复用或判重
                existing_bind = await self.model.filter(**bind_filter).first()
                if not existing_bind:
                    error_message: str = "新增环境绑定信息失败，相同应用、环境及节点类型已存在"
                    LOGGER.error(
                        f"{error_message}, "
                        f"关键字段: [project_id={env_in.project_id}, env_enum_id={dict_row.id}, env_type={env_in.env_type}]\n"
                        f"{traceback.format_exc()}"
                    )
                    raise DataBaseStorageException(message=error_message) from e

        # 已启用则直接复用；仅软删记录需要恢复
        if existing_bind.state == 0:
            if strict_duplicate:
                raise DataAlreadyExistsException(message="新增失败, 已存在相同应用、环境及节点记录")
            return existing_bind
        # 软删恢复不得跨写范围接管他人环境绑定
        if scope is not None:
            await scope.load_owners([existing_bind.created_user])
        if scope is not None and not scope.can_write(existing_bind.created_user):
            error_message: str = f"新增环境绑定信息失败, 环境绑定[code={existing_bind.env_code}]创建人[{existing_bind.created_user}]不在当前用户可操作范围内"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)
        try:
            restore_dict: Dict[str, Any] = {"state": 0}
            if env_in.env_desc is not None:
                restore_dict["env_desc"] = env_in.env_desc
            if operator:
                restore_dict["updated_user"] = operator
            return await self.update(id=existing_bind.id, obj_in=restore_dict)
        except (DoesNotExist, IntegrityError) as e:
            error_message: str = "新增环境绑定信息失败，目标环境绑定可能已被删除或与现有记录冲突，请刷新后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [env_bind_id={existing_bind.id}, project_id={env_in.project_id}, env_enum_id={dict_row.id}, env_type={env_in.env_type}]\n"
                f"{traceback.format_exc()}"
            )
            raise DataBaseStorageException(message=error_message) from e

    async def update_env(self, env_in: AutoTestEnvUpdate, scope: DataScope) -> AutoTestEnvBindModel:
        """
        按env_id/env_code精准更新单条环境绑定；描述写在绑定表，不影响同名其他节点类型。
        所属应用允许变更，换应用时目标应用必须存在且可读；节点类型创建后不可变更。

        :param env_in: 环境绑定更新schema
        :param scope: 数据权限上下文
        :return: 更新后的环境绑定实例
        :raises ParameterException: 定位参数为空、名称为空，或请求中的 env_type 与已存绑定不一致
        :raises NotFoundException: 环境绑定或目标应用不存在、已软删
        :raises NoPermissionException: 环境绑定创建人不在写范围，或目标应用不可读
        :raises DataBaseStorageException: 落库失败（改名或换应用后与既有绑定冲突）
        """
        env_id: Optional[int] = env_in.env_id
        env_code: Optional[str] = env_in.env_code

        if not env_id and not env_code:
            error_message: str = "更新环境绑定信息失败, 参数[env_id, env_code]不允许同时为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if env_id:
            instance = await self.get_by_id(env_id=env_id, on_error=True, state__not=1)
            env_code = instance.env_code
        else:
            instance = await self.get_by_code(env_code=env_code, on_error=True, state__not=1)
            env_id = instance.id

        await scope.load_owners([instance.created_user])
        if not scope.can_write(instance.created_user):
            error_message: str = f"更新环境绑定信息失败, 环境绑定[code={instance.env_code}]创建人[{instance.created_user}]不在当前用户可操作范围内"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)
        # 所属节点由创建时确定，不允许换节点
        if env_in.env_type is not None and instance.env_type != env_in.env_type:
            raise ParameterException(message="不支持修改环境所属节点类型")
        # 所属应用允许变更，换应用时目标应用必须存在且可读
        target_project_id: int = int(env_in.project_id) if env_in.project_id is not None else int(instance.project_id)
        if target_project_id != int(instance.project_id):
            await load_readable_project(scope, target_project_id)

        update_dict: Dict[str, Any] = env_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"env_id", "env_code", "env_type", "created_user", "updated_user"},
        )
        # 显式提交空名称时拒绝，避免静默跳过改名却返回成功
        if "env_name" in env_in.model_fields_set and not str(env_in.env_name or "").strip():
            error_message: str = "更新环境绑定信息失败, 参数[env_name]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        new_env_name = update_dict.pop("env_name", None)
        # 环境字典为纯词典，更新人只落在绑定表
        operator: Optional[str] = scope.username or get_current_username() or env_in.updated_user
        if operator:
            update_dict["updated_user"] = operator
        # env_desc保留在update_dict，落绑定表
        if new_env_name:
            dict_row = await self.get_or_create_env(env_name=new_env_name)
            update_dict["env_enum_id"] = dict_row.id

        try:
            instance = await self.update(id=env_id, obj_in=update_dict)
            return instance
        except DoesNotExist as e:
            error_message: str = "更新环境绑定信息失败，目标环境绑定不存在或已被删除，请刷新后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [env_id={env_id}, env_code={env_code}]\n"
                f"{traceback.format_exc()}"
            )
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = "更新环境绑定信息失败，相同应用、环境及节点类型已存在"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [env_id={env_id}, env_code={env_code}, project_id={target_project_id}, env_type={instance.env_type}, "
                f"env_name={new_env_name}]\n"
                f"{traceback.format_exc()}"
            )
            raise DataBaseStorageException(message=error_message) from e

    async def _assert_envs_not_referenced(self, targets: List[AutoTestEnvBindModel]) -> None:
        """
        批量校验环境绑定不存在引用关系：环境配置、任务用例执行配置中的环境名。

        配置按绑定一次分组统计，任务按应用一次取回后在内存匹配，避免逐条扫描；
        两类引用：环境配置走 env_bind_id 外键；任务只存环境名称字符串，因此需按绑定所属应用扫描
        任务的 cases_execute_config（case级 involve_envs 与步骤级 steps_execute_config 都算引用）。

        :param targets: 待删除的环境绑定实例列表
        :return: None
        :raises DataAlreadyExistsException: 任一绑定存在引用关系时拒绝删除
        """
        if not targets:
            return
        from backend.applications.autotest.models.autotest_task_model import AutoTestTaskModel
        from backend.applications.autotest.services.autotest_task_crud import extract_steps_execute_envs, extract_task_involve_envs

        # 外键为RESTRICT，物理删除本会被拦截；应用层前置校验给出可读文案
        config_rows = await AutoTestEnvConfigModel.filter(
            env_bind_id__in=[int(instance.id) for instance in targets],
            state__not=1,
        ).values_list("env_bind_id", flat=True)
        config_counts: Dict[int, int] = defaultdict(int)
        for bind_id in config_rows:
            config_counts[int(bind_id)] += 1
        for instance in targets:
            config_count: int = config_counts.get(int(instance.id), 0)
            if config_count > 0:
                error_message: str = f"删除环境绑定信息失败, 存在{config_count}个环境配置, 无法直接删除"
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)

        # 任务以环境名称字符串引用环境，物理删除前按应用归组扫描任务执行配置
        dict_names: Dict[int, str] = await self._get_dict_name_map({int(instance.env_enum_id) for instance in targets})
        names_by_project: Dict[int, set] = defaultdict(set)
        for instance in targets:
            env_name = dict_names.get(int(instance.env_enum_id))
            if env_name:
                names_by_project[int(instance.project_id)].add(env_name)
        if not names_by_project:
            return
        task_rows: List[Dict[str, Any]] = await AutoTestTaskModel.filter(
            task_project__in=list(names_by_project), state__not=1
        ).values("task_project", "task_name", "cases_execute_config")
        for row in task_rows:
            cases_cfg = row.get("cases_execute_config")
            if not isinstance(cases_cfg, dict):
                continue
            target_names: Optional[set] = names_by_project.get(int(row["task_project"]))
            if not target_names:
                continue
            referenced_envs = set(extract_task_involve_envs(cases_cfg)) | set(extract_steps_execute_envs(cases_cfg).values())
            hit_name: Optional[str] = next((name for name in sorted(target_names) if name in referenced_envs), None)
            if hit_name:
                error_message: str = f"删除环境绑定信息失败, 环境[{hit_name}]被任务[{row.get('task_name')}]引用, 无法直接删除"
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)

    async def delete_env(self, scope: DataScope, env_id: Optional[int] = None, env_code: Optional[str] = None) -> AutoTestEnvBindModel:
        """
        物理删除环境绑定；绑定下仍存在未删除的环境配置时禁止删除。

        :param scope: 数据权限上下文
        :param env_id: 环境绑定主键，与env_code二选一
        :param env_code: 绑定标识代码，与env_id二选一
        :return: 删除后的环境绑定实例快照
        :raises ParameterException: 两个定位参数同时为空
        :raises NotFoundException: 环境绑定不存在或已软删
        :raises NoPermissionException: 环境绑定创建人不在当前用户可删除范围
        :raises DataAlreadyExistsException: 存在环境配置或任务引用
        """
        if not env_id and not env_code:
            error_message: str = "删除环境绑定信息失败, 参数[env_id, env_code]不允许同时为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if env_id:
            instance = await self.get_by_id(env_id=env_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(env_code=env_code, on_error=True, state__not=1)

        await scope.load_owners([instance.created_user])
        if not scope.can_delete(instance.created_user):
            error_message: str = f"删除环境绑定信息失败, 环境绑定[code={instance.env_code}]创建人[{instance.created_user}]不在当前用户可删除范围内"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)

        # 外键为RESTRICT，物理删除本会被拦截；启用态配置必须为空，已软删配置随绑定清理
        await self._assert_envs_not_referenced([instance])

        try:
            async with in_transaction() as conn:
                # 已软删配置仍占用 RESTRICT 外键；历史行随绑定一并物理清理，避免删除后受阻
                await AutoTestEnvConfigModel.filter(env_bind_id=instance.id, state=1).using_db(conn).delete()
                await instance.delete(using_db=conn)
        except IntegrityError as e:
            # 校验与删除之间可能并发新增子配置，外键拦截转为可读提示
            error_message: str = "删除环境绑定信息失败, 环境绑定下仍存在环境配置, 请刷新后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [env_id={instance.id}, env_code={instance.env_code}]\n"
                f"{traceback.format_exc()}"
            )
            raise DataAlreadyExistsException(message=error_message) from e
        return instance

    async def delete_envs(self, env_in: AutoTestEnvDelete, scope: DataScope) -> int:
        """
        根据ID或code列表批量软删除环境绑定；软删与物理删同样拒绝存在引用关系的环境绑定。

        :param env_in: 环境绑定删除schema
        :param scope: 数据权限上下文
        :return: 更新条数
        :raises ParameterException: 两个定位参数同时为空，或列表中包含空值
        :raises NotFoundException: 任一目标绑定不存在或已软删
        :raises NoPermissionException: 任一绑定创建人不在当前用户可删除范围
        :raises DataAlreadyExistsException: 任一绑定仍被环境配置或任务引用
        """
        env_ids: Optional[List[int]] = env_in.env_ids
        env_codes: Optional[List[str]] = env_in.env_codes
        if not env_ids and not env_codes:
            error_message: str = "删除环境绑定信息失败, 参数[env_ids, env_codes]不允许同时为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 单次批量定位并按入参顺序收集，首个缺失(或空参)按单条查询原文案抛出，替代循环逐条查询
        targets: List[AutoTestEnvBindModel] = []
        if env_ids:
            id_map: Dict[int, AutoTestEnvBindModel] = {
                obj.id: obj for obj in await self.model.filter(id__in=env_ids, state__not=1)
            }
            for eid in env_ids:
                if not eid:
                    error_message: str = "查询环境绑定信息失败, 参数[env_id]不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)
                instance = id_map.get(eid)
                if not instance:
                    error_message: str = f"查询环境绑定信息失败, 记录[id={eid}]不存在"
                    LOGGER.error(error_message)
                    raise NotFoundException(message=error_message)
                targets.append(instance)
        else:
            code_map: Dict[str, AutoTestEnvBindModel] = {
                obj.env_code: obj for obj in await self.model.filter(env_code__in=env_codes, state__not=1)
            }
            for ecode in env_codes:
                if not ecode:
                    error_message: str = "查询环境绑定信息失败, 参数[env_code]不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)
                instance = code_map.get(ecode)
                if not instance:
                    error_message: str = f"查询环境绑定信息失败, 记录[code={ecode}]不存在"
                    LOGGER.error(error_message)
                    raise NotFoundException(message=error_message)
                targets.append(instance)

        await scope.load_owners([instance.created_user for instance in targets])
        if not all(scope.can_delete(instance.created_user) for instance in targets):
            error_message: str = "删除环境绑定信息失败, 存在不在当前用户可删除范围内的环境绑定"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)
        # 软删同样受引用关系约束：先全量校验再落库，保证批量操作全有或全无
        await self._assert_envs_not_referenced(targets)
        await self.soft_delete_batch(ids=[instance.id for instance in targets])
        return len(targets)

    async def select_envs(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestEnvBindModel]]:
        """
        根据条件分页查询环境绑定列表。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)
        :raises ParameterException: 查询/排序字段不被ORM支持
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = "查询环境绑定信息失败，查询或排序条件包含不支持的字段，请调整筛选或排序条件"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def list_env_names(self, scope: Optional[DataScope] = None) -> List[str]:
        """
        查询去重后的环境名称。

        环境字典是全局共享的纯词典，无法直接按行级过滤：限定范围时先按可见范围取绑定引用的字典ID，
        再回查这些字典的名称；scope 为 None 时直接返回全部字典名称。

        :param scope: 数据权限上下文
        :return: 环境名称列表
        """
        owner_q = scope.read_q("created_user") if scope is not None else None
        if owner_q is None:
            return await AutoTestEnvModel.all().distinct().values_list("env_name", flat=True)
        enum_ids = await self.model.filter(owner_q, state__not=1).values_list("env_enum_id", flat=True)
        if not enum_ids:
            return []
        return await AutoTestEnvModel.filter(
            id__in=list(set(enum_ids))
        ).distinct().values_list("env_name", flat=True)

    async def serialize_env(self, bind: AutoTestEnvBindModel, with_audit: bool = False) -> Dict[str, Any]:
        """
        将环境绑定实例与字典信息拼装为响应结构。

        :param bind: 环境绑定实例
        :param with_audit: 是否附带审计字段(创建/更新人员与时间)
        :return: 环境响应字典
        """
        dict_names = await AutoTestEnvModel.filter(id=bind.env_enum_id).values_list("env_name", flat=True)
        return await self._assemble_env_dict(bind, dict_names[0] if dict_names else None, with_audit)

    async def serialize_envs(self, binds: List[AutoTestEnvBindModel], with_audit: bool = False) -> List[Dict[str, Any]]:
        """
        批量拼装环境绑定列表响应结构。

        :param binds: 环境绑定实例列表
        :param with_audit: 是否附带审计字段(创建/更新人员与时间)
        :return: 环境响应字典列表
        """
        dict_ids = list({bind.env_enum_id for bind in binds})
        dict_map: Dict[int, str] = dict(
            await AutoTestEnvModel.filter(id__in=dict_ids).values_list("id", "env_name")
        ) if dict_ids else {}
        return [
            await self._assemble_env_dict(bind, dict_map.get(bind.env_enum_id), with_audit)
            for bind in binds
        ]

    @staticmethod
    async def _assemble_env_dict(bind: AutoTestEnvBindModel, env_name: Optional[str], with_audit: bool) -> Dict[str, Any]:
        """
        拼装环境响应字典。

        接口仍返回env_id表示绑定主键；库内字段env_enum_id不对外暴露。

        :param bind: 环境绑定实例
        :param env_name: 环境名称，缺失时降级为空
        :param with_audit: 是否附带审计字段
        :return: 环境响应字典
        """
        exclude_fields = {"state", "reserve_1", "reserve_2", "reserve_3", "env_enum", "env_enum_id"}
        if not with_audit:
            exclude_fields.update({"created_user", "updated_user", "created_time", "updated_time"})
        data = await bind.to_dict(
            exclude_fields=exclude_fields,
            replace_fields={"id": "env_id"},
        )
        data["env_name"] = env_name or ""
        data["env_desc"] = bind.env_desc
        return data

    async def get_envs(
            self,
            project_id: Optional[List[int]] = None,
            scope: Optional[DataScope] = None,
    ) -> Union[Dict[str, List[str]], Dict[int, Dict[str, List[str]]]]:
        """
        按节点类型聚合环境名称（读环境绑定表并联字典）。

        :param project_id: None=全局聚合；[]=全部应用；[ids]=指定应用（无绑定的应用也返回空字典）
        :param scope: 数据权限上下文
        :return: {app/file/database/redis: [...]} 或 {project_id: {app/file/database/redis: [...]}}
        :raises ParameterException: 查询异常（含非法节点类型/脏数据），统一转为可读提示
        """
        try:
            allowed_types = set(AutoTestConfigNodeType.get_values())
            base_qs = self.model.filter(state=0)
            owner_q = scope.read_q("created_user") if scope is not None else None
            if owner_q is not None:
                base_qs = base_qs.filter(owner_q)

            if project_id is None:
                rows = await base_qs.values("env_type", "env_enum_id")
                name_map = await self._get_dict_name_map({row["env_enum_id"] for row in rows})
                env_map: Dict[str, set] = defaultdict(set)
                for row in rows:
                    env_type = row["env_type"].value if hasattr(row["env_type"], "value") else str(row["env_type"])
                    name = name_map.get(row["env_enum_id"])
                    if env_type in allowed_types and name:
                        env_map[env_type].add(name)
                return {et: sorted(names) for et, names in env_map.items()}

            unique_pids: Optional[List[int]] = None
            if not project_id:
                rows = await base_qs.values("project_id", "env_type", "env_enum_id")
            else:
                unique_pids = list(dict.fromkeys(project_id))
                rows = await base_qs.filter(project_id__in=unique_pids).values(
                    "project_id", "env_type", "env_enum_id"
                )

            name_map = await self._get_dict_name_map({row["env_enum_id"] for row in rows})
            grouped: Dict[int, Dict[str, set]] = defaultdict(lambda: defaultdict(set))
            for row in rows:
                env_type = row["env_type"].value if hasattr(row["env_type"], "value") else str(row["env_type"])
                name = name_map.get(row["env_enum_id"])
                if env_type in allowed_types and name:
                    grouped[row["project_id"]][env_type].add(name)

            result: Dict[int, Dict[str, List[str]]] = {}
            target_pids = unique_pids if unique_pids is not None else sorted(grouped.keys())
            for pid in target_pids:
                result[pid] = {et: sorted(names) for et, names in grouped.get(pid, {}).items()}
            return result
        except Exception as e:
            error_message: str = "查询环境信息失败，暂时无法获取环境信息，请稍后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [project_id={project_id}]\n"
                f"{traceback.format_exc()}"
            )
            raise ParameterException(message=error_message) from e

    @staticmethod
    async def _get_dict_name_map(dict_ids) -> Dict[int, str]:
        """
        批量查询字典ID到环境名称的映射；字典无状态字段，供已确认有效的绑定行取名。

        :param dict_ids: 环境字典主键ID集合（可重复）
        :return: {字典ID: 环境名称}；空入参返回空字典，字典缺失的ID不出现在结果中
        """
        if not dict_ids:
            return {}
        return dict(await AutoTestEnvModel.filter(id__in=list(dict_ids)).values_list("id", "env_name"))

    async def get_env_search_list(self, query_in: AutoTestEnvPageSelect, scope: DataScope) -> Tuple[int, List[Dict[str, Any]]]:
        """
        以环境绑定表分页查询；可选按子配置IP/配置名称过滤。

        is_delete 为历史字段名，实际语义是“该绑定下是否无启用中的子配置”（True=无子配置），
        前端据此切换删除确认文案，与本表自身的软删状态无关。

        :param query_in: 环境分页查询入参(过滤条件与分页)
        :param scope: 数据权限上下文
        :return: (总条数, 当前页记录)；记录含env_id(绑定主键)/project_id/env_name/env_type/project_name/created_user/is_delete/时间字段
        :raises ParameterException: 查询异常，统一转为可读提示
        """
        try:
            base_qs = self.model.filter(state=0)
            owner_q = scope.read_q("created_user")
            if owner_q is not None:
                base_qs = base_qs.filter(owner_q)

            if query_in.ip:
                matched_bind_ids = await AutoTestEnvConfigModel.filter(
                    state=0,
                    config_host__contains=query_in.ip,
                ).values_list("env_bind_id", flat=True)
                if not matched_bind_ids:
                    return 0, []
                base_qs = base_qs.filter(id__in=list(set(matched_bind_ids)))

            if query_in.config_name:
                matched_bind_ids = await AutoTestEnvConfigModel.filter(
                    state=0,
                    config_name__contains=query_in.config_name,
                ).values_list("env_bind_id", flat=True)
                if not matched_bind_ids:
                    return 0, []
                base_qs = base_qs.filter(id__in=list(set(matched_bind_ids)))

            if query_in.project_id is not None:
                base_qs = base_qs.filter(project_id=query_in.project_id)
            if query_in.env_name:
                dict_ids = await self.get_dict_ids_by_name(query_in.env_name)
                if not dict_ids:
                    return 0, []
                base_qs = base_qs.filter(env_enum_id__in=dict_ids)
            if query_in.env_type is not None:
                base_qs = base_qs.filter(env_type=query_in.env_type)

            # 启用应用一次取id+名称映射，既过滤禁用应用的绑定，也复用为页内project_name来源
            active_project_map: Dict[int, str] = dict(
                await AutoTestProjectModel.filter(state=0).values_list("id", "project_name")
            )
            if active_project_map:
                base_qs = base_qs.filter(project_id__in=list(active_project_map))

            total = await base_qs.count()
            offset = (query_in.page - 1) * query_in.page_size
            page_rows = await base_qs.offset(offset).limit(query_in.page_size).values(
                "id", "project_id", "env_enum_id", "created_user",
                "env_type", "created_time", "updated_time"
            )
            dict_name_map = await self._get_dict_name_map({item["env_enum_id"] for item in page_rows})
            check_ids = [item["id"] for item in page_rows]
            sub_exists = set()
            if check_ids:
                # 仅统计启用中的子配置：被软删的配置不算“仍有子表配置”
                config_rows = await AutoTestEnvConfigModel.filter(
                    env_bind_id__in=check_ids,
                    state=0,
                ).values_list("env_bind_id", flat=True)
                sub_exists = set(config_rows)

            result: List[Dict[str, Any]] = []
            for item in page_rows:
                env_bind_id = item["id"]
                created_time = item["created_time"]
                updated_time = item["updated_time"]
                result.append({
                    "env_id": env_bind_id,
                    "project_id": item["project_id"],
                    "env_name": dict_name_map.get(item["env_enum_id"]),
                    "env_type": item["env_type"],
                    "created_time": (
                        created_time.strftime(GLOBAL_CONFIG.DATETIME_FORMAT2)
                        if isinstance(created_time, datetime) else created_time
                    ),
                    "updated_time": (
                        updated_time.strftime(GLOBAL_CONFIG.DATETIME_FORMAT2)
                        if isinstance(updated_time, datetime) else updated_time
                    ),
                    "project_name": active_project_map.get(int(item["project_id"]), ""),
                    "created_user": item["created_user"],
                    "is_delete": env_bind_id not in sub_exists,
                })
            return total, result
        except ParameterException:
            raise
        except Exception as e:
            error_message: str = "查询环境搜索列表失败，暂时无法获取环境列表，请稍后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [project_id={query_in.project_id}, env_name={query_in.env_name}, "
                f"env_type={query_in.env_type}, page={query_in.page}, page_size={query_in.page_size}]\n"
                f"{traceback.format_exc()}"
            )
            raise ParameterException(message=error_message) from e
