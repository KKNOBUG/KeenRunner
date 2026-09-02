# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_task_model.py
@DateTime: 2025/12/28 16:15
"""
from tortoise import fields

from backend.applications.base.services.scaffold import (
    ScaffoldModel,
    MaintainMixin,
    TimestampMixin,
    StateModel,
    ReserveFields,
    unique_identify,
)
from backend.enums import (
    AutoTestTaskStatus,
    AutoTestTaskType,
    AutoTestTaskPeriodicMode,
    AutoTestTaskExecuteMode,
)


class AutoTestTaskModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    task_name = fields.CharField(max_length=255, index=True, description="任务名称")
    task_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="任务标识代码")
    task_desc = fields.CharField(max_length=2048, null=True, description="任务描述")
    task_type = fields.CharEnumField(
        AutoTestTaskType,
        default=AutoTestTaskType.AUTOTEST_API,
        index=True,
        description="任务业务类型(扫描过滤)")
    task_project = fields.IntField(default=1, ge=1, index=True, description="任务所属应用")
    task_execute_mode = fields.CharEnumField(
        AutoTestTaskExecuteMode,
        default=AutoTestTaskExecuteMode.PARALLEL,
        description="执行模式(并行执行/串行执行)",
    )
    task_case_ids = fields.JSONField(default=list, null=True, description="关联用例ID列表")
    # task_kwargs: 当前仅承载任务执行入参initial_variables(初始变量列表)，随调度透传给用例执行；
    task_kwargs = fields.JSONField(default=dict, null=True, description="扩展参数(当前仅承载initial_variables)")
    # cases_execute_config字段数据格式：
    # {
    #     "env_mode": "single/multiple",
    #     "env_name": "SIT1",
    #     "<case_id>": {"execute_count": 1, "involve_envs": ["SIT1", "..."], "steps_execute_config": {"<step_id|step_id_@@op_index>": {env_name, config_type, config_name, config_host, config_port, database_name}}}
    # }
    cases_execute_config = fields.JSONField(default=dict, null=True, description="根据用例执行配置")
    # task_involve_envs: 任务级涉及环境名称列表(去重)，累积自各用例的cases_execute_config.{case_id}.involve_envs，由绑定脚本后解析回填
    task_involve_envs = fields.JSONField(default=list, null=True, description="任务级涉及环境名称列表(各用例involve_envs累积)")
    last_execute_time = fields.DatetimeField(default=None, null=True, description="最后执行时间")
    last_execute_state = fields.CharEnumField(AutoTestTaskStatus, default=None, null=True, description="最后执行状态")
    # task_schedule_expr数据格式：
    # ONLY_ONCE(执行1次): {"trigger_dates": ["YYYY-MM-DD HH:MM:SS", ...]} 触发日期时间列表, 逐点触发, 全部到期后关闭调度
    # UNBOUNDED(执行N次): {"trigger_cycle": "日/周/月", "trigger_weeks": [1-7, 周必输], "trigger_month": [1-31, 月必输], "trigger_times": ["HH:MM:SS", 最多3个]}
    task_schedule_expr = fields.JSONField(default=None, null=True, description="结构化定时表达式(时效×周期×时间点)")
    task_periodic_expr = fields.CharEnumField(
        AutoTestTaskPeriodicMode,
        default=AutoTestTaskPeriodicMode.UNBOUNDED,
        null=True,
        description="周期表达式(执行1次/执行N次)",
    )
    task_notify = fields.JSONField(default=None, null=True, description="任务执行明细反馈(预留)")
    task_notifier = fields.JSONField(default=None, null=True, description="任务执行通知人员(预留)")
    # dataset_enabled为任务级全局控制开关：启用后各绑定脚本执行时自动纳入其全部数据场景(总执行轮次=执行次数×场景数)
    dataset_enabled = fields.BooleanField(default=False, description="是否启用数据源(任务级全局控制)")
    task_enabled = fields.BooleanField(default=False, index=True, description="是否启动调度(True/False)")

    class Meta:
        table = "krun_autotest_task"
        table_description = "自动化测试-任务信息表"
        unique_together = (
            ("task_name", "task_project"),
            ("task_project", "state", "updated_time"),
        )
        ordering = ["-last_execute_time", "-updated_time"]

    def __str__(self):
        """返回任务名称。"""
        return self.task_name
