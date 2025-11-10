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

from backend.applications.aotutest.models.autotest_model import CodeLanguage


class BaseAutoTestStep(BaseModel):
    """步骤明细基础模型"""
    id: int
    step_name: str
    step_desc: Optional[str] = None
    step_type_id: int
    quote_case_id: Optional[int] = None
    request_url: Optional[str] = None
    request_port: Optional[str] = None
    request_protocol: str = "HTTP"
    request_method: Optional[str] = None
    request_header: Optional[Dict[str, Any]] = None
    request_body: Optional[Dict[str, Any]] = None
    request_params: Optional[Dict[str, Any]] = None
    request_form_data: Optional[Dict[str, Any]] = None
    request_form_file: Optional[str] = None
    request_form_urlencoded: Optional[Dict[str, Any]] = None
    pre_wait: Optional[int] = None
    post_wait: Optional[int] = None
    pre_code: Optional[str] = None
    post_code: Optional[str] = None
    pre_code_language: Optional[CodeLanguage] = None
    post_code_language: Optional[CodeLanguage] = None
    use_variables: Optional[Dict[str, Any]] = None
    ext_variables: Optional[Dict[str, Any]] = None
    validators: Optional[Dict[str, Any]] = None


class AutoTestStepCreate(BaseModel):
    """创建步骤明细"""
    step_name: str = Field(..., max_length=255, description="步骤名称")
    step_desc: Optional[str] = Field(None, max_length=2048, description="步骤描述")
    step_type_id: int = Field(..., description="步骤类型ID")
    quote_case_id: Optional[int] = Field(None, description="引用用例信息ID")
    request_url: Optional[str] = Field(None, max_length=2048, description="请求地址")
    request_port: Optional[str] = Field(None, max_length=16, description="请求端口")
    request_protocol: str = Field(default="HTTP", max_length=16, description="请求协议")
    request_method: Optional[str] = Field(None, max_length=16, description="请求方法")
    request_header: Optional[Dict[str, Any]] = Field(None, description="请求头，JSON格式")
    request_body: Optional[Dict[str, Any]] = Field(None, description="请求体，JSON格式")
    request_params: Optional[Dict[str, Any]] = Field(None, description="请求参数，JSON格式")
    request_form_data: Optional[Dict[str, Any]] = Field(None, description="请求表单，JSON格式")
    request_form_file: Optional[str] = Field(None, max_length=2048, description="请求文件路径")
    request_form_urlencoded: Optional[Dict[str, Any]] = Field(None, description="请求键值对，JSON格式")
    pre_wait: Optional[int] = Field(None, ge=0, description="前置等待时间（毫秒）")
    post_wait: Optional[int] = Field(None, ge=0, description="后置等待时间（毫秒）")
    pre_code: Optional[str] = Field(None, description="前置操作代码")
    post_code: Optional[str] = Field(None, description="后置操作代码")
    pre_code_language: Optional[CodeLanguage] = Field(None, description="前置操作代码语言类型")
    post_code_language: Optional[CodeLanguage] = Field(None, description="后置操作代码语言类型")
    use_variables: Optional[Dict[str, Any]] = Field(None, description="变量使用，JSON格式")
    ext_variables: Optional[Dict[str, Any]] = Field(None, description="变量提取，JSON格式")
    validators: Optional[Dict[str, Any]] = Field(None, description="断言规则，JSON格式")


class AutoTestStepUpdate(BaseModel):
    """更新步骤明细"""
    id: int = Field(..., description="步骤ID")
    step_name: Optional[str] = Field(None, max_length=255, description="步骤名称")
    step_desc: Optional[str] = Field(None, max_length=2048, description="步骤描述")
    step_type_id: Optional[int] = Field(None, description="步骤类型ID")
    quote_case_id: Optional[int] = Field(None, description="引用用例信息ID")
    request_url: Optional[str] = Field(None, max_length=2048, description="请求地址")
    request_port: Optional[str] = Field(None, max_length=16, description="请求端口")
    request_protocol: Optional[str] = Field(None, max_length=16, description="请求协议")
    request_method: Optional[str] = Field(None, max_length=16, description="请求方法")
    request_header: Optional[Dict[str, Any]] = Field(None, description="请求头，JSON格式")
    request_body: Optional[Dict[str, Any]] = Field(None, description="请求体，JSON格式")
    request_params: Optional[Dict[str, Any]] = Field(None, description="请求参数，JSON格式")
    request_form_data: Optional[Dict[str, Any]] = Field(None, description="请求表单，JSON格式")
    request_form_file: Optional[str] = Field(None, max_length=2048, description="请求文件路径")
    request_form_urlencoded: Optional[Dict[str, Any]] = Field(None, description="请求键值对，JSON格式")
    pre_wait: Optional[int] = Field(None, ge=0, description="前置等待时间（毫秒）")
    post_wait: Optional[int] = Field(None, ge=0, description="后置等待时间（毫秒）")
    pre_code: Optional[str] = Field(None, description="前置操作代码")
    post_code: Optional[str] = Field(None, description="后置操作代码")
    pre_code_language: Optional[CodeLanguage] = Field(None, description="前置操作代码语言类型")
    post_code_language: Optional[CodeLanguage] = Field(None, description="后置操作代码语言类型")
    use_variables: Optional[Dict[str, Any]] = Field(None, description="变量使用，JSON格式")
    ext_variables: Optional[Dict[str, Any]] = Field(None, description="变量提取，JSON格式")
    validators: Optional[Dict[str, Any]] = Field(None, description="断言规则，JSON格式")


class AutoTestStepSelect(BaseModel):
    """查询步骤明细条件"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["-updated_time"], description="排序字段")
    id: Optional[int] = Field(None, description="步骤ID")
    step_name: Optional[str] = Field(None, description="步骤名称")
    step_type_id: Optional[int] = Field(None, description="步骤类型ID")
    quote_case_id: Optional[int] = Field(None, description="引用用例信息ID")
