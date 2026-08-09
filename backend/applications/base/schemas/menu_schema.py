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

from backend.applications.base.services.scaffold import UpperStr
from backend.enums import MenuType


class BaseMenu(BaseModel):
    """菜单树节点出参，含children。"""

    id: int = Field(..., description="菜单ID")
    name: str = Field(..., max_length=32, description="菜单名称")
    path: str = Field(..., max_length=128, description="菜单路径")
    remark: Optional[dict] = Field(default=None, description="保留字段")
    menu_type: Optional[MenuType] = Field(default=None, description="菜单类型")
    icon: Optional[str] = Field(default=None, max_length=128, description="菜单图标")
    order: int = Field(..., description="排序")
    parent_id: int = Field(..., description="父菜单ID")
    is_hidden: bool = Field(..., description="是否隐藏")
    component: str = Field(..., max_length=128, description="组件")
    keepalive: bool = Field(..., description="存活")
    redirect: Optional[str] = Field(default=None, max_length=128, description="重定向")
    children: Optional[List["BaseMenu"]] = Field(default=None, description="子菜单")


class MenuCreate(BaseModel):
    """新增菜单入参。"""

    menu_type: MenuType = Field(default=MenuType.CATALOG, description="菜单类型")
    name: str = Field(..., max_length=32, description="菜单名称")
    icon: Optional[str] = Field(default="ph:user-list-bold", max_length=128, description="菜单图标")
    path: str = Field(..., max_length=128, description="菜单路径")
    order: Optional[int] = Field(default=0, description="排序")
    parent_id: Optional[int] = Field(default=0, description="父菜单ID")
    is_hidden: Optional[bool] = Field(default=False, description="是否隐藏")
    component: str = Field(default="Layout", max_length=128, description="组件")
    keepalive: Optional[bool] = Field(default=True, description="存活")
    redirect: Optional[str] = Field(default=None, max_length=128, description="重定向")
    created_user: Optional[UpperStr] = Field(default=None, max_length=16, description="创建人员")


class MenuUpdate(BaseModel):
    """更新菜单入参。"""

    id: int = Field(..., description="菜单ID")
    menu_type: Optional[MenuType] = Field(default=None, description="菜单类型")
    name: Optional[str] = Field(default=None, max_length=32, description="菜单名称")
    path: Optional[str] = Field(default=None, max_length=128, description="菜单路径")
    icon: Optional[str] = Field(default=None, max_length=128, description="菜单图标")
    order: Optional[int] = Field(default=None, description="排序")
    parent_id: Optional[int] = Field(default=None, description="父菜单ID")
    is_hidden: Optional[bool] = Field(default=None, description="是否隐藏")
    component: Optional[str] = Field(default=None, max_length=128, description="组件")
    keepalive: Optional[bool] = Field(default=None, description="存活")
    redirect: Optional[str] = Field(default=None, max_length=128, description="重定向")
    updated_user: Optional[UpperStr] = Field(default=None, max_length=16, description="更新人员")
