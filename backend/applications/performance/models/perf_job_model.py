# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_job_model.py
@DateTime: 2026/9/17 16:40
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
from backend.enums import PerfJobStatus, PerfJobType


class PerfJobModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    """
    性能测试-数据作业表(压测的带外作业: 造数/校验/清理)。

    作业是功能用例的一次参数化批量执行: 复用 autotest 执行链跑脚本用例 N 轮,
    prepare 从执行明细提取 extract_fields 回写数据集(造数产出可直接被场景消费),
    verify 对压测产生的数据做库面断言并产出独立报告, cleanup 按 x-perf-batch 清理。
    与场景的绑定由 bind_scene_id 承载(场景执行时反查挂接), 不在场景表冗余作业清单。
    """
    job_name = fields.CharField(max_length=255, index=True, description="作业名称")
    job_desc = fields.CharField(max_length=2048, default=None, null=True, description="作业描述")
    job_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="作业标识代码")
    job_type = fields.CharEnumField(PerfJobType, description="作业类型(prepare造数/verify校验/cleanup清理)")

    # 执行的脚本用例(公共脚本/用户脚本, 具备DB/Redis/HTTP/断言能力), BigInt逻辑关联业务层校验
    quote_case_id = fields.BigIntField(index=True, description="执行的脚本用例ID")
    quote_case_code = fields.CharField(max_length=64, default=None, null=True, description="执行的脚本用例标识代码")
    quote_case_name = fields.CharField(max_length=255, default=None, null=True, description="执行的脚本用例名称(快照)")

    # 产出归属(prepare回写数据集归属接口)与校验/联动对象(verify/cleanup关联的场景), 可空
    bind_api_id = fields.BigIntField(default=None, null=True, index=True, description="产出归属压测接口ID(prepare)")
    bind_scene_id = fields.BigIntField(default=None, null=True, index=True, description="关联压测场景ID(施压链路联动)")

    loop_times = fields.IntField(default=1, ge=1, description="执行轮数(每轮产出一行数据)")
    # 可选功能参数化数据源名: 传入时执行链以该数据源喂参(轮内参数化), 与loop_times叠加
    dataset_name = fields.CharField(max_length=255, default=None, null=True, description="功能参数化数据源名称(可选)")
    # 提取列契约: 从执行明细的提取快照/终态会话变量池按名称取值, 每轮产出一行
    extract_fields = JSONTextField(default=list, description="回写数据集的提取列名列表(如orderId/token)")

    status = fields.CharEnumField(PerfJobStatus, default=PerfJobStatus.PENDING, description="执行状态(pending/running/success/failed)")
    celery_id = fields.CharField(max_length=64, default=None, null=True, index=True, description="最近一次执行的Celery任务ID")
    error_message = fields.TextField(default=None, null=True, description="失败原因")

    # 产出与追溯: prepare成功后回填; report_code为最近一轮功能执行的报告(明细追溯入口)
    result_dataset_id = fields.BigIntField(default=None, null=True, index=True, description="产出数据集ID(prepare)")
    result_rows = fields.IntField(default=0, ge=0, description="产出数据行数")
    report_code = fields.CharField(max_length=64, default=None, null=True, index=True, description="最近一次功能执行报告标识代码")
    # 与压测批次/压测报告联动: 施压链路自动触发作业时回填, 手动执行为空
    perf_batch_code = fields.CharField(max_length=64, default=None, null=True, index=True, description="联动的压测批次标识代码")
    related_report_id = fields.BigIntField(default=None, null=True, index=True, description="联动的压测报告ID")

    class Meta:
        table = "krun_perf_data_job"
        table_description = "性能测试-数据作业表"
        indexes = (
            ("job_type", "state"),
            ("status", "state"),
            ("job_code", "state"),
            ("bind_scene_id", "state"),
            ("quote_case_id", "state"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        """返回作业名称。"""
        return self.job_name
