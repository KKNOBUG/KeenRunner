# -*- coding: utf-8 -*-
"""
压测结果分片写入(locust 子进程内运行, 禁止 import backend 主包)。

监听 locust test_start/test_stop 事件, 将本进程统计序列化写入 PERF_RESULT_FILE
指定目录下的 result_{pid}.json 分片; 由后端执行管线在子进程退出后合并所有分片
(多进程模式下 master 只收聚合直方图、收不到逐个样本, 分片落盘是可信分位数的
唯一数据来源)。单进程与worker角色各写一份, master角色不写(无用户流量)。

分片负载: locust 统计行(含 TX/VFY 记账行) + 错误明细 + 蓄水池原始样本 +
准备段指标 + 接口项索引(统计行名到压测接口资产的归因依据) + 结束原因。
文件原子写入(临时文件+os.replace), 避免管线读到半截JSON。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : result_writer.py
@DateTime: 2026/9/16 10:30
"""
from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import orjson
from locust import events as locust_events
from locust.env import Environment

from reservoir import Reservoir

# 环境变量契约: 由backend执行管线在启动locust子进程前注入(与管线双声明同步维护)
ENV_RESULT_FILE = "PERF_RESULT_FILE"
ENV_REPORT_CODE = "PERF_REPORT_CODE"
ENV_PERF_CODE = "PERF_PERF_CODE"

# 分片文件名模板: 以进程pid区分, 多进程模式下各worker各写一份
RESULT_SHARD_NAME = "result_{pid}.json"
# 分片结构版本(管线按版本兼容读取)
SHARD_VERSION = 2

# 引擎侧结束原因: completed=到期自然结束; circuit_break=本进程触发熔断;
# stopped=未到时长且非本进程熔断(被master/pipeline叫停)。最终 stopped_reason
# 由管线综合「是否有分片熔断」与「是否人工终止」判定
REASON_COMPLETED = "completed"
REASON_CIRCUIT_BREAK = "circuit_break"
REASON_STOPPED = "stopped"
# 提前结束判定余量(秒): 实际时长低于预期时长的差值超过该余量视为被叫停
REASON_EARLY_STOP_SLACK_SECONDS = 5


def _serialize_stats_entry(entry: Any) -> Dict[str, Any]:
    """序列化单个 StatsEntry 为可JSON化字典(p95由响应时间直方图计算, 供与蓄水池分位交叉校验)。"""
    try:
        p95_latency = entry.get_response_time_percentile(0.95)
    except Exception:
        p95_latency = 0
    return {
        "name": entry.name,
        "method": entry.method,
        "num_requests": entry.num_requests,
        "num_failures": entry.num_failures,
        "avg_response_time": entry.avg_response_time,
        "min_response_time": entry.min_response_time if entry.num_requests else 0,
        "max_response_time": entry.max_response_time if entry.num_requests else 0,
        "median_response_time": entry.median_response_time,
        "current_rps": entry.current_rps,
        "fail_ratio": entry.fail_ratio,
        "p95_response_time": p95_latency or 0,
    }


def write_result_file(result_file: str, snapshot: Dict[str, Any]) -> None:
    """
    原子写入结果分片文件(临时文件+os.replace)。

    :param result_file: 目标文件绝对路径
    :param snapshot: 结果分片字典(见 ResultWriter.build_result)
    :return: None
    """
    directory = os.path.dirname(os.path.abspath(result_file))
    os.makedirs(directory, exist_ok=True)
    file_descriptor, temp_path = tempfile.mkstemp(prefix=".perf_result_", dir=directory)
    try:
        with os.fdopen(file_descriptor, "wb") as temp_file:
            temp_file.write(orjson.dumps(snapshot, option=orjson.OPT_INDENT_2))
        os.replace(temp_path, result_file)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


class ResultWriter:
    """监听 locust 事件并在 test_stop 时写入本进程结果分片文件。"""

    def __init__(
            self,
            environment: Environment,
            *,
            result_dir: str,
            report_code: str,
            perf_code: str,
            samples: Reservoir,
            prepare_metrics: Dict[str, Dict[str, float]],
            item_index: List[Dict[str, Any]],
            run_duration: int,
            warmup_seconds: int,
    ) -> None:
        """
        初始化结果写入器。

        :param environment: locust Environment实例
        :param result_dir: 分片输出目录(PERF_RESULT_FILE语义为目录)
        :param report_code: 报告标识
        :param perf_code: 任务标识
        :param samples: 本进程蓄水池(引用, test_stop时读取最终样本)
        :param prepare_metrics: 准备段指标注册表(引用, 由施压入口持续累计)
        :param item_index: 接口项索引(统计行名与压测接口资产的归因关系)
        :param run_duration: 预期施压时长秒数(提前结束判定依据)
        :param warmup_seconds: 预热剔除秒数(透传分片, 供管线定剔除分界线)
        """
        self.environment = environment
        self.result_dir = result_dir
        self.report_code = report_code
        self.perf_code = perf_code
        self.samples = samples
        self.prepare_metrics = prepare_metrics
        self.item_index = item_index
        self.run_duration = run_duration
        self.warmup_seconds = warmup_seconds
        self.stopped_reason: str = REASON_COMPLETED
        self.started_time: Optional[datetime] = None
        self.finished_time: Optional[datetime] = None

    @classmethod
    def from_environment(
            cls,
            environment: Environment,
            *,
            samples: Reservoir,
            prepare_metrics: Dict[str, Dict[str, float]],
            item_index: List[Dict[str, Any]],
            run_duration: int,
            warmup_seconds: int,
    ) -> Optional["ResultWriter"]:
        """
        从环境变量构建写入器; 目录未注入或当前为master角色时返回None。

        :param environment: locust Environment实例
        :param samples: 本进程蓄水池(引用)
        :param prepare_metrics: 准备段指标注册表(引用)
        :param item_index: 接口项索引
        :param run_duration: 预期施压时长秒数
        :param warmup_seconds: 预热剔除秒数
        :return: 写入器实例或无需写出的None
        """
        from locust.runners import MasterRunner

        if isinstance(environment.runner, MasterRunner):
            return None
        result_dir = os.environ.get(ENV_RESULT_FILE, "").strip()
        if not result_dir:
            return None
        return cls(
            environment,
            result_dir=result_dir,
            report_code=os.environ.get(ENV_REPORT_CODE, "unknown"),
            perf_code=os.environ.get(ENV_PERF_CODE, "unknown"),
            samples=samples,
            prepare_metrics=prepare_metrics,
            item_index=item_index,
            run_duration=run_duration,
            warmup_seconds=warmup_seconds,
        )

    def register(self) -> None:
        """注册 test_start/test_stop 事件监听(在 locustfile @events.init 中调用)。"""
        locust_events.test_start.add_listener(self._on_test_start)
        locust_events.test_stop.add_listener(self._on_test_stop)

    def mark_stopped(self, reason: str) -> None:
        """
        标记本进程结束原因(熔断触发时由熔断器调用; 幂等, 首次标记生效)。

        :param reason: 结束原因(REASON_CIRCUIT_BREAK等)
        :return: None
        """
        if self.stopped_reason == REASON_COMPLETED:
            self.stopped_reason = reason

    def build_result(self) -> Dict[str, Any]:
        """
        构建结果分片(统计+样本+归因索引), 结构:
            {"shard_version": 2, "report_code": "xxx", "perf_code": "yyy", "pid": 123,
             "status": "completed", "stopped_reason": "completed",
             "started_time": "2026-09-16T06:00:00+00:00", "finished_time": "...",
             "actual_duration": 60, "run_duration": 60, "warmup_seconds": 20,
             "item_index": [...], "prepare_metrics": [...],
             "stats": {"entries": [...]}, "errors": [...], "samples": {...}}

        :return: 结果分片字典
        """
        errors: List[Dict[str, Any]] = [
            {
                "name": error.name,
                "method": error.method,
                "error": str(error.error),
                "occurrences": error.occurrences,
            }
            for error in self.environment.runner.stats.errors.values()
        ]
        started_time = self.started_time.astimezone(timezone.utc) if self.started_time else None
        finished_time = self.finished_time.astimezone(timezone.utc) if self.finished_time else None
        actual_duration = 0
        if started_time and finished_time:
            actual_duration = max(int((finished_time - started_time).total_seconds()), 0)
        # 到期自然结束之外的场景(被master/pipeline叫停)修正结束原因, 熔断标记优先
        stopped_reason = self.stopped_reason
        if stopped_reason == REASON_COMPLETED and self.run_duration > 0 \
                and actual_duration < self.run_duration - REASON_EARLY_STOP_SLACK_SECONDS:
            stopped_reason = REASON_STOPPED
        return {
            "shard_version": SHARD_VERSION,
            "report_code": self.report_code,
            "perf_code": self.perf_code,
            "pid": os.getpid(),
            "status": "completed",
            "stopped_reason": stopped_reason,
            "started_time": started_time.isoformat() if started_time else None,
            "finished_time": finished_time.isoformat() if finished_time else None,
            "actual_duration": actual_duration,
            "run_duration": self.run_duration,
            "warmup_seconds": self.warmup_seconds,
            "item_index": self.item_index,
            "prepare_metrics": [dict(metric, name=stats_name) for stats_name, metric in self.prepare_metrics.items()],
            "stats": {
                "entries": [
                    _serialize_stats_entry(entry) for entry in self.environment.runner.stats.entries.values()
                    if entry.name and str(entry.name) != "--"
                ],
            },
            "errors": errors,
            "samples": self.samples.to_payload(),
        }

    def _on_test_start(self, environment: Environment, **kwargs) -> None:
        """记录压测开始时间(UTC)。"""
        self.started_time = datetime.now(timezone.utc)

    def _on_test_stop(self, environment: Environment, **kwargs) -> None:
        """test_stop时写出本进程分片; 写文件失败仅记录(locust日志), 不阻断退出流程。"""
        self.finished_time = datetime.now(timezone.utc)
        result_file = os.path.join(self.result_dir, RESULT_SHARD_NAME.format(pid=os.getpid()))
        try:
            write_result_file(result_file, self.build_result())
        except Exception as e:
            # 分片写失败时该进程统计仍可从VM时序与locust日志观测, 不因IO异常崩溃子进程
            logging.getLogger(__name__).error("写入压测结果分片失败[%s]: %s", result_file, e)
