# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : database_sync_pool.py
@DateTime: 2025/1/16 12:45
"""
import dbutils
import pymysql
from dbutils.pooled_db import PooledDB

from backend.core.decorators.block import singleton


class DatabaseSyncPool(object):
    __pool: PooledDB = None

    def __init__(self):
        self.to_mysql: dict = {
            'host': "",
            'user': "",
            'port': "",
            'password': "",
            'database': ""
        }

    def __enter__(self):
        """
        上下文管理（开始），使用本类实例时自动执行本方法；获取数据库连接对象、游标
        :return:
        """
        self.conn: dbutils.pooled_db.PooledDedicatedDBConnection = self.__acquire_connection_object()
        self.cursor: dbutils.steady_db.SteadyDBCursor = self.conn.cursor()

    def __acquire_connection_object(self):
        """
        创建数据库连接池（私有方法）
        :return: 数据库连接对象
        """
        if self.__pool is None:
            try:
                self.__pool = PooledDB(
                    creator=pymysql,  # 连接数据库模块
                    mincached=10,  # 启动时开启的闲置连接量（默认值0，默认不创建）
                    maxcached=30,  # 连接池中允许的闲置连接量（默认值0，默认不闲置）
                    maxshared=50,  # 共享连接量允许的最大数量
                    maxconnections=100,  # 创建连接池中最大数量
                    blocking=True,  # 设置在连接池达到最大数量时的行为（阻塞）
                    maxusage=100,  # 单个连接的最大允许复用次数
                    setsession=[],  # 一个可选的SQL命令列表用于每个会话前的准备操作
                    ping=True,  # ping MySQL服务端，检查是否服务可用
                    use_unicode=True,  # 使用编码
                    charset="utf8",  # 设定编码
                    **self.to_mysql  # 密钥信息
                )
            except pymysql.err.OperationalError:
                raise ConnectionError(f"请检查数据库连接信息：{self.to_mysql}")
            except Exception as e:
                raise ConnectionError(f"数据库连接出现意外错误：{e}")
        return self.__pool.connection()

    # 释放连接池资源
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        上下文管理（结束），本类实例使用完毕或一定时间内没有活跃时执行；关闭游标、数据库连接对象
        :param exc_type:
        :param exc_val:
        :param exc_tb:
        :return:
        """
        try:
            self.cursor.close()
            self.conn.close()
        except Exception as e:
            pass

    @singleton
    def acquire_connection_object(self):
        """
        从数据库连接池中取出一个闲置数据库连接对象
        :return: 游标、数据库连接对象
        """
        __conn = self.__acquire_connection_object()
        return __conn


if __name__ == '__main__':
    mysql1 = DatabaseSyncPool()
    conn1 = mysql1.acquire_connection_object()
    print("是否连接成功1：", conn1)
    print("对象唯一标识1：", id(conn1))

    mysql2 = DatabaseSyncPool()
    conn2 = mysql2.acquire_connection_object()
    print("是否连接成功2：", conn2)
    print("对象唯一标识2：", id(conn2))
