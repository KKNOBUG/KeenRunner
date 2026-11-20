# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
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
        # 建连串行锁：懒创建并绑定当前事件循环，Celery prefork换新loop后自动重建
        self._create_lock: Optional[asyncio.Lock] = None
        self._create_lock_loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_create_lock(self) -> asyncio.Lock:
        """
        获取建连串行锁；事件循环变化时重建，避免跨loop使用旧锁。

        Celery worker_process_init会重置IO池换新loop，沿用旧loop的Lock会报
        "attached to a different loop"；按当前running loop判定重建。

        :return: 绑定当前事件循环的asyncio.Lock
        """
        current_loop = asyncio.get_running_loop()
        if self._create_lock is None or self._create_lock_loop is not current_loop:
            self._create_lock = asyncio.Lock()
            self._create_lock_loop = current_loop
        return self._create_lock

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

    @staticmethod
    def _normalize_mode_cache_key(
            project_id: Union[int, str],
            env_id: int,
            config_mode: str,
            database_name: str,
            config_host: Union[int, str],
            config_port: Union[int, str],
    ) -> Tuple[int, str, str, str]:
        """
        规范化按逻辑标识建连的四层缓存坐标。

        第二层用 env{env_id}@{host}:{port} 替代环境名称：主机/端口参与缓存键，
        配置改地址后命中新键立即生效，旧客户端由 close 回收；主机/端口为空时交由建连校验拦截。

        :param project_id: 应用主键ID
        :param env_id: 环境绑定ID
        :param config_mode: 配置逻辑标识
        :param database_name: Redis库编号
        :param config_host: 配置主机（执行解析快照）
        :param config_port: 配置端口（执行解析快照）
        :return: (project_id, env{env_id}@{host}:{port}, config_mode, database_name)
        """
        try:
            cache_project_id = int(str(project_id).strip())
        except (TypeError, ValueError) as e:
            raise ValueError(f"应用ID不合法: {project_id!r}") from e
        try:
            cache_env_id = int(str(env_id).strip())
        except (TypeError, ValueError) as e:
            raise ValueError(f"环境绑定ID不合法: {env_id!r}") from e
        # host/port 来源可能是配置表原始值（int 端口）或解析快照（str），统一先转字符串再归一
        env_host: str = str(config_host).strip().lower() if config_host not in (None, "") else ""
        env_port: str = str(config_port).strip() if config_port not in (None, "") else ""
        env_key: str = f"env{cache_env_id}@{env_host}:{env_port}"
        config_mode = (config_mode or "").strip()
        database_name = (database_name or "").strip().lower()
        if cache_project_id <= 0 or cache_env_id <= 0 or not config_mode or not database_name:
            raise ValueError("应用ID、环境绑定ID、配置逻辑标识、Redis库编号均不能为空")
        return cache_project_id, env_key, config_mode, database_name

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
            from backend.applications.autotest.models.autotest_env_config_model import AutoTestEnvBindModel
            from backend.applications.autotest.models.autotest_env_model import AutoTestEnvModel
            from backend.enums import AutoTestConfigNodeType
        except ImportError as e:
            error_message = f"无法导入自动化测试环境模型或枚举: {e}"
            self.logger.error(error_message)
            raise RuntimeError(error_message) from e

        # AutoTestEnvModel主键对外语义为env_enum_id
        env_enum_ids = await AutoTestEnvModel.filter(env_name__iexact=env_name).values_list("id", flat=True)
        if not env_enum_ids:
            self.logger.warning(f"未找到环境枚举 env_name(忽略大小写)={env_name!r}")
            return None

        # 必须带project_id与env_type，避免多应用同名环境或跨节点类型串配置
        env_bind = await AutoTestEnvBindModel.filter(
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

    async def _load_env_config_by_mode(
            self,
            project_id: int,
            env_id: int,
            config_mode: str,
    ) -> Optional[Any]:
        """
        按逻辑标识加载Redis配置行。

        解析路径：环境绑定(env_id + project_id + env_type=redis) -> 配置行(config_mode)。
        config_mode 在同应用同节点内唯一，可精确命中；库编号由调用方提供，不从配置行二次推断。

        :param project_id: 应用主键ID
        :param env_id: 环境绑定ID
        :param config_mode: 配置逻辑标识
        :return: 配置表ORM对象；未找到为None
        """
        if not self.config_model:
            raise ValueError("未提供ORM模型，请通过config_model参数传入")

        try:
            # 必须与Tortoise初始化时注册的模块路径一致，否则模型无default_connection
            from backend.applications.autotest.models.autotest_env_config_model import AutoTestEnvBindModel
            from backend.enums import AutoTestConfigNodeType
        except ImportError as e:
            error_message = f"无法导入自动化测试环境模型或枚举: {e}"
            self.logger.error(error_message)
            raise RuntimeError(error_message) from e

        env_bind = await AutoTestEnvBindModel.filter(
            id=env_id,
            project_id=project_id,
            env_type=AutoTestConfigNodeType.REDIS,
            state__not=1,
        ).first()
        if not env_bind:
            self.logger.warning(
                f"未找到环境绑定 project_id={project_id}, env_id={env_id}, "
                f"env_type={AutoTestConfigNodeType.REDIS.value}"
            )
            return None

        config_row = await self.config_model.filter(
            env_bind_id=env_bind.id,
            state__not=1,
            config_mode=config_mode,
        ).first()
        if not config_row:
            self.logger.warning(f"未找到Redis配置 env_id={env_id}, config_mode={config_mode!r}")
            return None
        return config_row

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
        cache_key: Tuple[int, str, str, str] = self._normalize_cache_key(
            project_id, env_name, config_name, database_name
        )
        if self._get_client(*cache_key):
            return False

        if max_retries <= 0:
            raise ValueError(f"建连重试次数非法: max_retries={max_retries}")

        try:
            redis_db = int(cache_key[3])
        except (TypeError, ValueError) as e:
            error_message = f"Redis库编号非法: {cache_key[3]!r}"
            self.logger.error(error_message)
            self._set_error(*cache_key, error_message)
            raise ValueError(error_message) from e
        if redis_db < 0:
            error_message = f"Redis库编号不能为负数: {redis_db}"
            self.logger.error(error_message)
            self._set_error(*cache_key, error_message)
            raise ValueError(error_message)

        try:
            config_row = await self._load_env_config(cache_key[0], cache_key[1], cache_key[2])
            if not config_row:
                error_message = (
                    f"配置表未找到Redis记录 [project_id={cache_key[0]}, "
                    f"env_name={cache_key[1]!r}, config_name={cache_key[2]!r}]"
                )
                self.logger.error(error_message)
                self._set_error(*cache_key, error_message)
                raise ValueError(error_message)
        except (ValueError, RuntimeError):
            raise
        except Exception as e:
            error_message = f"查询Redis配置失败：{e}"
            self.logger.error(f"{error_message}\n{traceback.format_exc()}")
            self._set_error(*cache_key, error_message)
            raise RuntimeError(error_message) from e

        return await self._build_client_from_config_row(cache_key, redis_db, config_row, max_retries)

    async def _build_client_from_config_row(
            self,
            cache_key: Tuple[int, str, str, str],
            redis_db: int,
            config_row: Any,
            max_retries: int,
    ) -> bool:
        """
        按已加载的配置行建连并写入缓存（名称版与逻辑标识版共用）。

        :param cache_key: 规范化四层缓存坐标
        :param redis_db: Redis库编号
        :param config_row: 环境配置表ORM对象
        :param max_retries: 建连失败重试次数
        :return: 新建成功为True
        """
        cache_project_id, cache_env_name, cache_config_name, cache_database_name = cache_key

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

    async def create_client_by_mode(
            self,
            project_id: Union[int, str],
            env_id: int,
            config_mode: str,
            database_name: str,
            config_host: str,
            config_port: str,
            max_retries: int = 3,
    ) -> bool:
        """
        按配置逻辑标识创建Redis客户端；已存在则不重复创建。

        :param project_id: 应用主键ID
        :param env_id: 环境绑定ID
        :param config_mode: 配置逻辑标识
        :param database_name: Redis库编号
        :param config_host: 配置主机（执行解析快照，参与缓存键）
        :param config_port: 配置端口（执行解析快照，参与缓存键）
        :param max_retries: 建连失败重试次数
        :return: 新建成功为True；客户端已存在为False
        """
        cache_key: Tuple[int, str, str, str] = self._normalize_mode_cache_key(
            project_id, env_id, config_mode, database_name, config_host, config_port
        )
        if self._get_client(*cache_key):
            return False

        if max_retries <= 0:
            raise ValueError(f"建连重试次数非法: max_retries={max_retries}")

        try:
            redis_db = int(cache_key[3])
        except (TypeError, ValueError) as e:
            error_message = f"Redis库编号非法: {cache_key[3]!r}"
            self.logger.error(error_message)
            self._set_error(*cache_key, error_message)
            raise ValueError(error_message) from e
        if redis_db < 0:
            error_message = f"Redis库编号不能为负数: {redis_db}"
            self.logger.error(error_message)
            self._set_error(*cache_key, error_message)
            raise ValueError(error_message)

        try:
            config_row = await self._load_env_config_by_mode(cache_key[0], env_id, config_mode)
            if not config_row:
                error_message = (
                    f"配置表未找到Redis记录 [project_id={cache_key[0]}, env_id={env_id}, "
                    f"config_mode={config_mode!r}]"
                )
                self.logger.error(error_message)
                self._set_error(*cache_key, error_message)
                raise ValueError(error_message)
        except (ValueError, RuntimeError):
            raise
        except Exception as e:
            error_message = f"查询Redis配置失败：{e}"
            self.logger.error(f"{error_message}\n{traceback.format_exc()}")
            self._set_error(*cache_key, error_message)
            raise RuntimeError(error_message) from e

        created = await self._build_client_from_config_row(cache_key, redis_db, config_row, max_retries)
        if created:
            # 改地址后旧键客户端不再被命中，空闲时淘汰，避免连接泄漏
            await self._evict_superseded_mode_clients(cache_key)
        return created

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

        # 串行建连：并发请求下check-then-create会重复建连互相覆盖，锁内double-check兜底
        async with self._get_create_lock():
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

    async def get_or_create_client_by_mode(
            self,
            project_id: Union[int, str],
            env_id: int,
            config_mode: str,
            database_name: str,
            config_host: str,
            config_port: str,
    ) -> Any:
        """
        获取已有Redis客户端；不存在则按配置逻辑标识创建后返回。

        :param project_id: 应用主键ID
        :param env_id: 环境绑定ID
        :param config_mode: 配置逻辑标识
        :param database_name: Redis库编号
        :param config_host: 配置主机（执行解析快照，参与缓存键）
        :param config_port: 配置端口（执行解析快照，参与缓存键）
        :return: redis.asyncio客户端实例
        """
        cache_key: Tuple[int, str, str, str] = self._normalize_mode_cache_key(
            project_id, env_id, config_mode, database_name, config_host, config_port
        )
        client: Any = self._get_client(*cache_key)
        if client:
            return client

        # 串行建连：并发请求下check-then-create会重复建连互相覆盖，锁内double-check兜底
        async with self._get_create_lock():
            client = self._get_client(*cache_key)
            if client:
                return client
            await self.create_client_by_mode(
                project_id, env_id, config_mode, database_name, config_host, config_port
            )
        client = self._get_client(*cache_key)
        if client:
            return client

        error_message = (
                self.errors.get(cache_key[0], {})
                .get(cache_key[1], {})
                .get(cache_key[2], {})
                .get(cache_key[3])
                or "未知错误"
        )
        raise ConnectionError(f"Redis连接创建失败：{error_message}")

    async def _close_client(self, client: Any) -> None:
        """关闭单个Redis客户端，释放底层连接池。"""
        await client.aclose()

    @staticmethod
    def _client_busy(client: Any) -> bool:
        """
        判定客户端是否有在用连接；无法判定时保守视为忙，跳过淘汰。

        :param client: redis.asyncio客户端实例
        :return: 存在在用连接为True
        """
        connection_pool = getattr(client, "connection_pool", None)
        in_use = getattr(connection_pool, "_in_use_connections", None)
        if in_use is not None:
            return len(in_use) > 0
        return True

    async def _evict_superseded_mode_clients(self, cache_key: Tuple[int, str, str, str]) -> None:
        """
        淘汰同绑定同mode同库编号下被新地址取代的旧客户端（仅空闲时关闭）。

        缓存第二层为env{env_id}@{host}:{port}，配置改地址后新键建连成功，
        同env_id前缀的旧键客户端不再被命中；忙客户端保留待下次建连或关停时回收。
        淘汰失败不影响新客户端的可用性。

        :param cache_key: 新建客户端的规范化四层缓存坐标
        """
        project_id, env_key, config_mode, database_name = cache_key
        env_id_prefix = env_key.split("@", 1)[0]
        try:
            config_map = self.clients.get(project_id, {})
            for cached_env_key in list(config_map.keys()):
                if not cached_env_key.startswith(env_id_prefix + "@") or cached_env_key == env_key:
                    continue
                database_map = config_map.get(cached_env_key, {}).get(config_mode, {})
                old_client = database_map.get(database_name)
                if not old_client or self._client_busy(old_client):
                    continue
                del database_map[database_name]
                self.errors.get(project_id, {}).get(cached_env_key, {}).get(config_mode, {}).pop(
                    database_name, None
                )
                await self._close_client(old_client)
                self.logger.info(
                    f"配置地址变更，旧Redis客户端已淘汰: "
                    f"[project_id={project_id}/{cached_env_key}/{config_mode}/{database_name}]"
                )
        except Exception as e:
            self.logger.warning(f"旧Redis客户端淘汰失败(不影响新客户端使用): {e}")

    async def _close_project_clients(self, project_id: int) -> None:
        """关闭指定应用下全部Redis客户端；单客户端关闭失败不阻断其余回收。"""
        for env_name in list(self.clients.get(project_id, {}).keys()):
            for config_name in list(self.clients[project_id][env_name].keys()):
                for database_name, client in list(self.clients[project_id][env_name][config_name].items()):
                    try:
                        await self._close_client(client)
                    except Exception as e:
                        self.logger.warning(
                            f"Redis客户端关闭失败: [project_id={project_id}/{env_name}/{config_name}/{database_name}], {e}"
                        )
                        continue
                    self.logger.info(
                        f"Redis客户端已关闭: [project_id={project_id}/{env_name}/{config_name}/{database_name}]"
                    )

    async def close(self, project_id: Optional[Union[int, str]] = None) -> None:
        """
        关闭指定应用或全部Redis客户端，并清理对应错误记录。

        :param project_id: 应用主键ID；为空则关闭全部
        """
        if project_id is not None:
            try:
                project_id = int(str(project_id).strip())
            except (TypeError, ValueError) as e:
                raise ValueError(f"应用ID不合法: {project_id!r}") from e
            if project_id not in self.clients:
                return
            await self._close_project_clients(project_id)
            del self.clients[project_id]
            self.errors.pop(project_id, None)
            return

        for cached_project_id in list(self.clients.keys()):
            await self._close_project_clients(cached_project_id)
        self.clients.clear()
        self.errors.clear()

    async def close_coordinate(
            self,
            project_id: Union[int, str],
            env_name: str,
            config_name: str,
            database_name: str,
    ) -> None:
        """
        关闭单个四层坐标的Redis客户端并清理缓存与错误记录（测试连接即用即关）。

        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param database_name: Redis库编号
        """
        cache_key = self._normalize_cache_key(project_id, env_name, config_name, database_name)
        client = self._get_client(*cache_key)
        if not client:
            return
        try:
            del self.clients[cache_key[0]][cache_key[1]][cache_key[2]][cache_key[3]]
        except KeyError:
            pass
        self._clear_error(*cache_key)
        await self._close_client(client)
        self.logger.info(
            f"Redis客户端已关闭: [project_id={cache_key[0]}/{cache_key[1]}/{cache_key[2]}/{cache_key[3]}]"
        )

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
    from backend.applications.autotest.models.autotest_env_config_model import AutoTestEnvConfigModel

    return RedisConnPoolFromConfig(config_model=AutoTestEnvConfigModel)
