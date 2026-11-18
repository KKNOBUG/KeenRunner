# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_task_model.py
@DateTime: 2025/12/28 16:15
"""
from tortoise import fields

from backend.applications.base.services.scaffold import (
    MaintainMixin,
    ReserveFields,
    ScaffoldModel,
    StateModel,
    TimestampMixin,
    UpperCharField,
    unique_identify,
)
from backend.enums import (
    AutoTestTaskStatus,
    AutoTestTaskType,
    AutoTestTaskPeriodicMode,
    AutoTestTaskExecuteMode,
)


class AutoTestTaskModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    task_name = fields.CharField(max_length=255, description="任务名称")
    task_desc = fields.CharField(max_length=2048, null=True, description="任务描述")
    task_project = fields.IntField(default=1, ge=1, index=True, description="任务所属应用")
    task_case_ids = fields.JSONField(default=list, null=True, description="任务关联用例ID列表")

    task_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="任务标识代码")
    task_execute_mode = fields.CharEnumField(AutoTestTaskExecuteMode, default=AutoTestTaskExecuteMode.PARALLEL, description="任务执行模式")
    task_type = fields.CharEnumField(AutoTestTaskType, default=AutoTestTaskType.MULTIPLE_CASE_EXECUTE, index=True, description="任务业务类型")
    # cases_execute_config 存储为Dict[str, Any]格式, 如下（执行配置只存引用键，名称/地址由执行期解析）：
    # {
    #     "env_mode": "single/multiple",
    #     "env_id": 12,              # 全局环境绑定ID
    #     "env_ids": [12, 13],       # 多环境模式涉及的环境绑定ID列表
    #     "<case_id>": {
    #         "execute_count": 1,
    #         "involve_env_ids": [12],   # 用例级涉及环境绑定ID
    #         "steps_execute_config": {
    #             "<step_id> | <step_name>_@@<op_index>": {
    #                 "env_id": 12,
    #                 "config_type": "app/file/database/redis",
    #                 "config_mode": "<环境配置逻辑标识>"
    #             }
    #         }
    #     }
    # }
    cases_execute_config = fields.JSONField(default=dict, null=True, description="用例执行配置")
    # task_schedule_expr 存储为Dict[str, Any]格式, 如下：
    # ONLY_ONCE(执行1次)模式: {"trigger_dates": ["YYYY-MM-DD HH:MM:SS", ...], "trigger_month": [1-31], "trigger_times": ["HH:MM:SS", 最多3个]}
    # UNBOUNDED(执行N次)模式: {"trigger_cycle": "daily/weekly/monthly", "trigger_weeks": [1-7, 周必输], "trigger_month": [1-31, 月必输], "trigger_times": ["HH:MM:SS", 最多3个]}
    task_schedule_expr = fields.JSONField(default=None, null=True, description="结构化定时表达式")
    task_periodic_expr = fields.CharEnumField(
        AutoTestTaskPeriodicMode,
        default=AutoTestTaskPeriodicMode.UNBOUNDED,
        null=True,
        description="周期表达式",
    )
    # task_involve_envs: 任务级涉及环境名称快照(去重)，保存时由 task_involve_env_ids 反查绑定生成，供列表展示与按环境筛选；
    # 回填前的存量任务仍为名称累积结果
    task_involve_envs = fields.JSONField(default=list, null=True, description="涉及环境名称列表")
    # task_involve_env_ids: 任务级涉及环境绑定ID列表(krun_autotest_env_bind.id)，供环境删除精确校验与筛选
    task_involve_env_ids = fields.JSONField(default=list, null=True, description="涉及环境绑定ID列表")
    last_execute_time = fields.DatetimeField(default=None, null=True, description="最后执行时间")
    last_execute_state = fields.CharEnumField(AutoTestTaskStatus, default=None, null=True, description="最后执行状态")
    # last_execute_user与updated_user语义分离：updated_user记录最后修改人(配置修改与启停调度均刷新)，
    # last_execute_user记录真实触发执行人(手动执行=点击执行者；调度触发=回退维护人(最近修改/启停者))
    last_execute_user = UpperCharField(max_length=16, default=None, null=True, description="最后执行人员")
    # task_kwargs 存储为Dict[str, Any]格式, 当前仅接受任务执行时给定的入参initial_variables(初始变量列表)，随任务调度透传给用例执行；
    task_kwargs = fields.JSONField(default=dict, null=True, description="任务扩展参数")
    task_notify = fields.JSONField(default=None, null=True, description="任务执行明细反馈")
    task_notifier = fields.JSONField(default=None, null=True, description="任务执行通知人员")
    # dataset_enabled: 启用后，绑定的各个用例在执行环节时自动收集其全部数据场景(总执行轮次=执行次数×场景数)
    dataset_enabled = fields.BooleanField(default=False, description="是否启用数据源")
    task_enabled = fields.BooleanField(default=False, index=True, description="是否启动调度")

    class Meta:
        table = "krun_autotest_task"
        table_description = "自动化测试-任务信息表"
        unique_together = (
            ("task_name", "task_project"),
        )
        ordering = ["-last_execute_time", "-updated_time"]

    def __str__(self):
        return f"AutoTestTaskModel(task_name={self.task_name}, task_project={self.task_project}, task_case_ids={self.task_case_ids}, task_code={self.task_code})"
