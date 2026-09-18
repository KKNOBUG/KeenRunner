# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_report_schema.py
@DateTime: 2026/9/14 11:20
"""
from typing import Optional, List

from pydantic import BaseModel, Field, model_validator

from backend.applications.base.services.scaffold import UpperStr
from backend.enums import PerfReportStatus, PerfRunMode


def _has_text(value: Optional[str]) -> bool:
    """非空字符串判断。"""
    return bool((value or "").strip())


class PerfReportSelect(BaseModel):
    """分页查询压测报告入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=100, description="每页数量")
    order: Optional[List[str]] = Field(None, description="排序字段列表")

    report_id: Optional[int] = Field(None, ge=1, description="报告ID")
    report_code: Optional[str] = Field(None, min_length=1, max_length=64, description="报告标识代码(模糊匹配)")
    perf_id: Optional[int] = Field(None, ge=1, description="压测任务ID")
    perf_code: Optional[str] = Field(None, min_length=1, max_length=64, description="压测任务标识代码(精确匹配)")
    scene_id: Optional[int] = Field(None, ge=1, description="压测场景ID(同场景梯度对比的主过滤条件)")
    scene_code: Optional[str] = Field(None, min_length=1, max_length=64, description="压测场景标识代码")
    run_mode: Optional[PerfRunMode] = Field(None, description="场景施压语义")
    batch_code: Optional[str] = Field(None, min_length=1, max_length=64, description="压测批次标识代码")
    config_fingerprint: Optional[str] = Field(None, min_length=1, max_length=64, description="配置指纹(查可对比历史记录)")
    status: Optional[PerfReportStatus] = Field(None, description="执行状态(running/completed/failed/stopped)")
    started_date_start: Optional[str] = Field(None, min_length=10, max_length=10, description="开始时间日区间起(yyyy-MM-dd)")
    started_date_end: Optional[str] = Field(None, min_length=10, max_length=10, description="开始时间日区间止(yyyy-MM-dd)")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")


class PerfReportLocate(BaseModel):
    """单报告定位入参(详情/曲线/删除共用, id或code二选一)。"""

    report_id: Optional[int] = Field(None, ge=1, description="报告ID")
    report_code: Optional[str] = Field(None, min_length=1, max_length=64, description="报告标识代码")

    @model_validator(mode="after")
    def _require_locator(self):
        """必须能定位到一条报告。"""
        if not self.report_id and not _has_text(self.report_code):
            raise ValueError("请提供参数[report_id | report_code]完成报告定位")
        return self


class PerfReportMetrics(BaseModel):
    """压测指标曲线查询入参(代理VictoriaMetrics query_range)。"""

    report_code: str = Field(..., min_length=1, max_length=64, description="报告标识代码")
    metrics: Optional[List[str]] = Field(None, description="指标名列表(缺省返回全部指标)")
    start: Optional[int] = Field(None, ge=0, description="窗口起始Unix秒级时间戳(缺省取报告起始时间)")
    end: Optional[int] = Field(None, ge=0, description="窗口结束Unix秒级时间戳(缺省取报告结束时间,执行中取当前时间)")
    step: Optional[int] = Field(None, ge=1, le=3600, description="采样步长秒数(缺省按窗口长度自适应)")

