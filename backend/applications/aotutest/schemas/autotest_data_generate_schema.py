# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_source_schema.py
@DateTime: 2026/3/6
"""
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field


class AutoTestApiDataCreateCreate(BaseModel):
    case_id: int = Field(..., description="用例ID")
    step_code: str = Field(..., max_length=64, description="用例标识代码")
    create_status: str = Field(..., description="创建状态（0：提交，1：生成中，2：失败，3：成功）")
    file_name: str = Field(..., max_length=255, description="接口文件存储名称")
    file_hash: str = Field(..., max_length=255, description="接口文件哈希代码")
    file_path: str = Field(..., max_length=1024, description="接口文件存储路径")
    file_desc: str = Field(None, max_length=2048, description="接口文件场景描述")
    file_code: Optional[str] = Field(None, max_length=64, description="接口文件标识代码")
    dataset: Optional[Dict[str, Any]] = Field(None, description="接口文件解析后的数据集")


class AutoTestApiDataCreateUpdate(BaseModel):
    id: int = Field(..., description="ID")
    create_status: str = Field(..., description="创建状态（0：提交，1：生成中，2：失败，3：成功）")
    file_path: str = Field(None, max_length=1024, description="接口文件存储路径")
    file_desc: str = Field(None, max_length=2048, description="接口文件场景描述")
