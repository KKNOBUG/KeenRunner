# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : role_tag_scope_model.py
@DateTime: 2026/10/28
"""
from tortoise import fields

from backend.applications.base.services.scaffold import ScaffoldModel, MaintainMixin, TimestampMixin
from backend.enums import DataScopeEnum


class RoleTag(ScaffoldModel, MaintainMixin, TimestampMixin):
    """角色按资源族标签覆盖的数据范围。"""

    role = fields.ForeignKeyField(model_name="models.Role", related_name="tag_scopes", on_delete=fields.CASCADE, description="角色")
    tag = fields.CharField(max_length=64, index=True, description="资源族标签(一级目录:二级模块)")
    select_scope = fields.CharEnumField(DataScopeEnum, null=True, default=None, max_length=16, description="数据可见范围(空表示按角色默认)")
    update_scope = fields.CharEnumField(DataScopeEnum, null=True, default=None, max_length=16, description="数据可写范围(空表示按角色默认)")
    delete_scope = fields.CharEnumField(DataScopeEnum, null=True, default=None, max_length=16, description="数据可删范围(空表示按角色默认)")

    class Meta:
        table = "krun_role_tag_scope"
        unique_together = (
            ("role", "tag"),
        )