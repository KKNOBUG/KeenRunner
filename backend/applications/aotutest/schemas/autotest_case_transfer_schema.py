# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_transfer_schema.py
@DateTime: 2026/8/17
"""
from typing import Optional, List

from pydantic import BaseModel, Field

from backend.applications.base.services.scaffold import UpperStr


class AutoTestApiCaseTransferCreate(BaseModel):
    """转让用例入参。"""

    case_id: int = Field(..., ge=1, description="用例ID")
    next_owner_user: UpperStr = Field(..., max_length=16, description="转入后所属人员")
    transfer_desc: Optional[str] = Field(None, max_length=2048, description="操作描述")


class AutoTestApiCaseTransferSelect(BaseModel):
    """分页查询转让记录入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["-created_time"], description="排序字段")

    transfer_id: Optional[int] = Field(None, ge=1, description="转让记录ID")
    case_id: Optional[int] = Field(None, ge=1, description="用例ID")
    prev_owner_user: Optional[UpperStr] = Field(None, max_length=16, description="转出前所属人员")
    next_owner_user: Optional[UpperStr] = Field(None, max_length=16, description="转入后所属人员")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="操作人")
    involve_user: Optional[UpperStr] = Field(None, max_length=16, description="转让链相关人员, 匹配转出人或转入人")
    created_time_begin: Optional[str] = Field(None, max_length=32, description="操作时间起")
    created_time_end: Optional[str] = Field(None, max_length=32, description="操作时间止")
