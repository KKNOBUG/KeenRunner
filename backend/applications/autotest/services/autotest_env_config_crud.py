# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_config_crud
@DateTime: 2026/4/16 10:51
"""
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Union

from tortoise.exceptions import FieldError, IntegrityError, OperationalError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet
from tortoise.transactions import in_transaction

from backend.applications.autotest.models.autotest_env_config_model import AutoTestEnvBindModel, AutoTestEnvConfigModel
from backend.applications.autotest.schemas.autotest_env_config_schema import (
    AutoTestEnvConfigCreate,
    AutoTestEnvConfigUpdate,
    AutoTestEnvConfigDelete,
    AutoTestEnvConfigTypedDelete,
    QueryAssignConfigEnv,
)
from backend.applications.autotest.schemas.autotest_env_schema import AutoTestEnvCreate
from backend.applications.autotest.services.autotest_env_crud import AutoTestEnvCrud
from backend.applications.autotest.services.autotest_scope_guard import ENV_TAG, assert_parent_readable, load_readable_project
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.common.database.database_connection_pool import get_app_database_pool
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataAlreadyExistsException,
    DataBaseStorageException,
    NoPermissionException,
)
from backend.enums import AutoTestConfigNodeType
from backend.services import DataScope, get_current_username


class AutoTestEnvConfigCrud(ScaffoldCrud[AutoTestEnvConfigModel, AutoTestEnvConfigCreate, AutoTestEnvConfigUpdate]):

    def __init__(self):
        """绑定环境配置模型，供基类通用CRUD复用。"""
        super().__init__(model=AutoTestEnvConfigModel)

    async def get_by_id(self, config_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestEnvConfigModel]:
        """
        根据主键ID查询环境配置。

        :param config_id: 配置主键，必填
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 配置实例或None
        :raises ParameterException: config_id 为空
        :raises NotFoundException: on_error=True 且记录不存在
        """
        if not config_id:
            error_message: str = "查询配置信息失败, 参数[config_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.model.filter(id=config_id, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询配置信息失败, 记录[id={config_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, config_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestEnvConfigModel]:
        """
        根据配置标识代码查询环境配置。

        :param config_code: 配置标识代码，必填
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 配置实例或None
        :raises ParameterException: config_code 为空
        :raises NotFoundException: on_error=True 且记录不存在
        """
        if not config_code:
            error_message: str = "查询配置信息失败, 参数[config_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(config_code=config_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询配置信息失败, 记录[code={config_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    @classmethod
    def _deadlock_errno(cls, error: OperationalError) -> Optional[int]:
        """提取MySQL死锁(1213)/锁等待超时(1205)错误码，其他数据库异常返回None。"""
        raw = error.args[0] if error.args else None
        if isinstance(raw, BaseException) and getattr(raw, "args", None):
            return raw.args[0] if raw.args else None
        return None

    async def create_config(self, config_in: AutoTestEnvConfigCreate, scope: DataScope) -> AutoTestEnvConfigModel:
        """
        创建环境配置；同名软删记录在写权限内恢复启用。

        :param config_in: 环境配置创建schema（project_id/env_name/env_type用于解析绑定，不落配置表）
        :param scope: 数据权限上下文
        :return: 配置ORM实例
        :raises ParameterException: 环境名称为空
        :raises NotFoundException: 所属应用/环境绑定不存在或已软删
        :raises NoPermissionException: 应用或环境归属不在当前用户可操作范围
        :raises DataAlreadyExistsException: 同绑定下已存在启用态同名配置，或 host/port 重复
        :raises DataBaseStorageException: 落库失败（索引冲突或关联数据无效）
        """
        env_type = config_in.env_type
        project_id = int(config_in.project_id)
        config_name = config_in.config_name
        # B级父资源校验：应用必须可读，向后挂载的配置才能被当前用户感知
        await load_readable_project(scope, project_id)

        env_bind = await self._get_or_create_env_bind(
            scope=scope,
            project_id=project_id,
            env_name=config_in.env_name,
            env_type=env_type,
            created_user=config_in.created_user,
        )
        await assert_parent_readable(scope, ENV_TAG, env_bind, "环境")
        payload = config_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"env_name", "project_id", "env_type", "env_id"},
        )
        payload.update({"env_bind_id": env_bind.id, "state": 0})
        try:
            # 绑定内串行化写入：锁住同环境全部配置行，避免host唯一性预检被并发插入穿透
            async with in_transaction():
                await self._lock_bind_config_rows(int(env_bind.id))
                existing = await self.model.filter(env_bind_id=env_bind.id, config_name=config_name).first()
                if existing:
                    if existing.state == 0:
                        raise DataAlreadyExistsException(message="相同应用和环境下, 配置名称不允许重复")
                    # 软删恢复不得跨写范围接管他人配置，且不覆盖原创建人
                    await scope.load_owners([existing.created_user])
                    if not scope.can_write(existing.created_user):
                        error_message: str = f"新增环境配置失败, 配置[{config_name}]创建人[{existing.created_user}]不在当前用户可操作范围内"
                        LOGGER.error(error_message)
                        raise NoPermissionException(message=error_message)
                    payload.pop("created_user", None)
                    await self._assert_host_unique(env_bind_id=env_bind.id, env_type=env_type, mapped=payload, exclude_id=existing.id)
                    return await self.update(id=existing.id, obj_in=payload)

                await self._assert_host_unique(env_bind_id=env_bind.id, env_type=env_type, mapped=payload)
                return await self.create(obj_in=payload)
        except IntegrityError as e:
            error_message: str = "新增环境配置失败，配置名称、IP、端口或数据库名称可能与现有记录重复"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [env_bind_id={env_bind.id}, config_name={config_name}, config_host={payload.get('config_host')}, "
                f"config_port={payload.get('config_port')}, database_name={payload.get('database_name')}]\n"
                f"{traceback.format_exc()}"
            )
            raise DataBaseStorageException(message=error_message) from e
        except OperationalError as e:
            # 事务内的批量写入不经过基类的死锁转换，这里统一兜底
            errno: Optional[int] = self._deadlock_errno(e)
            if errno in (1213, 1205):
                error_message = "新增环境配置失败，操作存在并发冲突，请稍后重试"
                LOGGER.error(
                    f"{error_message}, "
                    f"关键字段: [env_bind_id={env_bind.id}, config_name={config_name}, errno={errno}]\n"
                    f"{traceback.format_exc()}"
                )
                raise DataBaseStorageException(message=error_message) from e
            raise

    async def update_config(
            self,
            config_in: AutoTestEnvConfigUpdate,
            scope: DataScope,
    ) -> Tuple[AutoTestEnvConfigModel, str, Dict[str, Any]]:
        """
        更新环境配置，按 config_id 或 config_code 定位。
        所属应用、环境与节点类型在创建时确定，更新时不再接受变更。
        仅修改地址、端口、账密、备注等配置信息时直接更新，修改 config_name 时同步同应用、同节点类型下所有环境的同名配置。

        :param config_in: 环境配置更新schema
        :param scope: 数据权限上下文
        :return: (更新后的配置实例, 环境名称, 绑定维度信息)；绑定维度供响应序列化复用，避免重复查询
        :raises ParameterException: 定位参数缺失、应用或节点与绑定不匹配、环境已下线、名称为空
        :raises NotFoundException: 配置或关联环境绑定不存在
        :raises NoPermissionException: 配置归属人不在写范围
        :raises DataAlreadyExistsException: 同绑定内名称或 host 重复，改名目标名称被同节点的其他环境占用
        :raises DataBaseStorageException: 落库失败或并发冲突
        """
        # 定位参数二选一，缺失时直接拒绝，避免无效查询
        config_id: Optional[int] = config_in.config_id
        config_code: Optional[str] = config_in.config_code
        if not config_id and not config_code:
            error_message = "更新环境配置失败, 参数[config_id, config_code]不允许同时为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        # 优先按主键定位，未传主键时回退配置编码
        if config_id:
            instance = await self.get_by_id(config_id=config_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(config_code=config_code, on_error=True, state__not=1)
            config_id = instance.id

        # 只有归属人在写范围内的用户才能修改主配置
        await scope.load_owners([instance.created_user])
        if not scope.can_write(instance.created_user):
            error_message = f"更新环境配置失败, 配置[{instance.config_name}]创建人[{instance.created_user}]不在当前用户可操作范围内"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)

        # 回查所属绑定，环境与节点以创建时的绑定为准；一次join取回环境名，响应序列化不再重复查询
        bind = await AutoTestEnvBindModel.filter(id=instance.env_bind_id).select_related("env_enum").first()
        if not bind:
            raise NotFoundException(message="配置关联的环境信息不存在")
        # 环境已下线时不再允许修改，避免改动不可见数据
        if bind.state != 0:
            raise ParameterException(message="配置关联的环境已下线, 不允许修改")
        # 所属应用不可变更
        if config_in.project_id is not None and int(config_in.project_id) != int(bind.project_id):
            raise ParameterException(message="配置关联的所属应用不匹配")
        # 所属节点不可变更，只允许修改当前更新接口对应的节点类型
        env_type = bind.env_type
        if config_in.env_type is not None and config_in.env_type != env_type:
            raise ParameterException(message="不支持修改配置所属节点")
        # 应用与环境是配置的父资源，更新前仍校验可读
        await load_readable_project(scope, int(bind.project_id))
        await assert_parent_readable(scope, ENV_TAG, bind, "环境")
        # 提取落库字段，环境与节点字段不参与更新
        update_dict = config_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"config_id", "config_code", "env_name", "project_id", "env_type", "env_id"},
        )
        # 显式置空的可空字段回补，避免 exclude_none 丢弃导致库内旧值残留
        self.explicit_restored_null_fields(
            config_in,
            update_dict,
            (
                "config_desc", "config_port", "config_group", "config_params",
                "config_username", "config_password", "config_kwargs", "config_header",
                "is_no_password", "database_name", "database_type",
            ),
        )
        config_name = update_dict.get("config_name", instance.config_name)
        # 空名称会绕过改名判断直接落库，服务层必须兜底
        if config_name is None or not str(config_name).strip():
            error_message = "更新环境配置失败, 参数[config_name]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 改名只同步名称，地址端口等具体信息只改当前配置
        is_renamed: bool = config_name != instance.config_name
        # host 不是数据库唯一键，相关字段变化时需在事务内加锁后重查
        host_changed: bool = (
                ("config_host" in update_dict and update_dict["config_host"] != instance.config_host)
                or ("config_port" in update_dict and update_dict["config_port"] != instance.config_port)
                or ("database_name" in update_dict and update_dict["database_name"] != instance.database_name)
        )
        sync_count: int = 0
        try:
            # 同环境写入串行化，保证host/port唯一性校验与落库之间不被并发插入穿透
            async with in_transaction():
                await self._lock_bind_config_rows(int(bind.id))
                if host_changed:
                    await self._assert_host_unique(
                        env_bind_id=bind.id,
                        env_type=env_type,
                        # 未传的列回退主行值，避免只改 host 时丢失端口与库名条件
                        mapped={
                            "config_host": update_dict.get("config_host", instance.config_host),
                            "config_port": update_dict.get("config_port", instance.config_port),
                            "database_name": update_dict.get("database_name", instance.database_name),
                        },
                        exclude_id=instance.id,
                    )
                # 改名走同应用、同节点类型的跨环境名称同步，其余场景按主行更新
                if is_renamed:
                    updated, sync_count = await self._sync_envs_config_name(
                        instance=instance,
                        project_id=int(bind.project_id),
                        env_type=env_type,
                        update_dict=update_dict,
                    )
                else:
                    updated = await self.update(id=config_id, obj_in=update_dict)
        # 唯一索引冲突统一转为存储异常，避免向前端泄露数据库细节
        except IntegrityError as e:
            error_message: str = "更新环境配置失败，配置名称、IP、端口或数据库名称可能与现有记录重复"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [config_id={config_id}, config_code={config_code}, env_bind_id={bind.id}, config_name={config_name}]\n"
                f"{traceback.format_exc()}"
            )
            raise DataBaseStorageException(message=error_message) from e
        # 事务内的批量写入不经过基类的死锁转换，这里统一兜底
        except OperationalError as e:
            errno: Optional[int] = self._deadlock_errno(e)
            if errno in (1213, 1205):
                error_message = "更新环境配置失败，操作存在并发冲突，请稍后重试"
                LOGGER.error(
                    f"{error_message}, "
                    f"关键字段: [config_id={config_id}, env_bind_id={bind.id}, errno={errno}]\n"
                    f"{traceback.format_exc()}"
                )
                raise DataBaseStorageException(message=error_message) from e
            raise
        if is_renamed:
            # 事务提交后再记录，避免回滚时误报完成
            LOGGER.info(
                f"环境配置改名同步完成, "
                f"关键字段: [project_id={int(bind.project_id)}, env_type={env_type}, "
                f"old_config_name={instance.config_name}, new_config_name={config_name}, sync_count={sync_count}]"
            )
        env_name: str = bind.env_enum.env_name if bind.env_enum else ""
        bind_meta: Dict[str, Any] = {
            "project_id": int(bind.project_id),
            "env_type": bind.env_type.value if hasattr(bind.env_type, "value") else bind.env_type,
        }
        return updated, env_name, bind_meta

    async def _sync_envs_config_name(
            self,
            *,
            instance: AutoTestEnvConfigModel,
            project_id: int,
            env_type: Union[AutoTestConfigNodeType, str],
            update_dict: Dict[str, Any],
    ) -> Tuple[AutoTestEnvConfigModel, int]:
        """
        配置改名时同步同应用、同节点类型下所有启用环境中的同名配置。

        :param instance: 待改名的主配置实例
        :param project_id: 配置所属应用ID
        :param env_type: 配置所属节点类型，同步范围限定在该节点
        :param update_dict: 已过滤的更新字段，config_name 为新名称
        :return: (改名后的主配置实例, 同步的其他配置条数)
        :raises DataAlreadyExistsException: 同节点下任一环境已存在新名称配置，包括占用唯一键的软删记录
        :raises DataBaseStorageException: 落库失败、并发冲突或行基线已变化
        """
        # 提前取出旧名、新名与环境 CRUD
        old_config_name: str = instance.config_name
        new_config_name: str = update_dict["config_name"]
        env_crud = AutoTestEnvCrud()

        # 只取同应用、同节点类型的启用绑定，不同节点名称互不影响
        bind_ids: List[int] = [
            int(bind_id)
            for bind_id in await AutoTestEnvBindModel.filter(
                project_id=project_id,
                env_type=env_type,
                state__not=1,
            ).values_list("id", flat=True)
        ]
        # 只取待同步配置的主键，同步范围不区分创建人
        required_sync_ids: List[int] = list(
            await self.model.filter(
                env_bind_id__in=bind_ids,
                config_name=old_config_name,
                state=0,
            ).exclude(id=instance.id).values_list("id", flat=True)
        )
        # 仅改大小写时新名会命中自身行，冲突预检必须排除主行与待同步行
        rename_config_ids: List[int] = [instance.id, *required_sync_ids]
        # 目标名称被任一配置占用都无法落库，唯一索引覆盖软删行
        conflict_configs: List[Dict[str, Any]] = await self.model.filter(
            env_bind_id__in=bind_ids,
            config_name=new_config_name,
        ).exclude(id__in=rename_config_ids).values("env_bind_id", "state")
        if conflict_configs:
            # 批量换取冲突环境名，软删记录点明占用唯一键
            conflict_labels: List[str] = []
            conflict_env_map = await env_crud.get_env_name_map(
                [int(conflict_config["env_bind_id"]) for conflict_config in conflict_configs]
            )
            for conflict_config in conflict_configs:
                env_label = conflict_env_map.get(int(conflict_config["env_bind_id"])) or f"bind_id={conflict_config['env_bind_id']}"
                label = f"{env_label}(含已删除记录)" if int(conflict_config["state"]) == 1 else env_label
                if label not in conflict_labels:
                    conflict_labels.append(label)
            # 整体拒绝并点出具体环境，便于定位历史数据
            error_message: str = f"更新环境配置失败, 环境[{', '.join(conflict_labels)}]下已存在同名配置[{new_config_name}], 无法同步改名"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        # 同步是底层行为，命中的配置无论创建人都一起改名；异常由调用方事务统一转换
        await self._lock_config_name_baseline(
            instance_id=instance.id,
            config_ids=required_sync_ids,
            config_name=old_config_name,
        )
        updated = await self.update(id=instance.id, obj_in=update_dict)
        if required_sync_ids:
            # 带旧名条件批量改名，重复提交不会覆盖已完成或人工调整的数据
            await self.model.filter(
                id__in=required_sync_ids,
                config_name=old_config_name,
            ).update(
                config_name=new_config_name,
                updated_user=get_current_username() or updated.updated_user or instance.updated_user,
                # 批量 update 不触发 auto_now，显式刷新更新时间
                updated_time=datetime.now(),
            )
        return updated, len(required_sync_ids)

    async def _lock_bind_config_rows(self, env_bind_id: int) -> None:
        """
        事务内锁定绑定下全部配置行，串行化同环境写入。

        同环境并发写入会先后锁同一批行，按主键升序加锁降低死锁概率，
        同时消除host唯一性预检与落库之间的竞态窗口。

        :param env_bind_id: 环境绑定ID
        :return: None
        """
        await self.model.filter(env_bind_id=env_bind_id).select_for_update().order_by("id").only("id")

    async def _lock_config_name_baseline(self, *, instance_id: int, config_ids: List[int], config_name: str) -> None:
        """
        在修改配置名称的事务内锁定主行与各环境下相同配置名称的数据行，校验它们仍处于旧名称基线。

        预检与写入之间存在时间窗：并发改名会把部分行改成新名称，并发删除会把行置为软删。
        这里按主键排序一次性加排他锁（当前读），缺行或名称不一致即整体回滚，
        既避免出现“部分环境新名、部分环境旧名”的不一致，也降低两个并发改名互相加锁的死锁概率。

        :param instance_id: 主配置ID
        :param config_ids: 待同步的配置ID列表
        :param config_name: 待修改的配置名称
        :return: None
        :raises DataBaseStorageException: 任一配置已被并发修改或软删
        """
        instance_ids: List[int] = sorted({int(instance_id), *[int(cid) for cid in config_ids]})
        locked_config_rows: List[AutoTestEnvConfigModel] = await self.model.filter(
            id__in=instance_ids,
            state=0,
        ).select_for_update().order_by("id").only("id", "config_name")
        locked_config_names: Dict[int, str] = {
            int(locked_row.id): locked_row.config_name for locked_row in locked_config_rows
        }
        # 名称比较按大小写不敏感处理，与库内唯一索引的排序规则保持一致
        expected_name: str = config_name.casefold()
        if len(locked_config_names) != len(instance_ids) or any(
                str(locked_name).casefold() != expected_name for locked_name in locked_config_names.values()
        ):
            error_message: str = "环境配置改名失败，部分环境的配置已被其他操作修改，请刷新后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [config_ids={instance_ids}, config_name={config_name}, locked_config_names={locked_config_names}]"
            )
            raise DataBaseStorageException(message=error_message)

    async def _assert_configs_not_referenced(self, targets: List[AutoTestEnvConfigModel]) -> None:
        """
        校验环境配置未被步骤按名称引用：请求配置、数据库操作、Redis操作三处。

        同应用的配置合并扫描，单次取出步骤行后按配置名匹配，避免逐条查库。

        :param targets: 待删除的环境配置实例列表
        :return: None
        :raises NotFoundException: 配置关联的环境绑定已不存在
        :raises DataAlreadyExistsException: 任一配置被步骤引用时拒绝删除
        """
        if not targets:
            return
        from backend.applications.autotest.models.autotest_case_model import AutoTestCaseModel
        from backend.applications.autotest.models.autotest_step_model import AutoTestStepModel

        bind_map: Dict[int, int] = {
            obj.id: obj.project_id
            for obj in await AutoTestEnvBindModel.filter(id__in=[item.env_bind_id for item in targets])
        }
        # 配置名只在所属应用的用例步骤中生效，按项目归组后统一扫描
        names_by_project: Dict[int, List[str]] = {}
        for instance in targets:
            project_id = bind_map.get(instance.env_bind_id)
            if project_id is None:
                raise NotFoundException(message=f"配置[{instance.config_name}]关联的环境信息不存在")
            names_by_project.setdefault(project_id, []).append(instance.config_name)

        for project_id, config_names in names_by_project.items():
            case_ids = await AutoTestCaseModel.filter(
                case_project=project_id, state__not=1
            ).values_list("id", flat=True)
            if not case_ids:
                continue
            step_rows = await AutoTestStepModel.filter(
                case_id__in=list(case_ids), state__not=1
            ).values("request_config_name", "database_operates", "redis_operates")
            # 单次扫描步骤并按目标配置名聚合引用数，避免逐个配置回扫步骤
            target_names = set(config_names)
            ref_counts: Dict[str, int] = {}
            for row in step_rows:
                step_names = set()
                if row["request_config_name"]:
                    step_names.add(row["request_config_name"])
                for field in ("database_operates", "redis_operates"):
                    operates = row[field]
                    if not isinstance(operates, list):
                        continue
                    step_names.update(
                        operate["config_name"]
                        for operate in operates
                        if isinstance(operate, dict) and operate.get("config_name")
                    )
                # 同一配置在单个步骤内多处引用只计一次，与“引用该配置的步骤数”口径一致
                for config_name in step_names & target_names:
                    ref_counts[config_name] = ref_counts.get(config_name, 0) + 1
            for config_name in config_names:
                ref_count: int = ref_counts.get(config_name, 0)
                if ref_count > 0:
                    error_message: str = f"删除环境配置失败, 配置[{config_name}]被{ref_count}个步骤引用"
                    LOGGER.error(error_message)
                    raise DataAlreadyExistsException(message=error_message)

    async def delete_config(self, config_in: AutoTestEnvConfigTypedDelete, scope: DataScope) -> AutoTestEnvConfigModel:
        """
        按节点类型物理删除环境配置；被步骤引用时禁止删除。

        :param config_in: 删除入参
        :param scope: 数据权限上下文
        :return: 删除后的配置实例快照
        :raises ParameterException: 环境节点类型不匹配
        :raises NotFoundException: 配置或关联环境绑定不存在
        :raises NoPermissionException: 配置创建人不在当前用户可删除范围
        :raises DataAlreadyExistsException: 配置仍被步骤引用
        """
        instance = await self.get_by_id(config_id=config_in.config_id, on_error=True)
        bind = await AutoTestEnvBindModel.filter(id=instance.env_bind_id).first()
        if not bind:
            raise NotFoundException(message="配置关联的环境信息不存在")
        if bind.env_type != config_in.env_type:
            raise ParameterException(message="配置关联的环境节点不匹配")
        await scope.load_owners([instance.created_user])
        if not scope.can_delete(instance.created_user):
            error_message: str = f"删除环境配置失败, 配置[{instance.config_name}]创建人[{instance.created_user}]不在当前用户可删除范围内"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)

        await self._assert_configs_not_referenced([instance])

        await instance.delete()
        return instance

    async def delete_configs(self, config_in: AutoTestEnvConfigDelete, scope: DataScope) -> int:
        """
        根据ID或code列表批量软删除环境配置；软删与物理删同样拒绝被步骤引用的配置。

        :param config_in: 环境配置批量删除schema
        :param scope: 数据权限上下文，仅允许删除归属人在当前用户可删除范围内的环境配置
        :return: 更新条数
        :raises ParameterException: 两个定位参数同时为空，或列表中包含空值
        :raises NotFoundException: 任一目标配置不存在或已软删，或关联环境丢失
        :raises NoPermissionException: 任一配置创建人不在当前用户可删除范围
        :raises DataAlreadyExistsException: 任一配置仍被步骤引用
        """
        config_ids: Optional[List[int]] = config_in.config_ids
        config_codes: Optional[List[str]] = config_in.config_codes
        if not config_ids and not config_codes:
            error_message: str = "删除配置信息失败, 参数[config_ids, config_codes]不允许同时为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        targets: List[AutoTestEnvConfigModel] = []
        if config_ids:
            id_map: Dict[int, AutoTestEnvConfigModel] = {
                obj.id: obj for obj in await self.model.filter(id__in=config_ids, state__not=1)
            }
            for cid in config_ids:
                if not cid:
                    error_message: str = "查询配置信息失败, 参数[config_id]不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)
                instance = id_map.get(cid)
                if not instance:
                    error_message: str = f"查询配置信息失败, 记录[id={cid}]不存在"
                    LOGGER.error(error_message)
                    raise NotFoundException(message=error_message)
                targets.append(instance)
        else:
            code_map: Dict[str, AutoTestEnvConfigModel] = {
                obj.config_code: obj for obj in await self.model.filter(config_code__in=config_codes, state__not=1)
            }
            for ccode in config_codes:
                if not ccode:
                    error_message: str = "查询配置信息失败, 参数[config_code]不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)
                instance = code_map.get(ccode)
                if not instance:
                    error_message: str = f"查询配置信息失败, 记录[code={ccode}]不存在"
                    LOGGER.error(error_message)
                    raise NotFoundException(message=error_message)
                targets.append(instance)

        await scope.load_owners([instance.created_user for instance in targets])
        if not all(scope.can_delete(instance.created_user) for instance in targets):
            error_message: str = "删除环境配置失败, 存在不在当前用户可删除范围内的环境配置"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)
        # 软删同样受引用关系约束：先全量校验再落库，保证批量操作全有或全无
        await self._assert_configs_not_referenced(targets)
        await self.soft_delete_batch(ids=[instance.id for instance in targets])
        return len(targets)

    async def select_config(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestEnvConfigModel]]:
        """
        根据条件分页查询环境配置列表。

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
            error_message: str = "查询配置信息失败，查询或排序条件包含不支持的字段，请调整筛选或排序条件"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def query_classified_by_project_ids(
            self,
            project_ids: List[int],
            config_names: Optional[List[str]] = None,
            scope: Optional[DataScope] = None,
    ) -> Dict[int, Dict[str, Dict[str, Dict[str, Dict[str, Any]]]]]:
        """
        按应用ID列表查询未删除配置并分类。

        返回结构固定包含传入的每个应用；已出现环境会预置全部节点类型的空桶，
        使调用方（调试/执行取环境）无需做层级判空。无环境名称或未知节点类型的配置会被跳过并告警。

        :param project_ids: 应用ID列表
        :param config_names: 配置名称列表(可选)；非空时仅返回这些配置所在的环境及其配置
        :param scope: 数据权限上下文，传入时仅返回可见范围内的配置
        :return: project_id -> env_name -> api|file|database|redis -> config_name -> 主机信息
        :raises ParameterException: project_ids 为空
        """
        if not project_ids:
            error_message: str = "按应用列表查询环境配置失败, 参数[project_ids]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        distinct_project_ids: List[int] = list(dict.fromkeys(project_ids))
        classified_config_result: Dict[int, Dict[str, Dict[str, Dict[str, Dict[str, Any]]]]] = {
            project_id: {}
            for project_id in distinct_project_ids
        }
        allowed_types = set(AutoTestConfigNodeType.get_values())
        empty_type_buckets = {t: {} for t in allowed_types}

        bind_rows = await AutoTestEnvBindModel.filter(
            project_id__in=distinct_project_ids,
            state__not=1,
        ).values("id", "project_id", "env_type", "env_enum_id")
        if not bind_rows:
            return classified_config_result

        bind_meta = {
            row["id"]: {
                "project_id": row["project_id"],
                "env_type": row["env_type"],
                "env_enum_id": row["env_enum_id"],
            }
            for row in bind_rows
        }
        env_bind_ids = list(bind_meta.keys())
        # 配置名称过滤：非空时仅返回这些配置所在的环境及其配置（去重去空白）
        distinct_config_names: List[str] = [
            str(n).strip() for n in (config_names or []) if n is not None and str(n).strip()
        ]
        config_filter: Dict[str, Any] = {"env_bind_id__in": env_bind_ids, "state__not": 1}
        if distinct_config_names:
            config_filter["config_name__in"] = list(dict.fromkeys(distinct_config_names))
        owner_q = scope.read_q("created_user") if scope is not None else None
        config_qs = self.model.filter(**config_filter)
        if owner_q is not None:
            config_qs = config_qs.filter(owner_q)
        env_config_rows: List[Dict[str, Any]] = await config_qs.values(
            "id", "env_bind_id", "config_name", "config_host", "config_port", "database_name"
        )
        if not env_config_rows:
            return classified_config_result

        # 绑定行已带字典ID，直接批量取名，避免二次回查绑定表
        dict_name_map: Dict[int, str] = await AutoTestEnvCrud._get_dict_name_map(
            {int(row["env_enum_id"]) for row in bind_rows}
        )
        for cfg_row in env_config_rows:
            meta = bind_meta.get(int(cfg_row["env_bind_id"]))
            if not meta:
                continue
            project_id: int = int(meta["project_id"])
            if project_id not in classified_config_result:
                continue
            env_name: Optional[str] = dict_name_map.get(int(meta["env_enum_id"]))
            if not env_name:
                LOGGER.warning(f"跳过无对应环境主表记录的配置: config_id={cfg_row['id']}, env_bind_id={cfg_row['env_bind_id']}")
                continue
            env_type = meta["env_type"].value if hasattr(meta["env_type"], "value") else str(meta["env_type"])
            if env_type not in allowed_types:
                LOGGER.warning(f"跳过未知配置类型: project_id={project_id}, env={env_name}, env_type={env_type}")
                continue
            if env_name not in classified_config_result[project_id]:
                classified_config_result[project_id][env_name] = {
                    t: {} for t in empty_type_buckets
                }
            classified_config_result[project_id][env_name][env_type][cfg_row["config_name"]] = {
                "config_host": cfg_row["config_host"],
                "config_port": cfg_row["config_port"],
                "database_name": cfg_row["database_name"],
            }
        return classified_config_result

    async def list_distinct_config_names(
            self,
            project_id: Optional[int] = None,
            env_id: Optional[int] = None,
            env_type: Optional[str] = None,
            scope: Optional[DataScope] = None,
    ) -> List[str]:
        """
        未删除配置中config_name去重后的列表。

        定位优先级：env_id 直接限定绑定；否则 project_id/env_type 经绑定表换算出绑定ID集合。

        :param project_id: 应用ID，经绑定表过滤
        :param env_id: 环境绑定主键
        :param env_type: 节点类型，经绑定表过滤
        :param scope: 数据权限上下文，传入时仅返回可见范围内的配置名称
        :return: 去重且升序排列的配置名称列表
        """
        stmt: QuerySet = self.model.filter(state__not=1)
        owner_q = scope.read_q("created_user") if scope is not None else None
        if owner_q is not None:
            stmt = stmt.filter(owner_q)
        if env_id is not None:
            stmt = stmt.filter(env_bind_id=env_id)
        elif project_id is not None or env_type is not None:
            env_bind_ids = await AutoTestEnvCrud().list_bind_ids(
                project_id=project_id,
                env_type=env_type,
            )
            if not env_bind_ids:
                return []
            stmt = stmt.filter(env_bind_id__in=env_bind_ids)
        names = await stmt.values_list("config_name", flat=True)
        return sorted(set(names))

    async def query_assign_config_env_names(
            self,
            query_in: QueryAssignConfigEnv,
            scope: Optional[DataScope] = None,
    ) -> List[str]:
        """
        按应用/配置名称/节点类型查询符合的环境名称列表。

        与 list_distinct_config_names 不同，这里经外键反向取环境名（env_bind__env_enum__env_name）。

        :param query_in: 指派配置环境查询入参(三条件均可选)
        :param scope: 数据权限上下文，传入时仅返回可见范围内的配置所对应的环境名称
        :return: 去重且升序排列的环境名称列表
        """
        stmt: QuerySet = self.model.filter(state__not=1)
        owner_q = scope.read_q("created_user") if scope is not None else None
        if owner_q is not None:
            stmt = stmt.filter(owner_q)
        if query_in.config_name:
            stmt = stmt.filter(config_name=query_in.config_name)
        if query_in.project_id is not None or query_in.env_type is not None:
            env_bind_ids = await AutoTestEnvCrud().list_bind_ids(
                project_id=query_in.project_id,
                env_type=query_in.env_type,
            )
            if not env_bind_ids:
                return []
            stmt = stmt.filter(env_bind_id__in=env_bind_ids)
        # 环境链为真实外键, 经绑定表跨取环境名称
        names: List[str] = await stmt.values_list("env_bind__env_enum__env_name", flat=True)
        return sorted(set(names))

    async def serialize_config(
            self,
            instance: AutoTestEnvConfigModel,
            env_name: str = "",
            bind_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        按表字段序列化配置，并附带绑定派生字段与env_name。

        :param instance: 配置ORM实例
        :param env_name: 环境名称
        :param bind_meta: 可选绑定维度 {project_id, env_type}
        :return: 响应字典；接口字段保持config_id/env_id/project_id/env_type不变
        """
        data = await instance.to_dict(
            exclude_fields={"reserve_1", "reserve_2", "reserve_3", "env_bind", "env_bind_id", "state"},
            replace_fields={"id": "config_id"},
        )
        if bind_meta is None:
            bind_meta = (await AutoTestEnvCrud().get_bind_map([instance.env_bind_id])).get(instance.env_bind_id, {})
        data["env_name"] = env_name
        data["env_id"] = instance.env_bind_id
        data["project_id"] = bind_meta.get("project_id")
        data["env_type"] = bind_meta.get("env_type")
        return data

    async def _get_or_create_env_bind(
            self,
            *,
            scope: DataScope,
            project_id: int,
            env_name: str,
            env_type: Union[AutoTestConfigNodeType, str],
            created_user: Optional[str] = None,
    ) -> AutoTestEnvBindModel:
        """
        按应用+环境名+节点类型获取或创建环境绑定记录。

        :param scope: 数据权限上下文，透传给环境绑定创建以校验应用可读与写范围
        :param project_id: 应用ID
        :param env_name: 环境名称（会规范化为大写）
        :param env_type: 节点类型(app/file/database/redis)
        :param created_user: 无登录上下文时的回落创建人；有登录上下文时由Scaffold覆盖
        :return: 环境绑定实例
        :raises ParameterException: 环境名称为空
        :raises NotFoundException: 应用不存在或已软删
        :raises NoPermissionException: 应用/环境绑定归属不在当前用户可操作范围
        :raises DataBaseStorageException: 绑定落库失败
        """
        name = (env_name or "").strip().upper()
        if not name:
            raise ParameterException(message="参数[env_name]不允许为空")
        return await AutoTestEnvCrud().create_env(
            AutoTestEnvCreate(
                env_name=name,
                project_id=project_id,
                env_type=env_type,
                created_user=created_user,
                env_desc=None,
            ),
            scope=scope,
        )

    async def _assert_host_unique(
            self,
            *,
            env_bind_id: int,
            env_type: Union[AutoTestConfigNodeType, str],
            mapped: Dict[str, Any],
            exclude_id: Optional[int] = None,
    ) -> None:
        """
        校验同绑定下host/port(/database_name)唯一。

        未传 host 时视为不限制（凭据型配置可能只有名称）；仅 DB 节点额外比较 database_name。

        唯一性含节点类型、软删与空值等条件分支，无法用普通唯一索引表达，
        由调用方在同一事务内加锁后校验，保证少量并发下不产生重复主机。

        :param env_bind_id: 环境绑定ID
        :param env_type: 节点类型（仅影响DB提示文案与database_name条件）
        :param mapped: 已映射的落库字段
        :param exclude_id: 更新时排除的配置ID
        :return: None
        :raises DataAlreadyExistsException: 命中同 host/port(/database_name) 的启用态配置
        """
        host = mapped.get("config_host")
        if not host:
            return
        dup_q = self.model.filter(
            env_bind_id=env_bind_id,
            config_host=host,
            state=0,
        )
        if exclude_id is not None:
            dup_q = dup_q.exclude(id=exclude_id)
        port = mapped.get("config_port")
        if port is not None:
            dup_q = dup_q.filter(config_port=port)
        if env_type == AutoTestConfigNodeType.DB and mapped.get("database_name"):
            dup_q = dup_q.filter(database_name=mapped["database_name"])
        if await dup_q.exists():
            if env_type == AutoTestConfigNodeType.DB:
                raise DataAlreadyExistsException(message="相同应用和环境下，数据库名称、IP和端口不允许重复")
            raise DataAlreadyExistsException(message="相同应用和环境下，IP和端口不允许重复")

    async def get_config_list(
            self,
            project_id: Optional[int] = None,
            env_name: Optional[str] = None,
            env_type: Optional[Union[AutoTestConfigNodeType, str]] = None,
            page: int = 1,
            page_size: int = 10,
            scope: Optional[DataScope] = None,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        分页查询环境配置；project/env_name/env_type经绑定表过滤。

        :param project_id: 应用ID
        :param env_name: 环境名称
        :param env_type: 节点类型(app/file/database/redis)
        :param page: 页码
        :param page_size: 每页条数
        :param scope: 数据权限上下文，传入时仅返回可见范围内的配置（含凭据信息）
        :return: (总条数, 当前页列表)
        :raises ParameterException: 查询异常，统一转为可读提示
        """
        try:
            env_crud = AutoTestEnvCrud()
            query = self.model.filter(state=0)
            owner_q = scope.read_q("created_user") if scope is not None else None
            if owner_q is not None:
                query = query.filter(owner_q)
            need_bind_filter = project_id is not None or env_name or env_type is not None
            if need_bind_filter:
                env_enum_ids = None
                if env_name:
                    env_enum_ids = await env_crud.get_dict_ids_by_name(env_name, exact=True)
                    if not env_enum_ids:
                        return 0, []
                matched_bind_ids = await env_crud.list_bind_ids(
                    project_id=project_id,
                    env_type=env_type,
                    env_enum_ids=env_enum_ids,
                )
                if not matched_bind_ids:
                    return 0, []
                query = query.filter(env_bind_id__in=list(matched_bind_ids))

            total = await query.count()
            instances = await query.offset((page - 1) * page_size).limit(page_size).all()
            env_bind_ids = list({obj.env_bind_id for obj in instances})
            env_name_map = await env_crud.get_env_name_map(env_bind_ids)
            bind_map = await env_crud.get_bind_map(env_bind_ids)
            result = [
                await self.serialize_config(
                    obj,
                    env_name_map.get(obj.env_bind_id, ""),
                    bind_map.get(obj.env_bind_id),
                )
                for obj in instances
            ]
            return total, result
        except ParameterException:
            raise
        except Exception as e:
            error_message: str = "查询环境配置失败，暂时无法获取配置列表，请稍后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [project_id={project_id}, env_name={env_name}, env_type={env_type}, page={page}, page_size={page_size}]\n"
                f"{traceback.format_exc()}"
            )
            raise ParameterException(message=error_message) from e

    async def test_db_connection(
            self,
            config_id: int,
            project_id: int,
            env_name: str,
            config_name: str,
            database_name: str,
            scope: Optional[DataScope] = None,
    ) -> Dict[str, Any]:
        """
        校验DB配置存在后创建连接池。

        :param config_id: 配置ID
        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param database_name: 数据库名称
        :param scope: 数据权限上下文，传入时要求配置创建人在可见范围内
        :return: 连接成功时的摘要信息
        :raises NotFoundException: 环境绑定或配置不存在
        :raises NoPermissionException: 配置创建人不在当前用户可见范围
        :raises DataBaseStorageException: 连接池创建失败
        """
        env_row = await AutoTestEnvCrud().get_bind_by_env_name(
            project_id=project_id,
            env_name=env_name,
            env_type=AutoTestConfigNodeType.DB,
        )
        if not env_row:
            raise NotFoundException(message="配置表未找到对应记录，请检查")

        config = await self.model.filter(
            id=config_id,
            env_bind_id=env_row.id,
            config_name=config_name,
            database_name=database_name,
            state=0,
        ).first()
        if not config:
            raise NotFoundException(message="配置表未找到对应记录，请检查")

        # 连接测试会暴露主机端口等凭据信息，必须限制在可见范围内
        if scope is not None:
            await scope.load_owners([config.created_user])
        if scope is not None and not scope.can_read(config.created_user):
            error_message = f"测试数据库连接失败, 配置[{config_name}]创建人[{config.created_user}]不在当前用户可见范围"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)

        try:
            await get_app_database_pool().get_or_create_pool(
                project_id=project_id,
                env_name=env_name,
                config_name=config_name,
                database_name=database_name,
            )
        except Exception as e:
            error_message: str = "数据库连接测试失败，暂时无法建立连接池，请检查配置后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [config_id={config_id}, project_id={project_id}, env_name={env_name}, "
                f"config_name={config_name}, database_name={database_name}]\n"
                f"{traceback.format_exc()}"
            )
            raise DataBaseStorageException(message=error_message) from e

        return {
            "config_id": config_id,
            "database_type": config.database_type,
            "config_host": config.config_host,
            "config_port": config.config_port,
        }
