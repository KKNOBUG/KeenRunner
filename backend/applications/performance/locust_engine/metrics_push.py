# -*- coding: utf-8 -*-
"""
VictoriaMetrics 指标推送(locust 子进程内运行, 禁止 import backend 主包)。

以 gevent greenlet 周期读取 Locust runner 统计并按 Prometheus 文本格式
推送至 PERF_VM_URL(VictoriaMetrics /api/v1/import/prometheus 端点);
分布式 worker 角色不上报(统计由 master 聚合, 避免重复计数),
VM 地址为空时整体跳过。上报失败静默跳过本轮, 不影响压测主流程。

统计维度: 除总口径(name="total")外, 同时按 locust stats entry 逐接口上报
(name="方法 路径模板"), 多被测步骤场景下前端可按接口筛曲线; 当前用户数仅总口径有意义。
每条序列带 role 标签(measured/transaction/verify, 准备段为独立序列 role=prepare,
准备请求不进 locust 统计), 前端实时页据此拆分业务/事务/抽查/准备四类曲线;
被测接口序列附加 api_code/transaction 标签供曲线归因(由施压入口传入序列标签索引)。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : metrics_push.py
@DateTime: 2026/9/14 14:40
"""
from __future__ import annotations

import os
import time
from typing import Any, List, Optional, Tuple

import gevent
import requests
from locust.env import Environment

# 兜底角色推导用的记账方法名与角色取值: 与 perf_locustfile 的 ROLE_*/METHOD_* 逐字一致
# (perf_locustfile 单向依赖本模块, 不可反向import)
METHOD_TRANSACTION = "TX"
METHOD_VERIFY = "VFY"
ROLE_LABEL_MEASURED = "measured"
ROLE_LABEL_TRANSACTION = "transaction"
ROLE_LABEL_VERIFY = "verify"
ROLE_LABEL_PREPARE = "prepare"

# 环境变量契约: 由backend执行管线在启动locust子进程前注入
ENV_VM_URL = "PERF_VM_URL"
ENV_PUSH_INTERVAL = "PERF_METRICS_PUSH_INTERVAL"
ENV_REPORT_CODE = "PERF_REPORT_CODE"
ENV_PRESET_CODE = "PERF_PRESET_CODE"

# Prometheus指标名: 压测核心时序指标(VM侧按 report_code/preset_code label 检索绘制曲线)
METRIC_CURRENT_USERS = "krun_perf_current_users"
METRIC_RPS = "krun_perf_rps"
METRIC_FAILURE_RATE = "krun_perf_failure_rate"
METRIC_TOTAL_REQUESTS = "krun_perf_requests_total"
METRIC_TOTAL_FAILURES = "krun_perf_failures_total"
METRIC_AVG_LATENCY = "krun_perf_avg_latency_ms"
METRIC_P95_LATENCY = "krun_perf_p95_latency_ms"

DEFAULT_PUSH_INTERVAL = 5.0
PUSH_HTTP_TIMEOUT = 5
# 总口径的 name label 取值(与分接口曲线同指标名下区分同一时间序列)
TOTAL_SERIES_NAME = "total"
# 无接口归因的统计行名(locust 内部占位, 不上报)
UNNAMED_STATS = "--"


def _escape_label(value: Any) -> str:
    """
    转义 Prometheus label 值中的反斜杠与双引号。

    :param value: 原始 label 值(接口统计名等用户数据)
    :return: 可安全嵌入 label 花括号的字符串
    """
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"')


class MetricsPusher:
    """周期推送 locust 统计到 VictoriaMetrics 的 greenlet 封装。"""

    def __init__(
            self,
            environment: Environment,
            *,
            push_interval: float,
            vm_url: str,
            report_code: str,
            preset_code: str,
            series_labels: Optional[Dict[Tuple[str, str], Dict[str, str]]] = None,
            prepare_metrics: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        初始化推送器。

        :param environment: locust Environment实例(读runner统计)
        :param push_interval: 上报周期(秒)
        :param vm_url: VictoriaMetrics写入地址(完整 /api/v1/import/prometheus 路径)
        :param report_code: 报告标识(指标label)
        :param preset_code: 负载预设标识(指标label)
        :param series_labels: 统计行名到附加label的索引, 键为(name, method),
            值含 role/api_code/transaction(施压入口构建, 引擎内归因唯一来源)
        :param prepare_metrics: 准备段指标注册表(引用, 施压入口持续累计, role=prepare 独立序列上报)
        """
        self.environment = environment
        self.push_interval = push_interval
        self.vm_url = vm_url.rstrip("/")
        self.report_code = report_code
        self.preset_code = preset_code
        self.series_labels = series_labels or {}
        self.prepare_metrics = prepare_metrics or {}
        self._greenlet: Optional[gevent.Greenlet] = None
        self._stopped = gevent.event.Event()

    @classmethod
    def from_environment(
            cls,
            environment: Environment,
            *,
            series_labels: Optional[Dict[Tuple[str, str], Dict[str, str]]] = None,
            prepare_metrics: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> Optional["MetricsPusher"]:
        """
        从环境变量构建推送器; VM地址为空或当前为worker角色时返回None(跳过上报)。

        :param environment: locust Environment实例
        :param series_labels: 统计行名到附加label的索引(透传)
        :param prepare_metrics: 准备段指标注册表(透传)
        :return: 推送器实例或不需上报时的None
        """
        from locust.runners import WorkerRunner

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
            preset_code=os.environ.get(ENV_PRESET_CODE, "unknown"),
            series_labels=series_labels,
            prepare_metrics=prepare_metrics,
        )

    def start(self) -> None:
        """启动上报greenlet(幂等)。"""
        if self._greenlet is None:
            self._stopped.clear()
            self._greenlet = gevent.spawn(self._push_loop)

    def stop(self) -> None:
        """停止上报greenlet(幂等); 最后一次推送交由test_stop前的常规周期完成。"""
        self._stopped.set()
        if self._greenlet is not None:
            self._greenlet.join(timeout=self.push_interval + 2)
            self._greenlet = None

    def _push_loop(self) -> None:
        """上报主循环: 周期推送, 异常静默(指标链路故障不阻断压测)。"""
        while not self._stopped.wait(self.push_interval):
            try:
                self.push_once()
            except Exception:
                # 上报失败不打断压测: 网络抖动/VM不可用时跳过本轮, 下一周期重试
                continue

    def build_payload(self) -> str:
        """
        构造 Prometheus 文本格式指标负载(带毫秒时间戳)。

        总口径与逐接口口径共用指标名, 由 name label 区分; 活跃用户数只属于全局量。

        :return: 文本负载, 结构:
            krun_perf_rps{report_code="xxx",preset_code="yyy",name="total"} 12.5 1757826000000
            krun_perf_rps{report_code="xxx",preset_code="yyy",name="POST /api/users"} 8.1 1757826000000
        """
        runner = self.environment.runner
        base_label = f'report_code="{self.report_code}",preset_code="{self.preset_code}"'
        timestamp_ms = int(time.time() * 1000)
        user_count = getattr(runner, "user_count", 0) or 0
        lines: List[str] = [
            f"{METRIC_CURRENT_USERS}{{{base_label},name=\"{TOTAL_SERIES_NAME}\"}} {user_count} {timestamp_ms}",
        ]
        for series_name, entry in self._iter_entries():
            label = f'{base_label}{self._role_labels(series_name, entry)},name="{_escape_label(series_name)}"'
            lines.extend(self._build_entry_lines(entry=entry, label=label, timestamp_ms=timestamp_ms))
        lines.extend(self._build_prepare_lines(base_label=base_label, timestamp_ms=timestamp_ms))
        return "\n".join(lines) + "\n"

    def _role_labels(self, series_name: str, entry: Any) -> str:
        """
        构造单条统计序列的role归因label(业务吞吐/事务/抽查三条曲线的拆分依据)。

        :param series_name: 统计行名
        :param entry: locust StatsEntry
        :return: 可直接拼接的label串, 如 ',role="measured",api_code="PERF-API-xxx"'
        """
        info = self.series_labels.get((series_name, str(entry.method)))
        if info is None:
            # 未登记序列的兜底推导(与施压入口登记口径一致)
            if entry.method == METHOD_TRANSACTION:
                role = ROLE_LABEL_TRANSACTION
            elif entry.method == METHOD_VERIFY:
                role = ROLE_LABEL_VERIFY
            else:
                role = ROLE_LABEL_MEASURED
            return f',role="{role}"'
        labels = f',role="{info.get("role") or ROLE_LABEL_MEASURED}"'
        if info.get("api_code"):
            labels += f',api_code="{_escape_label(info["api_code"])}"'
        if info.get("transaction"):
            labels += f',transaction="{_escape_label(info["transaction"])}"'
        return labels

    def _build_prepare_lines(self, base_label: str, timestamp_ms: int) -> List[str]:
        """
        构造准备段独立序列(role=prepare): 准备请求不进locust统计, 以引擎本地计数上报。

        :param base_label: 已拼好的报告/任务label串
        :param timestamp_ms: 采样时间戳(毫秒)
        :return: Prometheus 文本行列表
        """
        lines: List[str] = []
        for metric in self.prepare_metrics.values():
            attempts = int(metric.get("attempts") or 0)
            label = (
                f'{base_label},role="{ROLE_LABEL_PREPARE}",'
                f'name="{_escape_label(metric.get("name"))}"'
            )
            avg_rt = round((metric.get("total_rt_ms") or 0) / attempts, 2) if attempts else 0
            lines.append(f"{METRIC_TOTAL_REQUESTS}{{{label}}} {attempts} {timestamp_ms}")
            lines.append(f"{METRIC_TOTAL_FAILURES}{{{label}}} {int(metric.get('failures') or 0)} {timestamp_ms}")
            lines.append(f"{METRIC_AVG_LATENCY}{{{label}}} {avg_rt} {timestamp_ms}")
        return lines

    def _iter_entries(self) -> List[Tuple[str, Any]]:
        """
        待上报的统计序列(总口径 + 逐接口), 接口名取序保证多次推送序列结构一致。

        :return: [(序列名, StatsEntry)], 首位固定为 ("total", stats.total)
        """
        stats = self.environment.runner.stats
        named_entries = [
            (str(entry.name), entry) for entry in stats.entries.values()
            if entry.name and str(entry.name) != UNNAMED_STATS
        ]
        named_entries.sort(key=lambda item: item[0])
        return [(TOTAL_SERIES_NAME, stats.total), *named_entries]

    @staticmethod
    def _build_entry_lines(entry: Any, label: str, timestamp_ms: int) -> List[str]:
        """
        构造单条统计序列的指标行。

        :param entry: locust StatsEntry(总口径或单接口)
        :param label: 已拼好的 label 串(含 name)
        :param timestamp_ms: 采样时间戳(毫秒)
        :return: Prometheus 文本行列表
        """
        try:
            p95_latency = entry.get_response_time_percentile(0.95)
        except Exception:
            p95_latency = 0
        return [
            f"{METRIC_RPS}{{{label}}} {entry.current_rps or 0} {timestamp_ms}",
            f"{METRIC_FAILURE_RATE}{{{label}}} {entry.fail_ratio or 0} {timestamp_ms}",
            f"{METRIC_TOTAL_REQUESTS}{{{label}}} {entry.num_requests} {timestamp_ms}",
            f"{METRIC_TOTAL_FAILURES}{{{label}}} {entry.num_failures} {timestamp_ms}",
            f"{METRIC_AVG_LATENCY}{{{label}}} {entry.avg_response_time or 0} {timestamp_ms}",
            f"{METRIC_P95_LATENCY}{{{label}}} {p95_latency or 0} {timestamp_ms}",
        ]

    def push_once(self) -> None:
        """执行一次上报; 网络异常向上抛出由调用方决策。"""
        payload = self.build_payload()
        response = requests.post(
            self.vm_url,
            data=payload.encode("UTF-8"),
            headers={"Content-Type": "text/plain"},
            timeout=PUSH_HTTP_TIMEOUT,
        )
        response.raise_for_status()
