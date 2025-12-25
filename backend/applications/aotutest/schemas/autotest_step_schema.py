# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_schema.py
@DateTime: 2025/4/28
"""
from typing import Optional, List, Dict, Any, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.applications.aotutest.models.autotest_model import StepType, CaseType
from backend.enums.http_enum import HTTPMethod


class AutoTestApiStepBase(BaseModel):
    """步骤明细基础模型"""
    step_no: Optional[int] = Field(None, description="步骤明细序号")
    step_name: Optional[str] = Field(None, description="步骤明细名称")
    step_desc: Optional[str] = Field(None, description="步骤明细描述")
    step_type: Optional[StepType] = Field(None, description="步骤明细类型")
    case_type: Optional[CaseType] = Field(None, description="用例所属类型")

    case_id: Optional[int] = Field(None, description="步骤明细所属用例")
    quote_case_id: Optional[int] = Field(None, description="引用公共用例ID")
    parent_step_id: Optional[int] = Field(None, description="父级步骤明细ID")

    request_url: Optional[str] = Field(None, description="请求地址")
    request_port: Optional[str] = Field(None, description="请求端口")
    request_method: Optional[HTTPMethod] = Field(None, description="请求方法(GET/POST/PUT/DELETE等)")
    request_header: Optional[Dict[str, Any]] = Field(None, description="请求头信息")
    request_text: Optional[str] = Field(None, description="请求体数据(Text格式)")
    request_body: Optional[Dict[str, Any]] = Field(None, description="请求体数据(Json格式)")
    request_params: Optional[str] = Field(None, description="请求路径参数(Text格式)")
    request_form_data: Optional[Dict[str, Any]] = Field(None, description="请求表单数据(Json格式)")
    request_form_file: Optional[Dict[str, Any]] = Field(None, description="请求文件路径(Json格式)")
    request_form_urlencoded: Optional[Dict[str, Any]] = Field(None, description="请求键值对数据(Json格式)")

    code: Optional[str] = Field(None, description="执行代码(Python)")
    wait: Optional[float] = Field(None, description="等待控制(正浮点数, 单位:秒)")
    max_cycles: Optional[int] = Field(None, description="最大循环次数(正整数)")
    max_interval: Optional[float] = Field(None, description="每次循环间隔时间(正浮点数)")
    conditions: Optional[List[Dict[str, Any]]] = Field(None, description="判断条件")

    session_variables: Optional[Dict[str, Any]] = Field(None, description="会话变量(所有步骤的执行结果持续累积)")
    defined_variables: Optional[Dict[str, Any]] = Field(None, description="定义变量(用户自定义、引用函数的结果)")
    extract_variables: Optional[List[Dict[str, Any]]] = Field(None,
                                                              description="提取变量(从请求控制器、上下文中提取、执行代码结果)")
    assert_validators: Optional[List[Dict[str, Any]]] = Field(None,
                                                              description="断言规则(支持对各类数据对象进行不同表达式的断言验证)")
    state: Optional[int] = Field(default=-1, description="步骤状态(-1:未删除, 1:删除, 2:执行成功, 3:执行失败)")


class AutoTestApiStepChildren(BaseModel):
    children: Optional[List["AutoTestApiStepBase"]] = Field(None, description="子步骤")
    quote_steps: Optional[List["AutoTestApiStepBase"]] = Field(None, description="引用步骤")


class AutoTestApiStepCreate(AutoTestApiStepBase):
    """创建步骤明细"""
    step_no: int = Field(..., description="步骤明细序号")
    step_type: StepType = Field(..., description="步骤明细类型")


class AutoTestApiStepUpdate(AutoTestApiStepBase):
    """更新步骤明细"""
    step_id: Optional[int] = Field(None, description="步骤明细ID")
    step_code: Optional[str] = Field(None, description="步骤明细标识代码")
    updated_user: Optional[str] = Field(None, description="更新人")


class AutoTestStepSelect(BaseModel):
    """查询步骤明细条件"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["case_id", "step_no"], description="排序字段")
    step_id: Optional[int] = Field(None, description="步骤ID")
    case_id: Optional[int] = Field(None, description="用例信息ID")
    step_type: Optional[StepType] = Field(None, description="步骤明细类型")
    case_type: Optional[CaseType] = Field(None, description="用例所属类型")
    parent_step_id: Optional[int] = Field(None, description="父级步骤ID")
    quote_case_id: Optional[int] = Field(None, description="引用用例信息ID")
    state: Optional[int] = Field(-1, description="步骤状态，正常：-1，删除：1")


class AutoTestStepTreeUpdateItem(BaseModel):
    """步骤树更新项（用于批量更新）"""
    step_id: Optional[int] = Field(None, description="步骤ID(更新必填，新增不填)")
    step_no: Optional[int] = Field(None, description="步骤明细序号")
    step_code: Optional[str] = Field(None, description="步骤明细标识代码")
    step_name: Optional[str] = Field(None, description="步骤明细名称")
    step_desc: Optional[str] = Field(None, description="步骤明细描述")
    step_type: Optional[StepType] = Field(None, description="步骤明细类型")

    case_id: Optional[int] = Field(None, description="步骤明细所属用例")
    quote_case_id: Optional[int] = Field(None, description="引用公共用例ID")
    parent_step_id: Optional[int] = Field(None, description="父级步骤明细ID")

    request_url: Optional[str] = Field(None, description="请求地址")
    request_port: Optional[str] = Field(None, description="请求端口")
    request_method: Optional[HTTPMethod] = Field(None, description="请求方法(GET/POST/PUT/DELETE等)")
    request_header: Optional[Dict[str, Any]] = Field(None, description="请求头信息")
    request_text: Optional[str] = Field(None, description="请求体数据(Text格式)")
    request_body: Optional[Dict[str, Any]] = Field(None, description="请求体数据(Json格式)")
    request_params: Optional[str] = Field(None, description="请求路径参数(Text格式)")
    request_form_data: Optional[Dict[str, Any]] = Field(None, description="请求表单数据(Json格式)")
    request_form_file: Optional[Dict[str, Any]] = Field(None, description="请求文件路径(Json格式)")
    request_form_urlencoded: Optional[Dict[str, Any]] = Field(None, description="请求键值对数据(Json格式)")

    code: Optional[str] = Field(None, description="执行代码(Python)")
    wait: Optional[float] = Field(None, description="等待控制(正浮点数, 单位:秒)")
    max_cycles: Optional[int] = Field(None, description="最大循环次数(正整数)")
    max_interval: Optional[float] = Field(None, description="每次循环间隔时间(正浮点数)")
    conditions: Optional[List[Dict[str, Any]]] = Field(None, description="判断条件")

    session_variables: Optional[Dict[str, Any]] = Field(None,
                                                        description="会话变量(包含提取变量，以及前后code设置的变量)")
    defined_variables: Optional[Dict[str, Any]] = Field(None,
                                                        description="定义变量(自定义变量，如编写指定值或引用随机函数)")
    extract_variables: Optional[List[Dict[str, Any]]] = Field(None,
                                                              description="提取变量(从请求控制器、上下文中提取、执行代码结果)")
    assert_validators: Optional[List[Dict[str, Any]]] = Field(None,
                                                              description="断言规则(支持对各类数据对象进行不同表达式的断言验证)")

    case: Optional[Dict[str, Any]] = Field(None, description="测试用例信息")
    children: Optional[List["AutoTestStepTreeUpdateItem"]] = Field(None, description="子步骤列表")
    quote_steps: Optional[List[Any]] = Field(None, description="引用步骤列表(更新时忽略)")
    quote_case: Optional[Any] = Field(None, description="引用用例信息(更新时忽略)")


class AutoTestStepTreeUpdateList(BaseModel):
    """批量更新步骤树"""
    steps: List[AutoTestStepTreeUpdateItem] = Field(..., description="步骤树数据")


class AutoTestHttpDebugRequest(BaseModel):
    """HTTP请求调试模型（不保存到数据库）"""
    step_name: str = Field(..., description="步骤名称")

    request_url: str = Field(..., description="请求地址")
    request_method: HTTPMethod = Field(..., description="请求方法")
    request_header: Optional[Dict[str, Any]] = Field(None, description="请求头信息")
    request_text: Optional[str] = Field(None, description="请求体数据(Text格式)")
    request_body: Optional[Dict[str, Any]] = Field(None, description="请求体数据(Json格式)")
    request_params: Optional[Union[Dict[str, Any], str]] = Field(None, description="请求路径参数(字典或字符串)")
    request_form_data: Optional[Dict[str, Any]] = Field(None, description="请求表单数据(Json格式)")
    request_form_file: Optional[Dict[str, Any]] = Field(None, description="请求文件路径(Json格式)")
    request_form_urlencoded: Optional[Dict[str, Any]] = Field(None, description="请求键值对数据(Json格式)")

    session_variables: Optional[Dict[str, Any]] = Field(None,
                                                        description="会话变量(包含提取变量，以及前后code设置的变量)")
    defined_variables: Optional[Dict[str, Any]] = Field(None,
                                                        description="定义变量(自定义变量，如编写指定值或引用随机函数)")
    extract_variables: Optional[List[Dict[str, Any]]] = Field(None,
                                                              description="提取变量(从请求控制器、上下文中提取、执行代码结果)")
    assert_validators: Optional[List[Dict[str, Any]]] = Field(None,
                                                              description="断言规则(支持对各类数据对象进行不同表达式的断言验证)")

    @field_validator('extract_variables', mode='before')
    @classmethod
    def normalize_extract_variables(cls, v):
        """将单个字典转换为列表格式，兼容前端可能发送的单个对象"""
        if v is None:
            return None
        if isinstance(v, dict):
            return [v]
        if isinstance(v, list):
            return v
        return v

    @field_validator('assert_validators', mode='before')
    @classmethod
    def normalize_assert_validators(cls, v):
        """将单个字典转换为列表格式，兼容前端可能发送的单个对象"""
        if v is None:
            return None
        if isinstance(v, dict):
            return [v]
        if isinstance(v, list):
            return v
        return v


class AutoTestStepTreeExecute(BaseModel):
    """执行测试步骤树请求模型"""
    case_id: Optional[int] = Field(None, description="用例ID（运行模式必填）")
    steps: Optional[List[AutoTestStepTreeUpdateItem]] = Field(None, description="步骤树数据（调试模式必填）")
    initial_variables: Optional[Dict[str, Any]] = Field(None, description="初始变量")

    @model_validator(mode='after')
    def validate_mode(self):
        """验证运行模式或调试模式参数"""
        case_id = self.case_id
        steps = self.steps

        # 必须提供case_id或steps之一，但不能同时提供
        if case_id is None and (steps is None or len(steps) == 0):
            raise ValueError("运行模式必须提供case_id，调试模式必须提供steps")
        if case_id is not None and steps is not None and len(steps) > 0:
            raise ValueError("运行模式和调试模式不能同时使用，请只提供case_id或steps之一")

        return self


# 允许递归引用
AutoTestApiStepBase.model_rebuild()
AutoTestStepTreeUpdateItem.model_rebuild()
