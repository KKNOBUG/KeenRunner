# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_task_model.py
@DateTime: 2026/9/14 10:30
"""
from tortoise import fields

from backend.applications.base.services.scaffold import (
    ScaffoldModel,
    MaintainMixin,
    TimestampMixin,
    StateModel,
    ReserveFields,
    UpperCharField,
    unique_identify,
)
from backend.enums import (
    PerfLoadMode,
    PerfTaskStatus,
)


class PerfTaskModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    """
    性能测试-压测任务表(调度层): 只回答「打多狠、什么时候打」。

    施压脚本与判定口径全部来自所引用的场景(krun_perf_scene), 本表不承载任何流量结构;
    同一场景 × 梯度并发即多份任务记录, 无需复制场景, 这是压力拐点测试的基本单位。
    """
    perf_name = fields.CharField(max_length=255, description="任务名称")
    perf_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="任务标识代码")
    perf_desc = fields.CharField(max_length=2048, null=True, description="任务描述")
    # 所属应用ID（普通字段，不设外键，业务层验证）
    perf_project = fields.IntField(default=1, ge=1, index=True, description="任务所属应用")

    # 施压目标环境（复用 autotest 环境三级链: env → env_bind(应用×环境×节点类型) → env_config）
    # 只存"用哪个环境的哪个APP配置": 环境绑定可由 应用+环境名+节点类型 唯一定位, 不另存绑定ID;
    # host/port 由执行管线在 Celery 主进程实时解析后下发子进程, 不落库以免环境变更后静默漂移
    env_name = fields.CharField(max_length=128, default=None, null=True, description="施压环境名称(解析入参与展示)")
    env_config_name = fields.CharField(max_length=128, default=None, null=True, description="施压目标配置名称(APP节点)")

    # 施压脚本来源: 引用场景(逻辑关联, 业务层校验存在且启用), 执行时由管线回查场景并展开为自包含快照
    scene_id = fields.BigIntField(index=True, description="压测场景ID")
    scene_code = fields.CharField(max_length=64, index=True, description="压测场景标识代码")
    scene_name = fields.CharField(max_length=255, default=None, null=True, description="压测场景名称(展示冗余)")

    # 施压参数
    load_mode = fields.CharEnumField(PerfLoadMode, default=PerfLoadMode.FIXED, description="施压模式(fixed固定并发/stepped阶梯加压/rps吞吐模式)")
    concurrent_users = fields.IntField(default=1, ge=1, description="并发用户数(stepped为峰值参考, rps为虚拟用户池上限)")
    spawn_rate = fields.IntField(default=1, ge=1, description="每秒启动用户数")
    run_duration = fields.IntField(default=60, ge=1, description="持续时长(秒)")
    # stepped 阶梯专用字段(P1 实现, 字段先行建齐避免二次表变更)
    step_start_users = fields.IntField(default=None, ge=1, null=True, description="阶梯起始并发(stepped专用)")
    step_increment = fields.IntField(default=None, ge=1, null=True, description="阶梯每档递增并发(stepped专用)")
    step_duration = fields.IntField(default=None, ge=1, null=True, description="阶梯每档持续秒数(stepped专用)")
    step_max_users = fields.IntField(default=None, ge=1, null=True, description="阶梯峰值并发(stepped专用)")
    step_sustain_duration = fields.IntField(default=None, ge=1, null=True, description="阶梯峰值持续秒数(stepped专用)")
    # rps 吞吐模式专用字段(目标吞吐, 稳态每秒请求数; 仅 load_mode=rps 时有值)
    target_rps = fields.FloatField(default=None, null=True, description="目标吞吐RPS(rps专用, 引擎按上限并发/目标RPS做每虚拟用户节流)")

    # 最近一次执行回填(对齐 krun_autotest_task 的 last_execute_* 三件套模式)
    last_execute_state = fields.CharEnumField(PerfTaskStatus, default=None, null=True, description="最近执行状态(idle/queued/running/completed/failed/stopping/stopped)")
    last_execute_time = fields.DatetimeField(default=None, null=True, description="最近执行时间")
    last_execute_user = UpperCharField(max_length=16, default=None, null=True, description="最近执行人员")
    last_celery_id = fields.CharField(max_length=64, default=None, null=True, description="最近一次执行的Celery任务ID")
    last_execute_error = fields.TextField(default=None, null=True, description="最近一次执行失败原因")

    class Meta:
        table = "krun_perf_task"
        table_description = "性能测试-任务配置表"
        unique_together = (
            ("perf_name", "perf_project"),
        )
        indexes = (
            ("perf_project", "state"),
            ("scene_id", "state"),
            ("last_execute_state", "state"),
        )
        ordering = ["-last_execute_time", "-updated_time"]

    def __str__(self):
        """返回任务名称。"""
        return self.perf_name
