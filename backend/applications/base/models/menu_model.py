# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : menu_model.py
@DateTime: 2025/2/19 22:42
"""
from tortoise import fields

from backend.enums.menu_enum import MenuType
from backend.applications.base.services.scaffold import ScaffoldModel, MaintainMixin, TimestampMixin


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
