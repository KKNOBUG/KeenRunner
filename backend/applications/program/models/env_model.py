# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : env_model.py
@DateTime: 2025/3/8 20:21
"""
from tortoise import fields

from backend.applications.base.services.scaffold import ScaffoldModel, MaintainMixin, TimestampMixin


class Environment(ScaffoldModel, MaintainMixin, TimestampMixin):
    name = fields.CharField(max_length=64, unique=True, description="环境名称")
    host = fields.CharField(max_length=16, description="环境地址")
    port = fields.IntField(description="环境端口")
    description = fields.TextField(null=True, description="描述")
    project = fields.ForeignKeyField(
        model_name="models.Project",
        related_name="env_projects",
        description="所属应用"
    )

    class Meta:
        table = "krun_program_env"
        unique_together = (
            ("host", "port"),
        )
