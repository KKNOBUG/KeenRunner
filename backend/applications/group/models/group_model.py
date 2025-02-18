# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : group_model.py
@DateTime: 2025/2/3 22:21
"""
from tortoise import fields

from backend.services.base_model import BaseModel, TimestampMixin, MaintainMixin


class Group(BaseModel, TimestampMixin, MaintainMixin):
    code = fields.CharField(max_length=16, unique=True, description="小组代码")
    name = fields.CharField(max_length=64, unique=True, description="小组名称")
    leader = fields.ForeignKeyField(
        null=True,
        index=True,
        related_name="leader_groups",
        model_name="models.User",
        on_delete=fields.RESTRICT,
        description="小组所属组长ID",
    )
    department = fields.ForeignKeyField(
        null=True,
        index=True,
        related_name="department_groups",
        model_name="models.Department",
        on_delete=fields.RESTRICT,
        description="小组所属部门ID",
    )
    description = fields.TextField(null=True, description="小组描述")
    state = fields.SmallIntField(default=1, description="小组状态(0:空闲,1:忙碌,2:调整,3:培训)")

    class Meta:
        table = "krun_group"
