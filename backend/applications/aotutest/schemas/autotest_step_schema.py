# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_schema.py
@DateTime: 2025/4/28
"""
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

from backend.applications.aotutest.models.autotest_model import StepType


class BaseAutoTestApiStep(BaseModel):
    """步骤明细基础模型"""
    id: int
    step_no: int
    step_name: str
    step_desc: Optional[str] = None
    step_code: str
    step_type: StepType
    case_id: int
    parent_step_id: Optional[int] = None
    quote_case_id: Optional[int] = None
    request_url: Optional[str] = None
    request_port: Optional[str] = None
    request_method: Optional[str] = None
    request_header: Optional[Dict[str, Any]] = None
    request_text: Optional[str] = None
    request_body: Optional[Dict[str, Any]] = None
    request_params: Optional[str] = None
    request_form_data: Optional[Dict[str, Any]] = None
    request_form_file: Optional[Dict[str, Any]] = None
    request_form_urlencoded: Optional[Dict[str, Any]] = None
    pre_wait: Optional[int] = None
    post_wait: Optional[int] = None
    pre_code: Optional[str] = None
    post_code: Optional[str] = None
    use_variables: Optional[Dict[str, Any]] = None
    ext_variables: Optional[Dict[str, Any]] = None
    validators: Optional[Dict[str, Any]] = None
    children: Optional[List["BaseAutoTestApiStep"]] = None
    quote_steps: Optional[List["BaseAutoTestApiStep"]] = None


class AutoTestApiStepCreate(BaseModel):
    """创建步骤明细"""
    step_no: int = Field(..., ge=1, description="步骤明细序号")
    step_name: str = Field(..., max_length=255, description="步骤明细名称")
    step_desc: Optional[str] = Field(None, max_length=2048, description="步骤明细描述")
    step_type: StepType = Field(..., description="步骤明细类型")
    case_id: int = Field(..., description="步骤所属用例")
    parent_step_id: Optional[int] = Field(None, description="父级步骤ID")
    quote_case_id: Optional[int] = Field(None, description="引用用例信息ID")
    request_url: Optional[str] = Field(None, max_length=2048, description="请求地址")
    request_port: Optional[str] = Field(None, max_length=16, description="请求端口")
    request_method: Optional[str] = Field(None, max_length=16, description="请求方法")
    request_header: Optional[Dict[str, Any]] = Field(None, description="请求头，JSON格式")
    request_text: Optional[str] = Field(None, description="请求体，Text格式")
    request_body: Optional[Dict[str, Any]] = Field(None, description="请求体，JSON格式")
    request_params: Optional[str] = Field(None, description="请求参数，Text格式")
    request_form_data: Optional[Dict[str, Any]] = Field(None, description="请求表单，JSON格式")
    request_form_file: Optional[Dict[str, Any]] = Field(None, description="请求文件，JSON格式")
    request_form_urlencoded: Optional[Dict[str, Any]] = Field(None, description="请求键值对，JSON格式")
    pre_wait: Optional[int] = Field(None, ge=0, description="前置等待时间（毫秒）")
    post_wait: Optional[int] = Field(None, ge=0, description="后置等待时间（毫秒）")
    pre_code: Optional[str] = Field(None, description="前置操作代码")
    post_code: Optional[str] = Field(None, description="后置操作代码")
    use_variables: Optional[Dict[str, Any]] = Field(None, description="变量使用，JSON格式")
    ext_variables: Optional[Dict[str, Any]] = Field(None, description="变量提取，JSON格式")
    validators: Optional[Dict[str, Any]] = Field(None, description="断言规则，JSON格式")


class AutoTestApiStepUpdate(BaseModel):
    """更新步骤明细"""
    id: int = Field(..., description="步骤ID")
    step_no: Optional[int] = Field(None, ge=1, description="步骤明细序号")
    step_name: Optional[str] = Field(None, max_length=255, description="步骤明细名称")
    step_desc: Optional[str] = Field(None, max_length=2048, description="步骤明细描述")
    step_type: Optional[StepType] = Field(None, description="步骤明细类型")
    case_id: Optional[int] = Field(None, description="步骤所属用例")
    parent_step_id: Optional[int] = Field(None, description="父级步骤ID")
    quote_case_id: Optional[int] = Field(None, description="引用用例信息ID")
    request_url: Optional[str] = Field(None, max_length=2048, description="请求地址")
    request_port: Optional[str] = Field(None, max_length=16, description="请求端口")
    request_method: Optional[str] = Field(None, max_length=16, description="请求方法")
    request_header: Optional[Dict[str, Any]] = Field(None, description="请求头，JSON格式")
    request_text: Optional[str] = Field(None, description="请求体，Text格式")
    request_body: Optional[Dict[str, Any]] = Field(None, description="请求体，JSON格式")
    request_params: Optional[str] = Field(None, description="请求参数，Text格式")
    request_form_data: Optional[Dict[str, Any]] = Field(None, description="请求表单，JSON格式")
    request_form_file: Optional[Dict[str, Any]] = Field(None, description="请求文件，JSON格式")
    request_form_urlencoded: Optional[Dict[str, Any]] = Field(None, description="请求键值对，JSON格式")
    pre_wait: Optional[int] = Field(None, ge=0, description="前置等待时间（毫秒）")
    post_wait: Optional[int] = Field(None, ge=0, description="后置等待时间（毫秒）")
    pre_code: Optional[str] = Field(None, description="前置操作代码")
    post_code: Optional[str] = Field(None, description="后置操作代码")
    use_variables: Optional[Dict[str, Any]] = Field(None, description="变量使用，JSON格式")
    ext_variables: Optional[Dict[str, Any]] = Field(None, description="变量提取，JSON格式")
    validators: Optional[Dict[str, Any]] = Field(None, description="断言规则，JSON格式")


class AutoTestStepSelect(BaseModel):
    """查询步骤明细条件"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["case_id", "step_no"], description="排序字段")
    id: Optional[int] = Field(None, description="步骤ID")
    step_name: Optional[str] = Field(None, description="步骤名称")
    case_id: Optional[int] = Field(None, description="用例信息ID")
    step_type: Optional[StepType] = Field(None, description="步骤类型")
    parent_step_id: Optional[int] = Field(None, description="父级步骤ID")
    quote_case_id: Optional[int] = Field(None, description="引用用例信息ID")
    state: Optional[int] = Field(-1, description="步骤状态，正常：-1，删除：1")


# 允许递归引用
BaseAutoTestApiStep.model_rebuild()
