# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : user_model.py
@DateTime: 2025/1/18 11:39
"""
from tortoise import fields

from backend.services.base_model import BaseModel, TimestampMixin


class User(BaseModel, TimestampMixin):
    username = fields.CharField(max_length=16, unique=True, description="用户账号")
    password = fields.CharField(max_length=128, description="用户密码")
    alias = fields.CharField(max_length=32, index=True, description="用户姓名")
    email = fields.CharField(max_length=64, unique=True, description="用户邮箱")
    phone = fields.CharField(max_length=20, description="用户电话")
    is_active = fields.BooleanField(default=True, index=True, description="是否激活")
    is_superuser = fields.BooleanField(default=False, index=True, description="是否为超级管理员")
    last_login = fields.DatetimeField(null=True, description="最后登录时间")

    class Meta:
        table = "krun_user"
