# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_dataset_model.py
@DateTime: 2026/9/15 10:45
"""
from tortoise import fields
from tortoise.validators import MaxValueValidator, MinValueValidator

from backend.applications.base.services.scaffold import (
    ScaffoldModel,
    MaintainMixin,
    TimestampMixin,
    StateModel,
    ReserveFields,
    JSONTextField,
    unique_identify,
)
from backend.enums import PerfDatasetSource


class PerfDatasetModel(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel, ReserveFields):
    """
    性能测试-参数化数据集表。

    结构与功能数据源(krun_autotest_data_source)同形: dataset 按场景名存
    head/body/assert_head/assert_body 四分区, 解析复用 autotest_data_source_parser,
    不为压测侧另设行式协议。「场景」即虚拟用户分配单元(round_robin/unique/random
    属场景用法层, 由场景接口项声明); 施压与调试仅消费 head/body 两分区,
    assert_* 分区按解析器原样输出保留以维持结构对齐。
    """
    ds_name = fields.CharField(max_length=255, index=True, description="数据集名称")
    ds_desc = fields.CharField(max_length=2048, null=True, description="数据集描述")
    ds_code = fields.CharField(max_length=64, default=unique_identify, unique=True, description="数据集标识代码")
    ds_project = fields.IntField(default=1, ge=1, index=True, description="数据集所属应用")

    # 归属压测接口ID（普通字段，不设外键，业务层验证；空=场景级自由数据, 名称/代码由id回查不落冗余列）
    bind_api_id = fields.BigIntField(default=None, null=True, index=True, description="归属压测接口ID")

    # 存储格式：{"场景1": {"head": {...}, "body": {...}, "assert_head": {...}, "assert_body": {...}}, ...}
    dataset = JSONTextField(default=dict, description="数据解析后的数据(该数据集×所有场景)")
    dataset_names = fields.JSONField(default=list, description="场景名称列表(保持矩阵中的场景顺序)")
    dataframe = fields.JSONField(default=list, null=True, description="数据矩阵(在线编辑回显)")
    axis = fields.SmallIntField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        description="数据矩阵(0:水平模式, 1:垂直模式)"
    )

    ds_source = fields.CharEnumField(PerfDatasetSource, default=PerfDatasetSource.FILE, description="数据来源")
    # 造数作业溯源(source_type=job时指向产出作业, 见 krun_perf_data_job)
    job_id = fields.BigIntField(default=None, null=True, index=True, description="产出作业ID(source_type=job)")
    job_code = fields.CharField(max_length=64, default=None, null=True, description="产出作业标识代码")
    file_name = fields.CharField(max_length=2048, default=None, null=True, description="来源文件名")
    file_path = fields.CharField(max_length=2048, default=None, null=True, description="来源文件路径")
    file_hash = fields.CharField(max_length=64, default=None, null=True, description="来源文件哈希(重复上传秒传与变更识别)")

    class Meta:
        table = "krun_perf_dataset"
        table_description = "性能测试-参数化数据集表"
        unique_together = (
            ("ds_project", "ds_name"),
        )
        indexes = (
            ("ds_project", "state", "created_time"),
            ("bind_api_id", "state"),
            ("ds_code", "state"),
        )
        ordering = ["-updated_time"]

    def __str__(self):
        """返回数据集名称。"""
        return self.ds_name
