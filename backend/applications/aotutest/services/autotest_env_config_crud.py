# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_config_crud
@DateTime: 2026/4/16 10:51
"""
import traceback
from types import SimpleNamespace
from typing import Optional, Dict, Any, List, Tuple

from tortoise.exceptions import IntegrityError, FieldError, DoesNotExist
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from backend.applications.aotutest.models.autotest_model import AutoTestApiEnvConfigInfo
from backend.applications.aotutest.schemas.autotest_env_config_schema import (
    AutoTestApiConfigCreate,
    AutoTestApiConfigUpdate,
    AutoTestApiConfigDelete
)
from backend.applications.aotutest.services.autotest_env_crud import AutoTestApiEnvEnumCrud
from backend.applications.aotutest.services.autotest_project_crud import AutoTestApiProjectCrud
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)
from backend.enums import AutoTestConfigNodeType


class AutoTestApiEnvConfigCrud(ScaffoldCrud[AutoTestApiEnvConfigInfo, AutoTestApiConfigCreate, AutoTestApiConfigUpdate]):

    def __init__(self):
        super().__init__(model=AutoTestApiEnvConfigInfo)
        self.required_fields = ["config_host", "config_port", "config_username", "config_password"]

    def _validate_config_required_fields(self, config_type: Any, payload: Any) -> None:
        """
        根据配置类型校验必填字段。

        :param config_type: 配置类型枚举或枚举值
        :param payload: 含配置字段的对象(支持getattr)
        """
        type_value = config_type.value if hasattr(config_type, "value") else config_type
        if type_value not in AutoTestConfigNodeType.get_values():
            error_message: str = f"参数[config_type]枚举值[{config_type}]不被允许"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if type_value == AutoTestConfigNodeType.API.value:
            if not getattr(payload, "config_host", None):
                error_message: str = "参数[config_type]枚举值为API时, 参数[config_host]不允许为空"
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)
        elif type_value == AutoTestConfigNodeType.DB.value:
            missing_fields = [field for field in self.required_fields if not getattr(payload, field, None)]
            if missing_fields:
                error_message: str = f"参数[config_type]枚举值为DB时, 参数[{', '.join(missing_fields)}]不允许为空"
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)
        elif type_value == AutoTestConfigNodeType.FILE.value:
            missing_fields = [field for field in self.required_fields if not getattr(payload, field, None)]
            if getattr(payload, "is_authorization", None) is None:
                missing_fields.append("is_authorization")
            if missing_fields:
                error_message: str = f"参数[config_type]枚举值为FILE时, 参数[{', '.join(missing_fields)}]不允许为空"
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)
        elif type_value == AutoTestConfigNodeType.REDIS.value:
            if not getattr(payload, "config_host", None):
                error_message: str = "参数[config_type]枚举值为REDIS时, 参数[config_host]不允许为空"
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)

    async def get_by_id(self, config_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestApiEnvConfigInfo]:
        """
        根据主键ID查询环境配置。

        :param config_id: 配置主键
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 配置实例或None
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

    async def get_by_code(self, config_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestApiEnvConfigInfo]:
        """
        根据配置标识代码查询环境配置。

        :param config_code: 配置标识代码
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 配置实例或None
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

    async def create_config(self, config_in: Union[APPEnvConfigCreate, FILEEnvConfigCreate, DBEnvConfigCreate]) -> Dict[str, Any]:
        """
        按节点类型新增环境配置（APP/FILE/DB）。

        :param config_in: 创建APP/FILE/DB入参
        :return: 配置响应字典
        """
        try:
            env_type = self._env_type_from_schema(config_in)
            config_type = resolve_config_type(env_type)
            data_dict = config_in.model_dump()
            project_id = int(data_dict["env_info_id"])
            config_name = data_dict["config_name"]
            env_name = (data_dict.get("env") or "").upper()
            operator = self._resolve_operator(config_in)
            payload = {**data_dict, "env": env_name, "maintainer": data_dict.get("maintainer") or operator}

            await AutoTestApiProjectCrud().get_by_id(project_id=project_id, on_error=True, state__not=1)
            env_enum = await self._get_or_create_env_enum(
                project_id=project_id,
                env_name=env_name,
                env_type=env_type,
                user=operator,
            )
            mapped = self._map_typed_config_fields(env_type, payload)

            existing = await self.model.filter(
                project_id=project_id,
                env_id=env_enum.id,
                config_name=config_name,
                config_type=config_type,
            ).first()
            if existing:
                if existing.state == 0:
                    raise DataAlreadyExistsException(
                        message=f"配置:{config_name}已存在，当前应用+环境下配置名称唯一，不能重复新增"
                    )
                update_dict = {**mapped, "state": 0, "config_type": config_type}
                instance = await self.update(id=existing.id, obj_in=update_dict)
                return self._serialize_typed_config(instance, env_name, env_type)

            await self._assert_host_unique(
                project_id=project_id,
                env_id=env_enum.id,
                config_type=config_type,
                env_type=env_type,
                mapped=mapped,
            )
            instance = await self.create(
                {
                    "project_id": project_id,
                    "env_id": env_enum.id,
                    "config_type": config_type,
                    "state": 0,
                    **mapped,
                }
            )
            return self._serialize_typed_config(instance, env_name, env_type)
        except (DataAlreadyExistsException, ParameterException, NotFoundException):
            raise
        except Exception as e:
            error_message = f"新增环境配置失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def create_redis_config(self, config_in: RedisEnvConfigCreate) -> Dict[str, Any]:
        """
        新增REDIS类型环境配置。

        :param config_in: Redis配置入参
        :return: 配置响应字典
        """
        try:
            data_dict = config_in.model_dump()
            project_id = int(data_dict["env_info_id"])
            config_name = data_dict["config_name"]
            env_name = (data_dict.get("env") or "").upper()
            operator = self._resolve_operator(config_in)
            config_type = AutoTestConfigNodeType.REDIS.value

            await AutoTestApiProjectCrud().get_by_id(project_id=project_id, on_error=True, state__not=1)
            # Redis配置挂在同名APP环境枚举下，便于调试侧按env_name解析
            env_enum = await self._get_or_create_env_enum(
                project_id=project_id,
                env_name=env_name,
                env_type=1,
                user=operator,
            )
            mapped = {
                "config_name": config_name,
                "config_desc": data_dict.get("remark"),
                "config_host": data_dict["redis_host"],
                "config_port": str(data_dict.get("redis_port") or "6379").strip()[:8],
                "config_username": data_dict.get("redis_username") or "",
                "config_password": data_dict.get("redis_password") or "",
                "database_name": str(data_dict.get("redis_db") or "0").strip(),
                "created_user": data_dict.get("created_user") or operator,
                "updated_user": operator,
            }

            existing = await self.model.filter(
                project_id=project_id,
                env_id=env_enum.id,
                config_name=config_name,
                config_type=config_type,
            ).first()
            if existing:
                if existing.state == 0:
                    raise DataAlreadyExistsException(
                        message=f"配置:{config_name}已存在，当前应用+环境下配置名称唯一，不能重复新增"
                    )
                instance = await self.update(id=existing.id, obj_in={**mapped, "state": 0, "config_type": config_type})
                return {
                    "id": instance.id,
                    "env_info_id": instance.project_id,
                    "config_name": instance.config_name,
                    "env": env_name,
                    "config_type": config_type,
                    "redis_host": instance.config_host,
                    "redis_port": instance.config_port,
                    "redis_db": instance.database_name,
                }

            instance = await self.create(
                {
                    "project_id": project_id,
                    "env_id": env_enum.id,
                    "config_type": config_type,
                    "state": 0,
                    **mapped,
                }
            )
            return {
                "id": instance.id,
                "env_info_id": instance.project_id,
                "config_name": instance.config_name,
                "env": env_name,
                "config_type": config_type,
                "redis_host": instance.config_host,
                "redis_port": instance.config_port,
                "redis_db": instance.database_name,
            }
        except (DataAlreadyExistsException, ParameterException, NotFoundException):
            raise
        except Exception as e:
            error_message = f"新增Redis环境配置失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def update_config(self, config_in: Union[APPEnvConfigUpdate, FILEEnvConfigUpdate, DBEnvConfigUpdate]) -> Dict[str, Any]:
        """
        按节点类型修改环境配置（APP/FILE/DB）。

        :param config_in: 更新APP/FILE/DB入参
        :return: 配置响应字典
        """
        try:
            env_type = self._env_type_from_schema(config_in)
            config_type = resolve_config_type(env_type)
            data_dict = config_in.model_dump()
            record_id = data_dict.get("id")
            if not record_id:
                raise ParameterException(message="缺少主键ID参数")
            frontend_project_id = data_dict.get("project_id")
            if frontend_project_id is None or frontend_project_id == "":
                raise ParameterException(message="缺少应用ID参数")

            existing = await self.model.filter(id=record_id).first()
            if not existing:
                raise NotFoundException(message=f"未找到ID为：{record_id}的配置记录")
            if existing.state == 1:
                raise ParameterException(message=f"该ID：{record_id}配置已被删除，无法修改")
            if str(frontend_project_id) != str(existing.project_id):
                raise ParameterException(message="应用ID不匹配，请检查")

            expected_type = enum_field_value(existing.config_type)
            if expected_type != config_type:
                raise ParameterException(
                    message=f"类型不匹配，记录类型为{expected_type}，请求类型为{config_type}"
                )

            operator = self._resolve_operator(config_in)
            env_name = (data_dict.get("env") or "").upper()
            env_enum = await self._get_or_create_env_enum(
                project_id=int(existing.project_id),
                env_name=env_name,
                env_type=env_type,
                user=operator,
            )
            mapped = self._map_typed_config_fields(
                env_type,
                {**data_dict, "env": env_name, "maintainer": data_dict.get("maintainer") or operator},
            )
            # 更新不改写创建人
            mapped.pop("created_user", None)

            name_dup = await self.model.filter(
                project_id=existing.project_id,
                env_id=env_enum.id,
                config_name=mapped["config_name"],
                config_type=config_type,
                state=0,
            ).exclude(id=record_id).first()
            if name_dup:
                raise DataAlreadyExistsException(message="当前应用+环境下已经存在相同的配置名称，不能重复新增")

            await self._assert_host_unique(
                project_id=existing.project_id,
                env_id=env_enum.id,
                config_type=config_type,
                env_type=env_type,
                mapped=mapped,
                exclude_id=record_id,
            )

            update_dict = {**mapped, "env_id": env_enum.id}
            instance = await self.update(id=record_id, obj_in=update_dict)
            return self._serialize_typed_config(instance, env_name, env_type)
        except (DataAlreadyExistsException, ParameterException, NotFoundException):
            raise
        except Exception as e:
            error_message = f"修改环境配置失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def delete_config(self, config_in: EnvConfigDelete) -> Dict[str, Any]:
        """
        按节点类型软删除环境配置。

        :param config_in: 删除APP/FILE/DB入参（id + env_type）
        :return: 配置响应字典
        """
        try:
            record_id = config_in.id
            env_type = config_in.env_type
            config_type = resolve_config_type(env_type)
            existing = await self.model.filter(id=record_id).first()
            if not existing:
                raise NotFoundException(message=f"未找到ID为{record_id}的配置记录")
            expected_type = enum_field_value(existing.config_type)
            if expected_type != config_type:
                raise ParameterException(message=f"类型不匹配，记录类型为{expected_type}，请求类型为{env_type}")
            env_row = await AutoTestApiEnvEnumInfo.filter(id=existing.env_id).first()
            env_name = env_row.env_name if env_row else ""
            instance = await self.soft_delete(id=record_id, updated_user=config_in.updated_user)
            return self._serialize_typed_config(instance, env_name, env_type)
        except (ParameterException, NotFoundException):
            raise
        except Exception as e:
            error_message = f"删除环境配置失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def delete_configs(self, config_in: AutoTestApiConfigDelete) -> int:
        """
        根据ID或code列表批量软删除环境配置。

        :param config_in: 环境配置批量删除schema
        :return: 更新条数
        """
        config_ids: Optional[List[int]] = config_in.config_ids
        config_codes: Optional[List[str]] = config_in.config_codes
        if not config_ids and not config_codes:
            error_message: str = "删除配置信息失败, 参数[config_ids]或[config_codes]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        targets: List[AutoTestApiEnvConfigInfo] = []
        if config_ids:
            for cid in config_ids:
                targets.append(await self.get_by_id(config_id=cid, on_error=True, state__not=1))
        else:
            for ccode in config_codes:
                targets.append(await self.get_by_code(config_code=ccode, on_error=True, state__not=1))

        for instance in targets:
            await self.soft_delete(id=instance.id)

        return len(targets)

    async def select_config(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestApiEnvConfigInfo]]:
        """
        根据条件分页查询环境配置列表。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询配置信息失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def query_classified_by_project_ids(
            self,
            project_ids: List[int],
    ) -> Dict[int, Dict[str, Dict[str, Dict[str, Dict[str, Any]]]]]:
        """
        按应用ID列表查询未删除配置并分类。

        :param project_ids: 应用ID列表
        :return: project_id -> env_name -> APP|FILE|DB -> config_name -> 主机信息
        """
        if not project_ids:
            error_message: str = "按应用列表查询环境配置失败, 参数(project_ids)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        distinct_project_ids: List[int] = list(dict.fromkeys(project_ids))
        classified_config_result: Dict[int, Dict[str, Dict[str, Dict[str, Dict[str, Any]]]]] = {
            project_id: {}
            for project_id in distinct_project_ids
        }
        # 响应桶标签与 get_envs / 前端约定一致（非库内 api/file/database）
        env_type_to_label: Dict[int, str] = {1: "APP", 2: "FILE", 3: "DB"}
        empty_type_buckets: Dict[str, Dict[str, Any]] = {label: {} for label in env_type_to_label.values()}

        env_config_instances: List[AutoTestApiEnvConfigInfo] = await self.model.filter(
            project_id__in=distinct_project_ids,
            state__not=1,
        ).all()
        if not env_config_instances:
            return classified_config_result

        env_ids: List[int] = list({int(cfg.env_id) for cfg in env_config_instances})
        env_rows = await AutoTestApiEnvEnumInfo.filter(id__in=env_ids, state__not=1).values("id", "env_name")
        env_name_map: Dict[int, str] = {int(row["id"]): row["env_name"] for row in env_rows}

        for cfg_instance in env_config_instances:
            project_id: int = int(cfg_instance.project_id)
            if project_id not in classified_config_result:
                continue

            env_name: Optional[str] = env_name_map.get(int(cfg_instance.env_id))
            if not env_name:
                LOGGER.warning(
                    f"跳过无对应环境主表记录的配置: config_id={cfg_instance.id}, env_id={cfg_instance.env_id}"
                )
                continue

            config_type_value: str = enum_field_value(cfg_instance.config_type)
            env_type: Optional[int] = CONFIG_TYPE_TO_ENV_TYPE.get(config_type_value)
            type_label: Optional[str] = env_type_to_label.get(env_type) if env_type is not None else None
            if not type_label:
                LOGGER.warning(
                    f"跳过未知配置类型: project_id={project_id}, env={env_name}, config_type={config_type_value}"
                )
                continue

            if env_name not in classified_config_result[project_id]:
                classified_config_result[project_id][env_name] = {
                    label: {} for label in empty_type_buckets
                }

            classified_config_result[project_id][env_name][type_label][cfg_instance.config_name] = {
                "config_host": cfg_instance.config_host,
                "config_port": cfg_instance.config_port,
                "database_name": cfg_instance.database_name,
            }
        return classified_config_result

    async def list_distinct_config_names(
            self,
            project_id: Optional[int] = None,
            env_id: Optional[int] = None,
            config_type: Optional[str] = None,
    ) -> List[str]:
        """
        未删除配置中config_name去重后的列表。

        :param project_id: 应用ID
        :param env_id: 环境ID
        :param config_type: 配置类型
        :return: 去重且升序排列的配置名称列表
        """
        stmt: QuerySet = self.model.filter(state__not=1)
        if project_id is not None:
            stmt = stmt.filter(project_id=project_id)
        if env_id is not None:
            stmt = stmt.filter(env_id=env_id)
        if config_type is not None:
            stmt = stmt.filter(config_type=config_type)
        names = await stmt.values_list("config_name", flat=True)
        return sorted(set(names))

    def _env_type_from_schema(
            self,
            config_in: Union[
                APPEnvConfigCreate, FILEEnvConfigCreate, DBEnvConfigCreate,
                APPEnvConfigUpdate, FILEEnvConfigUpdate, DBEnvConfigUpdate,
            ],
    ) -> int:
        """
        根据typed schema推断节点类型。

        :param config_in: APP/FILE/DB 创建或更新入参
        :return: 1=APP, 2=FILE, 3=DB
        """
        if isinstance(config_in, (APPEnvConfigCreate, APPEnvConfigUpdate)):
            return 1
        if isinstance(config_in, (FILEEnvConfigCreate, FILEEnvConfigUpdate)):
            return 2
        if isinstance(config_in, (DBEnvConfigCreate, DBEnvConfigUpdate)):
            return 3
        raise ParameterException(message="不支持的环境配置入参类型")

    def _resolve_operator(self, config_in: Any) -> str:
        """
        解析操作人：登录上下文优先，其次schema的created/updated_user/maintainer。

        :param config_in: 入参对象
        :return: 大写用户名（最多16位）
        """
        from services.ctx import get_current_username
        username = get_current_username()
        if username:
            return username
        for attr in ("created_user", "updated_user", "maintainer"):
            val = getattr(config_in, attr, None)
            if isinstance(val, str) and val.strip():
                return val.strip().upper()[:16]
        return "ADMIN"

    def _map_typed_config_fields(self, env_type: int, data_dict: dict) -> Dict[str, Any]:
        """
        将按节点类型拆分的入参映射为EnvConfig落库字段。

        :param env_type: 1=APP, 2=FILE, 3=DB
        :param data_dict: 创建/更新入参字典
        :return: 可写入 AutoTestApiEnvConfigInfo 的字段字典
        """
        fields: Dict[str, Any] = {
            "config_name": data_dict["config_name"],
            "config_desc": data_dict.get("remark"),
            "created_user": data_dict.get("created_user") or data_dict.get("maintainer"),
            "updated_user": data_dict.get("updated_user") or data_dict.get("maintainer"),
        }
        if env_type == 1:
            fields["config_host"] = data_dict["env_host"]
            port = data_dict.get("env_port")
            fields["config_port"] = None if port is None else str(port).strip()[:8]
        elif env_type == 2:
            fields["config_host"] = data_dict["server_ip"]
            port = data_dict.get("server_port")
            fields["config_port"] = None if port is None else str(port).strip()[:8]
            fields["config_username"] = data_dict.get("server_account")
            fields["config_password"] = data_dict.get("server_password")
            # is_no_password: 0=免密 → is_authorization=True
            fields["is_authorization"] = int(data_dict.get("is_no_password", 1)) == 0
        else:
            db_type_raw = (data_dict.get("db_type") or "mysql").lower()
            db_type = (
                db_type_raw
                if db_type_raw in AutoTestDataBaseType.get_values()
                else AutoTestDataBaseType.MYSQL.value
            )
            fields["config_host"] = data_dict["db_host"]
            port = data_dict.get("db_port")
            fields["config_port"] = None if port is None else str(port).strip()[:8]
            fields["config_username"] = data_dict.get("db_user")
            fields["config_password"] = data_dict.get("db_password")
            fields["database_name"] = data_dict.get("db_name")
            fields["database_type"] = db_type
        return fields

    def _serialize_typed_config(self, instance: AutoTestApiEnvConfigInfo, env_name: str, env_type: int) -> Dict[str, Any]:
        """
        将配置实例序列化为按节点类型拆分字段的响应结构。

        :param instance: 配置ORM实例
        :param env_name: 环境名称
        :param env_type: 节点类型 1/2/3
        :return: 前端约定字段字典
        """
        host = instance.config_host
        port = instance.config_port
        return {
            "id": instance.id,
            "env_info_id": instance.project_id,
            "config_name": instance.config_name,
            "env": env_name,
            "env_type": env_type,
            "state": instance.state,
            "updated_time": instance.updated_time or datetime.now(),
            "created_time": instance.created_time or datetime.now(),
            "env_host": host if env_type == 1 else None,
            "env_port": port if env_type == 1 else None,
            "server_ip": host if env_type == 2 else None,
            "server_port": port if env_type == 2 else None,
            "db_host": host if env_type == 3 else None,
            "db_port": port if env_type == 3 else None,
            "remark": instance.config_desc,
        }

    async def _get_or_create_env_enum(
            self,
            *,
            project_id: int,
            env_name: str,
            env_type: int,
            user: str,
    ) -> AutoTestApiEnvEnumInfo:
        """
        按应用+环境名+节点类型获取或创建环境主表记录。

        :param project_id: 应用ID
        :param env_name: 环境名称（会规范化为大写）
        :param env_type: 节点类型 1/2/3
        :param user: 操作人
        :return: 环境主表实例
        """
        name = (env_name or "").strip().upper()
        if not name:
            raise ParameterException(message="参数[env]不允许为空")
        return await AutoTestApiEnvEnumCrud().create_env(
            AutoTestApiEnvCreate(
                env_name=name,
                project_id=project_id,
                env_type=env_type,
                created_user=user,
                env_desc="",
            )
        )

    async def _assert_host_unique(
            self,
            *,
            project_id: int,
            env_id: int,
            config_type: str,
            env_type: int,
            mapped: Dict[str, Any],
            exclude_id: Optional[int] = None,
    ) -> None:
        """
        校验同应用+环境+类型下host/port(/database_name)唯一。

        :param project_id: 应用ID
        :param env_id: 环境ID
        :param config_type: 配置类型枚举值
        :param env_type: 节点类型编码
        :param mapped: 已映射的落库字段
        :param exclude_id: 更新时排除的配置ID
        :return: None
        """
        host = mapped.get("config_host")
        if not host:
            return
        dup_q = self.model.filter(
            project_id=project_id,
            env_id=env_id,
            config_type=config_type,
            config_host=host,
            state=0,
        )
        if exclude_id is not None:
            dup_q = dup_q.exclude(id=exclude_id)
        port = mapped.get("config_port")
        if port is not None:
            dup_q = dup_q.filter(config_port=port)
        if env_type == 3 and mapped.get("database_name"):
            dup_q = dup_q.filter(database_name=mapped["database_name"])
        if await dup_q.exists():
            if env_type == 3:
                raise DataAlreadyExistsException(
                    message="当前应用+环境下，数据库名称+IP+端口重复，不能重复新增"
                )
            raise DataAlreadyExistsException(message="当前应用+环境下，IP+端口重复，不能重复新增")

    async def get_config_list(
            self,
            env_info_id: Optional[int] = None,
            env_name: Optional[str] = None,
            env_type: Optional[int] = None,
            page: int = 1,
            page_size: int = 10,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        分页查询环境配置，并统一为ip/port+类型扩展字段结构。

        :param env_info_id: 应用ID
        :param env_name: 环境名称
        :param env_type: 节点类型
        :param page: 页码
        :param page_size: 每页条数
        :return: (总条数, 当前页列表)
        """
        try:
            query = self.model.filter(state=0, config_type__in=list(CONFIG_TYPE_TO_ENV_TYPE.keys()))
            if env_info_id is not None:
                query = query.filter(project_id=env_info_id)
            if env_type is not None:
                query = query.filter(config_type=resolve_config_type(env_type))
            if env_name:
                env_filter = AutoTestApiEnvEnumInfo.filter(
                    env_name__iexact=env_name.strip(),
                    state__not=1,
                )
                if env_info_id is not None:
                    env_filter = env_filter.filter(project_id=env_info_id)
                if env_type is not None:
                    env_filter = env_filter.filter(env_type=env_type)
                matched_env_ids = await env_filter.values_list("id", flat=True)
                if not matched_env_ids:
                    return 0, []
                query = query.filter(env_id__in=list(matched_env_ids))

            total = await query.count()
            instances = await query.offset((page - 1) * page_size).limit(page_size).all()

            env_ids = list({obj.env_id for obj in instances})
            env_name_map = {}
            if env_ids:
                env_name_map = dict(
                    await AutoTestApiEnvEnumInfo.filter(id__in=env_ids).values_list("id", "env_name")
                )

            result: List[Dict[str, Any]] = []
            for obj in instances:
                etype = CONFIG_TYPE_TO_ENV_TYPE.get(enum_field_value(obj.config_type), 1)
                db_type_val = obj.database_type
                if db_type_val is not None and hasattr(db_type_val, "value"):
                    db_type_val = db_type_val.value
                is_no_password = None
                if etype == 2 and obj.is_authorization is not None:
                    is_no_password = 0 if obj.is_authorization else 1

                result.append({
                    "id": obj.id,
                    "config_name": obj.config_name,
                    "env_name": env_name_map.get(obj.env_id, ""),
                    "ip": obj.config_host or "",
                    "port": str(obj.config_port) if obj.config_port is not None else "",
                    "remark": obj.config_desc,
                    "maintainer": obj.updated_user or obj.created_user or "",
                    "created_time": format_datetime(obj.created_time or datetime.now()),
                    "updated_time": format_datetime(obj.updated_time or datetime.now()),
                    "db_name": obj.database_name if etype == 3 else None,
                    "db_type": str(db_type_val) if etype == 3 and db_type_val else None,
                    "server_account": obj.config_username if etype == 2 else None,
                    "server_password": obj.config_password if etype == 2 else None,
                    "db_user": obj.config_username if etype == 3 else None,
                    "db_password": obj.config_password if etype == 3 else None,
                    "is_no_password": is_no_password,
                })
            return total, result
        except ParameterException:
            raise
        except Exception as e:
            error_message = f"子表环境配置查询异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def test_db_connection(
            self,
            config_id: int,
            project_id: str,
            env_name: str,
            config_name: str,
            db_name: str,
    ) -> Dict[str, Any]:
        """
        校验DB配置存在后创建连接池。

        :param config_id: 配置ID
        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param db_name: 数据库名称
        :return: {code, status, message, data}
        """
        try:
            project_id_int = int(str(project_id).strip())
        except (TypeError, ValueError):
            return {
                "code": "999999",
                "status": "failure",
                "message": "配置表未找到对应记录，请检查",
                "data": None,
            }

        env_row = await AutoTestApiEnvEnumInfo.filter(
            project_id=project_id_int,
            env_name__iexact=(env_name or "").strip(),
            env_type=3,
            state__not=1,
        ).first()
        if not env_row:
            env_row = await AutoTestApiEnvEnumInfo.filter(
                project_id=project_id_int,
                env_name__iexact=(env_name or "").strip(),
                state__not=1,
            ).first()
        if not env_row:
            return {
                "code": "999999",
                "status": "failure",
                "message": "配置表未找到对应记录，请检查",
                "data": None,
            }

        config = await self.model.filter(
            id=config_id,
            project_id=project_id_int,
            env_id=env_row.id,
            config_name=config_name,
            database_name=db_name,
            config_type=AutoTestConfigNodeType.DB.value,
            state=0,
        ).first()
        if not config:
            return {
                "code": "999999",
                "status": "failure",
                "message": "配置表未找到对应记录，请检查",
                "data": None,
            }

        try:
            await get_app_database_pool().create_pool(
                project_id=str(project_id),
                env_name=env_name,
                config_name=config_name,
                database_name=db_name,
            )
            return {
                "code": "000000",
                "status": "success",
                "message": "数据库连接成功",
                "data": {
                    "id": config_id,
                    "db_type": enum_field_value(config.database_type) if config.database_type else None,
                    "host": config.config_host,
                    "port": config.config_port,
                },
            }
        except Exception as e:
            LOGGER.error(f"创建连接池失败: {e}\n{traceback.format_exc()}")
            return {
                "code": "999999",
                "status": "failure",
                "message": f"创建连接池失败：{str(e)}",
                "data": None,
            }
