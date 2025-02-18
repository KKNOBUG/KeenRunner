# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : module_model.py
@DateTime: 2025/2/11 17:24
"""
from tortoise import fields

from backend.services.base_model import BaseModel, TimestampMixin, MaintainMixin


class Module(BaseModel, TimestampMixin, MaintainMixin):
    code = fields.CharField(max_length=16, unique=True, description="模块名称")
    name = fields.CharField(max_length=64, unique=True, description="模块名称")
    leader = fields.ForeignKeyField(
        null=True,
        index=True,
        related_name="leader_modules",
        model_name="models.Project",
        on_delete=fields.CASCADE,
        description="所属项目",
    )
    description = fields.TextField(null=True, description="模块描述")
    state = fields.SmallIntField(default=0, description="模块状态(0:未启用,1:已启用)")

    class Meta:
        table = "krun_module"
