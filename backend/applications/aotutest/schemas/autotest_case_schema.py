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

from backend.enums.autotest_enum import CaseType


class AutoTestApiCaseCreate(BaseModel):
    case_name: str = Field(..., max_length=255, description="用例名称")
    case_desc: Optional[str] = Field(None, max_length=2048, description="用例描述")
    case_tags: Optional[str] = Field(None, max_length=255, description="用例标签")
    case_type: Optional[CaseType] = Field(default=CaseType.PRIVATE_SCRIPT, max_length=255, description="用例所属类型")
    case_project: int = Field(default=1, ge=1, description="用例所属应用项目")


class AutoTestApiCaseBase(BaseModel):
    case_id: Optional[int] = Field(None, description="用例ID")
    case_code: Optional[str] = Field(None, max_length=64, description="用例标识代码")
    case_name: Optional[str] = Field(None, max_length=255, description="用例名称")
    case_tags: Optional[str] = Field(None, max_length=255, description="用例标签")
    case_type: Optional[CaseType] = Field(None, description="用例所属类型")
    case_steps: Optional[int] = Field(None, ge=0, description="用例步骤数量(含所有子级步骤)")
    case_project: Optional[int] = Field(None, ge=1, description="用例所属应用项目")
    case_version: Optional[int] = Field(None, ge=1, description="用例更新版本(修改次数)")


class AutoTestApiCaseUpdate(AutoTestApiCaseBase):
    case_desc: Optional[str] = Field(None, max_length=2048, description="用例描述")


class AutoTestApiCaseSelect(AutoTestApiCaseBase):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["-updated_time"], description="排序字段")

    created_user: Optional[str] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[str] = Field(None, max_length=16, description="更新人员")
    state: Optional[int] = Field(-1, description="状态(-1:未删除, 1:删除, 2:执行成功, 3:执行失败)")
