# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : role_model.py
@DateTime: 2025/2/11 17:19
"""
from tortoise import fields

from backend.applications.base.services.scaffold import ScaffoldModel, TimestampMixin


class Role(ScaffoldModel, TimestampMixin):
    code = fields.CharField(max_length=16, unique=True, description="角色代码")
    name = fields.CharField(max_length=64, unique=True, description="角色名称")
    description = fields.TextField(null=True, description="角色描述")
    menus = fields.ManyToManyField(
        model_name="models.Menu",
        related_name="role_menus",
        through="krun_role_menus",
    )
    routers = fields.ManyToManyField(
        model_name="models.Router",
        related_name="role_routers",
        through="krun_role_routers"
    )

    class Meta:
        table = "krun_role"
