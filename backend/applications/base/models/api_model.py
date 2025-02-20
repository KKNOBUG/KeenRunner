# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : api_model.py
@DateTime: 2025/2/19 22:41
"""
from tortoise import fields

from backend.enums.http_enum import HTTPMethod
from backend.applications.base.services.scaffold import ScaffoldModel, MaintainMixin, TimestampMixin


class Api(ScaffoldModel, MaintainMixin, TimestampMixin):
    path = fields.CharField(max_length=255, index=True, description="API路径")
    method = fields.CharEnumField(HTTPMethod, description="API方式")
    summary = fields.CharField(max_length=128, index=True, description='API简介')
    tags = fields.CharField(max_length=128, index=True, description='API标签')
    description = fields.TextField(null=True, description="API描述")

    class Meta:
        table = "krun_api"
        unique_together = (
            ("method", "path"),
        )
