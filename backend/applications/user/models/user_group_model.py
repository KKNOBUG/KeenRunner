# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : user_group_model.py
@DateTime: 2025/2/11 17:19
"""
from tortoise import fields

from backend.services.base_model import BaseModel


class UserGroup(BaseModel):
    user = fields.ForeignKeyField(
        index=True,
        related_name="user_groups",
        model_name="models.User",
        on_delete=fields.CASCADE,
        description="用户ID",
    )
    group = fields.ForeignKeyField(
        related_name="group_groups",
        model_name="models.Group",
        on_delete=fields.CASCADE,
        description="小组ID",
    )

    class Meta:
        table = "krun_user_group"
        unique_together = (
            ("user", "group"),
        )
