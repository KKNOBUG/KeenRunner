# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : group_schema.py
@DateTime: 2025/2/5 13:36
"""
from typing import Optional

from pydantic import BaseModel, Field


class GroupCreate(BaseModel):
    code: str = Field(example="GP001", description="小组代码")
    name: str = Field(example="自动化测试一组", description="小组名称")
    leader_id: Optional[int] = Field(example=1, description="小组所属组长ID")
    department_id: int = Field(example=1, description="所属部门ID")
    description: Optional[str] = Field(example=None, default=None, description="小队描述")
    state: int = Field(example=2, description="小组状态(0:空闲,1:忙碌,2:调整,3:培训)")

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class GroupUpdate(BaseModel):
    id: int
    name: Optional[str] = None
    leader_id: Optional[int] = None
    department_id: Optional[int] = None
    description: Optional[str] = None
    state: Optional[int] = None
    updated_user: Optional[str] = None


class GroupSelect(BaseModel):
    page_num: int = Field(default=1, ge=1, description="数据页码")
    page_size: int = Field(default=10, ge=10, description="数据数量")
    page_order: Optional[list] = Field(default=[], examples=["id"], description="数据排序")
    code: Optional[int] = None
    name: Optional[str] = None
    leader_id: Optional[int] = None
    department_id: Optional[int] = None
    state: Optional[int] = None
    created_user: Optional[str] = None
    updated_user: Optional[str] = None
    created_time: Optional[str] = None
    updated_time: Optional[str] = None
