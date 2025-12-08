# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_detail_schema
@DateTime: 2025/11/27 10:42
"""
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

from backend.applications.aotutest.models.autotest_model import StepType


class AutoTestApiDetailCreate(BaseModel):
    case_id: int = Field(..., description="用例ID")
    case_code: str = Field(..., max_length=64, description="用例标识")
    report_code: str = Field(..., max_length=64, description="报告标识")

    step_id: int = Field(..., description="步骤ID")
    step_no: int = Field(..., description="步骤序号")
    step_code: str = Field(..., max_length=64, description="步骤标识")
    step_type: StepType = Field(StepType, description="步骤明细类型")

    step_state: bool = Field(..., description="步骤执行状态")
    step_st_time: Optional[str] = Field(None, max_length=255, description="步骤执行开始时间")
    step_ed_time: Optional[str] = Field(None, max_length=255, description="步骤执行结束时间")
    step_elapsed: Optional[str] = Field(None, max_length=16, description="步骤执行消耗时间")
    step_exec_logger: Optional[str] = Field(None, description="步骤执行日志")
    step_exec_except: Optional[str] = Field(None, description="步骤错误描述")

    response_cookie: Optional[str] = Field(None, description="响应cookies信息")
    response_header: Optional[Dict[str, Any]] = Field({}, description="响应头信息")
    response_body: Optional[Dict[str, Any]] = Field({}, description="响应体信息")
    response_text: Optional[str] = Field(None, description="响应体信息")
    response_elapsed: Optional[str] = Field(None, max_length=16, description="响应时间")

    session_variables: Optional[Dict[str, Any]] = Field({}, description="会话变量(包含提取变量，以及前后code设置的变量)")
    defined_variables: Optional[Dict[str, Any]] = Field({}, escription="定义变量(自定义变量，如编写指定值或引用随机函数)")
    extract_variables: Optional[Dict[str, Any]] = Field({}, description="提取变量(从上下午中提取参数)")

    validators: Optional[Dict[str, Any]] = Field({}, description="断言规则")


class AutoTestApiDetailUpdate(BaseModel):
    id: Optional[int] = Field(None, description="报告ID")
    report_code: str = Field(..., description="报告标识")
    step_code: Optional[str] = Field(None, max_length=64, description="步骤标识")

    case_id: int = Field(..., description="用例ID")
    case_code: str = Field(..., max_length=64, description="用例标识")

    step_type: Optional[StepType] = Field(None, description="步骤明细类型")
    step_state: Optional[bool] = Field(None, description="步骤执行状态")
    step_st_time: Optional[str] = Field(None, max_length=255, description="步骤执行开始时间")
    step_ed_time: Optional[str] = Field(None, max_length=255, description="步骤执行结束时间")
    step_elapsed: Optional[str] = Field(None, max_length=16, description="步骤执行消耗时间")
    step_exec_logger: Optional[str] = Field(None, description="步骤执行日志")
    step_exec_except: Optional[str] = Field(None, description="步骤错误描述")

    response_cookie: Optional[str] = Field(None, description="响应cookies信息")
    response_header: Optional[Dict[str, Any]] = Field({}, description="响应头信息")
    response_body: Optional[Dict[str, Any]] = Field({}, description="响应体信息")
    response_text: Optional[str] = Field(None, description="响应体信息")
    response_elapsed: Optional[str] = Field(None, max_length=16, description="响应时间")

    session_variables: Optional[Dict[str, Any]] = Field({}, description="会话变量(包含提取变量，以及前后code设置的变量)")
    defined_variables: Optional[Dict[str, Any]] = Field({}, description="定义变量(自定义变量，如编写指定值或引用随机函数)")
    extract_variables: Optional[Dict[str, Any]] = Field({}, description="提取变量(从上下午中提取参数)")

    validators: Optional[Dict[str, Any]] = Field({}, description="断言规则")


class AutoTestApiDetailSelect(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["-updated_time"], description="排序字段")

    id: Optional[int] = Field(None, description="明细ID")
    case_id: Optional[int] = Field(None, description="用例ID")
    step_state: Optional[bool] = Field(None, description="步骤执行状态(True: Success, False: Failed)")
    created_user: Optional[str] = Field(None, max_length=16, description="创建人")
    updated_user: Optional[str] = Field(None, max_length=16, description="更新人")
    state: Optional[int] = Field(-1, description="用例状态，正常：-1，删除：1")
    step_type: Optional[StepType] = Field(None, description="步骤明细类型")
