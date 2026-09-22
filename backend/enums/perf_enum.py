# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_enum.py
@DateTime: 2026/9/14 10:30
"""
from backend.enums.base_enum_cls import StringEnum


class PerfLoadMode(StringEnum):
    """
    压测施压模式：fixed 固定并发(P0 实现)；stepped 阶梯加压(P1 实现，任务表字段先行建齐避免二次表变更)；
    rps 吞吐模式(固定并发池上限 + 每虚拟用户节流, 稳态吞吐≈目标RPS)。
    """
    FIXED = "fixed"
    STEPPED = "stepped"
    RPS = "rps"


class PerfPresetStatus(StringEnum):
    """
    负载预设最近一次执行状态：idle 仅配置未执行；stopping 为用户请求停止的过渡态，由执行管线感知后落 stopped。
    """
    IDLE = "idle"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPING = "stopping"
    STOPPED = "stopped"


class PerfReportStatus(StringEnum):
    """
    压测报告执行状态(报告为快照实体，状态机为任务执行状态的执行期子集)。
    """
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class PerfApiRole(StringEnum):
    """
    压测接口项的指标口径角色(热路径唯一允许的标注维度)。

    MEASURED 被测: 计入吞吐/RT/分位数与事务
    PREPARE  准备: 登录取token、造数, 走独立会话且不触发统计事件, 完全隔离于业务指标
    VERIFY   校验: 正确性抽查, 不计吞吐, 失败计入错误归因
    """
    MEASURED = "measured"
    PREPARE = "prepare"
    VERIFY = "verify"


class PerfRunMode(StringEnum):
    """
    场景施压语义：single 单接口；mixed 多接口加权混合(接口间独立并发)；
    journey 业务链路(接口串/并行成圈, 产出一笔事务样本)。
    """
    SINGLE = "single"
    MIXED = "mixed"
    JOURNEY = "journey"


class PerfDelayMode(StringEnum):
    """思考时间模式：fixed 固定值；uniform 区间随机(模拟真实用户思考行为)。"""
    FIXED = "fixed"
    UNIFORM = "uniform"


class PerfPhaseExecution(StringEnum):
    """链路阶段内接口项的执行方式：serial 串行(依 seq 顺序)；parallel 阶段内并发(受 max_parallel 约束)。"""
    SERIAL = "serial"
    PARALLEL = "parallel"


class PerfDatasetStrategy(StringEnum):
    """
    参数化行分配策略(属于场景用法层, 不属于数据资产层)。

    ROUND_ROBIN 循环轮询(行可重复使用)
    UNIQUE     每个虚拟用户独占一行(跨进程不重叠, 行数不足时拒绝施压)
    RANDOM     随机取行
    """
    ROUND_ROBIN = "round_robin"
    UNIQUE = "unique"
    RANDOM = "random"


class PerfDatasetSource(StringEnum):
    """数据集来源：file 文件上传解析；manual 页面表格录入；job 造数作业产出(溯源 job_id/job_code)。"""
    FILE = "file"
    MANUAL = "manual"
    JOB = "job"


class PerfJobType(StringEnum):
    """
    数据作业类型(带外作业, 复用功能执行链): prepare 压测前造数/铺底并回写数据集;
    verify 压测后校验(对压测产生数据做库面断言, 独立报告); cleanup 压测后按标记清理。
    """
    PREPARE = "prepare"
    VERIFY = "verify"
    CLEANUP = "cleanup"


class PerfJobStatus(StringEnum):
    """数据作业执行状态: pending 排队; running 执行中; success 成功; failed 失败(终态)。"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class PerfApiSource(StringEnum):
    """压测接口录入来源(单向拷贝并留溯源, 不建引用关系)。"""
    MANUAL = "manual"
    PUBLIC_API = "public_api"
    HTTP_STEP = "http_step"
    CURL = "curl"
    OPENAPI = "openapi"


class PerfAssertMode(StringEnum):
    """断言执行口径：all 逐请求断言(错误率含业务断言失败)；sample_ratio 按比例抽样断言。"""
    ALL = "all"
    SAMPLE_RATIO = "sample_ratio"


class PerfDebugState(StringEnum):
    """压测接口最近一次调试结果(施压前预检闸门依据)。"""
    NEVER = "never"
    SUCCESS = "success"
    FAILED = "failed"


class PerfStoppedReason(StringEnum):
    """
    压测结束原因：区分「到期自然结束/人工终止/熔断中止/引擎异常/超时兼底」,
    没达标不等于执行失败, 两者必须分开表达。
    """
    COMPLETED = "completed"
    MANUAL = "manual"
    CIRCUIT_BREAK = "circuit_break"
    ENGINE_ERROR = "engine_error"
    TIMEOUT_KILL = "timeout_kill"


class PerfTargetScope(StringEnum):
    """SLA 判定对象层级。"""
    GLOBAL = "global"
    API = "api"
    TRANSACTION = "transaction"


class PerfTargetMetric(StringEnum):
    """SLA 可判定指标(与报告字段名逐字一致, 避免判定与展示两套口径)。"""
    RPS = "rps"
    SUCCESS_RPS = "success_rps"
    TOTAL_REQUESTS = "total_requests"
    AVG_RT = "avg_rt"
    P90 = "p90"
    P95 = "p95"
    P99 = "p99"
    ERROR_RATE = "error_rate"


class PerfTargetOp(StringEnum):
    """SLA 比较运算符。"""
    GT = "gt"
    GE = "ge"
    LT = "lt"
    LE = "le"
    EQ = "eq"


class PerfTargetSeverity(StringEnum):
    """SLA 未达成时的严重级：fail 判失败；warn 仅告警不改结论。"""
    FAIL = "fail"
    WARN = "warn"


class PerfComparisonMode(StringEnum):
    """
    多记录对比/汇总模式(krun_perf_comparison)。

    compare 横向对比: 指定基准, 逐份报告相对基准的指标变化与配置差异;
    merge 汇总合并: 同场景多份报告视为并行实例聚合成一份视图(限同场景);
    hybrid 两者兼出。设计§3.7 对齐 BrickCore PerfComparisonReport。
    """
    COMPARE = "compare"
    MERGE = "merge"
    HYBRID = "hybrid"


# 准备段与抽查段不计入业务吞吐: 参与指标汇总的角色集合(仅 MEASURED 进业务指标)
PERF_BUSINESS_ROLES = (PerfApiRole.MEASURED,)
# 集合点屏障默认超时秒数(到达并行度或超时二者取先放行, 禁止裸 busy-wait)
PERF_BARRIER_TIMEOUT_SECONDS = 30
# 统计可信度常量: 样本量/时长不足时不得下 SLA 与对比结论(防止用噪声下结论)
PERF_MIN_SAMPLES_FOR_COMPARE = 50
PERF_MIN_DURATION_FOR_SLA = 60
# 每进程蓄水池容量(对齐业界合并样本上限, 超限等概率替换)
PERF_RESERVOIR_SIZE = 20000
# 默认预热剔除上限(超出须显式指定, 防止把整段压测剔成空样本)
PERF_WARMUP_DEFAULT_MAX = 300
# 压测标记头名(被测端可据此做影子表/MQ 隔离); 集中声明便于双方对齐
PERF_BATCH_HEADER_NAME = "x-perf-batch"
