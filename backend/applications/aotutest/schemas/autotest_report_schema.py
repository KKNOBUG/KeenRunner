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


class AutoTestApiReportCreate(BaseModel):
    case_id: int = Field(..., description="用例ID")
    case_name: str = Field(..., max_length=255, description="用例名称")
    case_code: str = Field(..., max_length=64, description="用例代码")
    case_st_time: Optional[str] = Field(None, max_length=32, description="用例执行开始时间")
    case_ed_time: Optional[str] = Field(None, max_length=32, description="用例执行结束时间")
    case_elapsed: Optional[str] = Field(None, max_length=16, description="用例执行消耗时间")
    case_state: bool = Field(..., description="用例执行状态(True: Success, False: Failed)")
    step_total: int = Field(1, description="用例步骤数量(含子级步骤)")
    step_fill_count: int = Field(0, description="用例步骤失败数量")
    step_pass_count: int = Field(0, description="用例步骤成功数量")
    step_pass_ratio: float = Field(0.0, description="用例步骤成功率")
    created_user: Optional[str] = Field(None, max_length=16, description="创建人")


class AutoTestApiReportUpdate(BaseModel):
    id: int = Field(None, description="报告ID")
    report_code: str = Field(None, max_length=64, description="报告标识")
    case_st_time: Optional[str] = Field(None, max_length=32, description="用例执行开始时间")
    case_ed_time: Optional[str] = Field(None, max_length=32, description="用例执行结束时间")
    case_elapsed: Optional[str] = Field(None, max_length=16, description="用例执行消耗时间")
    case_state: bool = Field(..., description="用例执行状态(True: Success, False: Failed)")
    step_total: int = Field(0, description="用例步骤数量(含子级步骤)")
    step_fill_count: int = Field(0, description="用例步骤失败数量")
    step_pass_count: int = Field(0, description="用例步骤成功数量")
    step_pass_ratio: float = Field(0.0, description="用例步骤成功率")
    updated_user: Optional[str] = Field(None, max_length=16, description="更新人")


class AutoTestApiReportSelect(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["case_id", "-updated_time"], description="排序字段")
    id: Optional[int] = Field(None, description="报告ID")
    case_id: Optional[int] = Field(None, description="用例ID")
    case_name: Optional[str] = Field(None, description="用例名称")
    case_state: Optional[bool] = Field(None, description="用例执行状态(True: Success, False: Failed)")
    created_user: Optional[str] = Field(None, max_length=16, description="创建人")
    updated_user: Optional[str] = Field(None, max_length=16, description="更新人")
    state: Optional[int] = Field(-1, description="用例状态，正常：-1，删除：1")
