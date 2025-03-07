# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : router_model.py
@DateTime: 2025/2/19 22:41
"""
from tortoise import fields

from backend.enums.http_enum import HTTPMethod
from backend.applications.base.services.scaffold import ScaffoldModel, MaintainMixin, TimestampMixin


class Router(ScaffoldModel, MaintainMixin, TimestampMixin):
    path = fields.CharField(max_length=255, index=True, description="路由请求路径")
    method = fields.CharEnumField(HTTPMethod, description="路由请求方式")
    summary = fields.CharField(max_length=128, index=True, description='路由作用简介')
    tags = fields.CharField(max_length=128, index=True, description='路由所属标签')
    description = fields.TextField(null=True, description="路由功能描述")

    class Meta:
        table = "krun_router"
        unique_together = (
            ("method", "path"),
        )
