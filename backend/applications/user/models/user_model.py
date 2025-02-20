# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : user_model.py
@DateTime: 2025/1/18 11:39
"""
from tortoise import fields

from backend.applications.base.services.scaffold import ScaffoldModel, TimestampMixin, MaintainMixin

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class User(ScaffoldModel, TimestampMixin, MaintainMixin):
    username = fields.CharField(max_length=32, unique=True, description="用户账号", index=True)
    password = fields.CharField(max_length=255, null=True, description="用户密码")
    alias = fields.CharField(max_length=64, index=True, description="用户姓名")
    email = fields.CharField(max_length=64, unique=True, description="用户邮箱")
    phone = fields.CharField(max_length=20, description="用户电话")
    avatar = fields.CharField(max_length=255, default=None, null=True, description="用户头像")
    state = fields.SmallIntField(default=2, index=True, description='用户状态(0:离职,1:正常,2:休假,3:出差,4:待岗)')
    is_active = fields.BooleanField(default=True, index=True, description="是否激活")
    is_superuser = fields.BooleanField(default=False, index=True, description="是否为超级管理员")
    last_login = fields.DatetimeField(null=True, index=True, description="最后一次登陆时间")
    roles = fields.ManyToManyField(
        model_name="models.Role",
        related_name="user_roles",
        through="krun_user_role",
    )
    dept_id = fields.IntField(null=True, index=True, description="所属部门ID")

    class Meta:
        table = "krun_user"
