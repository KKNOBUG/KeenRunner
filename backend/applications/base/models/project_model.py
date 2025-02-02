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
    name = fields.CharField(max_length=128, description="项目名称", index=True)
    initiator = fields.CharField(max_length=32, description="项目负责人", index=True)
    test_captain = fields.CharField(max_length=32, description="测试负责人", index=True)
    test_team = fields.TextField(default=None, description="测试成员")
    dev_captain = fields.CharField(max_length=32, description="开发负责人", index=True)
    dev_team = fields.TextField(default=None, description="开发成员")
    release = fields.CharField(max_length=16, description="项目版本")
    description = fields.TextField(default=None, description="项目描述")
    is_active = fields.BooleanField(default=True, description="是否激活")

    class Meta:
        table = "krun_project"
