# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_schema.py
@DateTime: 2025/4/28
"""
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.applications.base.services.scaffold import UpperStr
from backend.enums import AutoTestCaseType, AutoTestCaseAttr, AutoTestStepType, AutoTestReqArgsType


class AutoTestCaseMeta(BaseModel):
    """用例公共字段。"""

    case_id: Optional[int] = Field(None, description="用例ID")
    case_code: Optional[str] = Field(None, max_length=64, description="用例标识代码")
    case_types: Optional[List[AutoTestCaseType]] = Field(None, description="用例所属类型列表")
    case_steps: Optional[int] = Field(None, ge=0, description="用例步骤数量")
    case_state: Optional[bool] = Field(None, description="用例执行状态")
    case_last_time: Optional[str] = Field(None, description="用例执行时间")
    case_version: Optional[int] = Field(None, ge=1, description="用例更新版本")


class AutoTestCaseBase(BaseModel):
    """用例公共字段。"""

    case_name: Optional[str] = Field(None, max_length=255, description="用例名称")
    case_tags: Optional[List[int]] = Field(None, description="用例所属标签")
    case_type: Optional[AutoTestCaseType] = Field(None, description="用例所属类型")
    case_attr: Optional[AutoTestCaseAttr] = Field(None, description="用例所属属性")
    case_project: Optional[int] = Field(None, ge=1, description="用例所属应用")
    session_variables: Optional[List[Dict[str, Any]]] = Field(None, description="会话变量(初始变量池)")

    @field_validator("case_tags", "session_variables", mode="before")
    @classmethod
    def _empty_list_to_none(cls, v: Any) -> Any:
        """
        case_tags/session_variables字段空数组时归一为null值。

        :param v: 原始值
        :return: 空数组时返回None，其余原样返回
        """
        if isinstance(v, list) and not v:
            return None
        return v


class AutoTestCaseCreate(AutoTestCaseBase):
    """创建用例入参。"""

    case_name: str = Field(..., max_length=255, description="用例名称")
    case_desc: Optional[str] = Field(None, max_length=2048, description="用例描述")
    case_type: Optional[AutoTestCaseType] = Field(default=AutoTestCaseType.PRIVATE_SCRIPT, description="用例所属类型")
    case_attr: Optional[AutoTestCaseAttr] = Field(default=None, description="用例所属属性")
    case_project: int = Field(default=1, ge=1, description="用例所属应用")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class AutoTestCaseUpdate(AutoTestCaseMeta, AutoTestCaseBase):
    """更新用例入参。"""

    case_desc: Optional[str] = Field(None, max_length=2048, description="用例描述")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestCaseScriptGenerate(BaseModel):
    """公共接口转脚本生成入参。"""

    case_ids: List[int] = Field(..., description="用例ID列表")
    case_project: int = Field(..., ge=1, description="脚本所属应用")
    case_type: AutoTestCaseType = Field(..., description="用例所属类型")
    case_attr: AutoTestCaseAttr = Field(..., description="用例所属属性")
    case_tags: Optional[List[int]] = Field(None, description="脚本所属标签")

    @field_validator("case_type")
    @classmethod
    def _validate_script_type(cls, v: AutoTestCaseType) -> AutoTestCaseType:
        """
        校验脚本类型：公共接口自身不允许作为生成目标类型。

        :param v: 脚本类型
        :return: 校验通过的脚本类型
        """
        if v not in (AutoTestCaseType.PRIVATE_SCRIPT, AutoTestCaseType.PUBLIC_SCRIPT):
            raise ValueError("脚本类型仅允许[用户脚本/公共脚本]")
        return v

    @field_validator("case_tags", mode="before")
    @classmethod
    def _empty_tags_to_none(cls, v: Any) -> Any:
        """
        case_tags字段空数组时归一为null值。

        :param v: 原始值
        :return: 空数组时返回None，其余原样返回
        """
        if isinstance(v, list) and not v:
            return None
        return v

    @model_validator(mode="after")
    def _validate_tags_required(self) -> "AutoTestCaseScriptGenerate":
        """
        脚本类型为用户脚本时标签必选，公共脚本可选。

        :return: 校验通过的入参实例
        """
        if self.case_type == AutoTestCaseType.PRIVATE_SCRIPT and not self.case_tags:
            raise ValueError("脚本类型为[用户脚本]时必须选择所属标签")
        return self


class AutoTestCaseSelect(AutoTestCaseMeta, AutoTestCaseBase):
    """分页查询用例入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["-created_time"], description="排序字段")
    case_ids: Optional[List[int]] = Field(None, description="用例ID列表")

    step_type: Optional[AutoTestStepType] = Field(None, description="步骤类型")
    owner_user: Optional[UpperStr] = Field(None, max_length=16, description="所属人员")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    request_args_type: Optional[AutoTestReqArgsType] = Field(None, description="请求参数类型")
    state: Optional[int] = Field(default=0, description="状态")
