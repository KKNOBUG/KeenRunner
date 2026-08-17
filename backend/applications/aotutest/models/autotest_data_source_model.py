# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_source_model.py
@DateTime: 2025/12/28 16:15
"""
from tortoise import fields
from tortoise.validators import MinValueValidator, MaxValueValidator

from backend.applications.base.services.scaffold import (
    ScaffoldModel,
    MaintainMixin,
    TimestampMixin,
    StateModel,
    ReserveFields,
    unique_identify,
)


class AutoTestDataSourceModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    case_id = fields.BigIntField(ge=1, index=True, description="用例ID")
    case_code = fields.CharField(max_length=64, description="用例标识代码")
    step_id = fields.BigIntField(ge=1, index=True, description="步骤ID")
    step_code = fields.CharField(max_length=64, description="步骤标识代码")
    file_name = fields.CharField(max_length=255, null=True, description="数据驱动文件存储名称")
    file_hash = fields.CharField(max_length=255, null=True, description="数据驱动文件哈希代码")
    file_path = fields.CharField(max_length=1024, null=True, description="数据驱动文件存储路径")
    file_desc = fields.CharField(max_length=2048, null=True, description="数据驱动文件场景描述")
    # 存储格式：{"场景1": {"head":..., "body":..., "assert_head":..., "assert_body":... }, ... }
    dataset = fields.JSONField(description="数据驱动文件解析后的数据(该步骤×所有场景)")
    # 数据集名称列表, 如["场景1", "场景2", "场景3", ...], 便于前端多选
    dataset_names = fields.JSONField(default=list, description="数据驱动文件解析后的场景名称列表")
    # 存储格式：“dataset_{case_id}_{step_code}”
    cache_key = fields.CharField(max_length=128, description="获取Redis中该步骤数据的缓存键名")
    dataframe = fields.JSONField(default=list, null=True, description="数据驱动文件解析前的二维矩阵")
    axis = fields.SmallIntField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        description="数据矩阵(0:水平模式, 1:垂直模式)"
    )
    data_source_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="数据驱动文件标识代码")

    class Meta:
        table = "krun_autotest_data_source"
        table_description = "自动化测试-数据驱动文件存储表"
        unique_together = (
            ("case_id", "step_code"),
        )
        indexes = (
            ("case_id", "state"),
            ("case_id", "state", "updated_time"),
            ("data_source_code", "state"),
            ("case_id", "step_id"),
        )
        ordering = ["case_id", "step_code"]

    def __str__(self):
        return f"{self.data_source_code or ''}(case_id={self.case_id},step_code={self.step_code})"
