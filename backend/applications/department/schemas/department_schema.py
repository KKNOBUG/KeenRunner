# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : department_schema.py
@DateTime: 2025/2/3 16:27
"""
from typing import Optional

from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    code: str = Field(example="CS001", description="部门代码")
    name: str = Field(example="测试一部", description="部门名称")
    leader_id: Optional[int] = Field(example=1, description="部门所属领导ID")
    description: Optional[str] = Field(example="测试部门，测试一部", description="部门描述")
    state: int = Field(example=0, description="部门状态(0:启用,1:解散,2:调整,3:冻结)")

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class DepartmentUpdate(BaseModel):
    id: int
    code: Optional[int] = None
    name: Optional[str] = None
    leader_id: Optional[int] = None
    description: Optional[str] = None
    state: Optional[int] = None
    updated_user: Optional[str] = None


class DepartmentSelect(BaseModel):
    page_num: int = Field(default=1, ge=1, description="数据页码")
    page_size: int = Field(default=10, ge=10, description="数据数量")
    page_order: Optional[list] = Field(examples=["id"], description="数部门序")
    created_user: Optional[str] = None
    updated_user: Optional[str] = None
    created_time: Optional[str] = None
    updated_time: Optional[str] = None
