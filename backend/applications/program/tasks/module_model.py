# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : module_model.py
@DateTime: 2025/3/7 12:35
"""
from tortoise import fields

from backend.applications.base.services.scaffold import (
    ScaffoldModel,
    StateModel,
    MaintainMixin,
    TimestampMixin
)


class Module(ScaffoldModel, StateModel, MaintainMixin, TimestampMixin):
    code = fields.CharField(max_length=16, unique=True, description="模块代码")
    name = fields.CharField(max_length=64, unique=True, description="模块名称")
    description = fields.TextField(null=True, description="模块描述")
    project = fields.ForeignKeyField(
        model_name="project_model.Project",
        related_name="modules"
    )

    class Meta:
        table = "krun_module"
