# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : user_model.py
@DateTime: 2025/1/18 11:39
"""
from tortoise import fields

from backend.services.base_model import BaseModel, TimestampMixin, MaintainMixin

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(BaseModel, TimestampMixin, MaintainMixin):
    username = fields.CharField(max_length=32, unique=True, description="用户账号")
    password = fields.CharField(max_length=255, description="用户密码")
    alias = fields.CharField(max_length=64, index=True, description="用户姓名")
    email = fields.CharField(max_length=64, unique=True, description="用户邮箱")
    phone = fields.CharField(max_length=20, description="用户电话")
    image = fields.CharField(max_length=255, default=None, null=True, description="用户头像")
    state = fields.SmallIntField(default=2, index=True, description='用户状态(0:未启用,1:离职,2:正常,3:休假,4:出差)')
    level = fields.SmallIntField(default=0, index=True, description='用户等级(0:普通职工,1:小组组长,2:部门领导,3:待定,9:系统管理员)')
    last_login = fields.DatetimeField(null=True, index=True, description="最后一次登陆时间")
    department = fields.ForeignKeyField(
        null=True,
        index=True,
        related_name="department_users",
        model_name="models.Department",
        on_delete=fields.SET_NULL,
        description="用户所属部门ID",
    )

    class Meta:
        table = "krun_user"

    @classmethod
    async def create_user(cls, user_data):
        user_data["password"] = pwd_context.hash(user_data["password"])
        return await cls.create(**user_data)
