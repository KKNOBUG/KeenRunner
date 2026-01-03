# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_detail_schema
@DateTime: 2025/11/27 10:42
"""
from typing import Optional, List, Dict, Any, Type

from pydantic import BaseModel, Field

from backend.applications.base.services.scaffold import UpperStr
from backend.enums.autotest_enum import StepType

NON_DICT_TYPE: Type = Optional[Dict[str, Any]]
NON_LIST_DICT_TYPE: Type = Optional[List[Dict[str, Any]]]


class AutoTestApiDetailBase(BaseModel):
    step_st_time: Optional[str] = Field(None, max_length=255, description="步骤执行开始时间")
    step_ed_time: Optional[str] = Field(None, max_length=255, description="步骤执行结束时间")
    step_elapsed: Optional[str] = Field(None, max_length=16, description="步骤执行消耗时间")
    step_exec_logger: Optional[str] = Field(None, description="步骤执行日志")
    step_exec_except: Optional[str] = Field(None, description="步骤错误描述")
    num_cycles: Optional[int] = Field(None, le=100, description="循环执行次数(第几次)")

    response_cookie: Optional[str] = Field(None, description="响应信息(cookies)")
    response_header: NON_DICT_TYPE = Field(default={}, description="响应信息(headers)")
    response_body: NON_DICT_TYPE = Field(default={}, description="响应信息(body)")
    response_text: Optional[str] = Field(None, description="响应信息(text)")
    response_elapsed: Optional[str] = Field(None, max_length=16, description="响应信息(elapsed)")

    session_variables: NON_DICT_TYPE = Field(None, description="会话变量(包含提取变量，以及前后code设置的变量)")
    defined_variables: NON_DICT_TYPE = Field(None, description="定义变量(自定义变量，如编写指定值或引用随机函数)")
    extract_variables: NON_DICT_TYPE = Field(None, description="提取变量(从请求控制器、上下文中提取、执行代码结果)")
    assert_validators: NON_LIST_DICT_TYPE = Field(None, description="断言规则(支持对各类数据对象进行不同表达式的断言验证)")


class AutoTestApiDetailCreate(AutoTestApiDetailBase):
    case_id: int = Field(..., description="用例ID")
    case_code: str = Field(..., max_length=64, description="用例标识代码")
    report_code: str = Field(..., max_length=64, description="报告标识代码")
    step_id: int = Field(..., description="步骤ID")
    step_no: int = Field(..., description="步骤序号")
    step_name: str = Field(..., max_length=255, description="步骤名称")
    step_code: str = Field(..., max_length=64, description="步骤标识代码")
    step_type: StepType = Field(..., description="步骤类型")
    step_state: bool = Field(..., description="步骤执行状态")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class AutoTestApiDetailUpdate(AutoTestApiDetailBase):
    case_id: int = Field(..., description="用例ID")
    case_code: str = Field(..., max_length=64, description="用例标识代码")
    report_code: str = Field(..., max_length=64, description="报告标识代码")
    detail_id: Optional[int] = Field(None, description="明细ID")
    step_code: Optional[str] = Field(None, max_length=64, description="步骤标识代码")
    step_type: Optional[StepType] = Field(None, description="步骤类型")
    step_state: Optional[bool] = Field(None, description="步骤执行状态")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestApiDetailSelect(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["-updated_time"], description="排序字段")

    case_id: Optional[int] = Field(None, description="用例ID")
    case_code: Optional[str] = Field(None, description="用例标识代码")
    report_code: Optional[str] = Field(None, description="报告标识代码")

    step_id: Optional[int] = Field(None, description="步骤ID")
    step_no: Optional[int] = Field(None, description="步骤序号")
    step_code: Optional[str] = Field(None, max_length=64, description="步骤标识代码")
    step_type: Optional[StepType] = Field(None, description="步骤类型")
    step_state: Optional[bool] = Field(None, description="步骤执行状态(True:成功, False:失败)")

    detail_id: Optional[int] = Field(None, description="明细ID")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人")
    state: Optional[int] = Field(default=-1, description="状态(-1:未删除, 1:删除)")
