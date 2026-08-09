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
    """部门信息模型，最多两级树。"""

    code = fields.CharField(max_length=16, unique=True, description="部门代码")
    name = fields.CharField(max_length=64, unique=True, description="部门名称")
    description = fields.CharField(max_length=255, null=True, description="部门描述")
    order = fields.IntField(default=0, index=True, description="排序")
    parent_id = fields.IntField(default=0, max_length=10, index=True, description="父部门ID")

    class Meta:
        table = "krun_dept"


class DeptStruct(ScaffoldModel, TimestampMixin):
    """部门闭包表模型，ancestor/descendant关系。"""

    ancestor = fields.IntField(index=True, description="父部门")
    descendant = fields.IntField(index=True, description="子部门")
    level = fields.IntField(default=0, index=True, description="深度")

    class Meta:
        table = "krun_dept_nest"
