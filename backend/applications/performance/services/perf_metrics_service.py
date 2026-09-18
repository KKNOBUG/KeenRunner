# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_metrics_service.py
@DateTime: 2026/9/14 11:20
"""
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.applications.performance.services.perf_report_crud import PerfReportCrud
from backend.common.request.request_async_utils import HttpxClient
from backend.configure import LOGGER, PROJECT_CONFIG
from backend.core.exceptions import ParameterException

# 总口径序列名: 与 locust_engine/metrics_push.py 的 TOTAL_SERIES_NAME 逐字一致
TOTAL_SERIES_NAME = "total"

# Prometheus指标名清单, 与 locust_engine/metrics_push.py 的 METRIC_* 及 host_monitor.py 的 METRIC_HOST_* 双向锚定;
# 引擎子包禁止import backend(gevent红线), 因此两侧独立声明, 变更时必须同步
# (前端同步点: usePerfMetrics.js 的 PERF_METRIC_META)
PERF_METRIC_NAMES = (
    "krun_perf_current_users",
    "krun_perf_rps",
    "krun_perf_failure_rate",
    "krun_perf_requests_total",
    "krun_perf_failures_total",
    "krun_perf_avg_latency_ms",
    "krun_perf_p95_latency_ms",
    "krun_perf_host_cpu_percent",
    "krun_perf_host_memory_percent",
    "krun_perf_host_net_sent_kb_s",
    "krun_perf_host_net_recv_kb_s",
)

# VictoriaMetrics查询端点: 从写入地址派生(同一实例, 标准部署下写入与查询同端口同前缀)
VM_WRITE_PATH_SUFFIX = "/api/v1/import/prometheus"
VM_QUERY_PATH = "/api/v1/query_range"
VM_HEALTH_PATH = "/health"
VM_HTTP_TIMEOUT = 10.0
# 健康探活短超时: 诊断端点需快速反馈, 不能等满查询超时
VM_PROBE_TIMEOUT = 3.0
# 窗口长度与缺省步长的采样点配比(窗口秒数/采样点数)
QUERY_TARGET_POINTS = 120
QUERY_WINDOW_FALLBACK_SECONDS = 600


class PerfMetricsService:

    @staticmethod
    async def query_report_metrics(
            report_code: str,
            metrics: Optional[List[str]] = None,
            start: Optional[int] = None,
            end: Optional[int] = None,
            step: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        查询压测报告指标曲线：代理VictoriaMetrics query_range, 单次正则选择器请求拉取全部指标序列。

        VictoriaMetrics未配置或不可达时返回available=False与空序列(不抛异常),
        由前端提示指标服务不可用, 压测报告静态数据不受影响。

        :param report_code: 报告业务标识
        :param metrics: 指标名列表(缺省返回全部指标)
        :param start: 窗口起始Unix秒级时间戳(缺省取报告起始时间)
        :param end: 窗口结束Unix秒级时间戳(缺省取报告结束时间, 执行中取当前时间)
        :param step: 采样步长秒数(缺省按窗口长度自适应)
        :return: {"available": 是否可用, "series": {指标名: [{time, value}]},
                  "series_by_name": {指标名: {接口名: [{time, value}]}}, "reason": 不可用原因}
                  series 为总口径(name=total 或历史无name维度), series_by_name 按被测接口分组
        """
        requested_metrics: List[str] = list(metrics) if metrics else list(PERF_METRIC_NAMES)
        invalid_metrics = [name for name in requested_metrics if name not in PERF_METRIC_NAMES]
        if invalid_metrics:
            error_message: str = f"查询压测指标失败, 非法指标名: {invalid_metrics}"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        report = await PerfReportCrud().get_by_code(report_code=report_code, on_error=True, state__not=1)

        now_ts: int = int(time.time())
        start_ts: int = start if start is not None else (
            int(report.started_time.timestamp()) if report.started_time else now_ts - QUERY_WINDOW_FALLBACK_SECONDS
        )
        end_ts: int = end if end is not None else (
            int(report.finished_time.timestamp()) if report.finished_time else now_ts
        )
        if start_ts >= end_ts:
            error_message: str = "查询压测指标失败, 窗口起始时间必须早于结束时间"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        step_seconds: int = step or max((end_ts - start_ts) // QUERY_TARGET_POINTS, 1)

        vm_base_url: str = PerfMetricsService._derive_vm_base_url()
        if not vm_base_url:
            return {"available": False, "reason": "VictoriaMetrics地址未配置", "series": {}, "series_by_name": {}}

        # PromQL正则选择器: 一次请求按__name__正则匹配拉取全部目标指标序列, 避免循环远程请求
        name_pattern = "|".join(requested_metrics)
        query = f'{{__name__=~"{name_pattern}", report_code="{report_code}"}}'
        try:
            async with HttpxClient(timeout=VM_HTTP_TIMEOUT) as client:
                utils = await client.get(
                    url=f"{vm_base_url}{VM_QUERY_PATH}",
                    params={"query": query, "start": start_ts, "end": end_ts, "step": step_seconds},
                )
                payload = await utils.json_resp()
        except Exception as e:
            LOGGER.error(f"VictoriaMetrics指标查询失败, 异常描述: {e}")
            return {"available": False, "reason": f"指标服务不可达: {e}", "series": {}, "series_by_name": {}}

        series, series_by_name = PerfMetricsService._normalize_query_response(payload, requested_metrics)
        return {"available": True, "reason": "", "series": series, "series_by_name": series_by_name}

    @staticmethod
    def _derive_vm_base_url() -> str:
        """
        从VictoriaMetrics写入地址派生查询基地址(剥离写入端点路径, 保留协议与主机端口)。

        :return: 查询基地址, 未配置或非本实例写入端点时返回空串
        """
        push_url: str = str(getattr(PROJECT_CONFIG, "PERF_VICTORIA_METRICS_URL", "") or "").strip().rstrip("/")
        if not push_url.endswith(VM_WRITE_PATH_SUFFIX):
            return ""
        return push_url[: -len(VM_WRITE_PATH_SUFFIX)]

    @staticmethod
    async def probe_availability() -> Dict[str, Any]:
        """
        探测指标服务可用性: 配置检查 + GET /health 健康端点短超时探活(诊断端点与曲线页共用)。

        :return: {"configured": 是否配置写入地址, "base_url": 查询基地址(未配置为None),
                  "reachable": 是否可达(未配置时为None), "latency_ms": 探活耗时(不可达为None),
                  "reason": 不可用原因(可用时为空串)}
        """
        base_url: str = PerfMetricsService._derive_vm_base_url()
        if not base_url:
            return {
                "configured": False, "base_url": None, "reachable": None,
                "latency_ms": None, "reason": "VictoriaMetrics写入地址未配置或非标准写入端点",
            }
        probe_started = time.perf_counter()
        try:
            async with HttpxClient(timeout=VM_PROBE_TIMEOUT) as client:
                utils = await client.get(url=f"{base_url}{VM_HEALTH_PATH}")
                await utils.text_resp()
        except Exception as e:
            LOGGER.warning(f"VictoriaMetrics健康探活失败, 基地址: {base_url}, 异常描述: {e}")
            return {
                "configured": True, "base_url": base_url, "reachable": False,
                "latency_ms": None, "reason": f"指标服务不可达: {e}",
            }
        latency_ms = round((time.perf_counter() - probe_started) * 1000, 1)
        return {"configured": True, "base_url": base_url, "reachable": True, "latency_ms": latency_ms, "reason": ""}

    @staticmethod
    def _normalize_query_response(
            payload: Dict[str, Any],
            metrics: List[str],
    ) -> Tuple[Dict[str, List[Dict[str, float]]], Dict[str, Dict[str, List[Dict[str, float]]]]]:
        """
        归一化VictoriaMetrics query_range响应为前端图表序列结构。

        name label 为 total 或缺省(本轮之前的历史报告无接口维度)时归入总口径,
        其余按接口名分组; 单点脏数据跳过, 不影响其余采样点。

        :param payload: VM原始响应({"status", "data": {"result": [...]}})
        :param metrics: 本次请求的指标名列表
        :return: (总口径序列 {指标名: [{time, value}]}, 分接口序列 {指标名: {接口名: [点]}})
        """
        series: Dict[str, List[Dict[str, float]]] = {name: [] for name in metrics}
        series_by_name: Dict[str, Dict[str, List[Dict[str, float]]]] = {name: {} for name in metrics}
        if not isinstance(payload, dict) or payload.get("status") != "success":
            return series, series_by_name
        for item in payload.get("data", {}).get("result", []):
            metric_name = (item.get("metric") or {}).get("__name__", "")
            if metric_name not in series:
                continue
            points: List[Dict[str, float]] = []
            for timestamp, value in item.get("values", []):
                try:
                    points.append({"time": int(timestamp), "value": float(value)})
                except (TypeError, ValueError):
                    continue
            series_name = str((item.get("metric") or {}).get("name") or TOTAL_SERIES_NAME)
            if series_name == TOTAL_SERIES_NAME:
                series[metric_name] = points
            else:
                series_by_name[metric_name][series_name] = points
        return series, series_by_name
