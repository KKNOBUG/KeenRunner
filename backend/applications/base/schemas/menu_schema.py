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

from backend.enums import MenuType


#
# class MenuBase(BaseModel):
#     id: Optional[int] = Field(default=None, description="菜单ID")
#     name: Optional[str] = Field(default=None, max_length=32, description="菜单名称")
#     path: Optional[str] = Field(default=None, max_length=128, description="菜单路径")
#     remark: Optional[dict] = Field(default=None, description="保留字段")
#     menu_type: Optional[MenuType] = Field(default=None, description="菜单类型")
#     icon: Optional[str] = Field(default=None, max_length=128, description="菜单图标")
#     order: Optional[int] = Field(default=None, description="排序")
#     parent_id: Optional[int] = Field(default=None, description="父菜单ID")
#     is_hidden: Optional[bool] = Field(default=None, description="是否隐藏")
#     component: Optional[str] = Field(default=None, max_length=128, description="组件")
#     keepalive: Optional[bool] = Field(default=None, description="存活")
#     redirect: Optional[str] = Field(default=None, max_length=128, description="重定向")
#     children: Optional[List["MenuBase"]] = Field(default=None, description="子菜单")
#
#
# class MenuCreate(MenuBase):
#     menu_type: MenuType = Field(default=MenuType.CATALOG, description="菜单类型")
#     name: str = Field(..., max_length=32, description="菜单名称")
#     path: str = Field(..., max_length=128, description="菜单路径")
#     component: str = Field(default="Layout", max_length=128, description="组件")
#     order: Optional[int] = Field(default=0, description="排序")
#     parent_id: Optional[int] = Field(default=0, description="父菜单ID")
#     is_hidden: Optional[bool] = Field(default=False, description="是否隐藏")
#     keepalive: Optional[bool] = Field(default=True, description="存活")
#     icon: Optional[str] = Field(default="ph:user-list-bold", max_length=128, description="菜单图标")
#     redirect: Optional[str] = Field(default="", max_length=128, description="重定向")
#
#     def create_dict(self):
#         return self.model_dump(exclude_unset=True)
#
#
# class MenuUpdate(MenuBase):
#     id: int = Field(..., description="菜单ID")
#
#     def update_dict(self):
#         return self.model_dump(exclude_unset=True, exclude={"id"})
#


class BaseMenu(BaseModel):
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


class MenuUpdate(BaseModel):
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
