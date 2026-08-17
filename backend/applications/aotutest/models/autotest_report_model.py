# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_report_model.py
@DateTime: 2025/12/28 16:15
"""
from tortoise import fields

from backend.applications.base.services.scaffold import (
    ScaffoldModel,
    MaintainMixin,
    TimestampMixin,
    StateModel,
    ReserveFields,
    unique_identify,
)
from backend.enums import AutoTestReportType


class AutoTestReportModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    case_id = fields.BigIntField(index=True, description="用例ID")
    case_code = fields.CharField(max_length=64, description="用例标识代码")
    case_st_time = fields.CharField(max_length=32, null=True, description="用例执行开始时间")
    case_ed_time = fields.CharField(max_length=32, null=True, description="用例执行结束时间")
    case_elapsed = fields.CharField(max_length=16, null=True, description="用例执行消耗时间")
    case_state = fields.BooleanField(null=True, description="用例执行状态(True:成功, False:失败)")

    step_total = fields.IntField(default=0, ge=0, description="用例步骤数量(含所有子级步骤)")
    step_fail_count = fields.IntField(default=0, ge=0, description="用例步骤失败数量(含所有子级步骤)")
    step_pass_count = fields.IntField(default=0, ge=0, description="用例步骤成功数量(含所有子级步骤)")
    step_pass_ratio = fields.FloatField(default=0.0, ge=0.0, description="用例步骤成功率(含所有子级步骤)")

    batch_code = fields.CharField(max_length=64, default=None, null=True, description="批次标识代码")
    report_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="报告标识代码")
    report_type = fields.CharEnumField(AutoTestReportType, description="报告类型")
    task_code = fields.CharField(max_length=64, null=True, description="任务标识代码")
    dataset_name = fields.CharField(max_length=255, null=True, index=True, description="本次执行使用的数据集/场景名称(参数化)")
    involve_envs = fields.JSONField(default=list, null=True, description="脚本执行时涉及应用环境列表")

    class Meta:
        table = "krun_autotest_report"
        table_description = "自动化测试-报告信息表"
        indexes = (
            ("case_id", "case_code"),
            ("case_id", "state", "case_st_time"),
            ("case_id", "state", "updated_time"),
            ("case_id", "case_state"),
            ("case_id", "created_user"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        """返回报告标识代码。"""
        return self.report_code
