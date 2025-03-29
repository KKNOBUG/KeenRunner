# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : testcase_priority_enum.py
@DateTime: 2025/3/28 15:16
"""
from backend.enums.base_enum_cls import StringEnum


class TestCasePriorityEnum(StringEnum):
    """
    测试案例风险级别枚举值
    """
    P1 = "低"
    P2 = "中"
    P3 = "高"
    P4 = "危"
