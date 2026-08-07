# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_env_schema
@DateTime: 2026/1/2 16:44
"""
from typing import Optional, List, Union

from pydantic import BaseModel, Field

from backend.applications.base.services.scaffold import UpperStr


class AutoTestApiEnvCreate(BaseModel):
    """创建环境枚举入参。"""

    env_name: UpperStr = Field(..., max_length=64, description="环境枚举名称")
    env_desc: Optional[str] = Field(None, max_length=2048, description="环境枚举描述")
    created_user: Optional[Union[UpperStr, str]] = Field(None, max_length=16, description="创建人员")


class AutoTestApiEnvBase(BaseModel):
    """环境枚举公共字段。"""

    env_id: Optional[int] = Field(None, description="环境ID")
    env_code: Optional[str] = Field(None, max_length=64, description="环境标识代码")
    env_name: Optional[Union[UpperStr, str]] = Field(None, max_length=64, description="环境名称")
    env_desc: Optional[str] = Field(None, max_length=2048, description="环境枚举描述")
    updated_user: Optional[Union[UpperStr, str]] = Field(None, max_length=16, description="更新人员")


class AutoTestApiEnvUpdate(AutoTestApiEnvBase):
    """更新环境枚举入参。"""

    pass


class AutoTestApiEnvDelete(BaseModel):
    """删除环境枚举入参。"""

    env_ids: Optional[List[int]] = Field(None, description="环境ID列表")
    env_codes: Optional[List[str]] = Field(None, description="环境标识代码列表")


class AutoTestApiEnvSelect(AutoTestApiEnvBase):
    """分页查询环境枚举入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["-created_time"], description="排序字段")

    created_user: Optional[Union[UpperStr, str]] = Field(None, max_length=16, description="创建人员")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")
