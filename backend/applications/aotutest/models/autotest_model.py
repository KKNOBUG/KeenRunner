import datetime
import uuid
from enum import Enum

from tortoise import fields
from backend.applications.base.services.scaffold import (
    ScaffoldModel,
    MaintainMixin,
    TimestampMixin,
    StateModel
)


class StepType(str, Enum):
    """请求参数类型枚举"""
    HTTP = "HTTP/HTTPS协议网络请求"
    TCP = "TCP协议网络请求"
    SQL = "SQL语句执行"
    PYTHON = "执行代码(Python)"
    JAVA = "执行代码(Java)"
    PRE_PYTHON = "执行前置代码(Python)"
    POST_PYTHON = "执行后置代码(Python)"
    PRE_JAVA = "执行前置代码(Java)"
    POST_JAVA = "执行后置代码(Java)"
    CONDITION = "条件分支"
    WAIT = "等待控制"
    LOOP = "循环结构"
    ASSERT = "断言表达式"
    QUOTE = "引用测试用例"


def generate_timestamp() -> str:
    timestamp = int(datetime.datetime.now().timestamp())
    uuid4_str = uuid.uuid4().hex.upper()
    return f"{timestamp}-{uuid4_str}"


class AutoTestApiCaseInfo(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel):
    """
    测试用例信息表
    """
    case_name = fields.CharField(max_length=255, index=True, description="用例名称")
    case_desc = fields.CharField(max_length=2048, null=True, description="用例描述")
    case_tags = fields.CharField(max_length=255, null=True, description="用例标签")
    case_code = fields.CharField(max_length=64, default=generate_timestamp, unique=True, description="用例标识")
    case_version = fields.IntField(default=1, ge=1, description="用例版本")
    case_project = fields.IntField(default=1, ge=1, index=True, description="用例所属项目")

    class Meta:
        table = "krun_autotest_api_case"
        table_description = "自动化测试-用例信息表"
        # 同一项目下，用例名称唯一，避免重复
        unique_together = (
            ("case_name", "case_project", "created_user"),
        )
        indexes = (
            ("case_project", "state"),
            ("case_project", "case_name"),
            ("case_name", "state"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        return self.case_name


class AutoTestApiStepInfo(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel):
    """
    测试步骤明细表
    存储步骤的详细配置信息，使用普通字段而非外键，降低数据库复杂度
    关联关系在业务层进行验证和处理
    """
    step_no = fields.IntField(default=1, ge=1, description="步骤明细序号")
    step_name = fields.CharField(max_length=255, description="步骤明细名称")
    step_desc = fields.CharField(max_length=2048, null=True, description="步骤明细描述")
    step_code = fields.CharField(max_length=64, default=generate_timestamp, unique=True, description="步骤明细代码")
    step_type = fields.CharEnumField(StepType, description="步骤明细类型")

    # 用例信息ID（普通字段，不设外键，业务层验证）
    case_id = fields.BigIntField(index=True, description="步骤所属用例")
    # 父级步骤ID（普通字段，不设外键，避免自关联导致的ORM循环引用问题）
    parent_step_id = fields.BigIntField(null=True, index=True, description="父级步骤ID，允许拥有子级步骤明细")
    # 引用用例信息ID（普通字段，不设外键，业务层验证）
    quote_case_id = fields.BigIntField(null=True, index=True, description="引用用例信息ID，用于引用其他用例的步骤")

    # 请求相关字段
    request_url = fields.CharField(max_length=2048, null=True, description="请求地址")
    request_port = fields.CharField(max_length=16, null=True, description="请求端口")
    request_method = fields.CharField(max_length=16, null=True, description="请求方法（GET/POST/PUT/DELETE等）")

    # 参数相关字段（存储复杂数据结构）
    request_header = fields.JSONField(null=True, description="请求头，JSON格式")
    request_text = fields.TextField(null=True, description="请求体，Text格式")
    request_body = fields.JSONField(null=True, description="请求体，JSON格式")
    request_params = fields.TextField(null=True, description="请求参数，Text格式")
    request_form_data = fields.JSONField(null=True, description="请求表单，JSON格式")
    request_form_file = fields.JSONField(null=True, description="请求文件路径")
    request_form_urlencoded = fields.JSONField(null=True, description="请求键值对，JSON格式")
    # 逻辑相关
    wait = fields.IntField(ge=0, null=True, description="等待时间，正整数（毫秒），非必输")
    code = fields.TextField(null=True, description="后置操作代码，Text类型")

    # 前后置相关
    pre_wait = fields.IntField(ge=0, null=True, description="前置等待时间，正整数（毫秒），非必输")
    post_wait = fields.IntField(ge=0, null=True, description="后置等待时间，正整数（毫秒），非必输")
    pre_code = fields.TextField(null=True, description="前置操作代码，Text类型")
    post_code = fields.TextField(null=True, description="后置操作代码，Text类型")

    # 变量、断言和逻辑处理
    # 自定义的变量和调用函数的变量
    session_variables = fields.JSONField(null=True, description="会话变量(包含提取变量，以及前后code设置的变量)")
    defined_variables = fields.JSONField(null=True, description="定义变量(自定义变量，如编写指定值或引用随机函数)")
    # 提取和前后置操作产出的变量
    # 参数提取表达式模板：变量名称、提取来源、表达式、提取值、提取结果、错误信息
    extract_variables = fields.JSONField(null=True, description="提取变量(从上下午中提取参数)")
    # 断言表达式模板：断言名称，断言对象、断言路径、结果值、断言方式、期望值、断言结果、错误信息
    validators = fields.JSONField(null=True, description="断言规则，JSON格式")
    max_cycles = fields.IntField(ge=1, null=True, description="循环次数")
    conditions = fields.TextField(null=True, description="判断条件")

    class Meta:
        table = "krun_autotest_api_step"
        table_description = "自动化测试-步骤明细表"
        # 重要约束：同一用例内，步骤序号必须唯一（保证排序不冲突）
        unique_together = (
            ("case_id", "step_no"),
        )
        indexes = (
            ("case_id", "parent_step_id", "step_no"),
            ("case_id", "state"),
            ("case_id", "step_type"),
            ("step_name", "state"),
            ("parent_step_id",),
            ("quote_case_id",),
        )
        ordering = ["case_id", "step_no"]

    def __str__(self):
        return self.step_name


class AutoTestApiReportInfo(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel):
    """
    测试报告信息表
    """
    case_id = fields.BigIntField(index=True, description="用例ID")
    case_code = fields.CharField(max_length=64, description="用例代码")
    case_name = fields.CharField(max_length=255, index=True, description="用例名称")
    case_st_time = fields.CharField(max_length=32, null=True, description="用例执行开始时间")
    case_ed_time = fields.CharField(max_length=32, null=True, description="用例执行结束时间")
    case_elapsed = fields.CharField(max_length=16, null=True, description="用例执行消耗时间")
    case_state = fields.BooleanField(description="用例执行状态")
    step_total = fields.IntField(ge=0, description="用例步骤数量(含子级步骤)")
    step_fill_count = fields.IntField(ge=0, description="用例步骤失败数量")
    step_pass_count = fields.IntField(ge=0, description="用例步骤成功数量")
    step_pass_ratio = fields.FloatField(ge=0.0, description="用例步骤成功率")
    report_code = fields.CharField(max_length=64, default=generate_timestamp, unique=True, description="报告标识")

    class Meta:
        table = "krun_autotest_api_report"
        table_description = "自动化测试-测试报告表"
        indexes = (
            ("case_id", "case_code"),
            ("case_id", "case_name", "created_user"),
            ("case_name", "case_state"),
            ("case_name", "state"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        return self.case_name


class AutoTestApiDetailsInfo(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel):
    """
    测试步骤结果表
    """
    # 报告批次号
    report_code = fields.CharField(max_length=64, index=True, description="报告标识")
    # 用例信息相关
    case_id = fields.BigIntField(description="用例ID")
    case_code = fields.CharField(max_length=64, description="用例标识")

    # 步骤明细相关(指向步骤明细树结构中的具体步骤)
    step_id = fields.BigIntField(description="步骤ID")
    step_no = fields.BigIntField(description="步骤序号")
    step_code = fields.CharField(max_length=64, description="步骤标识")
    step_type = fields.CharEnumField(StepType, description="步骤明细类型")

    # 步骤执行相关
    step_state = fields.BooleanField(description="步骤执行状态")
    step_st_time = fields.CharField(max_length=255, null=True, description="步骤执行开始时间")
    step_ed_time = fields.CharField(max_length=255, null=True, description="步骤执行结束时间")
    step_elapsed = fields.CharField(max_length=255, null=True, description="步骤执行消耗时间")
    step_exec_logger = fields.TextField(null=True, description="步骤执行日志")
    step_exec_except = fields.TextField(null=True, description="步骤错误描述")

    # 请求相关
    response_cookie = fields.TextField(null=True, description="响应cookies")
    response_header = fields.JSONField(null=True, description="响应头，JSON格式")
    response_body = fields.JSONField(null=True, description="响应体，JSON格式")
    response_text = fields.TextField(null=True, description="响应文本，Text格式")
    response_elapsed = fields.CharField(max_length=16, null=True, description="响应时间")

    # 变量相关
    session_variables = fields.JSONField(null=True, description="会话变量(包含提取变量，以及前后code设置的变量)")
    defined_variables = fields.JSONField(null=True, description="定义变量(自定义变量，如编写指定值或引用随机函数)")
    extract_variables = fields.JSONField(null=True, description="提取变量(从上下午中提取参数)")

    validators = fields.JSONField(null=True, description="断言规则，JSON格式")

    class Meta:
        table = "krun_autotest_api_details"
        table_description = "自动化测试-步骤结果表"
        unique_together = (
            ("report_code", "step_code"),
        )
        indexes = (
            ("case_id", "step_id", "step_no"),
            ("case_id", "step_type"),
            ("case_id", "step_state"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        return self.step_code
