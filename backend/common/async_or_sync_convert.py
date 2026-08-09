# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : async_or_sync_convert
@DateTime: 2026/1/27 16:38
"""
from __future__ import annotations

import asyncio
import asyncio as aio
import inspect
import sys
import threading
from typing import Callable, Union, Coroutine, Any, Type, Awaitable, Optional

AnyCallable = Callable[..., Any]
AnyException = Union[Exception, Type[Exception]]
AnyCoroutine = Coroutine[Any, Any, Any]

PY39_VERSION = sys.version_info[:2] >= (3, 9)


async def sync_to_async(func, *args, **kwargs):
    """
    将同步函数放入线程池异步执行。

    :param func: 同步可调用对象
    :param args: 位置参数
    :param kwargs: 关键字参数
    :return: 同步函数的返回值
    """
    if PY39_VERSION:
        return await asyncio.to_thread(func, *args, **kwargs)
    else:
        pool = AsyncEventLoopContextIOPool.singleton
        if not pool:
            pool = AsyncEventLoopContextIOPool()
        return await pool.loop.run_in_executor(None, lambda: func(*args, **kwargs))


def async_to_sync(coroutine: Awaitable, *args, **kwargs):
    """
    在新建事件循环中同步执行协程。

    :param coroutine: 可等待协程对象
    :param args: 保留位置参数，当前未使用
    :param kwargs: 保留关键字参数，当前未使用
    :return: 协程执行结果
    """

    async def inner_async_function(*args, **kwargs):
        """包装并等待传入的协程。"""
        return await coroutine

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(inner_async_function(*args, **kwargs))
    loop.close()
    return result


class AsyncEventLoopContextIOPool:
    """
    进程内单例异步IO池，供Celery同步worker投递并执行协程。

    独立线程长期运行event loop；run将协程经run_coroutine_threadsafe投递到该loop，
    保证Tortoise/aiomysql等绑定同一loop，避免跨loop Future错误。
    """
    loop: aio.AbstractEventLoop
    loop_runner: threading.Thread
    singleton: Optional["AsyncEventLoopContextIOPool"] = None

    def __new__(cls, *args: Any, **kwargs: Any) -> "AsyncEventLoopContextIOPool":
        """
        创建或返回进程内单例实例。

        :return: AsyncEventLoopContextIOPool单例
        """
        if not isinstance(cls.singleton, cls):
            cls.singleton = super(AsyncEventLoopContextIOPool, cls).__new__(cls)
        return cls.singleton

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        初始化事件循环并在守护线程中run_forever。

        :param args: 保留位置参数
        :param kwargs: 保留关键字参数
        :raises SystemError: 当前线程已存在正在运行的事件循环
        """
        try:
            # 检查是否已有运行中的事件循环
            aio.get_running_loop()
            raise SystemError("此线程中已存在一个正在运行的循环！")
        except RuntimeError:
            pass

        # 设置池的限制
        self.limit = 1

        # 创建新的事件循环
        self.loop = aio.new_event_loop()

        # 在独立线程中运行事件循环
        self.loop_runner = threading.Thread(
            target=self.loop.run_forever,
            name="celery-worker-async-loop",
            daemon=True,
        )

        self.loop_runner.start()

        # 主线程：设置当前线程的事件循环（供主线程侧 get_event_loop 使用）
        aio.set_event_loop(self.loop)

        # 池线程：必须在「跑协程的线程」里也 set_event_loop，否则 Tortoise/aiomysql 在池线程里
        # 用 get_event_loop() 会拿到别的 loop，导致 Pool._wakeup 等 Future 绑定到错误 loop，引发
        # "Task got Future attached to a different loop"
        _done = threading.Event()

        def _set_loop_in_pool_thread():
            """在池线程内绑定当前event loop。"""
            aio.set_event_loop(self.loop)
            _done.set()

        self.loop.call_soon_threadsafe(_set_loop_in_pool_thread)
        _done.wait(timeout=2.0)

    def run(self, task_function: Union[AnyCallable, AnyCoroutine], *args: Any, **kwargs: Any) -> Any:
        """
        在池线程event loop中执行协程或可调用，主线程阻塞等待完成。

        :param task_function: 协程、协程函数或普通可调用
        :param args: 传给协程函数或可调用的位置参数
        :param kwargs: 传给协程函数或可调用的关键字参数
        :return: 任务执行结果；若结果仍可等待则递归run
        """
        # 若是 async 函数，先调用得到协程
        if inspect.iscoroutinefunction(task_function):
            task_function = task_function(*args, **kwargs)

        # 如果是普通函数，使用 asyncio.to_thread 转换为协程
        if callable(task_function) and not bool(inspect.iscoroutine(task_function) or aio.isfuture(task_function)):
            task_function = aio.to_thread(task_function, *args, **kwargs)

        # 如果不可等待，直接返回
        if not inspect.isawaitable(task_function):
            return task_function

        try:
            # 在事件循环中运行协程
            result: aio.Future = aio.run_coroutine_threadsafe(task_function, self.loop)
        except TypeError:
            return task_function

        # 检查是否有异常
        if error := result.exception():
            raise error

        # 递归处理结果（可能返回另一个可等待对象）
        return self.run(result.result())

    @classmethod
    def run_in_pool(cls, task_function: Union[AnyCallable, AnyCoroutine], *args: Any, **kwargs: Any) -> Any:
        """
        使用进程单例池执行任务；无单例时先创建。

        :param task_function: 协程、协程函数或普通可调用
        :param args: 位置参数
        :param kwargs: 关键字参数
        :return: 任务执行结果
        """
        if not (worker_pool := cls.singleton):
            worker_pool = cls()

        return worker_pool.run(task_function, *args, **kwargs)

    @classmethod
    def reset_process_state(cls) -> None:
        """
        清空进程内单例，供Celery prefork子进程worker_process_init调用。

        fork后池线程不会复制，沿用父进程singleton会导致协程投递到无人驱动的loop；
        清空后子进程首次run_in_pool会新建池与loop线程。
        """
        cls.singleton = None

    async def shutdown(self) -> None:
        """
        停止事件循环并关闭异步生成器。

        :return: None
        """
        if self.loop.is_running():
            self.loop.stop()
            await self.loop.shutdown_asyncgens()

        closer = getattr(self.loop, "aclose", None)
        if not self.loop.is_closed() and callable(closer):
            await closer()

    def join(self) -> None:
        """
        等待事件循环线程结束。

        :return: None
        """
        self.loop_runner.join()
