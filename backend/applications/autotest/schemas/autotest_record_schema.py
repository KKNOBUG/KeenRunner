# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_record_schema
@DateTime: 2026/2/1 12:13
"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, ConfigDict

from backend.applications.base.services.scaffold import UpperStr
from backend.enums import (
    AutoTestTaskStatus,
    AutoTestTaskTriggerType,
    AutoTestTaskType,
    AutoTestReportType,
)


class AutoTestRecordBase(BaseModel):
    """任务执行观测记录公共字段。"""

    model_config = ConfigDict(extra="ignore")

    task_id: Optional[int] = Field(None, description="任务ID")
    task_code: Optional[str] = Field(None, max_length=64, description="任务标识")
    task_name: Optional[str] = Field(None, max_length=255, description="任务名称")
    task_type: Optional[AutoTestTaskType] = Field(None, description="任务所属类型")
    task_project: Optional[int] = Field(None, description="任务所属应用")
    trigger_type: Optional[AutoTestTaskTriggerType] = Field(None, description="任务触发类型")
    report_type: Optional[AutoTestReportType] = Field(None, description="报告所属类型")
    batch_code: Optional[str] = Field(None, max_length=64, description="批次标识代码")
    case_ids: Optional[List[int]] = Field(None, description="用例ID列表")
    exec_snapshot: Optional[Dict[str, Any]] = Field(None, description="执行请求快照")
    task_summary: Optional[Any] = Field(None, description="任务响应快照")
    task_error: Optional[str] = Field(None, description="任务错误描述")
    celery_node: Optional[str] = Field(None, max_length=512, description="Celery节点名称")
    celery_trace_id: Optional[str] = Field(None, max_length=255, description="Celery回溯ID")
    celery_status: Optional[AutoTestTaskStatus] = Field(None, description="Celery执行状态")
    celery_start_time: Optional[datetime] = Field(None, description="Celery开始时间")
    celery_end_time: Optional[datetime] = Field(None, description="Celery结束时间")
    celery_elapsed: Optional[str] = Field(None, max_length=64, description="Celery执行耗时")


class AutoTestRecordCreate(AutoTestRecordBase):
    """创建任务执行观测记录入参。"""

    celery_id: str = Field(..., max_length=255, description="Celery调度ID")
    celery_status: AutoTestTaskStatus = Field(default=AutoTestTaskStatus.RUNNING, description="Celery执行状态")
    case_ids: Optional[List[int]] = Field(default_factory=list, description="用例ID列表")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")

    def create_dict(self) -> Dict[str, Any]:
        """
        转为落库字典，仅包含已设置字段。

        :return: 可直接传入CRUD.create的字段字典
        """
        return self.model_dump(exclude_unset=True, exclude_none=False)


class AutoTestRecordUpdate(AutoTestRecordBase):
    """更新任务执行观测记录入参（根据celery_id部分更新）。"""

    celery_id: Optional[str] = Field(None, max_length=255, description="Celery调度ID")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")

    def update_dict(self) -> Dict[str, Any]:
        """
        转为更新字典，排除未设置字段。

        :return: 可直接用于字段更新的字典
        """
        return self.model_dump(exclude_unset=True)


class AutoTestRecordSelect(BaseModel):
    """分页查询任务执行观测记录入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["-celery_start_time", "-id"], description="排序字段")

    task_id: Optional[int] = Field(None, description="任务ID")
    task_project: Optional[int] = Field(None, description="任务所属应用")
    task_code: Optional[str] = Field(None, max_length=64, description="任务标识")
    task_name: Optional[str] = Field(None, max_length=255, description="任务名称")
    task_type: Optional[AutoTestTaskType] = Field(None, description="任务所属类型")
    task_type_in: Optional[List[AutoTestTaskType]] = Field(None, description="任务所属类型列表")

    batch_code: Optional[str] = Field(None, max_length=64, description="批次标识代码")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    trigger_type: Optional[AutoTestTaskTriggerType] = Field(None, description="任务触发类型")

    celery_id: Optional[str] = Field(None, max_length=255, description="Celery调度ID")
    celery_status: Optional[AutoTestTaskStatus] = Field(None, description="Celery执行状态")
    celery_start_time_begin: Optional[str] = Field(None, max_length=32, description="Celery开始时间起")
    celery_start_time_end: Optional[str] = Field(None, max_length=32, description="Celery开始时间止")
    celery_end_time_begin: Optional[str] = Field(None, max_length=32, description="Celery结束时间起")
    celery_end_time_end: Optional[str] = Field(None, max_length=32, description="Celery结束时间止")
