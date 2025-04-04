# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : env_schema.py
@DateTime: 2025/4/2 19:41
"""
from typing import Optional

from pydantic import BaseModel, Field


class EnvCreate(BaseModel):
    name: str
    host: str
    port: int
    project_id: Optional[int] = None
    description: Optional[str] = None

    def create_dict(self, exclude_fields: Optional[list] = None):
        return self.model_dump(exclude_unset=True, exclude=exclude_fields)


class EnvUpdate(BaseModel):
    id: int
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    description: Optional[str] = None
    project_id: Optional[int] = None

    def update_dict(self):
        return self.model_dump(exclude_unset=True, exclude={"id"})


class EnvSelect(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="数据数量")
    order: Optional[list] = Field(default=["id"], description="排序字段")
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    project_id: Optional[int] = None
    created_user: Optional[str] = None
    updated_user: Optional[str] = None
