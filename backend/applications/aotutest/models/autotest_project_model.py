# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_project_model.py
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


class AutoTestProjectModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    project_name = fields.CharField(max_length=128, unique=True, description="应用名称")
    project_desc = fields.CharField(max_length=2048, null=True, description="应用描述")
    project_state = fields.CharField(max_length=64, null=True, description="应用状态")
    project_phase = fields.CharField(max_length=64, null=True, description="应用阶段")
    project_dev_owners = fields.JSONField(default=list, null=True, description="应用开发负责人")
    project_developers = fields.JSONField(default=list, null=True, description="应用开发人员列表")
    project_test_owners = fields.JSONField(default=list, null=True, description="应用测试负责人")
    project_testers = fields.JSONField(default=list, null=True, description="应用测试人员列表")
    project_current_month_env = fields.CharField(max_length=64, null=True, description="应用当前月版环境")
    project_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="应用标识代码")

    class Meta:
        table = "krun_autotest_project"
        table_description = "自动化测试-应用信息表"
        indexes = (
            ("project_name", "project_state"),
            ("state", "updated_time"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        """返回项目名称。"""
        return self.project_name
