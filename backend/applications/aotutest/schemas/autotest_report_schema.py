# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autest_report_schema
@DateTime: 2025/11/26 16:43
"""
from typing import Optional, List

from pydantic import BaseModel, Field

from backend.applications.base.services.scaffold import UpperStr
from backend.enums.autotest_enum import AutoTestReportType


class AutoTestApiReportBase(BaseModel):
    case_st_time: Optional[str] = Field(None, max_length=32, description="用例执行开始时间")
    case_ed_time: Optional[str] = Field(None, max_length=32, description="用例执行结束时间")
    case_elapsed: Optional[str] = Field(None, max_length=16, description="用例执行消耗时间")
    case_state: Optional[bool] = Field(None, description="用例执行状态(True:成功, False:失败)")

    step_total: Optional[int] = Field(None, ge=0, description="用例步骤数量(含所有子级步骤)")
    step_fail_count: Optional[int] = Field(None, ge=0, description="用例步骤失败数量(含所有子级步骤)")
    step_pass_count: Optional[int] = Field(None, ge=0, description="用例步骤成功数量(含所有子级步骤)")
    step_pass_ratio: Optional[float] = Field(None, ge=0, description="用例步骤成功率(含所有子级步骤)")

    task_code: Optional[str] = Field(None, max_length=64, description="任务标识代码")


class AutoTestApiReportCreate(AutoTestApiReportBase):
    case_id: int = Field(..., description="用例ID")
    case_code: str = Field(..., max_length=64, description="用例标识代码")
    case_state: bool = Field(default=False, description="用例执行状态(True:成功, False:失败)")

    step_total: int = Field(default=0, ge=0, description="用例步骤数量(含所有子级步骤)")
    step_fail_count: int = Field(default=0, ge=0, description="用例步骤失败数量(含所有子级步骤)")
    step_pass_count: int = Field(default=0, ge=0, description="用例步骤成功数量(含所有子级步骤)")
    step_pass_ratio: float = Field(default=0.0, ge=0, description="用例步骤成功率(含所有子级步骤)")

    report_type: AutoTestReportType = Field(..., description="报告类型")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class AutoTestApiReportUpdate(AutoTestApiReportBase):
    report_id: Optional[int] = Field(None, description="报告ID")
    report_code: Optional[str] = Field(None, max_length=64, description="报告标识代码")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestApiReportSelect(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["case_id", "-updated_time"], description="排序字段")

    case_id: Optional[int] = Field(None, description="用例ID")
    case_code: Optional[str] = Field(None, description="用例标识代码")
    report_id: Optional[int] = Field(None, description="报告ID")
    report_code: Optional[str] = Field(None, description="报告标识代码")
    report_type: Optional[AutoTestReportType] = Field(None, description="报告类型")
    task_code: Optional[str] = Field(None, description="任务标识代码")

    case_state: Optional[bool] = Field(None, description="用例执行状态(True:成功, False:失败)")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    step_pass_ratio: Optional[float] = Field(None, ge=0, description="用例步骤成功率(含所有子级步骤)")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")
