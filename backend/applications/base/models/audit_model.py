# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : scaffold_model.py
@DateTime: 2025/1/27 10:04
"""
from tortoise import fields

from backend.applications.base.services.scaffold import ScaffoldModel, TimestampMixin
from backend.enums.http_enum import HTTPMethod


class Audit(ScaffoldModel, TimestampMixin):
    user_id = fields.BigIntField(index=True, description="用户ID")
    username = fields.CharField(max_length=32, index=True, description="用户名称")
    request_time = fields.DatetimeField(index=True, description="请求时间")
    request_tags = fields.CharField(max_length=255, default="", null=True, index=True, description="请求模块")
    request_summary = fields.CharField(max_length=255, default="", null=True, index=True, description="请求接口")
    request_method = fields.CharEnumField(HTTPMethod, index=True, description="请求方式")
    request_router = fields.CharField(max_length=255, index=True, description="请求路由")
    request_client = fields.CharField(max_length=16, default="", null=True, description="请求来源")
    request_header = fields.JSONField(default=None, null=True, description="请求头部")
    request_params = fields.TextField(default="", null=True, description="请求参数")
    response_time = fields.DatetimeField(index=True, description="响应时间")
    response_header = fields.JSONField(default=None, null=True, description="响应头部")
    response_code = fields.CharField(max_length=16, default="", null=True, index=True, description="响应代码")
    response_message = fields.CharField(max_length=512, default="", null=True, description="响应消息")
    response_params = fields.TextField(default="", null=True, description="响应参数")
    response_elapsed = fields.CharField(max_length=16, description="响应耗时")

    class Meta:
        table = "krun_audit"
