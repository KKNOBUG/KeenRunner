# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_config_crud
@DateTime: 2026/4/16 10:51
"""
import traceback
from typing import Optional, Dict, Any, List, Tuple, Union

from tortoise.exceptions import DoesNotExist, FieldError, IntegrityError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from backend.applications.autotest.models.autotest_env_config_model import AutoTestEnvBindModel, AutoTestEnvConfigModel
from backend.applications.autotest.models.autotest_env_model import AutoTestEnvModel
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
from backend.services import DataScope


class AutoTestEnvConfigCrud(ScaffoldCrud[AutoTestEnvConfigModel, AutoTestEnvConfigCreate, AutoTestEnvConfigUpdate]):
    """
    环境配置CRUD：一个环境绑定下的具体节点配置（app/file/database/redis）。

    层级：应用 → 环境绑定(env_bind) → 环境配置(config_name, host/port/database_name)；
    创建/更新时按 project+env_name+env_type 自动获取或创建绑定，请求体不直接写 env_bind_id。

    唯一性：同绑定下 config_name 唯一，且 host+port(+database_name) 唯一。
    引用约束：删除/软删前需确认无步骤按 config_name 引用（请求配置/数据库操作/Redis操作）。
    归属口径：配置以 created_user 为归属人。
    """

    def __init__(self):
        """绑定环境配置模型，供基类通用CRUD复用。"""
        super().__init__(model=AutoTestEnvConfigModel)

    async def get_by_id(self, config_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestEnvConfigModel]:
        """
        根据主键ID查询环境配置。

        :param config_id: 配置主键，必填
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件（如 state__not=1 排除软删）
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
        :param kwargs: 额外过滤条件（如 state__not=1 排除软删）
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

    async def create_config(self, config_in: AutoTestEnvConfigCreate, scope: DataScope) -> AutoTestEnvConfigModel:
        """
        创建环境配置；同名软删记录在写权限内恢复启用。

        :param config_in: 环境配置创建schema（project_id/env_name/env_type用于解析绑定，不落配置表）
        :param scope: 数据权限上下文，恢复软删配置时要求创建人允许当前用户写入
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
        existing = await self.model.filter(env_bind_id=env_bind.id, config_name=config_name).first()
        if existing:
            if existing.state == 0:
                raise DataAlreadyExistsException(message="相同应用和环境下, 配置名称不允许重复")
            # 软删恢复不得跨写范围接管他人配置，且不覆盖原创建人
            await scope.load_owners([existing.created_user])
            if not scope.can_write(existing.created_user):
                error_message = f"新增环境配置失败, 配置[{config_name}]创建人[{existing.created_user}]不在当前用户可操作范围内, 无权操作"
                LOGGER.error(error_message)
                raise NoPermissionException(message=error_message)
            payload.pop("created_user", None)
            try:
                return await self.update(id=existing.id, obj_in=payload)
            except (DoesNotExist, IntegrityError) as e:
                error_message: str = "新增环境配置失败，目标配置可能已被删除或与现有记录冲突，请刷新后重试"
                LOGGER.error(
                    f"{error_message}, "
                    f"关键字段: [config_id={existing.id}, env_bind_id={env_bind.id}, config_name={config_name}]\n"
                    f"{traceback.format_exc()}"
                )
                raise DataBaseStorageException(message=error_message) from e

        await self._assert_host_unique(
            env_bind_id=env_bind.id,
            env_type=env_type,
            mapped=payload,
        )
        try:
            return await self.create(obj_in=payload)
        except IntegrityError as e:
            error_message: str = "新增环境配置失败，配置名称、IP、端口或数据库名称可能与现有记录重复，或关联环境无效，请检查后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [env_bind_id={env_bind.id}, config_name={config_name}, config_host={payload.get('config_host')}, "
                f"config_port={payload.get('config_port')}, database_name={payload.get('database_name')}]\n"
                f"{traceback.format_exc()}"
            )
            raise DataBaseStorageException(message=error_message) from e

    async def update_config(self, config_in: AutoTestEnvConfigUpdate, scope: DataScope) -> AutoTestEnvConfigModel:
        """
        更新环境配置，根据config_id或config_code定位。

        改名/改绑定都会重做唯一性校验（config_name 对比 state=0 行、host/port 对比全量配置）；
        未传 env_name 时回查当前绑定对应的环境名，保证绑定解析路径与存量一致。

        :param config_in: 环境配置更新schema
        :param scope: 数据权限上下文，仅允许修改归属人在当前用户可操作范围内的环境配置
        :return: 配置ORM实例
        :raises ParameterException: 定位参数为空、所属应用/环境节点不匹配、环境名为空
        :raises NotFoundException: 配置或关联环境绑定不存在
        :raises NoPermissionException: 配置创建人或目标环境归属不在当前用户可操作范围
        :raises DataAlreadyExistsException: 同绑定下重名或 host/port 重复
        :raises DataBaseStorageException: 落库失败
        """
        config_id: Optional[int] = config_in.config_id
        config_code: Optional[str] = config_in.config_code
        if not config_id and not config_code:
            error_message = "更新环境配置失败, 参数[config_id, config_code]不允许同时为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if config_id:
            instance = await self.get_by_id(config_id=config_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(config_code=config_code, on_error=True, state__not=1)
            config_id = instance.id

        await scope.load_owners([instance.created_user])
        if not scope.can_write(instance.created_user):
            error_message = f"更新环境配置失败, 配置[{instance.config_name}]创建人[{instance.created_user}]不在当前用户可操作范围内, 无权操作"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)

        bind = await AutoTestEnvBindModel.filter(id=instance.env_bind_id).first()
        if not bind:
            raise NotFoundException(message="配置关联的环境信息不存在")
        if config_in.project_id is not None and int(config_in.project_id) != int(bind.project_id):
            raise ParameterException(message="配置关联的所属应用不匹配")
        env_type = config_in.env_type if config_in.env_type is not None else bind.env_type
        if bind.env_type != env_type:
            raise ParameterException(message="配置关联的环境节点不匹配")

        env_name = config_in.env_name
        if not env_name and bind.state != 1:
            enum_names = await AutoTestEnvModel.filter(id=bind.env_enum_id).values_list("env_name", flat=True)
            env_name = enum_names[0] if enum_names else ""
        if not env_name:
            raise ParameterException(message="参数[env_name]不允许为空")

        env_bind = await self._get_or_create_env_bind(
            scope=scope,
            project_id=int(bind.project_id),
            env_name=env_name,
            env_type=env_type,
            created_user=config_in.updated_user,
        )
        await assert_parent_readable(scope, ENV_TAG, env_bind, "环境")
        update_dict = config_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"config_id", "config_code", "env_name", "project_id", "env_type", "env_id"},
        )
        update_dict["env_bind_id"] = env_bind.id
        config_name = update_dict.get("config_name", instance.config_name)
        name_duplicated = await self.model.filter(env_bind_id=env_bind.id, config_name=config_name, state=0).exclude(id=instance.id).first()
        if name_duplicated:
            raise DataAlreadyExistsException(message="相同应用和环境下, 配置名称不允许重复")

        await self._assert_host_unique(
            env_bind_id=env_bind.id,
            env_type=env_type,
            mapped={**update_dict, "config_host": update_dict.get("config_host", instance.config_host)},
            exclude_id=instance.id,
        )
        try:
            return await self.update(id=config_id, obj_in=update_dict)
        except DoesNotExist as e:
            error_message: str = "更新环境配置失败，目标配置不存在或已被删除，请刷新后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [config_id={config_id}, config_code={config_code}]\n"
                f"{traceback.format_exc()}"
            )
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = "更新环境配置失败，配置名称、IP、端口或数据库名称可能与现有记录重复，或关联环境无效，请检查后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [config_id={config_id}, config_code={config_code}, env_bind_id={env_bind.id}, config_name={config_name}]\n"
                f"{traceback.format_exc()}"
            )
            raise DataBaseStorageException(message=error_message) from e

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
            for config_name in config_names:
                ref_count: int = sum(
                    1 for row in step_rows
                    if row["request_config_name"] == config_name
                    or any(
                        isinstance(operate, dict) and operate.get("config_name") == config_name
                        for field in ("database_operates", "redis_operates")
                        for operate in (row[field] if isinstance(row[field], list) else [])
                    )
                )
                if ref_count > 0:
                    error_message: str = f"删除环境配置失败, 配置[{config_name}]被{ref_count}个步骤引用"
                    LOGGER.error(error_message)
                    raise DataAlreadyExistsException(message=error_message)

    async def delete_config(self, config_in: AutoTestEnvConfigTypedDelete, scope: DataScope) -> AutoTestEnvConfigModel:
        """
        按节点类型物理删除环境配置；被步骤引用时禁止删除。

        :param config_in: 删除入参
        :param scope: 数据权限上下文，仅允许删除归属人在当前用户可删除范围内的环境配置
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
            error_message: str = f"删除环境配置失败, 配置[{instance.config_name}]创建人[{instance.created_user}]不在当前用户可删除范围内, 无权操作"
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
            error_message: str = "删除环境配置失败, 存在不在当前用户可删除范围内的环境配置, 无权操作"
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
        ).values("id", "project_id", "env_type")
        if not bind_rows:
            return classified_config_result

        bind_meta = {
            row["id"]: {"project_id": row["project_id"], "env_type": row["env_type"]}
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

        env_crud = AutoTestEnvCrud()
        env_name_map: Dict[int, str] = await env_crud.get_env_name_map(env_bind_ids)
        for cfg_row in env_config_rows:
            meta = bind_meta.get(int(cfg_row["env_bind_id"]))
            if not meta:
                continue
            project_id: int = int(meta["project_id"])
            if project_id not in classified_config_result:
                continue
            env_name: Optional[str] = env_name_map.get(int(cfg_row["env_bind_id"]))
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
            exclude_fields={"reserve_1", "reserve_2", "reserve_3", "env_bind", "env_bind_id"},
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
                env_desc="",
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
