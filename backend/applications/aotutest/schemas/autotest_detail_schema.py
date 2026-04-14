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
from backend.enums import AutoTestStepType

NON_DICT_TYPE: Type = Optional[Dict[str, Any]]
NON_LIST_DICT_TYPE: Type = Optional[List[Dict[str, Any]]]


class AutoTestApiDetailBase(BaseModel):
    quote_case_id: Optional[int] = Field(default=None, ge=1, description="引用公共脚本ID")

    step_st_time: Optional[str] = Field(default=None, max_length=255, description="步骤执行开始时间")
    step_ed_time: Optional[str] = Field(default=None, max_length=255, description="步骤执行结束时间")
    step_elapsed: Optional[str] = Field(default=None, max_length=16, description="步骤执行消耗时间")
    step_exec_logger: Optional[str] = Field(default=None, description="步骤执行日志")
    step_exec_except: Optional[str] = Field(default=None, description="步骤错误描述")
    num_cycles: Optional[int] = Field(default=None, le=100, description="循环执行次数(第几次)")

    request_url: Optional[str] = Field(default=None, max_length=2048, description="本次执行使用的请求地址(快照)")
    request_port: Optional[str] = Field(default=None, max_length=16, description="本次执行使用的请求端口(快照)")
    request_method: Optional[str] = Field(default=None, max_length=16, description="本次执行使用的请求方法(快照)")
    request_args_type: Optional[Any] = Field(default=None, description="本次执行使用的请求参数类型(快照)")
    request_project_id: Optional[int] = Field(default=None, ge=1, description="本次执行使用的请求应用ID(快照)")
    request_header: NON_DICT_TYPE = Field(default=None, description="实际发出的请求头")
    request_params: NON_DICT_TYPE = Field(default=None, description="实际发出的请求参数")
    request_form_data: NON_DICT_TYPE = Field(default=None, description="实际发出的表单数据")
    request_form_urlencoded: NON_DICT_TYPE = Field(default=None, description="实际发出的 urlencoded 键值对")
    request_form_file: NON_DICT_TYPE = Field(default=None, description="实际发出的表单文件项")
    request_body: NON_DICT_TYPE = Field(default=None, description="实际发出的请求体(JSON)")
    request_text: Optional[str] = Field(default=None, description="实际发出的请求体(Raw)")

    code: Optional[str] = Field(default=None, description="本次执行使用的代码(Python)(快照)")
    wait: Optional[float] = Field(default=None, ge=0, description="本次执行等待时间(快照)")
    loop_mode: Optional[Any] = Field(default=None, description="本次执行循环模式(快照)")
    loop_maximums: Optional[int] = Field(default=None, ge=1, description="本次执行最大循环次数(快照)")
    loop_interval: Optional[float] = Field(default=None, ge=0, description="本次执行循环间隔(快照)")
    loop_iterable: Optional[str] = Field(default=None, max_length=512, description="本次执行循环对象来源(快照)")
    loop_iter_idx: Optional[str] = Field(default=None, max_length=64, description="本次执行循环索引变量名(快照)")
    loop_iter_key: Optional[str] = Field(default=None, max_length=64, description="本次执行循环字典键变量名(快照)")
    loop_iter_val: Optional[str] = Field(default=None, max_length=64, description="本次执行循环值变量名(快照)")
    loop_on_error: Optional[Any] = Field(default=None, description="本次执行循环错误策略(快照)")
    loop_timeout: Optional[float] = Field(default=None, ge=0, description="本次执行条件循环超时(快照)")
    conditions: NON_DICT_TYPE = Field(default=None, description="本次执行条件/循环判断条件(快照)")

    # 参数化驱动：本步骤执行使用的数据集名称和该步骤的数据快照，记录在明细中
    dataset_name: Optional[str] = Field(default=None, max_length=255, description="本步骤执行对应的数据集名称(参数化)")
    dataset_snapshot: Optional[Dict[str, Any]] = Field(default=None, description="本步骤执行使用的数据快照(该步骤的 head/body/assert)")

    response_cookie: Optional[str] = Field(default=None, description="响应信息(cookies)")
    response_header: NON_DICT_TYPE = Field(default=None, description="响应信息(headers)")
    response_body: NON_DICT_TYPE = Field(default=None, description="响应信息(body)")
    response_text: Optional[str] = Field(default=None, description="响应信息(text)")
    response_elapsed: Optional[str] = Field(default=None, max_length=16, description="响应信息(elapsed)")

    session_variables: NON_LIST_DICT_TYPE = Field(default=None, description="会话变量(包含提取变量，以及前后code设置的变量)")
    defined_variables: NON_LIST_DICT_TYPE = Field(default=None, description="定义变量(自定义变量，如编写指定值或引用随机函数)")
    extract_variables: NON_LIST_DICT_TYPE = Field(default=None, description="提取变量(从请求控制器、上下文中提取、执行代码结果)")
    assert_validators: NON_LIST_DICT_TYPE = Field(default=None, description="断言规则(支持对各类数据对象进行不同表达式的断言验证)")


class AutoTestApiDetailCreate(AutoTestApiDetailBase):
    case_id: int = Field(..., ge=1, description="用例ID")
    case_code: str = Field(..., max_length=64, description="用例标识代码")
    report_code: str = Field(..., max_length=64, description="报告标识代码")
    step_id: int = Field(..., ge=1, description="步骤ID")
    step_no: int = Field(..., ge=1, description="步骤序号")
    step_name: str = Field(..., max_length=255, description="步骤名称")
    step_code: str = Field(..., max_length=64, description="步骤标识代码")
    step_type: AutoTestStepType = Field(..., description="步骤类型")
    step_state: bool = Field(..., description="步骤执行状态")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class AutoTestApiDetailUpdate(AutoTestApiDetailBase):
    case_id: int = Field(..., ge=1, description="用例ID")
    case_code: str = Field(..., max_length=64, description="用例标识代码")
    report_code: str = Field(..., max_length=64, description="报告标识代码")
    detail_id: Optional[int] = Field(None, description="明细ID")
    step_code: Optional[str] = Field(None, max_length=64, description="步骤标识代码")
    step_type: Optional[AutoTestStepType] = Field(None, description="步骤类型")
    step_state: Optional[bool] = Field(None, description="步骤执行状态")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestApiDetailSelect(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["step_st_time"], description="排序字段")

    case_id: Optional[int] = Field(None, description="用例ID")
    case_code: Optional[str] = Field(None, max_length=64, description="用例标识代码")
    quote_case_id: Optional[int] = Field(None, description="引用公共脚本ID")
    report_code: Optional[str] = Field(None, description="报告标识代码")

    step_id: Optional[int] = Field(None, description="步骤ID")
    step_no: Optional[int] = Field(None, description="步骤序号")
    step_code: Optional[str] = Field(None, max_length=64, description="步骤标识代码")
    step_type: Optional[AutoTestStepType] = Field(None, description="步骤类型")
    step_state: Optional[bool] = Field(None, description="步骤执行状态(True:成功, False:失败)")

    detail_id: Optional[int] = Field(None, description="明细ID")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")
