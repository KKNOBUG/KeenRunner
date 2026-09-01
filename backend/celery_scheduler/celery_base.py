# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : celery_base
@DateTime: 2026/1/27 16:25
"""
from __future__ import annotations

import threading
from contextvars import ContextVar
from typing import Any, Awaitable, Coroutine, Dict, Union

from tortoise import Tortoise, connections
from tortoise.exceptions import DBConnectionError

from backend.configure import PROJECT_CONFIG, LOGGER

# 全局变量，标记数据库是否已初始化
_tortoise_orm_initialized = False
_init_threading_safe_lock = threading.Lock()


def reset_tortoise_orm_state() -> None:
    """
    重置Tortoise初始化标记，供Celery worker_process_init在prefork子进程中调用。

    :return: None
    """
    global _tortoise_orm_initialized
    _tortoise_orm_initialized = False


def run_async(func: Union[Coroutine, Awaitable]) -> Any:
    """
    在Celery任务同步上下文中执行异步协程，统一投递到池的event loop。

    :param func: 待执行的协程对象
    :return: 协程执行结果
    """
    from backend.common import AsyncEventLoopContextIOPool
    return AsyncEventLoopContextIOPool.run_in_pool(func)


async def init_tortoise_orm() -> None:
    """
    在当前running loop所在线程中初始化Tortoise，并做连接可用性检查。

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
                        try:
                            await Tortoise.close_connections()
                        except Exception:
                            pass
                else:
                    _tortoise_orm_initialized = False
            except Exception as e:
                LOGGER.warning(
                    f"【Celery-Worker】【span_id={get_span_id_for_log()}】数据库连接检查失败，将重新初始化: {str(e)}"
                )
                _tortoise_orm_initialized = False
                try:
                    await Tortoise.close_connections()
                except Exception:
                    pass

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
    """

    __slots__ = ("_storage",)

    def __init__(self) -> None:
        """
        初始化ContextVar存储。

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

        :param name: 属性名
        :param value: 属性值
        :return: None
        """
        values = self._storage.get({}).copy()
        values[name] = value
        self._storage.set(values)


LOCAL_CONTEXT_VAR = LocalContextVar()
