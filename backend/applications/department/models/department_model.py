# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : department_model.py
@DateTime: 2025/2/3 16:23
"""
from tortoise import fields

from backend.services.base_model import BaseModel, TimestampMixin, MaintainMixin


class Department(BaseModel, TimestampMixin, MaintainMixin):
    code = fields.CharField(max_length=16, unique=True, description="部门代码")
    name = fields.CharField(max_length=64, unique=True, description="部门名称")
    leader = fields.ForeignKeyField(
        null=True,
        index=True,
        related_name="leader_departments",
        model_name="models.User",
        on_delete=fields.SET_NULL,
        description="部门所属领导ID",
    )
    description = fields.TextField(null=True, description="部门描述")
    state = fields.SmallIntField(default=0, index=True, description='部门状态(0:启用,1:解散,2:调整,3:冻结)')

    class Meta:
        table = "krun_department"
