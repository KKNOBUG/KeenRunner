# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : user_model.py
@DateTime: 2025/1/18 11:39
"""
from tortoise import fields

from backend.applications.base.services.scaffold import ScaffoldModel, TimestampMixin, MaintainMixin, StateModel


class User(ScaffoldModel, StateModel, TimestampMixin, MaintainMixin):
    """系统用户模型。"""

    username = fields.CharField(max_length=32, unique=True, description="用户账号")
    password = fields.CharField(max_length=255, description="用户密码")
    alias = fields.CharField(max_length=64, description="用户姓名")
    email = fields.CharField(max_length=64, description="用户邮箱")
    phone = fields.CharField(max_length=20, null=True, description="用户电话")
    motto = fields.CharField(max_length=255, null=True, description="用户签名")
    avatar = fields.CharField(max_length=255, null=True, description="用户头像")
    is_superuser = fields.BooleanField(default=False, index=True, description="是否为超级管理员")
    last_login = fields.DatetimeField(null=True, index=True, description="最后一次登陆时间")
    token_version = fields.IntField(default=0, description="Token版本号，用于吊销用户所有Token")
    address = fields.CharField(max_length=255, null=True, description="用户住址")
    gender = fields.SmallIntField(default=0, description="用户性别: 0未知 1男 2女")
    user_type = fields.SmallIntField(default=0, description="用户类型：0xx 1xx 2xx")
    emergency_name = fields.CharField(max_length=32, null=True, description="紧急联系人")
    emergency_phone = fields.CharField(max_length=20, null=True, description="紧急联系电话")
    roles = fields.ManyToManyField(
        model_name="models.Role",
        related_name="user_roles",
        through="krun_user_role",
    )
    dept_id = fields.IntField(null=True, index=True, description="所属部门ID")

    class Meta:
        table = "krun_user"
        unique_together = (
            ("alias", "email"),
        )
