# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : api_schema.py
@DateTime: 2025/1/31 17:36
"""
from typing import Optional

from pydantic import BaseModel, Field


class ApiCreate(BaseModel):
    path: str = Field(example="/getAccessToken")
    method: str = Field(example="POST")
    summary: str = Field(example="Base-用户鉴权")
    description: str = Field(default=None, example="根据用户账号和密码生成token用于身份鉴权")
    tags: str = Field(example="基础服务")
    is_deleted: Optional[bool] = False

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class ApiUpdate(BaseModel):
    id: int
    path: Optional[str] = None
    method: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    is_deleted: Optional[bool] = False


class ApiSelect(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页展示数量")
    page_order: Optional[list] = Field(default=[], examples=["id"])
    path: Optional[str] = None
    method: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[str] = None
    is_deleted: Optional[bool] = None
