# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : module_model.py
@DateTime: 2025/4/5 12:25
"""
from tortoise import fields

from backend.applications.base.services.scaffold import ScaffoldModel, ClassModel, MaintainMixin, TimestampMixin


class Module(ScaffoldModel, ClassModel, MaintainMixin, TimestampMixin):
    dev_owner = fields.ForeignKeyField(
        model_name="models.User",
        related_name="module_dev_owner",
        description="模块开发负责人"
    )
    test_owner = fields.ForeignKeyField(
        model_name="models.User",
        related_name="module_test_owner",
        description="模块测试负责人"
    )
    project = fields.ForeignKeyField(
        model_name="models.Project",
        related_name="module_projects",
        description="所属项目"
    )

    class Meta:
        table = "krun_program_module"
