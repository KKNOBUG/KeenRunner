# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : scaffold_model.py
@DateTime: 2025/1/27 10:04
"""
from tortoise import fields

from backend.enums.http_enum import HTTPMethod
from backend.enums.menu_enum import MenuType
from backend.applications.base.services.scaffold import ScaffoldModel, MaintainMixin, TimestampMixin


class Api(ScaffoldModel, MaintainMixin, TimestampMixin):
    path = fields.CharField(max_length=128, index=True, description="API路径")
    method = fields.CharEnumField(HTTPMethod, description="API方式")
    summary = fields.CharField(max_length=128, index=True, description='API简介')
    tags = fields.CharField(max_length=128, index=True, description='API标签')
    description = fields.TextField(null=True, description="API描述")

    class Meta:
        table = "krun_api"
        unique_together = (
            ("method", "path"),
        )


class Menu(ScaffoldModel, TimestampMixin):
    name = fields.CharField(max_length=32, index=True, description="菜单名称")
    remark = fields.JSONField(null=True, description="保留字段")
    menu_type = fields.CharEnumField(MenuType, index=True, null=True, description="菜单类型")
    icon = fields.CharField(max_length=128, null=True, description="菜单图标")
    path = fields.CharField(max_length=128, index=True, description="菜单路径")
    order = fields.IntField(default=0, index=True, description="排序")
    parent_id = fields.IntField(default=0, max_length=16, index=True, description="父菜单ID")
    is_hidden = fields.BooleanField(default=False, description="是否隐藏")
    component = fields.CharField(max_length=128, description="组件")
    keepalive = fields.BooleanField(default=True, description="存活")
    redirect = fields.CharField(max_length=128, null=True, description="重定向")

    class Meta:
        table = "krun_menu"


class Audit(ScaffoldModel, TimestampMixin):
    user_id = fields.IntField(index=True, description="用户ID")
    username = fields.CharField(max_length=64, default="", index=True, description="用户名称")
    module = fields.CharField(max_length=64, default="", index=True, description="功能模块")
    summary = fields.CharField(max_length=128, default="", index=True, description="请求描述")
    method = fields.CharField(max_length=16, default="", index=True, description="请求方法")
    path = fields.CharField(max_length=255, default="", index=True, description="请求路径")
    status = fields.IntField(default=-1, index=True, description="状态码")
    response_time = fields.IntField(default=0, index=True, description="响应时间(单位ms)")

    class Meta:
        table = "krun_audit"
