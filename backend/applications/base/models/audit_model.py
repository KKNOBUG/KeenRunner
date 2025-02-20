# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : scaffold_model.py
@DateTime: 2025/1/27 10:04
"""
from tortoise import fields

from backend.applications.base.services.scaffold import ScaffoldModel, MaintainMixin, TimestampMixin


class Audit(ScaffoldModel, TimestampMixin):
    user_id = fields.BigIntField(index=True, description="用户ID")
    username = fields.CharField(max_length=32, default="", index=True, description="用户名称")
    module = fields.CharField(max_length=64, default="", index=True, description="功能模块")
    summary = fields.CharField(max_length=128, default="", index=True, description="请求描述")
    method = fields.CharField(max_length=16, default="", index=True, description="请求方法")
    path = fields.CharField(max_length=255, default="", index=True, description="请求路径")
    status = fields.SmallIntField(default=-1, index=True, description="状态码")
    response_time = fields.IntField(default=0, index=True, description="响应时间(单位ms)")

    class Meta:
        table = "krun_audit"
