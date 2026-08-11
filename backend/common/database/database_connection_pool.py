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
from typing import Dict, Optional, Any, Type, Tuple, Union

import aiomysql
import oracledb
import orjson
from loguru import logger

# 建池支持的数据库类型
SUPPORTED_DB_TYPES: Tuple[str, ...] = ("mysql", "tdsql", "oracle")


class DBConnPoolFromConfig:
    """
    基于环境配置表的数据库连接池管理器（单例）。

    池与错误按四层坐标缓存：project_id -> env_name -> config_name -> database_name。
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

        :param config_model: Tortoise环境配置模型类
        :param logger: 日志记录器，默认loguru.logger
        """
        if self.__private_initialized:
            return
        super().__init__()
        self.__private_initialized = True
        self.logger = logger
        self.config_model = config_model
        self.pools: Dict[int, Dict[str, Dict[str, Dict[str, Any]]]] = {}
        self.errors: Dict[int, Dict[str, Dict[str, Dict[str, str]]]] = {}

    @staticmethod
    def _normalize(project_id: int, env_name: str, config_name: str, database_name: str) -> Tuple[int, str, str, str]:
        """
        规范化四层缓存坐标：应用ID转整数，名称类字段去空白并转小写。

        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param database_name: 数据库名
        :return: (project_id, env_name, config_name, database_name)
        :raises ValueError: 应用ID非法或任一必填项为空
        """
        env_name = (env_name or "").strip().lower()
        config_name = (config_name or "").strip().lower()
        database_name = (database_name or "").strip().lower()
        if not project_id or not env_name or not config_name or not database_name:
            raise ValueError("应用ID、环境名称、配置名称、数据库名称均不能为空")
        return project_id, env_name, config_name, database_name

    async def _get_db_config_from_orm(self, project_id: int, env_name: str, config_name: str, database_name: str) -> Optional[Dict[str, Any]]:
        """
        从自动化环境配置表加载数据库连接参数。

        解析路径：环境字典(env_name) -> 环境绑定(project_id+env_type=database) -> 配置行。

        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param database_name: 数据库名
        :return: 含host/port/username/password/database_name/db_type的字典；未找到为None
        :raises ValueError: 未提供config_model
        :raises RuntimeError: 无法导入环境模型或枚举
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

        env_dict_ids = await AutoTestApiEnvInfo.filter(
            env_name__iexact=env_name,
            state__not=1,
        ).values_list("id", flat=True)
        if not env_dict_ids:
            self.logger.warning(f"未找到环境字典 env_name(忽略大小写)={env_name!r}")
            return None

        # 必须带project_id与env_type，避免多应用同名环境或跨节点类型串库
        env_bind = await AutoTestApiEnvBindInfo.filter(
            project_id=project_id,
            env_enum_id__in=list(env_dict_ids),
            env_type=AutoTestConfigNodeType.DB,
            state__not=1,
        ).first()
        if not env_bind:
            self.logger.warning(
                f"未找到环境绑定 project_id={project_id}, "
                f"env_name(忽略大小写)={env_name!r}, env_type={AutoTestConfigNodeType.DB.value}"
            )
            return None

        config_obj = await self.config_model.filter(
            env_bind_id=env_bind.id,
            state__not=1,
            config_name__iexact=config_name,
            database_name__iexact=database_name,
        ).first()
        if not config_obj:
            return None

        port_raw = config_obj.config_port or "3306"
        try:
            port = int(str(port_raw).strip())
        except (TypeError, ValueError):
            port = 3306

        database_type = config_obj.database_type
        if database_type is not None and hasattr(database_type, "value"):
            database_type = database_type.value

        return {
            "host": config_obj.config_host,
            "port": port,
            "username": config_obj.config_username,
            "password": config_obj.config_password or "",
            "database_name": config_obj.database_name,
            "db_type": str(database_type or "mysql").lower(),
        }

    def _set_pool(self, project_id: int, env_name: str, config_name: str, database_name: str, pool: Any) -> None:
        """
        写入四层连接池缓存。

        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param database_name: 数据库名
        :param pool: 连接池对象
        """
        if project_id not in self.pools:
            self.pools[project_id] = {}
        if env_name not in self.pools[project_id]:
            self.pools[project_id][env_name] = {}
        if config_name not in self.pools[project_id][env_name]:
            self.pools[project_id][env_name][config_name] = {}
        self.pools[project_id][env_name][config_name][database_name] = pool

    def _set_error(self, project_id: int, env_name: str, config_name: str, database_name: str, error_message: str) -> None:
        """
        写入四层建池错误缓存。

        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param database_name: 数据库名
        :param error_message: 错误描述
        """
        if project_id not in self.errors:
            self.errors[project_id] = {}
        if env_name not in self.errors[project_id]:
            self.errors[project_id][env_name] = {}
        if config_name not in self.errors[project_id][env_name]:
            self.errors[project_id][env_name][config_name] = {}
        self.errors[project_id][env_name][config_name][database_name] = error_message

    def _clear_error(self, project_id: int, env_name: str, config_name: str, database_name: str) -> None:
        """
        清除指定坐标的建池错误记录。

        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param database_name: 数据库名
        """
        try:
            del self.errors[project_id][env_name][config_name][database_name]
        except KeyError:
            pass

    def _get_pool(self, project_id: int, env_name: str, config_name: str, database_name: str) -> Optional[Any]:
        """
        读取已缓存的连接池。

        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param database_name: 数据库名
        :return: 连接池对象或None
        """
        try:
            return self.pools[project_id][env_name][config_name][database_name]
        except KeyError:
            return None

    async def create_pool(self, project_id: Union[int, str], env_name: str, config_name: str, database_name: str, max_retries: int = 3) -> bool:
        """
        按配置创建数据库连接池；已存在则不重复创建。

        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param database_name: 数据库名
        :param max_retries: 建池失败重试次数
        :return: 新建成功为True；池已存在为False
        :raises ValueError: 参数非法、配置缺失或不支持的数据库类型
        :raises RuntimeError: 查询配置过程出现非预期错误
        :raises ConnectionError: 建池连接失败且重试耗尽
        """
        project_id, env_name, config_name, database_name = self._normalize(
            project_id, env_name, config_name, database_name
        )
        if self._get_pool(project_id, env_name, config_name, database_name):
            return False

        try:
            db_config = await self._get_db_config_from_orm(
                project_id, env_name, config_name, database_name
            )
            if not db_config:
                error_message = (
                    f"配置表未找到记录 [project_id={project_id}, env_name={env_name!r}, "
                    f"config_name={config_name!r}, database_name={database_name!r}]"
                )
                self.logger.error(error_message)
                self._set_error(project_id, env_name, config_name, database_name, error_message)
                raise ValueError(error_message)

            missing_fields = [
                field for field in ("host", "port", "username", "database_name")
                if not db_config.get(field)
            ]
            if missing_fields:
                error_message = f"数据库配置缺少必填字段：{missing_fields}"
                self.logger.error(error_message)
                self._set_error(project_id, env_name, config_name, database_name, error_message)
                raise ValueError(error_message)
        except (ValueError, RuntimeError):
            raise
        except Exception as e:
            error_message = f"查询数据库配置失败：{e}"
            self.logger.error(f"{error_message}\n{traceback.format_exc()}")
            self._set_error(project_id, env_name, config_name, database_name, error_message)
            raise RuntimeError(error_message) from e

        db_type = str(db_config.get("db_type") or "mysql").lower()
        if db_type not in SUPPORTED_DB_TYPES:
            error_message = f"不支持的数据库类型: {db_type!r}"
            self.logger.error(error_message)
            self._set_error(project_id, env_name, config_name, database_name, error_message)
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
                    # Oracle使用同步连接池，SQL在线程池中执行
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

                self._set_pool(project_id, env_name, config_name, database_name, pool)
                self._clear_error(project_id, env_name, config_name, database_name)
                self.logger.info(
                    f"数据库连接池创建成功 "
                    f"[project_id={project_id}, env_name={env_name}, config_name={config_name}, "
                    f"database_name={database_name}, db_type={db_type}]"
                )
                return True
            except Exception as e:
                if retry_index < max_retries - 1:
                    self.logger.warning(
                        f"连接失败，{retry_index + 1}/{max_retries}次重试：{e}"
                    )
                    await asyncio.sleep(3)
                    continue
                error_message = f"数据库连接失败：{e}"
                self.logger.error(error_message)
                self._set_error(project_id, env_name, config_name, database_name, error_message)
                raise ConnectionError(error_message) from e
        # max_retries<=0时不会进入循环
        raise ValueError(f"建池重试次数非法: max_retries={max_retries}")

    async def execute_sql(self, pool: Any, sql: str, result_as_dict: bool = True) -> Dict[str, Any]:
        """
        在已有连接池上执行SQL。

        :param pool: aiomysql.Pool或oracledb.ConnectionPool
        :param sql: SQL语句
        :param result_as_dict: 查询结果是否转为字典列表
        :return: {"sql_data": 查询行或影响统计, "sql_count": 影响/返回行数}
        :raises ValueError: pool或sql非法
        :raises TypeError: 不支持的连接池类型
        :raises RuntimeError: SQL执行失败
        """
        if not pool:
            raise ValueError("缺少数据库连接池对象")
        if not sql or not str(sql).strip():
            raise ValueError("SQL语句不能为空")

        pool_type_name = type(pool).__name__
        if pool_type_name == "Pool":
            return await self._execute_mysql_sql(pool, sql, result_as_dict)
        if pool_type_name == "ConnectionPool":
            return await self._execute_oracle_sql(pool, sql, result_as_dict)
        raise TypeError(f"不支持的连接池类型: {pool_type_name}")

    async def _execute_mysql_sql(self, pool: Any, sql: str, result_as_dict: bool) -> Dict[str, Any]:
        """
        使用aiomysql连接池执行SQL。

        :param pool: aiomysql.Pool
        :param sql: SQL语句
        :param result_as_dict: 查询结果是否转为字典列表
        :return: {"sql_data": ..., "sql_count": int}
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
                error_message = f"SQL执行失败：{e}"
                self.logger.error(f"{error_message}\n{traceback.format_exc()}")
                raise RuntimeError(error_message) from e

    async def _execute_oracle_sql(self, pool: Any, sql: str, result_as_dict: bool) -> Dict[str, Any]:
        """
        使用oracledb同步连接池在线程中执行SQL。

        :param pool: oracledb.ConnectionPool
        :param sql: SQL语句
        :param result_as_dict: 查询结果是否转为字典列表
        :return: {"sql_data": ..., "sql_count": int}
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
            error_message = f"SQL执行失败：{e}"
            self.logger.error(f"{error_message}\n{traceback.format_exc()}")
            raise RuntimeError(error_message) from e

    @staticmethod
    def serialize_db_value(obj: Any) -> Any:
        """
        orjson default回调：序列化Decimal/日期时间/bytes等数据库字段。

        :param obj: 待序列化对象
        :return: 可被orjson处理的基础类型
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
        关闭单个连接池（aiomysql异步关闭；Oracle同步关闭）。

        :param pool: 连接池对象
        """
        if hasattr(pool, "close") and hasattr(pool, "wait_closed"):
            pool.close()
            await pool.wait_closed()
        elif hasattr(pool, "close"):
            await asyncio.get_running_loop().run_in_executor(None, pool.close)

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
            for env_name in list(self.pools[project_id].keys()):
                for config_name in list(self.pools[project_id][env_name].keys()):
                    for database_name, pool in list(self.pools[project_id][env_name][config_name].items()):
                        await self._close_pool(pool)
                        self.logger.info(f"连接池已关闭: [project_id={project_id}/{env_name}/{config_name}/{database_name}]")
            del self.pools[project_id]
            self.errors.pop(project_id, None)
            return

        for project_id in list(self.pools.keys()):
            for env_name in list(self.pools[project_id].keys()):
                for config_name in list(self.pools[project_id][env_name].keys()):
                    for database_name, pool in list(self.pools[project_id][env_name][config_name].items()):
                        await self._close_pool(pool)
                        self.logger.info(f"连接池已关闭: [project_id={project_id}/{env_name}/{config_name}/{database_name}]")
        self.pools.clear()
        self.errors.clear()

    async def get_or_create_pool(self, project_id: Union[int, str], env_name: str, config_name: str, database_name: str) -> Any:
        """
        获取已有连接池；不存在则按配置表创建后返回。

        :param project_id: 应用主键ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param database_name: 数据库名
        :return: 连接池对象
        :raises ConnectionError: 创建后仍无法取得连接池
        """
        project_id, env_name, config_name, database_name = self._normalize(
            project_id, env_name, config_name, database_name
        )
        pool = self._get_pool(project_id, env_name, config_name, database_name)
        if pool:
            return pool

        await self.create_pool(project_id, env_name, config_name, database_name)
        pool = self._get_pool(project_id, env_name, config_name, database_name)
        if pool:
            return pool

        error_message = (
                self.errors.get(project_id, {})
                .get(env_name, {})
                .get(config_name, {})
                .get(database_name)
                or "未知错误"
        )
        raise ConnectionError(f"连接池创建失败：{error_message}")


def get_app_database_pool() -> "DBConnPoolFromConfig":
    """
    返回绑定自动化环境配置表的单例连接池管理器。

    :return: DBConnPoolFromConfig单例
    """
    from backend.applications.aotutest.models.autotest_model import AutoTestApiEnvConfigInfo

    return DBConnPoolFromConfig(config_model=AutoTestApiEnvConfigInfo)
