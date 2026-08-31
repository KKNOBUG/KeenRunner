# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_tag_model.py
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


class AutoTestTagModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    tag_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="标签标识代码")
    tag_project = fields.IntField(default=1, ge=1, index=True, description="标签所属应用")
    tag_mode = fields.CharField(max_length=64, null=True, description="标签大类")
    tag_name = fields.CharField(max_length=64, null=True, description="标签名称")
    tag_desc = fields.CharField(max_length=2048, null=True, description="标签描述")

    class Meta:
        table = "krun_autotest_tag"
        table_description = "自动化测试-标签信息表"
        unique_together = (
            ("tag_project", "tag_mode", "tag_name"),
        )
        indexes = (
            ("tag_mode", "tag_name"),
            ("tag_project", "state", "updated_time"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        """返回标签名称。"""
        return self.tag_name
