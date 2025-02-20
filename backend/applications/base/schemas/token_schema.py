# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : token_schema.py
@DateTime: 2025/1/18 12:07
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CredentialsSchema(BaseModel):
    username: str = Field(..., description="用户账号[电子邮箱或手机号码]", example="admin@test.com")
    password: str = Field(..., description="用户密码[a-zZ-Z0-9_-.*@!]", example="123456")


class JWTOut(BaseModel):
    access_token: str
    username: str
    alias: str
    email: str
    phone: str
    avatar: str
    state: int
    is_active: bool
    is_superuser: bool
    last_login: Optional[datetime]


class JWTPayload(BaseModel):
    user_id: int
    username: str
    state: int
    is_superuser: bool
    exp: datetime
