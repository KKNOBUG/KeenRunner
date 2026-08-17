# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_model.py
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
    JSONTextField,
)
from backend.enums import (
    AutoTestStepType,
    AutoTestLoopMode,
    AutoTestLoopErrorStrategy,
    AutoTestReqArgsType,
)


class AutoTestStepModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    step_no = fields.IntField(default=1, ge=1, description="步骤序号")
    step_name = fields.CharField(max_length=255, description="步骤名称")
    step_desc = fields.CharField(max_length=2048, null=True, description="步骤描述")
    step_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="步骤标识代码")
    step_type = fields.CharEnumField(AutoTestStepType, description="步骤类型")

    # 用例信息ID（普通字段，不设外键，业务层验证）
    case_id = fields.BigIntField(null=True, index=True, description="所属用例")
    # 父级步骤ID（普通字段，不设外键，避免自关联导致的ORM循环引用问题）
    parent_step_id = fields.BigIntField(null=True, index=True, description="父级步骤ID")
    # 引用公共脚本ID（普通字段，不设外键，业务层验证）
    quote_case_id = fields.BigIntField(null=True, index=True, description="引用公共脚本ID")
    # 跳过/注释：执行时当作不存在该步骤（不写明细、不计入统计）；默认不跳过
    step_is_skipped = fields.BooleanField(default=False, description="是否跳过执行")

    # 请求相关
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

    # 逻辑相关
    code = fields.TextField(null=True, description="执行代码(Python)")
    wait = fields.FloatField(ge=0, null=True, description="等待控制(正浮点数, 单位:秒)")

    # 循环控制相关
    loop_mode = fields.CharEnumField(AutoTestLoopMode, default=None, null=True, description="循环模式类型")
    loop_maximums = fields.CharField(max_length=512, null=True, description="最大循环次数(正整数或变量占位符)")
    loop_interval = fields.FloatField(ge=0, null=True, description="每次循环间隔时间(正浮点数)")
    loop_iterable = fields.CharField(max_length=512, null=True, description="循环对象来源(变量名或可迭代对象)")
    loop_on_error = fields.CharEnumField(AutoTestLoopErrorStrategy, default=None, null=True, description="循环执行失败时的处理策略")
    loop_timeout = fields.FloatField(ge=0, null=True, description="条件循环超时时间(正浮点数, 单位:秒, 0表示不超时)")
    # loop_conditions 存储为Dict[str, Any]格式, 包含condition_expr、condition_compare、condition_value项
    loop_conditions = fields.JSONField(null=True, description="条件循环判断条件")

    # IF分支相关
    # branch_items 存储为List[Dict[str, Any]]格式, 每个元素包含branch_type、branch_desc、branch_conditions{condition_expr,condition_compare,condition_value}项
    branch_items = fields.JSONField(null=True, description="条件分支列表(仅条件分支步骤使用, 存储分支元数据)")
    branch_index = fields.IntField(null=True, description="所属分支序号(条件分支子步骤归属哪个分支)")

    # 变量、断言和逻辑处理
    # session_variables、defined_variables 存储为List[Dict[str, Any]]格式, 每个元素包含key、value、desc项
    session_variables = fields.JSONField(null=True, description="会话变量(所有步骤的执行结果持续累积)")
    defined_variables = fields.JSONField(null=True, description="定义变量(用户自定义、引用函数的结果)")
    # extract_variables 存储为List[Dict[str, Any]]格式, 每个元素包含name、scope、source、expr、index项
    extract_variables = fields.JSONField(null=True, description="提取变量(从请求控制器、上下文中提取、执行代码结果)")
    # assert_validators 存储为List[Dict[str, Any]]格式, 每个元素包含expr、name、source、operation、except_value项
    assert_validators = fields.JSONField(null=True, description="断言规则(支持对数据对象进行不同表达式的断言验证)")

    # 数据源相关
    data_source_id = fields.BigIntField(null=True, index=True, description="数据源ID")
    data_source_name = fields.CharField(max_length=2048, null=True, description="数据源名称")
    data_source_desc = fields.CharField(max_length=2048, null=True, description="数据源描述")

    # 数据库相关
    # database_operates 存储为List[Dict[str, Any]]格式, 每个元素包含name、desc、project_name、config_name、database_name、expr、variable_name项
    database_operates = fields.JSONField(null=True, description="数据库请求操作列表")
    database_searched = fields.BooleanField(null=True, description="数据库请求查到即止开关(多个配置时, 某一配置查询成功且存在数据时停止后续请求)")

    # Redis相关
    # redis_operates 存储为List[Dict[str, Any]]格式, 每个元素包含name、desc、project_id、project_name、config_name、database_name、expr、variable_name项
    redis_operates = fields.JSONField(null=True, description="Redis请求操作列表")
    redis_searched = fields.BooleanField(null=True, description="Redis请求查到即止开关(多个配置时, 某一配置返回有效结果时停止后续请求)")

    # 数据比对相关
    # datagram_field_compare 存储为List[Dict[str, Any]]格式, 每个元素包含left_text、right_text、datagram_field_ordered项
    datagram_field_compare = fields.JSONField(null=True, description="报文比对配置列表")

    class Meta:
        table = "krun_autotest_step"
        table_description = "自动化测试-步骤明细表"
        unique_together = (
            ("case_id", "step_no", "step_code"),
        )
        indexes = (
            ("case_id", "parent_step_id", "step_no"),
            ("case_id", "state", "step_no"),
            ("case_id", "step_type"),
            ("step_name", "state"),
        )
        ordering = ["case_id", "step_no"]

    def __str__(self):
        """返回步骤名称。"""
        return self.step_name
