# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : menu_schema.py
@DateTime: 2025/2/19 12:49
"""
from typing import Optional, List

from pydantic import BaseModel, Field

from backend.enums.base_enum_cls import StringEnum


class MenuType(StringEnum):
    CATALOG = "catalog"
    MENU = "menu"


class BaseMenu(BaseModel):
    id: int
    name: str
    path: str
    remark: Optional[dict]
    menu_type: Optional[MenuType]
    icon: Optional[str]
    order: int
    parent_id: int
    is_hidden: bool
    component: str
    keepalive: bool
    redirect: Optional[str]
    children: Optional[List["BaseMenu"]]


class MenuCreate(BaseModel):
    menu_type: MenuType = Field(default=MenuType.CATALOG.value)
    name: str = Field(example="用户管理")
    icon: Optional[str] = "ph:user-list-bold"
    path: str = Field(example="/system/user")
    order: Optional[int] = Field(example=1)
    parent_id: Optional[int] = Field(example=0, default=0)
    is_hidden: Optional[bool] = False
    component: str = Field(default="Layout", example="/system/user")
    keepalive: Optional[bool] = True
    redirect: Optional[str] = ""


class MenuUpdate(BaseModel):
    id: int
    menu_type: Optional[MenuType] = Field(example=MenuType.CATALOG.value)
    name: Optional[str] = Field(example="用户管理")
    icon: Optional[str] = "ph:user-list-bold"
    path: Optional[str] = Field(example="/system/user")
    order: Optional[int] = Field(example=1)
    parent_id: Optional[int] = Field(example=0)
    is_hidden: Optional[bool] = False
    component: str = Field(example="/system/user")
    keepalive: Optional[bool] = False
    redirect: Optional[str] = ""
