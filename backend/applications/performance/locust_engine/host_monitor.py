# -*- coding: utf-8 -*-
"""
施压机主机资源采集上报(locust 子进程内运行, 禁止 import backend 主包)。

以 gevent greenlet 周期读取 psutil 的 CPU/内存/网卡指标并按 Prometheus 文本格式
推送至 PERF_VM_URL, 回答"压测机本身是否成为瓶颈"——无自监控时把压测机资源打满
误判为被测系统瓶颈是高频事故。单机多进程模式下 master 与 workers 同机,
在非 worker 角色采集即可代表整机(与 MetricsPusher 的角色约束一致);
跨机分布式施压时每台 worker 机需各自采集, 属阶段三后续子项。

指标为 gauge 快照与 counter 差分, 无接口维度, 统一挂 name="total" 总口径标签;
采集失败(部分平台权限受限等)静默跳过本轮, 不影响压测主流程。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : host_monitor.py
@DateTime: 2026/9/17 13:50
"""
from __future__ import annotations

import os
import re
import time
from typing import Any, List, Optional, Tuple

import gevent
import psutil
import requests
from locust.env import Environment
from locust.runners import WorkerRunner

# 环境变量与总口径标签: 复用 metrics_push 的既有契约, 不新增环境变量
from metrics_push import (
    ENV_PUSH_INTERVAL,
    ENV_REPORT_CODE,
    ENV_PERF_CODE,
    ENV_VM_URL,
    TOTAL_SERIES_NAME,
    DEFAULT_PUSH_INTERVAL,
    PUSH_HTTP_TIMEOUT,
    _escape_label,
)

# Prometheus指标名: 施压机资源时序(VM侧按 report_code/perf_code label 检索, 与业务指标同报告维度)
METRIC_HOST_CPU = "krun_perf_host_cpu_percent"
METRIC_HOST_MEMORY = "krun_perf_host_memory_percent"
METRIC_HOST_NET_SENT = "krun_perf_host_net_sent_kb_s"
METRIC_HOST_NET_RECV = "krun_perf_host_net_recv_kb_s"


def _is_loopback(name: str) -> bool:
    """
    判断网卡名是否为回环接口(lo/lo0/lo1...), 回环流量不代表压测链路吞吐, 采集时排除。

    :param name: 网卡名(Linux 为 lo, macOS 为 lo0)
    :return: 是否回环接口
    """
    return re.fullmatch(r"lo\d*", name) is not None


class HostResourceMonitor:
    """周期采集施压机 CPU/内存/网卡资源并推送 VictoriaMetrics 的 greenlet 封装。"""

    def __init__(
            self,
            environment: Environment,
            *,
            push_interval: float,
            vm_url: str,
            report_code: str,
            perf_code: str,
    ) -> None:
        """
        初始化监控器。

        :param environment: locust Environment实例(仅用于角色判定与生命周期挂载)
        :param push_interval: 采集上报周期(秒)
        :param vm_url: VictoriaMetrics写入地址(完整 /api/v1/import/prometheus 路径)
        :param report_code: 报告标识(指标label)
        :param perf_code: 任务标识(指标label)
        """
        self.environment = environment
        self.push_interval = push_interval
        self.vm_url = vm_url.rstrip("/")
        self.report_code = report_code
        self.perf_code = perf_code
        self._greenlet: Optional[gevent.Greenlet] = None
        self._stopped = gevent.event.Event()
        # 网卡速率差分基准: (时间戳秒, 累计发送字节, 累计接收字节); 首轮无基准跳过速率上报
        self._last_net: Optional[Tuple[float, int, int]] = None

    @classmethod
    def from_environment(cls, environment: Environment) -> Optional["HostResourceMonitor"]:
        """
        从环境变量构建监控器; VM地址为空或当前为worker角色时返回None(跳过采集)。

        worker 不采集的原因: 单机多进程时 master 的系统级采集已覆盖整机,
        各 worker 重复上报会造成同一机器指标翻倍。

        :param environment: locust Environment实例
        :return: 监控器实例或不需采集时的None
        """
        if isinstance(environment.runner, WorkerRunner):
            return None
        vm_url = os.environ.get(ENV_VM_URL, "").strip()
        if not vm_url:
            return None
        try:
            push_interval = float(os.environ.get(ENV_PUSH_INTERVAL, "").strip() or DEFAULT_PUSH_INTERVAL)
        except ValueError:
            push_interval = DEFAULT_PUSH_INTERVAL
        return cls(
            environment,
            push_interval=max(push_interval, 1.0),
            vm_url=vm_url,
            report_code=os.environ.get(ENV_REPORT_CODE, "unknown"),
            perf_code=os.environ.get(ENV_PERF_CODE, "unknown"),
        )

    def start(self) -> None:
        """启动采集greenlet(幂等); 立即建立CPU占用与网卡计数基准, 首轮上报即为有效差分。"""
        if self._greenlet is None:
            self._stopped.clear()
            psutil.cpu_percent(interval=None)
            self._snapshot_net_bytes()
            self._greenlet = gevent.spawn(self._monitor_loop)

    def stop(self) -> None:
        """停止采集greenlet(幂等)。"""
        self._stopped.set()
        if self._greenlet is not None:
            self._greenlet.join(timeout=self.push_interval + 2)
            self._greenlet = None

    def _monitor_loop(self) -> None:
        """采集主循环: 周期采集并推送, 异常静默(资源链路故障不阻断压测)。"""
        while not self._stopped.wait(self.push_interval):
            try:
                self.push_once()
            except Exception:
                # 采集/上报失败不打断压测: psutil部分平台权限受限或VM不可用时跳过本轮
                continue

    def build_payload(self) -> str:
        """
        构造 Prometheus 文本格式指标负载(带毫秒时间戳)。

        :return: 文本负载, 结构:
            krun_perf_host_cpu_percent{report_code="xxx",perf_code="yyy",name="total"} 62.5 1757826000000
        """
        base_label = f'report_code="{self.report_code}",perf_code="{self.perf_code}"'
        label = f'{base_label},name="{_escape_label(TOTAL_SERIES_NAME)}"'
        timestamp_ms = int(time.time() * 1000)
        return "\n".join(self._collect_lines(label=label, timestamp_ms=timestamp_ms)) + "\n"

    def _collect_lines(self, label: str, timestamp_ms: int) -> List[str]:
        """
        采集一轮主机资源并构造指标行; CPU/内存失败整轮跳过, 网卡失败仅跳过速率行。

        :param label: 已拼好的 label 串
        :param timestamp_ms: 采样时间戳(毫秒)
        :return: Prometheus 文本行列表
        """
        lines: List[str] = []
        cpu_percent = psutil.cpu_percent(interval=None)
        memory_percent = psutil.virtual_memory().percent
        lines.append(f"{METRIC_HOST_CPU}{{{label}}} {round(cpu_percent, 1)} {timestamp_ms}")
        lines.append(f"{METRIC_HOST_MEMORY}{{{label}}} {round(memory_percent, 1)} {timestamp_ms}")
        sent_kb_s, recv_kb_s = self._net_speed_kb_s()
        if sent_kb_s is not None and recv_kb_s is not None:
            lines.append(f"{METRIC_HOST_NET_SENT}{{{label}}} {round(sent_kb_s, 1)} {timestamp_ms}")
            lines.append(f"{METRIC_HOST_NET_RECV}{{{label}}} {round(recv_kb_s, 1)} {timestamp_ms}")
        return lines

    def _snapshot_net_bytes(self) -> Optional[Tuple[float, int, int]]:
        """
        采集累计网卡字节计数(汇总全部物理网卡, 排除回环接口)。

        :return: (时间戳秒, 累计发送字节, 累计接收字节); 采集失败为None
        """
        try:
            pernic = psutil.net_io_counters(pernic=True)
            sent = sum(stats.bytes_sent for name, stats in pernic.items() if not _is_loopback(name))
            recv = sum(stats.bytes_recv for name, stats in pernic.items() if not _is_loopback(name))
        except Exception:
            return None
        snapshot = (time.monotonic(), sent, recv)
        self._last_net = snapshot
        return snapshot

    def _net_speed_kb_s(self) -> Tuple[Optional[float], Optional[float]]:
        """
        依据累计计数差分计算网卡收发速率; 无上一轮基准时仅建立基准并返回None。

        :return: (发送速率KB/s, 接收速率KB/s), 首轮或采集失败为(None, None)
        """
        # 先取旧基准再采新值: _snapshot_net_bytes 会覆盖 _last_net, 顺序颠倒则差分恒为0
        last = self._last_net
        snapshot = self._snapshot_net_bytes()
        if snapshot is None or last is None:
            return None, None
        last_ts, last_sent, last_recv = last
        current_ts, current_sent, current_recv = snapshot
        elapsed = current_ts - last_ts
        if elapsed <= 0 or current_sent < last_sent or current_recv < last_recv:
            return None, None
        return (current_sent - last_sent) / elapsed / 1024, (current_recv - last_recv) / elapsed / 1024

    def push_once(self) -> None:
        """执行一次采集并上报; 异常向上抛出由调用方决策。"""
        payload = self.build_payload()
        response = requests.post(
            self.vm_url,
            data=payload.encode("UTF-8"),
            headers={"Content-Type": "text/plain"},
            timeout=PUSH_HTTP_TIMEOUT,
        )
        response.raise_for_status()
