# -*- coding: utf-8 -*-
"""
多记录对比/汇总入参契约。

对 2~20 份已完成压测报告做横向对比(compare)或同场景汇总合并(merge),
创建时由服务层一次性计算结果快照, 本契约只描述创建/查询/定位的入参边界。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_comparison_schema.py
@DateTime: 2026/9/17 20:30
"""
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from backend.applications.base.services.scaffold import UpperStr
from backend.enums import PerfComparisonMode

# 参与对比的报告数量边界(设计§3.7: 2~20 份)
PERF_COMPARISON_REPORTS_MIN = 2
PERF_COMPARISON_REPORTS_MAX = 20


def _has_text(value: Optional[str]) -> bool:
    """非空字符串判断。"""
    return bool((value or "").strip())


class PerfComparisonCreate(BaseModel):
    """新建对比/汇总记录入参。"""

    comparison_name: str = Field(..., min_length=1, max_length=255, description="对比记录名称")
    comparison_mode: PerfComparisonMode = Field(..., description="对比模式(compare横向对比/merge汇总合并/hybrid两者兼出)")
    report_codes: List[str] = Field(
        ..., min_length=PERF_COMPARISON_REPORTS_MIN, max_length=PERF_COMPARISON_REPORTS_MAX,
        description="参与报告标识代码列表(2~20份, 自动去重)",
    )
    baseline_code: Optional[str] = Field(None, max_length=64, description="基准报告标识代码(compare/hybrid必填且须在report_codes内)")
    comparison_desc: Optional[str] = Field(None, max_length=2048, description="对比说明")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")

    @model_validator(mode="after")
    def _check_reports(self):
        """报告清单去重与基准归属校验: 基准必须在参与清单内, 否则相对变化的参照系不存在。"""
        if len(set(self.report_codes)) != len(self.report_codes):
            raise ValueError("参数[report_codes]存在重复报告")
        if self.comparison_mode in (PerfComparisonMode.COMPARE, PerfComparisonMode.HYBRID):
            if not _has_text(self.baseline_code):
                raise ValueError("参数[baseline_code]不能为空, 横向对比模式需指定基准报告")
            if self.baseline_code not in self.report_codes:
                raise ValueError("参数[baseline_code]必须在[report_codes]参与清单内")
        return self


class PerfComparisonSelect(BaseModel):
    """分页查询对比/汇总记录入参。"""

    comparison_id: Optional[int] = Field(None, ge=1, description="对比记录ID")
    comparison_code: Optional[str] = Field(None, max_length=64, description="对比记录标识代码")
    comparison_name: Optional[str] = Field(None, max_length=255, description="对比记录名称(模糊匹配)")
    comparison_mode: Optional[PerfComparisonMode] = Field(None, description="对比模式")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, le=100, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["-updated_time"], description="排序字段")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")


class PerfComparisonLocate(BaseModel):
    """定位单个对比/汇总记录入参(detail/delete共用)。"""

    comparison_id: Optional[int] = Field(None, ge=1, description="对比记录ID")
    comparison_code: Optional[str] = Field(None, max_length=64, description="对比记录标识代码")

    @model_validator(mode="after")
    def _require_locator(self):
        """必须能定位到一条对比记录。"""
        if not self.comparison_id and not _has_text(self.comparison_code):
            raise ValueError("请提供参数[comparison_id | comparison_code]完成操作")
        return self
