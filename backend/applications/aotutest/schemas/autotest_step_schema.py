# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_schema.py
@DateTime: 2025/4/28
"""
from typing import Optional, List, Dict, Any, Type

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.applications.aotutest.schemas.autotest_case_schema import AutoTestApiCaseUpdate
from backend.applications.base.services.scaffold import UpperStr
from backend.enums.autotest_enum import AutoTestCaseType, AutoTestStepType, AutoTestLoopMode, AutoTestLoopErrorStrategy, \
    AutoTestReqArgsType
from backend.enums.http_enum import HTTPMethod

NON_DICT_TYPE: Type = Optional[Dict[str, Any]]
NON_LIST_DICT_TYPE: Type = Optional[List[Dict[str, Any]]]


class AutoTestApiStepReqBase(BaseModel):
    request_url: Optional[str] = Field(None, max_length=2048, description="请求地址")
    request_port: Optional[str] = Field(None, max_length=16, description="请求端口")
    request_method: Optional[HTTPMethod] = Field(None, max_length=16, description="请求方法(GET/POST/PUT/DELETE等)")
    request_text: Optional[str] = Field(None, description="请求体数据(Text格式)")
    request_body: NON_DICT_TYPE = Field(None, description="请求体数据(Json格式)")
    request_header: NON_LIST_DICT_TYPE = Field(None, description="请求头信息")
    request_params: NON_LIST_DICT_TYPE = Field(None, description="请求路径参数")
    request_form_data: NON_LIST_DICT_TYPE = Field(None, description="请求表单数据")
    request_form_urlencoded: NON_LIST_DICT_TYPE = Field(None, description="请求键值对数据")
    request_form_file: NON_LIST_DICT_TYPE = Field(None, description="请求文件路径")
    request_project_id: Optional[int] = Field(None, description="请求应用ID")
    request_args_type: Optional[AutoTestReqArgsType] = Field(None, description="AutoTestReqArgsType")


class AutoTestApiStepVarBase(BaseModel):
    session_variables: NON_LIST_DICT_TYPE = Field(None, description="会话变量(所有步骤的执行结果持续累积)")
    defined_variables: NON_LIST_DICT_TYPE = Field(None, description="定义变量(用户自定义、引用函数的结果)")
    extract_variables: NON_LIST_DICT_TYPE = Field(None, description="提取变量(从请求控制器、上下文中提取、执行代码结果)")
    assert_validators: NON_LIST_DICT_TYPE = Field(None, description="断言规则(支持对数据对象进行不同表达式的断言验证)")


class AutoTestApiStepBase(AutoTestApiStepReqBase, AutoTestApiStepVarBase):
    step_id: Optional[int] = Field(None, description="步骤ID(更新必填, 新增不填)")
    step_no: Optional[int] = Field(None, ge=1, description="步骤序号")
    step_code: Optional[str] = Field(None, max_length=64, description="步骤标识代码(更新必填, 新增不填)")
    step_name: Optional[str] = Field(None, max_length=255, description="步骤名称")
    step_desc: Optional[str] = Field(None, description="步骤描述")
    step_type: Optional[AutoTestStepType] = Field(None, description="步骤所属类型")

    case_id: Optional[int] = Field(None, description="步骤所属用例")
    quote_case_id: Optional[int] = Field(None, description="引用公共用例ID")
    parent_step_id: Optional[int] = Field(None, description="父级步骤ID")

    code: Optional[str] = Field(None, description="执行代码(Python)")
    wait: Optional[float] = Field(None, ge=0, le=300, description="等待控制(正浮点数, 单位:秒)")
    loop_mode: Optional[AutoTestLoopMode] = Field(None, description="循环模式类型")
    loop_maximums: Optional[int] = Field(None, ge=1, le=100, description="最大循环次数(正整数)")
    loop_interval: Optional[float] = Field(None, ge=0, le=60, description="每次循环间隔时间(正浮点数)")
    loop_iterable: Optional[str] = Field(None, max_length=512, description="循环对象来源(变量名或可迭代对象)")
    loop_iter_idx: Optional[str] = Field(None, max_length=64, description="用于存储enumerate得到的索引值")
    loop_iter_key: Optional[str] = Field(None, max_length=64, description="用于存储字典的键")
    loop_iter_val: Optional[str] = Field(None, max_length=64, description="用于存储字典的值或列表的项")
    loop_on_error: Optional[AutoTestLoopErrorStrategy] = Field(None, description="循环执行失败时的处理策略")
    loop_timeout: Optional[float] = Field(None, ge=0, le=3000,
                                          description="条件循环超时时间(正浮点数, 单位:秒, 0表示不超时)")
    conditions: NON_LIST_DICT_TYPE = Field(None, description="判断条件(循环结构或条件分支)")
    state: Optional[int] = Field(default=0, description="状态(0:未删除, 1:删除, 2:执行成功, 3:执行失败)")


class AutoTestApiStepChildren(BaseModel):
    children: Optional[List["AutoTestApiStepBase"]] = Field(None, description="子步骤")
    quote_steps: Optional[List["AutoTestApiStepBase"]] = Field(None, description="引用步骤")


class AutoTestApiStepCreate(AutoTestApiStepBase):
    step_no: int = Field(..., ge=1, description="步骤序号")
    step_name: str = Field(..., max_length=255, description="步骤名称")
    step_type: AutoTestStepType = Field(..., description="步骤所属类型")
    created_user: Optional[UpperStr] = Field(None, description="创建人员")


class AutoTestApiStepUpdate(AutoTestApiStepBase):
    updated_user: Optional[UpperStr] = Field(None, description="更新人员")


class AutoTestApiStepSelect(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["case_id", "step_no"], description="排序字段")

    step_id: Optional[int] = Field(None, description="步骤ID")
    step_no: Optional[int] = Field(None, description="步骤序号")
    step_name: Optional[str] = Field(None, max_length=255, description="步骤名称")
    step_type: Optional[AutoTestStepType] = Field(None, description="步骤类型")

    case_id: Optional[int] = Field(None, description="用例ID")
    parent_step_id: Optional[int] = Field(None, description="父级步骤ID")
    quote_case_id: Optional[int] = Field(None, description="引用公共用例ID")
    created_user: Optional[UpperStr] = Field(None, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, description="更新人员")
    state: Optional[int] = Field(default=0, description="状态(0:未删除, 1:删除, 2:执行成功, 3:执行失败)")


class AutoTestStepTreeUpdateItem(AutoTestApiStepBase):
    case: NON_DICT_TYPE = Field(None, description="用例信息")
    children: Optional[List["AutoTestStepTreeUpdateItem"]] = Field(None, description="子步骤列表")
    quote_steps: Optional[List[Any]] = Field(None, description="引用步骤列表(更新时忽略)")
    quote_case: Optional[Any] = Field(None, description="引用公共用例信息(更新时忽略)")


class AutoTestStepTreeUpdateList(BaseModel):
    case: AutoTestApiCaseUpdate = Field(..., description="用例信息")
    steps: List[AutoTestStepTreeUpdateItem] = Field(..., description="步骤树数据")


class AutoTestHttpDebugRequest(AutoTestApiStepVarBase, AutoTestApiStepReqBase):
    env_name: str = Field(..., max_length=64, description="环境名称")
    step_name: str = Field(..., max_length=255, description="步骤名称")
    request_url: str = Field(..., max_length=2048, description="请求地址")
    request_method: HTTPMethod = Field(..., description="请求方法")
    request_project_id: int = Field(..., description="请求应用ID")

    @field_validator('extract_variables', mode='before')
    @classmethod
    def normalize_extract_variables(cls, v):
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
        if v is None:
            return None
        if isinstance(v, dict):
            return [v]
        if isinstance(v, list):
            return v
        return v


class AutoTestPythonCodeDebugRequest(AutoTestApiStepVarBase):
    step_name: str = Field(..., max_length=255, description="步骤名称")
    code: str = Field(..., description="执行代码(Python)")

    @field_validator('extract_variables', mode='before')
    @classmethod
    def normalize_extract_variables(cls, v):
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
        if v is None:
            return None
        if isinstance(v, dict):
            return [v]
        if isinstance(v, list):
            return v
        return v


class AutoTestStepTreeExecute(BaseModel):
    # todo：env_name 暂且实现
    env_name: Optional[str] = Field(None, max_length=64, description="环境名称")
    case_id: Optional[int] = Field(None, description="用例ID(运行模式和调试模式都必填)")
    steps: Optional[List[AutoTestStepTreeUpdateItem]] = Field(None,
                                                              description="步骤树数据(调试模式必填, 运行模式不填)")
    initial_variables: NON_LIST_DICT_TYPE = Field(None, description="会话变量(初始变量池)")

    @model_validator(mode='after')
    def validate_mode(self):
        case_id = self.case_id
        steps = self.steps
        # case_id 是必填的（运行模式和调试模式都需要）
        # 运行模式：只传递 case_id，不传递 steps
        # 调试模式：传递 case_id 和 steps
        if case_id is None:
            raise ValueError("必须提供[case_id]参数（运行模式和调试模式都需要）")
        return self


class AutoTestBatchExecuteCases(BaseModel):
    env_name: Optional[str] = Field(None, description="执行环境名称")
    case_ids: List[int] = Field(..., min_length=1, description="用例ID列表")
    initial_variables: NON_LIST_DICT_TYPE = Field(None, description="初始变量(会应用到所有用例)")


# 允许递归引用
AutoTestApiStepBase.model_rebuild()
AutoTestStepTreeUpdateItem.model_rebuild()
