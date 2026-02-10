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
    将同步函数转换为异步函数

    :param func: 同步函数
    :param args: 位置参数
    :param kwargs: 关键字参数
    :return: 异步执行的结果
    """
    if PY39_VERSION:
        return await asyncio.to_thread(func, *args, **kwargs)
    else:
        pool = AsyncEventLoopContextIOPool.singleton
        if not pool:
            pool = AsyncEventLoopContextIOPool()
        return await pool.loop.run_in_executor(
            None, lambda: func(*args, **kwargs)
        )


def async_to_sync(coroutine: Awaitable, *args, **kwargs):
    """
    将异步协程转换为同步执行

    :param coroutine: 异步协程
    :param args: 位置参数
    :param kwargs: 关键字参数
    :return: 异步协程执行的结果
    """

    async def inner_async_function(*args, **kwargs):
        return await coroutine

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(inner_async_function(*args, **kwargs))
    loop.close()
    return result


class AsyncEventLoopContextIOPool:
    """
    自定义的异步 IO 池，用于在 Celery worker 中执行 async 函数（含 Tortoise）。

    机制简述：
    - 主线程：Celery 同步 worker 线程，不跑 event loop；通过 run(coro) 把协程投递到池。
    - 池线程：单独一条线程，target=loop.run_forever()，长期跑一个 event loop。
    - run(coro)：用 run_coroutine_threadsafe(coro, self.loop) 把协程投到池的 loop 执行，主线程
      result.result() 阻塞等待完成。
    - Tortoise/aiomysql 的连接池会绑定到「init 时 get_running_loop()/get_event_loop() 返回的 loop」，
      因此必须保证：init 与所有使用 Tortoise 的协程都在「池线程 + 池的 loop」里执行。单例保证
      进程内只有一个池、一个 loop；池线程内 set_event_loop(self.loop) 保证该线程内 get_event_loop()
      与 running loop 一致，避免依赖库拿到错误 loop。
    """
    loop: aio.AbstractEventLoop
    loop_runner: threading.Thread
    singleton: Optional["AsyncEventLoopContextIOPool"] = None

    def __new__(cls, *args: Any, **kwargs: Any) -> "AsyncEventLoopContextIOPool":
        """
        单例模式，确保每个进程只有一个 AsyncEventLoopContextIOPool 实例
        """
        if not isinstance(cls.singleton, cls):
            cls.singleton = super(AsyncEventLoopContextIOPool, cls).__new__(cls)
        return cls.singleton

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        初始化异步 IO 池
        创建一个新的事件循环并在独立线程中运行
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
            aio.set_event_loop(self.loop)
            _done.set()

        self.loop.call_soon_threadsafe(_set_loop_in_pool_thread)
        _done.wait(timeout=2.0)

    def run(self, task_function: Union[AnyCallable, AnyCoroutine], *args: Any, **kwargs: Any) -> Any:
        """
        在池线程的 event loop 中执行 task_function（协程或可调用），主线程阻塞直到完成。
        调用方（如 task_prerun、ContextTask.__call__）在同步上下文中调用，通过 run_coroutine_threadsafe
        把协程投递到 self.loop，保证所有 async 逻辑（含 Tortoise）都在同一 loop 上执行。
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
        类方法：在池中运行任务
        :param task_function: 要执行的函数或协程
        :param args: 位置参数
        :param kwargs: 关键字参数
        :return: 任务的执行结果
        """
        if not (worker_pool := cls.singleton):
            worker_pool = cls()

        return worker_pool.run(task_function, *args, **kwargs)

    @classmethod
    def reset_process_state(cls) -> None:
        """
        重置进程内单例，供 Celery worker_process_init 在 prefork 子进程里调用。
        fork 后子进程只有主线程，池的 loop_runner 线程不会复制到子进程；若沿用父进程的
        singleton，子进程内 run() 会往「无人驱动的 loop」投递协程，导致挂起或 loop 错乱。
        清空后子进程首次 run_in_pool 会新建池、新建 loop_runner 线程，并在该线程中 init Tortoise。
        """
        cls.singleton = None

    async def shutdown(self) -> None:
        """关闭 worker 池"""
        if self.loop.is_running():
            self.loop.stop()
            await self.loop.shutdown_asyncgens()

        closer = getattr(self.loop, "aclose", None)
        if not self.loop.is_closed() and callable(closer):
            await closer()

    def join(self) -> None:
        """等待循环运行线程结束"""
        self.loop_runner.join()
