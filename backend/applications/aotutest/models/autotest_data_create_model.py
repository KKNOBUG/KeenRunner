# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_create_model.py
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


class AutoTestDataCreateModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    case_id = fields.BigIntField(ge=1, index=True, description="用例ID")
    case_code = fields.CharField(max_length=64, description="用例标识代码")
    create_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="接口文件标识代码")
    create_status = fields.SmallIntField(default=0, index=True, description="创建状态(0提交, 1生成中, 2失败, 3成功)")
    step_code = fields.CharField(max_length=64, description="步骤标识代码")
    file_name = fields.CharField(max_length=255, description="接口文件存储名称")
    file_hash = fields.CharField(max_length=255, description="接口文件哈希代码")
    file_path = fields.CharField(max_length=1024, description="接口文件存储路径")
    file_desc = fields.CharField(max_length=2048, null=True, description="接口文件场景描述")
    dataset = fields.JSONField(description="接口文件解析后的数据集")

    class Meta:
        table = "krun_autotest_data_create"
        table_description = "自动化测试-接口文件生成记录表"
        unique_together = (
            ("case_id", "step_code", "create_code"),
        )
        indexes = (
            ("case_id", "state"),
            ("case_code", "state"),
            ("create_code", "state"),
        )
        ordering = ["case_id", "step_code"]

    def __str__(self):
        return self.create_code
