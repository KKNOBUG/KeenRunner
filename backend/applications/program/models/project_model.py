# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : project_model.py
@DateTime: 2025/3/7 12:28
"""
from tortoise import fields

from backend.applications.base.services.scaffold import ScaffoldModel, StateModel, ClassModel, TimestampMixin


class Project(ScaffoldModel, ClassModel, StateModel, TimestampMixin):
    dev_owner = fields.ForeignKeyField(
        model_name="models.User",
        related_name="project_dev_owner",
        description="项目开发负责人"
    )
    test_owner = fields.ForeignKeyField(
        model_name="models.User",
        related_name="project_test_owner",
        description="项目测试负责人"
    )

    class Meta:
        table = "krun_program_project"
