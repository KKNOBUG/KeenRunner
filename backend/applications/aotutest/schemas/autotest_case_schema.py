# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_schema.py
@DateTime: 2025/4/28
"""
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, field_validator

from backend.applications.base.services.scaffold import UpperStr
from backend.enums import AutoTestCaseType, AutoTestCaseAttr, AutoTestStepType, AutoTestReqArgsType


class AutoTestApiCaseMeta(BaseModel):
    """用例公共字段。"""

    case_id: Optional[int] = Field(None, description="用例ID")
    case_code: Optional[str] = Field(None, max_length=64, description="用例标识代码")
    case_types: Optional[List[AutoTestCaseType]] = Field(None, description="用例所属类型集合")
    case_steps: Optional[int] = Field(None, ge=0, description="用例步骤数量(含所有子级步骤)")
    case_state: Optional[bool] = Field(None, description="用例执行状态(True:成功, False:失败)")
    case_last_time: Optional[str] = Field(None, description="用例执行时间")
    case_version: Optional[int] = Field(None, ge=1, description="用例更新版本(修改次数)")


class AutoTestApiCaseBase(BaseModel):
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


class AutoTestApiCaseCreate(AutoTestApiCaseBase):
    """创建用例入参。"""

    case_name: str = Field(..., max_length=255, description="用例名称")
    case_desc: Optional[str] = Field(None, max_length=2048, description="用例描述")
    case_type: Optional[AutoTestCaseType] = Field(default=AutoTestCaseType.PRIVATE_SCRIPT, description="用例所属类型")
    case_attr: Optional[AutoTestCaseAttr] = Field(default=None, description="用例所属属性")
    case_project: int = Field(default=1, ge=1, description="用例所属应用")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class AutoTestApiCaseUpdate(AutoTestApiCaseMeta, AutoTestApiCaseBase):
    """更新用例入参。"""

    case_desc: Optional[str] = Field(None, max_length=2048, description="用例描述")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestApiCaseSelect(AutoTestApiCaseMeta, AutoTestApiCaseBase):
    """分页查询用例入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["-created_time"], description="排序字段")

    step_type: Optional[AutoTestStepType] = Field(None, description="步骤类型")
    request_args_type: Optional[AutoTestReqArgsType] = Field(None, description="请求参数类型")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    owner_user: Optional[UpperStr] = Field(None, max_length=16, description="所属人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")
