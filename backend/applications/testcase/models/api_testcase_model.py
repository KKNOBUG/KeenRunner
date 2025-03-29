# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : api_testcase_model.py
@DateTime: 2025/3/28 15:12
"""
from tortoise import fields

from backend.applications.base.services.scaffold import ScaffoldModel, MaintainMixin, TimestampMixin
from backend.enums.http_enum import HTTPMethod
from backend.enums.testcase_priority_enum import TestCasePriorityEnum


class ApiTestCase(ScaffoldModel, MaintainMixin, TimestampMixin):
    url = fields.CharField(max_length=255, description="请求地址")
    method = fields.CharEnumField(HTTPMethod, description="请求方式")
    headers = fields.JSONField(default=None, null=True, description="请求头部")
    params = fields.CharField(max_length=512, default="", null=True, description="请求参数（键值对）")
    json_body = fields.JSONField(default=None, null=True, description="请求参数（JSON）")
    form_data = fields.JSONField(default=None, null=True, description="请求参数（表单）")
    priority = fields.CharEnumField(TestCasePriorityEnum, index=True, description="风险等级")
    project = fields.CharField(max_length=64, index=True, description="应用项目")
    module = fields.CharField(max_length=64, index=True, description="应用模块")
    testcase_name = fields.CharField(max_length=255, index=True, description="测试用例名称")
    description = fields.TextField(null=True, description="描述")
    variables = fields.JSONField(default=None, null=True, description="关联变量")

    class Meta:
        table = "krun_api_testcase"
        unique_together = (
            ("method", "url", "created_user", "testcase_name"),
        )
