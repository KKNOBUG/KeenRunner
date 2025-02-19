# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : user_schema.py
@DateTime: 2025/1/18 11:58
"""
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, FilePath


class UserCreate(BaseModel):
    username: str = Field(example="admin", description="用户账号")
    password: str = Field(example="123456", description="用户密码")
    alias: str = Field(example="管理员", description="用户姓名")
    email: EmailStr = Field(example="admin@test.com", description="用户邮箱")
    phone: str = Field(example="18888888888", description="用户电话")
    image: str = Field(example="/static/image/IMG-USER-ADMIN.png", default=None, description="用户头像路径")
    state: int = Field(example=2, description="用户状态(0:正常,1:离职,2:待岗,3:休假,4:出差)")
    level: int = Field(example=0, description="用户等级(0:普通职工,1:小组组长,2:部门领导,3:待定,9:系统管理员)")
    department_id: int = Field(example=1, default=None, description="用户所属部门ID")

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class UserUpdate(BaseModel):
    id: int
    password: Optional[str] = None
    alias: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[bool] = None
    image: Optional[FilePath] = None
    state: Optional[int] = None
    level: Optional[int] = None
    department_id: Optional[int] = None
    updated_user: Optional[str] = None


class UserSelect(BaseModel):
    page_num: int = Field(default=1, ge=1, description="数据页码")
    page_size: int = Field(default=10, ge=10, description="数据数量")
    page_order: Optional[list] = Field(default=[], examples=["id"], description="数据排序")
    username: Optional[str] = None
    alias: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[bool] = None
    image: Optional[FilePath] = None
    state: Optional[int] = None
    level: Optional[int] = None
    department_id: Optional[int] = None
    created_user: Optional[bool] = None
    updated_user: Optional[bool] = None
    created_time: Optional[str] = None
    updated_time: Optional[str] = None
