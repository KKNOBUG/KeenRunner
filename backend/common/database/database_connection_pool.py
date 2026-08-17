# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : database_connection_pool
@DateTime: 2026/4/21 14:33
"""
import asyncio
import os
import platform
import threading
import traceback
from datetime import date, time, datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, Any, Type, Tuple, Union, ClassVar

import aiomysql
import oracledb
import orjson
from loguru import logger

# 建池支持的数据库类型；TDSQL走MySQL协议
SUPPORTED_DB_TYPES: Tuple[str, ...] = ("mysql", "tdsql", "oracle")

# OracleClient模式进程内仅初始化一次，且必须在首次建连之前完成
_oracle_client_lock: threading.Lock = threading.Lock()
_oracle_client_inited: bool = False


def _ensure_oracle_client_mode() -> None:
    """
    首次创建Oracle连接池前初始化客户端模式。

    ORACLE_CLIENT_MODE仅允许thin/thick，空值按thick。
    thick可连11g/12.1/12.2+(须安装InstantClient；连11g建议Client19)。
    thin不兼容11g及部分12.1(DPY-3010)。进程内一旦建连不可再切换模式。
    """
    global _oracle_client_inited
    if _oracle_client_inited:
        return

    with _oracle_client_lock:
        if _oracle_client_inited:
            return
        if not oracledb.is_thin_mode():
            _oracle_client_inited = True
            return

        try:
            from backend.configure import PROJECT_CONFIG
            oracle_client_mode = (PROJECT_CONFIG.ORACLE_CLIENT_MODE or "").strip().lower()
            oracle_client_path = (PROJECT_CONFIG.ORACLE_CLIENT_PATH or "").strip()
        except Exception:
            oracle_client_mode = (os.environ.get("ORACLE_CLIENT_MODE") or "").strip().lower()
            oracle_client_path = (os.environ.get("ORACLE_CLIENT_PATH") or "").strip()

        if not oracle_client_mode:
            oracle_client_mode = "thick"
        if oracle_client_mode not in ("thin", "thick"):
            raise RuntimeError(f"ORACLE_CLIENT_MODE仅允许thin或thick，当前为: {oracle_client_mode!r}")
        if oracle_client_mode == "thin":
            _oracle_client_inited = True
            logger.warning(
                "[ORACLE]数据库使用thin模式连接时, 不兼容11g/12.1版本; "
                "若触发DPY-3010异常, 请设置ORACLE_CLIENT_MODE=thick并安装Oracle Instant Client。"
            )
            return

        init_kwargs: Dict[str, Any] = {}
        system_name: str = platform.system()
        if oracle_client_path:
            init_kwargs["lib_dir"] = oracle_client_path
        elif system_name in {"Darwin", "Windows"}:
            raise RuntimeError(
                f"[ORACLE]数据库使用thick模式连接失败，当前操作系统: {system_name}; "
                "请设置ORACLE_CLIENT_PATH指向Oracle Instant Client目录。"
            )

        try:
            oracledb.init_oracle_client(**init_kwargs)
            _oracle_client_inited = True
            logger.info(f"[ORACLE]数据库使用thin模式连接成功[PATH={oracle_client_path or "使用系统库搜索路径"}]")
        except Exception as exc:
            message: str = str(exc)
            if "DPI-2015" in message or "already been initialized" in message.lower():
                _oracle_client_inited = True
                return
            raise RuntimeError(
                f"[ORACLE]数据库使用thick模式连接失败，当前操作系统: {system_name}, {exc}"
                "请安装Oracle Instant Client并配置ORACLE_CLIENT_PATH(Linux可将库目录加入LD_LIBRARY_PATH); "
                "连接11g需使用Instant Client 19；Client 21仅支持DB12.1+，Client 23仅支持DB19+。"
            ) from exc


def _build_oracle_dsn(config_host: str, config_port: int, database_name: str) -> str:
    """
    构造Oracle DSN；database_name默认按service_name；以sid:前缀开头则按SID建连(常见于11g)。
    """
    database_name = (database_name or "").strip()
    if not database_name:
        raise ValueError("Oracle数据库名称不能为空")
    if database_name.lower().startswith("sid:"):
        sid: str = database_name.split(":", 1)[1].strip()
        if not sid:
            raise ValueError("Oracle SID不能为空，格式示例: sid:ORCL")
        return oracledb.makedsn(config_host, config_port, sid=sid)
    return oracledb.makedsn(config_host, config_port, service_name=database_name)


class DBConnPoolFromConfig:
    """
    基于环境配置表的数据库连接池管理器(单例)。

    池与错误按四层坐标缓存：project_id -> env_name -> config_name -> database_name。
    """

    __private_instance: ClassVar[Optional["DBConnPoolFromConfig"]] = None
    __private_initialized: ClassVar[bool] = False

    def __new__(cls, *args: Any, **kwargs: Any) -> "DBConnPoolFromConfig":
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
        self.pools: Dict[int, Dict[str, Dict[str, Dict[str, Any]]]] = {}
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
        :param database_name: 数据库名
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
            raise ValueError("应用ID、环境名称、配置名称、数据库名称均不能为空")
        return project_id, env_name, config_name, database_name

    async def _load_env_config(
            self,
            project_id: int,
            env_name: str,
            config_name: str,
            database_name: str,
    ) -> Optional[Any]:
        """
        从自动化环境配置表加载配置行。

        解析路径：环境枚举(env_name) -> 环境绑定(project_id+env_type=database) -> 配置行。

        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param database_name: 数据库名
        :return: 配置表ORM对象；未找到为None
        """
        if not self.config_model:
            raise ValueError("未提供ORM模型，请通过config_model参数传入")

        try:
            # 必须与Tortoise初始化时注册的模块路径一致，否则模型无default_connection
            from backend.applications.aotutest.models.autotest_env_config_model import AutoTestEnvBindModel
            from backend.applications.aotutest.models.autotest_env_model import AutoTestEnvModel
            from backend.enums import AutoTestConfigNodeType
        except ImportError as e:
            error_message = f"无法导入自动化测试环境模型或枚举: {e}"
            self.logger.error(error_message)
            raise RuntimeError(error_message) from e

        # AutoTestEnvModel主键对外语义为env_enum_id
        env_enum_ids = await AutoTestEnvModel.filter(
            env_name__iexact=env_name,
            state__not=1,
        ).values_list("id", flat=True)
        if not env_enum_ids:
            self.logger.warning(f"未找到环境枚举 env_name(忽略大小写)={env_name!r}")
            return None

        # 必须带project_id与env_type，避免多应用同名环境或跨节点类型串库
        env_bind = await AutoTestEnvBindModel.filter(
            project_id=project_id,
            env_enum_id__in=list(env_enum_ids),
            env_type=AutoTestConfigNodeType.DB,
            state__not=1,
        ).first()
        if not env_bind:
            self.logger.warning(
                f"未找到环境绑定 project_id={project_id}, "
                f"env_name(忽略大小写)={env_name!r}, env_type={AutoTestConfigNodeType.DB.value}"
            )
            return None

        return await self.config_model.filter(
            env_bind_id=env_bind.id,
            state__not=1,
            config_name__iexact=config_name,
            database_name__iexact=database_name,
        ).first()

    def _set_pool(
            self,
            project_id: int,
            env_name: str,
            config_name: str,
            database_name: str,
            pool: Any,
    ) -> None:
        """写入四层连接池缓存。"""
        self.pools.setdefault(project_id, {}).setdefault(env_name, {}).setdefault(config_name, {})[
            database_name
        ] = pool

    def _set_error(
            self,
            project_id: int,
            env_name: str,
            config_name: str,
            database_name: str,
            error_message: str,
    ) -> None:
        """写入四层建池错误缓存。"""
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
        """清除指定坐标的建池错误记录。"""
        try:
            del self.errors[project_id][env_name][config_name][database_name]
        except KeyError:
            pass

    def _get_pool(
            self,
            project_id: int,
            env_name: str,
            config_name: str,
            database_name: str,
    ) -> Optional[Any]:
        """读取已缓存的连接池。"""
        try:
            return self.pools[project_id][env_name][config_name][database_name]
        except KeyError:
            return None

    @staticmethod
    def _format_oracle_connect_error(exc: BaseException) -> str:
        """补充Oracle常见错误的处置提示。"""
        message = str(exc)
        if "DPY-3010" in message:
            return (
                f"{message}；当前为thin模式且目标库版本过旧。"
                "请设置ORACLE_CLIENT_MODE=thick，安装Oracle InstantClient"
                "(连11g用Client19)，并配置ORACLE_CLIENT_PATH后重启进程"
            )
        return message

    async def create_pool(
            self,
            project_id: Union[int, str],
            env_name: str,
            config_name: str,
            database_name: str,
            max_retries: int = 3,
    ) -> bool:
        """
        按配置创建数据库连接池；已存在则不重复创建。

        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param database_name: 数据库名
        :param max_retries: 建池失败重试次数
        :return: 新建成功为True；池已存在为False
        """
        cache_project_id, cache_env_name, cache_config_name, cache_database_name = (
            self._normalize_cache_key(project_id, env_name, config_name, database_name)
        )
        if self._get_pool(cache_project_id, cache_env_name, cache_config_name, cache_database_name):
            return False

        if max_retries <= 0:
            raise ValueError(f"建池重试次数非法: max_retries={max_retries}")

        try:
            config_row = await self._load_env_config(
                cache_project_id, cache_env_name, cache_config_name, cache_database_name
            )
            if not config_row:
                error_message = (
                    f"配置表未找到记录 [project_id={cache_project_id}, env_name={cache_env_name!r}, "
                    f"config_name={cache_config_name!r}, database_name={cache_database_name!r}]"
                )
                self.logger.error(error_message)
                self._set_error(
                    cache_project_id, cache_env_name, cache_config_name, cache_database_name, error_message
                )
                raise ValueError(error_message)
        except (ValueError, RuntimeError):
            raise
        except Exception as e:
            error_message = f"查询数据库配置失败：{e}"
            self.logger.error(f"{error_message}\n{traceback.format_exc()}")
            self._set_error(
                cache_project_id, cache_env_name, cache_config_name, cache_database_name, error_message
            )
            raise RuntimeError(error_message) from e

        # 直接读取配置表字段；缓存键与建连参数分离，避免同名变量语义混淆
        config_host: str = (config_row.config_host or "").strip()
        config_username: str = (config_row.config_username or "").strip()
        config_password: str = config_row.config_password or ""
        database_name: str = (config_row.database_name or "").strip()

        database_type_value: Any = config_row.database_type
        if database_type_value is not None and hasattr(database_type_value, "value"):
            database_type_value = database_type_value.value
        database_type: str = str(database_type_value or "").strip().lower()

        config_port_text: str = str(config_row.config_port or "").strip()
        missing_fields = [
            field_name
            for field_name, field_value in (
                ("config_host", config_host),
                ("config_port", config_port_text),
                ("config_username", config_username),
                ("database_name", database_name),
                ("database_type", database_type),
            )
            if not field_value
        ]
        if missing_fields:
            error_message = f"数据库配置缺少必填字段：{missing_fields}"
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

        if database_type not in SUPPORTED_DB_TYPES:
            error_message = f"不支持的数据库类型: {database_type!r}"
            self.logger.error(error_message)
            self._set_error(
                cache_project_id, cache_env_name, cache_config_name, cache_database_name, error_message
            )
            raise ValueError(error_message)

        event_loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        last_error_detail: str = ""
        for retry_index in range(max_retries):
            try:
                pool: Any
                if database_type in ("mysql", "tdsql"):
                    pool = await aiomysql.create_pool(
                        minsize=1,
                        maxsize=100,
                        connect_timeout=60,
                        pool_recycle=3600,
                        charset="utf8mb4",
                        host=config_host,
                        port=config_port,
                        user=config_username,
                        password=config_password,
                        db=database_name,
                        autocommit=True,
                    )
                else:
                    # 必须在首次建连前启用thick，否则11g/12.1会DPY-3010且进程内无法再切模式
                    _ensure_oracle_client_mode()
                    oracle_dsn: str = _build_oracle_dsn(config_host, config_port, database_name)

                    def _create_oracle_pool() -> Any:
                        return oracledb.create_pool(
                            user=config_username,
                            password=config_password,
                            dsn=oracle_dsn,
                            min=1,
                            max=100,
                            increment=1,
                        )

                    pool = await event_loop.run_in_executor(None, _create_oracle_pool)

                self._set_pool(
                    cache_project_id, cache_env_name, cache_config_name, cache_database_name, pool
                )
                self._clear_error(
                    cache_project_id, cache_env_name, cache_config_name, cache_database_name
                )
                self.logger.info(
                    f"数据库连接池创建成功 "
                    f"[project_id={cache_project_id}, env_name={cache_env_name}, "
                    f"config_name={cache_config_name}, database_name={cache_database_name}, "
                    f"database_type={database_type}]"
                )
                return True
            except RuntimeError:
                # thick初始化失败不重试
                raise
            except Exception as e:
                last_error_detail = (
                    self._format_oracle_connect_error(e) if database_type == "oracle" else str(e)
                )
                if retry_index < max_retries - 1:
                    self.logger.warning(
                        f"连接失败，{retry_index + 1}/{max_retries}次重试：{last_error_detail}"
                    )
                    await asyncio.sleep(3)

        error_message = f"数据库连接失败：{last_error_detail}"
        self.logger.error(error_message)
        self._set_error(
            cache_project_id, cache_env_name, cache_config_name, cache_database_name, error_message
        )
        raise ConnectionError(error_message)

    async def execute_sql(self, pool: Any, sql: str, result_as_dict: bool = True) -> Dict[str, Any]:
        """
        在已有连接池上执行SQL。

        :param pool: aiomysql.Pool或oracledb.ConnectionPool
        :param sql: SQL语句
        :param result_as_dict: 查询结果是否转为字典列表
        :return: {"sql_data": 查询行或影响统计, "sql_count": 影响/返回行数}
        """
        if not pool:
            raise ValueError("缺少数据库连接池对象")
        if not sql or not str(sql).strip():
            raise ValueError("SQL语句不能为空")

        if isinstance(pool, aiomysql.Pool):
            return await self._execute_mysql_sql(pool, sql, result_as_dict)
        if isinstance(pool, oracledb.ConnectionPool):
            return await self._execute_oracle_sql(pool, sql, result_as_dict)
        raise TypeError(f"不支持的连接池类型: {type(pool).__name__}")

    async def _execute_mysql_sql(self, pool: Any, sql: str, result_as_dict: bool) -> Dict[str, Any]:
        """使用aiomysql连接池执行SQL。"""
        async with pool.acquire() as connection:
            try:
                cursor_class = aiomysql.DictCursor if result_as_dict else aiomysql.Cursor
                async with connection.cursor(cursor_class) as cursor:
                    sql_count = await cursor.execute(sql)
                    if cursor.description:
                        fetched_rows = await cursor.fetchall()
                        rows = (
                            [dict(row) for row in fetched_rows]
                            if result_as_dict
                            else list(fetched_rows)
                        )
                        sql_data = orjson.loads(
                            orjson.dumps(
                                rows,
                                default=self._serialize_db_value,
                                option=orjson.OPT_PASSTHROUGH_DATETIME,
                            )
                        )
                    else:
                        await connection.commit()
                        sql_data = {"count": sql_count}
                    return {"sql_data": sql_data, "sql_count": sql_count}
            except Exception as e:
                await connection.rollback()
                error_message = f"SQL执行失败：{e}"
                self.logger.error(f"{error_message}\n{traceback.format_exc()}")
                raise RuntimeError(error_message) from e

    async def _execute_oracle_sql(self, pool: Any, sql: str, result_as_dict: bool) -> Dict[str, Any]:
        """使用oracledb同步连接池在线程中执行SQL。"""

        def _run_oracle_sql() -> Tuple[Any, int]:
            with pool.acquire() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(sql)
                    if cursor.description:
                        columns = [desc[0] for desc in cursor.description]
                        fetched_rows = cursor.fetchall()
                        if result_as_dict:
                            mapped_rows = [dict(zip(columns, row)) for row in fetched_rows]
                            sql_data = orjson.loads(
                                orjson.dumps(
                                    mapped_rows,
                                    default=self._serialize_db_value,
                                    option=orjson.OPT_PASSTHROUGH_DATETIME,
                                )
                            )
                        else:
                            sql_data = fetched_rows
                        return sql_data, len(fetched_rows)
                    connection.commit()
                    return {"count": cursor.rowcount}, cursor.rowcount
                except Exception:
                    try:
                        connection.rollback()
                    except Exception:
                        pass
                    raise
                finally:
                    cursor.close()

        try:
            sql_data, sql_count = await asyncio.get_running_loop().run_in_executor(
                None, _run_oracle_sql
            )
            return {"sql_data": sql_data, "sql_count": sql_count}
        except Exception as e:
            error_message = f"SQL执行失败：{self._format_oracle_connect_error(e)}"
            self.logger.error(f"{error_message}\n{traceback.format_exc()}")
            raise RuntimeError(error_message) from e

    @staticmethod
    def _serialize_db_value(obj: Any) -> Any:
        """
        orjson default回调：序列化Decimal/日期时间/bytes等数据库字段。

        :param obj: 待序列化对象
        :return: 可被orjson处理的基础类型
        """
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(obj, date):
            return obj.strftime("%Y-%m-%d")
        if isinstance(obj, time):
            return obj.strftime("%H:%M:%S")
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        if isinstance(obj, timedelta):
            return str(obj)
        raise TypeError(f"数据{obj}类型[{type(obj)}]无法完成序列化")

    async def _close_pool(self, pool: Any) -> None:
        """关闭单个连接池(aiomysql异步关闭；Oracle同步关闭)。"""
        if isinstance(pool, aiomysql.Pool):
            pool.close()
            await pool.wait_closed()
            return
        if isinstance(pool, oracledb.ConnectionPool):
            await asyncio.get_running_loop().run_in_executor(None, pool.close)
            return
        raise TypeError(f"不支持的连接池类型: {type(pool).__name__}")

    async def _close_project_pools(self, project_id: int) -> None:
        """关闭指定应用下全部连接池。"""
        for env_name in list(self.pools.get(project_id, {}).keys()):
            for config_name in list(self.pools[project_id][env_name].keys()):
                for database_name, pool in list(self.pools[project_id][env_name][config_name].items()):
                    await self._close_pool(pool)
                    self.logger.info(
                        f"连接池已关闭: [project_id={project_id}/{env_name}/{config_name}/{database_name}]"
                    )

    async def close(self, project_id: Optional[Union[int, str]] = None) -> None:
        """
        关闭指定应用或全部连接池，并清理对应错误记录。

        :param project_id: 应用主键ID；为空则关闭全部
        """
        if project_id is not None:
            try:
                project_id = int(str(project_id).strip())
            except (TypeError, ValueError) as e:
                raise ValueError(f"应用ID不合法: {project_id!r}") from e
            if project_id not in self.pools:
                return
            await self._close_project_pools(project_id)
            del self.pools[project_id]
            self.errors.pop(project_id, None)
            return

        for cached_project_id in list(self.pools.keys()):
            await self._close_project_pools(cached_project_id)
        self.pools.clear()
        self.errors.clear()

    async def get_or_create_pool(
            self,
            project_id: Union[int, str],
            env_name: str,
            config_name: str,
            database_name: str,
    ) -> Any:
        """
        获取已有连接池；不存在则按配置表创建后返回。

        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param database_name: 数据库名
        :return: 连接池对象
        """
        cache_project_id, cache_env_name, cache_config_name, cache_database_name = (
            self._normalize_cache_key(project_id, env_name, config_name, database_name)
        )
        pool = self._get_pool(
            cache_project_id, cache_env_name, cache_config_name, cache_database_name
        )
        if pool:
            return pool

        await self.create_pool(
            cache_project_id, cache_env_name, cache_config_name, cache_database_name
        )
        pool = self._get_pool(
            cache_project_id, cache_env_name, cache_config_name, cache_database_name
        )
        if pool:
            return pool

        error_message = (
                self.errors.get(cache_project_id, {})
                .get(cache_env_name, {})
                .get(cache_config_name, {})
                .get(cache_database_name)
                or "未知错误"
        )
        raise ConnectionError(f"连接池创建失败：{error_message}")


def get_app_database_pool() -> "DBConnPoolFromConfig":
    """
    返回绑定自动化环境配置表的单例连接池管理器。

    :return: DBConnPoolFromConfig单例
    """
    from backend.applications.aotutest.models.autotest_env_config_model import AutoTestEnvConfigModel

    return DBConnPoolFromConfig(config_model=AutoTestEnvConfigModel)
