# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : dept_model.py
@DateTime: 2025/2/3 16:23
"""
from tortoise import fields

from backend.applications.base.services.scaffold import ScaffoldModel, TimestampMixin, MaintainMixin


class Department(ScaffoldModel, TimestampMixin, MaintainMixin):
    code = fields.CharField(max_length=16, unique=True, description="部门代码")
    name = fields.CharField(max_length=64, unique=True, description="部门名称")
    description = fields.TextField(null=True, description="部门描述")
    is_deleted = fields.BooleanField(default=False, index=True, description="软删除标记")
    order = fields.IntField(default=0, index=True, description="排序")
    parent_id = fields.IntField(default=0, max_length=10, index=True, description="父部门ID")

    class Meta:
        table = "krun_dept"


class DeptStruct(ScaffoldModel, TimestampMixin):
    ancestor = fields.IntField(index=True, description="父部门")
    descendant = fields.IntField(index=True, description="子部门")
    level = fields.IntField(default=0, index=True, description="深度")

    class Meta:
        table = "krun_dept_nest"
