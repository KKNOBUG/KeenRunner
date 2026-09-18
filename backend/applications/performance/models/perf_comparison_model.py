# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_comparison_model.py
@DateTime: 2026/9/17 20:30
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
from backend.enums import PerfComparisonMode


class PerfComparisonModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    """
    性能测试-多记录对比/汇总表(阶段三, 设计§3.7)。

    对 2~20 份已完成压测报告做横向对比(compare)或汇总合并(merge), 创建时一次性
    计算结果快照落库, 之后与报告的后续变化解耦(报告本身不可变, 快照主要锚定引用
    与结论的对应关系)。引用经 report_refs 摘要快照承载(BigInt 逻辑关联, 业务层校验),
    报告事后被软删时 detail 按 refs 复核并标注缺失, 不影响已留存结论的展示。
    """
    comparison_name = fields.CharField(max_length=255, index=True, description="对比记录名称")
    comparison_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="对比记录标识代码")
    comparison_mode = fields.CharEnumField(PerfComparisonMode, description="对比模式(compare横向对比/merge汇总合并/hybrid两者兼出)")
    report_count = fields.IntField(default=2, ge=2, description="参与报告数量")

    # 引用快照: [{report_id, report_code, scene_name, concurrent_users, status, started_time, is_baseline}]
    report_refs = JSONTextField(default=list, description="参与报告引用摘要快照(创建时锚定)")
    # 对齐参数: 当前唯一策略为按接口标识精确对齐, 显式落位便于后续扩展对齐策略
    align_params = JSONTextField(default=dict, description="对齐参数({align_by: api_code})")
    # 结果快照(结构随模式): compare→{baseline_code, metric_rows, per_report_diffs};
    # merge→{merged, api_merged, warnings}; hybrid→{compare: {...}, merge: {...}}
    result_snapshot = JSONTextField(default=None, null=True, description="对比/汇总计算结果快照")
    comparison_desc = fields.CharField(max_length=2048, default=None, null=True, description="对比说明")

    class Meta:
        table = "krun_perf_comparison"
        table_description = "性能测试-多记录对比汇总表"
        indexes = (
            ("comparison_mode", "state"),
            ("comparison_code", "state"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        """返回对比记录名称。"""
        return self.comparison_name
