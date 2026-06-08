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


class TokenBase(BaseModel):
    user_id: Optional[int] = Field(default=None, description="用户ID")
    username: Optional[str] = Field(default=None, max_length=32, description="用户账号")
    password: Optional[str] = Field(default=None, max_length=255, description="用户密码")
    alias: Optional[str] = Field(default=None, max_length=64, description="用户姓名")
    email: Optional[str] = Field(default=None, max_length=64, description="用户邮箱")
    phone: Optional[str] = Field(default=None, max_length=20, description="用户电话")
    avatar: Optional[str] = Field(default=None, max_length=255, description="用户头像")
    state: Optional[int] = Field(default=None, description="用户状态")
    is_active: Optional[bool] = Field(default=None, description="是否激活")
    is_superuser: Optional[bool] = Field(default=None, description="是否为超级管理员")
    last_login: Optional[datetime] = Field(default=None, description="最后一次登录时间")
    access_token: Optional[str] = Field(default=None, description="访问令牌")
    exp: Optional[datetime] = Field(default=None, description="令牌过期时间")


class CredentialsSchema(TokenBase):
    username: str = Field(..., max_length=32, description="用户账号[电子邮箱或手机号码]")
    password: str = Field(..., max_length=255, description="用户密码[a-zZ-Z0-9_-.*@!]")


class JWTOut(TokenBase):
    access_token: str = Field(..., description="访问令牌")
    username: str = Field(..., max_length=32, description="用户账号")
    alias: str = Field(..., max_length=64, description="用户姓名")
    email: str = Field(..., max_length=64, description="用户邮箱")
    phone: Optional[str] = Field(default=None, max_length=20, description="用户电话")
    avatar: str = Field(..., max_length=255, description="用户头像")
    state: int = Field(..., description="用户状态")
    is_active: bool = Field(..., description="是否激活")
    is_superuser: bool = Field(..., description="是否为超级管理员")
    last_login: Optional[datetime] = Field(default=None, description="最后一次登录时间")


class JWTPayload(TokenBase):
    user_id: int = Field(..., description="用户ID")
    username: str = Field(..., max_length=32, description="用户账号")
    state: int = Field(..., description="用户状态")
    is_superuser: bool = Field(..., description="是否为超级管理员")
    token_version: int = Field(default=0, description="Token版本号")
    exp: datetime = Field(..., description="令牌过期时间")
