# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_schema.py
@DateTime: 2025/4/28
"""
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

from backend.applications.base.services.scaffold import UpperStr
from backend.enums.autotest_enum import AutoTestCaseType, AutoTestCaseAttr


class AutoTestApiCaseCreate(BaseModel):
    case_name: str = Field(..., max_length=255, description="用例名称")
    case_desc: Optional[str] = Field(None, max_length=2048, description="用例描述")
    case_tags: List[int] = Field(..., max_length=255, description="用例标签")
    case_type: Optional[AutoTestCaseType] = Field(default=AutoTestCaseType.PRIVATE_SCRIPT, description="用例所属类型")
    case_attr: Optional[AutoTestCaseAttr] = Field(default=None, description="用例所属属性")
    case_project: int = Field(default=1, ge=1, description="用例所属应用项目")
    session_variables: Optional[Dict[str, Any]] = Field(None, description="会话变量(初始化变量池)")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class AutoTestApiCaseBase(BaseModel):
    case_id: Optional[int] = Field(None, description="用例ID")
    case_code: Optional[str] = Field(None, max_length=64, description="用例标识代码")
    case_name: Optional[str] = Field(None, max_length=255, description="用例名称")
    case_tags: Optional[List[int]] = Field(None, description="用例标签")
    case_type: Optional[AutoTestCaseType] = Field(None, description="用例所属类型")
    case_attr: Optional[AutoTestCaseAttr] = Field(None, description="用例所属属性")
    case_steps: Optional[int] = Field(None, ge=0, description="用例步骤数量(含所有子级步骤)")
    case_project: Optional[int] = Field(None, ge=1, description="用例所属应用项目")
    session_variables: Optional[Dict[str, Any]] = Field(None, description="会话变量(初始化变量池)")
    case_version: Optional[int] = Field(None, ge=1, description="用例更新版本(修改次数)")


class AutoTestApiCaseUpdate(AutoTestApiCaseBase):
    case_desc: Optional[str] = Field(None, max_length=2048, description="用例描述")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestApiCaseSelect(AutoTestApiCaseBase):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["-updated_time"], description="排序字段")

    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    state: Optional[int] = Field(0, description="状态(0:启用, 1:禁用)")
