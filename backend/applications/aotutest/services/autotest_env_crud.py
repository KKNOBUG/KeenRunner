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
    AutoTestApiEnvInfo,
    AutoTestApiEnvBindInfo,
    AutoTestApiEnvConfigInfo,
    AutoTestApiProjectInfo,
)
from backend.applications.aotutest.schemas.autotest_env_schema import (
    AutoTestApiEnvCreate,
    AutoTestApiEnvUpdate,
    AutoTestApiEnvDelete,
)
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
)
from backend.enums import AutoTestConfigNodeType

# env_type(1/2/3/4) 与 config_type(api/file/database/redis) 双向映射
ENV_TYPE_TO_CONFIG_TYPE = {
    1: AutoTestConfigNodeType.API.value,
    2: AutoTestConfigNodeType.FILE.value,
    3: AutoTestConfigNodeType.DB.value,
    4: AutoTestConfigNodeType.REDIS.value,
}
CONFIG_TYPE_TO_ENV_TYPE = {
    AutoTestConfigNodeType.API.value: 1,
    AutoTestConfigNodeType.FILE.value: 2,
    AutoTestConfigNodeType.DB.value: 3,
    AutoTestConfigNodeType.REDIS.value: 4,
}


def resolve_config_type(env_type: int) -> str:
    """
    将节点类型编码转换为config_type枚举值。

    :param env_type: 1=APP, 2=FILE, 3=DB, 4=REDIS
    :return: api/file/database/redis
    """
    config_type = ENV_TYPE_TO_CONFIG_TYPE.get(env_type)
    if not config_type:
        error_message: str = f"节点类型[{env_type}]不被允许, 仅支持1:APP/2:FILE/3:DB/4:REDIS"
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


class AutoTestApiEnvCrud(ScaffoldCrud[AutoTestApiEnvBindInfo, AutoTestApiEnvCreate, AutoTestApiEnvUpdate]):

    def __init__(self):
        super().__init__(model=AutoTestApiEnvBindInfo)

    async def get_by_id(self, env_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestApiEnvBindInfo]:
        """
        根据主键ID查询环境绑定。

        :param env_id: 环境绑定主键
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 环境绑定实例或None
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

    async def get_by_code(self, env_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestApiEnvBindInfo]:
        """
        根据标识代码查询环境绑定。

        :param env_code: 绑定标识代码
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 环境绑定实例或None
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
            env_type: Optional[int] = None,
            on_error: bool = False,
    ) -> Optional[AutoTestApiEnvBindInfo]:
        """
        按应用+环境名称解析环境绑定记录，指定节点类型时优先匹配该类型。

        :param project_id: 应用主键ID
        :param env_name: 环境名称(忽略大小写)
        :param env_type: 优先匹配的节点类型，未匹配到时回退任意类型
        :param on_error: 未找到时是否抛出NotFoundException
        :return: 环境绑定实例或None
        """
        name = (env_name or "").strip()
        if not name:
            error_message: str = "查询环境绑定信息失败, 参数[env_name]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        dict_ids = await AutoTestApiEnvInfo.filter(
            env_name__iexact=name, state__not=1
        ).values_list("id", flat=True)
        instance: Optional[AutoTestApiEnvBindInfo] = None
        if dict_ids:
            base_filter: Dict[str, Any] = {
                "project_id": int(project_id),
                "env_id__in": list(dict_ids),
                "state__not": 1,
            }
            if env_type is not None:
                instance = await self.model.filter(env_type=resolve_config_type(env_type), **base_filter).first()
            if not instance:
                instance = await self.model.filter(**base_filter).first()
        if not instance and on_error:
            error_message: str = f"查询环境绑定信息失败, 记录[project_id={project_id}, env_name={name}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_dict_ids_by_name(self, env_name: str, exact: bool = False) -> List[int]:
        """
        按环境名称查询字典主键ID列表。

        :param env_name: 环境名称
        :param exact: True=精确匹配(忽略大小写)，False=模糊包含
        :return: 字典主键ID列表
        """
        name = (env_name or "").strip()
        if not name:
            return []
        query = AutoTestApiEnvInfo.filter(state__not=1)
        if exact:
            query = query.filter(env_name__iexact=name)
        else:
            query = query.filter(env_name__icontains=name)
        return await query.values_list("id", flat=True)

    async def get_env_name_map(self, bind_ids: List[int]) -> Dict[int, str]:
        """
        批量解析环境绑定ID到环境名称的映射，已删除的绑定不解析。

        :param bind_ids: 环境绑定主键ID列表
        :return: {绑定ID: 环境名称}
        """
        if not bind_ids:
            return {}
        bind_rows = await self.model.filter(
            id__in=list(set(bind_ids)), state__not=1
        ).values("id", "env_id")
        dict_ids = {row["env_id"] for row in bind_rows}
        if not dict_ids:
            return {}
        dict_name_map = dict(
            await AutoTestApiEnvInfo.filter(id__in=list(dict_ids)).values_list("id", "env_name")
        )
        return {row["id"]: dict_name_map.get(row["env_id"], "") for row in bind_rows}

    async def _get_or_create_env_dict(
            self,
            env_name: str,
            env_desc: Optional[str] = None,
            user: Optional[str] = None,
    ) -> AutoTestApiEnvInfo:
        """
        按环境名称获取或创建全局环境字典记录。

        :param env_name: 环境名称(规范化为大写)
        :param env_desc: 环境描述，仅在新建或非空时写入
        :param user: 操作人
        :return: 环境字典实例
        """
        name = (env_name or "").strip().upper()
        if not name:
            error_message: str = "参数[env_name]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        dict_row = await AutoTestApiEnvInfo.filter(env_name=name).first()
        if dict_row:
            update_dict: Dict[str, Any] = {}
            if dict_row.state == 1:
                update_dict["state"] = 0
            if env_desc:
                update_dict["env_desc"] = env_desc
            if update_dict:
                if user:
                    update_dict["updated_user"] = user
                await AutoTestApiEnvInfo.filter(id=dict_row.id).update(**update_dict)
                dict_row = await AutoTestApiEnvInfo.get(id=dict_row.id)
            return dict_row
        try:
            return await AutoTestApiEnvInfo.create(
                env_name=name,
                env_desc=env_desc,
                created_user=user,
            )
        except IntegrityError as e:
            # 并发创建触发唯一约束时回查既有记录
            dict_row = await AutoTestApiEnvInfo.filter(env_name=name).first()
            if dict_row:
                return dict_row
            error_message: str = f"新增环境字典信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def create_env(self, env_in: AutoTestApiEnvCreate) -> AutoTestApiEnvBindInfo:
        """
        创建环境绑定；同应用+环境+类型已存在则恢复启用。

        :param env_in: 环境创建schema（含 project_id / env_type）
        :return: 创建或恢复后的环境绑定实例
        """
        config_type = resolve_config_type(env_in.env_type)
        dict_row = await self._get_or_create_env_dict(
            env_name=env_in.env_name,
            env_desc=env_in.env_desc,
            user=env_in.created_user,
        )
        existing_bind: Optional[AutoTestApiEnvBindInfo] = await self.model.filter(
            env_id=dict_row.id,
            project_id=env_in.project_id,
            env_type=config_type,
        ).first()
        if not existing_bind:
            try:
                instance: AutoTestApiEnvBindInfo = await self.create(obj_in={
                    "env_id": dict_row.id,
                    "project_id": env_in.project_id,
                    "env_type": config_type,
                    "created_user": env_in.created_user,
                })
                return instance
            except IntegrityError as e:
                error_message: str = f"新增环境绑定信息异常, 违反约束规则: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise DataBaseStorageException(message=error_message) from e

        try:
            restore_dict: Dict[str, Any] = {"state": 0}
            if env_in.created_user:
                restore_dict["updated_user"] = env_in.created_user
            instance = await self.update(id=existing_bind.id, obj_in=restore_dict)
            return instance
        except (DoesNotExist, IntegrityError) as e:
            error_message: str = f"新增(更新)环境绑定信息异常, 违反约束规则或空指针异常: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_env(self, env_in: AutoTestApiEnvUpdate) -> AutoTestApiEnvBindInfo:
        """
        更新环境绑定，根据env_id或env_code定位；名称变更转为重指字典记录。

        :param env_in: 环境绑定更新schema
        :return: 更新后的环境绑定实例
        """
        env_id: Optional[int] = env_in.env_id
        env_code: Optional[str] = env_in.env_code

        if not env_id and not env_code:
            error_message: str = "更新环境绑定信息失败, 参数[env_id]或[env_code]不允许为空"
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
        new_env_name = update_dict.pop("env_name", None)
        env_desc = update_dict.pop("env_desc", None)
        if "env_type" in update_dict:
            update_dict["env_type"] = resolve_config_type(update_dict["env_type"])
        if new_env_name:
            dict_row = await self._get_or_create_env_dict(
                env_name=new_env_name,
                env_desc=env_desc,
                user=env_in.updated_user,
            )
            update_dict["env_id"] = dict_row.id
        elif env_desc is not None:
            # 名称未变更时同步字典描述；允许显式传入空串清空描述
            await AutoTestApiEnvInfo.filter(id=instance.env_id).update(env_desc=env_desc)

        try:
            instance = await self.update(id=env_id, obj_in=update_dict)
            return instance
        except DoesNotExist as e:
            error_message: str = f"更新环境绑定信息失败, 记录[id={env_id}]或[code={env_code}]不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = f"更新环境绑定信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_env(self, env_id: Optional[int] = None, env_code: Optional[str] = None) -> AutoTestApiEnvBindInfo:
        """
        软删除环境绑定。

        :param env_id: 环境绑定主键，与env_code二选一
        :param env_code: 绑定标识代码，与env_id二选一
        :return: 软删除后的环境绑定实例
        """
        if not env_id and not env_code:
            error_message: str = "删除环境绑定信息失败, 参数[env_id]或[env_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if env_id:
            instance = await self.get_by_id(env_id=env_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(env_code=env_code, on_error=True, state__not=1)

        return await self.soft_delete(id=instance.id)

    async def delete_envs(self, env_in: AutoTestApiEnvDelete) -> int:
        """
        根据ID或code列表批量软删除环境绑定；逐条复用单删校验。

        :param env_in: 环境绑定删除schema
        :return: 更新条数
        """
        env_ids: Optional[List[int]] = env_in.env_ids
        env_codes: Optional[List[str]] = env_in.env_codes
        if not env_ids and not env_codes:
            error_message: str = "删除环境绑定信息失败, 参数[env_ids]或[env_codes]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        targets: List[AutoTestApiEnvBindInfo] = []
        if env_ids:
            for eid in env_ids:
                targets.append(await self.get_by_id(env_id=eid, on_error=True, state__not=1))
        else:
            for ecode in env_codes:
                targets.append(await self.get_by_code(env_code=ecode, on_error=True, state__not=1))

        for instance in targets:
            await self.delete_env(env_id=instance.id)

        return len(targets)

    async def select_envs(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestApiEnvBindInfo]]:
        """
        根据条件分页查询环境绑定列表。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询环境绑定信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def list_env_names(self) -> List[str]:
        """
        查询未删除的环境名称(去重)。

        :return: 环境名称列表
        """
        return await AutoTestApiEnvInfo.filter(state__not=1).distinct().values_list("env_name", flat=True)

    async def serialize_env(self, bind: AutoTestApiEnvBindInfo, with_audit: bool = False) -> Dict[str, Any]:
        """
        将环境绑定实例与字典信息拼装为历史接口响应结构。

        :param bind: 环境绑定实例
        :param with_audit: 是否附带审计字段(创建/更新人员与时间)
        :return: 与历史接口一致的环境响应字典
        """
        dict_row = await AutoTestApiEnvInfo.filter(id=bind.env_id).first()
        return self._assemble_env_dict(bind, dict_row, with_audit)

    async def serialize_envs(self, binds: List[AutoTestApiEnvBindInfo], with_audit: bool = False) -> List[Dict[str, Any]]:
        """
        批量拼装环境绑定列表的历史接口响应结构。

        :param binds: 环境绑定实例列表
        :param with_audit: 是否附带审计字段(创建/更新人员与时间)
        :return: 与历史接口一致的环境响应字典列表
        """
        dict_ids = list({bind.env_id for bind in binds})
        dict_rows = await AutoTestApiEnvInfo.filter(id__in=dict_ids).all() if dict_ids else []
        dict_map = {row.id: row for row in dict_rows}
        return [self._assemble_env_dict(bind, dict_map.get(bind.env_id), with_audit) for bind in binds]

    @staticmethod
    def _assemble_env_dict(
            bind: AutoTestApiEnvBindInfo,
            dict_row: Optional[AutoTestApiEnvInfo],
            with_audit: bool,
    ) -> Dict[str, Any]:
        """
        按历史接口字段顺序拼装环境响应字典。

        :param bind: 环境绑定实例
        :param dict_row: 环境字典实例，缺失时名称与描述降级为空
        :param with_audit: 是否附带审计字段
        :return: 环境响应字典
        """
        data: Dict[str, Any] = {"env_id": bind.id}
        if with_audit:
            data.update({
                "created_user": bind.created_user,
                "updated_user": bind.updated_user,
                "created_time": format_datetime(bind.created_time),
                "updated_time": format_datetime(bind.updated_time),
            })
        data.update({
            "env_name": dict_row.env_name if dict_row else "",
            "env_desc": dict_row.env_desc if dict_row else None,
            "env_code": bind.env_code,
            "project_id": bind.project_id,
            "env_type": CONFIG_TYPE_TO_ENV_TYPE.get(enum_field_value(bind.env_type)),
        })
        return data

    async def get_envs(
            self,
            project_id: Optional[List[int]] = None,
    ) -> Union[Dict[str, List[str]], Dict[int, Dict[str, List[str]]]]:
        """
        按节点类型聚合环境名称（读环境绑定表并联字典）。

        :param project_id: None=全局聚合；[]=全部应用；[ids]=指定应用
        :return: {APP/FILE/DB: [...]} 或 {project_id: {APP/FILE/DB: [...]}}
        """
        try:
            config_type_to_label = {
                AutoTestConfigNodeType.API.value: "APP",
                AutoTestConfigNodeType.FILE.value: "FILE",
                AutoTestConfigNodeType.DB.value: "DB",
            }
            base_qs = self.model.filter(state=0)

            if project_id is None:
                rows = await base_qs.values("env_type", "env_id")
                name_map = await self._get_dict_name_map({row["env_id"] for row in rows})
                env_map: Dict[str, set] = defaultdict(set)
                for row in rows:
                    label = config_type_to_label.get(enum_field_value(row["env_type"]))
                    name = name_map.get(row["env_id"])
                    if label and name:
                        env_map[label].add(name)
                return {et: sorted(names) for et, names in env_map.items()}

            unique_pids: Optional[List[int]] = None
            if not project_id:
                rows = await base_qs.values("project_id", "env_type", "env_id")
            else:
                unique_pids = list(dict.fromkeys(project_id))
                rows = await base_qs.filter(project_id__in=unique_pids).values(
                    "project_id", "env_type", "env_id"
                )

            name_map = await self._get_dict_name_map({row["env_id"] for row in rows})
            grouped: Dict[int, Dict[str, set]] = defaultdict(lambda: defaultdict(set))
            for row in rows:
                label = config_type_to_label.get(enum_field_value(row["env_type"]))
                name = name_map.get(row["env_id"])
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

    @staticmethod
    async def _get_dict_name_map(dict_ids) -> Dict[int, str]:
        """批量查询字典ID到环境名称的映射。"""
        if not dict_ids:
            return {}
        return dict(await AutoTestApiEnvInfo.filter(id__in=list(dict_ids)).values_list("id", "env_name"))

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
        以环境绑定表分页查询；可选按子配置IP过滤。

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
                dict_ids = await self.get_dict_ids_by_name(env_name)
                if not dict_ids:
                    return 0, []
                base_qs = base_qs.filter(env_id__in=dict_ids)
            if env_type is not None:
                base_qs = base_qs.filter(env_type=resolve_config_type(env_type))

            active_project_ids = await AutoTestApiProjectInfo.filter(state=0).values_list("id", flat=True)
            if active_project_ids:
                base_qs = base_qs.filter(project_id__in=list(active_project_ids))

            total = await base_qs.count()
            offset = (page - 1) * page_size
            page_rows = await base_qs.offset(offset).limit(page_size).values(
                "id", "project_id", "env_id", "env_type", "created_time", "updated_time"
            )

            dict_name_map = await self._get_dict_name_map({item["env_id"] for item in page_rows})

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

            result: List[Dict[str, Any]] = []
            for item in page_rows:
                item_env_type = CONFIG_TYPE_TO_ENV_TYPE.get(enum_field_value(item["env_type"]))
                result.append({
                    "id": str(item["id"]),
                    "project_id": str(item["project_id"]),
                    "env_name": dict_name_map.get(item["env_id"], ""),
                    "env_type": item_env_type,
                    "created_time": format_datetime(item["created_time"]),
                    "updated_time": format_datetime(item["updated_time"]),
                    "project_name": project_map.get(int(item["project_id"]), ""),
                    "is_delete": (item["id"], item["project_id"], item_env_type) not in sub_exists,
                })
            return total, result
        except ParameterException:
            raise
        except Exception as e:
            error_message = f"查询环境搜索列表异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
