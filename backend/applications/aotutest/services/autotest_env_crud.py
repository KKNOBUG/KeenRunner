# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_env_crud
@DateTime: 2026/1/2 17:42
"""
import traceback
from typing import Optional, Dict, Any, List, Tuple

from tortoise.exceptions import IntegrityError, FieldError, DoesNotExist
from tortoise.expressions import Q

from backend.applications.aotutest.models.autotest_model import AutoTestApiEnvEnumInfo, AutoTestApiEnvConfigInfo
from backend.applications.aotutest.schemas.autotest_env_schema import (
    AutoTestApiEnvCreate,
    AutoTestApiEnvUpdate,
    AutoTestApiEnvDelete
)
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
)
from backend.enums import AutoTestConfigNodeType


async def resolve_env_api_base_host_port(project_id: int, env_name: str) -> Tuple[str, Optional[str]]:
    """
    根据全局环境枚举名与应用解析API的host/port。

    :param project_id: 应用主键ID
    :param env_name: 环境枚举名称
    :return: (host, port)；port可为空
    :raises ParameterException: env_name为空
    :raises NotFoundException: 环境枚举或API配置不存在
    """
    pid = int(project_id)
    name = (env_name or "").strip()
    if not name:
        error_message: str = "参数[env_name]不允许为空"
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)

    env_row = await AutoTestApiEnvEnumInfo.filter(env_name__iexact=name, state__not=1).first()
    if not env_row:
        error_message: str = f"查询环境枚举失败, 记录[env_name={name}]不存在"
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
        :raises ParameterException: env_id为空
        :raises NotFoundException: on_error为True且记录不存在
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
        :raises ParameterException: env_code为空
        :raises NotFoundException: on_error为True且记录不存在
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
        :raises ParameterException: env_name为空
        :raises NotFoundException: on_error为True且记录不存在
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
        创建环境枚举；同名已存在则恢复并更新。

        :param env_in: 环境枚举创建schema
        :return: 创建或恢复后的环境枚举实例
        :raises DataBaseStorageException: 违反数据库约束或记录异常丢失
        """
        env_name: str = env_in.env_name
        # 业务层验证：检查环境枚举名称是否存在
        env_dict: Dict[str, Any] = env_in.model_dump(exclude_none=True, exclude_unset=True)
        existing_env: Optional[AutoTestApiEnvEnumInfo] = await self.model.filter(env_name=env_name).first()
        if not existing_env:
            try:
                instance: AutoTestApiEnvEnumInfo = await self.create(obj_in=env_dict)
                return instance
            except IntegrityError as e:
                error_message: str = f"新增环境枚举信息异常, 违反约束规则: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise DataBaseStorageException(message=error_message) from e

        try:
            env_dict["state"] = 0
            instance: AutoTestApiEnvEnumInfo = await self.update(id=existing_env.id, obj_in=env_dict)
            return instance
        except (DoesNotExist, IntegrityError) as e:
            error_message: str = f"新增(更新)环境枚举信息异常, 违反约束规则或空指针异常: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_env(self, env_in: AutoTestApiEnvUpdate) -> AutoTestApiEnvEnumInfo:
        """
        更新环境枚举，根据env_id或env_code定位。

        :param env_in: 环境枚举更新schema
        :return: 更新后的环境枚举实例
        :raises NotFoundException: 环境枚举不存在
        :raises DataBaseStorageException: 违反约束
        """
        env_id: Optional[int] = env_in.env_id
        env_code: Optional[str] = env_in.env_code

        # 业务层验证：检查环境信息是否存在
        if env_id:
            instance = await self.get_by_id(env_id=env_id, on_error=True, state__not=1)
            env_code: str = instance.env_code
        else:
            instance = await self.get_by_code(env_code=env_code, on_error=True, state__not=1)
            env_id: int = instance.id

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
        :raises NotFoundException: 环境枚举不存在
        """
        # 业务层验证：检查环境信息是否存在
        if env_id:
            instance = await self.get_by_id(env_id=env_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(env_code=env_code, on_error=True, state__not=1)

        instance.state = 1
        await instance.save()
        return instance

    async def delete_envs(self, env_in: AutoTestApiEnvDelete) -> int:
        """
        根据ID或code列表批量软删除环境枚举。

        :param env_in: 环境枚举删除schema
        :return: 更新条数
        :raises ParameterException: env_ids与env_codes均未传
        """
        env_ids: Optional[List[int]] = env_in.env_ids
        env_codes: Optional[List[str]] = env_in.env_codes
        if not env_ids and not env_codes:
            error_message: str = "删除环境枚举信息失败, 参数[env_ids]或[env_codes]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if env_ids:
            count = await self.model.filter(id__in=env_ids).update(state=1)
        else:
            count = await self.model.filter(env_code__in=env_codes).update(state=1)
        return count

    async def select_envs(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestApiEnvEnumInfo]]:
        """
        根据条件分页查询环境枚举列表。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)
        :raises ParameterException: 查询字段非法
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询环境枚举信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
