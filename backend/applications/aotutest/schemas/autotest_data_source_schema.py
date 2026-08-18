# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_source_schema.py
@DateTime: 2026/3/6
"""
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, model_validator

from backend.applications.base.services.scaffold import UpperStr


def _has_text(value: Optional[str]) -> bool:
    """非空字符串判断。"""
    return bool((value or "").strip())


class AutoTestDataSourceBase(BaseModel):
    """数据驱动文件公共字段。"""

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
    axis: Optional[int] = Field(None, ge=0, le=1, description="数据矩阵(0:水平模式, 1:垂直模式)")


class AutoTestDataSourceCreate(AutoTestDataSourceBase):
    """创建数据驱动文件入参。定位：(case_id或case_code)且(step_id或step_code)。"""

    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")

    @model_validator(mode="after")
    def _require_case_and_step(self):
        """创建必须同时定位到用例与步骤。"""
        has_case = bool(self.case_id) or _has_text(self.case_code)
        has_step = bool(self.step_id) or _has_text(self.step_code)
        if not (has_case and has_step):
            raise ValueError("请提供(case_id或case_code)且(step_id或step_code)以绑定数据源")
        return self


class AutoTestDataSourceUpdate(AutoTestDataSourceBase):
    """更新数据驱动文件入参。定位：data_source_id/code，或(case_id或case_code)且(step_id或step_code)。"""

    data_source_id: Optional[int] = Field(None, ge=1, description="主键ID")
    data_source_code: Optional[str] = Field(None, max_length=64, description="数据驱动文件标识代码")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")

    @model_validator(mode="after")
    def _require_locator(self):
        """更新必须能定位到一条数据源。"""
        if self.data_source_id or _has_text(self.data_source_code):
            return self
        has_case = bool(self.case_id) or _has_text(self.case_code)
        has_step = bool(self.step_id) or _has_text(self.step_code)
        if not (has_case and has_step):
            raise ValueError(
                "请提供[data_source_id或data_source_code]，或提供(case_id或case_code)且(step_id或step_code)"
            )
        return self


class AutoTestDataSourceSaveOrUpdate(AutoTestDataSourceBase):
    """保存或更新数据源入参。有data_source_id/code则更新；否则按用例+步骤有则更新无则新增。"""

    data_source_id: Optional[int] = Field(None, ge=1, description="数据源ID")
    data_source_code: Optional[str] = Field(None, max_length=64, description="数据源标识代码")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="操作人员")

    @model_validator(mode="after")
    def _require_locator(self):
        """保存必须能定位到步骤上的数据源槽位。"""
        if self.data_source_id or _has_text(self.data_source_code):
            return self
        has_case = bool(self.case_id) or _has_text(self.case_code)
        has_step = bool(self.step_id) or _has_text(self.step_code)
        if not (has_case and has_step):
            raise ValueError(
                "请提供[data_source_id或data_source_code]，或提供(case_id或case_code)且(step_id或step_code)"
            )
        return self


class AutoTestDataSourceUnbindCase(BaseModel):
    """解绑指定用例下全部数据源入参。"""

    case_id: Optional[int] = Field(None, ge=1, description="用例ID")
    case_code: Optional[str] = Field(None, max_length=64, description="用例标识代码")

    @model_validator(mode="after")
    def _require_case(self):
        """解绑必须定位到用例。"""
        if not self.case_id and not _has_text(self.case_code):
            raise ValueError("请提供[case_id或case_code]以解绑用例数据源")
        return self


class AutoTestDataSourceSelect(BaseModel):
    """分页查询数据驱动文件入参。"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=100, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["-updated_time"], description="排序字段")

    data_source_id: Optional[int] = Field(None, ge=1, description="主键ID")
    data_source_code: Optional[str] = Field(None, max_length=64, description="数据驱动文件标识代码")
    case_id: Optional[int] = Field(None, ge=1, description="用例ID")
    case_code: Optional[str] = Field(None, max_length=64, description="用例标识代码")
    step_id: Optional[int] = Field(None, ge=1, description="步骤ID")
    step_code: Optional[str] = Field(None, max_length=64, description="步骤标识代码")
    file_name: Optional[str] = Field(None, max_length=255, description="数据驱动文件存储名称")
    file_path: Optional[str] = Field(None, max_length=1024, description="数据驱动文件存储路径")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")
