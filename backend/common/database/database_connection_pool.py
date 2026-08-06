# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : database_connection_pool
@DateTime: 2026/4/21 14:33
"""
import asyncio
import traceback
from datetime import date, time, datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, Any, Type, Set, Tuple

import aiomysql
import oracledb
import orjson
from loguru import logger

# 建池支持的数据库类型
SUPPORTED_DB_TYPES: Tuple[str, ...] = ("mysql", "tdsql", "oracle")


class DBConnPoolFromConfig:
    """
    基于环境配置表的数据库连接池管理器（单例）。

    池与错误按四层键缓存：app_id -> env -> config_name -> database_name。
    """

    __private_instance = None
    __private_initialized = False

    def __new__(cls, *args, **kwargs) -> object:
        if cls.__private_instance is None and cls.__private_initialized is False:
            cls.__private_instance = super().__new__(cls)
        return cls.__private_instance

    def __init__(self, config_model: Optional[Type], logger=logger):
        """
        初始化单例；重复构造时直接跳过。

        :param config_model: Tortoise 环境配置模型类
        :param logger: 日志记录器，默认 loguru.logger
        """
        if self.__private_initialized:
            return
        super().__init__()
        self.__private_initialized = True
        self.logger = logger
        self.config_model = config_model
        self.pools: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = {}
        self.errors: Dict[str, Dict[str, Dict[str, Dict[str, str]]]] = {}

    @staticmethod
    def _normalize_pool_keys(
            app_id: str,
            env: str,
            config_name: str,
            database_name: str,
    ) -> Tuple[str, str, str, str]:
        """
        规范化四层缓存键：app_id 去空白，其余转小写。

        :param app_id: 应用ID
        :param env: 环境名称
        :param config_name: 配置名称
        :param database_name: 数据库名
        :return: (app_id, env, config_name, database_name)
        """
        return (
            app_id.strip(),
            env.lower().strip(),
            config_name.lower().strip(),
            database_name.lower().strip(),
        )

    def _config_model_field_names(self) -> Set[str]:
        """
        读取 config_model 的 Tortoise 字段名集合。

        :return: 字段名集合；模型无效时为空集合
        """
        meta = getattr(self.config_model, "_meta", None)
        if not meta or not getattr(meta, "fields_map", None):
            return set()
        return set(meta.fields_map.keys())

    async def _load_legacy_db_config(
            self,
            app_id: int,
            env: str,
            config_name: str,
            database_name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        从 Legacy 配置表加载连接参数（env_info_id / db_* 字段）。

        :param app_id: 应用ID（对应 env_info_id）
        :param env: 环境名称
        :param config_name: 配置名称
        :param database_name: 数据库名
        :return: 标准化连接字典或None
        """
        config_obj = await self.config_model.filter(
            env_info_id=app_id,
            env=env,
            config_name=config_name,
            db_name=database_name,
            state=0,
        ).first()
        if not config_obj:
            return None
        return {
            "host": getattr(config_obj, "db_host", None),
            "port": int(getattr(config_obj, "db_port", None) or 3306),
            "username": getattr(config_obj, "db_user", None),
            "password": getattr(config_obj, "db_password", None) or "",
            "database_name": getattr(config_obj, "db_name", None),
            "db_type": str(getattr(config_obj, "db_type", None) or "mysql").lower(),
        }

    async def _load_autotest_db_config(
            self,
            app_id: int,
            env: str,
            config_name: str,
            database_name: str,
            field_names: Set[str],
    ) -> Optional[Dict[str, Any]]:
        """
        从自动化环境配置表加载连接参数（project_id + env_id + config_*）。

        :param app_id: 应用ID（对应 project_id）
        :param env: 环境名称（按 env_name 忽略大小写匹配）
        :param config_name: 配置名称
        :param database_name: 数据库名
        :param field_names: 模型字段名集合
        :return: 标准化连接字典或None
        """
        try:
            from backend.applications.aotutest.models.autotest_model import AutoTestApiEnvEnumInfo
            from backend.enums import AutoTestConfigNodeType
        except ImportError as e:
            self.logger.error(f"无法导入自动化测试环境模型或枚举: {e}")
            return None

        env_instance = await AutoTestApiEnvEnumInfo.filter(
            env_name__iexact=env,
        ).filter(state__not=1).first()
        if not env_instance:
            self.logger.warning(f"未找到环境枚举 env_name(忽略大小写)={env!r}")
            return None

        config_query = self.config_model.filter(
            project_id=app_id,
            env_id=env_instance.id,
        ).filter(state__not=1)
        if "config_type" in field_names:
            config_query = config_query.filter(config_type=AutoTestConfigNodeType.DB.value)
        config_obj = await config_query.filter(
            config_name__iexact=config_name,
            database_name__iexact=database_name,
        ).first()
        if not config_obj:
            return None

        raw_port = getattr(config_obj, "config_port", None) or "3306"
        try:
            port = int(str(raw_port).strip())
        except (TypeError, ValueError):
            port = 3306

        database_type = getattr(config_obj, "database_type", None)
        if database_type is not None and hasattr(database_type, "value"):
            database_type = database_type.value

        return {
            "host": getattr(config_obj, "config_host", None),
            "port": port,
            "username": getattr(config_obj, "config_username", None),
            "password": getattr(config_obj, "config_password", None) or "",
            "database_name": getattr(config_obj, "database_name", None),
            "db_type": str(database_type or "mysql").lower(),
        }

    async def _get_db_config_from_orm(
            self,
            app_id: str,
            env: str,
            config_name: str,
            database_name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        根据 config_model 字段形态选择 Legacy/Autotest 查询连接配置。

        :param app_id: 应用ID字符串
        :param env: 环境名称
        :param config_name: 配置名称
        :param database_name: 数据库名
        :return: 含 host/port/username/password/database_name/db_type 的字典；未找到为None
        :raises ValueError: 未注入模型，或字段形态无法识别
        """
        if not self.config_model:
            raise ValueError("未提供ORM模型，请通过config_model参数传入")

        try:
            app_id_int = int(str(app_id).strip())
        except (TypeError, ValueError) as e:
            self.logger.error(f"app_id 无法解析为整数: {app_id!r}, {e}")
            return None

        field_names = self._config_model_field_names()
        if "env_info_id" in field_names:
            return await self._load_legacy_db_config(app_id_int, env, config_name, database_name)
        if "project_id" in field_names and "env_id" in field_names:
            return await self._load_autotest_db_config(
                app_id_int, env, config_name, database_name, field_names
            )

        raise ValueError(
            f"config_model={getattr(self.config_model, '__name__', self.config_model)} "
            f"字段无法识别为 Legacy(env_info_id) 或 Autotest(project_id+env_id)，"
            f"当前字段: {sorted(field_names)}"
        )

    def _set_pool(
            self,
            app_id: str,
            env: str,
            config_name: str,
            database_name: str,
            pool: Any,
    ) -> None:
        """
        写入四层连接池缓存。

        :param app_id: 应用ID键
        :param env: 环境键
        :param config_name: 配置名称键
        :param database_name: 数据库名键
        :param pool: 连接池对象
        :return: None
        """
        if app_id not in self.pools:
            self.pools[app_id] = {}
        if env not in self.pools[app_id]:
            self.pools[app_id][env] = {}
        if config_name not in self.pools[app_id][env]:
            self.pools[app_id][env][config_name] = {}
        self.pools[app_id][env][config_name][database_name] = pool

    def _set_error(
            self,
            app_id: str,
            env: str,
            config_name: str,
            database_name: str,
            error_message: str,
    ) -> None:
        """
        写入四层建池错误缓存。

        :param app_id: 应用ID键
        :param env: 环境键
        :param config_name: 配置名称键
        :param database_name: 数据库名键
        :param error_message: 错误描述
        :return: None
        """
        if app_id not in self.errors:
            self.errors[app_id] = {}
        if env not in self.errors[app_id]:
            self.errors[app_id][env] = {}
        if config_name not in self.errors[app_id][env]:
            self.errors[app_id][env][config_name] = {}
        self.errors[app_id][env][config_name][database_name] = error_message

    def _clear_error(
            self,
            app_id: str,
            env: str,
            config_name: str,
            database_name: str,
    ) -> None:
        """
        清除指定键的建池错误记录。

        :param app_id: 应用ID键
        :param env: 环境键
        :param config_name: 配置名称键
        :param database_name: 数据库名键
        :return: None
        """
        try:
            del self.errors[app_id][env][config_name][database_name]
        except KeyError:
            pass

    def _get_pool(
            self,
            app_id: str,
            env: str,
            config_name: str,
            database_name: str,
    ) -> Optional[Any]:
        """
        读取已缓存的连接池。

        :param app_id: 应用ID键
        :param env: 环境键
        :param config_name: 配置名称键
        :param database_name: 数据库名键
        :return: 连接池对象或None
        """
        try:
            return self.pools[app_id][env][config_name][database_name]
        except KeyError:
            return None

    async def create_pool(
            self,
            app_id: str,
            env: str,
            config_name: str,
            database_name: str,
            max_retries: int = 3,
    ) -> bool:
        """
        按配置创建数据库连接池；已存在则不重复创建。

        :param app_id: 应用ID（Autotest 为 project_id）
        :param env: 环境名称
        :param config_name: 配置名称
        :param database_name: 数据库名
        :param max_retries: 建池失败重试次数
        :return: 新建成功为True；池已存在为False
        :raises ValueError: 参数为空、配置缺失或不支持的数据库类型
        :raises ConnectionError: 重试耗尽仍无法建池
        """
        if not all([app_id, env, config_name, database_name]):
            error_message: str = "应用ID、环境、配置名称、数据库名称均不能为空"
            self.logger.error(error_message)
            raise ValueError(error_message)

        app_id_key, env_key, config_key, db_key = self._normalize_pool_keys(
            app_id, env, config_name, database_name
        )
        if self._get_pool(app_id_key, env_key, config_key, db_key):
            return False

        try:
            db_config = await self._get_db_config_from_orm(
                app_id_key, env_key, config_key, db_key
            )
            if not db_config:
                error_message = (
                    f"配置表未找到记录 [app_id={app_id!r}, env={env_key!r}, "
                    f"config_name={config_key!r}, database_name={db_key!r}]"
                )
                self.logger.error(error_message)
                self._set_error(app_id_key, env_key, config_key, db_key, error_message)
                raise ValueError(error_message)

            missing_fields = [
                field for field in ("host", "port", "username", "database_name")
                if not db_config.get(field)
            ]
            if missing_fields:
                error_message = f"数据库配置缺少必填字段：{missing_fields}"
                self.logger.error(error_message)
                self._set_error(app_id_key, env_key, config_key, db_key, error_message)
                raise ValueError(error_message)
        except ValueError:
            raise
        except Exception as e:
            error_message = f"查询数据库配置失败：{e}"
            self.logger.error(f"{error_message}\n{traceback.format_exc()}")
            self._set_error(app_id_key, env_key, config_key, db_key, error_message)
            raise

        db_type = str(db_config.get("db_type") or "mysql").lower()
        if db_type not in SUPPORTED_DB_TYPES:
            error_message = f"不支持的数据库类型: {db_type!r}"
            self.logger.error(error_message)
            self._set_error(app_id_key, env_key, config_key, db_key, error_message)
            raise ValueError(error_message)

        event_loop = asyncio.get_running_loop()
        for retry_index in range(max_retries):
            try:
                if db_type in ("mysql", "tdsql"):
                    pool = await aiomysql.create_pool(
                        minsize=1,
                        maxsize=100,
                        connect_timeout=60,
                        pool_recycle=3600,
                        charset="utf8mb4",
                        host=db_config["host"],
                        port=db_config["port"],
                        user=db_config["username"],
                        password=db_config["password"],
                        db=db_config["database_name"],
                        autocommit=True,
                    )
                else:
                    # Oracle 使用同步连接池，SQL 在线程池中执行
                    def _create_oracle_pool():
                        return oracledb.create_pool(
                            user=db_config["username"],
                            password=db_config["password"],
                            service_name=db_config["database_name"],
                            host=db_config["host"],
                            port=db_config["port"],
                            min=1,
                            max=100,
                            increment=1,
                        )

                    pool = await event_loop.run_in_executor(None, _create_oracle_pool)

                self._set_pool(app_id_key, env_key, config_key, db_key, pool)
                self._clear_error(app_id_key, env_key, config_key, db_key)
                self.logger.info(
                    f"数据库连接池创建成功 "
                    f"[app_id={app_id_key}, env={env_key}, config={config_key}, "
                    f"db={db_key}, type={db_type}]"
                )
                return True
            except Exception as e:
                if retry_index < max_retries - 1:
                    self.logger.warning(
                        f"连接失败，{retry_index + 1}/{max_retries}次重试：{e}"
                    )
                    await asyncio.sleep(3)
                    continue
                error_message = f"连接失败，错误信息：{e}"
                self.logger.error(error_message)
                self._set_error(app_id_key, env_key, config_key, db_key, error_message)
                raise ConnectionError(error_message) from e
        return False

    async def execute_sql(
            self,
            pool: Any,
            sql: str,
            result_as_dict: bool = True,
    ) -> Dict[str, Any]:
        """
        在已有连接池上执行 SQL。

        :param pool: aiomysql.Pool 或 oracledb.ConnectionPool
        :param sql: SQL 语句
        :param result_as_dict: 查询结果是否转为字典列表
        :return: {"sql_data": 查询行或影响统计, "sql_count": 影响/返回行数}
        :raises ValueError: 连接池或SQL为空
        :raises TypeError: 不支持的连接池类型
        :raises RuntimeError: SQL 执行失败
        """
        if not pool:
            raise ValueError("缺少数据库池连接对象，请检查")
        if not sql or not str(sql).strip():
            raise ValueError("SQL语句不能为空")

        pool_type_name = type(pool).__name__
        if pool_type_name == "Pool":
            return await self._execute_mysql_sql(pool, sql, result_as_dict)
        if pool_type_name == "ConnectionPool":
            return await self._execute_oracle_sql(pool, sql, result_as_dict)
        raise TypeError(f"不支持的连接池类型: {pool_type_name}")

    async def _execute_mysql_sql(
            self,
            pool: Any,
            sql: str,
            result_as_dict: bool,
    ) -> Dict[str, Any]:
        """
        使用 aiomysql 连接池执行 SQL。

        :param pool: aiomysql.Pool
        :param sql: SQL 语句
        :param result_as_dict: 查询结果是否转为字典列表
        :return: {"sql_data": ..., "sql_count": int}
        :raises RuntimeError: 执行失败
        """
        async with pool.acquire() as connection:
            try:
                cursor_class = aiomysql.DictCursor if result_as_dict else aiomysql.Cursor
                async with connection.cursor(cursor_class) as cursor:
                    affected_rows = await cursor.execute(sql)
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
                                default=self.serialize_db_value,
                                option=orjson.OPT_PASSTHROUGH_DATETIME,
                            )
                        )
                    else:
                        await connection.commit()
                        sql_data = {"count": affected_rows}
                    return {"sql_data": sql_data, "sql_count": affected_rows}
            except Exception as e:
                await connection.rollback()
                error_message = f"SQL执行失败，{e}"
                self.logger.error(f"{error_message}\n{traceback.format_exc()}")
                raise RuntimeError(error_message) from e

    async def _execute_oracle_sql(
            self,
            pool: Any,
            sql: str,
            result_as_dict: bool,
    ) -> Dict[str, Any]:
        """
        使用 oracledb 同步连接池在线程中执行 SQL。

        :param pool: oracledb.ConnectionPool
        :param sql: SQL 语句
        :param result_as_dict: 查询结果是否转为字典列表
        :return: {"sql_data": ..., "sql_count": int}
        :raises RuntimeError: 执行失败
        """
        def _run_oracle_sql():
            connection = pool.acquire()
            try:
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
                                    default=self.serialize_db_value,
                                    option=orjson.OPT_PASSTHROUGH_DATETIME,
                                )
                            )
                        else:
                            sql_data = fetched_rows
                        affected_rows = len(fetched_rows)
                    else:
                        connection.commit()
                        sql_data = {"count": cursor.rowcount}
                        affected_rows = cursor.rowcount
                    return sql_data, affected_rows
                finally:
                    cursor.close()
            except Exception:
                try:
                    connection.rollback()
                except Exception:
                    pass
                raise
            finally:
                pool.release(connection)

        try:
            sql_data, sql_count = await asyncio.get_running_loop().run_in_executor(
                None, _run_oracle_sql
            )
            return {"sql_data": sql_data, "sql_count": sql_count}
        except Exception as e:
            error_message = f"执行sql失败，{e}"
            self.logger.error(f"{error_message}\n{traceback.format_exc()}")
            raise RuntimeError(error_message) from e

    @staticmethod
    def serialize_db_value(obj: Any) -> Any:
        """
        orjson default 回调：序列化 Decimal/日期时间/bytes 等数据库字段。

        :param obj: 待序列化对象
        :return: 可被 orjson 处理的基础类型
        :raises TypeError: 无法序列化的类型
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
        """
        关闭单个连接池（兼容 aiomysql 异步关闭与 Oracle 同步关闭）。

        :param pool: 连接池对象
        :return: None
        """
        if hasattr(pool, "close") and hasattr(pool, "wait_closed"):
            pool.close()
            await pool.wait_closed()
        elif hasattr(pool, "close"):
            await asyncio.get_running_loop().run_in_executor(None, pool.close)

    async def close(self, app_id: Optional[str] = None) -> None:
        """
        关闭指定应用或全部连接池，并清理对应错误记录。

        :param app_id: 应用ID；为空则关闭全部
        :return: None
        """
        if app_id:
            app_id_key = app_id.strip()
            if app_id_key not in self.pools:
                return
            for env_key in list(self.pools[app_id_key].keys()):
                for config_key in list(self.pools[app_id_key][env_key].keys()):
                    for db_key, pool in list(self.pools[app_id_key][env_key][config_key].items()):
                        await self._close_pool(pool)
                        self.logger.info(
                            f"连接池已关闭 [{app_id_key}/{env_key}/{config_key}/{db_key}]"
                        )
            del self.pools[app_id_key]
            self.errors.pop(app_id_key, None)
            return

        for app_id_key in list(self.pools.keys()):
            for env_key in list(self.pools[app_id_key].keys()):
                for config_key in list(self.pools[app_id_key][env_key].keys()):
                    for db_key, pool in list(self.pools[app_id_key][env_key][config_key].items()):
                        await self._close_pool(pool)
                        self.logger.info(
                            f"连接池已关闭 [{app_id_key}/{env_key}/{config_key}/{db_key}]"
                        )
        self.pools.clear()
        self.errors.clear()

    async def get_or_create_pool(
            self,
            app_id: str,
            env: str,
            config_name: str,
            database_name: str,
    ) -> Any:
        """
        获取已有连接池；不存在则按配置表创建后返回。

        :param app_id: 应用ID（Autotest 为 project_id）
        :param env: 环境名称
        :param config_name: 配置名称
        :param database_name: 数据库名
        :return: 连接池对象
        :raises ConnectionError: 创建失败
        """
        app_id_key, env_key, config_key, db_key = self._normalize_pool_keys(
            app_id, env, config_name, database_name
        )

        pool = self._get_pool(app_id_key, env_key, config_key, db_key)
        if pool:
            return pool

        await self.create_pool(app_id, env, config_name, database_name)
        pool = self._get_pool(app_id_key, env_key, config_key, db_key)
        if pool:
            return pool

        error_message = (
            self.errors.get(app_id_key, {})
            .get(env_key, {})
            .get(config_key, {})
            .get(db_key)
        )
        raise ConnectionError(f"连接池创建失败，错误信息：{error_message}")


def get_app_database_pool() -> "DBConnPoolFromConfig":
    """
    返回绑定自动化环境配置表的单例连接池管理器。

    :return: DBConnPoolFromConfig 单例
    """
    from backend.applications.aotutest.models.autotest_model import AutoTestApiEnvConfigInfo

    return DBConnPoolFromConfig(config_model=AutoTestApiEnvConfigInfo)
