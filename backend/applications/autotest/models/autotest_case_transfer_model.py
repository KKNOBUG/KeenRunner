# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_transfer_model.py
@DateTime: 2025/12/28 16:15
"""
from tortoise import fields

from backend.applications.base.services.scaffold import ScaffoldModel, MaintainMixin, TimestampMixin, UpperCharField


class AutoTestCaseTransferModel(ScaffoldModel, MaintainMixin, TimestampMixin):
    case_id = fields.BigIntField(index=True, description="用例ID")
    prev_owner_user = UpperCharField(max_length=16, description="用例转出前归属人员")
    next_owner_user = UpperCharField(max_length=16, description="用例转出后归属人员")
    transfer_desc = fields.CharField(max_length=2048, null=True, description="用例转出描述")

    class Meta:
        table = "krun_autotest_case_transfer"
        table_description = "自动化测试-用例转让表"
        indexes = (
            ("case_id", "created_time"),
            ("created_user", "created_time"),
        )
        ordering = ["-created_time"]

    def __str__(self):
        return f"{self.case_id}:{self.prev_owner_user}->{self.next_owner_user}"
