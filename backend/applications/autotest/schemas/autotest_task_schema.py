# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_task_schema
@DateTime: 2026/1/31 12:40
"""
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.applications.autotest.schemas.autotest_step_schema import StepsExecuteConfigBase
from backend.applications.base.services.scaffold import UpperStr
from backend.enums import (
    AutoTestTaskPeriodicMode,
    AutoTestTaskCycleType,
    AutoTestTaskStatus,
    AutoTestTaskType,
    AutoTestTaskExecuteMode,
    AutoTestEnvMode,
)


class AutoTestTaskSchedule(BaseModel):
    """
    结构化定时表达式：
    ONLY_ONCE(执行1次)模式: {"trigger_dates": ["YYYY-MM-DD HH:MM:SS", ...], "trigger_month": [1-31], "trigger_times": ["HH:MM:SS", 最多3个]}
    UNBOUNDED(执行N次)模式: {"trigger_cycle": "daily/weekly/monthly", "trigger_weeks": [1-7, 周必输], "trigger_month": [1-31, 月必输], "trigger_times": ["HH:MM:SS", 最多3个]}
    """

    trigger_dates: Optional[List[str]] = Field(None, min_length=1, description="触发日期时间列表(YYYY-MM-DD HH:MM:SS)")
    trigger_cycle: Optional[AutoTestTaskCycleType] = Field(None, description="调度周期(daily/weekly/monthly)")
    trigger_weeks: Optional[List[int]] = Field(None, min_length=1, description="星期多选(1=周一~7=周日, 周期=周时必输)")
    trigger_month: Optional[List[int]] = Field(None, min_length=1, description="月内日期多选(1~31, 周期=月时必输)")
    trigger_times: Optional[List[str]] = Field(None, min_length=1, max_length=3, description="触发时间点列表(HH:MM:SS, 最多3个)：两种模式必输")


class AutoTestApiTaskSchedulePreview(BaseModel):
    """定时执行预览入参：按时效与定时表达式正推即将到来的触发日期时间。"""

    task_periodic_expr: AutoTestTaskPeriodicMode = Field(..., description="周期表达式(执行1次/执行N次)")
    task_schedule_expr: Optional[AutoTestTaskSchedule] = Field(None, description="结构化定时表达式(时效×周期×时间点)")


class AutoTestTaskCaseExecuteConfig(BaseModel):
    """用例级执行配置：cases_execute_config中case_id键对应对象结构。"""

    execute_count: int = Field(1, ge=1, le=9999, description="执行次数")
    involve_envs: List[str] = Field(default_factory=list, description="涉及环境名称列表(用例级&去重)")
    # KEY：step_id 优先，否则@@step_name；DB/Redis多操作再拼_@@{index}
    steps_execute_config: Dict[str, StepsExecuteConfigBase] = Field(default_factory=dict, description="步骤执行环境配置")


class AutoTestTaskCasesExecuteConfig(BaseModel):
    """任务级用例执行配置：顶层环境配置(env_mode/env_name) + 动态case_id键(指向AutoTestTaskCaseExecuteConfig)。"""

    model_config = ConfigDict(extra="allow")

    env_mode: AutoTestEnvMode = Field(AutoTestEnvMode.SINGLE, description="环境模式(单环境/多环境)")
    env_name: Optional[str] = Field(None, max_length=128, description="全局环境名称")

    @model_validator(mode="after")
    def validate_case_configs(self):
        """校验动态case_id键对应对象必须符合用例级执行配置结构。"""
        extra = getattr(self, "__pydantic_extra__", None) or {}
        for case_key, case_cfg in extra.items():
            if not str(case_key).isdigit():
                raise ValueError(f"cases_execute_config存在非法键[{case_key}]，应为用例ID")
            AutoTestTaskCaseExecuteConfig.model_validate(case_cfg)
        return self


class AutoTestApiTaskCreate(BaseModel):
    """创建自动化测试任务入参。"""

    task_name: str = Field(..., max_length=255, description="任务名称")
    task_desc: Optional[str] = Field(None, max_length=2048, description="任务描述")
    task_type: Optional[AutoTestTaskType] = Field(AutoTestTaskType.AUTOTEST_API, description="任务业务类型(扫描过滤)")
    task_project: int = Field(default=1, ge=1, description="任务所属应用")
    task_execute_mode: AutoTestTaskExecuteMode = Field(AutoTestTaskExecuteMode.PARALLEL, description="执行模式(并行执行/串行执行)")
    task_case_ids: Optional[List[int]] = Field(None, description="关联用例ID列表")
    task_kwargs: Optional[Dict[str, Any]] = Field(None, description="扩展参数(当前仅承载initial_variables)")
    cases_execute_config: Optional[AutoTestTaskCasesExecuteConfig] = Field(None, description="用例执行配置")
    task_schedule_expr: Optional[AutoTestTaskSchedule] = Field(None, description="结构化定时表达式(时效×周期×时间点)")
    task_periodic_expr: Optional[AutoTestTaskPeriodicMode] = Field(AutoTestTaskPeriodicMode.UNBOUNDED, description="周期表达式(执行1次/执行N次)")
    task_notify: Optional[List[str]] = Field(None, description="任务执行明细反馈(预留)")
    task_notifier: Optional[List[str]] = Field(None, description="任务执行通知人员(预留)")
    task_enabled: Optional[bool] = Field(False, description="是否启动调度(True/False)")
    dataset_enabled: bool = Field(False, description="是否启用数据源(任务级全局控制)")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class AutoTestApiTaskUpdate(BaseModel):
    """更新自动化测试任务入参。"""

    task_id: Optional[int] = Field(None, description="任务ID")
    task_code: Optional[str] = Field(None, max_length=64, description="任务标识代码")
    task_name: Optional[str] = Field(None, max_length=255, description="任务名称")
    task_desc: Optional[str] = Field(None, max_length=2048, description="任务描述")
    task_type: Optional[AutoTestTaskType] = Field(None, description="任务业务类型(扫描过滤)")
    task_project: Optional[int] = Field(None, ge=1, description="任务所属应用")
    task_execute_mode: Optional[AutoTestTaskExecuteMode] = Field(None, description="执行模式(并行执行/串行执行)")
    task_case_ids: Optional[List[int]] = Field(None, description="关联用例ID列表")
    task_kwargs: Optional[Dict[str, Any]] = Field(None, description="扩展参数(当前仅承载initial_variables)")
    cases_execute_config: Optional[AutoTestTaskCasesExecuteConfig] = Field(None, description="用例执行配置")
    last_execute_time: Optional[str] = Field(None, max_length=32, description="最后执行时间")
    last_execute_state: Optional[AutoTestTaskStatus] = Field(None, description="最后执行状态")
    task_schedule_expr: Optional[AutoTestTaskSchedule] = Field(None, description="结构化定时表达式(时效×周期×时间点)")
    task_periodic_expr: Optional[AutoTestTaskPeriodicMode] = Field(None, description="周期表达式(执行1次/执行N次)")
    task_notify: Optional[List[str]] = Field(None, description="任务执行明细反馈(预留)")
    task_notifier: Optional[List[str]] = Field(None, description="任务执行通知人员(预留)")
    task_enabled: Optional[bool] = Field(None, description="是否启动调度(True/False)")
    dataset_enabled: Optional[bool] = Field(None, description="是否启用数据源(任务级全局控制)")
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
    env_name: Optional[str] = Field(None, max_length=64, description="涉及环境名称")
