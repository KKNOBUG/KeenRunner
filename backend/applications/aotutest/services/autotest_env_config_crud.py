# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_config_crud
@DateTime: 2026/4/16 10:51
"""
import traceback
from typing import Optional, Dict, Any, List, Tuple, Union

from tortoise.exceptions import DoesNotExist, FieldError, IntegrityError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from backend.applications.aotutest.models.autotest_model import AutoTestApiEnvConfigInfo, AutoTestApiEnvBindInfo
from backend.applications.aotutest.schemas.autotest_env_config_schema import (
    AutoTestApiEnvConfigCreate,
    AutoTestApiEnvConfigUpdate,
    AutoTestApiEnvConfigDelete,
    AutoTestApiEnvConfigTypedDelete,
)
from backend.applications.aotutest.schemas.autotest_env_schema import AutoTestApiEnvCreate
from backend.applications.aotutest.services.autotest_env_crud import AutoTestApiEnvCrud
from backend.applications.aotutest.services.autotest_project_crud import AutoTestApiProjectCrud
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.common.database.database_connection_pool import get_app_database_pool
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataAlreadyExistsException,
    DataBaseStorageException,
)
from backend.enums import AutoTestConfigNodeType


class AutoTestApiEnvConfigCrud(ScaffoldCrud[AutoTestApiEnvConfigInfo, AutoTestApiEnvConfigCreate, AutoTestApiEnvConfigUpdate]):

    def __init__(self):
        super().__init__(model=AutoTestApiEnvConfigInfo)

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

    async def create_config(self, config_in: AutoTestApiEnvConfigCreate) -> AutoTestApiEnvConfigInfo:
        """
        创建环境配置；同名软删记录则恢复启用。

        :param config_in: 环境配置创建schema（字段名与表对齐；env_name仅解析绑定）
        :return: 配置ORM实例
        """
        env_type = config_in.env_type
        project_id = int(config_in.project_id)
        config_name = config_in.config_name
        await AutoTestApiProjectCrud().get_by_id(project_id=project_id, on_error=True, state__not=1)

        env_bind = await self._get_or_create_env_bind(
            project_id=project_id,
            env_name=config_in.env_name,
            env_type=env_type,
            created_user=config_in.created_user,
        )
        payload = config_in.model_dump(exclude_none=True, exclude_unset=True, exclude={"env_name"})
        payload.update({
            "env_id": env_bind.id,
            "env_type": env_type,
            "state": 0,
        })

        existing = await self.model.filter(
            project_id=project_id,
            env_id=env_bind.id,
            config_name=config_name,
            env_type=env_type,
        ).first()
        if existing:
            if existing.state == 0:
                raise DataAlreadyExistsException(
                    message=f"配置:{config_name}已存在，当前应用+环境下配置名称唯一，不能重复新增"
                )
            try:
                return await self.update(id=existing.id, obj_in=payload)
            except (DoesNotExist, IntegrityError) as e:
                error_message = f"新增(恢复)环境配置异常, 违反约束规则或记录不存在: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise DataBaseStorageException(message=error_message) from e

        await self._assert_host_unique(
            project_id=project_id,
            env_id=env_bind.id,
            env_type=env_type,
            mapped=payload,
        )
        try:
            return await self.create(obj_in=payload)
        except IntegrityError as e:
            error_message = f"新增环境配置异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_config(self, config_in: AutoTestApiEnvConfigUpdate) -> AutoTestApiEnvConfigInfo:
        """
        更新环境配置，根据config_id或config_code定位。

        :param config_in: 环境配置更新schema
        :return: 配置ORM实例
        """
        config_id: Optional[int] = config_in.config_id
        config_code: Optional[str] = config_in.config_code
        if not config_id and not config_code:
            error_message = "更新环境配置失败, 参数[config_id]或[config_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if config_id:
            instance = await self.get_by_id(config_id=config_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(config_code=config_code, on_error=True, state__not=1)
            config_id = instance.id

        if config_in.project_id is not None and int(config_in.project_id) != int(instance.project_id):
            raise ParameterException(message="应用ID不匹配，请检查")

        env_type = config_in.env_type if config_in.env_type is not None else instance.env_type
        if instance.env_type != env_type:
            raise ParameterException(
                message=f"类型不匹配，记录类型为{instance.env_type}，请求类型为{env_type}"
            )

        env_name = config_in.env_name
        if not env_name:
            env_name_map = await AutoTestApiEnvCrud().get_env_name_map([instance.env_id])
            env_name = env_name_map.get(instance.env_id, "")
        if not env_name:
            raise ParameterException(message="参数[env_name]不允许为空")

        env_bind = await self._get_or_create_env_bind(
            project_id=int(instance.project_id),
            env_name=env_name,
            env_type=env_type,
            created_user=config_in.updated_user,
        )
        update_dict = config_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"config_id", "config_code", "env_name", "project_id"},
        )
        update_dict["env_id"] = env_bind.id
        update_dict["env_type"] = env_type

        config_name = update_dict.get("config_name", instance.config_name)
        name_dup = await self.model.filter(
            project_id=instance.project_id,
            env_id=env_bind.id,
            config_name=config_name,
            env_type=env_type,
            state=0,
        ).exclude(id=instance.id).first()
        if name_dup:
            raise DataAlreadyExistsException(message="当前应用+环境下已经存在相同的配置名称，不能重复")

        await self._assert_host_unique(
            project_id=instance.project_id,
            env_id=env_bind.id,
            env_type=env_type,
            mapped={**update_dict, "config_host": update_dict.get("config_host", instance.config_host)},
            exclude_id=instance.id,
        )
        try:
            return await self.update(id=config_id, obj_in=update_dict)
        except DoesNotExist as e:
            error_message = f"更新环境配置失败, 记录[id={config_id}]或[code={config_code}]不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message = f"更新环境配置异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_config(self, config_in: AutoTestApiEnvConfigTypedDelete) -> AutoTestApiEnvConfigInfo:
        """
        按节点类型软删除环境配置；已删除则直接返回（幂等）。

        :param config_in: 删除入参（config_id + env_type）
        :return: 软删除后的配置ORM实例
        """
        env_type = config_in.env_type
        instance = await self.get_by_id(config_id=config_in.config_id, on_error=True)
        if instance.env_type != env_type:
            raise ParameterException(
                message=f"类型不匹配，记录类型为{instance.env_type}，请求类型为{env_type}"
            )
        if instance.state == 1:
            return instance
        return await self.soft_delete(id=instance.id, updated_user=config_in.updated_user)

    async def delete_configs(self, config_in: AutoTestApiEnvConfigDelete) -> int:
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
        :return: project_id -> env_name -> api|file|database|redis -> config_name -> 主机信息
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
        allowed_types = set(AutoTestConfigNodeType.get_values())
        empty_type_buckets = {t: {} for t in allowed_types}

        env_config_instances: List[AutoTestApiEnvConfigInfo] = await self.model.filter(
            project_id__in=distinct_project_ids,
            state__not=1,
        ).all()
        if not env_config_instances:
            return classified_config_result

        env_ids: List[int] = list({int(cfg.env_id) for cfg in env_config_instances})
        env_name_map: Dict[int, str] = await AutoTestApiEnvCrud().get_env_name_map(env_ids)

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

            env_type = str(cfg_instance.env_type)
            if env_type not in allowed_types:
                LOGGER.warning(
                    f"跳过未知配置类型: project_id={project_id}, env={env_name}, env_type={env_type}"
                )
                continue

            if env_name not in classified_config_result[project_id]:
                classified_config_result[project_id][env_name] = {
                    t: {} for t in empty_type_buckets
                }

            classified_config_result[project_id][env_name][env_type][cfg_instance.config_name] = {
                "config_host": cfg_instance.config_host,
                "config_port": cfg_instance.config_port,
                "database_name": cfg_instance.database_name,
            }
        return classified_config_result

    async def list_distinct_config_names(
            self,
            project_id: Optional[int] = None,
            env_id: Optional[int] = None,
            env_type: Optional[str] = None,
    ) -> List[str]:
        """
        未删除配置中config_name去重后的列表。

        :param project_id: 应用ID
        :param env_id: 环境ID
        :param env_type: 配置类型
        :return: 去重且升序排列的配置名称列表
        """
        stmt: QuerySet = self.model.filter(state__not=1)
        if project_id is not None:
            stmt = stmt.filter(project_id=project_id)
        if env_id is not None:
            stmt = stmt.filter(env_id=env_id)
        if env_type is not None:
            stmt = stmt.filter(env_type=env_type)
        names = await stmt.values_list("config_name", flat=True)
        return sorted(set(names))

    @staticmethod
    async def serialize_config(instance: AutoTestApiEnvConfigInfo, env_name: str = "") -> Dict[str, Any]:
        """
        按表字段序列化配置，并附带env_name便于前端展示。

        :param instance: 配置ORM实例
        :param env_name: 环境名称
        :return: 与表字段对齐的响应字典
        """
        data = await instance.to_dict(
            exclude_fields={"reserve_1", "reserve_2", "reserve_3"},
            replace_fields={"id": "config_id"},
        )
        data["env_name"] = env_name
        return data

    async def _get_or_create_env_bind(
            self,
            *,
            project_id: int,
            env_name: str,
            env_type: Union[AutoTestConfigNodeType, str],
            created_user: Optional[str] = None,
    ) -> AutoTestApiEnvBindInfo:
        """
        按应用+环境名+节点类型获取或创建环境绑定记录。

        :param project_id: 应用ID
        :param env_name: 环境名称（会规范化为大写）
        :param env_type: 节点类型(api/file/database/redis)
        :param created_user: 无登录上下文时的回落创建人；有登录上下文时由Scaffold覆盖
        :return: 环境绑定实例
        """
        name = (env_name or "").strip().upper()
        if not name:
            raise ParameterException(message="参数[env_name]不允许为空")
        return await AutoTestApiEnvCrud().create_env(
            AutoTestApiEnvCreate(
                env_name=name,
                project_id=project_id,
                env_type=env_type,
                created_user=created_user,
                env_desc="",
            )
        )

    async def _assert_host_unique(
            self,
            *,
            project_id: int,
            env_id: int,
            env_type: Union[AutoTestConfigNodeType, str],
            mapped: Dict[str, Any],
            exclude_id: Optional[int] = None,
    ) -> None:
        """
        校验同应用+环境+类型下host/port(/database_name)唯一。

        :param project_id: 应用ID
        :param env_id: 环境绑定ID
        :param env_type: 配置类型
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
            env_type=env_type,
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
                raise DataAlreadyExistsException(
                    message="当前应用+环境下，数据库名称+IP+端口重复，不能重复新增"
                )
            raise DataAlreadyExistsException(message="当前应用+环境下，IP+端口重复，不能重复新增")

    async def get_config_list(
            self,
            project_id: Optional[int] = None,
            env_name: Optional[str] = None,
            env_type: Optional[Union[AutoTestConfigNodeType, str]] = None,
            page: int = 1,
            page_size: int = 10,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        分页查询环境配置，响应字段与表对齐。

        :param project_id: 应用ID
        :param env_name: 环境名称
        :param env_type: 配置类型(api/file/database/redis)；过滤绑定时对应env_type，同属AutoTestConfigNodeType
        :param page: 页码
        :param page_size: 每页条数
        :return: (总条数, 当前页列表)
        """
        try:
            allowed_types = AutoTestConfigNodeType.get_values()
            query = self.model.filter(state=0, env_type__in=allowed_types)
            if project_id is not None:
                query = query.filter(project_id=project_id)
            if env_type is not None:
                query = query.filter(env_type=env_type)
            if env_name:
                dict_ids = await AutoTestApiEnvCrud().get_dict_ids_by_name(env_name, exact=True)
                if not dict_ids:
                    return 0, []
                # 配置.env_id存的是绑定主键；按字典名找到绑定后再用绑定id过滤配置
                bind_filter = AutoTestApiEnvBindInfo.filter(
                    env_id__in=dict_ids,
                    state__not=1,
                )
                if project_id is not None:
                    bind_filter = bind_filter.filter(project_id=project_id)
                if env_type is not None:
                    bind_filter = bind_filter.filter(env_type=env_type)
                matched_bind_ids = await bind_filter.values_list("id", flat=True)
                if not matched_bind_ids:
                    return 0, []
                query = query.filter(env_id__in=list(matched_bind_ids))

            total = await query.count()
            instances = await query.offset((page - 1) * page_size).limit(page_size).all()
            env_ids = list({obj.env_id for obj in instances})
            env_name_map = await AutoTestApiEnvCrud().get_env_name_map(env_ids)
            result = [
                await self.serialize_config(obj, env_name_map.get(obj.env_id, ""))
                for obj in instances
            ]
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
            project_id: Union[int, str],
            env_name: str,
            config_name: str,
            database_name: str,
    ) -> Dict[str, Any]:
        """
        校验DB配置存在后创建连接池。

        :param config_id: 配置ID
        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param database_name: 数据库名称
        :return: 连接成功时的摘要信息
        """
        try:
            project_id_int = int(str(project_id).strip())
        except (TypeError, ValueError) as e:
            raise ParameterException(message="应用ID不合法") from e

        env_row = await AutoTestApiEnvCrud().get_bind_by_env_name(
            project_id=project_id_int,
            env_name=env_name,
            env_type=AutoTestConfigNodeType.DB,
        )
        if not env_row:
            raise NotFoundException(message="配置表未找到对应记录，请检查")

        config = await self.model.filter(
            id=config_id,
            project_id=project_id_int,
            env_id=env_row.id,
            config_name=config_name,
            database_name=database_name,
            env_type=AutoTestConfigNodeType.DB,
            state=0,
        ).first()
        if not config:
            raise NotFoundException(message="配置表未找到对应记录，请检查")

        try:
            await get_app_database_pool().create_pool(
                project_id=str(project_id_int),
                env_name=env_name,
                config_name=config_name,
                database_name=database_name,
            )
        except Exception as e:
            error_message = f"创建连接池失败：{e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

        return {
            "config_id": config_id,
            "database_type": config.database_type,
            "config_host": config.config_host,
            "config_port": config.config_port,
        }
