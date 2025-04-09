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
    # 基本请求信息
    url = fields.CharField(max_length=255, description="请求地址")
    method = fields.CharEnumField(HTTPMethod, description="请求方式")
    headers = fields.JSONField(default=None, null=True, description="请求头部")

    # 请求参数
    params = fields.JSONField(default=dict, null=True, description="URL查询参数")
    json_body = fields.JSONField(default=dict, null=True, description="JSON格式请求体")
    form_data = fields.JSONField(default=dict, null=True, description="multipart/form-data格式请求体")
    x_www_form_urlencoded = fields.JSONField(default=dict, null=True, description="x-www-form-urlencoded格式请求体")

    # 测试用例基本信息
    priority = fields.CharEnumField(TestCasePriorityEnum, index=True, description="优先等级")
    project = fields.ForeignKeyField(
        model_name="models.Project",
        related_name="api_testcase_projects",
        description="所属应用"
    )
    module = fields.ForeignKeyField(
        model_name="models.Module",
        related_name="api_testcase_modules",
        description="所属模块",
        null=True
    )
    env = fields.ForeignKeyField(
        model_name="models.Environment",
        related_name="api_testcase_envs",
        description="所属环境"
    )
    testcase_name = fields.CharField(max_length=255, index=True, description="测试用例名称")
    testcase_tags = fields.CharField(max_length=255, null=True, description="测试用例标签")
    description = fields.TextField(null=True, description="测试用例描述")
    variables = fields.JSONField(default=None, null=True, description="关联变量")

    class Meta:
        table = "krun_api_testcase"
        unique_together = (
            ("method", "url", "created_user", "testcase_name"),
        )
