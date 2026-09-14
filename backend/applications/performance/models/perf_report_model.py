# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_report_model.py
@DateTime: 2026/9/14 10:30
"""
from tortoise import fields

from backend.applications.base.services.scaffold import (
    ScaffoldModel,
    MaintainMixin,
    TimestampMixin,
    StateModel,
    ReserveFields,
    JSONTextField,
    unique_identify,
)
from backend.enums import PerfReportStatus


class PerfReportModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    # 任务双轨关联: 表内定位用 perf_id, 跨表引用用 perf_code(对齐 report 表 case_id+case_code 模式)
    perf_id = fields.BigIntField(index=True, description="压测任务ID")
    perf_code = fields.CharField(max_length=64, index=True, description="压测任务标识代码")
    report_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="报告标识代码")
    batch_code = fields.CharField(max_length=64, default=None, null=True, index=True, description="批次标识代码(第一期与report_code同值)")
    status = fields.CharEnumField(PerfReportStatus, description="报告执行状态(running/completed/failed/stopped)")
    celery_id = fields.CharField(max_length=64, default=None, null=True, index=True, description="本次执行的Celery任务ID")

    started_time = fields.DatetimeField(default=None, null=True, description="压测开始时间")
    finished_time = fields.DatetimeField(default=None, null=True, description="压测结束时间")
    actual_duration = fields.IntField(default=None, ge=0, null=True, description="实际持续秒数")

    # 最终统计快照(由 locust result.json 解析回填, 执行中保持默认值)
    total_requests = fields.IntField(default=0, ge=0, description="总请求数")
    total_failures = fields.IntField(default=0, ge=0, description="总失败数")
    rps = fields.FloatField(default=0.0, ge=0.0, description="平均RPS")
    fail_rate = fields.FloatField(default=0.0, ge=0.0, description="失败率(0~1)")
    avg_latency = fields.FloatField(default=0.0, ge=0.0, description="平均响应时间(ms)")
    min_latency = fields.FloatField(default=0.0, ge=0.0, description="最小响应时间(ms)")
    max_latency = fields.FloatField(default=0.0, ge=0.0, description="最大响应时间(ms)")
    median_latency = fields.FloatField(default=0.0, ge=0.0, description="中位数响应时间(ms)")
    p95_latency = fields.FloatField(default=0.0, ge=0.0, description="P95响应时间(ms)")
    # locust 原始统计快照(含 per-entry 明细): JSONTextField 避免 MySQL JSON 键归一化且容量充足
    locust_stats = JSONTextField(default=None, null=True, description="Locust原始统计快照")
    error_message = fields.TextField(default=None, null=True, description="失败原因")

    class Meta:
        table = "krun_perf_report"
        table_description = "性能测试-执行报告表"
        indexes = (
            ("perf_id", "perf_code"),
            ("perf_code", "state"),
            ("status", "state"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        """返回报告标识代码。"""
        return self.report_code
