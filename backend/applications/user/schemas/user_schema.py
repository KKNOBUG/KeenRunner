# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : user_schema.py
@DateTime: 2025/1/18 11:58
"""
import os.path
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, FilePath

from backend import PROJECT_CONFIG


class UserCreate(BaseModel):
    username: str = Field(example="zhangsan", description="用户账号")
    password: str = Field(example="123456", description="用户密码")
    alias: str = Field(example="张三", description="用户姓名")
    email: EmailStr = Field(example="zhangsan@test.com", description="用户邮箱")
    phone: str = Field(example="15800001234", description="用户电话")
    avatar: str = Field(
        example=os.path.join(PROJECT_CONFIG.STATIC_IMG_DIR, "20250220204648.png"),
        default=None,
        description="用户头像路径"
    )
    state: int = Field(example=2, description="用户状态(0:正常,1:离职,2:待岗,3:休假,4:出差)")
    is_active: bool = Field(example=True, description="是否激活")
    is_superuser: bool = Field(example=True, description="是否为超级管理员")

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class UserUpdate(BaseModel):
    id: int
    password: Optional[str] = None
    alias: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[bool] = None
    avatar: Optional[FilePath] = None
    state: Optional[int] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    updated_user: Optional[str] = None


class UserSelect(BaseModel):
    page_num: int = Field(default=1, ge=1, description="数据页码")
    page_size: int = Field(default=10, ge=10, description="数据数量")
    page_order: Optional[list] = Field(default=[], examples=["id"], description="数据排序")
    username: Optional[str] = None
    alias: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[bool] = None
    state: Optional[int] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    created_user: Optional[bool] = None
    updated_user: Optional[bool] = None
    created_time: Optional[str] = None
    updated_time: Optional[str] = None
