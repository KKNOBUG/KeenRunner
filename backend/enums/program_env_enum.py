# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : program_env_enum.py
@DateTime: 2025/4/2 19:44
"""
from backend.enums.base_enum_cls import StringEnum


class TestCasePriorityEnum(StringEnum):
    """
    应用系统环境
    """
    UAT = ("Use Acceptance Test", "用户验收测试")
    SIT = ("System Integrate Test", "系统整合测试")
    PP = ("Pre production", "预生产")
    PET = ("Performance Evaluation Test", "性能评估测试")
    SIM = ("Simulation", "仿真测试")
    PRO = ("production", "生产测试")
