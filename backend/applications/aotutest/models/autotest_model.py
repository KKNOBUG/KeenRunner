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


class CaseType(str, Enum):
    PUBLIC_API = "公共接口"
    PUBLIC_SCRIPT = "公共脚本"
    PRIVATE_SCRIPT = "用户脚本"


class ReportType(str, Enum):
    EXEC1 = "单笔执行"
    EXEC2 = "批量执行"
    EXEC3 = "定时执行"


class StepType(str, Enum):
    """请求参数类型枚举"""
    TCP = "TCP请求"
    HTTP = "HTTP请求"
    DATABASE = "数据库请求"
    PYTHON = "执行代码请求(Python)"
    IF = "条件分支"
    WAIT = "等待控制"
    LOOP = "循环结构"


def unique_identify() -> str:
    timestamp = int(datetime.datetime.now().timestamp())
    uuid4_str = uuid.uuid4().hex.upper()
    return f"{timestamp}-{uuid4_str}"


class AutoTestApiProjectInfo(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel):
    project_name = fields.CharField(max_length=255, unique=True, description="应用名称")
    project_desc = fields.CharField(max_length=2048, null=True, description="应用描述")
    project_state = fields.CharField(max_length=64, null=True, description="应用状态")
    project_phase = fields.CharField(max_length=64, null=True, description="应用阶段")
    project_dev_owners = fields.JSONField(default=list, null=True, description="应用开发负责人")
    project_developers = fields.JSONField(default=list, null=True, description="应用开发人员列表")
    project_test_owners = fields.JSONField(default=list, null=True, description="应用测试负责人")
    project_testers = fields.JSONField(default=list, null=True, description="应用测试人员列表")
    project_current_month_env = fields.CharField(max_length=64, null=True, description="应用当前月版环境")
    project_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="应用标识代码")
    state = fields.SmallIntField(default=-1, index=True, description="状态(-1:删除, 1:未删除)")

    class Meta:
        table = "krun_autotest_api_project"
        table_description = "自动化测试-应用信息表"
        indexes = (
            ("project_name", "project_state"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        return self.project_name


class AutoTestApiEnvironmentInfo(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel):
    project_id = fields.BigIntField(index=True, description="环境所属项目")
    env_name = fields.CharField(max_length=64, index=True, description="环境名称")
    env_host = fields.CharField(max_length=255, description="环境主机(http://127.0.0.1:8000 | https://127.0.0.1:8000)")
    env_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="环境标识代码")
    state = fields.SmallIntField(default=-1, index=True, description="状态(-1:启用, 1:禁用)")

    class Meta:
        table = "krun_autotest_api_env"
        table_description = "自动化测试-环境信息表"
        # 同一项目下，用例名称唯一，避免重复
        unique_together = (
            ("project_id", "env_name"),
        )
        indexes = (
            ("project_id", "env_name"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        return self.env_name


class AutoTestApiCaseInfo(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel):
    """
    测试用例信息表
    """
    case_name = fields.CharField(max_length=255, index=True, description="用例名称")
    case_desc = fields.CharField(max_length=2048, null=True, description="用例描述")
    case_tags = fields.CharField(max_length=255, null=True, description="用例标签")
    case_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="用例标识代码")
    case_steps = fields.IntField(default=0, ge=0, description="用例步骤数量(含所有子级步骤)")
    case_version = fields.IntField(default=1, ge=1, description="用例更新版本(修改次数)")
    case_project = fields.IntField(default=1, ge=1, index=True, description="用例所属应用项目")
    state = fields.SmallIntField(default=-1, index=True, description="状态(-1:未删除, 1:删除, 2:执行成功, 3:执行失败)")

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
    step_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="步骤明细标识代码")
    step_type = fields.CharEnumField(StepType, description="步骤明细类型")
    case_type = fields.CharEnumField(CaseType, description="用例所属类型")

    # 用例信息ID（普通字段，不设外键，业务层验证）
    case_id = fields.BigIntField(null=True, index=True, description="步骤明细所属用例")
    # 父级步骤ID（普通字段，不设外键，避免自关联导致的ORM循环引用问题）
    parent_step_id = fields.BigIntField(null=True, index=True, description="父级步骤明细ID")
    # 引用用例信息ID（普通字段，不设外键，业务层验证）
    quote_case_id = fields.BigIntField(null=True, index=True, description="引用公共用例ID")

    # 请求相关字段
    request_url = fields.CharField(max_length=2048, null=True, description="请求地址")
    request_port = fields.CharField(max_length=16, null=True, description="请求端口")
    request_method = fields.CharField(max_length=16, null=True, description="请求方法(GET/POST/PUT/DELETE等)")
    request_header = fields.JSONField(null=True, description="请求头信息")
    request_text = fields.TextField(null=True, description="请求体数据(Text格式)")
    request_body = fields.JSONField(null=True, description="请求体数据(Json格式)")
    request_params = fields.TextField(null=True, description="请求路径参数(Text格式)")
    request_form_data = fields.JSONField(null=True, description="请求表单数据(Json格式)")
    request_form_file = fields.JSONField(null=True, description="请求文件路径(Json格式)")
    request_form_urlencoded = fields.JSONField(null=True, description="请求键值对数据(Json格式)")
    request_project = fields.BigIntField(max_length=255, null=True, description="请求应用名称")
    request_environment = fields.CharField(max_length=64, null=True, description="请求环境名称")

    # 逻辑相关
    code = fields.TextField(null=True, description="执行代码(Python)")
    wait = fields.FloatField(ge=0, null=True, description="等待控制(正浮点数, 单位:秒)")
    max_cycles = fields.IntField(ge=1, null=True, description="最大循环次数(正整数)")
    max_interval = fields.FloatField(ge=0, null=True, description="每次循环间隔时间(正浮点数)")
    conditions = fields.JSONField(null=True, description="判断条件")

    # 变量、断言和逻辑处理
    # 自定义的变量和调用函数的变量
    session_variables = fields.JSONField(null=True, description="会话变量(所有步骤的执行结果持续累积)")
    defined_variables = fields.JSONField(null=True, description="定义变量(用户自定义、引用函数的结果)")
    # 提取和前后置操作产出的变量
    # 参数提取表达式模板：变量名称、提取来源、表达式、提取值、提取结果、错误信息
    extract_variables = fields.JSONField(null=True, description="提取变量(从请求控制器、上下文中提取、执行代码结果)")
    # 断言表达式模板：断言名称，断言对象、断言路径、结果值、断言方式、期望值、断言结果、错误信息
    assert_validators = fields.JSONField(null=True, description="断言规则(支持对各类数据对象进行不同表达式的断言验证)")
    state = fields.SmallIntField(default=-1, index=True, description="状态(-1:未删除, 1:删除, 2:执行成功, 3:执行失败)")

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
    case_code = fields.CharField(max_length=64, description="用例标识代码")
    case_st_time = fields.CharField(max_length=32, null=True, description="用例执行开始时间")
    case_ed_time = fields.CharField(max_length=32, null=True, description="用例执行结束时间")
    case_elapsed = fields.CharField(max_length=16, null=True, description="用例执行消耗时间")
    case_state = fields.BooleanField(null=True, description="用例执行状态(True:成功, False:失败)")

    step_total = fields.IntField(default=0, ge=0, description="用例步骤数量(含所有子级步骤)")
    step_fill_count = fields.IntField(default=0, ge=0, description="用例步骤失败数量(含所有子级步骤)")
    step_pass_count = fields.IntField(default=0, ge=0, description="用例步骤成功数量(含所有子级步骤)")
    step_pass_ratio = fields.FloatField(default=0.0, ge=0.0, description="用例步骤成功率(含所有子级步骤)")

    report_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="报告标识代码")
    report_type = fields.CharEnumField(ReportType, description="报告标识类型")
    task_code = fields.CharField(max_length=64, null=True, description="报告标识类型")
    state = fields.SmallIntField(default=-1, index=True, description="状态(-1:未删除, 1:删除)")

    class Meta:
        table = "krun_autotest_api_report"
        table_description = "自动化测试-测试报告表"
        indexes = (
            ("case_id", "case_code"),
            ("case_id", "state"),
            ("case_id", "case_state"),
            ("case_id", "created_user"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        return self.report_code


class AutoTestApiDetailsInfo(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel):
    """
    测试步骤结果表
    """
    # 用例信息相关
    case_id = fields.BigIntField(index=True, description="用例ID")
    case_code = fields.CharField(max_length=64, index=True, description="用例标识代码")
    report_code = fields.CharField(max_length=64, index=True, description="报告标识代码")

    # 步骤明细相关(指向步骤明细树结构中的具体步骤)
    step_id = fields.BigIntField(description="步骤明细ID")
    step_no = fields.BigIntField(description="步骤明细序号")
    step_name = fields.CharField(max_length=255, description="步骤明细名称")
    step_code = fields.CharField(max_length=64, index=True, description="步骤标识代码")
    step_type = fields.CharEnumField(StepType, description="步骤明细类型")
    step_state = fields.BooleanField(description="步骤执行状态(True:成功, False:失败)")
    step_st_time = fields.CharField(max_length=255, null=True, description="步骤执行开始时间")
    step_ed_time = fields.CharField(max_length=255, null=True, description="步骤执行结束时间")
    step_elapsed = fields.CharField(max_length=255, null=True, description="步骤执行消耗时间")
    step_exec_logger = fields.TextField(null=True, description="步骤执行日志")
    step_exec_except = fields.TextField(null=True, description="步骤错误描述")

    # 请求相关
    response_cookie = fields.TextField(null=True, description="响应信息(cookies)")
    response_header = fields.JSONField(null=True, description="响应信息(headers)")
    response_body = fields.JSONField(null=True, description="响应信息(body)")
    response_text = fields.TextField(null=True, description="响应信息(text)")
    response_elapsed = fields.CharField(max_length=16, null=True, description="响应信息(elapsed)")

    # 变量相关
    session_variables = fields.JSONField(null=True, description="会话变量(所有步骤的执行结果持续累积)")
    defined_variables = fields.JSONField(null=True, description="定义变量(用户自定义、引用函数的结果)")
    extract_variables = fields.JSONField(null=True, description="提取变量(从请求控制器、上下文中提取、执行代码结果)")
    assert_validators = fields.JSONField(null=True, description="断言规则(支持对各类数据对象进行不同表达式的断言验证)")

    num_cycles = fields.IntField(null=True, description="循环执行次数(第几次)")
    state = fields.SmallIntField(default=-1, index=True, description="状态(-1:未删除, 1:删除)")

    class Meta:
        table = "krun_autotest_api_details"
        table_description = "自动化测试-步骤结果表"
        unique_together = (
            ("report_code", "case_code", "step_code", "num_cycles"),
        )
        indexes = (
            ("case_id", "step_id", "step_no"),
            ("case_id", "step_type"),
            ("case_id", "step_state"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        return self.step_code
