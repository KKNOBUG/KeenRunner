# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : module_model.py
@DateTime: 2025/3/7 12:35
"""
from tortoise import fields

from backend.applications.base.services.scaffold import ScaffoldModel, MaintainMixin, TimestampMixin


class Module(ScaffoldModel, MaintainMixin, TimestampMixin):
    code = fields.CharField(max_length=16, unique=True, description="模块代码")
    name = fields.CharField(max_length=64, unique=True, description="模块名称")
    state = fields.SmallIntField(default=1, index=True, description='模块状态')
    description = fields.TextField(null=True, description="模块描述")

    class Meta:
        table = "krun_module"
