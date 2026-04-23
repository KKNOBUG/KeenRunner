# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : database_connection_pool
@DateTime: 2026/4/21 14:33
"""
import asyncio
import json
import traceback
from datetime import date, time, datetime
from decimal import Decimal
from typing import Dict, Optional, Any, Type, Set

import aiomysql
import cx_Oracle
from loguru import logger


class DBConnPoolFromConfig:
    # 应用数据库连接池管理器，基于环境配置子表
    __private_instance = None
    __private_initialized = False

    def __new__(cls, *args, **kwargs) -> object:
        if cls.__private_instance is None and cls.__private_initialized is False:
            cls.__private_instance = super().__new__(cls)
        return cls.__private_instance

    def __init__(self, config_model: Optional[Type], logger=logger):
        """
        初始化，元数据库配置
        """
        if self.__private_initialized:
            return
        super().__init__()
        self.__private_initialized = True
        self.logger = logger
        self.config_model = config_model

        # 存储结构-
        self.pools: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = {}

        # 错误信息存储结构
        self.errors: Dict[str, Dict[str, Dict[str, Dict[str, str]]]] = {}

    def _config_model_field_names(self) -> Set[str]:
        """Tortoise 模型字段名集合，用于区分旧表结构与自动化环境配置表。"""
        meta = getattr(self.config_model, "_meta", None)
        if not meta or not getattr(meta, "fields_map", None):
            return set()
        return set(meta.fields_map.keys())

    async def _get_db_config_from_orm(self, app_id, env, config_name, db_name) -> Optional[Dict[str, Any]]:
        """
        通过 ORM 查询数据库连接配置。

        支持两种元数据形态：
        1) Legacy：env_info_id / env / config_name / db_name / db_host / db_user…
        2) Autotest：与 AutoTestApiConfigBase 一致 — project_id、env_id（由 project_id+env 名称解析）、
           config_name、database_name、config_host、config_port、config_username、config_password、database_type；
           且 config_type 为 database。
        """
        if not self.config_model:
            raise ValueError("未提供ORM模型，请通过config_model参数传入")

        try:
            try:
                app_id_int = int(str(app_id).strip())
            except (TypeError, ValueError) as e:
                self.logger.error(f"app_id 无法解析为整数: {app_id!r}, {e}")
                return None

            field_names = self._config_model_field_names()

            # ---------- Legacy ----------
            if "env_info_id" in field_names:
                config_obj = await self.config_model.filter(
                    env_info_id=app_id_int,
                    env=env,
                    config_name=config_name,
                    db_name=db_name,
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
                    "db_type": getattr(config_obj, "db_type", "mysql"),
                }

            # ---------- Autotest（字段与 AutoTestApiConfigBase / 环境配置表一致）----------
            if "project_id" in field_names and "env_id" in field_names:
                try:
                    from backend.applications.aotutest.models.autotest_model import AutoTestApiEnvEnumInfo
                    from backend.enums import AutoTestConfigNodeType
                except ImportError as e:
                    self.logger.error(f"无法导入自动化测试环境模型或枚举: {e}")
                    return None

                env_row = await AutoTestApiEnvEnumInfo.filter(
                    env_name__iexact=env,
                ).filter(state__not=1).first()
                if not env_row:
                    self.logger.warning(
                        f"未找到环境枚举 env_name(忽略大小写)={env!r}"
                    )
                    return None

                qs = self.config_model.filter(
                    project_id=app_id_int,
                    env_id=env_row.id,
                ).filter(state__not=1)
                if "config_type" in field_names:
                    qs = qs.filter(config_type=AutoTestConfigNodeType.DB.value)
                config_obj = await qs.filter(
                    config_name__iexact=config_name,
                    database_name__iexact=db_name,
                ).first()
                if not config_obj:
                    return None

                port_raw = getattr(config_obj, "config_port", None) or "3306"
                try:
                    port = int(str(port_raw).strip())
                except (TypeError, ValueError):
                    port = 3306

                db_type_val = getattr(config_obj, "database_type", None)
                if db_type_val is not None and hasattr(db_type_val, "value"):
                    db_type_val = db_type_val.value
                db_type_str = str(db_type_val or "mysql").lower()

                return {
                    "host": getattr(config_obj, "config_host", None),
                    "port": port,
                    "username": getattr(config_obj, "config_username", None),
                    "password": getattr(config_obj, "config_password", None) or "",
                    "database_name": getattr(config_obj, "database_name", None),
                    "db_type": db_type_str,
                }

            raise ValueError(
                f"config_model={getattr(self.config_model, '__name__', self.config_model)} "
                f"字段无法识别为 Legacy(env_info_id) 或 Autotest(project_id+env_id)，"
                f"当前字段: {sorted(field_names)}"
            )
        except ValueError:
            raise
        except Exception as e:
            self.logger.error(f"ORM 查询失败 {str(e)}\n{traceback.format_exc()}")
            raise

    def _set_pool(self, app_id: str, env: str, config_name: str, db_name: str, pool: Any):
        """四层嵌套结构存储连接池"""
        if app_id not in self.pools:
            self.pools[app_id] = {}
        if env not in self.pools[app_id]:
            self.pools[app_id][env] = {}
        if config_name not in self.pools[app_id][env]:
            self.pools[app_id][env][config_name] = {}
        self.pools[app_id][env][config_name][db_name] = pool

    def _set_error(self, app_id: str, env: str, config_name: str, db_name: str, error_msg: str):
        """四层嵌套结构存储错误信息"""
        if app_id not in self.errors:
            self.errors[app_id] = {}
        if env not in self.errors[app_id]:
            self.errors[app_id][env] = {}
        if config_name not in self.errors[app_id][env]:
            self.errors[app_id][env][config_name] = {}
        self.errors[app_id][env][config_name][db_name] = error_msg

    def _clear_error(self, app_id: str, env: str, config_name: str, db_name: str):
        """清除错误记录"""
        try:
            if (app_id in self.errors and
                    env in self.errors[app_id] and
                    config_name in self.errors[app_id][env] and
                    db_name in self.errors[app_id][env][config_name]):
                del self.errors[app_id][env][config_name][db_name]
        except Exception:
            pass

    def _get_pool(self, app_id: str, env: str, config_name: str, db_name: str) -> Optional[Any]:
        """获取已存在的连接池"""
        try:
            return self.pools[app_id][env][config_name][db_name]
        except KeyError:
            return None

    async def connection(self, app_id: str, env: str, config_name: str, db_name: str, max_retries: int = 3) -> bool:
        """创建数据库连接池"""
        # 参数校验
        if not all([app_id, env, config_name, db_name]):
            err_msg = "应用ID、环境、配置名称、数据库名称均不能为空"
            self.logger.error(err_msg)
            raise ValueError(err_msg)

        # 转换小写(保持与之前逻辑一致，env_info_id保持原样用于查询)
        app_id_key = app_id.strip()  # 字典key
        env_clean = env.lower().strip()
        config_clean = config_name.lower().strip()
        db_clean = db_name.lower().strip()

        # 检查是否存在(使用app_id作为字符串key存储，但查询时转为int)
        existing_pool = self._get_pool(app_id_key, env_clean, config_clean, db_clean)
        if existing_pool:
            return False

        # 使用ORM查询配置
        try:
            config = await self._get_db_config_from_orm(
                app_id_key, env_clean, config_clean, db_clean)

            if not config:
                err_msg = (
                    f"配置表未找到记录 [app_id={app_id!r}, env={env_clean!r}, config_name={config_clean!r}, "
                    f"database/db_name={db_clean!r}]（Legacy: env_info_id；Autotest: project_id + env_name + database）"
                )
                self.logger.error(err_msg)
                self._set_error(app_id_key, env_clean, config_clean, db_clean, err_msg)
                raise Exception(err_msg)
            db_type = config.get("db_type", "mysql").lower()

            # 检查必填字段
            required_fields = ["host", "port", "username", "database_name"]
            missing = [f for f in required_fields if not config.get(f)]
            if missing:
                err_msg = f"数据库配置缺少必填字段：{missing},请检查环境配置子表里的数据"
                self._set_error(app_id_key, env_clean, config_clean, db_clean, err_msg)
                raise Exception(err_msg)
        except Exception as e:
            if "配置表未找到记录" not in str(e) and "缺少必填字段" not in str(e):
                err_msg = f"查询数据库配置失败：{str(e)}"
                self.logger.error(err_msg + f"\n{traceback.format_exc()}")
            raise

        # 创建连接池
        for retry in range(max_retries):
            try:
                if db_type in ("mysql", "tdsql"):
                    pool = await aiomysql.create_pool(
                        minsize=1,
                        maxsize=100,
                        connect_timeout=60,
                        pool_recycle=3600,
                        charset='utf8mb4',
                        host=config["host"],
                        port=config["port"],
                        user=config["username"],
                        password=config["password"],
                        db=config["database_name"],
                        autocommit=True
                    )
                elif db_type == 'oracle':
                    def _create_oracle_pool():
                        return cx_Oracle.SessionPool(
                            user=config['username'],
                            password=config['password'],
                            dsn=f"{config['host']}:{config['port']}/{config['database_name']}",
                            min=1,
                            max=100,
                            increment=1,
                            encoding='UTF-8'
                        )

                    # 线程池里创建，避免阻塞时间
                    loop = asyncio.get_event_loop()
                    pool = await loop.run_in_executor(None, _create_oracle_pool)
                self._set_pool(app_id_key, env_clean, config_clean, db_clean, pool)
                self._clear_error(app_id_key, env_clean, config_clean, db_clean)
                self.logger.info("数据库创建连接池成功")

                return True

            except Exception as e:
                if retry < max_retries - 1:
                    self.logger.warning(f"连接失败，{retry + 1}/{max_retries}次重试：{str(e)}")
                    await asyncio.sleep(3)
                    continue
                else:
                    err_msg = f"连接失败，错误信息：{str(e)}"
                    self.logger.error(err_msg)
                    self._set_error(app_id_key, env_clean, config_clean, db_clean, err_msg)
                    raise ConnectionError(err_msg)

    async def execute_sql(self, pool, sql: str, is_dict: bool = True):
        """根据已有的数据库连接池执行sql"""
        if not pool:
            raise ValueError("缺少数据库池连接对象，请检查")
        pool_cls_name = type(pool).__name__
        loop = asyncio.get_event_loop()
        if pool_cls_name == "Pool":
            async with pool.acquire() as conn:
                try:
                    cursor_class = aiomysql.DictCursor if is_dict else aiomysql.Cursor
                    async with conn.cursor(cursor_class) as cursor:
                        rowcount = await cursor.execute(sql)

                        if cursor.description:
                            # 查询数据，返回列表
                            result = await cursor.fetchall()
                            sql_data = json.loads(
                                json.dumps([dict(row) for row in result], default=self.serializer)
                            )
                        else:
                            await conn.commit()
                            sql_data = {"count": rowcount}

                        return {
                            "sql_data": sql_data,
                            "sql_count": rowcount,
                        }
                except Exception as e:
                    await conn.rollback()
                    err_msg = f"SQL执行失败，{str(e)}"
                    self.logger.error(err_msg + f"\n{traceback.format_exc()}")
                    raise Exception(err_msg)
        elif pool_cls_name == 'SessionPool':
            def _oracle_execute():
                # 同步函数，线程池子里执行
                conn = pool.acquire()
                cursor = conn.cursor()
                try:
                    cursor.execute(sql)
                    if cursor.description:
                        # 获取列名
                        colums = [desc[0] for desc in cursor.description]
                        rows = cursor.fetchall()
                        if is_dict:
                            # 组装字典
                            result = []
                            for row in rows:
                                row_dict = {}
                                for i, col in enumerate(colums):
                                    row_dict[col] = row[i]
                                result.append(row_dict)
                            data = json.loads(json.dumps(result, default=self.serializer))
                        else:
                            data = rows
                        rowcount = len(rows)
                    else:
                        conn.commit()
                        data = {"count": cursor.rowcount}
                        rowcount = cursor.rowcount
                    return data, rowcount
                except Exception as e:
                    conn.rollback()
                    raise e
                finally:
                    cursor.close()
                    conn.close()

            try:
                sql_data, sql_count = await loop.run_in_executor(None, _oracle_execute)
                return {"sql_data": sql_data, "sql_count": sql_count}
            except Exception as e:
                err_msg = f"执行sql失败，{str(e)}"
                self.logger.error(err_msg + f"\n{traceback.format_exc()}")
                raise Exception(err_msg)

    @staticmethod
    def serializer(obj):
        """json序列化处理"""
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, date):
            return obj.strftime("%Y-%m-%d")
        elif isinstance(obj, time):
            return obj.strftime("%H:%M:%S")
        elif isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(obj, bytes):
            return obj.decode('utf-8')
        else:
            raise TypeError(f"数据{obj}类型[{type(obj)}]无法完成序列化")

    async def _close_single_pool(self, pool):
        # 关闭单个池子
        if hasattr(pool, 'close') and hasattr(pool, 'wait_closed'):
            pool.close()
            await pool.wait_closed()
        elif hasattr(pool, 'close'):
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, pool.close)

    async def close(self, app_id: Optional[str] = None):
        """关闭连接池"""
        if app_id:
            app_id_key = app_id.strip()
            if app_id_key in self.pools:
                for env in list(self.pools[app_id_key].keys()):
                    for config_name in list(self.pools[app_id_key][env].keys()):
                        for db_name, pool in list(self.pools[app_id_key][env][config_name].items()):
                            await self._close_single_pool(pool)
                            self.logger.info(f"连接池已关闭，[{app_id_key}/{env}{config_name}/{db_name}]")

                del self.pools[app_id_key]
        else:
            # 关闭全部
            for app_id_key in list(self.pools.keys()):
                for env in list(self.pools[app_id_key].keys()):
                    for config_name in list(self.pools[app_id_key][env].keys()):
                        for db_name, pool in list(self.pools[app_id_key][env][config_name].items()):
                            await self._close_single_pool(pool)

            self.pools.clear()

    def get_status(self):
        """获取当前状态"""
        return {
            "pools": self.pools,  # 成功连接
            "errors": self.errors  # 失败记录
        }

    async def get_or_create_pool(self, app_id: str, env: str, config_name: str, db_name: str) -> Any:
        """
        根据参数获取连接池对象，有则直接返回，没有先提示，在去配置表查询创建，创建成功后返回
        """
        app_id_key = app_id.strip()
        env_clean = env.lower().strip()
        config_clean = config_name.lower().strip()
        db_clean = db_name.lower().strip()
        # 1、尝试获取已有连接池
        pool = self._get_pool(app_id_key, env_clean, config_clean, db_clean)
        if pool:
            return pool

        # 2、没有连接池，不存在则自动创建
        create_success = await self.connection(app_id, env, config_name, db_name)

        pool = self._get_pool(app_id_key, env_clean, config_clean, db_clean)
        if pool:
            return pool
        # 3、创建失败，查错误信息抛异常
        err_msg = self._get_error(app_id_key, env_clean, config_clean, db_clean)
        raise ConnectionError(f"连接池创建失败，错误信息：{err_msg}")

    def _get_error(self, app_id: str, env: str, config_name: str, db_name: str) -> Optional[str]:
        # 获取指定配置的错误信息
        try:
            return self.errors[app_id][env][config_name][db_name]
        except KeyError:
            return None


def get_app_database_pool() -> "DBConnPoolFromConfig":
    """
    返回绑定自动化环境配置表的单例连接池管理器（首次调用时注入 Tortoise 模型）。
    """
    from backend.applications.aotutest.models.autotest_model import AutoTestApiEnvConfigInfo

    return DBConnPoolFromConfig(config_model=AutoTestApiEnvConfigInfo)
