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

from backend.enums.http_enum import HTTPMethod


class RouterCreate(BaseModel):
    path: str = Field(example="/base/access_token", description="路由请求路径")
    method: HTTPMethod = Field(example="POST", description="路由请求方式")
    summary: str = Field(example="根据用户账号和密码生成token用于身份鉴权", description="路由作用简介")
    description: str = Field(default=None, example="根据用户账号和密码生成token用于身份鉴权", description="路由功能描述")
    tags: str = Field(example="用户鉴权", description="路由所属标签")

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class RouterUpdate(BaseModel):
    id: int
    path: Optional[str] = None
    method: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None


class RouterSelect(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="数据数量")
    order: Optional[list] = Field(default=["id"], description="排序字段")
    id: Optional[int] = None
    path: Optional[str] = None
    method: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[str] = None
