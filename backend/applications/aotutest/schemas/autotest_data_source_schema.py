# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_source_schema.py
@DateTime: 2026/3/6
"""
from typing import Optional, List, Dict, Any, Union

from pydantic import BaseModel, ConfigDict, Field

from backend.applications.base.services.scaffold import UpperStr


class AutoTestDataSourceBase(BaseModel):
    """数据驱动文件公共字段（创建/更新共用）。"""

    case_id: Optional[int] = Field(None, ge=1, description="用例ID")
    case_code: Optional[str] = Field(None, max_length=64, description="用例标识代码")
    step_id: Optional[int] = Field(None, ge=1, description="步骤ID")
    step_code: Optional[str] = Field(None, max_length=64, description="步骤标识代码")
    file_name: Optional[str] = Field(None, max_length=255, description="数据驱动文件存储名称")
    file_path: Optional[str] = Field(None, max_length=1024, description="数据驱动文件存储路径")
    file_hash: Optional[str] = Field(None, max_length=255, description="数据驱动文件哈希代码")
    file_desc: Optional[str] = Field(None, max_length=2048, description="数据驱动文件场景描述")
    dataset: Optional[Dict[str, Any]] = Field(None, description="数据驱动文件解析后的数据(该步骤×所有场景)")
    dataset_names: Optional[List[str]] = Field(None, description="数据驱动文件解析后的场景名称列表")
    cache_key: Optional[str] = Field(None, max_length=128, description="获取Redis中该步骤数据的缓存键名")
    dataframe: Optional[List[Any]] = Field(None, description="数据驱动文件解析前的二维矩阵")
    axis: Optional[int] = Field(0, ge=0, le=1, description="数据矩阵方向(0:水平模式-场景为行, 1:垂直模式-场景为列)")


class AutoTestDataSourceCreate(AutoTestDataSourceBase):
    """创建数据驱动文件入参。"""

    case_id: int = Field(..., ge=1, description="用例ID")
    case_code: str = Field(..., max_length=64, description="用例标识代码")
    step_id: int = Field(..., ge=1, description="步骤ID")
    step_code: str = Field(..., max_length=64, description="步骤标识代码")
    created_user: Optional[Union[UpperStr, str]] = Field(None, max_length=16, description="创建人员")


class AutoTestDataSourceUpdate(AutoTestDataSourceBase):
    """更新数据驱动文件入参。"""

    data_source_id: Optional[int] = Field(None, ge=1, description="主键ID")
    data_source_code: Optional[str] = Field(None, max_length=64, description="数据驱动文件标识代码")
    updated_user: Optional[Union[UpperStr, str]] = Field(None, max_length=16, description="更新人员")


class AutoTestDataSourceSaveOrUpdate(AutoTestDataSourceBase):
    """保存或更新数据源入参"""

    data_source_id: Optional[int] = Field(None, ge=1, description="数据源ID")
    data_source_code: Optional[str] = Field(None, max_length=64, description="数据源标识代码")
    case_id: int = Field(..., ge=1, description="用例ID")
    case_code: str = Field(..., max_length=64, description="用例标识代码")
    step_id: int = Field(..., ge=1, description="步骤ID")
    step_code: str = Field(..., max_length=64, description="步骤标识代码")
    created_user: Optional[Union[UpperStr, str]] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[Union[UpperStr, str]] = Field(None, max_length=16, description="操作人员")


class AutoTestDataSourceSelect(BaseModel):
    """分页查询数据驱动文件入参。"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=100, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["-updated_time"], description="排序字段")
    data_source_id: Optional[int] = Field(None, ge=1, description="主键过滤")
    data_source_code: Optional[str] = Field(None, max_length=64, description="数据驱动标识过滤")
    case_id: Optional[int] = Field(None, ge=1, description="用例ID")
    case_code: Optional[str] = Field(None, max_length=64, description="用例标识代码")
    step_id: Optional[int] = Field(None, ge=1, description="步骤ID")
    step_code: Optional[str] = Field(None, max_length=64, description="步骤标识代码")
    file_name: Optional[str] = Field(None, max_length=255, description="数据驱动文件存储名称")
    file_path: Optional[str] = Field(None, max_length=1024, description="数据驱动文件存储路径")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)，默认仅查启用")


class AutoTestDataSourceConditionQuery(BaseModel):
    """根据任意模型字段条件查询"""

    conditions: Dict[str, Any] = Field(..., description="与模型字段一致的等值条件")
    only_one: bool = Field(default=True, description="为 True 返回单条，否则返回列表")


class AutoTestDataSourceListOut(BaseModel):
    """数据驱动文件列表输出字段模型。"""

    case_id: Optional[int] = Field(None, description="用例ID")
    case_code: Optional[str] = Field(None, description="用例标识代码")
    data_source_code: Optional[str] = Field(None, description="数据驱动标识代码")
    file_name: Optional[str] = Field(None, description="上传的数据驱动文件存储名称")
    file_path: Optional[str] = Field(None, description="上传的数据驱动文件存储路径")
    file_desc: Optional[str] = Field(None, description="上传的数据驱动文件场景描述")
    dataset_names: Optional[List[str]] = Field(None, description="数据集名称列表")
    steps: Optional[List[Dict[str, Any]]] = Field(None, description="步骤列表 [{step_id, step_code}, ...]")
    created_time: Optional[str] = Field(None, description="创建时间")
    updated_time: Optional[str] = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)
