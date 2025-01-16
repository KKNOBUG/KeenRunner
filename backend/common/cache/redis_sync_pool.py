# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : redis_sync_pool.py
@DateTime: 2025/1/14 15:30
"""
import json
from typing import Optional, Union, List, Any, Dict

import redis
import pickle
from redis.exceptions import RedisError


class RedisSyncPool:
    """
    RedisSyncPool 类用于管理 Redis 连接池并提供常用的 Redis 操作方法。
    """

    def __init__(self, dbid: Optional[str] = None) -> None:
        """
        初始化 RedisSyncPool 实例。

        :param dbid: Redis 数据库 ID，默认为 "0"。
        """
        self.dbid = dbid or "0"
        self.pool = {}
        self.reds = self.charge_pool(dbid=self.dbid)

    def charge_pool(self, dbid: str) -> redis.Redis:
        """
        创建或获取 Redis 连接池。

        :param dbid: Redis 数据库 ID。
        :return: Redis 实例。
        """
        if dbid not in self.pool:
            self.pool[dbid] = redis.ConnectionPool(
                db=dbid,
                host='localhost',
                port=6379,
                password='',
                decode_responses=True,
            )
        return redis.Redis(connection_pool=self.pool[dbid])

    def charge_dbid(self, dbid: str) -> None:
        """
        更改当前使用的 Redis 数据库 ID。

        :param dbid: 新的 Redis 数据库 ID。
        """
        if dbid != self.dbid:
            self.dbid = dbid
            self.reds = self.charge_pool(dbid=dbid)

    def clear_redis_conn(self, isall: bool = False) -> bool:
        """
        清空 Redis 数据库。

        :param isall: 如果为 True，清空所有数据库；否则清空当前数据库。
        :return: 操作成功返回 True，失败返回 False。
        """
        try:
            return self.reds.flushall() if isall else self.reds.flushdb()
        except RedisError as e:
            print(f"Error clearing Redis connection: {e}")
            return False

    def key_exists(self, key: str) -> bool:
        """
        检查键是否存在。

        :param key: 键名。
        :return: 如果键存在返回 True，否则返回 False。
        """
        try:
            return self.reds.exists(key) > 0
        except RedisError as e:
            print(f"Error checking existence of key {key}: {e}")
            return False

    def set_expire(self, key: str, time: int) -> bool:
        """
        设置键的过期时间。

        :param key: 键名。
        :param time: 过期时间（秒）。
        :return: 操作成功返回 True，失败返回 False。
        """
        try:
            return self.reds.expire(key, time)
        except RedisError as e:
            print(f"Error setting expiration on key {key}: {e}")
            return False

    def increment_value(self, key: str, amount: int = 1) -> int:
        """
        增加键的整数值。

        :param key: 键名。
        :param amount: 增加的数量，默认为 1。
        :return: 增加后的值。
        """
        try:
            return self.reds.incr(key, amount)
        except RedisError as e:
            print(f"Error incrementing value for key {key}: {e}")
            return 0

    def del_keys(self, *keys: str) -> int:
        """
        删除一个或多个键。

        :param keys: 键名。
        :return: 被删除的键的数量。
        """
        try:
            return self.reds.delete(*keys)
        except RedisError as e:
            print(f"Error deleting keys from Redis: {e}")
            return 0

    def get_all_keys(self, pattern: str = "*") -> List[str]:
        """
        获取匹配模式的所有键。

        :param pattern: 匹配模式，默认为 "*"。
        :return: 匹配的键列表。
        """
        try:
            return self.reds.keys(pattern=pattern)
        except RedisError as e:
            print(f"Error retrieving keys from Redis: {e}")
            return []

    def get_list_keys(self, pattern: str = "*", count: int = 10, cursor: int = 0) -> List[str]:
        """
        分页列出匹配模式的所有键。

        :param pattern: 匹配模式，默认为 "*"。
        :param count: 每次扫描返回的键数量，默认为 10。
        :param cursor: 游标，默认为 0。
        :return: 匹配的键列表。
        """
        try:
            keys = []
            while cursor != 0 or not keys:
                cursor, keys = self.reds.scan(cursor=cursor, match=pattern, count=count)
            return keys
        except RedisError as e:
            print(f"Error listing keys from Redis: {e}")
            return []

    def set_str(self, key: str, value: Union[int, str], time: Optional[int] = None) -> bool:
        """
        设置字符串值。

        :param key: 键名。
        :param value: 键值，可以是字符串或整数。
        :param time: 可选，过期时间（秒）。
        :return: 操作成功返回 True，失败返回 False。
        """
        try:
            if time:
                return self.reds.setex(name=key, value=value, time=time)
            return self.reds.set(name=key, value=value)
        except RedisError as e:
            print(f"Error setting value in Redis: {e}")
            return False

    def get_str(self, key: str) -> Optional[Any]:
        """
        获取字符串值。

        :param key: 键名。
        :return: 键值，如果不存在则返回 None。
        """
        try:
            return self.reds.get(key)
        except RedisError as e:
            print(f"Error getting value from Redis: {e}")
            return None

    def set_list(self, key: str, values: List[Any]) -> bool:
        """
        存储列表。

        :param key: 键名。
        :param values: 列表值。
        :return: 操作成功返回 True，失败返回 False。
        """
        try:
            return self.reds.rpush(key, *values) > 0
        except RedisError as e:
            print(f"Error setting list for key {key}: {e}")
            return False

    def get_list(self, key: str) -> List[Any]:
        """
        获取列表。

        :param key: 键名。
        :return: 列表值，如果不存在则返回空列表。
        """
        try:
            return self.reds.lrange(key, 0, -1)
        except RedisError as e:
            print(f"Error getting list for key {key}: {e}")
            return []

    def set_set(self, key: str, values: List[Any]) -> bool:
        """
        存储集合。

        :param key: 键名。
        :param values: 集合值。
        :return: 操作成功返回 True，失败返回 False。
        """
        try:
            return self.reds.sadd(key, *values) > 0
        except RedisError as e:
            print(f"Error setting set for key {key}: {e}")
            return False

    def get_set(self, key: str) -> List[Any]:
        """
        获取集合。

        :param key: 键名。
        :return: 集合值，如果不存在则返回空列表。
        """
        try:
            return list(self.reds.smembers(key))
        except RedisError as e:
            print(f"Error getting set for key {key}: {e}")
            return []

    def set_dict(self, key: str, value: Dict[str, Any]) -> Optional[Any]:
        """
        存储字典。

        :param key: 键名。
        :param value: 字典值。
        :return: 操作成功返回 True，失败返回 False。
        """
        try:
            return self.reds.hset(key, mapping=value)
        except RedisError as e:
            print(f"Error setting dict for key {key}: {e}")
            return None

    def get_dict(self, key: str) -> Dict[str, Any]:
        """
        获取字典。

        :param key: 键名。
        :return: 字典值，如果不存在则返回空字典。
        """
        try:
            return self.reds.hgetall(key)
        except RedisError as e:
            print(f"Error getting dict for key {key}: {e}")
            return {}

    def set_object(self, key: str, obj: Any) -> bool:
        """
        存储对象（序列化为 JSON）。

        :param key: 键名。
        :param obj: 对象。
        :return: 操作成功返回 True，失败返回 False。
        """
        try:
            pickle_data = pickle.dumps(obj)
            return self.reds.set(key, pickle_data)
        except RedisError as e:
            print(f"Error setting object for key {key}: {e}")
            return False

    def get_object(self, key: str) -> Any:
        """
        获取对象（反序列化 JSON）。

        :param key: 键名。
        :return: 对象，如果不存在则返回 None。
        """
        try:
            pickle_data = self.reds.get(key)
            return pickle.loads(pickle_data) if pickle_data else None
        except RedisError as e:
            print(f"Error getting object for key {key}: {e}")
            return None


if __name__ == "__main__":
    import time

    # 创建 RedisSyncPool 实例
    redis_pool = RedisSyncPool(dbid="0")

    # 测试设置值
    print("设置值：", redis_pool.set_str("test_key", "Hello, Redis!", time=60))

    # 测试获取值
    print("获取值：", redis_pool.get_str("test_key"))

    # 测试检查键是否存在
    print("键是否存在：", redis_pool.key_exists("test_key"))

    # 测试增加值
    print("增加值：", redis_pool.increment_value("counter_key", 5))

    # 测试获取增加后的值
    print("获取增加后的值：", redis_pool.get_str("counter_key"))

    # 测试存储列表
    print("存储列表：", redis_pool.set_list("my_list", [1, 2, 3, 4, 5]))
    print("获取列表：", redis_pool.get_list("my_list"))

    # 测试存储集合
    print("存储集合：", redis_pool.set_set("my_set", ["a", "b", "c"]))
    print("获取集合：", redis_pool.get_set("my_set"))

    # 测试存储字典
    print("存储字典：", redis_pool.set_dict("my_dict", {"name": "Alice", "age": 30}))
    print("获取字典：", redis_pool.get_dict("my_dict"))

    # 测试存储对象
    print("存储对象：", redis_pool.set_object("my_object", {"key": "value", "number": 42}))
    print("获取对象：", redis_pool.get_object("my_object"))

    # 测试删除值
    print("删除值：", redis_pool.del_keys("test_key"))

    # 测试清空 Redis 数据库
    print("清空 Redis 数据库：", redis_pool.clear_redis_conn(isall=False))

    # 测试获取所有键
    print("获取所有键：", redis_pool.get_all_keys())
