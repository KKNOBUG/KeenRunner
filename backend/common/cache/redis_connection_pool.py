# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : redis_connection_pool
@DateTime: 2026/6/6
"""
import asyncio
import shlex
import traceback
from typing import Any, Dict, List, Optional, Tuple, Type, Union, ClassVar

import redis.asyncio as aioredis
from loguru import logger


class RedisConnPoolFromConfig:
    """
    基于环境配置表的Redis连接管理器(单例)。

    客户端与错误按四层坐标缓存：project_id -> env_name -> config_name -> database_name。
    其中database_name表示Redis库编号。
    """

    __private_instance: ClassVar[Optional["RedisConnPoolFromConfig"]] = None
    __private_initialized: ClassVar[bool] = False

    def __new__(cls, *args: Any, **kwargs: Any) -> "RedisConnPoolFromConfig":
        if cls.__private_instance is None:
            cls.__private_instance = super().__new__(cls)
        return cls.__private_instance

    def __init__(self, config_model: Optional[Type[Any]], logger: Any = logger) -> None:
        """
        初始化单例；重复构造时直接跳过。

        :param config_model: Tortoise环境配置模型类
        :param logger: 日志记录器，默认loguru.logger
        """
        if type(self).__private_initialized:
            return
        super().__init__()
        type(self).__private_initialized = True
        self.logger: Any = logger
        self.config_model: Optional[Type[Any]] = config_model
        self.clients: Dict[int, Dict[str, Dict[str, Dict[str, Any]]]] = {}
        self.errors: Dict[int, Dict[str, Dict[str, Dict[str, str]]]] = {}

    @staticmethod
    def _normalize_cache_key(
            project_id: Union[int, str],
            env_name: str,
            config_name: str,
            database_name: str,
    ) -> Tuple[int, str, str, str]:
        """
        规范化四层缓存坐标：应用ID转整数，名称类字段去空白并转小写。

        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param database_name: Redis库编号
        :return: (project_id, env_name, config_name, database_name)
        """
        try:
            project_id = int(str(project_id).strip())
        except (TypeError, ValueError) as e:
            raise ValueError(f"应用ID不合法: {project_id!r}") from e
        env_name = (env_name or "").strip().lower()
        config_name = (config_name or "").strip().lower()
        database_name = (database_name or "").strip().lower()
        if project_id <= 0 or not env_name or not config_name or not database_name:
            raise ValueError("应用ID、环境名称、配置名称、Redis库编号均不能为空")
        return project_id, env_name, config_name, database_name

    async def _load_env_config(
            self,
            project_id: int,
            env_name: str,
            config_name: str,
    ) -> Optional[Any]:
        """
        从自动化环境配置表加载Redis配置行。

        解析路径：环境枚举(env_name) -> 环境绑定(project_id+env_type=redis) -> 配置行。
        配置表唯一键为(env_bind, config_name)，故按config_name加载；
        Redis库编号由调用方database_name提供，不从配置行二次推断。

        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :return: 配置表ORM对象；未找到为None
        """
        if not self.config_model:
            raise ValueError("未提供ORM模型，请通过config_model参数传入")

        try:
            # 必须与Tortoise初始化时注册的模块路径一致，否则模型无default_connection
            from backend.applications.aotutest.models.autotest_model import (
                AutoTestApiEnvInfo,
                AutoTestApiEnvBindInfo,
            )
            from backend.enums import AutoTestConfigNodeType
        except ImportError as e:
            error_message = f"无法导入自动化测试环境模型或枚举: {e}"
            self.logger.error(error_message)
            raise RuntimeError(error_message) from e

        # AutoTestApiEnvInfo主键对外语义为env_enum_id
        env_enum_ids = await AutoTestApiEnvInfo.filter(
            env_name__iexact=env_name,
            state__not=1,
        ).values_list("id", flat=True)
        if not env_enum_ids:
            self.logger.warning(f"未找到环境枚举 env_name(忽略大小写)={env_name!r}")
            return None

        # 必须带project_id与env_type，避免多应用同名环境或跨节点类型串配置
        env_bind = await AutoTestApiEnvBindInfo.filter(
            project_id=project_id,
            env_enum_id__in=list(env_enum_ids),
            env_type=AutoTestConfigNodeType.REDIS,
            state__not=1,
        ).first()
        if not env_bind:
            self.logger.warning(
                f"未找到环境绑定 project_id={project_id}, "
                f"env_name(忽略大小写)={env_name!r}, env_type={AutoTestConfigNodeType.REDIS.value}"
            )
            return None

        return await self.config_model.filter(
            env_bind_id=env_bind.id,
            state__not=1,
            config_name__iexact=config_name,
        ).first()

    def _set_client(
            self,
            project_id: int,
            env_name: str,
            config_name: str,
            database_name: str,
            client: Any,
    ) -> None:
        """写入四层Redis客户端缓存。"""
        self.clients.setdefault(project_id, {}).setdefault(env_name, {}).setdefault(config_name, {})[
            database_name
        ] = client

    def _set_error(
            self,
            project_id: int,
            env_name: str,
            config_name: str,
            database_name: str,
            error_message: str,
    ) -> None:
        """写入四层建连错误缓存。"""
        self.errors.setdefault(project_id, {}).setdefault(env_name, {}).setdefault(config_name, {})[
            database_name
        ] = error_message

    def _clear_error(
            self,
            project_id: int,
            env_name: str,
            config_name: str,
            database_name: str,
    ) -> None:
        """清除指定坐标的建连错误记录。"""
        try:
            del self.errors[project_id][env_name][config_name][database_name]
        except KeyError:
            pass

    def _get_client(
            self,
            project_id: int,
            env_name: str,
            config_name: str,
            database_name: str,
    ) -> Optional[Any]:
        """读取已缓存的Redis客户端。"""
        try:
            return self.clients[project_id][env_name][config_name][database_name]
        except KeyError:
            return None

    async def create_client(
            self,
            project_id: Union[int, str],
            env_name: str,
            config_name: str,
            database_name: str,
            max_retries: int = 3,
    ) -> bool:
        """
        按配置创建Redis客户端；已存在则不重复创建。

        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param database_name: Redis库编号
        :param max_retries: 建连失败重试次数
        :return: 新建成功为True；客户端已存在为False
        """
        cache_project_id, cache_env_name, cache_config_name, cache_database_name = (
            self._normalize_cache_key(project_id, env_name, config_name, database_name)
        )
        if self._get_client(cache_project_id, cache_env_name, cache_config_name, cache_database_name):
            return False

        if max_retries <= 0:
            raise ValueError(f"建连重试次数非法: max_retries={max_retries}")

        try:
            redis_db = int(cache_database_name)
        except (TypeError, ValueError) as e:
            error_message = f"Redis库编号非法: {cache_database_name!r}"
            self.logger.error(error_message)
            self._set_error(
                cache_project_id, cache_env_name, cache_config_name, cache_database_name, error_message
            )
            raise ValueError(error_message) from e
        if redis_db < 0:
            error_message = f"Redis库编号不能为负数: {redis_db}"
            self.logger.error(error_message)
            self._set_error(
                cache_project_id, cache_env_name, cache_config_name, cache_database_name, error_message
            )
            raise ValueError(error_message)

        try:
            config_row = await self._load_env_config(
                cache_project_id, cache_env_name, cache_config_name
            )
            if not config_row:
                error_message = (
                    f"配置表未找到Redis记录 [project_id={cache_project_id}, "
                    f"env_name={cache_env_name!r}, config_name={cache_config_name!r}]"
                )
                self.logger.error(error_message)
                self._set_error(
                    cache_project_id, cache_env_name, cache_config_name, cache_database_name, error_message
                )
                raise ValueError(error_message)
        except (ValueError, RuntimeError):
            raise
        except Exception as e:
            error_message = f"查询Redis配置失败：{e}"
            self.logger.error(f"{error_message}\n{traceback.format_exc()}")
            self._set_error(
                cache_project_id, cache_env_name, cache_config_name, cache_database_name, error_message
            )
            raise RuntimeError(error_message) from e

        # 直接读取配置表字段；库编号使用调用方database_name，不做host/port二次映射
        config_host: str = (config_row.config_host or "").strip()
        config_username: Optional[str] = (config_row.config_username or "").strip() or None
        config_password: Optional[str] = (config_row.config_password or "").strip() or None
        config_port_text: str = str(config_row.config_port or "").strip()

        missing_fields = [
            field_name
            for field_name, field_value in (
                ("config_host", config_host),
                ("config_port", config_port_text),
            )
            if not field_value
        ]
        if missing_fields:
            error_message = f"Redis配置缺少必填字段：{missing_fields}"
            self.logger.error(error_message)
            self._set_error(
                cache_project_id, cache_env_name, cache_config_name, cache_database_name, error_message
            )
            raise ValueError(error_message)

        try:
            config_port: int = int(config_port_text)
        except (TypeError, ValueError) as e:
            error_message = f"配置端口非法: {config_row.config_port!r}"
            self.logger.error(error_message)
            self._set_error(
                cache_project_id, cache_env_name, cache_config_name, cache_database_name, error_message
            )
            raise ValueError(error_message) from e

        last_error_detail: str = ""
        for retry_index in range(max_retries):
            try:
                client = aioredis.Redis(
                    host=config_host,
                    port=config_port,
                    username=config_username,
                    password=config_password,
                    db=redis_db,
                    decode_responses=True,
                )
                await client.ping()
                self._set_client(
                    cache_project_id, cache_env_name, cache_config_name, cache_database_name, client
                )
                self._clear_error(
                    cache_project_id, cache_env_name, cache_config_name, cache_database_name
                )
                self.logger.info(
                    f"Redis连接创建成功 "
                    f"[project_id={cache_project_id}, env_name={cache_env_name}, "
                    f"config_name={cache_config_name}, database_name={cache_database_name}]"
                )
                return True
            except Exception as e:
                last_error_detail = str(e)
                if retry_index < max_retries - 1:
                    self.logger.warning(
                        f"Redis连接失败，{retry_index + 1}/{max_retries}次重试：{last_error_detail}"
                    )
                    await asyncio.sleep(2)

        error_message = f"Redis连接失败：{last_error_detail}"
        self.logger.error(error_message)
        self._set_error(
            cache_project_id, cache_env_name, cache_config_name, cache_database_name, error_message
        )
        raise ConnectionError(error_message)

    async def get_or_create_client(
            self,
            project_id: Union[int, str],
            env_name: str,
            config_name: str,
            database_name: str,
    ) -> Any:
        """
        获取已有Redis客户端；不存在则按配置表创建后返回。

        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param database_name: Redis库编号
        :return: redis.asyncio客户端实例
        """
        cache_project_id, cache_env_name, cache_config_name, cache_database_name = (
            self._normalize_cache_key(project_id, env_name, config_name, database_name)
        )
        client = self._get_client(
            cache_project_id, cache_env_name, cache_config_name, cache_database_name
        )
        if client:
            return client

        await self.create_client(
            cache_project_id, cache_env_name, cache_config_name, cache_database_name
        )
        client = self._get_client(
            cache_project_id, cache_env_name, cache_config_name, cache_database_name
        )
        if client:
            return client

        error_message = (
                self.errors.get(cache_project_id, {})
                .get(cache_env_name, {})
                .get(cache_config_name, {})
                .get(cache_database_name)
                or "未知错误"
        )
        raise ConnectionError(f"Redis连接创建失败：{error_message}")

    @staticmethod
    def _parse_redis_commands(expr: str) -> List[List[str]]:
        """
        将多行Redis命令文本解析为参数列表。

        :param expr: 命令文本，支持#注释行与shlex分词
        :return: 每条命令的参数列表，如[["GET", "key"]]
        """
        commands: List[List[str]] = []
        for raw_line in (expr or "").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                parts = shlex.split(line)
            except ValueError:
                parts = line.split()
            if parts:
                commands.append(parts)
        return commands

    @staticmethod
    def _normalize_result(value: Any) -> Any:
        """
        将Redis返回值规范化为可JSON序列化结构。

        :param value: 原始返回值
        :return: 规范化后的标量、列表或字典
        """
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, (list, tuple)):
            return [RedisConnPoolFromConfig._normalize_result(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): RedisConnPoolFromConfig._normalize_result(item)
                for key, item in value.items()
            }
        return str(value)

    async def execute_commands(self, client: Any, expr: str) -> Dict[str, Any]:
        """
        在指定客户端上顺序执行多条Redis命令。

        :param client: redis.asyncio客户端实例
        :param expr: 多行命令文本
        :return: {"redis_data": 结果列表, "redis_count": 结果条数}
        """
        if not client:
            raise ValueError("缺少Redis连接对象")
        commands = self._parse_redis_commands(expr)
        if not commands:
            raise ValueError("Redis命令不能为空")

        command_results: List[Any] = []
        for parts in commands:
            command_name = parts[0].upper()
            command_args = parts[1:]
            result = await client.execute_command(command_name, *command_args)
            normalized_result = self._normalize_result(result)
            if isinstance(normalized_result, list):
                command_results.extend(normalized_result)
            else:
                command_results.append(normalized_result)

        return {
            "redis_data": command_results,
            "redis_count": len(command_results),
        }


def get_app_redis_pool() -> "RedisConnPoolFromConfig":
    """
    返回绑定自动化环境配置表的Redis连接管理单例。

    :return: RedisConnPoolFromConfig单例
    """
    from backend.applications.aotutest.models.autotest_model import AutoTestApiEnvConfigInfo

    return RedisConnPoolFromConfig(config_model=AutoTestApiEnvConfigInfo)
