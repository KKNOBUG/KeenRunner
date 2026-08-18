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

from backend.applications.aotutest.models.autotest_env_config_model import AutoTestEnvBindModel, AutoTestEnvConfigModel
from backend.applications.aotutest.models.autotest_env_model import AutoTestEnvModel
from backend.applications.aotutest.models.autotest_project_model import AutoTestProjectModel
from backend.applications.aotutest.schemas.autotest_env_schema import (
    AutoTestApiEnvCreate,
    AutoTestApiEnvUpdate,
    AutoTestApiEnvDelete,
)
from backend.applications.aotutest.services.autotest_project_crud import AutoTestProjectCrud
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import GLOBAL_CONFIG, LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
)
from backend.enums import AutoTestConfigNodeType


class AutoTestEnvCrud(ScaffoldCrud[AutoTestEnvBindModel, AutoTestApiEnvCreate, AutoTestApiEnvUpdate]):

    def __init__(self):
        super().__init__(model=AutoTestEnvBindModel)

    async def get_by_id(self, env_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestEnvBindModel]:
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

    async def get_by_code(self, env_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestEnvBindModel]:
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
            env_type: Optional[Union[AutoTestConfigNodeType, str]] = None,
            on_error: bool = False,
    ) -> Optional[AutoTestEnvBindModel]:
        """
        按应用+环境名称解析环境绑定；指定env_type时仅匹配该类型。

        :param project_id: 应用主键ID
        :param env_name: 环境名称(忽略大小写)
        :param env_type: 节点类型(app/file/database/redis)，为空则取首条启用绑定
        :param on_error: 未找到时是否抛出NotFoundException
        :return: 环境绑定实例或None
        """
        name = (env_name or "").strip()
        if not name:
            error_message: str = "查询环境绑定信息失败, 参数[env_name]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        dict_ids = await AutoTestEnvModel.filter(
            env_name__iexact=name, state__not=1
        ).values_list("id", flat=True)
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
            error_message: str = (
                f"查询环境绑定信息失败, 记录[project_id={project_id}, env_name={name}{type_hint}]不存在"
            )
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
        query = AutoTestEnvModel.filter(state__not=1)
        if exact:
            query = query.filter(env_name__iexact=name)
        else:
            query = query.filter(env_name__icontains=name)
        return await query.values_list("id", flat=True)

    async def get_env_name_map(self, env_bind_ids: List[int]) -> Dict[int, str]:
        """
        批量解析环境绑定ID到环境名称的映射，已删除的绑定不解析。

        :param env_bind_ids: 环境绑定主键ID列表
        :return: {绑定ID: 环境名称}
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
        :return: {绑定ID: {project_id, env_type, env_enum_id}}
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
        :param env_enum_ids: 环境字典ID列表
        :param state_not: 排除的状态值
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

    async def _get_or_create_env_dict(
            self,
            env_name: str,
            user: Optional[str] = None,
    ) -> AutoTestEnvModel:
        """
        按环境名称获取或创建全局环境枚举记录。

        :param env_name: 环境名称(规范化为大写)
        :param user: 操作人
        :return: 环境枚举实例
        """
        name = (env_name or "").strip().upper()
        if not name:
            error_message: str = "参数[env_name]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        dict_row = await AutoTestEnvModel.filter(env_name=name).first()
        if dict_row:
            if dict_row.state == 1:
                update_dict: Dict[str, Any] = {"state": 0}
                if user:
                    update_dict["updated_user"] = user
                await AutoTestEnvModel.filter(id=dict_row.id).update(**update_dict)
                dict_row = await AutoTestEnvModel.get(id=dict_row.id)
            return dict_row
        try:
            return await AutoTestEnvModel.create(
                env_name=name,
                created_user=user,
            )
        except IntegrityError as e:
            # 并发创建触发唯一约束时回查既有记录
            dict_row = await AutoTestEnvModel.filter(env_name=name).first()
            if dict_row:
                return dict_row
            error_message: str = f"新增环境枚举信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def create_env(self, env_in: AutoTestApiEnvCreate) -> AutoTestEnvBindModel:
        """
        创建环境绑定；同应用+环境+类型已存在则恢复启用。

        :param env_in: 环境创建schema（含 project_id / env_type）
        :return: 创建或恢复后的环境绑定实例
        """
        await AutoTestProjectCrud().get_by_id(project_id=env_in.project_id, on_error=True, state__not=1)
        dict_row = await self._get_or_create_env_dict(
            env_name=env_in.env_name,
            user=env_in.created_user,
        )
        existing_bind: Optional[AutoTestEnvBindModel] = await self.model.filter(
            env_enum_id=dict_row.id,
            project_id=env_in.project_id,
            env_type=env_in.env_type,
        ).first()
        if not existing_bind:
            payload = env_in.model_dump(
                exclude_none=True,
                exclude_unset=True,
                exclude={"env_name"},
            )
            payload["env_enum_id"] = dict_row.id
            try:
                return await self.create(obj_in=payload)
            except IntegrityError as e:
                error_message: str = f"新增环境绑定信息异常, 违反约束规则: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise DataBaseStorageException(message=error_message) from e

        # 已启用则直接复用；仅软删记录需要恢复
        if existing_bind.state == 0:
            return existing_bind
        try:
            restore_dict: Dict[str, Any] = {"state": 0}
            if env_in.env_desc is not None:
                restore_dict["env_desc"] = env_in.env_desc
            if env_in.created_user:
                restore_dict["updated_user"] = env_in.created_user
            return await self.update(id=existing_bind.id, obj_in=restore_dict)
        except (DoesNotExist, IntegrityError) as e:
            error_message: str = f"新增(更新)环境绑定信息异常, 违反约束规则或空指针异常: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_env(self, env_in: AutoTestApiEnvUpdate) -> AutoTestEnvBindModel:
        """
        按env_id/env_code精准更新单条环境绑定；描述写在绑定表，不影响同名其他节点类型。

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

        if env_in.env_type is not None and instance.env_type != env_in.env_type:
            raise ParameterException(
                message=f"类型不匹配，记录类型为{instance.env_type}，请求类型为{env_in.env_type}"
            )
        if env_in.project_id is not None and int(instance.project_id) != int(env_in.project_id):
            raise ParameterException(message="应用ID不匹配，请检查")

        update_dict: Dict[str, Any] = env_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"env_id", "env_code", "env_type", "project_id"},
        )
        new_env_name = update_dict.pop("env_name", None)
        # env_desc保留在update_dict，落绑定表
        if new_env_name:
            dict_row = await self._get_or_create_env_dict(
                env_name=new_env_name,
                user=env_in.updated_user,
            )
            update_dict["env_enum_id"] = dict_row.id

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

    async def delete_env(self, env_id: Optional[int] = None, env_code: Optional[str] = None) -> AutoTestEnvBindModel:
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
        根据ID或code列表批量软删除环境绑定。

        :param env_in: 环境绑定删除schema
        :return: 更新条数
        """
        env_ids: Optional[List[int]] = env_in.env_ids
        env_codes: Optional[List[str]] = env_in.env_codes
        if not env_ids and not env_codes:
            error_message: str = "删除环境绑定信息失败, 参数[env_ids]或[env_codes]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        targets: List[AutoTestEnvBindModel] = []
        if env_ids:
            for eid in env_ids:
                targets.append(await self.get_by_id(env_id=eid, on_error=True, state__not=1))
        else:
            for ecode in env_codes:
                targets.append(await self.get_by_code(env_code=ecode, on_error=True, state__not=1))

        for instance in targets:
            await self.soft_delete(id=instance.id)

        return len(targets)

    async def select_envs(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestEnvBindModel]]:
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
        return await AutoTestEnvModel.filter(state__not=1).distinct().values_list("env_name", flat=True)

    async def serialize_env(self, bind: AutoTestEnvBindModel, with_audit: bool = False) -> Dict[str, Any]:
        """
        将环境绑定实例与字典信息拼装为响应结构。

        :param bind: 环境绑定实例
        :param with_audit: 是否附带审计字段(创建/更新人员与时间)
        :return: 环境响应字典
        """
        dict_row = await AutoTestEnvModel.filter(id=bind.env_enum_id).first()
        return await self._assemble_env_dict(bind, dict_row, with_audit)

    async def serialize_envs(self, binds: List[AutoTestEnvBindModel], with_audit: bool = False) -> List[Dict[str, Any]]:
        """
        批量拼装环境绑定列表响应结构。

        :param binds: 环境绑定实例列表
        :param with_audit: 是否附带审计字段(创建/更新人员与时间)
        :return: 环境响应字典列表
        """
        dict_ids = list({bind.env_enum_id for bind in binds})
        dict_rows = await AutoTestEnvModel.filter(id__in=dict_ids).all() if dict_ids else []
        dict_map = {row.id: row for row in dict_rows}
        return [
            await self._assemble_env_dict(bind, dict_map.get(bind.env_enum_id), with_audit)
            for bind in binds
        ]

    @staticmethod
    async def _assemble_env_dict(
            bind: AutoTestEnvBindModel,
            dict_row: Optional[AutoTestEnvModel],
            with_audit: bool,
    ) -> Dict[str, Any]:
        """
        拼装环境响应字典。

        接口仍返回env_id表示绑定主键；库内字段env_enum_id不对外暴露。

        :param bind: 环境绑定实例
        :param dict_row: 环境枚举实例，缺失时名称降级为空
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
        data["env_name"] = dict_row.env_name if dict_row else ""
        data["env_desc"] = bind.env_desc
        return data

    async def get_envs(
            self,
            project_id: Optional[List[int]] = None,
    ) -> Union[Dict[str, List[str]], Dict[int, Dict[str, List[str]]]]:
        """
        按节点类型聚合环境名称（读环境绑定表并联字典）。

        :param project_id: None=全局聚合；[]=全部应用；[ids]=指定应用
        :return: {app/file/database/redis: [...]} 或 {project_id: {app/file/database/redis: [...]}}
        """
        try:
            allowed_types = set(AutoTestConfigNodeType.get_values())
            base_qs = self.model.filter(state=0)

            if project_id is None:
                rows = await base_qs.values("env_type", "env_enum_id")
                name_map = await self._get_dict_name_map({row["env_enum_id"] for row in rows})
                env_map: Dict[str, set] = defaultdict(set)
                for row in rows:
                    env_type = row["env_type"].value
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
                env_type = row["env_type"].value
                name = name_map.get(row["env_enum_id"])
                if env_type in allowed_types and name:
                    grouped[row["project_id"]][env_type].add(name)

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
        return dict(await AutoTestEnvModel.filter(id__in=list(dict_ids)).values_list("id", "env_name"))

    async def get_env_search_list(
            self,
            project_id: Optional[int] = None,
            env_name: Optional[str] = None,
            env_type: Optional[Union[AutoTestConfigNodeType, str]] = None,
            ip: Optional[str] = None,
            page: int = 1,
            page_size: int = 10,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        以环境绑定表分页查询；可选按子配置IP过滤。

        :return: (总条数, 当前页记录)；记录含env_id(绑定主键)/project_id/env_name/env_type/project_name/is_delete/时间字段
        """
        try:
            base_qs = self.model.filter(state=0)

            if ip:
                matched_bind_ids = await AutoTestEnvConfigModel.filter(
                    state=0,
                    config_host__contains=ip,
                ).values_list("env_bind_id", flat=True)
                if not matched_bind_ids:
                    return 0, []
                base_qs = base_qs.filter(id__in=list(set(matched_bind_ids)))

            if project_id is not None:
                base_qs = base_qs.filter(project_id=project_id)
            if env_name:
                dict_ids = await self.get_dict_ids_by_name(env_name)
                if not dict_ids:
                    return 0, []
                base_qs = base_qs.filter(env_enum_id__in=dict_ids)
            if env_type is not None:
                base_qs = base_qs.filter(env_type=env_type)

            active_project_ids = await AutoTestProjectModel.filter(state=0).values_list("id", flat=True)
            if active_project_ids:
                base_qs = base_qs.filter(project_id__in=list(active_project_ids))

            total = await base_qs.count()
            offset = (page - 1) * page_size
            page_rows = await base_qs.offset(offset).limit(page_size).values(
                "id", "project_id", "env_enum_id", "env_type", "created_time", "updated_time"
            )

            dict_name_map = await self._get_dict_name_map({item["env_enum_id"] for item in page_rows})

            project_ids = [int(item["project_id"]) for item in page_rows]
            project_map = {}
            if project_ids:
                project_map = dict(
                    await AutoTestProjectModel.filter(id__in=project_ids, state=0).values_list("id", "project_name")
                )

            check_ids = [item["id"] for item in page_rows]
            sub_exists = set()
            if check_ids:
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
                    "project_name": project_map.get(int(item["project_id"]), ""),
                    "is_delete": env_bind_id not in sub_exists,
                })
            return total, result
        except ParameterException:
            raise
        except Exception as e:
            error_message = f"查询环境搜索列表异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
