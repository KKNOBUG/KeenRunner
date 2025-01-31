# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : api_model.py
@DateTime: 2025/1/27 10:04
"""
from tortoise import fields

from backend.enums.http_enum import HTTPMethod
from backend.services.base_model import BaseModel, TimestampMixin


class Api(BaseModel, TimestampMixin):
    path = fields.CharField(max_length=128, description="API路径", index=True)
    method = fields.CharEnumField(HTTPMethod, description="请求方法")
    summary = fields.CharField(max_length=255, description="请求简介")
    description = fields.TextField(default=None, description="请求描述")
    tags = fields.CharField(max_length=64, description="API标签", index=True)
    is_active = fields.BooleanField(default=True, description="是否激活")

    class Meta:
        table = "krun_api"
