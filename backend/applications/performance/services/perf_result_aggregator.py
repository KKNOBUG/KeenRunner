# -*- coding: utf-8 -*-
"""
压测结果分片合并与报告聚合(backend 主进程侧, Celery 管线在引擎退出后调用)。

引擎各进程在 test_stop 时各写一份 result_{pid}.json 分片(多进程下 master 不写),
本模块把分片合并为报告口径: 统计行按 (name, method) 聚合、错误按归因键累加、
蓄水池样本直接拼接(各分片样本对全局仍是均匀随机样本, 拼接后分位数无偏)、
准备段按统计名累加。延迟类指标一律由合并样本剔除 warmup 后计算(真分位),
Locust 直方图值仅存 locust_stats 快照供交叉校验。

口径常量(事务前缀/抽查方法)与 locust_engine/perf_locustfile 独立双声明:
引擎子包禁止 import backend, 反向复用 perf_locustfile 又会触发 locust/gevent
导入(主进程禁入), 故两侧字面量同步维护。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_result_aggregator.py
@DateTime: 2026/9/16 16:40
"""
import operator
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.applications.performance.locust_engine.reservoir import (
    COLUMN_NAME,
    COLUMN_OK,
    COLUMN_RT,
    COLUMN_TS,
    compute_percentile,
    compute_std_dev,
)
from backend.enums import (
    PERF_MIN_DURATION_FOR_SLA,
    PERF_MIN_SAMPLES_FOR_COMPARE,
    PerfApiRole,
    PerfTargetOp,
)

# 事务统计行名前缀与手工记账方法(与 locust_engine/perf_locustfile.py 双声明同步维护)
TRANSACTION_NAME_PREFIX = "transaction:"
METHOD_VERIFY = "VFY"

# SLA 比较运算符映射(与 PerfTargetOp 枚举值一致)
_TARGET_OP_FUNCTIONS = {
    PerfTargetOp.GT.value: operator.gt,
    PerfTargetOp.GE.value: operator.ge,
    PerfTargetOp.LT.value: operator.lt,
    PerfTargetOp.LE.value: operator.le,
    PerfTargetOp.EQ.value: operator.eq,
}


def _merge_stats_entries(shards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    聚合各分片的统计行(按 name+method 求和; 加权平均与极值可加, 直方图派生值不可加置0)。

    :param shards: 结果分片列表
    :return: 聚合后的统计行列表
    """
    merged: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for shard in shards:
        for entry in (shard.get("stats") or {}).get("entries") or []:
            key = (str(entry.get("name")), str(entry.get("method")))
            target = merged.get(key)
            if target is None:
                merged[key] = dict(entry)
                continue
            requests = int(entry.get("num_requests") or 0)
            total_requests = int(target["num_requests"]) + requests
            # 响应时间均值按请求数加权(含0请求行避免除零)
            target["avg_response_time"] = (
                (float(target["avg_response_time"]) * target["num_requests"]
                 + float(entry.get("avg_response_time") or 0) * requests) / total_requests
            ) if total_requests else 0.0
            target["min_response_time"] = min(
                float(target["min_response_time"] or 0) if target["num_requests"] else float("inf"),
                float(entry.get("min_response_time") or 0) if requests else float("inf"),
            )
            target["max_response_time"] = max(
                float(target["max_response_time"] or 0),
                float(entry.get("max_response_time") or 0),
            )
            target["num_requests"] = total_requests
            target["num_failures"] = int(target["num_failures"]) + int(entry.get("num_failures") or 0)
            target["fail_ratio"] = target["num_failures"] / total_requests if total_requests else 0.0
            # median/current_rps/p95 由各进程直方图派生不可跨进程相加, 置0以样本口径为准
            target["median_response_time"] = 0
            target["current_rps"] = 0
            target["p95_response_time"] = 0
    for target in merged.values():
        if not target["num_requests"]:
            target["min_response_time"] = 0
        target["min_response_time"] = round(float(target["min_response_time"]), 2)
        target["max_response_time"] = round(float(target["max_response_time"]), 2)
        target["avg_response_time"] = round(float(target["avg_response_time"]), 2)
    return list(merged.values())


def _merge_errors(shards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """聚合各分片错误明细(按 name+method+error 归因键累加出现次数)。"""
    merged: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for shard in shards:
        for error in shard.get("errors") or []:
            key = (str(error.get("name")), str(error.get("method")), str(error.get("error")))
            if key in merged:
                merged[key]["occurrences"] += int(error.get("occurrences") or 0)
            else:
                merged[key] = dict(error)
    return sorted(merged.values(), key=lambda item: -int(item["occurrences"]))


def _merge_prepare_metrics(shards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """聚合各分片准备段指标(同名累加; 各VU在各自进程各跑一次, 求和即全量)。"""
    merged: Dict[str, Dict[str, float]] = {}
    for shard in shards:
        for metric in shard.get("prepare_metrics") or []:
            name = str(metric.get("name"))
            target = merged.setdefault(name, {"name": name, "attempts": 0, "failures": 0, "total_rt_ms": 0})
            target["attempts"] += int(metric.get("attempts") or 0)
            target["failures"] += int(metric.get("failures") or 0)
            target["total_rt_ms"] += float(metric.get("total_rt_ms") or 0)
    return list(merged.values())


def merge_result_shards(shards: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    合并全部结果分片为统一快照(聚合器与报告回填的统一输入)。

    :param shards: 结果分片列表(至少1个, 由管线校验)
    :return: 合并快照, 结构:
        {"started_time": "ISO", "finished_time": "ISO", "actual_duration": 60,
         "run_duration": 60, "warmup_seconds": 20, "stopped_reason": "completed",
         "circuit_break": false, "item_index": [...], "entries": [...], "errors": [...],
         "samples": {"columns": [...], "rows": [...]}, "prepare_metrics": [...],
         "shard_count": 2, "shards": [{"pid": 1, "stopped_reason": "completed"}]}
    """
    ordered = sorted(
        shards,
        key=lambda shard: (shard.get("started_time") or "", shard.get("pid") or 0),
    )
    started_times = [shard.get("started_time") for shard in ordered if shard.get("started_time")]
    finished_times = [shard.get("finished_time") for shard in ordered if shard.get("finished_time")]
    sample_rows: List[List[Any]] = []
    sampled_over = False
    for shard in shards:
        samples = shard.get("samples") or {}
        sample_rows.extend(samples.get("rows") or [])
        if int(samples.get("seen") or 0) > len(samples.get("rows") or []):
            sampled_over = True
    # 熔断优先于其他结束原因: 任一进程熔断即整批被叫停
    reasons = [str(shard.get("stopped_reason") or "") for shard in shards]
    if "circuit_break" in reasons:
        stopped_reason = "circuit_break"
    elif all(reason == "completed" for reason in reasons):
        stopped_reason = "completed"
    else:
        stopped_reason = "stopped"
    return {
        "started_time": min(started_times) if started_times else None,
        "finished_time": max(finished_times) if finished_times else None,
        "actual_duration": max(int(shard.get("actual_duration") or 0) for shard in shards),
        "run_duration": int(ordered[0].get("run_duration") or 0),
        "warmup_seconds": int(ordered[0].get("warmup_seconds") or 0),
        "stopped_reason": stopped_reason,
        "circuit_break": "circuit_break" in reasons,
        "item_index": ordered[0].get("item_index") or [],
        "entries": _merge_stats_entries(shards),
        "errors": _merge_errors(shards),
        "samples": {"columns": list(ordered[0].get("samples", {}).get("columns") or []), "rows": sample_rows},
        "prepare_metrics": _merge_prepare_metrics(shards),
        "sampled_over": sampled_over,
        "shard_count": len(shards),
        "shards": [
            {"pid": shard.get("pid"), "stopped_reason": shard.get("stopped_reason")}
            for shard in ordered
        ],
    }


def _summarize_rows(rows: List[List[Any]], duration_seconds: int) -> Dict[str, Any]:
    """
    对样本行集合计算吞吐与延迟摘要(样本行五列契约见 reservoir.SAMPLE_COLUMNS)。

    :param rows: 样本行列表(ts/rt/ok/name/txn)
    :param duration_seconds: 有效统计秒数(RPS分母, 不足1秒按1秒)
    :return: 摘要字典(total/success/fail/error_rate/rps/success_rps/avg/min/max/分位/std_dev)
    """
    safe_duration = max(duration_seconds, 1)
    total = len(rows)
    success = sum(1 for row in rows if row[COLUMN_OK])
    rt_values = [float(row[COLUMN_RT]) for row in rows]
    rt_sorted = sorted(rt_values)
    summary = {
        "total_requests": total,
        "success_requests": success,
        "fail_requests": total - success,
        "error_rate": round((total - success) / total * 100, 2) if total else 0.0,
        "rps": round(total / safe_duration, 2),
        "success_rps": round(success / safe_duration, 2),
        "avg_rt": round(sum(rt_values) / total, 2) if total else 0.0,
        "min_rt": round(rt_sorted[0], 2) if rt_sorted else 0.0,
        "max_rt": round(rt_sorted[-1], 2) if rt_sorted else 0.0,
        "p50": round(compute_percentile(rt_sorted, 0.50), 2),
        "p90": round(compute_percentile(rt_sorted, 0.90), 2),
        "p95": round(compute_percentile(rt_sorted, 0.95), 2),
        "p99": round(compute_percentile(rt_sorted, 0.99), 2),
        "std_dev": round(compute_std_dev(rt_values), 2),
    }
    return summary


def _effective_rows(
        merged: Dict[str, Any],
) -> Tuple[List[List[Any]], List[List[Any]], int, Optional[str]]:
    """
    取合并样本的有效统计集: 剔除预热段样本, 并拆分业务请求与事务圈两类样本。

    :param merged: 合并快照(见 merge_result_shards)
    :return: (业务请求样本, 事务圈样本, 有效统计秒数, 剔除异常说明)
    """
    started_time = parse_iso(merged.get("started_time"))
    actual_duration = int(merged.get("actual_duration") or 0)
    warmup_seconds = int(merged.get("warmup_seconds") or 0)
    # 有效秒数=总时长扣预热(下限1秒防除零); 预热≥总时长说明配置失当, 全样本保留并提示
    duration_seconds = max(actual_duration - warmup_seconds, 1)
    warning: Optional[str] = None
    if warmup_seconds >= actual_duration and actual_duration > 0:
        warning = f"warmup[{warmup_seconds}s]不小于实际时长[{actual_duration}s], 预热剔除未生效"
        warmup_seconds = 0
    warmup_cut_ms = (started_time.timestamp() + warmup_seconds) * 1000 if started_time else 0
    request_rows: List[List[Any]] = []
    transaction_rows: List[List[Any]] = []
    for row in (merged.get("samples") or {}).get("rows") or []:
        if warmup_cut_ms and row[COLUMN_TS] < warmup_cut_ms:
            continue
        if str(row[COLUMN_NAME]).startswith(TRANSACTION_NAME_PREFIX):
            transaction_rows.append(row)
        else:
            request_rows.append(row)
    return request_rows, transaction_rows, duration_seconds, warning


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    """解析ISO时间字符串(引擎分片时间为UTC ISO格式; 解析失败返回None)。"""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _resolve_target_view(
        target: Dict[str, Any],
        global_view: Dict[str, Any],
        api_views: Dict[str, Dict[str, Any]],
        transaction_views: Dict[str, Dict[str, Any]],
) -> Tuple[Optional[float], Optional[str]]:
    """
    定位单条SLA目标的判定对象与实际值。

    :param target: SLA目标定义(scene.perf_targets 元素)
    :param global_view: 全局指标视图
    :param api_views: {api_code: 指标视图}
    :param transaction_views: {事务名: 指标视图}
    :return: (实际值, 跳过原因); 实际值为None时表示无法判定
    """
    scope = str(target.get("scope"))
    if scope == "global":
        return global_view.get(str(target.get("target"))), None
    if scope == "api":
        view = api_views.get(str(target.get("api_code") or ""))
        if view is None:
            return None, f"报告未包含接口[{target.get('api_code')}]的统计数据"
        return view.get(str(target.get("target"))), None
    if scope == "transaction":
        view = transaction_views.get(str(target.get("transaction") or ""))
        if view is None:
            return None, f"报告未包含事务[{target.get('transaction')}]的统计数据"
        return view.get(str(target.get("target"))), None
    return None, f"未知判定层级[{scope}]"


def evaluate_targets(
        perf_targets: List[Dict[str, Any]],
        global_view: Dict[str, Any],
        api_views: Dict[str, Dict[str, Any]],
        transaction_views: Dict[str, Dict[str, Any]],
        duration_seconds: int,
) -> List[Dict[str, Any]]:
    """
    逐条判定SLA目标(显著性闸门: 样本量或有效时长不足时跳过判定而非产出噪声结论)。

    :param perf_targets: 场景SLA目标列表
    :param global_view: 全局指标视图(键与PerfTargetMetric取值一致)
    :param api_views: 接口指标视图
    :param transaction_views: 事务指标视图
    :param duration_seconds: 有效统计秒数
    :return: 判定结果列表, 元素结构:
        {"scope": "api", "target": "p95", "api_ref": "PERF-API-xxx", "op": "le",
         "expect": 200, "actual": 185.3, "passed": true, "severity": "fail",
         "skipped": false, "reason": null}
    """
    results: List[Dict[str, Any]] = []
    for target in perf_targets or []:
        min_requests = int(target.get("min_total_requests") or 0)
        min_duration = int(target.get("min_duration_seconds") or PERF_MIN_DURATION_FOR_SLA)
        actual, skip_reason = _resolve_target_view(target, global_view, api_views, transaction_views)
        total_requests = int(global_view.get("total_requests") or 0)
        # 定位失败原因(对象缺失/层级不支持)优先保留, 显著性门槛只对可判定目标生效
        if actual is None and not skip_reason:
            skip_reason = "该层级不支持的判定指标"
        elif not skip_reason and duration_seconds < min_duration:
            skip_reason = f"有效时长[{duration_seconds}s]不足判定门槛[{min_duration}s]"
        elif not skip_reason and min_requests and total_requests < min_requests:
            skip_reason = f"总请求数[{total_requests}]不足判定门槛[{min_requests}]"
        compare = _TARGET_OP_FUNCTIONS.get(str(target.get("op")))
        if skip_reason or compare is None or actual is None:
            results.append({
                "scope": target.get("scope"), "target": target.get("target"),
                "api_ref": target.get("api_code") or target.get("transaction"),
                "op": target.get("op"), "expect": target.get("expect"), "actual": actual,
                "passed": None, "severity": target.get("severity", "fail"),
                "skipped": True, "reason": skip_reason or "未知比较运算符",
            })
            continue
        passed = bool(compare(actual, target.get("expect")))
        results.append({
            "scope": target.get("scope"), "target": target.get("target"),
            "api_ref": target.get("api_code") or target.get("transaction"),
            "op": target.get("op"), "expect": target.get("expect"), "actual": actual,
            "passed": passed, "severity": target.get("severity", "fail"),
            "skipped": False, "reason": None,
        })
    return results


def compute_report_metrics(
        merged: Dict[str, Any],
        perf_targets: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    由合并快照计算报告全部统计字段(B吞吐延迟/C维度聚合/D判定)。

    口径说明: 全局与接口维度只统计业务请求样本(事务圈与抽查不计入),
    事务维度单独成表; 全部分位数由合并样本剔除warmup后计算(真分位)。

    :param merged: 合并快照(见 merge_result_shards)
    :param perf_targets: 场景SLA目标列表(空则跳过判定)
    :return: 报告统计字段字典, 键与 PerfReportModel 统计列逐字对齐:
        {"global": {...}, "duration_seconds": 40, "api_aggregations": [...],
         "transaction_aggregations": [...], "prepare_metrics": {...},
         "verify_metrics": {...}, "error_breakdown": [...], "target_result": [...],
         "stat_warnings": [...]}
    """
    request_rows, transaction_rows, duration_seconds, warmup_warning = _effective_rows(merged)
    global_view = _summarize_rows(request_rows, duration_seconds)

    item_index = merged.get("item_index") or []
    # 接口维度: 仅measured项(准备段独立隔离, 抽查独立归因), 按统计行名过滤样本
    api_aggregations: List[Dict[str, Any]] = []
    api_views: Dict[str, Dict[str, Any]] = {}
    for item in item_index:
        if item.get("role") != PerfApiRole.MEASURED.value:
            continue
        stats_name = str(item.get("stats_name"))
        rows = [row for row in request_rows if str(row[COLUMN_NAME]) == stats_name]
        summary = _summarize_rows(rows, duration_seconds)
        aggregation = {
            "api_code": item.get("api_code"), "api_name": item.get("api_name"),
            "api_version": item.get("api_version"), "method": item.get("method"),
            "stats_name": stats_name,
            "total_requests": summary["total_requests"],
            "failed_requests": summary["fail_requests"],
            "error_rate": summary["error_rate"],
            "avg_rt": summary["avg_rt"], "p90": summary["p90"],
            "p95": summary["p95"], "p99": summary["p99"],
            "rps": summary["rps"],
            "low_confidence": summary["total_requests"] < PERF_MIN_SAMPLES_FOR_COMPARE,
        }
        api_aggregations.append(aggregation)
        api_views[str(item.get("api_code"))] = {
            "rps": summary["rps"], "total_requests": summary["total_requests"],
            "avg_rt": summary["avg_rt"], "p90": summary["p90"], "p95": summary["p95"],
            "p99": summary["p99"], "error_rate": summary["error_rate"],
        }

    # 事务维度: 事务圈样本按归属事务聚合(业务TPS=完成圈数/有效秒数)
    transaction_names = sorted({
        str(item.get("transaction")) for item in item_index if item.get("transaction")
    })
    transaction_aggregations: List[Dict[str, Any]] = []
    transaction_views: Dict[str, Dict[str, Any]] = {}
    for name in transaction_names:
        stats_name = f"{TRANSACTION_NAME_PREFIX}{name}"
        rows = [row for row in transaction_rows if str(row[COLUMN_NAME]) == stats_name]
        summary = _summarize_rows(rows, duration_seconds)
        transaction_aggregations.append({
            "name": name, "rounds": summary["total_requests"], "failed": summary["fail_requests"],
            "avg_rt": summary["avg_rt"], "p95": summary["p95"], "business_tps": summary["success_rps"],
        })
        transaction_views[name] = {
            "rps": summary["rps"], "success_rps": summary["success_rps"],
            "total_requests": summary["total_requests"], "avg_rt": summary["avg_rt"],
            "p90": summary["p90"], "p95": summary["p95"], "p99": summary["p99"],
            "error_rate": summary["error_rate"],
        }

    # 准备段: 完全独立于业务吞吐, 汇总为总量口径
    prepare_total = sum(int(metric.get("attempts") or 0) for metric in merged.get("prepare_metrics") or [])
    prepare_failed = sum(int(metric.get("failures") or 0) for metric in merged.get("prepare_metrics") or [])
    prepare_rt_total = sum(float(metric.get("total_rt_ms") or 0) for metric in merged.get("prepare_metrics") or [])
    prepare_metrics = {
        "rounds": prepare_total,
        "success_rate": round((prepare_total - prepare_failed) / prepare_total * 100, 2) if prepare_total else 100.0,
        "avg_rt": round(prepare_rt_total / prepare_total, 2) if prepare_total else 0.0,
    }

    # 抽查段: 从聚合统计行取VFY维度(样本池不含抽查, 与吞吐彻底隔离)
    verify_requests = sum(
        int(entry.get("num_requests") or 0) for entry in merged.get("entries") or []
        if entry.get("method") == METHOD_VERIFY
    )
    verify_failures = sum(
        int(entry.get("num_failures") or 0) for entry in merged.get("entries") or []
        if entry.get("method") == METHOD_VERIFY
    )
    verify_metrics = {
        "checks": verify_requests,
        "pass_rate": round((verify_requests - verify_failures) / verify_requests * 100, 2) if verify_requests else 100.0,
        "fail_samples": [
            {"name": error.get("name"), "error": error.get("error"), "occurrences": error.get("occurrences")}
            for error in merged.get("errors") or [] if error.get("method") == METHOD_VERIFY
        ][:10],
    }

    # 错误归因: 统计行名回查接口资产(事务行无归属接口, api_code留空);
    # 索引只登记真实方法, 抽查行记账键为VFY, 按role额外推导归因键
    index_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for item in item_index:
        index_by_key[(str(item.get("stats_name")), str(item.get("method")))] = item
        if item.get("role") == PerfApiRole.VERIFY.value:
            index_by_key[(str(item.get("stats_name")), METHOD_VERIFY)] = item
    error_breakdown: List[Dict[str, Any]] = []
    for error in merged.get("errors") or []:
        item = index_by_key.get((str(error.get("name")), str(error.get("method")))) or {}
        error_breakdown.append({
            "api_code": item.get("api_code"), "api_name": item.get("api_name"),
            "method": error.get("method"), "name": error.get("name"),
            "error": error.get("error"), "occurrences": error.get("occurrences"),
        })

    # 统计可信度提示(报告头部风险条)
    stat_warnings: List[Dict[str, str]] = []
    if merged.get("sampled_over"):
        stat_warnings.append({
            "type": "sampled_percentile",
            "text": "请求量超出蓄水池容量, 分位数基于等概率采样样本计算",
        })
    if global_view["total_requests"] < PERF_MIN_SAMPLES_FOR_COMPARE:
        stat_warnings.append({
            "type": "low_samples",
            "text": f"业务请求总数[{global_view['total_requests']}]低于显著性闸门[{PERF_MIN_SAMPLES_FOR_COMPARE}], 指标结论仅供参考",
        })
    if warmup_warning:
        stat_warnings.append({"type": "warmup_invalid", "text": warmup_warning})

    return {
        "global": global_view,
        "duration_seconds": duration_seconds,
        "api_aggregations": api_aggregations,
        "transaction_aggregations": transaction_aggregations,
        "prepare_metrics": prepare_metrics,
        "verify_metrics": verify_metrics,
        "error_breakdown": error_breakdown,
        "target_result": evaluate_targets(
            perf_targets or [], global_view, api_views, transaction_views, duration_seconds,
        ),
        "stat_warnings": stat_warnings,
    }
