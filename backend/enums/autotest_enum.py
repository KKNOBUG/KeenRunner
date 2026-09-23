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
    TRUE_CASE = "正案例"
    FALSE_CASE = "反案例"


class AutoTestCaseType(StringEnum):
    PUBLIC_API = "公共接口"
    PUBLIC_SCRIPT = "公共脚本"
    PRIVATE_SCRIPT = "用户脚本"


# 公共标识：可以被「引用公共脚本/接口」步骤引用；自身不可引用其他脚本、不可绑定数据源；
PUBLIC_CASE_TYPES = (AutoTestCaseType.PUBLIC_SCRIPT, AutoTestCaseType.PUBLIC_API,)

# 标签管控：仅公共接口不允许打标签，公共脚本/用户脚本均可打标签；
NO_TAG_CASE_TYPES = (AutoTestCaseType.PUBLIC_API,)


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
    QUOTE_PUBLIC_SCRIPT = "引用公共脚本"
    QUOTE_PUBLIC_API = "引用公共接口"
    DIFF = "报文比对"
    ASSERT = "断言"
    EXTRACT = "提取"


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
    NOT_EMPTY = "不为空"
    IS_EMPTY = "为空"


class AutoTestTaskType(StringEnum):
    """
    任务业务类型：Task定义分类、Beat扫描过滤、执行记录分类均根据此区分。

    - MULTIPLE_CASE_EXECUTE 为 krun_autotest_task.task_type 唯一实际取值（模型默认值，Beat 扫描按此过滤）；
    - 其余成员仅作为 krun_autotest_record.task_type 执行记录分类；
    - 历史存储值(autotest_api/用例执行/调度扫描/导出用例数据/导出公共接口)由
      backend/scripts/task_type_rename_migrate.sql 一次性迁移至当前存储值；
      部署含本次改动的代码前必须先执行该脚本，否则存量行反序列化失败、Beat 扫描失效。
    """
    MULTIPLE_CASE_EXECUTE = "多个用例执行"  # 用例编排：任务列表定时/手动，多用例整树执行
    SINGLE_CASE_EXECUTE = "单个用例执行"  # 单用例步骤树异步执行
    SCHEDULE_SCANNER = "调度任务扫描"  # Beat 扫描派发（通常不写 Record）
    EXPORT_PUBLIC_API_DATAGRAM = "公共接口报文导出"  # 公共接口请求头/体报文导出
    EXPORT_PUBLIC_API_SCRIPT = "公共接口导出"  # 公共接口脚本导出
    IMPORT_PUBLIC_API_SCRIPT = "公共接口导入"  # 公共接口脚本导入
    PUBLIC_API_TO_SCRIPT = "单接口脚本生成"  # 公共接口转脚本
    GENERATE_TEST_CASE = "测试案例生成"  # 测试案例生成


class AutoTestTaskExecuteMode(StringEnum):
    """任务执行模式：存储值与存量数据中文文案保持一致。"""
    PARALLEL = "并行执行"
    SERIAL = "串行执行"


class AutoTestEnvMode(StringEnum):
    """任务环境模式：cases_execute_config.env_mode存储枚举。"""
    SINGLE = "single"
    MULTIPLE = "multiple"


class AutoTestTaskStatus(StringEnum):
    PENDING = "等待执行"
    RUNNING = "正在执行"
    SUCCESS = "成功"
    FAILURE = "失败"
    PARTIAL_SUCCESS = "部分成功"


class AutoTestTaskTriggerType(StringEnum):
    """任务触发来源：记录表用于区分手动执行与定时扫描。"""
    MANUAL = "手动执行"
    SCHEDULE = "定时执行"


class AutoTestTaskPeriodicMode(StringEnum):
    """任务时效。"""
    ONLY_ONCE = "执行1次"
    UNBOUNDED = "执行N次"


class AutoTestTaskCycleType(StringEnum):
    """任务调度周期。"""
    DAY = "daily"
    WEEK = "weekly"
    MONTH = "monthly"


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
    APP = "app"
    DB = "database"
    REDIS = "redis"
    FILE = "file"
