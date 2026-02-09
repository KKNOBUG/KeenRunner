# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_model.py
@DateTime: 2025/12/28 16:15
"""
import datetime
import uuid

from tortoise import fields

from backend.applications.base.services.scaffold import (
    ScaffoldModel,
    MaintainMixin,
    TimestampMixin,
    StateModel,
    ReserveFields
)
from backend.enums.autotest_enum import (
    AutoTestCaseType,
    AutoTestTagType,
    AutoTestStepType,
    AutoTestReportType,
    AutoTestLoopMode,
    AutoTestCaseAttr,
    AutoTestLoopErrorStrategy,
    AutoTestTaskStatus,
    AutoTestTaskScheduler,
    AutoTestReqArgsType
)


def unique_identify() -> str:
    timestamp = int(datetime.datetime.now().timestamp())
    uuid4_str = uuid.uuid4().hex.upper()
    return f"{timestamp}-{uuid4_str}"


class AutoTestApiProjectInfo(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
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
    state = fields.SmallIntField(default=0, index=True, description="状态(0:启用, 1:禁用)")

    class Meta:
        table = "krun_autotest_api_project"
        table_description = "自动化测试-应用信息表"
        indexes = (
            ("project_name", "project_state"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        return self.project_name


class AutoTestApiEnvInfo(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    project_id = fields.BigIntField(index=True, description="环境所属项目")
    env_name = fields.CharField(max_length=64, index=True, description="环境名称")
    env_host = fields.CharField(max_length=128, description="环境主机(http|https://127.0.0.1)")
    env_port = fields.CharField(max_length=8, description="环境端口(8000)")
    env_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="环境标识代码")
    state = fields.SmallIntField(default=0, index=True, description="状态(0:启用, 1:禁用)")

    class Meta:
        table = "krun_autotest_api_env"
        table_description = "自动化测试-环境信息表"
        unique_together = (
            ("project_id", "env_name"),
        )
        indexes = (
            ("project_id", "env_name"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        return self.env_name


class AutoTestApiTagInfo(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    tag_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="标签标识代码")
    tag_type = fields.CharEnumField(AutoTestTagType, description="标签所属类型")
    tag_project = fields.IntField(default=1, ge=1, index=True, description="标签所属应用")
    tag_mode = fields.CharField(max_length=64, null=True, description="标签大类")
    tag_name = fields.CharField(max_length=64, null=True, description="标签名称")
    tag_desc = fields.CharField(max_length=2048, null=True, description="标签描述")
    state = fields.SmallIntField(default=0, index=True, description="状态(0:启用, 1:禁用)")

    class Meta:
        table = "krun_autotest_api_tag"
        table_description = "自动化测试-标签信息表"
        unique_together = (
            ("tag_project", "tag_type", "tag_mode", "tag_name"),
        )
        indexes = (
            ("tag_type", "tag_mode", "tag_name"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        return self.tag_name


class AutoTestApiCaseInfo(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    case_name = fields.CharField(max_length=255, index=True, description="用例名称")
    case_desc = fields.CharField(max_length=2048, null=True, description="用例描述")
    case_tags = fields.JSONField(default=list, description="用例所属标签")
    case_type = fields.CharEnumField(AutoTestCaseType, default=None, null=True, description="用例所属类型")
    case_attr = fields.CharEnumField(AutoTestCaseAttr, default=None, null=True, description="用例所属属性")
    case_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="用例标识代码")
    case_steps = fields.IntField(default=0, ge=0, description="用例步骤数量(含所有子级步骤)")
    case_state = fields.BooleanField(null=True, description="用例执行状态(True:成功, False:失败)")
    case_version = fields.IntField(default=1, ge=1, description="用例更新版本(修改次数)")
    case_project = fields.IntField(default=1, ge=1, index=True, description="用例所属应用")
    case_last_time = fields.DatetimeField(null=True, description="用例执行时间")
    # session_variables 存储为List[Dict[str, Any]]格式，每个元素包含 key、value、desc 项
    session_variables = fields.JSONField(default=list, null=True, description="会话变量(初始变量池)")
    state = fields.SmallIntField(default=0, index=True, description="状态(0:启用, 1:禁用)")

    class Meta:
        table = "krun_autotest_api_case"
        table_description = "自动化测试-用例信息表"
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


class AutoTestApiStepInfo(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    step_no = fields.IntField(default=1, ge=1, description="步骤序号")
    step_name = fields.CharField(max_length=255, description="步骤名称")
    step_desc = fields.CharField(max_length=2048, null=True, description="步骤描述")
    step_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="步骤标识代码")
    step_type = fields.CharEnumField(AutoTestStepType, description="步骤类型")

    # 用例信息ID（普通字段，不设外键，业务层验证）
    case_id = fields.BigIntField(null=True, index=True, description="步骤所属用例")
    # 父级步骤ID（普通字段，不设外键，避免自关联导致的ORM循环引用问题）
    parent_step_id = fields.BigIntField(null=True, index=True, description="父级步骤ID")
    # 引用用例信息ID（普通字段，不设外键，业务层验证）
    quote_case_id = fields.BigIntField(null=True, index=True, description="引用公共用例ID")

    # 请求相关字段
    request_url = fields.CharField(max_length=2048, null=True, description="请求地址")
    request_port = fields.CharField(max_length=16, null=True, description="请求端口")
    request_method = fields.CharField(max_length=16, null=True, description="请求方法(GET/POST/PUT/DELETE等)")
    """
    request_header、request_params、request_form_data、request_form_urlencoded、request_form_file字段
    存储格式为列表嵌套字典, 每个元素包含 key、value、desc 项
    """
    request_header = fields.JSONField(null=True, description="请求头信息")
    request_text = fields.TextField(null=True, description="请求体数据")
    request_body = fields.JSONField(null=True, description="请求体数据")
    request_params = fields.JSONField(null=True, description="请求路径参数")
    request_form_data = fields.JSONField(null=True, description="请求表单数据")
    request_form_file = fields.JSONField(null=True, description="请求文件路径")
    request_form_urlencoded = fields.JSONField(null=True, description="请求键值对数据")
    request_project_id = fields.BigIntField(null=True, description="请求应用ID")
    request_args_type = fields.CharEnumField(AutoTestReqArgsType, default=None, null=True, description="请求参数类型")

    # 逻辑相关
    code = fields.TextField(null=True, description="执行代码(Python)")
    wait = fields.FloatField(ge=0, null=True, description="等待控制(正浮点数, 单位:秒)")
    loop_mode = fields.CharEnumField(AutoTestLoopMode, default=None, null=True, description="循环模式类型")
    loop_maximums = fields.IntField(ge=1, null=True, description="最大循环次数(正整数)")
    loop_interval = fields.FloatField(ge=0, null=True, description="每次循环间隔时间(正浮点数)")
    loop_iterable = fields.CharField(max_length=512, null=True, description="循环对象来源(变量名或可迭代对象)")
    loop_iter_idx = fields.CharField(max_length=64, null=True, description="用于存储enumerate得到的索引值")
    loop_iter_key = fields.CharField(max_length=64, null=True, description="用于存储字典的键")
    loop_iter_val = fields.CharField(max_length=64, null=True, description="用于存储字典的值或列表的项")
    loop_on_error = fields.CharEnumField(AutoTestLoopErrorStrategy, default=None, null=True,
                                         description="循环执行失败时的处理策略")
    loop_timeout = fields.FloatField(ge=0, null=True, description="条件循环超时时间(正浮点数, 单位:秒, 0表示不超时)")
    conditions = fields.JSONField(null=True, description="判断条件(循环结构或条件分支)")

    # 变量、断言和逻辑处理
    # session_variables、defined_variables 存储为List[Dict[str, Any]]格式，每个元素包含 key、value、desc 项
    session_variables = fields.JSONField(null=True, description="会话变量(所有步骤的执行结果持续累积)")
    defined_variables = fields.JSONField(null=True, description="定义变量(用户自定义、引用函数的结果)")
    # extract_variables 存储为List[Dict[str, Any]]格式，每个元素包含 name、range、source、expr、index 项
    extract_variables = fields.JSONField(null=True, description="提取变量(从请求控制器、上下文中提取、执行代码结果)")
    # assert_validators 存储为List[Dict[str, Any]]格式，每个元素包含 expr、name、range、operation、except_value 项
    assert_validators = fields.JSONField(null=True, description="断言规则(支持对数据对象进行不同表达式的断言验证)")
    state = fields.SmallIntField(default=0, index=True, description="状态(0:启用, 1:禁用)")

    class Meta:
        table = "krun_autotest_api_step"
        table_description = "自动化测试-步骤明细表"
        unique_together = (
            ("case_id", "step_no", "step_code"),
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


class AutoTestApiReportInfo(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    case_id = fields.BigIntField(index=True, description="用例ID")
    case_code = fields.CharField(max_length=64, description="用例标识代码")
    case_st_time = fields.CharField(max_length=32, null=True, description="用例执行开始时间")
    case_ed_time = fields.CharField(max_length=32, null=True, description="用例执行结束时间")
    case_elapsed = fields.CharField(max_length=16, null=True, description="用例执行消耗时间")
    case_state = fields.BooleanField(null=True, description="用例执行状态(True:成功, False:失败)")

    step_total = fields.IntField(default=0, ge=0, description="用例步骤数量(含所有子级步骤)")
    step_fail_count = fields.IntField(default=0, ge=0, description="用例步骤失败数量(含所有子级步骤)")
    step_pass_count = fields.IntField(default=0, ge=0, description="用例步骤成功数量(含所有子级步骤)")
    step_pass_ratio = fields.FloatField(default=0.0, ge=0.0, description="用例步骤成功率(含所有子级步骤)")

    batch_code = fields.CharField(max_length=64, default=None, null=True, description="批次标识代码")
    report_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="报告标识代码")
    report_type = fields.CharEnumField(AutoTestReportType, description="报告类型")
    task_code = fields.CharField(max_length=64, null=True, description="任务标识代码")
    state = fields.SmallIntField(default=0, index=True, description="状态(0:启用, 1:禁用)")

    class Meta:
        table = "krun_autotest_api_report"
        table_description = "自动化测试-报告信息表"
        indexes = (
            ("case_id", "case_code"),
            ("case_id", "state"),
            ("case_id", "case_state"),
            ("case_id", "created_user"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        return self.report_code


class AutoTestApiDetailInfo(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    # 用例信息相关
    case_id = fields.BigIntField(index=True, description="用例ID")
    case_code = fields.CharField(max_length=64, index=True, description="用例标识代码")
    report_code = fields.CharField(max_length=64, index=True, description="报告标识代码")
    quote_case_id = fields.BigIntField(null=True, index=True, description="引用公共用例ID")

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

    # 请求相关
    response_cookie = fields.TextField(null=True, description="响应信息(cookies)")
    response_header = fields.JSONField(null=True, description="响应信息(headers)")
    response_body = fields.JSONField(null=True, description="响应信息(body)")
    response_text = fields.TextField(null=True, description="响应信息(text)")
    response_elapsed = fields.CharField(max_length=16, null=True, description="响应信息(elapsed)")

    # 变量相关
    # session_variables、defined_variables 存储为List[Dict[str, Any]]格式，每个元素包含 key、value、desc 项
    session_variables = fields.JSONField(null=True, description="会话变量(所有步骤的执行结果持续累积)")
    defined_variables = fields.JSONField(null=True, description="定义变量(用户自定义、引用函数的结果)")
    # extract_variables 存储为List[Dict[str, Any]]格式，每个元素包含 name、range、source、expr、index、extract_value、success、error 项
    extract_variables = fields.JSONField(null=True, description="提取变量(从请求控制器、上下文中提取、执行代码结果)")
    # assert_validators 存储为List[Dict[str, Any]]格式，每个元素包含 name、expr、operation、except_value、actual_value、success、error 项
    assert_validators = fields.JSONField(null=True, description="断言规则(支持对数据对象进行不同表达式的断言验证)")

    num_cycles = fields.IntField(null=True, description="循环执行次数(第几次)")
    state = fields.SmallIntField(default=0, index=True, description="状态(0:启用, 1:禁用)")

    class Meta:
        table = "krun_autotest_api_details"
        table_description = "自动化测试-明细信息表"
        unique_together = (
            ("report_code", "case_code", "step_code", "num_cycles"),
        )
        indexes = (
            ("case_id", "step_id", "step_no"),
            # 优化查询性能：添加常用查询条件的组合索引
            ("report_code", "case_id", "state"),
            ("case_id", "report_code", "state"),
            # 优化排序性能：为排序字段添加索引
            ("report_code", "step_st_time"),
            ("case_id", "report_code", "step_st_time"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        return self.step_code


class AutoTestApiTaskInfo(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    task_name = fields.CharField(max_length=255, index=True, description="任务名称")
    task_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="任务标识代码")
    task_desc = fields.CharField(max_length=2048, null=True, description="任务描述")
    task_type = fields.CharField(max_length=1024, null=True, description="任务实现函数的完全限定名")
    task_project = fields.IntField(default=1, ge=1, index=True, description="任务所属应用")
    task_kwargs = fields.JSONField(default=dict, null=True, description="任务参数字典")
    last_execute_time = fields.DatetimeField(default=None, null=True, description="最后执行时间")
    last_execute_state = fields.CharEnumField(AutoTestTaskStatus, default=None, null=True, description="最后执行状态")
    task_scheduler = fields.CharEnumField(AutoTestTaskScheduler, default=None, null=True, description="任务调度状态")
    task_interval_expr = fields.IntField(null=True, description="任务触发条件1")
    task_datetime_expr = fields.CharField(max_length=64, null=True, description="任务触发条件2")
    task_crontabs_expr = fields.CharField(max_length=255, null=True, description="任务触发条件3")
    task_notify = fields.JSONField(default=None, null=True, description="任务执行明细反馈")
    task_notifier = fields.JSONField(default=None, null=True, description="任务执行通知人员")
    task_enabled = fields.BooleanField(default=False, index=True, description="是否启动调度(True/False)")
    state = fields.SmallIntField(default=0, index=True, description="状态(0:启用, 1:禁用)")

    class Meta:
        table = "krun_autotest_api_task"
        table_description = "自动化测试-任务信息表"
        unique_together = (
            ("task_name", "task_project"),
        )
        indexes = (
            ("task_name", "task_project"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        return self.task_name


class AutoTestApiRecordInfo(ScaffoldModel, TimestampMixin):
    task_id = fields.BigIntField(null=True, index=True, description="任务ID(krun_autotest_api_task表主键)")
    task_name = fields.CharField(max_length=255, null=True, index=True, description="任务名称")
    task_kwargs = fields.JSONField(default=dict, null=True, description="定时任务实现函数的关键字参数")
    task_summary = fields.TextField(null=True, description="任务的执行摘要")
    task_error = fields.TextField(null=True, description="任务的错误信息")
    celery_id = fields.CharField(max_length=255, index=True, description="调度ID")
    celery_node = fields.CharField(max_length=512, null=True, index=True, description="调度节点")
    celery_trace_id = fields.CharField(max_length=255, null=True, index=True, description="调度回溯ID")
    celery_status = fields.CharEnumField(AutoTestTaskStatus, default=AutoTestTaskStatus.RUNNING, description="调度状态")
    celery_scheduler = fields.CharEnumField(AutoTestTaskScheduler, default=None, null=True, description="调度方式")
    celery_start_time = fields.DatetimeField(null=True, description="开始时间")
    celery_end_time = fields.DatetimeField(null=True, description="结束时间")
    celery_duration = fields.CharField(max_length=64, null=True, description="耗时(秒或描述)")

    class Meta:
        table = "krun_autotest_api_record"
        table_description = "自动化测试-任务执行记录表"
        indexes = (
            ("celery_id",),
            ("task_id",),
            ("celery_status",),
            ("celery_start_time",),
        )
        ordering = ["-celery_start_time", "-id"]

    def __str__(self):
        return f"{self.celery_id or ''}-{self.task_name or ''}"
