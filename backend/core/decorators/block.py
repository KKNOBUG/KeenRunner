# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : block.py
@DateTime: 2025/1/16 12:48
"""
import functools
import threading


# 单例模式装饰器
def singleton(cls):
    # 使用字典存储类对象的实例
    instances = {}

    @functools.wraps(cls)
    def _singleton(*args, **kwargs):
        if cls not in instances:
            # 如果类没有被创建过，那就new个新对象并存储到字典中
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return _singleton


# 锁状态装饰器
def synchronized(func):
    lock = threading.Lock()

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # 利用上下文管理器，保证上锁和释放锁
        with lock:
            return func(*args, **kwargs)

    return wrapper
