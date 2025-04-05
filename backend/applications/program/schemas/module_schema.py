# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : module_schema.py
@DateTime: 2025/4/5 12:36
"""
from typing import Optional

from pydantic import BaseModel, Field


class ModuleCreate(BaseModel):
    code: str
    name: str
    dev_owner: int
    test_owner: int
    project: Optional[int] = None
    description: Optional[str] = None
    created_user: Optional[str] = None

    def create_dict(self, exclude_fields: Optional[list] = None):
        return self.model_dump(exclude_unset=True, exclude=exclude_fields)


class ModuleUpdate(BaseModel):
    id: int
    code: Optional[str] = None
    name: Optional[str] = None
    dev_owner: Optional[int] = None
    test_owner: Optional[int] = None
    project: Optional[int] = None
    description: Optional[str] = None
    updated_user: Optional[str] = None

    def update_dict(self):
        return self.model_dump(exclude_unset=True, exclude={"id"})


class ModuleSelect(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="数据数量")
    order: Optional[list] = Field(default=["id"], description="排序字段")
    code: Optional[str] = None
    name: Optional[str] = None
    dev_owner: Optional[int] = None
    test_owner: Optional[int] = None
    project: Optional[int] = None
    description: Optional[str] = None
    created_user: Optional[str] = None
    updated_user: Optional[str] = None
