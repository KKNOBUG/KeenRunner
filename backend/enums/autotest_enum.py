# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_enum
@DateTime: 2026/1/3 10:42
"""
from backend.enums.base_error_enum import StringEnum


class AutoTestCaseAttr(StringEnum):
    ATTR1 = "正用例"
    ATTR2 = "反用例"


class AutoTestCaseType(StringEnum):
    PUBLIC_SCRIPT = "公共脚本"
    PRIVATE_SCRIPT = "用户脚本"


class AutoTestTagType(StringEnum):
    API = "接口"
    SCRIPT = "脚本"


class AutoTestReportType(StringEnum):
    EXEC1 = "单笔执行"
    EXEC2 = "批量执行"
    EXEC3 = "定时执行"


class AutoTestStepType(StringEnum):
    """请求参数类型枚举"""
    TCP = "TCP请求"
    HTTP = "HTTP请求"
    DATABASE = "数据库请求"
    PYTHON = "执行代码请求(Python)"
    IF = "条件分支"
    WAIT = "等待控制"
    LOOP = "循环结构"
    QUOTE = "引用公共用例"


class AutoTestLoopMode(StringEnum):
    # 循环模式：次数循环(loop_mode + loop_maximums + loop_interval)
    COUNT = "次数循环"
    # 循环模式：对象循环(loop_mode + loop_iterable + loop_iter_idx + loop_iter_val + loop_interval)
    ITERABLE = "对象循环"
    # 循环模式：字典循环(loop_mode + loop_iterable + loop_iter_idx + loop_iter_key + loop_iter_val + loop_interval)
    DICT = "字典循环"
    # 循环模式：条件循环(loop_mode + conditions + loop_interval + loop_timeout)
    CONDITION = "条件循环"


class AutoTestLoopErrorStrategy(StringEnum):
    CONTINUE = "继续下一次循环"
    BREAK = "中断循环"
    STOP = "停止整个用例执行"
