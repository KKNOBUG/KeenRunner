# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : department_schema.py
@DateTime: 2025/2/3 16:27
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    code: str = Field(..., description="部门代码")
    name: str = Field(..., description="部门名称")
    description: Optional[str] = Field(default=None, description="部门描述")
    order: int = Field(default=0, description="排序")
    parent_id: int = Field(default=0, description="父部门ID")

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class DepartmentUpdate(BaseModel):
    id: int = Field(..., description="部门ID")
    code: Optional[str] = Field(default=None, max_length=16, description="部门代码")
    name: Optional[str] = Field(default=None, max_length=64, description="部门名称")
    description: Optional[str] = Field(default=None, max_length=255, description="部门描述")
    order: Optional[int] = Field(default=None, ge=0, description="排序")
    parent_id: Optional[int] = Field(default=None, ge=0, description="父部门ID")
    updated_user: Optional[str] = Field(default=None, max_length=16, description="更新人员")

    def update_dict(self):
        return self.model_dump(exclude_unset=True, exclude={"id"})


class DepartmentSelect(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="数据数量")
    order: Optional[list] = Field(default=["id"], description="排序字段")
    code: Optional[str] = Field(default=None, description="部门代码（模糊）")
    name: Optional[str] = Field(default=None, description="部门名称（模糊）")
    is_deleted: Optional[bool] = Field(default=None, description="是否已删除；不传则仅查未删除")
    created_user: Optional[str] = Field(default=None, max_length=16, description="创建人员")
    updated_user: Optional[str] = Field(default=None, max_length=16, description="更新人员")
    created_time: Optional[datetime] = Field(default=None, description="创建时间")
    updated_time: Optional[datetime] = Field(default=None, description="更新时间")


class DepartmentBatchDelete(BaseModel):
    department_ids: Optional[List[int]] = Field(None, description="部门ID列表")
