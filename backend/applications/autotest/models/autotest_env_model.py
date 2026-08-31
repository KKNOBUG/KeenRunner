# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_env_model.py
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


class AutoTestEnvModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    """环境枚举主数据；主键对外语义为env_enum_id；仅存全局环境名。"""

    env_name = fields.CharField(max_length=128, unique=True, description="环境名称")
    env_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="环境标识代码")

    class Meta:
        table = "krun_autotest_env"
        table_description = "自动化测试-环境枚举表"
        ordering = ["-updated_time"]

    def __str__(self):
        """返回环境名称。"""
        return self.env_name
