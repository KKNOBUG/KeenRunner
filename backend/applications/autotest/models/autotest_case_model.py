# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_model.py
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
    UpperCharField,
)
from backend.enums import AutoTestCaseType, AutoTestCaseAttr


class AutoTestCaseModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    case_name = fields.CharField(max_length=255, index=True, description="用例名称")
    case_desc = fields.CharField(max_length=2048, null=True, description="用例描述")
    # case_tags 存储为List[int]格式
    case_tags = fields.JSONField(default=None, null=True, description="用例所属标签")
    case_type = fields.CharEnumField(AutoTestCaseType, default=None, null=True, description="用例所属类型")
    case_attr = fields.CharEnumField(AutoTestCaseAttr, default=None, null=True, description="用例所属属性")
    case_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="用例标识代码")
    case_steps = fields.IntField(default=0, ge=0, description="用例步骤数量(含所有子级步骤)")
    case_state = fields.BooleanField(null=True, description="用例执行状态(True:成功, False:失败)")
    case_version = fields.IntField(default=1, ge=1, description="用例更新版本(修改次数)")
    case_project = fields.IntField(default=1, ge=1, index=True, description="用例所属应用")
    case_last_time = fields.DatetimeField(null=True, description="用例执行时间")
    # session_variables 存储为List[Dict[str, Any]]格式, 每个元素包含key、value、desc项；
    session_variables = fields.JSONField(default=None, null=True, description="会话变量(初始变量池)")
    # owner_user与created_user同一套账号规范；创建时等于创建人, 仅转让接口可改
    owner_user = UpperCharField(max_length=16, default=None, null=True, index=True, description="用例所属人员")

    class Meta:
        table = "krun_autotest_case"
        table_description = "自动化测试-用例信息表"
        unique_together = (
            ("case_project", "case_name", "case_type", "owner_user"),
        )
        indexes = (
            ("case_project", "state", "created_time"),
            ("case_project", "case_name", "case_type"),
            ("case_project", "case_name", "state"),
            ("case_project", "owner_user", "state"),
            ("case_name", "state"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        """返回用例名称。"""
        return self.case_name
