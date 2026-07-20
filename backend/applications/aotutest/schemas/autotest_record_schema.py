# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_record_schema
@DateTime: 2026/2/1 12:13
"""
from typing import Optional, List

from pydantic import BaseModel, Field

from backend.enums import AutoTestTaskStatus, AutoTestTaskTriggerType, AutoTestTaskType


class AutoTestApiRecordSelect(BaseModel):
    """分页查询任务执行观测记录入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["-celery_start_time", "-id"], description="排序字段")

    celery_id: Optional[str] = Field(None, max_length=255, description="调度ID")
    task_id: Optional[int] = Field(None, description="任务ID")
    task_code: Optional[str] = Field(None, max_length=64, description="任务标识")
    task_name: Optional[str] = Field(None, max_length=255, description="任务名称")
    task_type: Optional[AutoTestTaskType] = Field(None, description="任务类型")
    task_project: Optional[int] = Field(None, description="所属应用")
    trigger_type: Optional[AutoTestTaskTriggerType] = Field(None, description="触发来源")
    batch_code: Optional[str] = Field(None, max_length=64, description="批次码")
    celery_status: Optional[AutoTestTaskStatus] = Field(None, description="执行状态")
    celery_start_time_begin: Optional[str] = Field(None, max_length=32, description="开始时间起")
    celery_start_time_end: Optional[str] = Field(None, max_length=32, description="开始时间止")
    celery_end_time_begin: Optional[str] = Field(None, max_length=32, description="结束时间起")
    celery_end_time_end: Optional[str] = Field(None, max_length=32, description="结束时间止")
