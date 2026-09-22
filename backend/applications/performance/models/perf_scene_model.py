# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_scene_model.py
@DateTime: 2026/9/15 15:20
"""
from tortoise import fields

from backend.applications.base.services.scaffold import (
    ScaffoldModel,
    MaintainMixin,
    TimestampMixin,
    StateModel,
    ReserveFields,
    JSONTextField,
    unique_identify,
)
from backend.enums import PerfAssertMode, PerfRunMode


class PerfSceneModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    """
    性能测试-压测场景表(编排层)。

    场景回答「打什么、怎么打」: 接口项组合(角色/权重/思考时间/事务/数据集策略)、业务链路阶段、
    判定口径(SLA目标/基线策略/熔断/warmup); 「打多狠、什么时候打」由 krun_perf_load_preset 承载。
    本表不直接执行, 故不建 last_execute_* 三件套(与负载预设表重复即分叉源)。
    事务不单独建字段: 由 scene_items[].transaction 与 journey.phases 派生, 避免两处维护互相漂移。
    """
    scene_name = fields.CharField(max_length=255, index=True, description="场景名称")
    scene_desc = fields.CharField(max_length=2048, null=True, description="场景描述")
    scene_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="场景标识代码")
    # 所属应用ID（普通字段，不设外键，业务层验证）
    scene_project = fields.IntField(default=1, ge=1, index=True, description="场景所属应用")
    run_mode = fields.CharEnumField(PerfRunMode, default=PerfRunMode.SINGLE, description="施压语义(single单接口/mixed混合流量/journey业务链路)")

    # 接口项数组, 元素结构见 schemas/perf_scene_schema.PerfSceneItem(引用压测接口资产, 保存时校验存在且启用)
    scene_items = JSONTextField(default=list, description="压测接口项列表(角色/权重/思考时间/事务/数据集策略)")
    # 链路定义, 结构见 schemas/perf_scene_schema.PerfJourney; run_mode=journey 时必填, phases 只引用 item 的 seq
    journey = JSONTextField(default=None, null=True, description="业务链路定义(阶段/集合点/串并行/失败即停)")

    # 判定与口径: 三层分离, 目标失败(SLA)≠运行失败(熔断), 基线退化是趋势结论
    perf_targets = JSONTextField(default=None, null=True, description="SLA绝对目标列表, 元素见 schemas/perf_scene_schema.PerfTargetItem")
    # 基线为钉住的历史报告; 报告只读快照不回查场景, 故基线定位信息随场景一并冗余
    baseline_report_id = fields.BigIntField(default=None, null=True, description="基线报告ID(相对基线退化的比较对象)")
    baseline_report_code = fields.CharField(max_length=64, default=None, null=True, description="基线报告标识代码")
    baseline_policy = fields.JSONField(default=None, null=True, description="基线退化阈值{p95_degrade_pct,qps_degrade_pct,error_rate_increase}")
    # 加压段剔除时长: 0=不剔除; 空=执行时按 ramp 时长派生(默认 concurrent_users/spawn_rate)
    warmup_seconds = fields.IntField(default=None, ge=0, null=True, description="预热剔除秒数")
    # 运行中熔断错误率阈值(%), 0或空=不熔断; 与SLA的error_rate目标互不影响
    error_rate_threshold = fields.FloatField(default=None, ge=0.0, le=100.0, null=True, description="熔断错误率阈值(百分比)")
    assert_mode = fields.CharEnumField(PerfAssertMode, default=PerfAssertMode.ALL, description="断言执行口径(all逐请求/sample_ratio抽样)")
    sample_ratio = fields.FloatField(default=100.0, ge=0.0, le=100.0, description="断言采样比例(百分比, assert_mode=sample_ratio时生效)")
    # 压测标记头: 开启后所有出站请求注入 x-perf-batch, 供被测端做数据隔离与清理
    inject_perf_tag = fields.BooleanField(default=True, description="是否注入x-perf-batch压测标记头")

    class Meta:
        table = "krun_perf_scene"
        table_description = "性能测试-压测场景表"
        unique_together = (
            ("scene_project", "scene_name"),
        )
        indexes = (
            ("scene_project", "state", "created_time"),
            ("scene_code", "state"),
            ("run_mode", "state"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        """返回场景名称。"""
        return self.scene_name
