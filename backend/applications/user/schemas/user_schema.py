# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : user_schema.py
@DateTime: 2025/1/18 11:58
"""
import os.path
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field, FilePath

from backend import PROJECT_CONFIG


class UserCreate(BaseModel):
    username: str = Field(example="zhangsan", description="用户账号")
    password: str = Field(example="123456", description="用户密码")
    alias: str = Field(example="张三", description="用户姓名")
    email: EmailStr = Field(example="zhangsan@test.com", description="用户邮箱")
    phone: str = Field(example="15800001234", description="用户电话")
    avatar: str = Field(
        example="/static/avatar/default/20250101010101.png",
        default="/static/avatar/default/20250101010101.png",
        description="用户头像路径"
    )
    state: int = Field(example=1, default=1, description="用户状态(0:离职,1:正常,2:休假,3:出差,4:待岗)")
    is_active: bool = Field(example=True, default=True, description="是否激活")
    is_superuser: bool = Field(example=False, default=False, description="是否为超级管理员")
    role_ids: Optional[List[int]] = Field(example=[], default=[], description="角色ID")
    dept_id: Optional[int] = Field(example=[0], default=[], description="部门ID")

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class UserUpdate(BaseModel):
    id: int
    password: Optional[str] = None
    alias: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    state: Optional[int] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    role_ids: Optional[List[int]] = None
    dept_id: Optional[int] = None
    updated_user: Optional[str] = None


class UserSelect(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: Optional[list] = Field(default=[], examples=["id"], description="排序字段")
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
