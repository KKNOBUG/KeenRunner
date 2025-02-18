# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : project_group_model.py
@DateTime: 2025/2/11 17:27
"""
from tortoise import fields

from backend.services.base_model import BaseModel


class ProjectGroup(BaseModel):
    project = fields.ForeignKeyField(
        index=True,
        related_name="project_projects",
        model_name="models.Project",
        on_delete=fields.CASCADE,
        description="项目ID",
    )
    group = fields.ForeignKeyField(
        related_name="group_projects",
        model_name="models.Group",
        on_delete=fields.CASCADE,
        description="模块ID",
    )

    class Meta:
        table = "krun_project_group"
        unique_together = (
            ("project", "group"),
        )
