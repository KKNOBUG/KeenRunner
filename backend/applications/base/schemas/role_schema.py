# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : role_schema.py
@DateTime: 2025/2/19 23:05
"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class BaseRole(BaseModel):
    id: int
    name: str
    desc: str = ""
    users: Optional[list] = []
    menus: Optional[list] = []
    apis: Optional[list] = []
    created_time: Optional[datetime]
    updated_time: Optional[datetime]


class RoleCreate(BaseModel):
    code: str = Field(example="AD-9001", description="角色代码")
    name: str = Field(example="管理员", description="角色名称")
    description: str = Field(default="", example="管理员角色")


class RoleUpdate(BaseModel):
    id: int = Field(example=1)
    code: str = Field(example="AD-9001")
    name: str = Field(example="管理员")
    description: str = Field(default="", example="管理员角色")


class RoleUpdateMenusApis(BaseModel):
    id: int
    menu_ids: List[int] = []
    api_infos: List[dict] = []
