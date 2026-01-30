# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_env_schema
@DateTime: 2026/1/2 16:44
"""
from typing import Optional, List

from pydantic import BaseModel, Field

from backend.applications.base.services.scaffold import UpperStr


class AutoTestApiEnvCreate(BaseModel):
    project_id: int = Field(..., description="环境所属项目")
    env_name: UpperStr = Field(..., max_length=64, description="环境名称")
    env_port: int = Field(..., ge=1, description="环境端口(8000)")
    env_host: str = Field(..., max_length=128, description="环境主机(http|https://127.0.0.1)")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class AutoTestApiEnvBase(BaseModel):
    env_id: Optional[int] = Field(None, description="环境ID")
    env_code: Optional[str] = Field(None, max_length=64, description="环境标识代码")
    project_id: Optional[int] = Field(None, description="环境所属项目")
    env_name: Optional[UpperStr] = Field(None, max_length=64, description="环境名称")
    env_port: Optional[int] = Field(None, ge=1, description="环境端口(8000)")
    env_host: Optional[str] = Field(None, max_length=255, description="环境主机(http|https://127.0.0.1)")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestApiEnvUpdate(AutoTestApiEnvBase):
    pass


class AutoTestApiEnvSelect(AutoTestApiEnvBase):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["-updated_time"], description="排序字段")

    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")
