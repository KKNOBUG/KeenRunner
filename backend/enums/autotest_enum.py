# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_enum
@DateTime: 2026/1/3 10:42
"""
from backend.enums.base_enum_cls import StringEnum


class AutoTestCaseAttr(StringEnum):
    TRUE_CASE = "正用例"
    FALSE_CASE = "反用例"


class AutoTestCaseType(StringEnum):
    PUBLIC_API = "公共接口"
    PUBLIC_SCRIPT = "公共脚本"
    PRIVATE_SCRIPT = "用户脚本"


# 公共标识：不可引用其他脚本、不可绑定数据源、不允许打标签
PUBLIC_CASE_TYPES = (AutoTestCaseType.PUBLIC_SCRIPT, AutoTestCaseType.PUBLIC_API)


class AutoTestReportType(StringEnum):
    SYNC_EXEC = "同步执行"
    ASYNC_EXEC = "异步执行"
    DEBUG_EXEC = "调试执行"
    SCHEDULE_EXEC = "定时执行"


class AutoTestStepType(StringEnum):
    """请求参数类型枚举"""
    USER_VARIABLES = "用户变量"
    IF = "条件分支"
    WAIT = "等待控制"
    LOOP = "循环结构"
    TCP = "TCP请求"
    HTTP = "HTTP请求"
    PYTHON = "代码请求(Python)"
    DATABASE = "数据库请求"
    REDIS = "Redis请求"
    QUOTE = "引用公共脚本"
    DIFF = "报文比对"
    ASSERT = "断言"


class AutoTestLoopMode(StringEnum):
    # 循环模式：次数循环(loop_mode + loop_maximums + loop_interval；loop_maximums支持正整数或变量占位符)
    COUNT = "次数循环"
    # 循环模式：列表循环(loop_mode + loop_iterable + loop_interval；会话变量固定loop_index/loop_value)
    LIST = "列表循环"
    # 循环模式：字典循环(loop_mode + loop_iterable + loop_interval；会话变量固定loop_index/loop_key/loop_value)
    DICT = "字典循环"
    # 循环模式：条件循环(loop_mode + loop_conditions + loop_interval + loop_timeout)
    CONDITION = "条件循环"


class AutoTestLoopErrorStrategy(StringEnum):
    BREAK = "中断循环"
    STOP = "停止整个用例执行"
    CONTINUE = "继续下一次循环"


class AutoTestAssertionOperation(StringEnum):
    """
    断言/条件分支/条件循环中condition_compare的合法取值，与AutoTestToolService.compare_assertion支持集一致；新增比较方式时在此扩展成员即可。
    """
    EQUAL = "等于"
    NOT_EQUAL = "不等于"
    GREATER_THAN = "大于"
    GREATER_OR_EQUAL = "大于等于"
    LESS_THAN = "小于"
    LESS_OR_EQUAL = "小于等于"
    LENGTH_EQUAL = "长度等于"
    ARRAY_LENGTH_EQUAL = "数组长度等于"
    CONTAINS = "包含"
    NOT_CONTAINS = "不包含"
    IN_SET = "属于集合"
    NOT_IN_SET = "不属于集合"
    STARTS_WITH = "以...开始"
    ENDS_WITH = "以...结束"
    NOT_EMPTY = "非空"
    IS_EMPTY = "为空"


class AutoTestTaskType(StringEnum):
    """
    任务业务类型：Task定义分类、Beat扫描过滤、执行记录分类均根据此区分。
    AUTOTEST_API保留历史值autotest_api，与存量任务行兼容。
    """
    AUTOTEST_API = "autotest_api"  # 用例编排（任务列表定时/手动）
    CASE_STEP_EXEC = "用例执行"  # 单用例步骤树异步执行
    EXPORT_CASE_DATA = "导出用例数据"  # 公共接口HEAD/BODY导出
    EXPORT_CASE_SCRIPT = "导出公共接口"  # 公共接口脚本模板导出
    SCHEDULE_SCAN = "调度扫描"  # Beat 扫描派发（通常不写 Record）


class AutoTestTaskTriggerType(StringEnum):
    """任务触发来源：记录表用于区分手动执行与定时扫描。"""
    MANUAL = "手动执行"
    SCHEDULE = "定时执行"


class AutoTestTaskPeriodicSwitch(StringEnum):
    """任务周期表达式：配合 crontab 控制调度触发次数（字段 task_periodic_expr）。"""
    ONLY_ONCE = "执行1次"
    INFINITY = "执行N次"


class AutoTestTaskStatus(StringEnum):
    PENDING = "等待执行"
    RUNNING = "正在执行"
    SUCCESS = "成功"
    FAILURE = "失败"
    PARTIAL_SUCCESS = "部分成功"


class AutoTestReqArgsType(StringEnum):
    RAW = "raw"
    NONE = "none"
    JSON = "json"
    XML = "xml"
    PARAMS = "params"
    FORM_DATA = "form-data"
    X_WWW_FORM_URLENCODED = "x-www-form-urlencoded"


class AutoTestDataBaseType(StringEnum):
    MYSQL = "mysql"
    ORACLE = "oracle"
    TDSQL = "tdsql"


class AutoTestConfigNodeType(StringEnum):
    API = "api"
    DB = "database"
    REDIS = "redis"
    FILE = "file"
