# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : user_schmea.py
@DateTime: 2025/1/18 11:58
"""
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(example="admin")
    password: str = Field(example="123456")
    alias: str = Field(example="张三")
    email: EmailStr = Field(example="admin@test.com")
    phone: str = Field(example="18800009999")
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class UserUpdate(BaseModel):
    id: int
    email: EmailStr
    username: str
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
