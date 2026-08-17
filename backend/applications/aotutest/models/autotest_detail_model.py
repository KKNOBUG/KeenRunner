# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_detail_model.py
@DateTime: 2025/12/28 16:15
"""
from tortoise import fields

from backend.applications.base.services.scaffold import (
    ScaffoldModel,
    MaintainMixin,
    TimestampMixin,
    StateModel,
    ReserveFields,
    JSONTextField,
)
from backend.enums import (
    AutoTestStepType,
    AutoTestLoopMode,
    AutoTestLoopErrorStrategy,
    AutoTestReqArgsType,
)


class AutoTestDetailModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    # 用例信息相关
    case_id = fields.BigIntField(index=True, description="用例ID")
    case_code = fields.CharField(max_length=64, index=True, description="用例标识代码")
    report_code = fields.CharField(max_length=64, index=True, description="报告标识代码")
    quote_case_id = fields.BigIntField(null=True, index=True, description="引用公共脚本ID")

    # 步骤明细相关(指向步骤树结构中的具体步骤)
    step_id = fields.BigIntField(description="步骤ID")
    step_no = fields.BigIntField(description="步骤序号")
    step_name = fields.CharField(max_length=255, description="步骤名称")
    step_code = fields.CharField(max_length=64, index=True, description="步骤标识代码")
    step_type = fields.CharEnumField(AutoTestStepType, description="步骤类型")
    step_state = fields.BooleanField(description="步骤执行状态(True:成功, False:失败)")
    step_st_time = fields.CharField(max_length=255, null=True, description="步骤执行开始时间")
    step_ed_time = fields.CharField(max_length=255, null=True, description="步骤执行结束时间")
    step_elapsed = fields.CharField(max_length=16, null=True, description="步骤执行消耗时间")
    step_exec_logger = fields.TextField(null=True, description="步骤执行日志")
    step_exec_except = fields.TextField(null=True, description="步骤错误描述")

    # 请求相关(实际发出的请求快照)
    request_url = fields.CharField(max_length=2048, null=True, description="请求地址")
    request_port = fields.CharField(max_length=16, null=True, description="请求端口")
    request_method = fields.CharField(max_length=16, null=True, description="请求方法(GET/POST/PUT/DELETE等)")
    # request_header、request_params、request_form_data、request_form_urlencoded、request_form_file字段, 存储格式为列表嵌套字典, 每个元素包含key、value、desc项
    request_header = fields.JSONField(null=True, description="请求头信息")
    request_params = fields.JSONField(null=True, description="请求路径参数")
    request_form_data = fields.JSONField(null=True, description="请求表单数据")
    request_form_file = fields.JSONField(null=True, description="请求文件路径")
    request_form_urlencoded = fields.JSONField(null=True, description="请求键值对数据")
    # 其他请求格式
    request_text = fields.TextField(null=True, description="请求体数据")
    request_body = JSONTextField(null=True, description="请求体数据")
    # 请求元数据字段
    request_project_id = fields.BigIntField(null=True, description="请求应用ID")
    request_args_type = fields.CharEnumField(AutoTestReqArgsType, default=None, null=True, description="请求参数类型")
    request_config_name = fields.CharField(max_length=128, null=True, description="请求环境配置名称")
    request_env_name = fields.CharField(max_length=128, null=True, description="请求环境名称")

    # 响应相关(实际得到的响应快照)
    response_cookie = fields.JSONField(null=True, description="响应信息(cookies)")
    response_header = fields.JSONField(null=True, description="响应信息(headers)")
    response_body = fields.JSONField(null=True, description="响应信息(body)")
    response_text = fields.TextField(null=True, description="响应信息(text)")
    response_elapsed = fields.CharField(max_length=16, null=True, description="响应信息(elapsed)")

    # 逻辑相关
    code = fields.TextField(null=True, description="执行代码(Python)")
    wait = fields.FloatField(ge=0, null=True, description="等待控制(正浮点数, 单位:秒)")

    # 循环控制相关
    loop_mode = fields.CharEnumField(AutoTestLoopMode, default=None, null=True, description="循环模式类型")
    loop_maximums = fields.IntField(ge=1, null=True, description="最大循环次数(正整数)")
    loop_interval = fields.FloatField(ge=0, null=True, description="每次循环间隔时间(正浮点数)")
    loop_iterable = fields.CharField(max_length=512, null=True, description="循环对象来源(变量名或可迭代对象)")
    loop_on_error = fields.CharEnumField(AutoTestLoopErrorStrategy, default=None, null=True, description="循环执行失败时的处理策略")
    loop_timeout = fields.FloatField(ge=0, null=True, description="条件循环超时时间(正浮点数, 单位:秒, 0表示不超时)")
    # loop_conditions存储为Dict[str, Any]格式, 包含condition_expr、condition_compare、condition_value项
    loop_conditions = fields.JSONField(null=True, description="条件循环判断条件")
    loop_cycles = fields.IntField(null=True, description="循环执行圈数")

    # IF分支相关
    # branch_items 存储为List[Dict[str, Any]]格式, 每个元素包含branch_type、branch_desc、branch_conditions{condition_expr,condition_compare,condition_value}项
    branch_items = fields.JSONField(null=True, description="本次命中的条件分支快照(仅命中项,不含子步骤)")
    branch_index = fields.IntField(null=True, description="所属分支序号快照(条件分支子步骤归属)")
    branch_match = fields.IntField(null=True, description="本次命中的分支序号快照(条件分支父步骤)")

    # 变量相关
    # session_variables、defined_variables 存储为List[Dict[str, Any]]格式, 每个元素包含key、value、desc项
    session_variables = fields.JSONField(null=True, description="会话变量(所有步骤的执行结果持续累积)")
    defined_variables = fields.JSONField(null=True, description="定义变量(用户自定义、引用函数的结果)")
    # extract_variables 存储为List[Dict[str, Any]]格式, 每个元素包含name、scope、source、expr、index、extract_value、success、error项
    extract_variables = fields.JSONField(null=True, description="提取变量(从请求控制器、上下文中提取、执行代码结果)")
    # assert_validators 存储为List[Dict[str, Any]]格式, 每个元素包含name、expr、operation、except_value、actual_value、success、error（及可选 source）项
    assert_validators = fields.JSONField(null=True, description="断言规则(支持对数据对象进行不同表达式的断言验证)")

    # 数据源相关
    dataset_name = fields.CharField(max_length=255, null=True, index=True, description="数据源名称")
    # dataset_snapshot 存储为List[Dict[str, Any]]格式, 每个元素包含head、body、assert_head、assert_body项
    dataset_snapshot = fields.JSONField(null=True, description="数据源快照")

    # 数据库相关
    # database_operates 存储为List[Dict[str, Any]]格式, 每个元素包含index、name、env_name、expr、project_id、project_name、variable_name(List)、config_name、database_name、desc项
    database_operates = fields.JSONField(null=True, description="数据库请求操作列表")
    database_searched = fields.BooleanField(null=True, description="数据库请求查到即止开关(多个配置时, 某一配置查询成功且存在数据时停止后续请求)")

    # Redis相关
    # redis_operates 存储为List[Dict[str, Any]]格式, 每个元素包含index、name、env_name、expr、project_id、project_name、variable_name(List)、config_name、database_name、desc项
    redis_operates = fields.JSONField(null=True, description="Redis请求操作列表")
    redis_searched = fields.BooleanField(null=True, description="Redis请求查到即止开关(多个配置时, 某一配置返回有效结果时停止后续请求)")

    # 数据比对相关
    # datagram_field_compare 存储为List[Dict[str, Any]]格式, 每个元素包含left_text、right_text、datagram_field_ordered项
    datagram_field_compare = fields.JSONField(null=True, description="报文比对配置列表")

    class Meta:
        table = "krun_autotest_details"
        table_description = "自动化测试-明细信息表"
        unique_together = (
            ("report_code", "case_code", "step_code", "loop_cycles"),
        )
        indexes = (
            ("case_id", "step_id", "step_no"),
            ("report_code", "case_id", "state"),
            ("case_id", "report_code", "state", "step_st_time"),
            ("report_code", "step_st_time"),
            ("case_id", "report_code", "step_st_time"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        """返回步骤标识代码。"""
        return self.step_code
