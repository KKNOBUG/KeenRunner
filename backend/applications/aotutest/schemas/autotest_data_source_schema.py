# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_source_schema.py
@DateTime: 2026/3/6
"""
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

from backend.applications.base.services.scaffold import UpperStr


class AutoTestDataSourceCreate(BaseModel):
    """创建数据源单条记录（上传时由服务层按解析结果批量创建多条；file_code 由后端生成）。"""
    case_id: int = Field(..., ge=1, description="用例ID")
    step_code: str = Field(..., max_length=64, description="步骤标识代码")
    file_name: str = Field(None, max_length=255, description="数据驱动文件存储名称")
    file_hash: str = Field(None, max_length=255, description="数据驱动文件哈希代码")
    file_path: str = Field(None, max_length=1024, description="数据驱动文件存储路径")
    file_desc: Optional[str] = Field(None, max_length=2048, description="数据驱动文件场景描述")
    dataset: Dict[str, Any] = Field(None, description="数据驱动文件解析后的完整数据(所有步骤×所有场景)")
    dataset_names: Optional[List[str]] = Field(default_factory=list, description="数据驱动文件解析后的场景名称列表")
    cache_key: str = Field(None, max_length=64, description="获取Redis中该步骤数据的缓存键名")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class AutoTestDataSourceBase(BaseModel):
    case_id: Optional[int] = Field(None, ge=1, description="用例ID")
    step_code: Optional[str] = Field(None, max_length=64, description="步骤标识代码")
    file_name: Optional[str] = Field(None, max_length=255, description="数据驱动文件存储名称")
    file_path: Optional[str] = Field(None, max_length=1024, description="数据驱动文件哈希代码")
    file_hash: Optional[str] = Field(None, max_length=255, description="数据驱动文件存储路径")
    file_desc: Optional[str] = Field(None, max_length=2048, description="数据驱动文件场景描述")
    dataset: Optional[Dict[str, Any]] = Field(None, description="数据驱动文件解析后的数据(该步骤×所有场景)")
    dataset_names: Optional[List[str]] = Field(None, description="数据驱动文件解析后的场景名称列表")
    cache_key: Optional[str] = Field(None, max_length=64, description="获取Redis中该步骤数据的缓存键名")


class AutoTestDataSourceUpdate(AutoTestDataSourceBase):
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestDataSourceSelect(AutoTestDataSourceBase):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=100, description="每页数量")
    order: List[str] = Field(default=["-updated_time"], description="排序字段")


class AutoTestDataSourceListOut(BaseModel):
    """列表返回（按 file_code 聚合）：不含 dataset，含 steps 列表。"""
    file_code: Optional[str] = Field(None, description="文件标识代码")
    case_id: Optional[int] = Field(None, description="用例ID")
    file_name: Optional[str] = Field(None, description="上传的数据驱动文件存储名称")
    file_path: Optional[str] = Field(None, description="上传的数据驱动文件存储路径")
    file_desc: Optional[str] = Field(None, description="上传的数据驱动文件场景描述")
    dataset_names: Optional[List[str]] = Field(None, description="数据集名称列表")
    steps: Optional[List[Dict[str, Any]]] = Field(None, description="步骤列表 [{step_code}, ...]")
    created_time: Optional[str] = Field(None, description="创建时间")
    updated_time: Optional[str] = Field(None, description="更新时间")

    class Config:
        from_attributes = True
