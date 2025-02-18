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
from backend.services.base_model import BaseModel, MaintainMixin, TimestampMixin


class Api(BaseModel, MaintainMixin, TimestampMixin):
    path = fields.CharField(max_length=128, description="API路径")
    method = fields.CharEnumField(HTTPMethod, description="请求方式")
    summary = fields.CharField(max_length=128, description='请求简介', unique=True)
    description = fields.TextField(null=True, description="请求描述")
    tags = fields.CharField(max_length=128, description='请求标签')
    state = fields.SmallIntField(default=0, description='接口状态(0:未删除,1:已删除)')

    class Meta:
        table = "krun_api"
        unique_together = (
            ("method", "path"),
        )
