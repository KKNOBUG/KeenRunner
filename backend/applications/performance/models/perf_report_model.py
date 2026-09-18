# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_report_model.py
@DateTime: 2026/9/14 10:30
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
from backend.enums import PerfReportStatus, PerfRunMode, PerfStoppedReason


class PerfReportModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    """
    性能测试-执行报告表(一次施压的不可变结论)。

    字段分四组: A 归属与快照(可追溯) / B 吞吐与延迟(measured 全局口径) / C 维度聚合
    (接口/事务/准备/抽查/错误归因) / D 判定与结束原因。
    所有展示与判定只读本表快照, 不回查场景与接口: 被引用资产事后被改或被删都不影响历史结论;
    延迟类指标一律由引擎分片样本经管线合并算得(真分位), Locust 直方图值仅作交叉校验。
    引擎产物目录为 OUTPUT_PERF_DIR/{report_code}/, 由 report_code 派生, 不另存路径列。
    """
    # ---------- A. 归属与快照 ----------
    # 任务双轨关联: 表内定位用 perf_id, 跨表引用用 perf_code(对齐 report 表 case_id+case_code 模式)
    perf_id = fields.BigIntField(index=True, description="压测任务ID")
    perf_code = fields.CharField(max_length=64, index=True, description="压测任务标识代码")
    report_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="报告标识代码")
    # 批次码串联压测记录、注入的 x-perf-batch 标记、造数/校验作业与产出数据集
    batch_code = fields.CharField(max_length=64, default=None, null=True, index=True, description="压测批次标识代码")
    status = fields.CharEnumField(PerfReportStatus, description="执行状态(running/completed/failed/stopped)")
    celery_id = fields.CharField(max_length=64, default=None, null=True, index=True, description="本次执行的Celery任务ID")

    scene_id = fields.BigIntField(default=None, null=True, index=True, description="压测场景ID")
    scene_code = fields.CharField(max_length=64, default=None, null=True, description="压测场景标识代码")
    scene_name = fields.CharField(max_length=255, default=None, null=True, description="压测场景名称(快照)")
    run_mode = fields.CharEnumField(PerfRunMode, default=None, null=True, description="场景施压语义(快照)")
    # 实际施压的负载参数快照: 同场景梯度并发对比要靠它定位"这一条是多少并发打出来的"
    concurrent_users = fields.IntField(default=0, ge=0, description="实际并发用户数(快照, rps模式下为虚拟用户池上限)")
    target_rps = fields.FloatField(default=None, null=True, description="目标吞吐RPS(快照, rps模式专用, 其余模式为空)")
    run_duration = fields.IntField(default=0, ge=0, description="计划持续秒数(快照)")
    process_count = fields.IntField(default=1, ge=1, description="引擎进程数(--processes 实际值)")

    env_name = fields.CharField(max_length=128, default=None, null=True, description="施压环境名称(快照)")
    env_config_name = fields.CharField(max_length=128, default=None, null=True, description="施压目标配置名称(快照)")
    target_host = fields.CharField(max_length=512, default=None, null=True, description="解析后的施压目标host(含协议)")
    # 解析后的完整场景(接口定义+覆盖+数据集摘要), 报告页"配置快照与差异区"的唯一数据源
    config_snapshot = JSONTextField(default=None, null=True, description="场景与接口全量解析快照")
    scene_items_snapshot = JSONTextField(default=None, null=True, description="下发引擎的接口项快照(含版本)")
    api_versions = fields.JSONField(default=None, null=True, description="引用接口的版本号映射{api_code: version}")
    config_fingerprint = fields.CharField(max_length=64, default=None, null=True, description="配置指纹(可比性判定依据)")

    # ---------- B. 吞吐与延迟(measured 全局口径) ----------
    started_time = fields.DatetimeField(default=None, null=True, description="压测开始时间")
    finished_time = fields.DatetimeField(default=None, null=True, description="压测结束时间")
    duration_seconds = fields.IntField(default=0, ge=0, description="有效统计秒数(已扣预热段)")
    warmup_seconds = fields.IntField(default=0, ge=0, description="实际剔除的预热秒数")

    total_requests = fields.IntField(default=0, ge=0, description="measured总请求数")
    success_requests = fields.IntField(default=0, ge=0, description="measured成功请求数")
    fail_requests = fields.IntField(default=0, ge=0, description="measured失败请求数")
    # 百分比口径(0~100), 与熔断阈值 error_rate_threshold、SLA 指标 error_rate 同一把尺子
    error_rate = fields.FloatField(default=0.0, ge=0.0, le=100.0, description="失败率(百分比)")
    rps = fields.FloatField(default=0.0, ge=0.0, description="平均RPS(含失败)")
    success_rps = fields.FloatField(default=0.0, ge=0.0, description="平均成功RPS(业务吞吐)")
    avg_rt = fields.FloatField(default=0.0, ge=0.0, description="平均响应时间(ms)")
    min_rt = fields.FloatField(default=0.0, ge=0.0, description="最小响应时间(ms)")
    max_rt = fields.FloatField(default=0.0, ge=0.0, description="最大响应时间(ms, 非采样上限)")
    p50 = fields.FloatField(default=0.0, ge=0.0, description="P50响应时间(ms, 分位样本合并计算)")
    p90 = fields.FloatField(default=0.0, ge=0.0, description="P90响应时间(ms, 分位样本合并计算)")
    p95 = fields.FloatField(default=0.0, ge=0.0, description="P95响应时间(ms, 分位样本合并计算)")
    p99 = fields.FloatField(default=0.0, ge=0.0, description="P99响应时间(ms, 分位样本合并计算)")
    std_dev = fields.FloatField(default=0.0, ge=0.0, description="响应时间标准差(ms, Locust不产出, 由样本自算)")
    sent_kb_s = fields.FloatField(default=0.0, ge=0.0, description="平均上行KB/s")
    received_kb_s = fields.FloatField(default=0.0, ge=0.0, description="平均下行KB/s")
    # 低置信与口径提示: 施压机资源/样本不足/unique行饥饿/集合点超时/分位口径差异等, 报告头部风险条
    stat_warnings = fields.JSONField(default=None, null=True, description="统计可信度提示列表[{type,text}]")

    # ---------- C. 维度聚合 ----------
    # 接口维度: [{api_code,api_name,method,total_requests,failed_requests,error_rate,avg_rt,p90,p95,p99,rps,low_confidence}]
    api_aggregations = JSONTextField(default=None, null=True, description="接口维度聚合快照")
    # 事务维度: [{name,rounds,failed,avg_rt,p95,business_tps,fail_distribution}]
    transaction_aggregations = JSONTextField(default=None, null=True, description="事务(链路/子事务)维度聚合快照")
    # 准备段: {rounds,success_rate,avg_rt,token_pool_hit,retry_count}(完全独立于业务吞吐)
    prepare_metrics = fields.JSONField(default=None, null=True, description="准备段指标(不计业务吞吐)")
    # 抽查段: {checks,pass_rate,fail_samples[]}(不计业务吞吐, 失败单独归因)
    verify_metrics = fields.JSONField(default=None, null=True, description="正确性抽查指标(不计业务吞吐)")
    # 错误归因: [{api_code,error,occurrences,method}] + 抽查错误独立分区, 源于 stats.errors
    error_breakdown = JSONTextField(default=None, null=True, description="错误归因明细(按接口聚合TopN)")
    locust_stats = JSONTextField(default=None, null=True, description="Locust原始统计快照(交叉校验与追溯)")

    # ---------- D. 判定与结束原因 ----------
    # 逐条SLA判定: [{scope,target,api_ref,op,expect,actual,passed,severity,skipped,reason}]
    target_result = JSONTextField(default=None, null=True, description="SLA目标逐条判定结果")
    baseline_report_id = fields.BigIntField(default=None, null=True, description="对比基线报告ID")
    baseline_report_code = fields.CharField(max_length=64, default=None, null=True, description="对比基线报告标识代码")
    # 相对基线退化结论: {comparable, diff:{p95,qps,error_rate}, violations[], incomparable_reasons[]}
    baseline_diff = fields.JSONField(default=None, null=True, description="相对基线的退化对比结果")
    # 结束原因与执行状态分离: 未达标(SLA)不改执行结局, 熔断才是运行被中止
    stopped_reason = fields.CharEnumField(PerfStoppedReason, default=None, null=True, description="压测结束原因")
    error_message = fields.TextField(default=None, null=True, description="失败原因(引擎日志尾部)")

    # ---------- E. 作业与关联 ----------
    # 压测链路自动联动的数据作业(见 krun_perf_data_job): 作业自身结论查作业表, 此处只留追溯索引
    prepare_job_ids = fields.JSONField(default=None, null=True, description="施压前执行的prepare作业ID列表")
    verify_job_ids = fields.JSONField(default=None, null=True, description="施压后执行的verify作业ID列表")
    verify_report_codes = fields.JSONField(default=None, null=True, description="verify作业产出的功能报告标识列表")
    notes = fields.TextField(default=None, null=True, description="报告备注(人工补充的结论说明)")

    class Meta:
        table = "krun_perf_report"
        table_description = "性能测试-执行报告表"
        indexes = (
            ("perf_id", "perf_code"),
            ("perf_code", "state"),
            ("scene_id", "state"),
            ("batch_code", "state"),
            ("status", "state"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        """返回报告标识代码。"""
        return self.report_code
