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
    AutoTestTaskPeriodicSwitch,
)


class AutoTestTaskModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    task_name = fields.CharField(max_length=255, index=True, description="任务名称")
    task_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="任务标识代码")
    task_desc = fields.CharField(max_length=2048, null=True, description="任务描述")
    task_type = fields.CharEnumField(
        AutoTestTaskType,
        default=AutoTestTaskType.AUTOTEST_API,
        index=True,
        description="任务业务类型(扫描过滤)",
    )
    task_project = fields.IntField(default=1, ge=1, index=True, description="任务所属应用")
    # case_ids、initial_variables 及未来扩展键；不含 cases_execute_config
    task_kwargs = fields.JSONField(default=dict, null=True, description="轻量扩展参数")
    # cases_execute_config字段数据格式：{case_id: {steps_execute_config, selected_dataset_names, global_env_id, env_mode, env_name, execute_count}}
    cases_execute_config = fields.JSONField(default=dict, null=True, description="根据用例执行配置")
    related_cases_env_id = fields.JSONField(default=list, null=True, description="涉及环境ID列表(由cases_execute_config汇总)")
    last_execute_time = fields.DatetimeField(default=None, null=True, description="最后执行时间")
    last_execute_state = fields.CharEnumField(AutoTestTaskStatus, default=None, null=True, description="最后执行状态")
    task_crontabs_expr = fields.CharField(max_length=255, null=True, description="Cron 触发表达式")
    task_periodic_expr = fields.CharEnumField(
        AutoTestTaskPeriodicSwitch,
        default=AutoTestTaskPeriodicSwitch.INFINITY,
        null=True,
        description="周期表达式(执行1次/执行N次)",
    )
    task_notify = fields.JSONField(default=None, null=True, description="任务执行明细反馈(预留)")
    task_notifier = fields.JSONField(default=None, null=True, description="任务执行通知人员(预留)")
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
