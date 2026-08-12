# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autest_report_schema
@DateTime: 2025/11/26 16:43
"""
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, Field

from backend.applications.base.services.scaffold import UpperStr
from backend.enums import AutoTestReportType, AutoTestTaskStatus


class AutoTestApiReportBase(BaseModel):
    """测试报告公共字段。"""

    case_st_time: Optional[str] = Field(None, max_length=32, description="用例执行开始时间")
    case_ed_time: Optional[str] = Field(None, max_length=32, description="用例执行结束时间")
    case_elapsed: Optional[str] = Field(None, max_length=16, description="用例执行消耗时间")
    case_state: Optional[bool] = Field(None, description="用例执行状态(True:成功, False:失败)")

    step_total: Optional[int] = Field(None, ge=0, description="用例步骤数量(含所有子级步骤)")
    step_fail_count: Optional[int] = Field(None, ge=0, description="用例步骤失败数量(含所有子级步骤)")
    step_pass_count: Optional[int] = Field(None, ge=0, description="用例步骤成功数量(含所有子级步骤)")
    step_pass_ratio: Optional[float] = Field(None, ge=0, description="用例步骤成功率(含所有子级步骤)")

    task_code: Optional[str] = Field(None, max_length=64, description="任务标识代码")
    batch_code: Optional[str] = Field(None, max_length=64, description="批次标识代码")
    dataset_name: Optional[str] = Field(None, max_length=255, description="本次执行使用的数据集/场景名称(参数化)")


class AutoTestApiReportCreate(AutoTestApiReportBase):
    """创建测试报告入参。"""

    case_id: int = Field(..., ge=1, description="用例ID")
    case_code: str = Field(..., max_length=64, description="用例标识代码")
    case_state: bool = Field(default=False, description="用例执行状态(True:成功, False:失败)")

    step_total: int = Field(default=0, ge=0, description="用例步骤数量(含所有子级步骤)")
    step_fail_count: int = Field(default=0, ge=0, description="用例步骤失败数量(含所有子级步骤)")
    step_pass_count: int = Field(default=0, ge=0, description="用例步骤成功数量(含所有子级步骤)")
    step_pass_ratio: float = Field(default=0.0, ge=0, description="用例步骤成功率(含所有子级步骤)")

    report_type: AutoTestReportType = Field(..., description="报告类型")
    report_code: Optional[str] = Field(
        None,
        max_length=64,
        description="报告标识代码；执行引擎落库时传入与明细一致的预生成code，未传时由ORM默认生成",
    )
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class AutoTestApiReportUpdate(AutoTestApiReportBase):
    """更新测试报告入参。"""

    report_id: Optional[int] = Field(None, description="报告ID")
    report_code: Optional[str] = Field(None, max_length=64, description="报告标识代码")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestApiReportSelect(BaseModel):
    """分页查询测试报告入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=5, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["-updated_time"], description="排序字段")

    case_id: Optional[int] = Field(None, description="用例ID")
    case_code: Optional[str] = Field(None, description="用例标识代码")
    case_name: Optional[str] = Field(None, description="用例名称（模糊匹配）")
    report_id: Optional[int] = Field(None, description="报告ID")
    report_code: Optional[str] = Field(None, description="报告标识代码")
    report_type: Optional[AutoTestReportType] = Field(default=None, description="报告类型（不传则不按类型过滤，可查同步/异步/调试/定时）")
    task_code: Optional[str] = Field(None, description="任务标识代码（未传则仅查 task_code 为空的报告）")
    batch_code: Optional[str] = Field(None, description="批次标识代码")
    exclude_task_code: Optional[bool] = Field(None, description="是否排除带任务标识的报告")

    case_state: Optional[bool] = Field(None, description="用例执行状态(True:成功, False:失败)")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    step_pass_ratio: Optional[float] = Field(None, ge=0, description="用例步骤成功率(含所有子级步骤)")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")

    date_from: Optional[str] = Field(None, description="执行开始时间-起(YYYY-MM-DD或带时分秒)")
    date_to: Optional[str] = Field(None, description="执行开始时间-止(YYYY-MM-DD或带时分秒)")


class AutoTestApiReportBatchSelect(BaseModel):
    """按批次聚合查询任务执行历史入参（分页粒度=批次）。"""

    page: int = Field(default=1, ge=1, description="页码（按批次）")
    page_size: int = Field(default=10, ge=1, le=200, description="每页批次数")
    task_code: str = Field(..., min_length=1, max_length=64, description="任务标识代码（必填）")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")
    include_reports: bool = Field(default=True, description="是否在批次行中附带报告明细列表")


class AutoTestApiReportBatchItem(BaseModel):
    """单次任务执行（一个 batch_code）的汇总行。"""

    batch_code: Optional[str] = Field(None, description="批次标识；空表示无 batch_code 的单报孤立行")
    execute_result: AutoTestTaskStatus = Field(..., description="批次执行结果(成功/失败/部分成功)")
    pass_rate: Optional[float] = Field(None, description="通过率(0-100)，成功报告数/总报告数")
    pass_count: int = Field(default=0, description="成功报告数")
    report_count: int = Field(default=0, description="本批次报告总数")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="执行人员")
    execute_time: Optional[str] = Field(None, description="执行时间（本批次最早 case_st_time）")
    elapsed_seconds: float = Field(default=0.0, description="本批次耗时合计（秒）")
    reports: List[Dict[str, Any]] = Field(default_factory=list, description="本批次报告明细（含 case_name）")
