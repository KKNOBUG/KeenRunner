# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : router_schema.py
@DateTime: 2025/1/31 17:36
"""
from typing import Optional

from pydantic import BaseModel, Field

from backend.enums import HTTPMethod


class RouterBase(BaseModel):
    id: Optional[int] = Field(default=None, description="路由ID")
    path: Optional[str] = Field(default=None, max_length=255, description="路由请求路径")
    method: Optional[HTTPMethod] = Field(default=None, description="路由请求方式")
    summary: Optional[str] = Field(default=None, max_length=255, description="路由作用简介")
    description: Optional[str] = Field(default=None, description="路由功能描述")
    tags: Optional[str] = Field(default=None, max_length=255, description="路由所属标签")


class RouterCreate(RouterBase):
    path: str = Field(..., max_length=255, description="路由请求路径")
    method: HTTPMethod = Field(..., description="路由请求方式")
    summary: str = Field(..., max_length=255, description="路由作用简介")
    tags: str = Field(..., max_length=255, description="路由所属标签")
    description: Optional[str] = Field(default=None, description="路由功能描述")

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class RouterUpdate(RouterBase):
    id: int = Field(..., description="路由ID")

    def update_dict(self):
        return self.model_dump(exclude_unset=True, exclude={"id"})


class RouterSelect(RouterBase):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: Optional[list] = Field(default=[], examples=["id"], description="排序字段")
