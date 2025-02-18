# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : project_model.py
@DateTime: 2025/2/2 13:11
"""
from tortoise import fields

from backend.services.base_model import BaseModel, TimestampMixin, MaintainMixin


class Project(BaseModel, TimestampMixin, MaintainMixin):
    code = fields.CharField(max_length=16, unique=True, description="项目代码")
    name = fields.CharField(max_length=64, unique=True, description="项目名称")
    leader = fields.ForeignKeyField(
        null=True,
        index=True,
        related_name="leader_projects",
        model_name="models.User",
        on_delete=fields.CASCADE,
        description="项目负责人",
    )
    release = fields.CharField(max_length=32, description="项目版本")
    description = fields.TextField(null=True, description="项目描述")
    state = fields.SmallIntField(default=0, description="项目状态(0:未启用,1:已启用)")

    class Meta:
        table = "krun_project"
