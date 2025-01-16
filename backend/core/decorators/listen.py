# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : listen.py
@DateTime: 2025/1/16 21:08
"""
import asyncio
import functools
import time


def retry(retries: int = 3, delay: float = 1):
    # 校验重拾的参数，参数值不正确时使用默认参数
    if retries < 1 or delay <= 0:
        retries, delay = 3, 1

    def _retry_wrapper(func):
        # 同步循环
        @functools.wraps(func)
        def _sync_wrapper(*args, **kwargs):
            for count in range(1, retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if count + 1 == retries:
                        print(f"{func.__name__}(): 执行失败，已重新尝试{count}次, 错误描述: {repr(e)}")
                        break
                    else:
                        print(f"{func.__name__}(): 执行失败，将再{delay}秒后进行第{count}次重试, 错误描述: {repr(e)}")
                        time.sleep(delay)

        @functools.wraps(func)
        async def _async_wrapper(*args, **kwargs):
            for count in range(1, retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if count + 1 == retries:
                        print(f"{func.__name__}(): 执行失败，已重新尝试{count}次, 错误描述: {repr(e)}")
                        break
                    else:
                        print(f"{func.__name__}(): 执行失败，将再{delay}秒后进行第{count}次重试, 错误描述: {repr(e)}")
                        await asyncio.sleep(delay)

        return _async_wrapper if asyncio.iscoroutinefunction(func) else _sync_wrapper

    return _retry_wrapper
