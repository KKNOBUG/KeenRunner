# -*- coding: utf-8 -*-
import asyncio
from collections import deque


class AdaptiveSemaphore:
    """自适应信号量：根据历史任务响应时间动态调整异步并发上限。"""

    # 调整目标是平衡系统吞吐量与稳定性：响应快则放大并发，响应慢则收缩并发

    def __init__(self, max_concurrent: int = 5, min_concurrent: int = 2, max_history_length: int = 10):
        """
        初始化自适应信号量。

        :param max_concurrent: 最大并发数
        :param min_concurrent: 最小并发数
        :param max_history_length: 保存的历史响应时间最大数量
        """
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
        self.min_concurrent = min_concurrent
        self.max_history_length = max_history_length
        self.response_times = deque(maxlen=max_history_length)
        self.lock = asyncio.Lock()

    async def adjust_concurrent(self, response_time: float):
        # 使用异步锁保证调整逻辑的原子性，避免多协程同时修改
        async with self.lock:
            # 将新的响应时间加入历史队列
            self.response_times.append(response_time)

            # 通过计算历史平均消耗时间，得出最新的最大并发数
            avg_time = sum(self.response_times) / len(self.response_times)
            new_max = min(self.max_concurrent, max(self.min_concurrent, int(180 / (avg_time + 1e-6))))

            # 当计算出新并发数量时则更新信号量
            if new_max != self.max_concurrent:
                self.max_concurrent = new_max
                self.semaphore = asyncio.Semaphore(new_max)

    def get_status(self):
        return {
            'max_concurrent': self.max_concurrent,
            'response_times': list(self.response_times)
        }
