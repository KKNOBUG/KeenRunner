# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_env_crud
@DateTime: 2026/1/2 17:42
"""
import traceback
from typing import Optional, Dict, Any, Union, List, Tuple

from tortoise.exceptions import IntegrityError, FieldError, DoesNotExist
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

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
    按「全局环境枚举名 + 应用」解析 HTTP 网关 host/port：
    先查 AutoTestApiEnvEnumInfo（仅 env_name），再查 AutoTestApiEnvConfigInfo（project_id + env_id，config_type=api）。
    """
    pid = int(project_id)
    name = (env_name or "").strip()
    if not name:
        raise ParameterException(message="执行环境名称(env_name)不允许为空")

    env_row = await AutoTestApiEnvEnumInfo.filter(env_name__iexact=name, state__not=1).first()
    if not env_row:
        raise NotFoundException(message=f"环境枚举不存在: env_name={name!r}")

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
        raise NotFoundException(
            message=(
                f"未找到可用的 API 环境配置(config_type={AutoTestConfigNodeType.API.value!r} 且 config_host 非空): "
                f"project_id={pid}, env_id={env_row.id}"
            )
        )
    host = str(cfg.config_host).strip().rstrip("/").rstrip(":")
    port_raw = getattr(cfg, "config_port", None)
    if port_raw is None or str(port_raw).strip() == "":
        return host, None
    return host, str(port_raw).strip()


class AutoTestApiEnvEnumCrud(ScaffoldCrud[AutoTestApiEnvEnumInfo, AutoTestApiEnvCreate, AutoTestApiEnvUpdate]):
    """自动化测试环境的 CRUD 服务，负责环境枚举的增删改查。"""

    def __init__(self):
        """初始化 CRUD，绑定模型 AutoTestApiEnvEnumInfo。"""
        super().__init__(model=AutoTestApiEnvEnumInfo)

    async def get_by_id(self, env_id: int, on_error: bool = False) -> Optional[AutoTestApiEnvEnumInfo]:
        """
        根据环境枚举主键查询
        :param env_id: 环境枚举主键
        :param on_error: 为 True 时若未找到则抛出 NotFoundException
        :returns: 环境实例或 None
        :raises ParameterException: 当 env_id 为空时
        :raises NotFoundException: 当 on_error 为 True 且记录不存在时
        """
        if not env_id:
            error_message: str = "查询环境枚举信息失败, 参数(env_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(id=env_id, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询环境枚举信息失败, 环境(id={env_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, env_code: str, on_error: bool = False) -> Optional[AutoTestApiEnvEnumInfo]:
        """
        根据环境枚举标识代码查询
        :param env_code: 环境标识代码
        :param on_error: 为 True 时若未找到则抛出 NotFoundException
        :returns: 环境实例或 None
        :raises ParameterException: 当 env_code 为空时
        :raises NotFoundException: 当 on_error 为 True 且记录不存在时
        """
        if not env_code:
            error_message: str = "查询环境枚举信息失败, 参数(env_code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(env_code=env_code, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询环境枚举信息失败, 环境(code={env_code})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_name(self, env_name: str, on_error: bool = False) -> Optional[AutoTestApiEnvEnumInfo]:
        """
        根据环境枚举名称查询
        :param env_name: 环境枚举名称
        :param on_error: 为 True 时若未找到则抛出 NotFoundException
        :returns: 环境实例或 None
        :raises ParameterException: 当 env_id 为空时
        :raises NotFoundException: 当 on_error 为 True 且记录不存在时
        """
        if not env_name:
            error_message: str = "查询环境枚举信息失败, 参数(env_name)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(env_name=env_name, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询环境枚举信息失败, 环境(env_name={env_name})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True,
            on_error: bool = False
    ) -> Optional[Union[AutoTestApiEnvEnumInfo, List[AutoTestApiEnvEnumInfo]]]:
        """
        根据条件查询
        :param conditions: 查询条件字典
        :param only_one: 为 True 时返回单条记录，否则返回列表
        :param on_error: 为 True 时若未找到则抛出 NotFoundException
        :returns: 单条环境、环境列表或 None
        :raises ParameterException: 条件非法或查询异常时
        :raises NotFoundException: 当 on_error 为 True 且无匹配记录时
        """
        try:
            stmt: QuerySet = self.model.filter(**conditions, state__not=1)
            instances = await (stmt.first() if only_one else stmt.all())
        except FieldError as e:
            error_message: str = f"查询环境枚举信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
        except Exception as e:
            error_message: str = f"查询环境枚举信息发生未知异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

        if not instances and on_error:
            error_message: str = f"查询环境枚举信息失败, 条件{conditions}不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instances

    async def create_env(self, env_in: AutoTestApiEnvCreate) -> AutoTestApiEnvEnumInfo:
        """
        创建环境枚举信息
        :param env_in: 环境枚举创建 schema 定义
        :returns: 创建或恢复后的环境枚举实例
        :raises DataAlreadyExistsException: 已存在启用状态的环境枚举名称时
        :raises DataBaseStorageException: 违反数据库约束时
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
        更新环境信息
        :param env_in: 环境枚举更新 schema 定义
        :returns: 更新后的环境枚举实例
        :raises NotFoundException: 环境枚举不存在时
        :raises DataAlreadyExistsException: 环境枚举名称重复时
        :raises DataBaseStorageException: 违反约束时
        """
        env_id: Optional[int] = env_in.env_id
        env_code: Optional[str] = env_in.env_code

        # 业务层验证：检查环境信息是否存在
        if env_id:
            instance = await self.get_by_id(env_id=env_id, on_error=True)
            env_code: str = instance.env_code
        else:
            instance = await self.get_by_code(env_code=env_code, on_error=True)
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
            error_message: str = f"更新环境枚举信息失败, 环境(id={env_id}或code={env_code})不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = f"更新环境枚举信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_env(self, env_id: Optional[int] = None, env_code: Optional[str] = None) -> AutoTestApiEnvEnumInfo:
        """
        删除环境枚举信息
        :param env_id: 环境枚举主键
        :param env_code: 环境枚举标识代码
        :returns: 删除后的环境枚举实例
        :raises NotFoundException: 环境枚举不存在时
        """
        # 业务层验证：检查环境信息是否存在
        if env_id:
            instance = await self.get_by_id(env_id=env_id, on_error=True)
        else:
            instance = await self.get_by_code(env_code=env_code, on_error=True)

        instance.state = 1
        await instance.save()
        return instance

    async def delete_envs(self, env_in: AutoTestApiEnvDelete) -> int:
        """
        删除环境枚举信息
        :param env_in: 环境枚举删除 schema 定义
        :returns: 删除的数量
        """
        env_ids: Optional[List[int]] = env_in.env_ids
        env_codes: Optional[List[str]] = env_in.env_codes
        if env_ids:
            count = await self.model.filter(id__in=env_ids).update(state=1)
        elif env_codes:
            count = await self.model.filter(env_code__in=env_codes).update(state=1)
        else:
            count = 0
        return count

    async def select_envs(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        """
        分页查询环境枚举列表
        :param search: Tortoise Q 查询条件。
        :param page: 页码。
        :param page_size: 每页条数。
        :param order: 排序字段列表。
        :returns: 由 (总条数, 当前页记录列表) 组成的元组。
        :raises ParameterException: 查询条件非法导致 FieldError 时。
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询环境枚举信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e


AUTOTEST_API_ENV_ENUM_CRUD = AutoTestApiEnvEnumCrud()
