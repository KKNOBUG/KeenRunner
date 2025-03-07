# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : project_model.py
@DateTime: 2025/3/7 12:28
"""
from tortoise import fields

from backend.applications.base.services.scaffold import ScaffoldModel, MaintainMixin, TimestampMixin


class Project(ScaffoldModel, MaintainMixin, TimestampMixin):
    code = fields.CharField(max_length=16, unique=True, description="项目代码")
    name = fields.CharField(max_length=64, unique=True, description="项目名称")
    state = fields.SmallIntField(default=1, index=True, description='项目状态')
    description = fields.TextField(null=True, description="项目描述")

    class Meta:
        table = "krun_project"
