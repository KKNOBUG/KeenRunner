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


class AutoTestApiRecordSelect(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["-celery_start_time", "-id"], description="排序字段")

    celery_id: Optional[str] = Field(None, max_length=255, description="调度ID")
    task_id: Optional[int] = Field(None, description="任务ID")
    task_name: Optional[str] = Field(None, max_length=255, description="任务名称")
    celery_node: Optional[str] = Field(None, max_length=512, description="调度节点")
    celery_status: Optional[str] = Field(None, max_length=32, description="调度状态")
    celery_scheduler: Optional[str] = Field(None, max_length=32, description="调度方式")
    celery_start_time_begin: Optional[str] = Field(None, max_length=32, description="开始时间起")
    celery_start_time_end: Optional[str] = Field(None, max_length=32, description="开始时间止")
    celery_end_time_begin: Optional[str] = Field(None, max_length=32, description="结束时间起")
    celery_end_time_end: Optional[str] = Field(None, max_length=32, description="结束时间止")
