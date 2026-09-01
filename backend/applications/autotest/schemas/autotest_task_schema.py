# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_task_schema
@DateTime: 2026/1/31 12:40
"""
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

from backend.applications.base.services.scaffold import UpperStr
from backend.enums import AutoTestTaskPeriodicMode, AutoTestTaskCycleType, AutoTestTaskStatus, AutoTestTaskType


class AutoTestTaskSchedule(BaseModel):
    """结构化定时表达式：ONLY_ONCE使用trigger_dates；UNBOUNDED使用trigger_cycle×(trigger_weeks/trigger_month)×trigger_times。"""

    trigger_dates: Optional[List[str]] = Field(None, min_length=1, description="ONLY_ONCE触发日期时间列表(YYYY-MM-DD HH:MM:SS)")
    trigger_cycle: Optional[AutoTestTaskCycleType] = Field(None, description="UNBOUNDED调度周期(日/周/月)")
    trigger_weeks: Optional[List[int]] = Field(None, min_length=1, description="UNBOUNDED星期多选(1=周一~7=周日, 周期=周时必输)")
    trigger_month: Optional[List[int]] = Field(None, min_length=1, description="UNBOUNDED日期多选(1~31, 周期=月时必输)")
    trigger_times: Optional[List[str]] = Field(None, min_length=1, max_length=3, description="UNBOUNDED触发时间点列表(HH:MM:SS, 最多3个)")


class AutoTestApiTaskSchedulePreview(BaseModel):
    """定时执行预览入参：按时效与定时表达式正推即将到来的触发日期时间。"""

    task_periodic_expr: AutoTestTaskPeriodicMode = Field(..., description="时效(执行1次/执行N次)")
    task_schedule_expr: Optional[AutoTestTaskSchedule] = Field(None, description="结构化定时表达式")


class AutoTestApiTaskCreate(BaseModel):
    """创建自动化测试任务入参。"""

    task_name: str = Field(..., max_length=255, description="任务名称")
    task_desc: Optional[str] = Field(None, max_length=2048, description="任务描述")
    task_type: Optional[AutoTestTaskType] = Field(AutoTestTaskType.AUTOTEST_API, description="任务业务类型")
    task_project: int = Field(default=1, ge=1, description="任务所属应用")
    task_kwargs: Optional[Dict[str, Any]] = Field(None, description="轻量扩展参数")
    cases_execute_config: Optional[Dict[str, Any]] = Field(None, description="根据用例ID的执行配置")
    task_schedule_expr: Optional[AutoTestTaskSchedule] = Field(None, description="结构化定时表达式")
    task_periodic_expr: Optional[AutoTestTaskPeriodicMode] = Field(AutoTestTaskPeriodicMode.UNBOUNDED, description="时效(执行1次/执行N次)")
    task_notify: Optional[List[str]] = Field(None, description="任务执行明细反馈")
    task_notifier: Optional[List[str]] = Field(None, description="任务执行通知人员")
    task_enabled: Optional[bool] = Field(False, description="是否启动调度(True/False)")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class AutoTestApiTaskUpdate(BaseModel):
    """更新自动化测试任务入参。"""

    task_id: Optional[int] = Field(None, description="任务ID")
    task_code: Optional[str] = Field(None, max_length=64, description="任务标识代码")
    task_name: Optional[str] = Field(None, max_length=255, description="任务名称")
    task_desc: Optional[str] = Field(None, max_length=2048, description="任务描述")
    task_type: Optional[AutoTestTaskType] = Field(None, description="任务业务类型")
    task_project: Optional[int] = Field(None, ge=1, description="任务所属应用")
    task_kwargs: Optional[Dict[str, Any]] = Field(None, description="轻量扩展参数")
    cases_execute_config: Optional[Dict[str, Any]] = Field(None, description="根据用例ID的执行配置")
    last_execute_time: Optional[str] = Field(None, max_length=32, description="最后执行时间")
    last_execute_state: Optional[AutoTestTaskStatus] = Field(None, description="最后执行状态")
    task_schedule_expr: Optional[AutoTestTaskSchedule] = Field(None, description="结构化定时表达式")
    task_periodic_expr: Optional[AutoTestTaskPeriodicMode] = Field(None, description="时效(执行1次/执行N次)")
    task_notify: Optional[List[str]] = Field(None, description="任务执行明细反馈")
    task_notifier: Optional[List[str]] = Field(None, description="任务执行通知人员")
    task_enabled: Optional[bool] = Field(None, description="是否启动调度(True/False)")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestApiTaskSelect(AutoTestApiTaskUpdate):
    """分页查询自动化测试任务入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["-last_execute_time"], description="排序字段")

    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    task_enabled: Optional[bool] = Field(None, description="是否启动调度(True/False)")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")
    date_from: Optional[str] = Field(None, description="最后执行时间-起")
    date_to: Optional[str] = Field(None, description="最后执行时间-止")
    env_id: Optional[int] = Field(None, ge=1, description="涉及环境ID")
