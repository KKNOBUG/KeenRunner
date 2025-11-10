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


class BaseAutoTestCase(BaseModel):
    """用例信息基础模型"""
    id: int
    case_name: str
    case_desc: Optional[str] = None
    case_flag: Optional[str] = None
    case_version: Optional[int] = None
    project_id: str


class AutoTestCaseCreate(BaseModel):
    """创建用例信息"""
    case_name: str = Field(..., max_length=255, description="用例名称")
    case_desc: Optional[str] = Field(None, max_length=2048, description="用例描述")
    case_flag: Optional[str] = Field(None, max_length=255, description="用例标签")
    project_id: str = Field(..., max_length=255, description="项目编号")


class AutoTestCaseUpdate(BaseModel):
    """更新用例信息"""
    id: int = Field(..., description="用例ID")
    case_name: Optional[str] = Field(None, max_length=255, description="用例名称")
    case_desc: Optional[str] = Field(None, max_length=2048, description="用例描述")
    case_flag: Optional[str] = Field(None, max_length=255, description="用例标签")
    project_id: Optional[str] = Field(None, max_length=255, description="项目编号")


class AutoTestCaseSelect(BaseModel):
    """查询用例信息条件"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["-updated_time"], description="排序字段")
    id: Optional[int] = Field(None, description="用例ID")
    case_name: Optional[str] = Field(None, description="用例名称")
    case_flag: Optional[str] = Field(None, description="用例标签")
    project_id: Optional[str] = Field(None, description="项目编号")
    case_version: Optional[int] = Field(None, ge=1, description="用例版本，正整数，最小值1")
    state: Optional[int] = Field(-1, description="用例状态，正常：-1，删除：1")
