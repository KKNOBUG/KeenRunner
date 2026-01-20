# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_project_schema
@DateTime: 2026/1/2 16:49
"""
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator

from backend.applications.base.services.scaffold import UpperStr


class AutoTestApiProjectBase(BaseModel):
    project_name: Optional[str] = Field(None, max_length=255, description="应用名称")
    project_desc: Optional[str] = Field(None, max_length=2048, description="应用描述")
    project_state: Optional[str] = Field(None, max_length=64, description="应用状态")
    project_phase: Optional[str] = Field(None, max_length=64, description="应用阶段")
    project_dev_owners: Optional[List[str]] = Field(None, description="应用开发负责人")
    project_developers: Optional[List[str]] = Field(None, description="应用开发人员列表")
    project_test_owners: Optional[List[str]] = Field(None, description="应用测试负责人")
    project_testers: Optional[List[str]] = Field(None, description="应用测试人员列表")
    project_current_month_env: Optional[UpperStr] = Field(None, max_length=64, description="应用当前月版环境")


class AutoTestApiProjectCreate(AutoTestApiProjectBase):
    project_name: str = Field(..., max_length=255, description="应用名称")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")

    @field_validator('project_dev_owners', mode='before')
    @classmethod
    def normalize_project_dev_owners(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            return v.replace("，", ",").split(",")
        if isinstance(v, list):
            return v
        return v

    @field_validator('project_developers', mode='before')
    @classmethod
    def normalize_project_developers(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            return v.replace("，", ",").split(",")
        if isinstance(v, list):
            return v
        return v

    @field_validator('project_test_owners', mode='before')
    @classmethod
    def normalize_project_test_owners(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            return v.replace("，", ",").split(",")
        if isinstance(v, list):
            return v
        return v

    @field_validator('project_testers', mode='before')
    @classmethod
    def normalize_project_testers(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            return v.replace("，", ",").split(",")
        if isinstance(v, list):
            return v
        return v


class AutoTestApiProjectUpdate(AutoTestApiProjectBase):
    project_id: Optional[int] = Field(None, description="应用ID")
    project_code: Optional[str] = Field(None, max_length=64, description="应用标识代码")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestApiProjectSelect(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["-updated_time"], description="排序字段")

    project_id: Optional[int] = Field(None, description="应用ID")
    project_code: Optional[str] = Field(None, max_length=64, description="应用标识代码")
    project_state: Optional[str] = Field(None, max_length=64, description="应用状态")
    project_phase: Optional[str] = Field(None, max_length=64, description="应用阶段")
    project_dev_owners: Optional[List[str]] = Field(None, description="应用开发负责人")
    project_test_owners: Optional[List[str]] = Field(None, description="应用测试负责人")

    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    state: Optional[int] = Field(None, description="状态(0:启用, 1:禁用)")
