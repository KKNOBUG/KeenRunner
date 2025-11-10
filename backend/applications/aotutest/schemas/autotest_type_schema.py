# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_schema.py
@DateTime: 2025/4/28
"""
from typing import Optional, List

from pydantic import BaseModel, Field


class BaseAutoTestType(BaseModel):
    """用例信息基础模型"""
    id: int
    type_name: str
    type_desc: Optional[str] = None


class AutoTestTypeCreate(BaseModel):
    """创建用例信息"""
    type_name: str = Field(..., max_length=255, description="步骤枚举名称")
    type_desc: Optional[str] = Field(None, max_length=2048, description="步骤枚举描述")


class AutoTestTypeUpdate(BaseModel):
    """更新用例信息"""
    id: int = Field(..., description="用例ID")
    type_name: Optional[str] = Field(None, max_length=255, description="步骤枚举名称")
    type_desc: Optional[str] = Field(None, max_length=2048, description="步骤枚举描述")
    state: Optional[int] = Field(-1, description="步骤枚举状态，正常：-1，删除：1")


class AutoTestTypeSelect(BaseModel):
    """查询用例信息条件"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["-updated_time"], description="排序字段")
    id: Optional[int] = Field(None, description="用例ID")
    type_name: Optional[str] = Field(None, description="步骤枚举名称")
    type_desc: Optional[str] = Field(None, description="步骤枚举描述")
    state: Optional[int] = Field(-1, description="步骤枚举状态，正常：-1，删除：1")
