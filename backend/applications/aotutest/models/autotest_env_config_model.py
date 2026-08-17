# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_env_config_model.py
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
)
from backend.enums import AutoTestConfigNodeType, AutoTestDataBaseType


class AutoTestEnvBindModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    """应用×环境枚举×节点类型的挂载点；主键对外语义为env_bind_id。"""

    env_enum = fields.ForeignKeyField(
        "models.AutoTestEnvModel",
        related_name="env_binds",
        on_delete=fields.RESTRICT,
        db_constraint=True,
        index=True,
        description="环境枚举",
    )
    env_type = fields.CharEnumField(AutoTestConfigNodeType, default=AutoTestConfigNodeType.API, index=True, description="节点类型")
    env_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="绑定标识代码")
    env_desc = fields.CharField(max_length=2048, null=True, description="绑定描述")
    project_id = fields.BigIntField(ge=1, index=True, description="应用ID")

    class Meta:
        table = "krun_autotest_env_bind"
        table_description = "自动化测试-环境绑定表"
        unique_together = (
            ("env_enum", "project_id", "env_type"),
        )
        indexes = (
            ("project_id", "state"),
            ("env_type", "state"),
            ("env_enum", "state"),
            ("project_id", "env_type", "state"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        """返回绑定标识代码。"""
        return self.env_code


class AutoTestEnvConfigModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    """挂载点下的连接明细；主键对外语义为env_config_id；project_id/env_type由绑定派生。"""

    env_bind = fields.ForeignKeyField(
        "models.AutoTestEnvBindModel",
        related_name="env_configs",
        on_delete=fields.RESTRICT,
        db_constraint=True,
        index=True,
        description="环境绑定",
    )
    config_name = fields.CharField(max_length=128, description="配置名称")
    config_desc = fields.CharField(max_length=2048, null=True, description="配置描述")
    config_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="配置标识代码")
    config_host = fields.CharField(max_length=128, description="数据库/服务器主机地址")
    config_port = fields.CharField(max_length=8, null=True, description="数据库/服务器端口")
    database_name = fields.CharField(max_length=128, null=True, description="数据库名称")
    database_type = fields.CharEnumField(AutoTestDataBaseType, default=None, null=True, description="数据库类型")
    config_username = fields.CharField(max_length=128, null=True, description="数据库/服务器用户名")
    config_password = fields.CharField(max_length=128, null=True, description="数据库/服务器密码")
    config_group = fields.CharField(max_length=128, null=True, description="数据库/服务器分组")
    config_params = fields.JSONField(default=None, null=True, description="数据库/服务器参数")
    config_kwargs = fields.JSONField(default=None, null=True, description="通用环境变量配置")
    config_header = fields.JSONField(default=None, null=True, description="通用请求头配置")
    is_no_password = fields.BooleanField(default=None, null=True, description="是否免密")

    class Meta:
        table = "krun_autotest_env_config"
        table_description = "自动化测试-环境配置表"
        unique_together = (
            ("env_bind", "config_name"),
        )
        indexes = (
            ("env_bind", "state"),
            ("config_code", "state"),
            ("config_host", "config_port"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        return self.config_name
