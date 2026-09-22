# -*- coding: utf-8 -*-
"""
KeenRunner 性能测试 Locust 施压入口(由执行管线以 `locust -f 本文件 --headless` 运行,
禁止 import backend 主包)。

环境变量契约(由 backend 执行管线在启动子进程前注入, 与管线双声明同步维护):
- PERF_SCENE_FILE: 施压场景文件路径(JSON, 结构见 _load_scene)
- PERF_RESULT_FILE: 结果分片输出目录(各进程写 result_{pid}.json, 管线合并)
- PERF_VERIFY_MIN_INTERVAL_SECONDS: 校验抽查进程级最小间隔(缺省10秒)
- PERF_VM_URL / PERF_METRICS_PUSH_INTERVAL: VictoriaMetrics上报配置(兼作熔断巡检周期)
- PERF_REPORT_CODE / PERF_PERF_CODE: 报告与任务标识(指标label与结果分片)

施压场景来源: krun_perf_scene.scene_items + 引用接口定义, 由管线在子进程启动前解析组装
(回查接口/数据集/环境三级链并补齐绝对地址), 引擎永不回查数据库。

角色语义(与 backend enums/perf_enum.PerfApiRole 取值逐字一致):
- measured 被测: 计入吞吐/RT/分位数, 按 weight 加权抽样, 归属事务时追加 TX 记账
- prepare  准备: 登录取token/造数, 虚拟用户启动时执行一次, 走独立会话且不触发
  locust 统计事件, 指标以引擎本地计数独立上报(完全隔离于业务指标)
- verify   校验: 正确性抽查, 进程级时间闸限频(默认每项每10秒至多1次),
  以 VFY 方法手工记账, 不计业务吞吐, 失败独立归因

指标口径: 接口请求由 locust client 自动记账; 事务(TX)与抽查(VFY)经 events.request
手工记账形成独立统计行(method 取 TX/VFY), 报告侧按 method 拆分维度, 口径互不污染。
分层判定: 传输层(连接错误/HTTP状态码>=300)记 locust 失败; 业务断言按场景断言口径
(all/sample_ratio)逐请求校验, 失败同样记入失败(带断言名前缀)。

熔断: error_rate_threshold>0 时各用户进程周期巡检自身业务错误率(样本量达
PERF_MIN_SAMPLES_FOR_COMPARE 后才判定), 超限进程标记自身结束原因并通知 master
(单进程时自派发)优雅停场, 管线按分片熔断标记区分自然结束与熔断中止。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_locustfile.py
@DateTime: 2026/9/16 10:30
"""
from __future__ import annotations

import logging
import os
import random
import sys
import time
from bisect import bisect_left
from collections import deque
from itertools import accumulate
from typing import Any, Deque, Dict, List, Optional, Tuple
from urllib.parse import urlparse

# locust以文件路径加载本文件, 同目录引擎模块不自动入sys.path, 显式注入保证可导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gevent  # noqa: E402
import orjson  # noqa: E402
import requests  # noqa: E402
from locust import HttpUser, LoadTestShape, between, events, task  # noqa: E402
from locust.exception import StopUser  # noqa: E402
from locust.runners import MasterRunner, WorkerRunner  # noqa: E402

from host_monitor import HostResourceMonitor  # noqa: E402
from metrics_push import ENV_PUSH_INTERVAL, MetricsPusher  # noqa: E402
from request_executor import (  # noqa: E402
    DATASET_RANDOM,
    DATASET_ROUND_ROBIN,
    RequestBuilder,
    apply_extract_variables,
    build_response_context,
    execute_assertions,
)
from reservoir import Reservoir  # noqa: E402
from result_writer import ResultWriter  # noqa: E402

# ============================ 常量与契约(引擎内独立声明) ============================

# 环境变量契约: 施压场景文件路径与抽查限频间隔
ENV_SCENE_FILE = "PERF_SCENE_FILE"
ENV_VERIFY_MIN_INTERVAL = "PERF_VERIFY_MIN_INTERVAL_SECONDS"

# 接口项角色: 与 backend enums/perf_enum.PerfApiRole 取值逐字一致(引擎内不可import枚举)
ROLE_MEASURED = "measured"
ROLE_PREPARE = "prepare"
ROLE_VERIFY = "verify"

# 场景施压语义: 与 PerfRunMode 取值一致(single为缺省值, journey 需在装载期拒绝;
# mixed 与 single 在引擎内共用同一加权循环, 无需单独常量)
RUN_MODE_SINGLE = "single"
RUN_MODE_JOURNEY = "journey"

# 负载模式: 与 PerfLoadMode 取值一致(stepped 由 shape 类接管用户数驱动,
# fixed/rps 走 CLI 参数; rps 差异仅在循环内 per-VU 节流)
LOAD_MODE_STEPPED = "stepped"
LOAD_MODE_RPS = "rps"

# 数据集场景分配策略: unique 为虚拟用户独占场景(见 _build_unique_scene_queues)
DATASET_UNIQUE = "unique"

# 手工记账 method 值: 事务与抽查在 locust 统计中的独立维度标识
METHOD_TRANSACTION = "TX"
METHOD_VERIFY = "VFY"
# 事务统计行名前缀(TX样本与统计行共用该命名, 管线据此归并事务维度)
TRANSACTION_NAME_PREFIX = "transaction:"

# 思考时间模式: 与 PerfDelayMode 取值一致
DELAY_MODE_UNIFORM = "uniform"

# 压测标记头名(被测端可据此做影子表/MQ隔离; 同步: backend enums/perf_enum.PERF_BATCH_HEADER_NAME)
PERF_BATCH_HEADER_NAME = "x-perf-batch"
# 蓄水池容量(同步: backend enums/perf_enum.PERF_RESERVOIR_SIZE)
RESERVOIR_CAPACITY = 20000
# 熔断判定的最小业务样本量(同步: backend enums/perf_enum.PERF_MIN_SAMPLES_FOR_COMPARE;
# 加压初期少量请求即出现高错误率属噪声, 不做样本量闸门会误熔断)
MIN_SAMPLES_FOR_CIRCUIT_BREAK = 50
# 校验抽查进程级默认最小间隔(秒): 抽查流量与吞吐量解耦, 以固定节奏验证读路径正确性
DEFAULT_VERIFY_MIN_INTERVAL_SECONDS = 10.0
# 准备段单请求超时(秒): 准备失败的用户退出施压, 不能因造数接口卡死拖挂整批虚拟用户
PREPARE_REQUEST_TIMEOUT = 10.0
# 施压请求缺省超时(秒): 场景项未显式给timeout时兜底, 避免无超时请求挂死虚拟用户
DEFAULT_REQUEST_TIMEOUT = 10.0
# 熔断巡检未配置时取的上报周期(秒): 与 PERF_METRICS_PUSH_INTERVAL 缺省值一致
DEFAULT_POLL_INTERVAL = 5.0
# 熔断通知消息类型(worker上报master停场; LocalRunner 自派发)
CIRCUIT_BREAK_MESSAGE_TYPE = "perf_circuit_break"


def _load_scene() -> Dict[str, Any]:
    """
    读取施压场景文件(路径来自 PERF_SCENE_FILE)。

    :return: 场景字典, 结构:
        {"run_mode": "single|mixed", "perf_batch_code": "PB-xxx", "run_duration": 60,
         "warmup_seconds": 20, "error_rate_threshold": 5.0, "inject_perf_tag": true,
         "assert_mode": "all|sample_ratio", "sample_ratio": 100.0,
         "session_variables": [{"key", "value", "desc"}],
         "items": [{"seq", "role", "api_code", "api_name", "api_version",
                    "request_method", "request_url", "request_port", "request_header",
                    "request_params", "request_form_data", "request_form_file",
                    "request_form_urlencoded", "request_text", "request_body",
                    "request_args_type", "extract_variables", "assert_validators",
                    "weight", "delay_mode", "delay_ms", "delay_ms_min", "delay_ms_max",
                    "transaction", "timeout",
                    "dataset": {"strategy", "scenes": [{"name", "head", "body"}]}}]}
    :raises RuntimeError: 路径未注入、文件缺失或结构非法(快速失败, 不静默零请求)
    """
    path = os.environ.get(ENV_SCENE_FILE, "").strip()
    if not path:
        raise RuntimeError(f"环境变量[{ENV_SCENE_FILE}]未注入, 无法构造施压场景")
    if not os.path.isfile(path):
        raise RuntimeError(f"施压场景文件不存在[{path}]")
    with open(path, "rb") as scene_file:
        scene = orjson.loads(scene_file.read())
    if not isinstance(scene, dict) or not isinstance(scene.get("items"), list) or not scene["items"]:
        raise RuntimeError("施压场景内容为空或缺少[items]字段")
    return scene


def _stats_name(item: Dict[str, Any]) -> str:
    """
    统计聚合口径: 方法 + 渲染前路径模板(参数化行与查询串不打散统计)。

    :param item: 单个接口项定义
    :return: locust request name, 如 "POST /base/auth/access_token"
    """
    request_url = str(item.get("request_url") or "")
    parsed = urlparse(request_url)
    path = parsed.path or request_url
    return f"{str(item.get('request_method') or 'GET').upper()} {path}"


def _resolve_host(items: List[Dict[str, Any]]) -> str:
    """
    取首个施压项的 scheme://host[:port] 作为 locust base_url(会话复用与Cookie域基准)。

    :param items: 接口项列表(地址已由管线补齐为绝对地址)
    :return: base_url, 无合法地址时返回空串
    """
    for item in items:
        parsed = urlparse(str(item.get("request_url") or ""))
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    return ""


# ============================ 场景装载(模块级, 每进程独立) ============================

SCENE: Dict[str, Any] = _load_scene()
SESSION_VARIABLES: List[Dict[str, Any]] = [
    item for item in (SCENE.get("session_variables") or []) if isinstance(item, dict)
]
ALL_ITEMS: List[Dict[str, Any]] = [item for item in SCENE["items"] if isinstance(item, dict)]
MEASURED_ITEMS: List[Dict[str, Any]] = [item for item in ALL_ITEMS if item.get("role") == ROLE_MEASURED]
PREPARE_ITEMS: List[Dict[str, Any]] = sorted(
    (item for item in ALL_ITEMS if item.get("role") == ROLE_PREPARE),
    key=lambda item: item.get("seq") or 0,
)
VERIFY_ITEMS: List[Dict[str, Any]] = [item for item in ALL_ITEMS if item.get("role") == ROLE_VERIFY]

RUN_MODE: str = str(SCENE.get("run_mode") or RUN_MODE_SINGLE)
if RUN_MODE == RUN_MODE_JOURNEY:
    # 链路编排(集合点/阶段并行/多步事务)未在当前版本实装, 明确拒绝而非静默退化为混合流量
    raise RuntimeError("施压引擎暂不支持journey链路模式, 请改用单接口(single)或混合流量(mixed)模式")
if not MEASURED_ITEMS:
    raise RuntimeError("施压场景没有被测接口项(measured), 请在场景中至少配置1个被测项")

BATCH_CODE: str = str(SCENE.get("perf_batch_code") or "")
INJECT_PERF_TAG: bool = bool(SCENE.get("inject_perf_tag"))
ERROR_RATE_THRESHOLD: float = float(SCENE.get("error_rate_threshold") or 0)
ASSERT_MODE_ALL: bool = str(SCENE.get("assert_mode") or "all") == "all"
SAMPLE_RATIO: float = float(SCENE.get("sample_ratio") or 100.0)
RUN_DURATION: int = int(SCENE.get("run_duration") or 0)
WARMUP_SECONDS: int = int(SCENE.get("warmup_seconds") or 0)
VERIFY_MIN_INTERVAL: float = float(
    os.environ.get(ENV_VERIFY_MIN_INTERVAL, "").strip() or DEFAULT_VERIFY_MIN_INTERVAL_SECONDS
)
POLL_INTERVAL: float = float(os.environ.get(ENV_PUSH_INTERVAL, "").strip() or DEFAULT_POLL_INTERVAL)
LOCUST_HOST: str = _resolve_host(MEASURED_ITEMS or ALL_ITEMS)
# 负载计划段(管线组装, stepped 专用; fixed 模式无消费方): 派生值(档数/总时长)由管线统一计算,
# 引擎只消费不推导, 保证报告快照/管线 deadline/shape 三处口径同源
LOAD_PLAN: Dict[str, Any] = SCENE.get("load") if isinstance(SCENE.get("load"), dict) else {}
LOAD_MODE: str = str(LOAD_PLAN.get("mode") or "fixed")
if LOAD_MODE == LOAD_MODE_STEPPED:
    _missing_load_keys = [
        key for key in ("rampup_stages", "step_duration", "sustain_duration", "max_users", "spawn_rate")
        if not LOAD_PLAN.get(key)
    ]
    if _missing_load_keys:
        raise RuntimeError(f"阶梯负载计划缺少字段: {_missing_load_keys}")
# RPS 吞吐模式: per-VU 节流间隔(全局口径: 每个虚拟用户独立按此间隔发起迭代,
# 合并稳态吞吐 ≈ target_rps; 多进程下各进程 VU 天然按比例分摊, 无需进程间协调;
# 并发池不足以跑出目标吞吐时 pacing 归零, 退化为全速施压, 上限即并发池能力)
PACING_INTERVAL: Optional[float] = None
if LOAD_MODE == LOAD_MODE_RPS:
    _rps_missing = [key for key in ("target_rps", "users") if not LOAD_PLAN.get(key)]
    if _rps_missing:
        raise RuntimeError(f"RPS吞吐负载计划缺少字段: {_rps_missing}")
    if float(LOAD_PLAN["target_rps"]) <= 0:
        raise RuntimeError("RPS吞吐负载计划目标吞吐必须大于0")
    PACING_INTERVAL = float(LOAD_PLAN["users"]) / float(LOAD_PLAN["target_rps"])


def _build_item_index() -> List[Dict[str, Any]]:
    """
    构建接口项索引(统计行名到压测接口资产的归因关系), 随结果分片落盘。

    校验项的记账键为 (stats_name, "VFY"), 管线按 role 推导, 索引内只登记真实方法。

    :return: 索引列表, 元素结构:
        {"seq": 1, "role": "measured", "api_code": "PERF-API-xxx", "api_name": "下单",
         "api_version": 3, "stats_name": "POST /order/create", "method": "POST",
         "transaction": "下单链路"}
    """
    return [
        {
            "seq": item.get("seq"),
            "role": item.get("role"),
            "api_code": item.get("api_code"),
            "api_name": item.get("api_name"),
            "api_version": item.get("api_version"),
            "stats_name": _stats_name(item),
            "method": str(item.get("request_method") or "GET").upper(),
            "transaction": str(item.get("transaction") or ""),
        }
        for item in ALL_ITEMS
    ]


ITEM_INDEX: List[Dict[str, Any]] = _build_item_index()


def _build_series_labels() -> Dict[Tuple[str, str], Dict[str, str]]:
    """
    构建统计序列附加label索引(metrics_push 拆分业务/事务/抽查曲线与接口归因依据)。

    :return: {(统计行名, method): {"role", "api_code", "transaction"}}
    """
    labels: Dict[Tuple[str, str], Dict[str, str]] = {}
    for item in ALL_ITEMS:
        if item.get("role") == ROLE_PREPARE:
            continue
        info = {
            "role": item.get("role"),
            "api_code": str(item.get("api_code") or ""),
            "transaction": str(item.get("transaction") or ""),
        }
        if item.get("role") == ROLE_VERIFY:
            labels[(_stats_name(item), METHOD_VERIFY)] = info
        else:
            labels[(_stats_name(item), str(item.get("request_method") or "GET").upper())] = info
            if item.get("transaction"):
                labels[(f"{TRANSACTION_NAME_PREFIX}{item['transaction']}", METHOD_TRANSACTION)] = {
                    "role": METHOD_TRANSACTION.lower(),
                    "api_code": "",
                    "transaction": str(item.get("transaction")),
                }
    return labels


SERIES_LABELS: Dict[Tuple[str, str], Dict[str, str]] = _build_series_labels()

# 本进程蓄水池(measured请求与TX事务圈共用; test_stop时随分片落盘, 管线合并算分位数)
MEASURED_SAMPLES: Reservoir = Reservoir(capacity=RESERVOIR_CAPACITY)
# 准备段指标注册表(引擎本地计数, 不进locust统计; 分片与VM prepare序列共用)
PREPARE_METRICS: Dict[str, Dict[str, float]] = {}
# 校验抽查进程级限频游标(gevent协作式调度下查改原子, 无需加锁)
VERIFY_LAST_RUN: Dict[str, float] = {}
# unique策略独占场景队列(存场景下标): 进程内虚拟用户各领一场景互不重叠(场景数不足由执行闸门在施压前拦截;
# 跨进程场景级不重叠的游标协调属后续版本范围, 多进程下不同进程会各自分配同一批场景)
UNIQUE_SCENE_QUEUES: Dict[int, Deque[int]] = {}


def _build_unique_scene_queues() -> None:
    """为声明了unique策略的接口项建立进程内独占场景队列(键为场景内序号, 存场景下标)。"""
    for item in ALL_ITEMS:
        dataset = item.get("dataset") or {}
        if str(dataset.get("strategy") or "") != DATASET_UNIQUE:
            continue
        scenes = [scene for scene in (dataset.get("scenes") or []) if isinstance(scene, dict)]
        if scenes:
            UNIQUE_SCENE_QUEUES[int(item.get("seq") or 0)] = deque(range(len(scenes)))


_build_unique_scene_queues()


def _warn_once(warn_key: str, message: str) -> None:
    """同键告警仅输出一次(海量虚拟用户同因退出时不刷屏, 计数仍在指标中体现)。"""
    if warn_key in _WARNED_KEYS:
        return
    _WARNED_KEYS.add(warn_key)
    logging.getLogger(__name__).warning("%s", message)


_WARNED_KEYS: set = set()


def _prepare_metric_entry(stats_name: str) -> Dict[str, float]:
    """取(或建)准备项指标累计器(注册表引用随分片与VM序列共享)。"""
    return PREPARE_METRICS.setdefault(stats_name, {"attempts": 0, "failures": 0, "total_rt_ms": 0})


def _inject_batch_header(request_kwargs: Dict[str, Any]) -> None:
    """
    注入压测标记头(被测端可据 x-perf-batch 做数据隔离与清理)。

    :param request_kwargs: 待发送的请求参数(就地修改headers)
    :return: None
    """
    if not INJECT_PERF_TAG:
        return
    headers = dict(request_kwargs.get("headers") or {})
    headers[PERF_BATCH_HEADER_NAME] = BATCH_CODE
    request_kwargs["headers"] = headers


def _measured_error_rate(stats: Any) -> Optional[float]:
    """
    计算业务口径错误率(仅统计真实HTTP请求行, TX/VFY记账行不参与熔断判定)。

    :param stats: locust RequestStats
    :return: 错误率百分比; 样本量未达熔断判定闸门时返回None(加压初期错误率为噪声)
    """
    total_requests = 0
    total_failures = 0
    for entry in stats.entries.values():
        if entry.method in (METHOD_TRANSACTION, METHOD_VERIFY) or not entry.name or str(entry.name) == "--":
            continue
        total_requests += entry.num_requests
        total_failures += entry.num_failures
    if total_requests < MIN_SAMPLES_FOR_CIRCUIT_BREAK:
        return None
    return total_failures / total_requests * 100


def _on_circuit_break_message(environment: Any, msg: Any) -> None:
    """
    熔断停场消息处理(master/单进程角色注册): 优雅退出并触发 test_stop 写分片。

    :param environment: locust Environment实例
    :param msg: 消息体(data含error_rate/threshold)
    :return: None
    """
    message_data = getattr(msg, "data", None) or {}
    logging.getLogger(__name__).warning(
        "业务错误率[%s%%]达到熔断阈值[%s%%], 停止施压",
        message_data.get("error_rate"), message_data.get("threshold"),
    )
    environment.runner.quit()


class ErrorRateBreaker:
    """周期巡检本进程业务错误率的熔断器(仅用户进程装载; master聚合口径不巡检)。"""

    def __init__(self, environment: Any, *, threshold_pct: float, poll_interval: float) -> None:
        """
        初始化熔断器。

        :param environment: locust Environment实例
        :param threshold_pct: 熔断错误率阈值(百分比)
        :param poll_interval: 巡检周期(秒)
        """
        self.environment = environment
        self.threshold_pct = threshold_pct
        self.poll_interval = poll_interval
        self._greenlet: Optional[gevent.Greenlet] = None

    def start(self) -> None:
        """启动巡检greenlet(幂等)。"""
        if self._greenlet is None:
            self._greenlet = gevent.spawn(self._monitor_loop)

    def _monitor_loop(self) -> None:
        """巡检主循环: 周期计算业务错误率, 超限则标记熔断并通知停场。"""
        while True:
            gevent.sleep(self.poll_interval)
            runner = self.environment.runner
            if str(runner.state) in ("stopped", "stopping"):
                return
            error_rate = _measured_error_rate(runner.stats)
            if error_rate is None or error_rate < self.threshold_pct:
                continue
            result_writer = getattr(self.environment, "_perf_result_writer", None)
            if result_writer is not None:
                result_writer.mark_stopped("circuit_break")
            # worker上报master停场; 单进程LocalRunner注册了同名消息, send_message自派发
            runner.send_message(
                CIRCUIT_BREAK_MESSAGE_TYPE,
                {"error_rate": round(error_rate, 2), "threshold": self.threshold_pct},
            )
            return


class WeightedPicker:
    """按 weight 加权随机抽取被测项(预构建累积权重表, 热路径仅二分查找)。"""

    def __init__(self, runners: List["ItemRunner"]) -> None:
        """
        初始化抽取器。

        :param runners: 被测项执行器列表(非空, 装载期已校验)
        """
        weights = [max(int(runner.item.get("weight") or 1), 1) for runner in runners]
        self.runners = runners
        self.cum_weights: List[int] = list(accumulate(weights))
        self.total_weight = self.cum_weights[-1]

    def pick(self) -> "ItemRunner":
        """按权重抽取本轮施压项。"""
        return self.runners[bisect_left(self.cum_weights, random.random() * self.total_weight)]


class ItemRunner:
    """
    单接口项施压执行器: 持有请求构造器与统计名, 与其他项共享该虚拟用户的变量池。

    数据集场景序即虚拟用户取场景序; unique策略场景由虚拟用户启动时分配后注入固定场景。
    """

    def __init__(self, item: Dict[str, Any], variable_pool: Dict[str, Any]) -> None:
        """
        初始化执行器。

        :param item: 接口项定义(见 _load_scene 的 items 元素)
        :param variable_pool: 该虚拟用户的共享变量池(引用)
        """
        self.item = item
        self.stats_name: str = _stats_name(item)
        self.role: str = str(item.get("role") or ROLE_MEASURED)
        self.transaction: str = str(item.get("transaction") or "")
        self.timeout: float = float(item.get("timeout") or DEFAULT_REQUEST_TIMEOUT)
        self.assert_validators: List[Dict[str, Any]] = item.get("assert_validators") or []
        self.extract_variables: List[Dict[str, Any]] = item.get("extract_variables") or []
        dataset = item.get("dataset") or {}
        strategy = str(dataset.get("strategy") or DATASET_ROUND_ROBIN)
        self.unique_seq: Optional[int] = int(item.get("seq") or 0) if strategy == DATASET_UNIQUE else None
        self.builder = RequestBuilder(
            request_definition=item,
            dataset_scenes=dataset.get("scenes") or [],
            variable_pool=variable_pool,
            scene_strategy=DATASET_RANDOM if strategy == DATASET_RANDOM else DATASET_ROUND_ROBIN,
        )

    def build_request(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """组装本项的下一次请求参数与本次合并后的变量池。"""
        return self.builder.build_request()

    def apply_extracts(self, response_context: Dict[str, Any]) -> None:
        """
        执行变量提取并写回共享变量池(失败项由 apply_extract_variables 记录, 不中断施压)。

        :param response_context: 提取上下文(见 build_response_context)
        :return: None
        """
        for snapshot in apply_extract_variables(self.extract_variables, response_context):
            if snapshot["success"]:
                self.builder.base_lookup[str(snapshot["name"])] = snapshot["extract_value"]

    def failed_assertion_names(self, snapshots: List[Dict[str, Any]]) -> List[str]:
        """
        归因断言失败项名称。

        :param snapshots: execute_assertions 产出的断言快照列表
        :return: 失败断言名列表(空列表表示全部通过)
        """
        return [
            str(snapshot.get("name") or snapshot.get("expr"))
            for snapshot in snapshots
            if not snapshot["success"]
        ]


@events.init.add_listener
def on_locust_init(environment: Any, **kwargs) -> None:
    """
    locust初始化: 注册结果分片写入/指标上报/熔断巡检(各角色自行裁剪)。

    熔断消息处理注册在非worker角色(单进程自派发, master接收worker上报);
    巡检只装在用户进程(LocalRunner/WorkerRunner), master聚合口径不触发熔断,
    避免master先停导致各worker分片丢失熔断标记。
    """
    runner = environment.runner
    if not isinstance(runner, WorkerRunner):
        runner.register_message(CIRCUIT_BREAK_MESSAGE_TYPE, _on_circuit_break_message)
    if not isinstance(runner, MasterRunner):
        result_writer = ResultWriter.from_environment(
            environment,
            samples=MEASURED_SAMPLES,
            prepare_metrics=PREPARE_METRICS,
            item_index=ITEM_INDEX,
            run_duration=RUN_DURATION,
            warmup_seconds=WARMUP_SECONDS,
        )
        if result_writer is not None:
            environment._perf_result_writer = result_writer
            result_writer.register()
        if ERROR_RATE_THRESHOLD > 0:
            breaker = ErrorRateBreaker(
                environment, threshold_pct=ERROR_RATE_THRESHOLD, poll_interval=max(POLL_INTERVAL, 1.0)
            )
            breaker.start()
            environment._perf_breaker = breaker
    metrics_pusher = MetricsPusher.from_environment(
        environment, series_labels=SERIES_LABELS, prepare_metrics=PREPARE_METRICS
    )
    if metrics_pusher is not None:
        environment._perf_metrics_pusher = metrics_pusher
        metrics_pusher.start()
    # 主机资源监控与业务统计同周期上报(单机多进程时 master 采集即代表整机, worker 不重复上报)
    host_monitor = HostResourceMonitor.from_environment(environment)
    if host_monitor is not None:
        environment._perf_host_monitor = host_monitor
        host_monitor.start()


@events.test_stop.add_listener
def on_locust_test_stop(environment: Any, **kwargs) -> None:
    """压测结束: 停止指标上报与主机资源采集greenlet(最后一次周期推送已在stop前完成)。"""
    metrics_pusher = getattr(environment, "_perf_metrics_pusher", None)
    if metrics_pusher is not None:
        metrics_pusher.stop()
    host_monitor = getattr(environment, "_perf_host_monitor", None)
    if host_monitor is not None:
        host_monitor.stop()


class PerfUser(HttpUser):
    """
    压测虚拟用户: 启动阶段分配独占行并跑准备段, 施压阶段按权重抽取被测项,
    循环外沿按进程级时间闸抽查校验项。

    单接口与混合流量共用同一加权循环(single场景恰有1个被测项, 权重退化无效);
    wait_time 为零, 节奏由被测项思考时间(gevent.sleep)控制;
    RPS 吞吐模式下另有每虚拟用户节流间隔(见 PACING_INTERVAL), 与思考时间合并取最大。
    """

    host = LOCUST_HOST
    wait_time = between(0.0, 0.0)

    def on_start(self) -> None:
        """
        虚拟用户启动: 建立私有变量池与各项执行器, 分配unique独占行, 顺序执行准备段。

        准备段用独立 requests 会话发送, 既避免把造数/登录请求计入压测指标,
        又在结束后把 Set-Cookie 合并进施压会话与抽查会话, 保留登录态复用能力。
        准备失败即退出该虚拟用户(准备不成立时施压只会产出噪声数据)。

        :return: None
        """
        self.variable_pool: Dict[str, Any] = {
            item.get("key"): item.get("value") for item in SESSION_VARIABLES if item.get("key")
        }
        # 接口定义变量覆盖会话初始池(defined > session, 与调试链路同口径); 多项同名按声明序后者生效
        for item in ALL_ITEMS:
            for kv in item.get("defined_variables") or []:
                if isinstance(kv, dict) and kv.get("key"):
                    self.variable_pool[kv["key"]] = kv.get("value")
        self.prepare_runners: List[ItemRunner] = [ItemRunner(item, self.variable_pool) for item in PREPARE_ITEMS]
        self.measured_runners: List[ItemRunner] = [ItemRunner(item, self.variable_pool) for item in MEASURED_ITEMS]
        self.verify_runners: List[ItemRunner] = [ItemRunner(item, self.variable_pool) for item in VERIFY_ITEMS]
        self.picker = WeightedPicker(self.measured_runners)
        self.verify_session = requests.Session()
        self._bind_unique_scenes()
        if self.prepare_runners:
            self._run_prepare_phase()

    def on_stop(self) -> None:
        """虚拟用户退出: 释放抽查会话连接。"""
        self.verify_session.close()

    def _bind_unique_scenes(self) -> None:
        """
        为unique策略项分配本虚拟用户独占数据场景(进程内队列领取, 互不重叠)。

        :return: None
        :raises StopUser: 场景队列已耗尽(场景数不足由执行闸门事前拦截, 此处为兜底)
        """
        for runner in (*self.prepare_runners, *self.measured_runners, *self.verify_runners):
            if runner.unique_seq is None:
                continue
            queue = UNIQUE_SCENE_QUEUES.get(runner.unique_seq)
            if not queue:
                _warn_once(
                    f"unique:{runner.unique_seq}",
                    f"接口项[{runner.stats_name}]unique策略数据场景已耗尽, 后续虚拟用户退出",
                )
                raise StopUser
            runner.builder.fixed_scene_index = queue.popleft()

    def _run_prepare_phase(self) -> None:
        """执行准备段: 单独会话顺序跑全部准备项, 结束后合并登录态到施压与抽查会话。"""
        with requests.Session() as prepare_session:
            for runner in self.prepare_runners:
                self._run_prepare_item(prepare_session, runner)
            self.client.cookies.update(prepare_session.cookies)
            self.verify_session.cookies.update(prepare_session.cookies)

    def _run_prepare_item(self, session: requests.Session, runner: ItemRunner) -> None:
        """
        执行单个准备项: 发送、传输层与断言判定、提取变量入池、累计准备指标。

        :param session: 准备段专用 requests 会话(不进 locust 统计)
        :param runner: 准备项执行器
        :return: None
        :raises StopUser: 传输层失败或业务断言未通过(该虚拟用户退出)
        """
        request_kwargs, merged_lookup = runner.build_request()
        _inject_batch_header(request_kwargs)
        metric = _prepare_metric_entry(runner.stats_name)
        metric["attempts"] += 1
        started_at = time.perf_counter()
        try:
            response = session.request(timeout=PREPARE_REQUEST_TIMEOUT, allow_redirects=False, **request_kwargs)
        except requests.RequestException as e:
            metric["failures"] += 1
            _warn_once(f"prepare:{runner.stats_name}", f"准备项[{runner.stats_name}]请求失败: {type(e).__name__}: {e}")
            raise StopUser
        metric["total_rt_ms"] += (time.perf_counter() - started_at) * 1000
        if response.status_code >= 300:
            metric["failures"] += 1
            _warn_once(
                f"prepare:{runner.stats_name}",
                f"准备项[{runner.stats_name}]HTTP状态码[{response.status_code}]大于等于300, 传输层判定失败",
            )
            raise StopUser
        response_context = build_response_context(response, request_kwargs, merged_lookup)
        runner.apply_extracts(response_context)
        failed_names = runner.failed_assertion_names(
            execute_assertions(assert_validators=runner.assert_validators, response_context=response_context)
        )
        if failed_names:
            metric["failures"] += 1
            _warn_once(f"prepare:{runner.stats_name}", f"准备项[{runner.stats_name}]业务断言未通过: {'、'.join(failed_names)}")
            raise StopUser

    def _resolve_delay_seconds(self, runner: ItemRunner) -> float:
        """
        解析被测项思考时间(秒); uniform模式取区间随机。

        :param runner: 被测项执行器
        :return: 思考时间秒数
        """
        item = runner.item
        if str(item.get("delay_mode") or "") == DELAY_MODE_UNIFORM:
            low = float(item.get("delay_ms_min") or 0)
            high = float(item.get("delay_ms_max") or 0)
            return random.uniform(min(low, high), max(low, high)) / 1000
        return float(item.get("delay_ms") or 0) / 1000

    def _assertions_due(self) -> bool:
        """按场景断言口径判定本次请求是否执行业务断言(sample_ratio模式按比例抽样)。"""
        if ASSERT_MODE_ALL:
            return True
        return random.random() * 100 < SAMPLE_RATIO

    @task
    def execute_iteration(self) -> None:
        """
        单轮施压循环: 抽取被测项发请求并记账(TX) -> 思考时间 -> 按时间闸抽查校验项 -> RPS节流。

        :return: None
        """
        iteration_started_at = time.perf_counter()
        self._execute_measured_once()
        self._execute_verify_if_due()
        # RPS 吞吐模式: 本轮起点到此刻(含请求/思考/抽查)不足节流间隔则补足等待;
        # 思考时间已被计入 elapsed, 与节流自然合并不双重等待
        if PACING_INTERVAL is not None:
            elapsed = time.perf_counter() - iteration_started_at
            if elapsed < PACING_INTERVAL:
                gevent.sleep(PACING_INTERVAL - elapsed)

    def _execute_measured_once(self) -> None:
        """执行一次被测请求: 渲染发送 -> 传输层与断言双层判定 -> 蓄水池采样 -> TX记账 -> 思考时间。"""
        runner = self.picker.pick()
        request_kwargs, merged_lookup = runner.build_request()
        _inject_batch_header(request_kwargs)
        transaction_started_at = time.perf_counter()
        failure_reason: Optional[str] = None
        with self.client.request(
                catch_response=True, name=runner.stats_name, timeout=runner.timeout, **request_kwargs
        ) as response:
            # request_meta由locust回填: response_time/length为接口RT与字节数的权威口径
            request_meta = getattr(response, "request_meta", {}) or {}
            rt_ms = float(request_meta.get("response_time") or 0)
            content_length = int(request_meta.get("response_length") or 0)
            transport_error: Optional[Any] = getattr(response, "error", None)
            if transport_error or response.status_code >= 300:
                failure_reason = (
                    str(transport_error) if transport_error
                    else f"HTTP状态码[{response.status_code}]大于等于300, 传输层判定失败"
                )
            else:
                response_context = build_response_context(response, request_kwargs, merged_lookup)
                runner.apply_extracts(response_context)
                # 业务断言按场景口径执行; 失败同样计为请求失败(明细已含在断言快照)
                if self._assertions_due():
                    failed_names = runner.failed_assertion_names(
                        execute_assertions(assert_validators=runner.assert_validators, response_context=response_context)
                    )
                    if failed_names:
                        failure_reason = f"业务断言未通过: {'、'.join(failed_names)}"
                if failure_reason is None:
                    response.success()
            if failure_reason is not None:
                response.failure(failure_reason)
            MEASURED_SAMPLES.record(
                ts_ms=int(time.time() * 1000),
                rt_ms=rt_ms,
                ok=failure_reason is None,
                name=runner.stats_name,
                txn=runner.transaction,
            )
        if runner.transaction:
            # 单步事务圈耗时=请求耗时(含提取断言开销); 思考时间在圈外, 不计入事务RT
            transaction_rt_ms = int((time.perf_counter() - transaction_started_at) * 1000)
            self.environment.events.request.fire(
                request_type=METHOD_TRANSACTION,
                name=f"{TRANSACTION_NAME_PREFIX}{runner.transaction}",
                response_time=transaction_rt_ms,
                response_length=content_length,
                exception=failure_reason,
            )
            MEASURED_SAMPLES.record(
                ts_ms=int(time.time() * 1000),
                rt_ms=transaction_rt_ms,
                ok=failure_reason is None,
                name=f"{TRANSACTION_NAME_PREFIX}{runner.transaction}",
                txn=runner.transaction,
            )
        delay_seconds = self._resolve_delay_seconds(runner)
        if delay_seconds > 0:
            gevent.sleep(delay_seconds)

    def _execute_verify_if_due(self) -> None:
        """
        按进程级时间闸抽查校验项: 每项至多每 VERIFY_MIN_INTERVAL 秒执行一次。

        :return: None
        """
        now = time.monotonic()
        for runner in self.verify_runners:
            if now - VERIFY_LAST_RUN.get(runner.stats_name, 0.0) < VERIFY_MIN_INTERVAL:
                continue
            VERIFY_LAST_RUN[runner.stats_name] = now
            self._execute_verify_request(runner)

    def _execute_verify_request(self, runner: ItemRunner) -> None:
        """
        执行一次正确性抽查: 独立会话发送(不触发locust自动记账), 以VFY方法手工记账。

        :param runner: 校验项执行器
        :return: None
        """
        request_kwargs, merged_lookup = runner.build_request()
        _inject_batch_header(request_kwargs)
        started_at = time.perf_counter()
        failure_reason: Optional[str] = None
        response: Optional[requests.Response] = None
        try:
            response = self.verify_session.request(timeout=runner.timeout, allow_redirects=False, **request_kwargs)
        except requests.RequestException as e:
            failure_reason = f"请求失败: {type(e).__name__}: {e}"
        if response is not None and response.status_code >= 300:
            failure_reason = f"HTTP状态码[{response.status_code}]大于等于300, 传输层判定失败"
        if response is not None and failure_reason is None:
            response_context = build_response_context(response, request_kwargs, merged_lookup)
            runner.apply_extracts(response_context)
            failed_names = runner.failed_assertion_names(
                execute_assertions(assert_validators=runner.assert_validators, response_context=response_context)
            )
            if failed_names:
                failure_reason = f"业务断言未通过: {'、'.join(failed_names)}"
        rt_ms = int((time.perf_counter() - started_at) * 1000)
        content_length = len(response.content or b"") if response is not None else 0
        self.environment.events.request.fire(
            request_type=METHOD_VERIFY,
            name=runner.stats_name,
            response_time=rt_ms,
            response_length=content_length,
            exception=failure_reason,
        )


# ============================ 阶梯负载驱动(stepped 专用) ============================

# 条件式类定义: locust 发现模块内存有 LoadTestShape 子类即接管用户数驱动(忽略 -u/-r/--run-time),
# 因此仅在 load.mode=stepped 时定义 shape 类; fixed 模式无 shape 类, CLI 参数路径与既有行为一致。
if LOAD_MODE == LOAD_MODE_STEPPED:

    class PerfStepLoadShape(LoadTestShape):
        """
        阶梯负载形状: 自起始并发起每档持续秒数上调一档递增并发, 至峰值后保持至计划结束。

        档数/总时长等派生值由执行管线统一计算并随 load 段下发(单一事实源),
        tick 返回 None 即通知 locust 优雅停场(等待在途用户完成收尾, 与 --stop-timeout 配合)。
        """

        def tick(self) -> Optional[Tuple[int, float]]:
            """
            计算当前时刻的目标并发。

            :return: (目标用户数, 每秒拉起用户数); 阶梯计划走完后返回 None 结束施压
            """
            elapsed = self.get_run_time()
            rampup_seconds = int(LOAD_PLAN["rampup_stages"]) * int(LOAD_PLAN["step_duration"])
            if elapsed < rampup_seconds:
                stage = int(elapsed // int(LOAD_PLAN["step_duration"]))
                return min(int(LOAD_PLAN["start_users"]) + stage * int(LOAD_PLAN["increment"]),
                           int(LOAD_PLAN["max_users"])), float(LOAD_PLAN["spawn_rate"])
            if elapsed < rampup_seconds + int(LOAD_PLAN["sustain_duration"]):
                return int(LOAD_PLAN["max_users"]), float(LOAD_PLAN["spawn_rate"])
            return None
