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
from typing import Any, Dict, List, Optional, Set, Type

import redis.asyncio as aioredis
from loguru import logger


class RedisConnPoolFromConfig:
    """
    基于自动化环境配置表的Redis连接管理器（单例）。

    连接与错误按四层键缓存：app_id -> env -> config_name -> db_name。
    """

    __private_instance = None
    __private_initialized = False

    def __new__(cls, *args, **kwargs) -> object:
        """
        创建或返回单例实例。

        :return: RedisConnPoolFromConfig单例
        """
        if cls.__private_instance is None and cls.__private_initialized is False:
            cls.__private_instance = super().__new__(cls)
        return cls.__private_instance

    def __init__(self, config_model: Optional[Type], logger=logger):
        """
        初始化单例；重复构造时直接跳过。

        :param config_model: Tortoise环境配置模型类
        :param logger: 日志记录器，默认loguru.logger
        """
        if self.__private_initialized:
            return
        super().__init__()
        self.__private_initialized = True
        self.logger = logger
        self.config_model = config_model
        self.clients: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = {}
        self.errors: Dict[str, Dict[str, Dict[str, Dict[str, str]]]] = {}

    def _config_model_field_names(self) -> Set[str]:
        """
        读取config_model的Tortoise字段名集合。

        :return: 字段名集合；模型无效时为空集合
        """
        meta = getattr(self.config_model, "_meta", None)
        if not meta or not getattr(meta, "fields_map", None):
            return set()
        return set(meta.fields_map.keys())

    async def _get_redis_config_from_orm(
            self,
            app_id: int,
            env: str,
            config_name: str,
            db_name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        从环境配置表读取Redis连接参数。

        :param app_id: 应用主键ID，对应project_id
        :param env: 环境名称，忽略大小写匹配
        :param config_name: 配置名称，忽略大小写匹配
        :param db_name: Redis库序号或database_name
        :return: 含host/port/username/password/db_index的字典；未找到时为None
        :raises ValueError: 未提供config_model或模型字段无法识别
        """
        if not self.config_model:
            raise ValueError("未提供ORM模型，请通过config_model参数传入")

        try:
            app_id_int = int(str(app_id).strip())
        except (TypeError, ValueError) as e:
            self.logger.error(f"app_id 无法解析为整数: {app_id!r}, {e}")
            return None

        field_names = self._config_model_field_names()
        if "project_id" not in field_names or "env_id" not in field_names:
            raise ValueError(
                f"config_model={getattr(self.config_model, '__name__', self.config_model)} "
                f"字段无法识别为 Autotest(project_id+env_id)"
            )

        try:
            from applications.aotutest.models.autotest_model import AutoTestApiEnvEnumInfo
            from enums import AutoTestConfigNodeType
        except ImportError as e:
            self.logger.error(f"无法导入自动化测试环境模型或枚举: {e}")
            return None

        env_row = await AutoTestApiEnvEnumInfo.filter(
            project_id=app_id_int,
            env_name__iexact=env,
        ).filter(state__not=1).first()
        if not env_row:
            self.logger.warning(
                f"未找到环境 project_id={app_id_int}, env_name(忽略大小写)={env!r}"
            )
            return None

        qs = self.config_model.filter(
            project_id=app_id_int,
            env_id=env_row.id,
        ).filter(state__not=1)
        if "config_type" in field_names:
            qs = qs.filter(config_type=AutoTestConfigNodeType.REDIS.value)
        config_obj = await qs.filter(
            config_name__iexact=config_name,
            database_name__iexact=db_name,
        ).first()
        if not config_obj:
            config_obj = await qs.filter(config_name__iexact=config_name).first()
        if not config_obj:
            return None

        port_raw = getattr(config_obj, "config_port", None) or "6379"
        try:
            port = int(str(port_raw).strip())
        except (TypeError, ValueError):
            port = 6379

        db_index_raw = db_name or getattr(config_obj, "database_name", None) or "0"
        try:
            db_index = int(str(db_index_raw).strip())
        except (TypeError, ValueError):
            db_index = 0

        return {
            "host": getattr(config_obj, "config_host", None),
            "port": port,
            "username": getattr(config_obj, "config_username", None) or None,
            "password": getattr(config_obj, "config_password", None) or "",
            "db_index": db_index,
        }

    def _set_client(self, app_id: str, env: str, config_name: str, db_name: str, client: Any):
        """
        缓存已建立的Redis客户端。

        :param app_id: 应用ID缓存键
        :param env: 环境名称缓存键
        :param config_name: 配置名称缓存键
        :param db_name: 库序号缓存键
        :param client: redis.asyncio客户端实例
        """
        if app_id not in self.clients:
            self.clients[app_id] = {}
        if env not in self.clients[app_id]:
            self.clients[app_id][env] = {}
        if config_name not in self.clients[app_id][env]:
            self.clients[app_id][env][config_name] = {}
        self.clients[app_id][env][config_name][db_name] = client

    def _set_error(self, app_id: str, env: str, config_name: str, db_name: str, error_msg: str):
        """
        记录指定四层键下的连接错误信息。

        :param app_id: 应用ID缓存键
        :param env: 环境名称缓存键
        :param config_name: 配置名称缓存键
        :param db_name: 库序号缓存键
        :param error_msg: 错误描述
        """
        if app_id not in self.errors:
            self.errors[app_id] = {}
        if env not in self.errors[app_id]:
            self.errors[app_id][env] = {}
        if config_name not in self.errors[app_id][env]:
            self.errors[app_id][env][config_name] = {}
        self.errors[app_id][env][config_name][db_name] = error_msg

    def _clear_error(self, app_id: str, env: str, config_name: str, db_name: str):
        """
        清除指定四层键下的连接错误信息。

        :param app_id: 应用ID缓存键
        :param env: 环境名称缓存键
        :param config_name: 配置名称缓存键
        :param db_name: 库序号缓存键
        """
        try:
            del self.errors[app_id][env][config_name][db_name]
        except KeyError:
            pass

    def _get_client(self, app_id: str, env: str, config_name: str, db_name: str) -> Optional[Any]:
        """
        按四层键获取已缓存的Redis客户端。

        :param app_id: 应用ID缓存键
        :param env: 环境名称缓存键
        :param config_name: 配置名称缓存键
        :param db_name: 库序号缓存键
        :return: 客户端实例；未缓存时为None
        """
        try:
            return self.clients[app_id][env][config_name][db_name]
        except KeyError:
            return None

    async def connection(self, app_id: str, env: str, config_name: str, db_name: str, max_retries: int = 3) -> bool:
        """
        创建并缓存Redis连接；已存在同键连接时直接返回False。

        :param app_id: 应用主键ID
        :param env: 环境名称
        :param config_name: 配置名称
        :param db_name: Redis库序号，缺省按0处理
        :param max_retries: 建连失败时的最大重试次数
        :return: 新创建连接为True；连接已存在为False
        :raises ValueError: app_id/env/config_name为空
        :raises Exception: 配置缺失或字段不完整
        :raises ConnectionError: 重试耗尽后仍无法连接
        """
        if not all([app_id, env, config_name]):
            err_msg = "应用ID、环境、配置名称均不能为空"
            self.logger.error(err_msg)
            raise ValueError(err_msg)

        app_id_key = app_id.strip()
        env_clean = env.lower().strip()
        config_clean = config_name.lower().strip()
        db_clean = (db_name or "0").lower().strip()

        existing = self._get_client(app_id_key, env_clean, config_clean, db_clean)
        if existing:
            return False

        try:
            config = await self._get_redis_config_from_orm(app_id_key, env_clean, config_clean, db_clean)
            if not config:
                err_msg = (
                    f"配置表未找到Redis记录 [app_id={app_id!r}, env={env_clean!r}, "
                    f"config_name={config_clean!r}, database/db_index={db_clean!r}]"
                )
                self.logger.error(err_msg)
                self._set_error(app_id_key, env_clean, config_clean, db_clean, err_msg)
                raise Exception(err_msg)
            if not config.get("host"):
                err_msg = "Redis配置缺少必填字段：host"
                self._set_error(app_id_key, env_clean, config_clean, db_clean, err_msg)
                raise Exception(err_msg)
        except Exception:
            raise

        for retry in range(max_retries):
            try:
                client = aioredis.Redis(
                    host=config["host"],
                    port=config["port"],
                    username=config.get("username") or None,
                    password=config.get("password") or None,
                    db=config.get("db_index", 0),
                    decode_responses=True,
                )
                await client.ping()
                self._set_client(app_id_key, env_clean, config_clean, db_clean, client)
                self._clear_error(app_id_key, env_clean, config_clean, db_clean)
                self.logger.info("Redis连接创建成功")
                return True
            except Exception as e:
                if retry < max_retries - 1:
                    self.logger.warning(f"Redis连接失败，{retry + 1}/{max_retries}次重试：{e}")
                    await asyncio.sleep(2)
                    continue
                err_msg = f"Redis连接失败，错误信息：{e}"
                self.logger.error(err_msg)
                self._set_error(app_id_key, env_clean, config_clean, db_clean, err_msg)
                raise ConnectionError(err_msg) from e
        return False

    async def get_or_create_client(self, app_id: str, env: str, config_name: str, db_name: str) -> Any:
        """
        获取已缓存客户端；不存在时先建连再返回。

        :param app_id: 应用主键ID
        :param env: 环境名称
        :param config_name: 配置名称
        :param db_name: Redis库序号，缺省按0处理
        :return: redis.asyncio客户端实例
        :raises ConnectionError: 建连失败或缓存中仍无客户端
        """
        app_id_key = app_id.strip()
        env_clean = env.lower().strip()
        config_clean = config_name.lower().strip()
        db_clean = (db_name or "0").lower().strip()

        client = self._get_client(app_id_key, env_clean, config_clean, db_clean)
        if client:
            return client

        await self.connection(app_id, env, config_name, db_name or "0")
        client = self._get_client(app_id_key, env_clean, config_clean, db_clean)
        if client:
            return client

        err_msg = self.errors.get(app_id_key, {}).get(env_clean, {}).get(config_clean, {}).get(db_clean)
        raise ConnectionError(f"Redis连接创建失败，错误信息：{err_msg}")

    @staticmethod
    def parse_redis_commands(expr: str) -> List[List[str]]:
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
            return [RedisConnPoolFromConfig._normalize_result(v) for v in value]
        if isinstance(value, dict):
            return {str(k): RedisConnPoolFromConfig._normalize_result(v) for k, v in value.items()}
        return str(value)

    async def execute_commands(self, client: Any, expr: str) -> Dict[str, Any]:
        """
        在指定客户端上顺序执行多条Redis命令。

        :param client: redis.asyncio客户端实例
        :param expr: 多行命令文本
        :return: 含redis_data与redis_count的结果字典
        :raises ValueError: 客户端为空或命令文本为空
        """
        if not client:
            raise ValueError("缺少Redis连接对象，请检查")
        commands = self.parse_redis_commands(expr)
        if not commands:
            raise ValueError("Redis命令不能为空")

        command_results: List[Any] = []
        for parts in commands:
            cmd = parts[0].upper()
            args = parts[1:]
            result = await client.execute_command(cmd, *args)
            if isinstance(self._normalize_result(result), list):
                command_results.extend(result)
            else:
                command_results.append(result)

        return {
            "redis_data": command_results,
            "redis_count": len(command_results),
        }


def get_app_redis_pool() -> "RedisConnPoolFromConfig":
    """
    获取绑定AutoTestApiEnvConfigInfo的Redis连接管理单例。

    :return: RedisConnPoolFromConfig实例
    """
    from backend.applications.aotutest.models.autotest_model import AutoTestApiEnvConfigInfo

    return RedisConnPoolFromConfig(config_model=AutoTestApiEnvConfigInfo)
