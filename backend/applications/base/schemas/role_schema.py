# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : role_schema.py
@DateTime: 2025/2/19 23:05
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class RoleBase(BaseModel):
    code: Optional[str] = Field(default=None, max_length=16, description="角色代码")
    name: Optional[str] = Field(default=None, max_length=64, description="角色名称")
    description: Optional[str] = Field(default=None, description="角色描述")


class RoleCreate(RoleBase):
    code: str = Field(..., max_length=16, description="角色代码")
    name: str = Field(..., max_length=64, description="角色名称")
    description: Optional[str] = Field(default="", description="角色描述")

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class RoleUpdate(RoleBase):
    id: int = Field(..., description="角色ID")

    def update_dict(self):
        return self.model_dump(exclude_unset=True, exclude={"id"})


class RoleSelect(RoleBase):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: Optional[list] = Field(default=[], examples=["id"], description="排序字段")


class RoleUpdateMenusRouters(BaseModel):
    id: int = Field(..., description="角色ID")
    menu_ids: List[int] = Field(default_factory=list, description="菜单ID列表")
    router_infos: List[dict] = Field(default_factory=list, description="路由信息列表")


class RoleBatchDelete(BaseModel):
    role_ids: Optional[List[int]] = Field(default=None, description="角色ID列表")
    role_codes: Optional[List[str]] = Field(default=None, description="角色代码列表")
