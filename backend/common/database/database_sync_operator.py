# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : database_sync_operator.py
@DateTime: 2025/1/16 12:52
"""
import traceback
from typing import Union, Any, Optional
from warnings import filterwarnings

import pymysql
from pymysql.cursors import DictCursor

from backend.common.database.database_sync_pool import DatabaseSyncPool
from backend.core.decorators.block import synchronized

filterwarnings("ignore", category=pymysql.Warning)


class DatabaseSyncOperator(object):
    """
    代码设计思想：
    1.利用类属性，实例化数据库连接池
    2.使用构造器，初始化数据库连接池，获取连接对象和游标对象
    3.利用装饰器，完成上锁（同一时刻有且只有一个游标再工作）和释放锁，避免在多线程或并发时导致异常（涉及线程安全问题）
    4.利用参数化，完成防止SQL注入，支持原生SQL执行（select * from student）、关键字执行(table="student")
    5.利用封装化，完成增删改查等功能（简易版的ORM行为函数）
    """

    __connect_pool = DatabaseSyncPool()

    def __init__(self):
        self.conn: pymysql.Connection = DatabaseSyncOperator.__connect_pool.acquire_connection_object()
        self.cursor = self.conn.cursor(DictCursor)

    "用于存储该类的当一实例"
    __instance = None

    "重写父类的__new__方法，实现单例模式"

    def __new__(cls, *args, **kwargs) -> object:
        if not cls.__instance:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    @synchronized
    def execute_sql(self, sql: str, params: Optional[Union[str, list, tuple]] = None,
                    exe_many: bool = False, is_query_one: bool = False, is_query_all: bool = False) -> Any:
        """
        数据库连接对象执行SQL语句的基础方法
        :param sql:         必填参数；字符类型；SQL语句；select %s from table where column = %s 其中%s就是形参
        :param params:      非必填项；列表类型；SQL语句携带参数；单条SQL语句参数：(1,2,3...)，多条SQL语句参数：[[1,2,3...],[2,3,4...]]
        :param exe_many:    必填参数；布尔类型；默认False，是否批量执行SQL语句；True多条SQL语句，False单条SQL语句
        :param is_query_one:必填参数；布尔类型；默认False，执行SQL语句是否为查询语句；True返回fetchone，False返回受影响行数
        :param is_query_all:必填参数；布尔类型；默认False，执行SQL语句是否为查询语句；True返回fetchall，False返回受影响行数
        :return:    返回数据库连接对象conn 和数据游标cursor 及SQL语句影响行数count
        """
        execute_result = 0  # 执行结果/受影响行数
        try:
            # 开启事务
            self.cursor.execute("START TRANSACTION;")
            # 是否一次执行多条sql语句
            if exe_many:
                execute_result = self.cursor.executemany(sql, params) if params else self.cursor.executemany(sql)
            else:
                execute_result = self.cursor.execute(sql, params) if params else self.cursor.execute(sql)

            # 查询单条？返回fetchone
            if is_query_one:
                execute_result = self.cursor.fetchone()
                self.cursor.nextset()  # 每次执行sql语句后将结果集全部倒出保证游标内是空的

            # 查询所有？返回fetchall
            elif is_query_all:
                execute_result = self.cursor.fetchall()
                self.cursor.nextset()  # 每次执行sql语句后将结果集全部倒出保证游标内是空的

            print("==================================================")
            if params and len(params) > 1:
                for param in params:
                    print(f"SQL语句：{self.cursor.mogrify(query=sql, args=param)}")
                    print(f"执行SQL语句成功，受影响的行数：{execute_result}")
            else:
                print(f"SQL语句：{self.cursor.mogrify(query=sql, args=params)}")
                print(f"执行SQL语句成功，受影响的行数：{execute_result}")
            print("==================================================")

            self.conn.commit()
            return execute_result
        except Exception as e:
            print(f"执行SQL语句失败：{e}")
            print(f"执行SQL语句失败：{traceback.format_exc()}")
            self.conn.rollback()
            return execute_result

    def insert_data(self, **kwargs) -> int:
        """
        根据条件自产新增SQL语句，执行后返回影响行
        table：必填，插入表名，字符类型
        data ：必填，更新数据，字典类型
        """
        # 将插入表名以table作为键值设为必填参数
        table = kwargs["table"]
        # 将更新数据以data作为键值设为必填参数
        data = kwargs["data"]
        # 设置基础SQL语句
        sql = "insert into %s (" % table
        # 记录表字段
        fields = ""
        flag = ""
        # 记录插入的数据
        params = []
        for k, v in data.items():
            fields += "%s," % k
            params.append(str(v))
            flag += "%s,"
        fields = fields.rstrip(",")
        # 如果是字典则会产生对应字典的数据，如果是字符串则没有
        params = tuple(params)
        flag = flag.rstrip(",")
        sql += fields + ") values (" + flag + ")"
        return self.execute_sql(sql=sql, params=params)

    def delete_data(self, **kwargs) -> int:
        """
        根据条件自产删除SQL语句，执行后返回影响行
        table： 必填项，查询表名，字符串类型，如：table="test_table"
        where： 非必填，查询条件，分两种类型，如：1.字典类型用于=，如：where={"aaa": 333, "bbb": 2}；2.字符串类型用于非等于判断，如：where="aaa>=333"
        """
        # 将查询表名以table作为键值设为必填参数
        table = kwargs["table"]
        # 将查询条件以where作为键值设为必填参数
        where = kwargs["where"]
        # 基础SQL语句
        sql = "delete from %s where 1=1" % table
        # where条件携带参数
        params = []
        # 如果where参数是以字典形式携带，则表示K值=V值
        if isinstance(where, dict):
            for k, v in where.items():
                sql += " and {} in (%s)".format(k)
                params.append(str(v))
        # 如果where参数是以字符串形式携带，则直接将字符串and到SQL语句上
        elif isinstance(where, str):
            sql += " and %s" % where
        # sql += ";"
        # 如果是字典则会产生对应字典的数据，如果是字符串则没有
        params = tuple(params)
        return self.execute_sql(sql=sql, params=params)

    def update_data(self, **kwargs) -> int:
        """
        根据条件自产修改SQL语句，执行返回影响行
        table：必填项，查询表名，字符串类型，如：table="test_table"
        data ：必填项，更新数据，字典类型，如：data={"aaa": "6666", "bbb": "888"}
        where：非必填，查询条件，分两种类型，如：1.字典类型用于=，如：where={"aaa": 333, "bbb": 2}；2.字符串类型用于非等于判断，如：where="aaa>=333"
        """
        # 将查询表名以table作为键值设为必填参数
        table = kwargs["table"]
        # 将更新数据以data作为键值设为必填参数
        data = kwargs["data"]
        # 将查询条件以where作为键值设为必填参数
        where = kwargs["where"]
        # 基础SQL语句
        sql = "update %s set " % table
        # where条件携带参数
        params = []
        for k, v in data.items():
            sql += "{}=%s,".format(k)
            params.append(str(v))
        sql = sql.rstrip(",")
        sql += " where 1=1 "
        # 如果where参数是以字典形式携带，则表示K值=V值
        if isinstance(where, dict):
            for k, v in where.items():
                sql += " and {} in (%s)".format(k)
                params.append(str(v))
        # 如果where参数是以字符串形式携带，则直接将字符串and到SQL语句上
        elif isinstance(where, str):
            sql += " and %s" % where
        # sql += ";"
        # 如果是字典则会产生对应字典的数据，如果是字符串则没有
        params = tuple(params)
        return self.execute_sql(sql=sql, params=params)

    def query_one(self, **kwargs) -> tuple:
        """
        根据条件自产查询SQL语句，执行后返回第一条数据
        table：必填项，查询表名，字符串类型，如：table="test_table"
        where：非必填，查询条件，如果是字典类型表示等于，如：where={"a列": 111, "b列": 2222}；如果是字符串类型表示非等于判断，如：where="c列>=333"
        field：非必填，查询列名，字符串类型，如：field="aaa, bbb"，不填默认*
        order：非必填，排序字段，字符串类型，如：order="a列"
        sort： 非必填，排序方式，字符串类型，如：sort="asc" 或者 "desc"，不填默认asc
        """
        # 将查询表名以table作为键值设为必填参数
        table = kwargs['table']
        # 判断是否携带查询列值，如果携带则查询传递字段，否则查询所有字段
        field = "field" in kwargs and kwargs["field"] or "*"
        # 将查询条件以where作为键值设为必填参数
        where = kwargs["where"]
        # 判断是否传递order关键字参数，如果没有传递则不拼接，否则拼接order by字段
        order = "order" in kwargs and "order by " + kwargs["order"] or ""
        # 将排序方式以sort作为键值设为必填参数，默认asc
        sort = kwargs.get("sort", "asc")
        # 如果order为空则sort也设置为空
        if order == "":
            sort = ""
        # 基础SQL语句
        sql = f"select {field} from {table} where 1=1"
        # where条件携带参数
        params = []
        # 如果where参数是以字典形式携带，则表示K值=V值
        if isinstance(where, dict):
            for k, v in where.items():
                sql += " and {} in (%s)".format(k)
                params.append(str(v))
        # 如果where参数是以字符串形式携带，则直接将字符串and到SQL语句上
        elif isinstance(where, str):
            sql += f" and {where}"
        # 排序处理后筛选第1条数据
        sql += f" {order} {sort} limit 1"
        # 如果是字典则会产生对应字典的数据，如果是字符串则没有
        params = tuple(params)
        return self.execute_sql(sql=sql, params=params, is_query_one=True)

    def query_all(self, **kwargs) -> tuple:
        """
        根据条件自产查询SQL语句，执行后返回所有数据
        table： 必填项，查询表名，字符串类型，如：table="test_table"
        where： 非必填，查询条件，分两种类型，如：1.字典类型用于=，如：where={"aaa": 333, "bbb": 2}；2.字符串类型用于非等于判断，如：where="aaa>=333"
        field： 非必填，查询列名，字符串类型，如：field="aaa, bbb"，不填默认*
        order： 非必填，排序字段，字符串类型，如：order="a列"
        sort：  非必填，排序方式，字符串类型，如：sort="asc" 或者 "desc"，不填默认asc
        offset：非必填，偏移数量，如翻页，不填默认0
        limit： 非必填，查询条数，不填默认100
        """
        # 将查询表名以table作为键值设为必填参数
        table = kwargs["table"]
        # 判断是否携带查询列值，如果携带则查询传递字段，否则查询所有字段
        field = "field" in kwargs and kwargs["field"] or "*"
        # 判断是否传递order关键字参数，如果没有传递则不拼接，否则拼接order by字段
        order = "order" in kwargs and "order by " + kwargs["order"] or ""
        # 将排序方式以sort作为键值设为必填参数，默认asc
        sort = kwargs.get("sort", "asc")
        # 如果order为空则sort也设置为空
        if order == "":
            sort = ""
        # 将偏移数量以offset作为键值设为必填参数，默认0，如果查询需要分页则以offset和limit来计算
        offset = kwargs.get("offset", 0)
        # 将查询条数以limit作为键值设为必填参数，默认100
        limit = kwargs.get("limit", 100)
        # 基础SQL语句
        sql = "select %s from %s where 1=1 " % (field, table)
        # where条件携带参数
        params = []
        # 将查询条件设置为非必填项，如果使用该方法时，传递了where关键字，则根据传入的数据类型进行SQL语句处理
        if 'where' in kwargs.keys():
            where = kwargs["where"]
            # 如果where参数是以字典形式携带，则表示K值=V值
            if isinstance(where, dict):
                for k, v in where.items():
                    sql += " and {} in (%s)".format(k)
                    params.append(str(v))
            # 如果where参数是以字符串形式携带，则直接将字符串and到SQL语句上
            elif isinstance(where, str):
                sql += " and %s" % where
        # 如果是字典则会产生对应字典的数据，如果是字符串则没有
        params = tuple(params)
        # 处理SQL语句，拼接排序字段和方式以及或分页计算
        sql += " %s %s limit %s, %s" % (order, sort, offset, limit)
        return self.execute_sql(sql=sql, params=params, is_query_all=True)

    def query_count(self, **kwargs) -> int:
        """
        根据条件自产查询SQL语句，执行后返回结果行数
        :param kwargs：
                table：必填项，查询表名，字符串类型，如：table="test_table"
                where：非必填，查询条件，如果是字典类型表示等于，如：where={"a列": 111, "b列": 2222}；
                               如果是字符串类型表示非等于判断，如：where="c列>=333"
        :return:
        """
        # 将查询表名以table作为键值设为必填参数
        table = kwargs["table"]
        # 基础SQL语句
        sql = f"select count(1) as count from {table} where 1=1 "
        # 使用params列表记录where携带的条件参数
        params = []
        # 将查询条件设置为非必填项，如果传递了where关键字，则根据传入的数据类型处理
        if 'where' in kwargs.keys():
            where = kwargs["where"]
            # 如果where参数是以字典形式携带，则表示K值=V值
            if isinstance(where, dict):
                for k, v in where.items():
                    sql += " and {} in (%s)".format(k)
                    params.append(str(v))
            # 如果where参数是以字符串形式携带，则直接将字符串and到SQL语句上
            elif isinstance(where, str):
                sql += " and %s" % where
        # 如果是字典则会产生对应字典的数据，如果是字符串则没有
        params = tuple(params)
        return self.execute_sql(sql=sql, params=params, is_query_one=True)[0]

    def query_multi_tables(self, **kwargs) -> tuple:
        """
        根据条件自产查询SQL语句，执行后返回多表查询的所有数据
        tables： 必填项，查询的表名及其别名，格式为：{"main_table": "mt", "joined_table": "jt"}
        join_on： 必填项，连接条件，格式为：{"mt.field": "jt.field"}
        where： 非必填，查询条件，同query_all函数中的where参数
        fields：非必填，查询的字段列表，格式为：["mt.field1, mt.field2, jt.field3"]，不填默认选择所有字段
        order： 非必填，排序字段，同query_all函数中的order参数
        sort：  非必填，排序方式，同query_all函数中的sort参数
        offset：非必填，偏移数量，同query_all函数中的offset参数
        limit： 非必填，查询条数，同query_all函数中的limit参数
        """
        # 必填项检查
        if "tables" not in kwargs or "join_on" not in kwargs:
            raise ValueError("Both 'tables' and 'join_on' are required.")

        tables = kwargs["tables"]
        join_on = kwargs["join_on"]

        # 初始化SQL语句
        sql = "SELECT "

        # 判断是否携带查询列值，如果携带则查询传递字段，否则查询所有字段
        fields = kwargs.get("fields", ["*"])
        sql += ", ".join(fields)

        # 添加FROM和JOIN部分
        sql += " FROM " + list(tables.values())[0]  # 假设第一个表是主表
        for alias, table in tables.items():
            if alias == list(tables.keys())[0]:
                continue  # 主表已经添加
            join_field = list(join_on.keys())[0] if alias == list(join_on.keys())[0] else list(join_on.values())[0]
            sql += " JOIN " + table + " ON " + join_field

        # 添加WHERE部分
        sql += " WHERE 1=1 "
        if 'where' in kwargs:
            where = kwargs["where"]
            if isinstance(where, dict):
                for k, v in where.items():
                    # 假设k的格式为"table_alias.field"
                    table_alias, field = k.split(".")
                    sql += " AND " + table_alias + "." + field + " = %s"
                    kwargs["params"].append(v) if "params" in kwargs else kwargs.update({"params": [v]})
            elif isinstance(where, str):
                sql += " AND " + where

        # 初始化或获取params列表
        params = kwargs.get("params", [])

        # 处理排序和分页
        order = "order" in kwargs and "ORDER BY " + kwargs["order"] or ""
        sort = kwargs.get("sort", "ASC")
        offset = kwargs.get("offset", 0)
        limit = kwargs.get("limit", 100)

        sql += " " + order + " " + sort.upper() + " LIMIT %s, %s"
        params.extend([offset, limit])

        # 执行SQL查询
        return self.execute_sql(sql=sql, params=tuple(params), is_query_all=True)


if __name__ == '__main__':
    mysql_operation = DatabaseSyncOperator()

    # 验证execute_sql函数
    # execute_sql = "select * from student"
    execute_sql = "select * from student  where sno >= 110"
    # execute_sql = "update student set sname = '忠诚的矮人谢尔涅' where sno >= 116"
    result = mysql_operation.execute_sql(execute_sql, is_query_one=True)
    print('查询数量：', result)
    print('执行语句：', mysql_operation.cursor.mogrify(query=execute_sql, args=None))
    print('查询结果：', mysql_operation.cursor.fetchone())
    print('查询结果：', mysql_operation.cursor.fetchall())

    # 验证insert_data函数
    # table_data = {"sno": 116, "sname": "谢尔涅", "ssex": "男", "sbirthday": datetime.datetime.now(), "sclass": "95030"}
    # result = mysql_operation.insert_data(table="student", data=table_data)
    # print('新增结果：', result)

    # # 验证update_data函数
    # result = mysql_operation.update_data(
    #     table="student",
    #     data={"sname": "忠诚的矮人谢尔涅"},
    #     where={"sno": "116"}
    # )
    # print('修改结果：', result)

    # 验证query_one函数
    # result = mysql_operation.query_one(
    #     table="student",
    #     field="sno,sname",
    #     where={
    #         "sno": 116,
    #         "sclass": "95030"
    #     }
    # )
    # print('查询一条结果：', result)

    # 验证query_count函数
    # result = mysql_operation.query_count(table="student", where="sno between 112 and 116")
    # print('查询结果数量：', result)

    # 验证query_all函数
    # result = mysql_operation.query_all(
    #     table="student",
    #     field="sno, sname, ssex, sclass",
    #     order="sno",
    #     sort="asc"
    # )
    # print('查询全部结果：', result)

    # 验证delete_data函数
    # result = mysql_operation.delete_data(table="student", where={"sno": "116"})
    # print('删除结果：', result)
