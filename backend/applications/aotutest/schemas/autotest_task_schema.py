# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_task_schema
@DateTime: 2026/1/31 12:40
"""
from typing import Optional, List, Dict, Any, Union

from pydantic import BaseModel, Field

from backend.applications.base.services.scaffold import UpperStr
from backend.enums import AutoTestTaskPeriodicSwitch, AutoTestTaskStatus, AutoTestTaskType


class AutoTestApiTaskCreate(BaseModel):
    """创建自动化测试任务入参。"""

    task_name: str = Field(..., max_length=255, description="任务名称")
    task_desc: Optional[str] = Field(None, max_length=2048, description="任务描述")
    task_type: Optional[AutoTestTaskType] = Field(
        AutoTestTaskType.AUTOTEST_API,
        description="任务业务类型",
    )
    task_project: int = Field(default=1, ge=1, description="任务所属应用")
    task_kwargs: Optional[Dict[str, Any]] = Field(None, description="轻量扩展参数")
    cases_execute_config: Optional[Dict[str, Any]] = Field(None, description="根据用例ID的执行配置")
    task_crontabs_expr: Optional[str] = Field(None, max_length=255, description="Cron 触发表达式")
    task_periodic_expr: Optional[AutoTestTaskPeriodicSwitch] = Field(AutoTestTaskPeriodicSwitch.INFINITY, description="周期表达式(执行1次/执行N次)")
    task_notify: Optional[List[str]] = Field(None, description="任务执行明细反馈")
    task_notifier: Optional[List[str]] = Field(None, description="任务执行通知人员")
    task_enabled: Optional[bool] = Field(False, description="是否启动调度(True/False)")
    created_user: Optional[Union[UpperStr, str]] = Field(None, max_length=16, description="创建人员")


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
    task_crontabs_expr: Optional[str] = Field(None, max_length=255, description="Cron 触发表达式")
    task_periodic_expr: Optional[AutoTestTaskPeriodicSwitch] = Field(None, description="周期表达式(执行1次/执行N次)")
    task_notify: Optional[List[str]] = Field(None, description="任务执行明细反馈")
    task_notifier: Optional[List[str]] = Field(None, description="任务执行通知人员")
    task_enabled: Optional[bool] = Field(None, description="是否启动调度(True/False)")
    updated_user: Optional[Union[UpperStr, str]] = Field(None, max_length=16, description="更新人员")


class AutoTestApiTaskSelect(AutoTestApiTaskUpdate):
    """分页查询自动化测试任务入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["-last_execute_time"], description="排序字段")

    created_user: Optional[Union[UpperStr, str]] = Field(None, max_length=16, description="创建人员")
    task_enabled: Optional[bool] = Field(None, description="是否启动调度(True/False)")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")
    date_from: Optional[str] = Field(None, description="最后执行时间-起")
    date_to: Optional[str] = Field(None, description="最后执行时间-止")
    env_id: Optional[int] = Field(None, ge=1, description="涉及环境ID")
