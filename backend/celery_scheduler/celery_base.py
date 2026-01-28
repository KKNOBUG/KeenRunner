# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : celery_base
@DateTime: 2026/1/27 16:25
"""
import asyncio
import threading
from contextvars import ContextVar
from typing import Dict, Any, Union, Coroutine, Awaitable, Iterator, Tuple

from tortoise import Tortoise, connections
from tortoise.exceptions import DBConnectionError

from backend import PROJECT_CONFIG, LOGGER

# 全局变量，标记数据库是否已初始化
_tortoise_orm_initialized = False
_init_threading_safe_lock = threading.Lock()


def run_async(func: Union[Coroutine, Awaitable]) -> Any:
    """
    异步函数调用辅助函数, 用于在 Celery 任务中执行异步函数
    :param func: 协程或可等待对象
    :return: 异步函数的执行结果
    """
    try:
        # 单线程模式
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(func)
    except Exception as err:
        # 如果没有事件循环，创建新的
        asyncio.set_event_loop(asyncio.new_event_loop())
        return asyncio.run(func)


async def init_tortoise_orm() -> None:
    """
    初始化 Tortoise ORM 数据库连接

    这个函数确保在 Celery worker 中 Tortoise ORM 已正确初始化
    如果已经初始化，则检查连接是否可用
    """
    global _tortoise_orm_initialized

    # 使用线程锁保护初始化过程
    with _init_threading_safe_lock:
        # 如果已经初始化，检查连接是否可用
        if _tortoise_orm_initialized:
            try:
                # 尝试获取连接来验证连接是否可用
                conn = connections.get("default")
                if conn and hasattr(conn, '_pool') and conn._pool:
                    try:
                        # 连接池存在，尝试执行一个简单查询来验证连接
                        await conn.execute_query("SELECT 1")
                        return
                    except Exception:
                        # 连接可能已断开，需要重新初始化
                        LOGGER.warning("数据库连接已断开，将重新初始化")
                        _tortoise_orm_initialized = False
                        try:
                            await Tortoise.close_connections()
                        except:
                            pass
                else:
                    # 连接池不存在，需要初始化
                    _tortoise_orm_initialized = False
            except Exception as e:
                LOGGER.warning(f"数据库连接检查失败，将重新初始化: {str(e)}")
                _tortoise_orm_initialized = False
                try:
                    # 关闭现有连接
                    await Tortoise.close_connections()
                except:
                    pass

        # 初始化数据库配置
        config: Dict[str, Any] = {
            "connections": PROJECT_CONFIG.DATABASE_CONNECTIONS,
            "apps": {
                "models": {
                    "models": PROJECT_CONFIG.APPLICATIONS_MODELS,
                    "default_connection": "default"
                }
            },
            "use_tz": False,
            "timezone": "Asia/Shanghai",
        }

        try:
            # 初始化 Tortoise ORM
            # 注意：如果已经初始化过，Tortoise.init 会重新初始化
            await Tortoise.init(config=config)
            _tortoise_orm_initialized = True
            LOGGER.info("Tortoise ORM 数据库连接初始化成功")
        except DBConnectionError as e:
            LOGGER.error(f"数据库连接失败: {str(e)}")
            raise RuntimeError(f"数据库连接失败, 请检查主机地址是否可达: {str(e)}")
        except Exception as e:
            LOGGER.error(f"数据库初始化失败: {str(e)}")
            raise


def ensure_tortoise_orm_initialized():
    """
    同步函数：确保数据库已初始化
    在异步任务执行前调用，使用 AsyncIOPool 来执行异步初始化

    这个函数在 task_prerun 信号中被调用，确保每次任务执行前数据库连接可用
    """
    from backend.common.async_or_sync_convert import AsyncEventLoopContextIOPool

    try:
        # 使用 AsyncIOPool 执行异步初始化
        # 注意：这里传递的是协程对象，AsyncIOPool.run_in_pool 会处理它
        AsyncEventLoopContextIOPool.run_in_pool(init_tortoise_orm())
    except Exception as e:
        LOGGER.error(f"确保数据库初始化失败: {str(e)}")
        # 不抛出异常，让任务继续执行，但记录错误
        # 如果数据库连接真的有问题，任务执行时会再次报错


class LocalContextVar:
    """
    基于 ContextVar 的本地上下文变量类
    用于在异步环境中传递上下文信息（如 trace_id）
    """
    __slots__ = ("_storage",)

    def __init__(self) -> None:
        object.__setattr__(self, "_storage", ContextVar("local_storage"))

    def __iter__(self) -> Iterator[Tuple[int, Any]]:
        return iter(self._storage.get({}).items())

    def __release_local__(self) -> None:
        self._storage.set({})

    def __getattr__(self, name: str) -> Any:
        values = self._storage.get({})
        try:
            return values[name]
        except KeyError:
            return None

    def __setattr__(self, name: str, value: Any) -> None:
        values = self._storage.get({}).copy()
        values[name] = value
        self._storage.set(values)

    def __delattr__(self, name: str) -> None:
        values = self._storage.get({}).copy()
        try:
            del values[name]
            self._storage.set(values)
        except KeyError:
            ...


LOCAL_CONTEXT_VAR = LocalContextVar()
