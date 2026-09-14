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
    JSONTextField,
    unique_identify,
)
from backend.enums import (
    AutoTestReqArgsType,
    PerfLoadMode,
    PerfTaskStatus,
)


class PerfTaskModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    perf_name = fields.CharField(max_length=255, description="任务名称")
    perf_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="任务标识代码")
    perf_desc = fields.CharField(max_length=2048, null=True, description="任务描述")
    # 所属应用ID（普通字段，不设外键，业务层验证）
    perf_project = fields.IntField(default=1, ge=1, index=True, description="任务所属应用")

    # 请求定义（与 krun_autotest_step 请求字段同构，支撑「从用例步骤导入拷贝」的字段平移）
    request_url = fields.CharField(max_length=2048, null=True, description="请求地址")
    request_port = fields.CharField(max_length=16, null=True, description="请求端口")
    request_method = fields.CharField(max_length=16, null=True, description="请求方法(GET/POST/PUT/DELETE/PATCH)")
    # request_header、request_params 存储为列表嵌套字典, 每个元素包含key、value、desc项; Cookie 以请求头 Cookie 项写入, 不设独立字段
    request_header = fields.JSONField(null=True, description="请求头信息")
    request_params = fields.JSONField(null=True, description="请求路径参数")
    request_args_type = fields.CharEnumField(AutoTestReqArgsType, default=None, null=True, description="请求参数类型")
    request_text = fields.TextField(null=True, description="请求体数据(raw/xml等原始文本)")
    # request_body 以TEXT存储JSON: 对象键序保真(签名场景依赖键顺序、编辑回显保真), 对齐 step.request_body
    request_body = JSONTextField(null=True, description="请求体数据(JSON)")

    # 断言: 与 step 断言同构, 每个元素包含expr、name、source、operation、except_value项; source 复用引擎注册表取值, operation 复用 AutoTestAssertionOperation; HTTP状态码判定由 locust 层承担, 不作为断言来源
    assert_validators = fields.JSONField(null=True, description="业务断言规则(压测逐请求校验)")
    # 初始变量池: 渲染请求中 ${var} 占位符(从用例导入时随步骤拷贝), 每个元素包含key、value、desc项
    session_variables = fields.JSONField(null=True, description="初始变量池(渲染请求占位符)")

    # 参数化数据集: JSONTextField 存数组, 每个元素一行payload对象; 行序=虚拟用户轮询序(必须保序), 行内键序同样保真
    dataset_content = JSONTextField(null=True, description="参数化数据集(数组, 每元素一行payload)")
    dataset_name = fields.CharField(max_length=255, null=True, description="数据集名称")

    # 施压参数
    load_mode = fields.CharEnumField(PerfLoadMode, default=PerfLoadMode.FIXED, description="施压模式(fixed固定并发/stepped阶梯加压)")
    concurrent_users = fields.IntField(default=1, ge=1, description="并发用户数(stepped模式下为峰值参考)")
    spawn_rate = fields.IntField(default=1, ge=1, description="每秒启动用户数")
    run_duration = fields.IntField(default=60, ge=1, description="持续时长(秒)")
    # stepped 阶梯专用字段(P1 实现, 字段先行建齐避免二次表变更)
    step_start_users = fields.IntField(default=None, ge=1, null=True, description="阶梯起始并发(stepped专用)")
    step_increment = fields.IntField(default=None, ge=1, null=True, description="阶梯每档递增并发(stepped专用)")
    step_duration = fields.IntField(default=None, ge=1, null=True, description="阶梯每档持续秒数(stepped专用)")
    step_max_users = fields.IntField(default=None, ge=1, null=True, description="阶梯峰值并发(stepped专用)")
    step_sustain_duration = fields.IntField(default=None, ge=1, null=True, description="阶梯峰值持续秒数(stepped专用)")

    # 导入溯源: 记录从 autotest 步骤一次性拷贝的来源(仅快照, 无实时同步)
    quote_step_id = fields.BigIntField(default=None, null=True, index=True, description="导入来源步骤ID(krun_autotest_step.id)")

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
            ("last_execute_state", "state"),
        )
        ordering = ["-last_execute_time", "-updated_time"]

    def __str__(self):
        """返回任务名称。"""
        return self.perf_name
