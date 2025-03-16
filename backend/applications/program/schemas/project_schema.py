# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : project_schema.py
@DateTime: 2025/3/15 15:08
"""
from typing import Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    code: str = Field(example="XM-1001", description="项目代码")
    name: str = Field(example="无尽寒冬", description="项目名称")
    description: Optional[str] = Field(default=None, example="无尽寒冬", description="项目描述")
    dev_owner: int = Field(example=1, description="开发负责人ID")
    test_owner: int = Field(example=1, description="测试负责人ID")
    state: int = Field(example=1, default=1, description="项目状态")

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class ProjectUpdate(BaseModel):
    id: int
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    dev_owner: Optional[int] = None
    test_owner: Optional[int] = None
    state: Optional[int] = None

    def update_dict(self):
        return self.model_dump(exclude_unset=True, exclude={"id"})


class ProjectSelect(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="数据数量")
    order: Optional[list] = Field(default=["id"], description="排序字段")
    code: Optional[str] = None
    name: Optional[str] = None
    dev_owner: Optional[int] = None
    test_owner: Optional[int] = None
    state: Optional[int] = None
    created_user: Optional[str] = None
    updated_user: Optional[str] = None
