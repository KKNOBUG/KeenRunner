# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_config_crud
@DateTime: 2026/4/16 10:51
"""
import traceback
from collections import defaultdict
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Union

from tortoise.exceptions import FieldError, IntegrityError, OperationalError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet
from tortoise.transactions import in_transaction

from backend.applications.autotest.models.autotest_case_model import AutoTestCaseModel
from backend.applications.autotest.models.autotest_env_config_model import AutoTestEnvBindModel, AutoTestEnvConfigModel
from backend.applications.autotest.models.autotest_step_model import AutoTestStepModel
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
from backend.applications.base.services.scaffold import ScaffoldCrud, unique_identify
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
from backend.services.transport_crypto import assert_cipher_format


class AutoTestEnvConfigCrud(ScaffoldCrud[AutoTestEnvConfigModel, AutoTestEnvConfigCreate, AutoTestEnvConfigUpdate]):
    """环境配置CRUD：环境配置表krun_autotest_env_config的创建、更新、改名同步、删除引用校验、查询分类。"""

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
        """提取MySQL死锁1213与锁等待超时1205错误码，其他数据库异常返回None。"""
        raw = error.args[0] if error.args else None
        if isinstance(raw, BaseException) and getattr(raw, "args", None):
            return raw.args[0] if raw.args else None
        return None

    @staticmethod
    def _assert_password_payload(config_password: Optional[str], env_type: Union[AutoTestConfigNodeType, str], is_update: bool) -> None:
        """
        密码入参校验：非空只接受RSA密文；更新未传/None表示不修改。

        :param config_password: 入参密码值
        :param env_type: 节点类型，空串清空仅限Redis/File
        :param is_update: 是否更新场景
        :raises ParameterException: 明文传递或DB密码清空
        """
        if config_password is None:
            return
        if config_password == "":
            # 空串是免密/清空信号；DB密码必填不允许清空
            if is_update and env_type == AutoTestConfigNodeType.DB:
                error_message: str = "更新环境配置失败, DB配置密码不允许清空"
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)
            return
        assert_cipher_format(config_password)

    async def create_config(self, config_in: AutoTestEnvConfigCreate, scope: DataScope) -> AutoTestEnvConfigModel:
        """
        创建环境配置；同应用同节点同名配置复用逻辑标识，同名软删记录在写权限内恢复启用。

        :param config_in: 环境配置创建schema（project_id/env_name/env_type 用于解析绑定，env_name 不落配置表，project_id/env_type 冗余回填）
        :param scope: 数据权限上下文
        :return: 配置ORM实例
        :raises ParameterException: 配置名称或环境名称为空
        :raises NotFoundException: 所属应用/环境绑定不存在或已软删
        :raises NoPermissionException: 应用或环境归属不在当前用户可操作范围
        :raises DataAlreadyExistsException: 同绑定下已存在启用态同名配置，或 host/port 重复
        :raises DataBaseStorageException: 落库失败（索引冲突或关联数据无效）
        """
        env_type = config_in.env_type
        project_id = int(config_in.project_id)
        config_name = config_in.config_name.strip()
        # schema 只约束必填，空白名称会绕过改名与唯一性判断直接落库，入口必须拦截
        if not config_name:
            error_message: str = "新增环境配置失败, 参数[config_name]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        # 密码只接受RSA密文，明文传递在服务层入口拒绝
        self._assert_password_payload(config_in.config_password, env_type, is_update=False)
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
            # 锁定同应用同节点的全部启用绑定行：创建/恢复与改名在该维度串行，
            # 保证“按名查逻辑配置—落库”之间不被并发写入穿透（设计 5.2）
            async with in_transaction():
                await self._lock_project_type_binds(project_id, env_type)
                existing = await self.model.filter(
                    env_bind_id=env_bind.id,
                    config_name__iexact=config_name,
                ).first()
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
                    if existing.config_mode:
                        # 恢复沿用原逻辑标识；同组启用行存在时以现有写法为准（设计 5.6）
                        sibling_names: List[str] = await self.model.filter(
                            config_mode=existing.config_mode,
                            state=0,
                        ).exclude(id=existing.id).order_by("id").values_list("config_name", flat=True)
                        payload["config_mode"] = existing.config_mode
                        payload["config_name"] = sibling_names[0] if sibling_names else existing.config_name
                    else:
                        # 批次空隙遗留的空标识行：按同名启用行解析或就地补标识，避免分裂第二组逻辑配置
                        mode, canonical_name = await self._resolve_config_mode(
                            project_id=project_id,
                            env_type=env_type,
                            config_name=existing.config_name,
                        )
                        payload["config_mode"] = mode
                        payload["config_name"] = canonical_name
                    payload["project_id"] = project_id
                    payload["env_type"] = env_type
                    await self._assert_host_unique(env_bind_id=env_bind.id, env_type=env_type, mapped=payload, exclude_id=existing.id)
                    return await self.update(id=existing.id, obj_in=payload)

                # 同应用同节点下同名配置共享一个逻辑标识，名称取已有写法（设计 5.2/5.9）
                mode, canonical_name = await self._resolve_config_mode(
                    project_id=project_id,
                    env_type=env_type,
                    config_name=config_name,
                )
                payload["config_mode"] = mode
                payload["config_name"] = canonical_name
                payload["project_id"] = project_id
                payload["env_type"] = env_type
                await self._assert_host_unique(env_bind_id=env_bind.id, env_type=env_type, mapped=payload)
                return await self.create(obj_in=payload)
        except IntegrityError as e:
            error_message: str = "新增环境配置失败, 配置名称、IP、端口或数据库名称与现有记录冲突"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [env_bind_id={env_bind.id}, config_name={config_name}, config_host={payload.get('config_host')}, config_port={payload.get('config_port')}, database_name={payload.get('database_name')}]\n"
                f"异常回溯: {traceback.format_exc()}"
            )
            raise DataBaseStorageException(message=error_message) from e
        except OperationalError as e:
            # 事务内的批量写入不经过基类的死锁转换，这里统一兜底
            errno: Optional[int] = self._deadlock_errno(e)
            if errno in (1213, 1205):
                error_message = "新增环境配置失败, 操作存在并发冲突"
                LOGGER.error(
                    f"{error_message}, "
                    f"关键字段: [env_bind_id={env_bind.id}, config_name={config_name}, errno={errno}]\n"
                    f"{traceback.format_exc()}"
                )
                raise DataBaseStorageException(message=error_message) from e
            raise

    async def update_config(self, config_in: AutoTestEnvConfigUpdate, scope: DataScope, ) -> Tuple[AutoTestEnvConfigModel, str, Dict[str, Any]]:
        """
        更新环境配置：按 config_id 或 config_code 定位，改名时同步该逻辑配置的全部启用实例。

        :param config_in: 环境配置更新schema
        :param scope: 数据权限上下文
        :return: (更新后的配置实例, 环境名称, 绑定维度信息)；绑定维度供响应序列化复用，避免重复查询
        :raises ParameterException: 定位参数缺失、应用或节点与绑定不匹配、环境已下线、名称为空
        :raises NotFoundException: 配置或关联环境绑定不存在
        :raises NoPermissionException: 配置归属人不在写范围
        :raises DataAlreadyExistsException: 同绑定内名称或 host 重复，改名目标名称被同环境内的同名配置占用（含软删记录）
        :raises DataBaseStorageException: 落库失败或并发冲突
        """
        # 所属应用、环境与节点类型在创建时确定，更新时不再接受变更；
        # 不改名时仅更新当前配置的地址/端口/账密/备注等，改名时同步该逻辑配置的全部启用实例
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
        # 环境名已随绑定 join 取回，改名冲突文案与响应序列化共用，不再重复查库
        env_name: str = bind.env_enum.env_name if bind.env_enum else ""
        # 所属应用不可变更
        if config_in.project_id is not None and int(config_in.project_id) != int(bind.project_id):
            raise ParameterException(message="配置关联的所属应用不匹配")
        # 所属节点不可变更，只允许修改当前更新接口对应的节点类型
        env_type = bind.env_type
        if config_in.env_type is not None and config_in.env_type != env_type:
            raise ParameterException(message="不支持修改配置所属节点")
        # 密码只接受RSA密文；未传/None不修改，空串仅限Redis/File免密清空
        self._assert_password_payload(config_in.config_password, env_type, is_update=True)
        # 应用与环境是配置的父资源，更新前仍校验可读
        await load_readable_project(scope, int(bind.project_id))
        await assert_parent_readable(scope, ENV_TAG, bind, "环境")
        # 提取落库字段，环境与节点字段不参与更新
        update_dict = config_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"config_id", "config_code", "env_name", "project_id", "env_type", "env_id"},
        )
        # 显式置空的可空字段回补，避免 exclude_none 丢弃导致库内旧值残留；
        # config_password 不在回补列：未传/None表示不修改，清空只走空串免密信号
        self.explicit_restored_null_fields(
            config_in,
            update_dict,
            (
                "config_desc", "config_port", "config_group", "config_params",
                "config_username", "config_kwargs", "config_header",
                "is_no_password", "database_name", "database_type",
            ),
        )
        # 与创建入口同口径：先 strip 再校验，避免带空白名称绕过同名判定（设计 5.2）
        if "config_name" in update_dict:
            update_dict["config_name"] = str(update_dict["config_name"] or "").strip()
        config_name = update_dict.get("config_name", instance.config_name)
        # 空名称会绕过改名判断直接落库，服务层必须兜底
        if not config_name:
            error_message = "更新环境配置失败, 参数[config_name]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        # 逻辑标识决定改名同步范围；冗余维度随写入同步，空标识在事务锁内补齐
        config_mode: str = str(instance.config_mode or "")
        update_dict["config_mode"] = config_mode
        update_dict["project_id"] = int(bind.project_id)
        update_dict["env_type"] = env_type

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
            # 先锁同应用同节点绑定行（与创建/恢复互斥），改名时再锁同标识行
            async with in_transaction():
                await self._lock_project_type_binds(int(bind.project_id), env_type)
                if not config_mode:
                    # 批次空隙遗留的空标识在锁内补齐，避免与并发创建分裂出第二组逻辑配置
                    config_mode, _ = await self._resolve_config_mode(
                        project_id=int(bind.project_id),
                        env_type=env_type,
                        config_name=instance.config_name,
                    )
                    update_dict["config_mode"] = config_mode
                    LOGGER.warning(
                        f"环境配置逻辑标识为空已自动补齐, 关键字段: [config_id={instance.id}, config_mode={config_mode}]"
                    )
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
                # 改名走同逻辑标识跨环境同步，其余场景按主行更新
                if is_renamed:
                    updated, sync_count = await self._sync_config_mode_group_name(
                        instance=instance,
                        project_id=int(bind.project_id),
                        env_type=env_type,
                        config_mode=config_mode,
                        update_dict=update_dict,
                        env_name=env_name,
                    )
                else:
                    updated = await self.update(id=config_id, obj_in=update_dict)
        # 唯一索引冲突统一转为存储异常，避免向前端泄露数据库细节
        except IntegrityError as e:
            error_message: str = "更新环境配置失败, 配置名称、IP、端口或数据库名称与现有记录冲突"
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
                error_message = "更新环境配置失败, 操作存在并发冲突"
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
                f"old_config_name={instance.config_name}, new_config_name={updated.config_name}, sync_count={sync_count}]"
            )
        bind_meta: Dict[str, Any] = {
            "project_id": int(bind.project_id),
            "env_type": bind.env_type.value if hasattr(bind.env_type, "value") else bind.env_type,
        }
        return updated, env_name, bind_meta

    async def _sync_config_mode_group_name(
            self,
            *,
            instance: AutoTestEnvConfigModel,
            project_id: int,
            env_type: Union[AutoTestConfigNodeType, str],
            config_mode: str,
            update_dict: Dict[str, Any],
            env_name: str = "",
    ) -> Tuple[AutoTestEnvConfigModel, int]:
        """
        配置改名：目标名空闲时按逻辑标识同步同应用、同节点类型下全部启用实例；
        目标名被其他环境占用时与创建同口径并入既有组（只改主行）；仅同环境内同名占用才拒绝。

        :param instance: 待改名的主配置实例
        :param project_id: 配置所属应用ID
        :param env_type: 配置所属节点类型，同步范围限定在该节点
        :param config_mode: 逻辑配置标识，同步范围限定在该标识
        :param update_dict: 已过滤的更新字段，config_name 为新名称
        :param env_name: 主行所属环境名，冲突文案用（调用方已 join 取回，避免重复查库）
        :return: (改名后的主配置实例, 同步的其他实例条数)；并入既有组时只改主行，同步条数为0
        :raises DataAlreadyExistsException: 同环境内已存在新名称配置，含占用唯一键的软删记录
        :raises DataBaseStorageException: 落库失败或并发冲突
        """
        new_config_name: str = update_dict["config_name"]
        instance_bind_id: int = int(instance.env_bind_id)
        # 绑定行锁由调用方持有；这里锁定同标识启用行（主键升序），防止同组并发改名/删除穿插
        group_rows: List[AutoTestEnvConfigModel] = await self.model.filter(
            config_mode=config_mode,
            state__not=1,
        ).select_for_update().order_by("id").only("id")
        group_ids: List[int] = [int(row.id) for row in group_rows] or [int(instance.id)]
        # 唯一键按环境绑定独立：只有同环境内的同名行才真正撞键（软删行同样占用 UNIQUE(env_bind, config_name)），
        # 其他环境占用目标名不影响当前环境落库，与创建同口径复用逻辑标识并入该组
        bind_ids: List[int] = list(await AutoTestEnvBindModel.filter(
            project_id=project_id,
            env_type=env_type,
            state__not=1,
        ).values_list("id", flat=True))
        conflict_configs: List[Dict[str, Any]] = await self.model.filter(
            env_bind_id__in=bind_ids,
            config_name__iexact=new_config_name,
        ).exclude(id__in=group_ids).order_by("id").values("env_bind_id", "state", "config_mode")
        same_bind_conflicts: List[Dict[str, Any]] = [
            conflict_config for conflict_config in conflict_configs
            if int(conflict_config["env_bind_id"]) == instance_bind_id
        ]
        if same_bind_conflicts:
            # 同环境启用行撞名称唯一键、软删行占用唯一键，均拒绝并点出环境
            env_label: str = env_name or f"bind_id={instance_bind_id}"
            if any(int(conflict_config["state"]) == 1 for conflict_config in same_bind_conflicts):
                env_label = f"{env_label}(含已删除记录)"
            error_message: str = f"更新环境配置失败, 环境[{env_label}]下已存在同名配置[{new_config_name}], 无法改名"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)
        foreign_conflicts: List[Dict[str, Any]] = [
            conflict_config for conflict_config in conflict_configs
            if int(conflict_config["env_bind_id"]) != instance_bind_id
        ]
        # 目标名空闲才同步同组实例；group_ids 可能因空标识自愈而未包含主行，同步范围始终排除主行
        sync_ids: List[int] = [] if foreign_conflicts else [cid for cid in group_ids if cid != int(instance.id)]
        if foreign_conflicts:
            active_conflicts: List[Dict[str, Any]] = [
                conflict_config for conflict_config in foreign_conflicts if int(conflict_config["state"]) == 0
            ]
            if active_conflicts:
                # 存在启用行：与创建同口径（设计 5.2）复用其标识与组内写法，含空标识自愈；绑定ID复用免重查
                target_mode, canonical_name = await self._resolve_config_mode(
                    project_id=project_id,
                    env_type=env_type,
                    config_name=new_config_name,
                    bind_ids=bind_ids,
                )
            else:
                # 仅软删行占用：直接沿用其标识，避免日后恢复时同名分裂出第二组逻辑配置
                legacy_modes: List[str] = [
                    str(conflict_config["config_mode"]) for conflict_config in foreign_conflicts
                    if conflict_config["config_mode"]
                ]
                target_mode = legacy_modes[0] if legacy_modes else unique_identify()
                canonical_name = new_config_name
            update_dict["config_mode"] = target_mode
            update_dict["config_name"] = canonical_name
        # 主行统一写入名称与其余字段，再按标识批量同步同组实例
        updated = await self.update(id=instance.id, obj_in=update_dict)
        if sync_ids:
            await self.model.filter(
                id__in=sync_ids,
                state__not=1,
            ).update(
                config_name=new_config_name,
                updated_user=get_current_username() or updated.updated_user or instance.updated_user,
                # 批量 update 不触发 auto_now，显式刷新更新时间
                updated_time=datetime.now(),
            )
        return updated, len(sync_ids)

    async def _lock_project_type_binds(
            self,
            project_id: int,
            env_type: Union[AutoTestConfigNodeType, str],
    ) -> None:
        """
        事务内锁定同应用同节点的全部启用绑定行，串行化该维度下的配置创建/恢复与改名。

        :param project_id: 应用ID
        :param env_type: 节点类型
        :return: None
        """
        # 锁粒度是该应用该节点类型的绑定行（通常 1~4 行），只影响同维度并发写入；按主键升序加锁降低死锁概率
        await AutoTestEnvBindModel.filter(
            project_id=project_id,
            env_type=env_type,
            state__not=1,
        ).select_for_update().order_by("id").only("id")

    async def _resolve_config_mode(
            self,
            *,
            project_id: int,
            env_type: Union[AutoTestConfigNodeType, str],
            config_name: str,
            bind_ids: Optional[List[int]] = None,
    ) -> Tuple[str, str]:
        """
        按同应用+同节点+同名启用配置解析逻辑标识与组内统一写法。

        :param project_id: 应用ID
        :param env_type: 节点类型
        :param config_name: 用户输入的配置名称
        :param bind_ids: 可选预取的同维度启用绑定ID，传入时免重复查绑定表
        :return: (config_mode, 组内统一名称)
        """
        # 经绑定表定位同维度全部配置行，不依赖冗余列（兼容批次空隙未回填的存量行）：
        # 命中启用行复用其 config_mode 与名称写法；仅命中空标识行时以新标识就地补齐；
        # 未命中生成新标识；调用方需已持有绑定行锁
        if bind_ids is None:
            bind_ids = list(await AutoTestEnvBindModel.filter(
                project_id=project_id,
                env_type=env_type,
                state__not=1,
            ).values_list("id", flat=True))
        rows: List[Dict[str, Any]] = await self.model.filter(
            env_bind_id__in=bind_ids,
            config_name__iexact=config_name,
            state=0,
        ).order_by("id").values("id", "config_mode", "config_name")
        for row in rows:
            if row["config_mode"]:
                return str(row["config_mode"]), str(row["config_name"])
        mode: str = unique_identify()
        if rows:
            # 批次 1~2 之间旧逻辑写入的空标识行：就地补齐，避免同一名称分裂出第二组逻辑配置
            healed_ids: List[int] = [int(row["id"]) for row in rows]
            await self.model.filter(id__in=healed_ids).update(
                config_mode=mode,
                project_id=project_id,
                env_type=env_type,
                updated_user=get_current_username(),
                updated_time=datetime.now(),
            )
            LOGGER.warning(
                f"环境配置逻辑标识为空已自动补齐, "
                f"关键字段: [config_ids={healed_ids}, config_name={rows[0]['config_name']}, config_mode={mode}]"
            )
            return mode, str(rows[0]["config_name"])
        return mode, config_name

    async def _assert_configs_not_referenced(self, targets: List[AutoTestEnvConfigModel]) -> None:
        """
        校验环境配置删除后引用仍可解析：逻辑标识精确匹配，DB/Redis 操作保留旧名称兜底。

        步骤/压测引用按 mode/名称定位、不绑定具体环境，同组（同应用同节点同名）仍有启用实例时
        允许删除部分实例；仅当本次删除会清空整组（无任何存留启用实例）时才拒绝。

        :param targets: 待删除的环境配置实例列表
        :return: None
        :raises NotFoundException: 配置关联的环境绑定已不存在
        :raises DataAlreadyExistsException: 被引用配置所在逻辑组将被本次删除清空时拒绝删除
        """
        # 步骤与压测接口按 request_config_mode 精确匹配（旧名称列已随迁移 32 删除），
        # DB/Redis 的 operates 内仍可能残留未回填的 config_name，按同应用名称兜底；
        # 同应用的配置合并扫描，单次取回引用行后在内存匹配，避免逐条查库
        if not targets:
            return
        # 延迟导入: autotest 服务层不在模块加载期依赖 performance 模块，避免初始化顺序耦合
        from backend.applications.performance.models.perf_api_model import PerfApiModel

        bind_map: Dict[int, int] = {
            obj.id: obj.project_id
            for obj in await AutoTestEnvBindModel.filter(id__in=[item.env_bind_id for item in targets])
        }
        # 配置（mode/名称）只在所属应用的用例步骤与压测接口中生效，按项目归组后统一扫描
        targets_by_project: Dict[int, List[AutoTestEnvConfigModel]] = {}
        for instance in targets:
            project_id = bind_map.get(instance.env_bind_id)
            if project_id is None:
                raise NotFoundException(message=f"配置[{instance.config_name}]关联的环境信息不存在")
            targets_by_project.setdefault(int(project_id), []).append(instance)

        for project_id, project_targets in targets_by_project.items():
            # 目标行按 mode 与名称建索引：单个步骤/接口内多处引用同一配置只计一次，与“引用数”口径一致
            mode_to_ids: Dict[str, List[int]] = defaultdict(list)
            name_to_ids: Dict[str, List[int]] = defaultdict(list)
            for target in project_targets:
                if target.config_mode:
                    mode_to_ids[str(target.config_mode)].append(int(target.id))
                if target.config_name:
                    name_to_ids[target.config_name].append(int(target.id))

            # 步骤引用：请求配置按 mode 精确匹配，DB/Redis 操作按 mode 匹配并以旧名称兜底
            step_counts: Dict[int, int] = {}
            case_ids = await AutoTestCaseModel.filter(
                case_project=project_id, state__not=1
            ).values_list("id", flat=True)
            if case_ids:
                step_rows = await AutoTestStepModel.filter(
                    case_id__in=list(case_ids), state__not=1
                ).values("request_config_mode", "database_operates", "redis_operates")
                for row in step_rows:
                    step_modes = set()
                    step_names = set()
                    if row["request_config_mode"]:
                        step_modes.add(row["request_config_mode"])
                    for field in ("database_operates", "redis_operates"):
                        operates = row[field]
                        if not isinstance(operates, list):
                            continue
                        for operate in operates:
                            if not isinstance(operate, dict):
                                continue
                            if operate.get("config_mode"):
                                step_modes.add(operate["config_mode"])
                            if operate.get("config_name"):
                                step_names.add(operate["config_name"])
                    matched_ids = set()
                    for mode in step_modes:
                        matched_ids.update(mode_to_ids.get(mode, ()))
                    for name in step_names:
                        matched_ids.update(name_to_ids.get(name, ()))
                    for target_id in matched_ids:
                        step_counts[target_id] = step_counts.get(target_id, 0) + 1

            # 压测接口引用：同应用启用接口按 mode 精确匹配（一次查询覆盖整组目标）
            perf_counts: Dict[int, int] = {}
            target_modes: List[str] = list(mode_to_ids)
            if target_modes:
                perf_rows = await PerfApiModel.filter(
                    request_project_id=project_id,
                    request_config_mode__in=target_modes,
                    state__not=1,
                ).values("request_config_mode")
                for row in perf_rows:
                    for target_id in mode_to_ids.get(str(row["request_config_mode"]), ()):
                        perf_counts[target_id] = perf_counts.get(target_id, 0) + 1

            referenced_targets: List[AutoTestEnvConfigModel] = [
                target for target in project_targets
                if step_counts.get(int(target.id), 0) > 0 or perf_counts.get(int(target.id), 0) > 0
            ]
            if not referenced_targets:
                continue
            # 同组存留判定：引用不绑定环境，删除后同组仍有启用实例即可继续解析，至少保留一个
            survivor_modes, survivor_names = await self._count_group_survivors(
                project_id=project_id,
                batch_targets=project_targets,
                referenced=referenced_targets
            )
            for target in project_targets:
                target_id: int = int(target.id)
                if target.config_mode:
                    survivor_count: int = survivor_modes.get(str(target.config_mode), 0)
                else:
                    survivor_count = survivor_names.get(target.config_name, 0)
                if survivor_count > 0:
                    LOGGER.info(
                        f"删除环境配置成功, 同应用同节点下仍有实例, 允许删除, "
                        f"关键字段: [config_id={target_id}, config_name={target.config_name}, config_mode={target.config_mode}, survivor_count={survivor_count}]"
                    )
                    continue
                step_count: int = step_counts.get(target_id, 0)
                references: List[str] = []
                if step_count > 0:
                    references.append(f"{step_count}个步骤")
                error_message: str = f"删除环境配置失败, 该配置被{'、'.join(references)}引用(同应用同节点下至少需保留一个启用实例)"
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)

    async def _count_group_survivors(
            self,
            *,
            project_id: int,
            batch_targets: List[AutoTestEnvConfigModel],
            referenced: List[AutoTestEnvConfigModel],
    ) -> Tuple[Dict[str, int], Dict[str, int]]:
        """
        统计被引用配置所属逻辑组在本次删除后的存留启用实例数（按绑定表定位，不依赖冗余列）。

        :param project_id: 应用ID
        :param batch_targets: 本批全部待删除配置（含未被引用行，一并从存留数中扣除）
        :param referenced: 本批被引用的配置，用于确定需要统计的 mode/名称键
        :return: (按 mode 的存留数, 按名称的存留数；名称键仅覆盖无 mode 的存量行)
        """
        mode_counts: Dict[str, int] = defaultdict(int)
        name_counts: Dict[str, int] = defaultdict(int)
        ref_modes = {str(item.config_mode) for item in referenced if item.config_mode}
        ref_names = {item.config_name for item in referenced if not item.config_mode and item.config_name}
        if not ref_modes and not ref_names:
            return mode_counts, name_counts
        bind_ids = list(await AutoTestEnvBindModel.filter(
            project_id=project_id, state__not=1
        ).values_list("id", flat=True))
        if not bind_ids:
            return mode_counts, name_counts
        conditions = Q()
        if ref_modes:
            conditions |= Q(config_mode__in=ref_modes)
        if ref_names:
            conditions |= Q(config_name__in=ref_names)
        batch_ids = {int(item.id) for item in batch_targets}
        rows = await self.model.filter(
            env_bind_id__in=bind_ids, state=0
        ).filter(conditions).values("id", "config_mode", "config_name")
        for row in rows:
            if int(row["id"]) in batch_ids:
                continue
            if row["config_mode"] and str(row["config_mode"]) in ref_modes:
                mode_counts[str(row["config_mode"])] += 1
            if row["config_name"] and row["config_name"] in ref_names:
                name_counts[row["config_name"]] += 1
        return mode_counts, name_counts

    async def delete_config(self, config_in: AutoTestEnvConfigTypedDelete, scope: DataScope) -> AutoTestEnvConfigModel:
        """
        按节点类型物理删除环境配置；被引用且同组无其他启用实例可保留时禁止删除。

        :param config_in: 删除入参
        :param scope: 数据权限上下文
        :return: 删除后的配置实例快照
        :raises ParameterException: 环境节点类型不匹配
        :raises NotFoundException: 配置或关联环境绑定不存在
        :raises NoPermissionException: 配置创建人不在当前用户可删除范围
        :raises DataAlreadyExistsException: 配置被引用且同组将被清空
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
        根据ID或code列表批量软删除环境配置；软删与物理删同样要求被引用配置所在组至少保留一个启用实例。

        :param config_in: 环境配置批量删除schema
        :param scope: 数据权限上下文，仅允许删除归属人在当前用户可删除范围内的环境配置
        :return: 更新条数
        :raises ParameterException: 两个定位参数同时为空，或列表中包含空值
        :raises NotFoundException: 任一目标配置不存在或已软删，或关联环境丢失
        :raises NoPermissionException: 任一配置创建人不在当前用户可删除范围
        :raises DataAlreadyExistsException: 任一被引用配置所在组将被本次删除清空
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
            error_message: str = "查询配置信息失败, 查询或排序条件包含不支持的字段"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def query_classified_by_project_ids(
            self,
            project_ids: List[int],
            config_modes: Optional[List[str]] = None,
            scope: Optional[DataScope] = None,
    ) -> Dict[int, Dict[str, Dict[str, Dict[str, Dict[str, Any]]]]]:
        """
        按应用ID列表查询未删除配置并分类。

        :param project_ids: 应用ID列表
        :param config_modes: 配置逻辑标识列表(可选)；非空时仅返回这些逻辑配置所在的环境及其配置
        :param scope: 数据权限上下文，传入时仅返回可见范围内的配置
        :return: project_id -> env_id(数字字符串) -> api|file|database|redis -> config_mode -> {config_name, 主机信息}
        :raises ParameterException: project_ids 为空
        """
        # 返回结构固定包含传入的每个应用；已出现环境会预置全部节点类型的空桶，
        # 使调用方（调试/执行取环境）无需做层级判空；无逻辑标识或未知节点类型的配置会被跳过并告警；
        # 环境层 key 为绑定ID（数字字符串），环境名称由 /env/list 单独提供，避免改名影响引用
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
        ).values("id", "project_id", "env_type")
        if not bind_rows:
            return classified_config_result

        bind_meta = {
            row["id"]: {
                "project_id": row["project_id"],
                "env_type": row["env_type"],
            }
            for row in bind_rows
        }
        env_bind_ids = list(bind_meta.keys())
        # 逻辑标识过滤：非空时仅返回这些配置所在的环境及其配置（去重去空白）
        distinct_config_modes: List[str] = [
            str(m).strip() for m in (config_modes or []) if m is not None and str(m).strip()
        ]
        config_filter: Dict[str, Any] = {"env_bind_id__in": env_bind_ids, "state__not": 1}
        if distinct_config_modes:
            config_filter["config_mode__in"] = list(dict.fromkeys(distinct_config_modes))
        owner_q = scope.read_q("created_user") if scope is not None else None
        config_qs = self.model.filter(**config_filter)
        if owner_q is not None:
            config_qs = config_qs.filter(owner_q)
        env_config_rows: List[Dict[str, Any]] = await config_qs.values(
            "id", "env_bind_id", "config_mode", "config_name", "config_host", "config_port", "database_name"
        )
        if not env_config_rows:
            return classified_config_result

        for cfg_row in env_config_rows:
            env_bind_id: int = int(cfg_row["env_bind_id"])
            meta = bind_meta.get(env_bind_id)
            if not meta:
                continue
            project_id: int = int(meta["project_id"])
            if project_id not in classified_config_result:
                continue
            env_type = meta["env_type"].value if hasattr(meta["env_type"], "value") else str(meta["env_type"])
            if env_type not in allowed_types:
                LOGGER.warning(f"跳过未知配置类型: project_id={project_id}, env_bind_id={env_bind_id}, env_type={env_type}")
                continue
            config_mode: Optional[str] = cfg_row["config_mode"]
            if not config_mode:
                LOGGER.warning(f"跳过逻辑标识为空的环境配置: config_id={cfg_row['id']}, env_bind_id={env_bind_id}")
                continue
            env_key: str = str(env_bind_id)
            if env_key not in classified_config_result[project_id]:
                classified_config_result[project_id][env_key] = {t: {} for t in empty_type_buckets}
            classified_config_result[project_id][env_key][env_type][config_mode] = {
                "config_name": cfg_row["config_name"],
                "config_host": cfg_row["config_host"],
                "config_port": cfg_row["config_port"],
                "database_name": cfg_row["database_name"],
            }
        return classified_config_result

    async def list_distinct_configs(
            self,
            project_id: Optional[int] = None,
            env_id: Optional[int] = None,
            env_type: Optional[str] = None,
            scope: Optional[DataScope] = None,
    ) -> List[Dict[str, str]]:
        """
        未删除配置的逻辑标识去重列表。

        :param project_id: 应用ID，经绑定表过滤
        :param env_id: 环境绑定主键
        :param env_type: 节点类型，经绑定表过滤
        :param scope: 数据权限上下文，传入时仅返回可见范围内的配置
        :return: [{config_name, config_mode}]，按配置名称、逻辑标识升序
        """
        # 定位优先级：env_id 直接限定绑定；否则 project_id/env_type 经绑定表换算出绑定ID集合；
        # 只返回启用配置（R6），逻辑标识为空的历史行跳过并告警
        stmt: QuerySet = self.model.filter(state=0)
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
        rows: List[Dict[str, Any]] = await stmt.order_by("config_name", "id").values("config_mode", "config_name")
        mode_names: Dict[str, str] = {}
        for row in rows:
            config_mode: Optional[str] = row["config_mode"]
            if not config_mode:
                LOGGER.warning(f"跳过逻辑标识为空的启用配置: config_name={row['config_name']}")
                continue
            # 同一逻辑标识的理论写法一致，取最先生成的行作为展示名
            mode_names.setdefault(str(config_mode), str(row["config_name"]))
        return [
            {"config_name": config_name, "config_mode": config_mode}
            for config_mode, config_name in sorted(mode_names.items(), key=lambda item: (item[1], item[0]))
        ]

    async def query_assign_config_env_names(
            self,
            query_in: QueryAssignConfigEnv,
            scope: Optional[DataScope] = None,
    ) -> List[Dict[str, Any]]:
        """
        按应用/逻辑标识/节点类型查询符合的环境列表。

        :param query_in: 指派配置环境查询入参(三条件均可选)
        :param scope: 数据权限上下文，传入时仅返回可见范围内的配置所对应的环境
        :return: [{env_id, env_name}]，按环境名称、环境ID升序
        """
        # 环境链为真实外键，经绑定表跨取环境名称；返回值同时携带 env_id 与 env_name，
        # 前端可直接以 env_id 作为环境选择值，不再依赖名称匹配
        stmt: QuerySet = self.model.filter(state=0)
        owner_q = scope.read_q("created_user") if scope is not None else None
        if owner_q is not None:
            stmt = stmt.filter(owner_q)
        if query_in.config_mode:
            stmt = stmt.filter(config_mode=query_in.config_mode)
        if query_in.project_id is not None or query_in.env_type is not None:
            env_bind_ids = await AutoTestEnvCrud().list_bind_ids(
                project_id=query_in.project_id,
                env_type=query_in.env_type,
            )
            if not env_bind_ids:
                return []
            stmt = stmt.filter(env_bind_id__in=env_bind_ids)
        rows: List[Dict[str, Any]] = await stmt.values("env_bind_id", "env_bind__env_enum__env_name")
        env_map: Dict[int, str] = {}
        for row in rows:
            env_name: Optional[str] = row.get("env_bind__env_enum__env_name")
            if not env_name:
                continue
            env_map.setdefault(int(row["env_bind_id"]), str(env_name))
        return [
            {"env_id": env_id, "env_name": env_name}
            for env_id, env_name in sorted(env_map.items(), key=lambda item: (item[1], item[0]))
        ]

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
        校验同绑定下host、port、database_name唯一。

        :param env_bind_id: 环境绑定ID
        :param env_type: 节点类型（仅影响DB提示文案与database_name条件）
        :param mapped: 已映射的落库字段
        :param exclude_id: 更新时排除的配置ID
        :return: None
        :raises DataAlreadyExistsException: 命中同 host/port(/database_name) 的启用态配置
        """
        # 未传 host 时视为不限制（凭据型配置可能只有名称）；仅 DB 节点额外比较 database_name；
        # 唯一性含节点类型、软删与空值等条件分支，无法用普通唯一索引表达，
        # 由调用方在同一事务内加锁后校验，保证少量并发下不产生重复主机
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
            error_message: str = "暂时无法获取配置列表, 请稍后重试"
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
            raise NotFoundException(message="未找到对应的数据库环境绑定记录")

        config = await self.model.filter(
            id=config_id,
            env_bind_id=env_row.id,
            config_name=config_name,
            database_name=database_name,
            state=0,
        ).first()
        if not config:
            raise NotFoundException(message="未找到对应的数据库配置记录")

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
            error_message: str = "暂时无法测试数据库连接, 请稍后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [config_id={config_id}, project_id={project_id}, env_name={env_name}, "
                f"config_name={config_name}, database_name={database_name}]\n"
                f"{traceback.format_exc()}"
            )
            raise DataBaseStorageException(message=error_message) from e
        finally:
            # 测试连接即用即关：只关本坐标测试池，不影响执行期按mode缓存的池
            try:
                await get_app_database_pool().close_coordinate(
                    project_id=project_id,
                    env_name=env_name,
                    config_name=config_name,
                    database_name=database_name,
                )
            except Exception as close_error:
                LOGGER.warning(f"测试连接池释放失败(不影响测试结果): {close_error}")

        return {
            "config_id": config_id,
            "database_type": config.database_type,
            "config_host": config.config_host,
            "config_port": config.config_port,
        }
