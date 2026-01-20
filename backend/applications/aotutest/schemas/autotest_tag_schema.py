# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_tag_schema
@DateTime: 2026/1/16 16:47
"""

from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

from backend.applications.base.services.scaffold import UpperStr
from backend.enums.autotest_enum import AutoTestTagType


class AutoTestApiTagCreate(BaseModel):
    tag_type: AutoTestTagType = Field(default=AutoTestTagType.SCRIPT, description="标签所属类型")
    tag_mode: str = Field(..., max_length=64, description="标签大类")
    tag_name: str = Field(..., max_length=64, description="标签名称")
    tag_desc: Optional[str] = Field(None, max_length=2048, description="标签描述")


class AutoTestApiTagUpdate(BaseModel):
    tag_id: Optional[int] = Field(None, description="标签ID")
    tag_code: Optional[str] = Field(None, max_length=64, description="标签标识代码")
    tag_type: Optional[AutoTestTagType] = Field(None, description="标签所属类型")
    tag_mode: Optional[str] = Field(None, max_length=64, description="标签大类")
    tag_name: Optional[str] = Field(None, max_length=64, description="标签名称")
    tag_desc: Optional[str] = Field(None, max_length=2048, description="标签描述")


class AutoTestApiTagSelect(AutoTestApiTagUpdate):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["-updated_time"], description="排序字段")

    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    state: Optional[int] = Field(0, description="状态(0:启用, 1:禁用)")
