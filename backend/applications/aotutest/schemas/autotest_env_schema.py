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
from backend.enums import AutoTestConfigNodeType


class AutoTestApiEnvBase(BaseModel):
    """环境绑定公共字段。"""

    env_name: Optional[UpperStr] = Field(None, max_length=64, description="环境名称")
    project_id: Optional[int] = Field(None, ge=1, description="应用ID")
    env_type: Optional[AutoTestConfigNodeType] = Field(None, description="节点类型(api/file/database/redis)")
    env_desc: Optional[str] = Field(None, max_length=2048, description="环境描述")


class AutoTestApiEnvCreate(AutoTestApiEnvBase):
    """创建环境绑定入参。"""

    env_name: UpperStr = Field(..., max_length=64, description="环境名称")
    project_id: int = Field(..., ge=1, description="应用ID")
    env_type: AutoTestConfigNodeType = Field(..., description="节点类型(api/file/database/redis)")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class AutoTestApiEnvUpdate(AutoTestApiEnvBase):
    """更新环境绑定入参。"""

    env_id: Optional[int] = Field(None, ge=1, description="环境绑定主键ID")
    env_code: Optional[str] = Field(None, max_length=64, description="环境绑定标识代码")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestApiEnvDelete(BaseModel):
    """批量删除环境绑定入参。"""

    env_ids: Optional[List[int]] = Field(None, description="环境绑定主键ID列表")
    env_codes: Optional[List[str]] = Field(None, description="环境绑定标识代码列表")


class AutoTestApiEnvSelect(AutoTestApiEnvUpdate):
    """分页查询环境绑定入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["-created_time"], description="排序字段")

    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")


class AutoTestApiEnvListQuery(BaseModel):
    """按应用聚合查询环境名称列表入参。"""

    project_id: Optional[List[int]] = Field(None, description="应用ID列表，如 [999,998,997]")
