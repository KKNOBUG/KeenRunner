# -*- coding: utf-8 -*-
"""
压测进程注册表(backend 主进程侧): 管理执行管线拉起的 locust 进程组生命周期。

以 report_code 为键登记进程集合, 支撑停止接口按批次终止进程组;
仅主进程使用, 故置于 services 而非 locust_engine 子包(引擎红线: 子包禁止
import backend)。进程登记与终止均为内存态, 服务重启后注册表随之清空。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_process_registry.py
@DateTime: 2026/9/14 14:40
"""
from __future__ import annotations

import threading
from typing import Dict, List

import psutil

from backend.configure import LOGGER

# 优雅退出等待秒数: locust对SIGTERM响应迅速, 超时进程走SIGKILL兜底
GRACEFUL_STOP_TIMEOUT = 10.0
KILL_WAIT_TIMEOUT = 3.0


class PerfProcessRegistry:
    """report_code -> locust 进程组 的线程安全注册表。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._registry: Dict[str, List[psutil.Process]] = {}

    def register(self, report_code: str, processes: List[psutil.Process]) -> None:
        """
        登记执行批次的进程集合(同批次重复注册时覆盖)。

        :param report_code: 报告标识(批次键)
        :param processes: 本批次拉起的进程列表(master与workers)
        :return: None
        """
        with self._lock:
            self._registry[report_code] = list(processes)

    def unregister(self, report_code: str) -> None:
        """
        移除批次登记(进程自然退出后由管线调用)。

        :param report_code: 报告标识
        :return: None
        """
        with self._lock:
            self._registry.pop(report_code, None)

    def stop(self, report_code: str, *, timeout: float = GRACEFUL_STOP_TIMEOUT) -> bool:
        """
        终止批次进程组: 先SIGTERM优雅退出, 超时进程SIGKILL兜底。

        :param report_code: 报告标识
        :param timeout: 优雅退出等待秒数
        :return: 是否完成终止(登记项已移除; 个别强杀失败记录日志)
        """
        with self._lock:
            processes = self._registry.pop(report_code, [])
        graceful_targets: List[psutil.Process] = []
        for process in processes:
            try:
                if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                    process.terminate()
                    graceful_targets.append(process)
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied as e:
                LOGGER.error(f"停止压测进程组[{report_code}]失败, 进程无权访问: {e}")
        _, alive = psutil.wait_procs(graceful_targets, timeout=timeout)
        for process in alive:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                continue
        psutil.wait_procs(alive, timeout=KILL_WAIT_TIMEOUT)
        return True


# 模块级单例: 执行管线与停止接口共用同一注册表实例
PERF_PROCESS_REGISTRY = PerfProcessRegistry()
