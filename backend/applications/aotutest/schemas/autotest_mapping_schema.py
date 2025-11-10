# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_mapping_schema.py
@DateTime: 2025/4/28
"""
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class BaseAutoTestStepMapping(BaseModel):
    """步骤映射基础模型"""
    id: int
    case_id: int
    step_info_id: int
    parent_mapping_id: Optional[int] = None
    step_no: int
    children: Optional[List["BaseAutoTestStepMapping"]] = None
    step_info: Optional[Dict[str, Any]] = None


class AutoTestStepMappingCreate(BaseModel):
    """创建步骤映射"""
    case_id: int = Field(..., description="用例信息ID")
    step_info_id: int = Field(..., description="步骤明细ID")
    parent_mapping_id: Optional[int] = Field(None, description="父级步骤映射ID")
    step_no: int = Field(..., ge=1, description="步骤序号，正整数")


class AutoTestStepMappingUpdate(BaseModel):
    """更新步骤映射"""
    id: int = Field(..., description="步骤映射ID")
    case_id: Optional[int] = Field(None, description="用例信息ID")
    step_info_id: Optional[int] = Field(None, description="步骤明细ID")
    parent_mapping_id: Optional[int] = Field(None, description="父级步骤映射ID")
    step_no: Optional[int] = Field(None, ge=1, description="步骤序号，正整数")


class AutoTestStepMappingSelect(BaseModel):
    """查询步骤映射条件"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["step_no"], description="排序字段")
    id: Optional[int] = Field(None, description="步骤映射ID")
    case_id: Optional[int] = Field(None, description="用例信息ID")
    step_info_id: Optional[int] = Field(None, description="步骤明细ID")
    parent_mapping_id: Optional[int] = Field(None, description="父级步骤映射ID")
    step_no: Optional[int] = Field(None, description="步骤序号")


# 允许递归引用
BaseAutoTestStepMapping.model_rebuild()

