# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : celery_base
@DateTime: 2026/1/25 16:25

Celery worker 基座：进程内 Tortoise ORM 的初始化/探活/断连重建，以及跨异步边界的轻量上下文容器。
"""
from __future__ import annotations

import threading
from contextlib import suppress
from contextvars import ContextVar
from typing import Any, Dict

from tortoise import Tortoise, connections
from tortoise.exceptions import DBConnectionError

from backend.configure import PROJECT_CONFIG, LOGGER

# 全局变量，标记数据库是否已初始化
_tortoise_orm_initialized = False
# prefork 子进程内可能有多个线程同时触发初始化，用锁串行化避免重复 Tortoise.init 互相覆盖连接池
_init_threading_safe_lock = threading.Lock()


def reset_tortoise_orm_state() -> None:
    """
    重置Tortoise初始化标记，供Celery worker_process_init在prefork子进程中调用。

    :return: None
    """
    global _tortoise_orm_initialized
    _tortoise_orm_initialized = False


async def init_tortoise_orm() -> None:
    """
    在当前running loop所在线程中初始化Tortoise，并做连接可用性检查。

    已初始化时先执行 SELECT 1 探活：探活成功直接返回（避免每个任务重复 init）；
    探活失败或连接池缺失则关闭旧连接后重建。锁保证同进程内并发调用串行执行。

    :return: None
    :raises RuntimeError: 数据库主机不可达等连接失败
    """
    global _tortoise_orm_initialized

    with _init_threading_safe_lock:
        if _tortoise_orm_initialized:
            try:
                conn = connections.get("default")
                if conn and hasattr(conn, "_pool") and conn._pool:
                    try:
                        await conn.execute_query("SELECT 1")
                        return
                    except Exception:
                        LOGGER.warning("【Celery-Worker】数据库连接已断开，将重新初始化")
                        _tortoise_orm_initialized = False
                        with suppress(Exception):
                            await Tortoise.close_connections()
                else:
                    _tortoise_orm_initialized = False
            except Exception as e:
                LOGGER.warning(
                    f"【Celery-Worker】【span_id={get_span_id_for_log()}】数据库连接检查失败，将重新初始化: {str(e)}"
                )
                _tortoise_orm_initialized = False
                with suppress(Exception):
                    await Tortoise.close_connections()

        config: Dict[str, Any] = {
            "connections": PROJECT_CONFIG.DATABASE_CONNECTIONS,
            "apps": {
                "models": {
                    "models": PROJECT_CONFIG.APPLICATIONS_MODELS,
                    "default_connection": "default",
                }
            },
            "use_tz": False,
            "timezone": "Asia/Shanghai",
        }

        try:
            await Tortoise.init(config=config)
            _tortoise_orm_initialized = True
            LOGGER.info("【Celery-Worker】Tortoise ORM 数据库连接初始化成功")
        except DBConnectionError as e:
            LOGGER.error(f"【Celery-Worker】数据库连接失败: {str(e)}")
            raise RuntimeError(f"数据库连接失败, 请检查主机地址是否可达: {str(e)}")
        except Exception as e:
            LOGGER.error(f"【Celery-Worker】数据库初始化失败: {str(e)}")
            raise


def ensure_tortoise_orm_initialized() -> None:
    """
    同步封装，在池的loop中执行init_tortoise_orm()。

    供 Celery 同步钩子（如 worker 启动、信号处理）调用；初始化失败只记录日志，
    不向调用方抛出，避免启动钩子因数据库瞬断直接崩溃（任务执行时仍会再次尝试初始化）。

    :return: None
    """
    from backend.common import AsyncEventLoopContextIOPool

    try:
        AsyncEventLoopContextIOPool.run_in_pool(init_tortoise_orm())
    except Exception as e:
        LOGGER.error(f"【Celery-Worker】确保数据库初始化失败: {str(e)}")


def get_span_id_for_log() -> str:
    """
    从Worker上下文获取span_id，用于Celery业务日志定位。

    优先取请求上下文（HTTP/任务透传）中的 span_id，缺失或为占位符"-"时回落本地 ContextVar。

    :return: span_id字符串；不可用时返回空串
    """
    from backend.common.request_context import get_span_id

    sid = get_span_id()
    if sid and sid != "-":
        return sid
    return getattr(LOCAL_CONTEXT_VAR, "span_id", None) or ""


class LocalContextVar:
    """
    基于ContextVar的轻量上下文，供Celery链路传递trace_id/span_id。

    字典式读写：属性访问从 ContextVar 中当前协程的字典取值；写入采用 copy-on-write 整体替换，
    不在原字典上原地修改，避免并发协程互相污染。
    注意：__getattr__ 未命中返回 None 而非抛 AttributeError，因此 hasattr 恒为 True，
    调用方需按真值判断而不是用 hasattr 探测。
    """

    __slots__ = ("_storage",)

    def __init__(self) -> None:
        """
        初始化ContextVar存储。

        必须用 object.__setattr__ 直接写 slot：本类重写了 __setattr__，普通赋值会被拦截并
        试图从 _storage 取值，而此刻 _storage 尚未建立。

        :return: None
        """
        object.__setattr__(self, "_storage", ContextVar("local_storage"))

    def __getattr__(self, name: str) -> Any:
        """
        读取上下文中的属性。

        :param name: 属性名
        :return: 属性值；不存在时返回None
        """
        try:
            return self._storage.get({})[name]
        except KeyError:
            return None

    def __setattr__(self, name: str, value: Any) -> None:
        """
        写入上下文属性。

        复制当前字典后整体 set 回 ContextVar：ContextVar 按对象身份隔离，原地修改原字典
        会同时影响其他协程持有的引用，因此采用 copy-on-write 替换。

        :param name: 属性名
        :param value: 属性值
        :return: None
        """
        values = self._storage.get({}).copy()
        values[name] = value
        self._storage.set(values)


# 进程内共享的上下文单例：按 ContextVar 隔离，不同任务协程读到的值互不可见
LOCAL_CONTEXT_VAR = LocalContextVar()
