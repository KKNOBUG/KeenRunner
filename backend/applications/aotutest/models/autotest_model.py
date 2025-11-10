import datetime
import uuid
from enum import Enum

from tortoise import fields
from backend.applications.base.services.scaffold import (
    ScaffoldModel, MaintainMixin, TimestampMixin, StateModel
)


class CodeLanguage(str, Enum):
    """代码语言类型枚举"""
    JAVA = "JAVA"
    PYTHON = "PYTHON"


class RequestParamsType(str, Enum):
    """请求参数类型枚举"""
    JSON = "JSON"
    FORM_DATA = "FORM_DATA"
    FORM_URLENCODED = "FORM_URLENCODED"
    XML = "XML"
    RAW = "RAW"
    NONE = "NONE"


def generate_timestamp() -> str:
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S.%f").split(".")[-1]
    uuid4_str = uuid.uuid4().hex.upper()
    return f"{timestamp}-{uuid4_str}"


class AutoTestCaseInfo(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel):
    """
    测试用例信息表
    """
    case_name = fields.CharField(max_length=255, index=True, description="用例名称，必输")
    case_desc = fields.CharField(max_length=2048, null=True, description="用例描述，非必输")
    case_flag = fields.CharField(max_length=255, null=True, description="用例标签，非必输")
    case_code = fields.CharField(max_length=64, default=generate_timestamp, unique=True, description="用例代码")
    case_version = fields.IntField(default=None, null=True, ge=1, description="用例版本，正整数，默认None, 最小值1")
    project_id = fields.CharField(max_length=255, index=True, description="项目编号，必输")

    class Meta:
        table = "krun_autotest_case"
        table_description = "自动化测试-用例信息表"
        # 同一项目下，用例名称唯一，避免重复
        unique_together = (
            ("case_name", "project_id"),
        )
        indexes = (
            ("project_id", "state"),
            ("project_id", "case_name"),
            ("case_name", "state"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        return self.case_name


class AutoTestStepType(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel):
    """
    用例步骤类型表
    """
    type_name = fields.CharField(max_length=255, unique=True, description="步骤枚举名称，唯一")
    type_desc = fields.CharField(max_length=1024, null=True, description="步骤描述")

    class Meta:
        table = "krun_autotest_type"
        indexes = (
            ("type_name", "state"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        return self.type_name


class AutoTestStepInfo(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel):
    """
    测试步骤明细表
    存储步骤的详细配置信息，不包含层级关系和用例关联
    """
    step_name = fields.CharField(max_length=255, description="步骤名称，必输")
    step_desc = fields.CharField(max_length=2048, null=True, description="步骤描述，非必输")
    step_code = fields.CharField(max_length=64, default=generate_timestamp, unique=True, description="步骤代码")

    # 步骤类型外键
    step_type: fields.ForeignKeyRelation[AutoTestStepType] = fields.ForeignKeyField(
        "models.AutoTestStepType",
        index=True,
        related_name="step_types",
        on_delete=fields.RESTRICT,
        description="步骤类型",
    )

    # 引用用例信息外键（用于引用其他用例的步骤）
    quote_case: fields.ForeignKeyNullableRelation[AutoTestCaseInfo] = fields.ForeignKeyField(
        "models.AutoTestCaseInfo",
        null=True,
        related_name="quote_steps",
        on_delete=fields.RESTRICT,
        description="引用用例信息",
    )

    # 请求相关字段
    request_url = fields.CharField(max_length=2048, null=True, description="请求地址")
    request_port = fields.CharField(max_length=16, null=True, description="请求端口")
    request_protocol = fields.CharField(max_length=16, default="HTTP", description="请求协议（HTTP/TCP）")
    request_method = fields.CharField(max_length=16, null=True, description="请求方法（GET/POST/PUT/DELETE等）")

    # 参数相关字段（存储复杂数据结构）
    request_header = fields.JSONField(null=True, description="请求头，JSON格式")
    request_text = fields.TextField(null=True, description="请求体，Text格式")
    request_body = fields.JSONField(null=True, description="请求体，JSON格式")
    request_params = fields.JSONField(null=True, description="请求参数，JSON格式")
    request_form_data = fields.JSONField(null=True, description="请求表单，JSON格式")
    request_form_file = fields.CharField(max_length=2048, null=True, description="请求文件路径")
    request_form_urlencoded = fields.JSONField(null=True, description="请求键值对，JSON格式")

    # 等待时间（正整数）
    pre_wait = fields.IntField(ge=0, null=True, description="前置等待时间，正整数（毫秒），非必输")
    post_wait = fields.IntField(ge=0, null=True, description="后置等待时间，正整数（毫秒），非必输")

    # 代码执行相关
    pre_code = fields.TextField(null=True, description="前置操作代码，Text类型")
    post_code = fields.TextField(null=True, description="后置操作代码，Text类型")
    pre_code_language = fields.CharEnumField(CodeLanguage, null=True, description="前置操作代码语言类型")
    post_code_language = fields.CharEnumField(CodeLanguage, null=True, description="后置操作代码语言类型")

    # 变量和断言
    use_variables = fields.JSONField(null=True, description="变量使用，JSON格式")
    ext_variables = fields.JSONField(null=True, description="变量提取，JSON格式")
    validators = fields.JSONField(null=True, description="断言规则，JSON格式")

    class Meta:
        table = "krun_autotest_info"
        table_description = "自动化测试-步骤明细表"
        indexes = (
            ("step_type", "state"),
            ("step_name", "state"),
            ("quote_case",),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        return self.step_name


class AutoTestStepMapping(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel):
    """
    测试步骤映射表
    管理测试用例与步骤明细的关联关系，以及步骤之间的层级关系
    """
    # 用例信息外键
    case: fields.ForeignKeyRelation[AutoTestCaseInfo] = fields.ForeignKeyField(
        "models.AutoTestCaseInfo",
        related_name="case_mappings",
        on_delete=fields.RESTRICT,
        description="用例信息",
    )

    # 步骤明细外键
    step_info: fields.ForeignKeyRelation[AutoTestStepInfo] = fields.ForeignKeyField(
        "models.AutoTestStepInfo",
        related_name="step_mappings",
        on_delete=fields.RESTRICT,
        description="步骤明细信息",
    )

    # 父步骤映射外键（指向另一个步骤映射，形成层级关系）
    parent_mapping: fields.ForeignKeyNullableRelation["AutoTestStepMapping"] = fields.ForeignKeyField(
        "models.AutoTestStepMapping",
        null=True,
        related_name="child_mappings",
        on_delete=fields.SET_NULL,
        description="父级步骤映射",
    )

    # 步骤序号（在同一用例内唯一，用于排序）
    step_no = fields.IntField(ge=1, description="步骤序号，正整数，用于对用例中的所有步骤进行排序标注")

    class Meta:
        table = "krun_autotest_mapping"
        table_description = "自动化测试-步骤映射表"
        # 重要约束：同一用例内，步骤序号必须唯一（保证排序不冲突）
        unique_together = (
            ("case", "step_no"),
        )
        indexes = (
            ("case", "parent_mapping", "step_no"),
            ("case", "state"),
            ("case", "step_info"),
            ("parent_mapping",),
            ("step_no",),
        )
        ordering = ["case", "step_no"]

    def __str__(self):
        return f"{self.case.case_name} - Step {self.step_no}"
