# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_record_model.py
@DateTime: 2025/12/28 16:15
"""
from tortoise import fields

from backend.applications.base.services.scaffold import (
    ScaffoldModel,
    MaintainMixin,
    TimestampMixin,
    StateModel,
    ReserveFields,
)
from backend.enums import (
    AutoTestReportType,
    AutoTestTaskStatus,
    AutoTestTaskType,
    AutoTestTaskTriggerType,
)


class AutoTestRecordModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    task_id = fields.BigIntField(null=True, index=True, description="任务ID")
    task_name = fields.CharField(max_length=255, null=True, index=True, description="任务名称")
    task_code = fields.CharField(max_length=64, null=True, index=True, description="任务标识代码")
    task_type = fields.CharEnumField(AutoTestTaskType, default=None, null=True, index=True, description="任务所属类型")
    task_project = fields.IntField(null=True, index=True, description="任务所属应用")
    trigger_type = fields.CharEnumField(AutoTestTaskTriggerType, default=None, null=True, index=True, description="任务触发类型")
    report_type = fields.CharEnumField(AutoTestReportType, default=None, null=True, description="报告所属类型")
    batch_code = fields.CharField(max_length=64, null=True, index=True, description="批次标识代码")
    case_ids = fields.JSONField(default=list, null=True, description="用例ID列表")
    exec_snapshot = fields.JSONField(default=None, null=True, description="执行请求快照")
    task_summary = fields.JSONField(default=None, null=True, description="任务响应快照")
    task_error = fields.TextField(null=True, description="任务错误描述")
    celery_id = fields.CharField(max_length=255, index=True, description="Celery调度ID")
    celery_node = fields.CharField(max_length=512, null=True, index=True, description="Celery节点名称")
    celery_trace_id = fields.CharField(max_length=255, null=True, index=True, description="Celery回溯ID")
    celery_status = fields.CharEnumField(AutoTestTaskStatus, default=AutoTestTaskStatus.RUNNING, description="Celery执行状态")
    celery_start_time = fields.DatetimeField(null=True, description="Celery开始时间")
    celery_end_time = fields.DatetimeField(null=True, description="Celery结束时间")
    celery_elapsed = fields.CharField(max_length=64, null=True, description="Celery执行耗时")

    class Meta:
        table = "krun_autotest_record"
        table_description = "自动化测试-任务执行记录表"
        indexes = (
            ("celery_status",),
            ("celery_start_time",),
            ("trigger_type", "celery_start_time"),
            ("task_id", "celery_start_time"),
        )
        ordering = ["-celery_start_time", "-id"]

    def __str__(self):
        """返回 celery_id 与 task_name 的组合字符串。"""
        return f"{self.celery_id or ''}-{self.task_name or ''}"
