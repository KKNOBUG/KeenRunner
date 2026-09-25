# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autest_report_schema
@DateTime: 2025/11/26 16:43
"""
from typing import Optional, List

from pydantic import BaseModel, Field

from backend.applications.base.services.scaffold import UpperStr
from backend.enums import AutoTestReportType, AutoTestTaskStatus


class AutoTestReportBase(BaseModel):
    """报告信息公共字段。"""

    case_st_time: Optional[str] = Field(None, max_length=32, description="用例执行开始时间")
    case_ed_time: Optional[str] = Field(None, max_length=32, description="用例执行结束时间")
    case_elapsed: Optional[str] = Field(None, max_length=16, description="用例执行消耗时间")
    case_state: Optional[bool] = Field(None, description="用例执行状态")

    step_total: Optional[int] = Field(None, ge=0, description="用例步骤数量")
    step_fail_count: Optional[int] = Field(None, ge=0, description="用例步骤失败数量")
    step_pass_count: Optional[int] = Field(None, ge=0, description="用例步骤成功数量")
    step_pass_ratio: Optional[float] = Field(None, ge=0, description="用例步骤成功率")

    task_code: Optional[str] = Field(None, max_length=64, description="任务标识代码")
    batch_code: Optional[str] = Field(None, max_length=64, description="批次标识代码")
    dataset_name: Optional[str] = Field(None, max_length=255, description="本次执行使用的数据源/场景名称")
    involve_envs: Optional[List[str]] = Field(None, description="涉及应用环境列表")
    round_no: Optional[int] = Field(None, ge=1, description="执行轮次")


class AutoTestReportCreate(AutoTestReportBase):
    """创建报告信息入参。"""

    case_id: int = Field(..., ge=1, description="用例ID")
    case_code: str = Field(..., max_length=64, description="用例标识代码")
    case_state: bool = Field(default=False, description="用例执行状态")

    step_total: int = Field(default=0, ge=0, description="用例步骤数量")
    step_fail_count: int = Field(default=0, ge=0, description="用例步骤失败数量")
    step_pass_count: int = Field(default=0, ge=0, description="用例步骤成功数量")
    step_pass_ratio: float = Field(default=0.0, ge=0, description="用例步骤成功率")

    report_type: AutoTestReportType = Field(..., description="报告所属类型")
    report_code: Optional[str] = Field(None, max_length=64, description="报告标识代码")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class AutoTestReportUpdate(AutoTestReportBase):
    """更新报告信息入参。"""

    report_id: Optional[int] = Field(None, description="报告ID")
    report_code: Optional[str] = Field(None, max_length=64, description="报告标识代码")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestReportSelect(BaseModel):
    """分页查询报告信息入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=5, description="每页数量")

    case_id: Optional[int] = Field(None, description="用例ID")
    case_code: Optional[str] = Field(None, description="用例标识代码")
    case_name: Optional[str] = Field(None, description="用例名称")
    case_state: Optional[bool] = Field(None, description="用例执行状态")

    report_id: Optional[int] = Field(None, description="报告ID")
    report_code: Optional[str] = Field(None, description="报告标识代码")
    report_type: Optional[AutoTestReportType] = Field(default=None, description="报告类型")

    batch_code: Optional[str] = Field(None, description="批次标识代码")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    step_pass_ratio: Optional[float] = Field(None, ge=0, description="用例步骤成功率")
    state: Optional[int] = Field(default=0, description="状态")

    date_from: Optional[str] = Field(None, description="用例执行开始时间起(YYYY-MM-DD或带时分秒)")
    date_to: Optional[str] = Field(None, description="用例执行结束时间止(YYYY-MM-DD或带时分秒)")


class AutoTestReportBatchSelect(BaseModel):
    """按批次聚合查询任务执行历史入参（分页粒度=批次）。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    task_code: str = Field(..., min_length=1, max_length=64, description="任务标识代码")
    state: Optional[int] = Field(default=0, description="状态")


class AutoTestReportBatchDetailSelect(BaseModel):
    """按批次标识分页查询同批次执行报告入参（报告维度，分页粒度=报告）。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["case_st_time", "id"], description="排序字段")

    batch_code: str = Field(..., min_length=1, max_length=64, description="批次标识代码")
    state: Optional[int] = Field(default=0, description="状态")


class AutoTestReportBatchScriptSelect(BaseModel):
    """按批次标识分页查询批次内脚本维度执行信息入参（脚本维度，分页粒度=脚本）。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    batch_code: str = Field(..., min_length=1, max_length=64, description="批次标识代码")
    state: Optional[int] = Field(default=0, description="状态")


class AutoTestReportScriptRoundItem(BaseModel):
    """批次内单个脚本（用例）单个执行轮次的元数据行。"""

    round_no: int = Field(..., description="执行轮次序号(1起)")
    dataset_names: List[str] = Field(default_factory=list, description="本轮次执行的数据源名称列表(未参数化执行为空)")


class AutoTestReportBatchScriptItem(BaseModel):
    """批次内单个脚本（用例）的执行信息汇总行。"""

    case_id: Optional[int] = Field(None, description="用例ID")
    case_name: str = Field(default="", description="脚本(用例)名称")
    case_execute_count: int = Field(default=0, description="用例执行次数")
    case_exec_passed: int = Field(default=0, description="用例执行成功数量")
    case_exec_failed: int = Field(default=0, description="用例执行失败数量")
    case_pass_rate: Optional[float] = Field(None, description="用例通过率")
    case_st_time: Optional[str] = Field(None, description="用例首次开始时间")
    case_ed_time: Optional[str] = Field(None, description="用例最晚结束时间")
    case_elapsed: float = Field(default=0.0, description="用例执行耗时")
    rounds: List[AutoTestReportScriptRoundItem] = Field(default_factory=list, description="执行轮次元数据")
    involve_envs: List[str] = Field(default_factory=list, description="涉及应用环境列表")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="执行人员")


class AutoTestReportScriptReportSelect(BaseModel):
    """按批次标识+用例ID+轮次分页查询脚本执行明细入参（报告维度，一行=一次场景执行）。"""

    batch_code: str = Field(..., min_length=1, max_length=64, description="批次标识代码")
    case_id: int = Field(..., ge=1, description="用例ID")
    round_no: int = Field(..., ge=1, description="执行轮次")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    state: Optional[int] = Field(default=0, description="状态")


class AutoTestReportBatchItem(BaseModel):
    """单次任务执行（一个 batch_code）的汇总行。"""

    batch_code: Optional[str] = Field(None, description="批次标识")
    task_exec_status: AutoTestTaskStatus = Field(..., description="任务执行状态")
    task_bind_script: int = Field(default=0, description="任务绑定脚本数量")
    task_exec_passed: int = Field(default=0, description="任务执行成功数量")
    task_exec_failed: int = Field(default=0, description="任务执行失败数量")
    task_pass_rate: Optional[float] = Field(None, description="任务通过率")
    task_st_time: Optional[str] = Field(None, description="任务首次开始时间")
    task_ed_time: Optional[str] = Field(None, description="任务最晚结束时间")
    task_elapsed: float = Field(default=0.0, description="任务执行耗时")
    involve_envs: List[str] = Field(default_factory=list, description="涉及应用环境列表")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="执行人员")
