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
from backend.enums.autotest_enum import AutoTestTaskScheduler


class AutoTestApiTaskCreate(BaseModel):
    task_name: str = Field(..., max_length=255, description="任务名称")
    task_desc: Optional[str] = Field(None, max_length=2048, description="任务描述")
    task_type: Optional[str] = Field(None, max_length=255, description="任务类型")
    task_project: int = Field(default=1, ge=1, description="任务所属应用")
    task_kwargs: Dict[str, Any] = Field(None, description="任务参数字典")
    task_scheduler: Optional[AutoTestTaskScheduler] = Field(None, description="任务调度状态")
    task_interval_expr: Optional[int] = Field(None, description="任务触发条件1(间隔)")
    task_datetime_expr: Optional[str] = Field(None, max_length=64, description="任务触发条件2(日期时间)")
    task_crontabs_expr: Optional[str] = Field(None, max_length=255, description="任务触发条件3(Cron)")
    task_notify: Optional[List[str]] = Field(None, description="任务执行明细反馈")
    task_notifier: Optional[List[str]] = Field(None, description="任务执行通知人员")
    task_enabled: Optional[bool] = Field(False, description="是否启动调度(True/False)")


class AutoTestApiTaskUpdate(BaseModel):
    task_id: Optional[int] = Field(None, description="任务ID")
    task_code: Optional[str] = Field(None, max_length=64, description="任务标识代码")
    task_name: Optional[str] = Field(None, max_length=255, description="任务名称")
    task_desc: Optional[str] = Field(None, max_length=2048, description="任务描述")
    task_type: Optional[str] = Field(None, max_length=255, description="任务类型")
    task_project: Optional[int] = Field(None, ge=1, description="任务所属应用")
    task_kwargs: Optional[Dict[str, Any]] = Field(None, description="任务参数字典")
    last_execute_time: Optional[str] = Field(None, max_length=32, description="最后执行时间")
    last_execute_state: Optional[AutoTestTaskScheduler] = Field(None, description="最后执行状态")
    task_scheduler: Optional[AutoTestTaskScheduler] = Field(None, description="任务调度状态")
    task_interval_expr: Optional[int] = Field(None, description="任务触发条件1(间隔)")
    task_datetime_expr: Optional[str] = Field(None, max_length=64, description="任务触发条件2(日期时间)")
    task_crontabs_expr: Optional[str] = Field(None, max_length=255, description="任务触发条件3(Cron)")
    task_notify: Optional[List[str]] = Field(None, description="任务执行明细反馈")
    task_notifier: Optional[List[str]] = Field(None, description="任务执行通知人员")
    task_enabled: Optional[bool] = Field(None, description="是否启动调度(True/False)")


class AutoTestApiTaskSelect(AutoTestApiTaskUpdate):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["-created_time"], description="排序字段")

    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    task_enabled: Optional[bool] = Field(None, description="是否启动调度(True/False)")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")
