# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_env_crud
@DateTime: 2026/1/2 17:42
"""
import traceback
from collections import defaultdict
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Union

from tortoise.exceptions import IntegrityError, FieldError, DoesNotExist
from tortoise.expressions import Q

from backend.applications.aotutest.models.autotest_model import (
    AutoTestApiEnvEnumInfo,
    AutoTestApiEnvConfigInfo,
    AutoTestApiProjectInfo,
)
from backend.applications.aotutest.schemas.autotest_env_schema import (
    AutoTestApiEnvCreate,
    AutoTestApiEnvUpdate,
    AutoTestApiEnvDelete,
    EnvCreate,
    EnvEditRequest,
)
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)
from backend.enums import AutoTestConfigNodeType

# env_type(1/2/3) 与 config_type(api/file/database) 双向映射
ENV_TYPE_TO_CONFIG_TYPE = {
    1: AutoTestConfigNodeType.API.value,
    2: AutoTestConfigNodeType.FILE.value,
    3: AutoTestConfigNodeType.DB.value,
}
CONFIG_TYPE_TO_ENV_TYPE = {
    AutoTestConfigNodeType.API.value: 1,
    AutoTestConfigNodeType.FILE.value: 2,
    AutoTestConfigNodeType.DB.value: 3,
}


def resolve_config_type(env_type: int) -> str:
    """
    将节点类型编码转换为config_type枚举值。

    :param env_type: 1=APP, 2=FILE, 3=DB
    :return: api/file/database
    """
    config_type = ENV_TYPE_TO_CONFIG_TYPE.get(env_type)
    if not config_type:
        error_message: str = f"节点类型[{env_type}]不被允许, 仅支持1:APP/2:FILE/3:DB"
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)
    return config_type


def enum_field_value(value: Any) -> str:
    """兼容CharEnumField返回枚举实例或字符串。"""
    return value.value if hasattr(value, "value") else str(value)


def format_datetime(value: Any) -> Optional[str]:
    """将时间格式化为YYYY-MM-DD HH:MM:SS；空值返回None。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    text = str(value).strip()
    return text[:19] if text else None


async def resolve_env_api_base_host_port(project_id: int, env_name: str) -> Tuple[str, Optional[str]]:
    """
    根据应用与环境名称解析API的host/port。

    :param project_id: 应用主键ID
    :param env_name: 环境名称
    :return: (host, port)；port可为空
    """
    pid = int(project_id)
    name = (env_name or "").strip()
    if not name:
        error_message: str = "参数[env_name]不允许为空"
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)

    env_row = await AutoTestApiEnvEnumInfo.filter(
        project_id=pid,
        env_name__iexact=name,
        env_type=1,
        state__not=1,
    ).first()
    if not env_row:
        # 兼容历史：同名环境可能挂在其他 env_type 行上，再按配置反查
        env_row = await AutoTestApiEnvEnumInfo.filter(
            project_id=pid,
            env_name__iexact=name,
            state__not=1,
        ).first()
    if not env_row:
        error_message: str = f"查询环境失败, 记录[project_id={pid}, env_name={name}]不存在"
        LOGGER.error(error_message)
        raise NotFoundException(message=error_message)

    cfg = (
        await AutoTestApiEnvConfigInfo.filter(
            project_id=pid,
            env_id=env_row.id,
            config_type=AutoTestConfigNodeType.API.value,
            state__not=1,
        )
        .order_by("id")
        .first()
    )
    if not cfg or not str(cfg.config_host or "").strip():
        error_message: str = (
            f"未找到可用的API环境配置, 查询条件: [project_id={pid}, env_id={env_row.id}, config_type={AutoTestConfigNodeType.API.value}]"
        )
        LOGGER.error(error_message)
        raise NotFoundException(message=error_message)
    host = str(cfg.config_host).strip().rstrip("/").rstrip(":")
    port_raw = getattr(cfg, "config_port", None)
    if port_raw is None or str(port_raw).strip() == "":
        return host, None
    return host, str(port_raw).strip()


class AutoTestApiEnvEnumCrud(ScaffoldCrud[AutoTestApiEnvEnumInfo, AutoTestApiEnvCreate, AutoTestApiEnvUpdate]):

    def __init__(self):
        super().__init__(model=AutoTestApiEnvEnumInfo)

    async def get_by_id(self, env_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestApiEnvEnumInfo]:
        """
        根据主键ID查询环境枚举。

        :param env_id: 环境枚举主键
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 环境枚举实例或None
        """
        if not env_id:
            error_message: str = "查询环境枚举信息失败, 参数[env_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.get_or_none(id=env_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询环境枚举信息失败, 记录[id={env_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, env_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestApiEnvEnumInfo]:
        """
        根据标识代码查询环境枚举。

        :param env_code: 环境标识代码
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 环境枚举实例或None
        """
        if not env_code:
            error_message: str = "查询环境枚举信息失败, 参数[env_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(env_code=env_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询环境枚举信息失败, 记录[code={env_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_name(self, env_name: str, on_error: bool = False, **kwargs) -> Optional[AutoTestApiEnvEnumInfo]:
        """
        根据名称查询环境枚举。

        :param env_name: 环境枚举名称
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 环境枚举实例或None
        """
        if not env_name:
            error_message: str = "查询环境枚举信息失败, 参数[env_name]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(env_name=env_name, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询环境枚举信息失败, 记录[env_name={env_name}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def create_env(self, env_in: AutoTestApiEnvCreate) -> AutoTestApiEnvEnumInfo:
        """
        创建环境；同应用+名称+类型已存在则恢复并更新。

        :param env_in: 环境创建schema（含 project_id / env_type）
        :return: 创建或恢复后的环境实例
        """
        resolve_config_type(env_in.env_type)
        env_name: str = env_in.env_name
        env_dict: Dict[str, Any] = env_in.model_dump(exclude_none=True, exclude_unset=True)
        existing_env: Optional[AutoTestApiEnvEnumInfo] = await self.model.filter(
            project_id=env_in.project_id,
            env_name=env_name,
            env_type=env_in.env_type,
        ).first()
        if not existing_env:
            try:
                instance: AutoTestApiEnvEnumInfo = await self.create(obj_in=env_dict)
                return instance
            except IntegrityError as e:
                error_message: str = f"新增环境信息异常, 违反约束规则: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise DataBaseStorageException(message=error_message) from e

        try:
            env_dict["state"] = 0
            instance: AutoTestApiEnvEnumInfo = await self.update(id=existing_env.id, obj_in=env_dict)
            return instance
        except (DoesNotExist, IntegrityError) as e:
            error_message: str = f"新增(更新)环境信息异常, 违反约束规则或空指针异常: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_env(self, env_in: AutoTestApiEnvUpdate) -> AutoTestApiEnvEnumInfo:
        """
        更新环境枚举，根据env_id或env_code定位。

        :param env_in: 环境枚举更新schema
        :return: 更新后的环境枚举实例
        """
        env_id: Optional[int] = env_in.env_id
        env_code: Optional[str] = env_in.env_code

        if not env_id and not env_code:
            error_message: str = "更新环境枚举信息失败, 参数[env_id]或[env_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if env_id:
            instance = await self.get_by_id(env_id=env_id, on_error=True, state__not=1)
            env_code = instance.env_code
        else:
            instance = await self.get_by_code(env_code=env_code, on_error=True, state__not=1)
            env_id = instance.id

        update_dict: Dict[str, Any] = env_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"env_id", "env_code"}
        )
        try:
            instance = await self.update(id=env_id, obj_in=update_dict)
            return instance
        except DoesNotExist as e:
            error_message: str = f"更新环境枚举信息失败, 记录[id={env_id}]或[code={env_code}]不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = f"更新环境枚举信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_env(self, env_id: Optional[int] = None, env_code: Optional[str] = None) -> AutoTestApiEnvEnumInfo:
        """
        软删除环境枚举。

        :param env_id: 环境枚举主键，与env_code二选一
        :param env_code: 环境枚举标识代码，与env_id二选一
        :return: 软删除后的环境枚举实例
        """
        if not env_id and not env_code:
            error_message: str = "删除环境枚举信息失败, 参数[env_id]或[env_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if env_id:
            instance = await self.get_by_id(env_id=env_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(env_code=env_code, on_error=True, state__not=1)

        return await self.soft_delete(id=instance.id)

    async def delete_envs(self, env_in: AutoTestApiEnvDelete) -> int:
        """
        根据ID或code列表批量软删除环境枚举；逐条复用单删校验。

        :param env_in: 环境枚举删除schema
        :return: 更新条数
        """
        env_ids: Optional[List[int]] = env_in.env_ids
        env_codes: Optional[List[str]] = env_in.env_codes
        if not env_ids and not env_codes:
            error_message: str = "删除环境枚举信息失败, 参数[env_ids]或[env_codes]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        targets: List[AutoTestApiEnvEnumInfo] = []
        if env_ids:
            for eid in env_ids:
                targets.append(await self.get_by_id(env_id=eid, on_error=True, state__not=1))
        else:
            for ecode in env_codes:
                targets.append(await self.get_by_code(env_code=ecode, on_error=True, state__not=1))

        for instance in targets:
            await self.delete_env(env_id=instance.id)

        return len(targets)

    async def select_envs(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestApiEnvEnumInfo]]:
        """
        根据条件分页查询环境枚举列表。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询环境枚举信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def get_envs(
            self,
            project_id: Optional[List[int]] = None,
    ) -> Union[Dict[str, List[str]], Dict[int, Dict[str, List[str]]]]:
        """
        按节点类型聚合环境名称（直接读环境主表）。

        :param project_id: None=全局聚合；[]=全部应用；[ids]=指定应用
        :return: {APP/FILE/DB: [...]} 或 {project_id: {APP/FILE/DB: [...]}}
        """
        try:
            env_type_to_label = {
                1: "APP",
                2: "FILE",
                3: "DB",
            }
            base_qs = self.model.filter(state=0)

            if project_id is None:
                rows = await base_qs.values("env_type", "env_name")
                env_map: Dict[str, set] = defaultdict(set)
                for row in rows:
                    label = env_type_to_label.get(int(row["env_type"]))
                    name = row.get("env_name")
                    if label and name:
                        env_map[label].add(name)
                return {et: sorted(names) for et, names in env_map.items()}

            unique_pids: Optional[List[int]] = None
            if not project_id:
                rows = await base_qs.values("project_id", "env_type", "env_name")
            else:
                unique_pids = list(dict.fromkeys(project_id))
                rows = await base_qs.filter(project_id__in=unique_pids).values(
                    "project_id", "env_type", "env_name"
                )

            grouped: Dict[int, Dict[str, set]] = defaultdict(lambda: defaultdict(set))
            for row in rows:
                label = env_type_to_label.get(int(row["env_type"]))
                name = row.get("env_name")
                if label and name:
                    grouped[row["project_id"]][label].add(name)

            result: Dict[int, Dict[str, List[str]]] = {}
            target_pids = unique_pids if unique_pids is not None else sorted(grouped.keys())
            for pid in target_pids:
                result[pid] = {et: sorted(names) for et, names in grouped.get(pid, {}).items()}
            return result
        except Exception as e:
            error_message = f"查询环境信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def get_env_search_list(
            self,
            project_id: Optional[int] = None,
            env_name: Optional[str] = None,
            env_type: Optional[int] = None,
            ip: Optional[str] = None,
            page: int = 1,
            page_size: int = 10,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        以环境主表分页查询；可选按子配置IP过滤。

        :return: (总条数, 当前页记录)；记录含 id/project_id/env_name/env_type/project_name/is_delete/时间字段
        """
        try:
            if env_type is not None:
                resolve_config_type(env_type)

            base_qs = self.model.filter(state=0)

            if ip:
                config_qs = AutoTestApiEnvConfigInfo.filter(
                    state=0,
                    config_host__contains=ip,
                    config_type__in=list(CONFIG_TYPE_TO_ENV_TYPE.keys()),
                )
                matched_env_ids = await config_qs.values_list("env_id", flat=True)
                if not matched_env_ids:
                    return 0, []
                base_qs = base_qs.filter(id__in=list(set(matched_env_ids)))

            if project_id is not None:
                base_qs = base_qs.filter(project_id=project_id)
            if env_name:
                base_qs = base_qs.filter(env_name__icontains=env_name.strip())
            if env_type is not None:
                base_qs = base_qs.filter(env_type=env_type)

            active_project_ids = await AutoTestApiProjectInfo.filter(state=0).values_list("id", flat=True)
            if active_project_ids:
                base_qs = base_qs.filter(project_id__in=list(active_project_ids))

            total = await base_qs.count()
            offset = (page - 1) * page_size
            page_rows = await base_qs.offset(offset).limit(page_size).values(
                "id", "project_id", "env_name", "env_type", "created_time", "updated_time"
            )

            project_ids = [int(item["project_id"]) for item in page_rows]
            project_map = {}
            if project_ids:
                project_map = dict(
                    await AutoTestApiProjectInfo.filter(id__in=project_ids, state=0).values_list("id", "project_name")
                )

            check_ids = [item["id"] for item in page_rows]
            sub_exists = set()
            if check_ids:
                config_rows = await AutoTestApiEnvConfigInfo.filter(
                    env_id__in=check_ids,
                    state=0,
                    config_type__in=list(CONFIG_TYPE_TO_ENV_TYPE.keys()),
                ).values("env_id", "project_id", "config_type")
                for crow in config_rows:
                    ctype = enum_field_value(crow["config_type"])
                    sub_exists.add((crow["env_id"], crow["project_id"], CONFIG_TYPE_TO_ENV_TYPE.get(ctype)))

            result = [
                {
                    "id": str(item["id"]),
                    "project_id": str(item["project_id"]),
                    "env_name": item["env_name"],
                    "env_type": item["env_type"],
                    "created_time": format_datetime(item["created_time"]),
                    "updated_time": format_datetime(item["updated_time"]),
                    "project_name": project_map.get(int(item["project_id"]), ""),
                    "is_delete": (item["id"], item["project_id"], item["env_type"]) not in sub_exists,
                }
                for item in page_rows
            ]
            return total, result
        except ParameterException:
            raise
        except Exception as e:
            error_message = f"查询环境搜索列表异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def create_automation_env(self, data: EnvCreate) -> Dict[str, Any]:
        """
        新增环境主表记录（应用+名称+类型唯一）。

        :param data: 环境创建入参
        :return: 与历史接口一致的环境响应字典
        """
        try:
            resolve_config_type(data.env_type)
            from backend.applications.aotutest.services.autotest_project_crud import AutoTestApiProjectCrud
            await AutoTestApiProjectCrud().get_by_id(project_id=data.project_id, on_error=True, state__not=1)

            env_name = data.env_name.upper()
            existing_env = await self.model.filter(
                project_id=data.project_id,
                env_name=env_name,
                env_type=data.env_type,
            ).first()
            if existing_env:
                if existing_env.state == 0:
                    raise DataAlreadyExistsException(
                        message=f"应用：{data.project_id}+环境{env_name}+类型{data.env_type}已存在，不能重复新增"
                    )
                restore_dict: Dict[str, Any] = {"state": 0}
                if data.created_user:
                    restore_dict["updated_user"] = data.created_user
                env_instance = await self.update(id=existing_env.id, obj_in=restore_dict)
            else:
                env_instance = await self.create_env(
                    AutoTestApiEnvCreate(
                        env_name=env_name,
                        project_id=data.project_id,
                        env_type=data.env_type,
                        created_user=data.created_user,
                    )
                )

            now = env_instance.updated_time or env_instance.created_time or datetime.now()
            return {
                "id": env_instance.id,
                "project_id": env_instance.project_id,
                "env_name": env_instance.env_name,
                "env_type": env_instance.env_type,
                "updated_time": now,
                "created_time": env_instance.created_time or now,
            }
        except (DataAlreadyExistsException, ParameterException, NotFoundException):
            raise
        except Exception as e:
            error_message = f"新增环境失败：{e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def update_automation_env(self, data: EnvEditRequest) -> Dict[str, Any]:
        """
        更新环境主表字段，并级联同类型配置的env_id/project_id。

        :param data: 环境编辑入参
        :return: 环境响应字典
        """
        try:
            config_type = resolve_config_type(data.env_type)
            from backend.applications.aotutest.services.autotest_project_crud import AutoTestApiProjectCrud
            await AutoTestApiProjectCrud().get_by_id(project_id=data.project_id, on_error=True, state__not=1)

            existing = await self.get_by_id(env_id=data.id, on_error=True, state__not=1)
            new_env_name = data.env_name.upper()
            old_project_id = existing.project_id
            old_env_name = existing.env_name
            old_env_type = existing.env_type

            duplicate = await self.model.filter(
                project_id=data.project_id,
                env_name=new_env_name,
                env_type=data.env_type,
                state=0,
            ).first()
            if duplicate and duplicate.id != existing.id:
                raise DataAlreadyExistsException(
                    message=f"应用：{data.project_id}+环境：{new_env_name}+类型：{data.env_type}已经存在，不能重复"
                )

            update_dict: Dict[str, Any] = {
                "project_id": data.project_id,
                "env_name": new_env_name,
                "env_type": data.env_type,
            }
            if data.updated_user:
                update_dict["updated_user"] = data.updated_user
            existing = await self.update(id=data.id, obj_in=update_dict)

            config_qs = AutoTestApiEnvConfigInfo.filter(
                env_id=data.id,
                config_type=resolve_config_type(old_env_type),
                state=0,
            )
            if old_project_id != data.project_id or old_env_name != new_env_name or old_env_type != data.env_type:
                from backend.applications.aotutest.services.autotest_env_config_crud import AutoTestApiEnvConfigCrud
                config_crud = AutoTestApiEnvConfigCrud()
                config_update: Dict[str, Any] = {
                    "project_id": data.project_id,
                    "config_type": config_type,
                }
                if data.updated_user:
                    config_update["updated_user"] = data.updated_user
                config_crud._fill_updated_user(config_update)
                await config_qs.update(**config_update)

            return {
                "id": existing.id,
                "project_id": existing.project_id,
                "env_name": existing.env_name,
                "env_type": existing.env_type,
                "updated_time": existing.updated_time or datetime.now(),
                "created_time": existing.created_time or datetime.now(),
            }
        except (DataAlreadyExistsException, ParameterException, NotFoundException):
            raise
        except Exception as e:
            error_message = f"编辑环境失败：异常信息{e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def delete_automation_env(self, env_id: int, env_type: int) -> Dict[str, Any]:
        """
        软删环境主表记录，并软删其下对应类型的配置。

        :param env_id: 环境主键ID
        :param env_type: 节点类型（校验与主表一致）
        :return: 环境响应字典
        """
        try:
            config_type = resolve_config_type(env_type)
            existing = await self.get_by_id(env_id=env_id, on_error=True, state__not=1)
            if existing.env_type != env_type:
                raise ParameterException(
                    message=f"环境ID:{env_id}的节点类型为{existing.env_type}，与请求类型{env_type}不一致"
                )

            from backend.applications.aotutest.services.autotest_env_config_crud import AutoTestApiEnvConfigCrud
            config_crud = AutoTestApiEnvConfigCrud()
            config_ids = await AutoTestApiEnvConfigInfo.filter(
                env_id=env_id,
                config_type=config_type,
                state=0,
            ).values_list("id", flat=True)
            await config_crud.soft_delete_batch(ids=list(config_ids))

            existing = await self.soft_delete(id=env_id)

            return {
                "id": existing.id,
                "project_id": existing.project_id,
                "env_name": existing.env_name,
                "env_type": existing.env_type,
                "updated_time": existing.updated_time or datetime.now(),
                "created_time": existing.created_time or datetime.now(),
            }
        except (ParameterException, NotFoundException):
            raise
        except Exception as e:
            error_message = f"删除环境失败，异常信息：{e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
