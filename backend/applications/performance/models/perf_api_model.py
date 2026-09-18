# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_api_model.py
@DateTime: 2026/9/15 10:40
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
from backend.enums import (
    AutoTestReqArgsType,
    AutoTestStepType,
    PerfApiSource,
    PerfDebugState,
)


class PerfApiModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    """
    性能测试-压测接口资产表。

    一条记录 = 一个可独立施压的 HTTP/TCP 请求 + 其断言与变量提取, 是施压热路径的唯一合法单元;
    请求类字段命名与 krun_autotest_step 逐字对齐, 使「从公共接口/HTTP步骤导入」为纯字段搬运,
    且引擎侧 RequestBuilder 消费口径无需二次映射。
    """
    api_name = fields.CharField(max_length=255, index=True, description="压测接口名称")
    api_desc = fields.CharField(max_length=2048, null=True, description="接口描述")
    api_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="接口标识代码")
    # 所属应用ID（普通字段，不设外键，业务层验证）
    api_project = fields.IntField(default=1, ge=1, index=True, description="接口所属应用")
    api_version = fields.IntField(default=1, ge=1, description="接口版本号(每次保存自增, 报告快照记录, 用于可比性判定)")

    # 仅 HTTP请求/TCP请求 两类, 且保存时强校验有且仅一个请求(与公共接口同构, 保证压测单元语义纯净)
    step_type = fields.CharEnumField(AutoTestStepType, default=AutoTestStepType.HTTP, description="请求类型")

    # 请求相关(字段结构与 krun_autotest_step 保持一致; request_url 存渲染前模板, 相对地址由执行管线按环境补齐)
    request_url = fields.CharField(max_length=2048, null=True, description="请求地址(可相对路径, 含${}占位符)")
    request_port = fields.CharField(max_length=16, null=True, description="请求端口")
    request_method = fields.CharField(max_length=16, null=True, description="请求方法(GET/POST/PUT/DELETE等)")
    # request_header、request_params 等字段, 存储格式为列表嵌套字典, 每个元素包含key、value、desc项
    request_header = fields.JSONField(null=True, description="请求头信息")
    request_params = fields.JSONField(null=True, description="请求路径参数")
    request_form_data = fields.JSONField(null=True, description="请求表单数据")
    request_form_file = fields.JSONField(null=True, description="请求文件路径")
    request_form_urlencoded = fields.JSONField(null=True, description="请求键值对数据")
    request_text = fields.TextField(null=True, description="原始请求体文本(raw/xml)")
    request_body = JSONTextField(null=True, description="请求体数据(json/表单键值)")
    # 施压目标定位: 应用 + APP节点配置名, 与用例执行/调试同一解析口径(host/port 不落库, 执行时实时解析)
    request_args_type = fields.CharEnumField(AutoTestReqArgsType, default=None, null=True, description="请求参数类型")
    request_project_id = fields.BigIntField(null=True, description="请求目标应用ID")
    request_config_name = fields.CharField(max_length=128, null=True, description="请求目标环境配置名称(APP节点)")

    # 变量与断言(元素结构与步骤容器字段一致: extract_variables含name/scope/source/expr/index; assert_validators含name/expr/source/operation/except_value)
    extract_variables = fields.JSONField(null=True, description="变量提取规则列表")
    assert_validators = fields.JSONField(null=True, description="业务断言规则列表")

    # 录入来源(单向拷贝留溯源, 不建引用关系, 功能用例变更不静默影响压测资产)
    api_source = fields.CharEnumField(PerfApiSource, default=PerfApiSource.MANUAL, description="录入来源")
    source_case_code = fields.CharField(max_length=64, null=True, description="来源用例标识(导入时写入)")
    source_step_code = fields.CharField(max_length=64, null=True, description="来源步骤标识(导入时写入)")

    debug_state = fields.CharEnumField(PerfDebugState, default=PerfDebugState.NEVER, description="最近调试结果")
    debug_time = fields.DatetimeField(default=None, null=True, description="最近调试时间")

    class Meta:
        table = "krun_perf_api"
        table_description = "性能测试-压测接口资产表"
        unique_together = (
            ("api_project", "api_name"),
        )
        indexes = (
            ("api_project", "state", "created_time"),
            ("api_code", "state"),
            ("request_project_id", "state"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        """返回接口名称。"""
        return self.api_name
