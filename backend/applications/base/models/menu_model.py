# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : menu_model.py
@DateTime: 2025/2/19 22:42
"""
from tortoise import fields

from backend.applications.base.services.scaffold import (
    MaintainMixin,
    ScaffoldModel,
    TimestampMixin,
)
from backend.enums import MenuType


class Menu(ScaffoldModel, MaintainMixin, TimestampMixin):
    """菜单模型。"""

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
        # (name, path) 联合唯一：并发创建同名校验会同时通过，靠唯一索引兜底幂等
        # (parent_id, path) 联合唯一：前端路由全路径=父path+子path，同级重复path会导致后注册路由不可达
        unique_together = (("name", "path"), ("parent_id", "path"))

    def __str__(self):
        return f"Menu(name={self.name}, menu_type={self.menu_type}, path={self.path})"
