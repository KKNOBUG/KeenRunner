# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : database_async_pool.py
@DateTime: 2025/1/12 19:55
"""
import asyncio
import aiomysql
import json
from datetime import date, time, datetime
from decimal import Decimal
from typing import Dict, Any, Optional

from backend.configure.database_config import DATABASES


class DatabaseAsyncPool:
    """
    数据库异步连接池类，用于管理多层次多环境的数据库连接并允许指定游标执行SQL语句

    该类使用单例模式确保整个应用程序中只有一个实例，通过连接池管理数据库的连接对象
    提供了数据库的连接、连接对象的复用、执行SQL语句等功能。

    """
    # 用于存储该类的唯一实例
    __private_instance = None
    __private_initialized = False

    def __new__(cls, *args, **kwargs) -> object:
        """
        创建并返回类的唯一实例
        使用单例模式，确保在整个应用程序的生命周期内只有一个`DatabaseAsyncPool`实例

        :param args: 位置参数
        :param kwargs: 关键字参数
        :return: `DatabaseAsyncPool`类的实例
        """
        if cls.__private_instance is None and cls.__private_initialized is False:
            cls.__private_instance = super().__new__(cls)
            cls.__private_initialized = True
        return cls.__private_instance

    def __init__(self, database_config: Dict[str, Dict[str, Any]], *args, **kwargs):
        """
        初始化 `DatabaseAsyncPool` 实例
        :param database_config: 数据库配置信息，是一个字典，包含不同环境不同类别不同分片分区的数据库连接信息
        :param args: 位置参数
        :param kwargs: 关键字参数
        """
        super(DatabaseAsyncPool, self).__init__(*args, **kwargs)
        self.database_config: dict = database_config
        self.database_object: dict = {}
        self.database_errors: dict = {}

    async def connection(self, env: str, tos: str, zone: Optional[str] = None) -> bool:
        """
        根据给定的环境、类别和分区信息建立数据库连接。
        :param env: 环境名称，必须是非空字符串
        :param tos: 类别名称，必须是非空字符串
        :param zone: 分区名称，可选参数，如未提供则为`None`，类型为字符串。
        :return: 如果建立连接成功则返回`True`，否则返回`False`
        :raise ValueError: 如果 `env` 或 `tos` 不是非空字符串，或者 `env`、`tos` 或 `zone` 不在预定义的配置中
        """
        # 检查[env-tos]参数是否正确上送
        if not env or not isinstance(env, str) or not tos or not isinstance(tos, str):
            raise ValueError(f"环境[env]和类别[tos]必须是非空字符串")

        # 将参数转换为小写（提高容错率）
        env, tos = env.lower(), tos.lower()
        if zone:
            zone.lower()

        # 检查[env-tos-zone]参数是否存在于配置清单中
        if env not in self.database_config or tos not in self.database_config[env]:
            raise ValueError(f"环境[{env}]和类别[{tos}]必须是预定义信息")

        # 获取[env-tos]对应的数据库配置信息
        assign_tos_databases: dict = self.database_config[env][tos]

        # 初始化数据库连接对象的存储结构
        if env not in self.database_object:
            self.database_object[env] = {}
        if tos not in self.database_object:
            self.database_object[env][tos] = {}

        # 检查[env-tos-zone]对应的数据库是否已经成功建立连接
        # 场景1:未指定zone参数，为[env-tos]下所有的分区分片创建数据库连接对象
        if not zone and not self.database_object[env][tos]:
            for zone_name, zone_values in assign_tos_databases.items():
                for db_name, db_values in zone_values.items():
                    await self._create_database_pool(
                        items=db_values, env=env, tos=tos, zone=zone_name, name=db_name
                    )
            return True

        # 场景2:已指定zone参数，为[env-tos-zone]下所有的分片创建数据库连接对象
        if zone and zone not in assign_tos_databases:
            raise ValueError(f"环境[{env}]和类别[{tos}]和分区[{zone}]必须是预定义信息")

        if zone and zone not in self.database_object[env][tos]:
            for db_name, db_values in assign_tos_databases[zone]:
                await self._create_database_pool(
                    items=db_values, env=env, tos=tos, zone=zone, name=db_name
                )
            return True

        return False

    async def _create_database_pool(self, items: dict, env: str, tos: str, zone: str, name: str):
        """
        创建数据库连接池并存储在相应的结构中
        :param items: 数据库配置项的字典，包含`host`、`port`、`username`、`password`、`database`等信息
        :param env: 环境名称
        :param tos: 类别名称
        :param zone: 分区名称
        :param name: 数据库名称
        :return: None
        :raise Exception: 如果创建数据库连接池对象时发生意外错误
        """
        try:
            database_object: aiomysql = await aiomysql.create_pool(
                minsize=1,
                maxsize=10,
                connect_timeout=60,
                pool_recycle=3600,
                charset="utf8mb4",
                host=items["host"],
                port=items["port"],
                user=items["username"],
                password=items["password"],
                db=items["databases"],
            )
            self.database_object.setdefault(env, {}).setdefault(tos, {}).setdefault(zone, {})[name] = database_object
        except Exception as e:
            DatabaseAsyncPool.__private_initialized = False
            self.database_errors.setdefault(env, {}).setdefault(tos, {}).setdefault(zone, {})[name] = e.__str__()

    @staticmethod
    def serializer(obj):
        """
        将特定类型的对象序列化为可JSON序列化的格式
        :param obj: 要序列化的对象
        :return: 序列化后的对象
        :raise ValueError: 如果对象不在预先定义的对象转换中则抛出异常
        """
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, date):
            return obj.strftime("%Y-%m-%d")
        elif isinstance(obj, time):
            return obj.strftime("%H-%M-%S")
        elif isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H-%M-%S")
        elif isinstance(obj, bytes):
            return obj.decode("utf-8")
        else:
            raise ValueError(f"类型:[{type(obj)}]无法完成序列化")

    async def assign_tos_execute_sql(self, env: str, tos: str, sql: str):
        """
        在指定环境和类别的所有数据库实例上执行给定的SQL语句
        :param env: 环境名称
        :param tos: 类别名称
        :param sql: 待执行的SQL语句
        :return: 一个包含所有数据库实例执行结果的列表
        """
        tasks: list = []
        env, tos = env.lower(), tos.lower()
        await self.connection(env=env, tos=tos)
        assign_tos_databases = self.database_object[env][tos]

        for zone_name, zone_values in assign_tos_databases.items():
            for db_name, db_values in zone_values.items():
                task = asyncio.create_task(
                    self.execute_sql(env=env, tos=tos, zone=zone_name, name=db_name, pooled=db_values, sql=sql)
                )
                tasks.append(task)
        result = await asyncio.gather(*tasks, return_exceptions=True)

        return result

    async def execute_sql(self, env: str, tos: str, zone: str, name: str, pooled, sql: str, dict_cursor: bool = True):
        """
        在指定的数据库连接上执行SQL语句
        :param env: 环境名称
        :param tos: 类别名称
        :param zone: 分区名称
        :param name: 数据库名称
        :param pooled: 数据库连接池对象
        :param sql: 待执行SQL语句
        :param dict_cursor: 是否使用字典游标，默认为`True`
        :return: 包含执行结果的字典
        :raise Exception: 如果执行过程中发生意外错误则抛出异常
        """
        try:
            async with pooled.acquire() as conn:
                # await conn.ping() # 连接池在获取连接时已确保连接有效，因此无需显式调用 ping()，减少额外延迟。
                cursor_class = aiomysql.cursors.DictCursor if dict_cursor else aiomysql.cursors.Cursor
                async with conn.cursor(cursor_class) as cursor:
                    rowcount = await cursor.execute(sql)
                    # 使用 cursor.description 判断是否有结果集，避免对非查询语句（如INSERT/UPDATE）调用 fetchall()，防止错误
                    if cursor.description:
                        result = await cursor.fetchall()
                        data = json.loads(json.dumps([dict(row) for row in result], default=self.serializer))

                    else:
                        await conn.commit()
                        data = json.loads(json.dumps({"count": rowcount}, default=self.serializer))
                return {"env": env, "tos": tos, "zone": zone, "name": name, "data": data}
        except Exception as e:
            raise RuntimeError(f"执行SQL时发生错误: {e}") from e


DATABASE_ASYNC_POOL = DatabaseAsyncPool(DATABASES)
