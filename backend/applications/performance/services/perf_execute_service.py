# -*- coding: utf-8 -*-
"""
压测执行服务：执行下发、停止链与 Celery 编排管线（backend 主进程侧）。

职责边界：
- run_task/stop_task：视图侧业务（状态校验与原子状态迁移），进程操作不在此层；
- execute_pipeline：Celery 任务编排主体（装载场景 → 建报告 → 拉起引擎 → 等待循环
  → 分片合并聚合 → 落库回填），执行期不持有长 DB 事务（等待循环仅轮询状态列），
  任何异常兜底置 failed 保证任务不卡 running。

引擎环境变量契约（PERF_ENV_*）：与 locust_engine 引擎文件的 ENV_* 字符串逐字对齐；
引擎子包禁止 import backend，契约常量在两侧独立声明，新增契约字段须同步引擎文件
与本清单。施压场景由本服务回查 krun_perf_scene/krun_perf_api/krun_perf_dataset 与
环境三级链后组装为自包含 scene.json 经路径下发（百KB级报文不走环境变量，
Linux 单变量 32KB 上限 MAX_ARG_STRLEN 不变），引擎子进程永不回查数据库。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_execute_service.py
@DateTime: 2026/9/14 15:30
"""
from __future__ import annotations

import asyncio
import hashlib
import math
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import orjson
import psutil
from tortoise.expressions import Q

from backend.applications.autotest.dependencies import get_autotest_api_services
from backend.applications.autotest.services.autotest_step_debug_service import (
    EnvEndpoint,
    StepDebugService,
)
from backend.applications.base.services.scaffold import unique_identify
from backend.applications.performance.locust_engine.request_executor import build_request_url
from backend.applications.performance.models.perf_api_model import PerfApiModel
from backend.applications.performance.models.perf_dataset_model import PerfDatasetModel
from backend.applications.performance.models.perf_report_model import PerfReportModel
from backend.applications.performance.models.perf_scene_model import PerfSceneModel
from backend.applications.performance.models.perf_task_model import PerfTaskModel
from backend.applications.performance.schemas.perf_task_schema import PerfTaskLocate
from backend.applications.performance.services.perf_asset_utils import diff_report_pair, summarize_report_diff
from backend.applications.performance.services.perf_process_registry import (
    KILL_WAIT_TIMEOUT,
    PERF_PROCESS_REGISTRY,
)
from backend.applications.performance.services.perf_result_aggregator import (
    compute_report_metrics,
    merge_result_shards,
    parse_iso,
)
from backend.applications.performance.services.perf_task_crud import STEPPED_REQUIRED_FIELDS, PerfTaskCrud
from backend.common.url_utils import build_absolute_http_url, is_absolute_http_url
from backend.configure import LOGGER, PROJECT_CONFIG
from backend.core.exceptions import ParameterException
from backend.enums import (
    PERF_MIN_SAMPLES_FOR_COMPARE,
    PERF_WARMUP_DEFAULT_MAX,
    AutoTestConfigNodeType,
    AutoTestStepType,
    PerfApiRole,
    PerfDatasetStrategy,
    PerfLoadMode,
    PerfReportStatus,
    PerfRunMode,
    PerfStoppedReason,
    PerfTaskStatus,
)

# ---------- 引擎环境变量契约(与 locust_engine 引擎文件 ENV_* 逐字对齐, 禁止单侧擅改) ----------
PERF_ENV_SCENE_FILE = "PERF_SCENE_FILE"
PERF_ENV_RESULT_FILE = "PERF_RESULT_FILE"
PERF_ENV_VM_URL = "PERF_VM_URL"
PERF_ENV_PUSH_INTERVAL = "PERF_METRICS_PUSH_INTERVAL"
PERF_ENV_REPORT_CODE = "PERF_REPORT_CODE"
PERF_ENV_PERF_CODE = "PERF_PERF_CODE"

# 引擎契约全量清单: perf_locustfile 2 项 + metrics_push 4 项 + result_writer 3 项(去重);
# host_monitor 复用 metrics_push 的 VM/周期/标识四项, 不新增环境变量,
# 冒烟脚本按此清单与引擎源码双向核对, 防两侧声明漂移
PERF_ENV_FIELDS = (
    PERF_ENV_SCENE_FILE, PERF_ENV_RESULT_FILE, PERF_ENV_VM_URL,
    PERF_ENV_PUSH_INTERVAL, PERF_ENV_REPORT_CODE, PERF_ENV_PERF_CODE,
)

# ---------- 引擎产物文件名约定(OUTPUT_PERF_DIR/{report_code}/ 目录下) ----------
SCENE_FILE_NAME = "scene.json"
LOCUST_LOG_NAME = "locust.log"

# 引擎入口(locust -f 加载), 与本文件同模块树: services/../locust_engine/perf_locustfile.py
LOCUSTFILE_PATH = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "locust_engine", "perf_locustfile.py",
))

# ---------- 管线参数 ----------
# locust --stop-timeout: 结束时等待在途请求完成的秒数
LOCUST_STOP_TIMEOUT = 5
# 失败时回读引擎日志尾部字符数(入 error_message 供前端直接展示)
LOG_TAIL_LIMIT = 2000
# 管线等待循环兜底时限系数: 2倍run_duration + 该宽限秒数后强制回收进程组
PIPELINE_IDLE_GRACE = 600

# 执行锁定态(与 PerfTaskCrud.ensure_task_editable 口径一致): 排队/执行中/停止中禁止再次下发
EXECUTE_LOCKED_STATES = (PerfTaskStatus.QUEUED, PerfTaskStatus.RUNNING, PerfTaskStatus.STOPPING)


def _pick_scene_items(scene: PerfSceneModel) -> List[Dict[str, Any]]:
    """
    取出场景中参与施压的接口项(启用状态), 按序号升序。

    :param scene: 压测场景实例
    :return: 接口项字典列表(PerfSceneItem 结构)
    """
    items: List[Dict[str, Any]] = [
        dict(item) if isinstance(item, dict) else item.model_dump()
        for item in (scene.scene_items or []) if (item or {}).get("enabled", True)
    ]
    return sorted(items, key=lambda item: int(item.get("seq") or 0))


async def _resolve_endpoints(
        *,
        project_id: int,
        env_name: str,
        config_names: List[str],
        label: str,
) -> Dict[str, EnvEndpoint]:
    """
    按 APP 配置名批量解析施压环境端点(host/port)。

    复用 autotest 调试链路同一解析器 resolve_env_config, 保证与用例执行得到的
    环境地址口径完全一致(环境变更实时生效, 不依赖任务保存时的快照)。配置名去重后
    每个配置名一次解析, 且仅在任务下发时执行一次(不在虚拟用户循环内触库)。

    :param project_id: 应用ID(krun_autotest_project.id)
    :param env_name: 施压环境名称
    :param config_names: 接口涉及的 APP 配置名称列表(可含重复与空值)
    :param label: 错误信息前缀(对齐 autotest 解析器文案风格)
    :return: {配置名称: EnvEndpoint}
    """
    distinct_names: List[str] = sorted({name for name in config_names if name})
    if not distinct_names:
        return {}
    services = await get_autotest_api_services()
    endpoints: Dict[str, EnvEndpoint] = {}
    for config_name in distinct_names:
        endpoints[config_name] = await StepDebugService.resolve_env_config(
            services,
            project_id=project_id,
            env_name=env_name,
            config_name=config_name,
            config_type=AutoTestConfigNodeType.APP,
            label=label,
        )
    return endpoints


def _merge_kv_containers(
        base: Optional[List[Dict[str, Any]]],
        override: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    按key合并两组键值容器(场景override覆盖接口同名项, 新key追加)。

    :param base: 接口定义的键值列表(request_header/request_params)
    :param override: 场景项覆盖键值列表
    :return: 合并后的键值列表
    """
    merged: Dict[str, Dict[str, Any]] = {
        str((item or {}).get("key")): dict(item)
        for item in (base or []) if (item or {}).get("key")
    }
    for item in (override or []):
        key = (item or {}).get("key")
        if key:
            merged[str(key)] = dict(item)
    return list(merged.values())


def _validate_launchable_items(payload_items: List[Dict[str, Any]]) -> None:
    """
    下发前置闸门: 每个参与施压项组装后的URL必须是含host的合法 http(s) 地址。

    压测接口的request_url惯例为相对路径(运行时由环境配置注入host), 若环境配置本身
    缺 host, 直接下发会拼出空host非法URL导致locust零请求崩溃退出, 故在创建report之前拒绝。

    :param payload_items: 已完成地址组装的接口项负载列表
    :return: None
    """
    for item in payload_items:
        request_url: str = str(item.get("request_url") or "")
        parsed = urlparse(build_request_url(request_url, item.get("request_port")))
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            error_message: str = (
                f"执行压测任务失败, 接口[{item.get('api_name')}]地址[{request_url}]缺少目标host, "
                "请检查施压环境APP配置的host或把接口地址完善为 http(s)://host[:port]/path 完整地址"
            )
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)


def _stepped_load_plan(task: PerfTaskModel) -> Optional[Dict[str, Any]]:
    """
    构建阶梯负载计划(stepped 专用; fixed 返回 None, 消费方按无阶梯处理)。

    档数/总时长等派生值在此统一计算, 随 payload.load 段下发引擎与报告快照/管线
    deadline 共用同一份口径(单一事实源), 引擎 shape 只消费不重复推导。

    :param task: 压测任务实例
    :return: 负载计划字典(fixed 模式返回 None), 形如:
        {"mode": "stepped", "users": 10, "spawn_rate": 5, "start_users": 10,
         "increment": 10, "step_duration": 60, "max_users": 50,
         "sustain_duration": 300, "rampup_stages": 5, "total_seconds": 600}
    :raises ParameterException: stepped 模式任一专用字段缺失(保存期已校验, 执行期快速失败防脏数据)
    """
    # 注意: 不能用 str(枚举成员) 与 .value 比较 —— Enum 元类覆盖了 __str__,
    # str(PerfLoadMode.STEPPED) 是 'PerfLoadMode.STEPPED' 而非 'stepped';
    # StringEnum 为 str mixin, 与枚举或裸字符串直接 == 均成立(兼容JSON往返)
    if getattr(task, "load_mode", None) != PerfLoadMode.STEPPED:
        return None
    values: Dict[str, Optional[int]] = {field: getattr(task, field, None) for field in STEPPED_REQUIRED_FIELDS}
    missing = [field for field, value in values.items() if not value]
    if missing:
        error_message: str = f"执行压测任务失败, 阶梯负载专用字段缺失: {missing}, 请补全任务负载配置"
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)
    start_users = int(values["step_start_users"])
    increment = int(values["step_increment"])
    max_users = int(values["step_max_users"])
    # 爬坡档数 = ceil((峰值-起始)/每档递增) + 起始档; 峰值不大于起始时退化为单档起始并发
    rampup_stages = max(1, -(-(max_users - start_users) // increment) + 1)
    step_duration = int(values["step_duration"])
    sustain_duration = int(values["step_sustain_duration"])
    return {
        "mode": PerfLoadMode.STEPPED.value,
        "users": start_users, "spawn_rate": int(task.spawn_rate or 1),
        "start_users": start_users, "increment": increment,
        "step_duration": step_duration, "max_users": max_users,
        "sustain_duration": sustain_duration,
        "rampup_stages": rampup_stages,
        "total_seconds": rampup_stages * step_duration + sustain_duration,
    }


def _rps_load_plan(task: PerfTaskModel) -> Optional[Dict[str, Any]]:
    """
    构建吞吐负载计划(rps 专用; 其余模式返回 None)。

    引擎无 shape 类, 用户数/时长与 fixed 同走 CLI; 差异仅在 load 段 target_rps:
    引擎按 上限并发/目标RPS 做每虚拟用户节流, 全局稳态吞吐≈target_rps。

    :param task: 压测任务实例
    :return: 负载计划字典(非 rps 模式返回 None), 形如:
        {"mode": "rps", "users": 50, "spawn_rate": 10, "target_rps": 100.0, "total_seconds": 600}
    :raises ParameterException: rps 模式目标RPS缺失(保存期已校验, 执行期快速失败防脏数据)
    """
    if getattr(task, "load_mode", None) != PerfLoadMode.RPS:
        return None
    target_rps = float(task.target_rps or 0)
    if target_rps <= 0:
        error_message: str = "执行压测任务失败, 吞吐模式[rps]目标RPS缺失或非法, 请补全任务负载配置"
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)
    return {
        "mode": PerfLoadMode.RPS.value,
        "users": int(task.concurrent_users or 1), "spawn_rate": int(task.spawn_rate or 1),
        "target_rps": target_rps,
        "total_seconds": int(task.run_duration or 0),
    }


def _resolve_load_plan(task: PerfTaskModel) -> Optional[Dict[str, Any]]:
    """
    按施压模式解析负载计划(stepped/rps 各自产计划, fixed 返回 None)。

    :param task: 压测任务实例
    :return: 负载计划字典(fixed 模式返回 None)
    """
    if getattr(task, "load_mode", None) == PerfLoadMode.RPS:
        return _rps_load_plan(task)
    return _stepped_load_plan(task)


def _effective_peak_users(task: PerfTaskModel) -> int:
    """
    实际峰值并发: stepped 取阶梯峰值, fixed/rps 取并发用户数(报告快照/执行闸门/指纹统一口径)。

    :param task: 压测任务实例
    :return: 峰值并发用户数
    """
    load_plan = _resolve_load_plan(task)
    if load_plan and load_plan.get("mode") == PerfLoadMode.STEPPED:
        return int(load_plan["max_users"])
    # fixed/rps 的用户池上限均为 concurrent_users
    return int(task.concurrent_users or 1)


def _derive_warmup_seconds(scene: PerfSceneModel, task: PerfTaskModel, users: int, spawn_rate: int) -> int:
    """
    解析预热剔除秒数: 场景显式配置优先; 未配置时按加压期时长派生(上限
    PERF_WARMUP_DEFAULT_MAX, 预热本质是剔除ramp爬坡段, 不应把整段压测剔空)。

    fixed/rps 模式加压期 = 并发/spawn_rate(rps仅是节流语义, 启动节奏与fixed一致);
    stepped 模式加压期 = 爬坡档数×每档秒数(峰值
    保持段已是稳态流量, 不属于预热范畴)。

    :param scene: 压测场景实例
    :param task: 压测任务实例
    :param users: 并发用户数
    :param spawn_rate: 每秒启动用户数
    :return: 预热剔除秒数(0=不剔除)
    """
    if scene.warmup_seconds is not None:
        return int(scene.warmup_seconds)
    load_plan = _resolve_load_plan(task)
    if load_plan and load_plan.get("mode") == PerfLoadMode.STEPPED:
        ramp_seconds = int(load_plan["rampup_stages"]) * int(load_plan["step_duration"])
    else:
        ramp_seconds = math.ceil(users / max(spawn_rate, 1))
    return min(ramp_seconds, PERF_WARMUP_DEFAULT_MAX)


async def _assemble_scene_payload(
        *,
        task: PerfTaskModel,
        scene: PerfSceneModel,
        batch_code: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, int]]:
    """
    构建下发引擎的自包含施压场景负载: 场景闸门 -> 批量回查接口/数据集 -> 地址组装 -> 校验。

    闸门顺序(执行期最终防线, 场景保存期已有一层校验):
    journey模式拒绝(引擎未实装链路编排) -> TCP项拒绝(M1仅HTTP施压)
    -> measured项存在 -> unique策略行数充足 -> 地址合法性。

    :param task: 压测任务实例
    :param scene: 压测场景实例
    :param batch_code: 压测批次标识(注入 x-perf-batch 与报告关联)
    :return: (场景负载字典, 接口项负载列表, 接口版本映射{api_code: version})
    :raises ParameterException: 任一闸门不通过或引用资产缺失
    """
    users = int(task.concurrent_users or 1)
    spawn_rate = int(task.spawn_rate or 1)
    load_plan = _resolve_load_plan(task)
    # 阶梯模式的行饥饿闸门/预热派生均以峰值并发为口径(爬坡初期行数充足不代表峰值期充足)
    peak_users = _effective_peak_users(task)
    if scene.run_mode == PerfRunMode.JOURNEY:
        error_message: str = (
            "执行压测任务失败, 施压引擎暂不支持journey链路模式, "
            "请改用单接口(single)或混合流量(mixed)场景"
        )
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)

    scene_items = _pick_scene_items(scene)
    if not any(str(item.get("role")) == PerfApiRole.MEASURED.value for item in scene_items):
        error_message = "执行压测任务失败, 场景中没有启用的被测接口项(measured)"
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)

    # 批量回查引用资产(每个code一次查询, 循环外完成; 缺失/禁用即拒绝)
    api_codes = sorted({str(item.get("api_code")) for item in scene_items})
    apis = await PerfApiModel.filter(api_code__in=api_codes, state__not=1)
    api_map: Dict[str, PerfApiModel] = {api.api_code: api for api in apis}
    missing_apis = [code for code in api_codes if code not in api_map]
    if missing_apis:
        error_message = f"执行压测任务失败, 场景引用的压测接口不存在或已禁用: {missing_apis}"
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)
    tcp_apis = [
        api.api_name for code in api_codes
        if api_map[code].step_type == AutoTestStepType.TCP
    ]
    if tcp_apis:
        error_message = (
            f"执行压测任务失败, TCP施压暂未开放(当前仅支持HTTP), "
            f"请从场景中移除TCP接口: {tcp_apis}"
        )
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)

    ds_codes = sorted({str(item.get("ds_code")) for item in scene_items if item.get("ds_code")})
    datasets = await PerfDatasetModel.filter(ds_code__in=ds_codes, state__not=1) if ds_codes else []
    dataset_map: Dict[str, PerfDatasetModel] = {ds.ds_code: ds for ds in datasets}
    missing_datasets = [code for code in ds_codes if code not in dataset_map]
    if missing_datasets:
        error_message = f"执行压测任务失败, 场景引用的参数化数据集不存在或已禁用: {missing_datasets}"
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)
    for item in scene_items:
        if str(item.get("dataset_strategy")) != PerfDatasetStrategy.UNIQUE.value:
            continue
        dataset = dataset_map[str(item["ds_code"])]
        # 「场景」即unique策略下的虚拟用户独占单元, 场景数不足则后期虚拟用户取不到专属场景
        scene_count: int = len(dataset.dataset_names or [])
        if scene_count < peak_users:
            error_message = (
                f"执行压测任务失败, 接口[{item.get('api_name')}]的unique策略数据场景数"
                f"[{scene_count}]小于并发用户数[{peak_users}], 请补充数据或降低并发"
            )
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

    # 地址组装: 接口侧配置名为主, 回退任务级缺省配置(与功能用例执行同口径)
    default_config: str = (task.env_config_name or "").strip()
    env_name: str = (task.env_name or "").strip()
    step_configs: List[str] = []
    for item in scene_items:
        api = api_map[str(item.get("api_code"))]
        step_configs.append((api.request_config_name or "").strip() or default_config)
    endpoints: Dict[str, EnvEndpoint] = await _resolve_endpoints(
        project_id=task.perf_project,
        env_name=env_name,
        config_names=step_configs,
        label=f"执行压测任务失败(施压环境[{env_name or '未选择'}])",
    )

    payload_items: List[Dict[str, Any]] = []
    for item, config_name in zip(scene_items, step_configs):
        api = api_map[str(item.get("api_code"))]
        request_url: str = (api.request_url or "").strip()
        if not is_absolute_http_url(request_url):
            endpoint = endpoints.get(config_name)
            if endpoint is None:
                error_message = (
                    f"执行压测任务失败, 接口[{api.api_name}]地址[{request_url}]是相对路径, "
                    f"但未解析到施压环境APP配置[{config_name or '未选择'}]的host"
                )
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)
            request_url = build_absolute_http_url(endpoint.config_host, endpoint.config_port, request_url)
        override = item.get("override") or {}
        payload_item: Dict[str, Any] = {
            "seq": item.get("seq"), "role": str(item.get("role")),
            "api_code": api.api_code, "api_name": api.api_name, "api_version": api.api_version,
            "request_method": (api.request_method or "GET").upper(),
            "request_url": request_url, "request_port": api.request_port,
            "request_header": _merge_kv_containers(api.request_header, override.get("request_header")),
            "request_params": _merge_kv_containers(api.request_params, override.get("request_params")),
            "request_form_data": api.request_form_data or [],
            "request_form_file": api.request_form_file or [],
            "request_form_urlencoded": api.request_form_urlencoded or [],
            "request_text": api.request_text,
            "request_body": api.request_body,
            "request_args_type": api.request_args_type.value if api.request_args_type else None,
            "defined_variables": api.defined_variables or [],
            "extract_variables": api.extract_variables or [],
            "assert_validators": api.assert_validators or [],
            "weight": int(item.get("weight") or 1),
            "transaction": item.get("transaction"),
            "delay_mode": str(item.get("delay_mode") or "fixed"),
            "delay_ms": int(item.get("delay_ms") or 0),
            "delay_ms_min": item.get("delay_ms_min"),
            "delay_ms_max": item.get("delay_ms_max"),
        }
        if item.get("ds_code"):
            dataset = dataset_map[str(item["ds_code"])]
            dataset_data: Dict[str, Any] = dataset.dataset or {}
            # 场景序即引擎轮询序(dataset_names声明顺序); 施压仅消费 head/body 两分区,
            # assert_* 分区按存储层原样保留不参与施压
            payload_item["dataset"] = {
                "strategy": str(item.get("dataset_strategy") or PerfDatasetStrategy.ROUND_ROBIN.value),
                "scenes": [
                    {
                        "name": scene_name,
                        "head": (dataset_data.get(scene_name) or {}).get("head") or {},
                        "body": (dataset_data.get(scene_name) or {}).get("body") or {},
                    }
                    for scene_name in dataset.dataset_names or []
                ],
            }
        payload_items.append(payload_item)

    _validate_launchable_items(payload_items)

    scene_payload: Dict[str, Any] = {
        "run_mode": scene.run_mode.value,
        "perf_batch_code": batch_code,
        # stepped 模式 run_duration 语义为阶梯计划总时长(shape 自控结束, CLI --run-time 不参与)
        "run_duration": int(load_plan["total_seconds"]) if load_plan else int(task.run_duration or 0),
        # 负载计划段(stepped 专用; fixed 模式为 None, 引擎无消费方)
        "load": load_plan,
        "warmup_seconds": _derive_warmup_seconds(scene, task, users, spawn_rate),
        "error_rate_threshold": float(scene.error_rate_threshold or 0),
        "inject_perf_tag": bool(scene.inject_perf_tag),
        "assert_mode": scene.assert_mode.value,
        "sample_ratio": float(scene.sample_ratio if scene.sample_ratio is not None else 100.0),
        # 场景层暂无初始变量池, 变量全部来自准备段提取
        "session_variables": [],
        "items": payload_items,
    }
    api_versions = {item["api_code"]: item["api_version"] for item in payload_items}
    return scene_payload, payload_items, api_versions


def _resolve_target_host(payload_items: List[Dict[str, Any]]) -> Optional[str]:
    """
    取首个施压项的 scheme://host[:port] 作为施压目标快照(报告展示与基线对比维度)。

    :param payload_items: 接口项负载列表(地址已组装为绝对地址)
    :return: 目标host字符串; 无合法地址时返回None
    """
    for item in payload_items:
        parsed = urlparse(str(item.get("request_url") or ""))
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    return None


def _build_config_fingerprint(
        scene_payload: Dict[str, Any],
        task: PerfTaskModel,
) -> str:
    """
    计算配置指纹(可比性判定依据): 场景结构与负载参数的md5, 任一变化即视为不可比。

    :param scene_payload: 场景负载字典(见 _assemble_scene_payload)
    :param task: 压测任务实例
    :return: 32位md5十六进制串
    """
    fingerprint_source = orjson.dumps({
        "items": [
            {
                key: item.get(key) for key in
                ("seq", "role", "api_code", "api_version", "weight", "transaction",
                 "delay_mode", "delay_ms", "dataset")
            }
            for item in scene_payload.get("items") or []
        ],
        "run_mode": scene_payload.get("run_mode"),
        "assert_mode": scene_payload.get("assert_mode"),
        "sample_ratio": scene_payload.get("sample_ratio"),
        "warmup_seconds": scene_payload.get("warmup_seconds"),
        "error_rate_threshold": scene_payload.get("error_rate_threshold"),
        # 指纹取有效峰值并发/计划总时长/目标吞吐: 两份报告指纹相同即负载口径完全一致(可比前提)
        "concurrent_users": _effective_peak_users(task),
        "run_duration": int(scene_payload.get("run_duration") or 0),
        "target_rps": (float(task.target_rps) if task.target_rps is not None
                       and getattr(task, "load_mode", None) == PerfLoadMode.RPS else None),
    })
    return hashlib.md5(fingerprint_source).hexdigest()


def _build_launch_context(
        *,
        task: PerfTaskModel,
        report_code: str,
        scene_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    构建施压引擎启动上下文：工作目录、场景文件、环境变量与 locust 命令行。

    :param task: 压测任务实例(配置于子进程启动前读取, 全程不变)
    :param report_code: 报告标识(工作目录与指标标签键)
    :param scene_payload: 已组装的场景负载(见 _assemble_scene_payload)
    :return: 启动上下文字典, 结构:
        {"argv": [可执行文件与参数], "env": {环境变量}, "work_dir": "工作目录",
         "result_dir": "结果分片目录", "log_file": "引擎日志路径",
         "process_count": 期望进程数(1为单进程), "target_host": "施压目标host"}
    """
    work_dir = os.path.join(PROJECT_CONFIG.OUTPUT_PERF_DIR, report_code)
    os.makedirs(work_dir, exist_ok=True)
    log_file = os.path.join(work_dir, LOCUST_LOG_NAME)

    # 场景负载经工作目录文件传递: 含数据集行与断言定义的报文可达百KB级,
    # 走环境变量会撞 Linux 单变量 32KB 上限(MAX_ARG_STRLEN)导致子进程 exec 失败
    scene_file = os.path.join(work_dir, SCENE_FILE_NAME)
    with open(scene_file, "wb") as scene_handle:
        scene_handle.write(orjson.dumps(scene_payload))

    # 阶梯模式峰值并发参与多进程决策; CLI -u/-r/--run-time 传 fixed 与 rps 模式
    # (stepped 由引擎 shape 类接管用户数驱动, locust 发现 shape 会忽略这三参数)
    users = _effective_peak_users(task)
    load_plan = scene_payload.get("load") if isinstance(scene_payload.get("load"), dict) else None
    planned_duration = int(load_plan["total_seconds"]) if load_plan else int(task.run_duration or 0)
    argv: List[str] = [
        sys.executable, "-m", "locust",
        "-f", LOCUSTFILE_PATH,
        "--headless", "--only-summary",
    ]
    if not load_plan or load_plan.get("mode") == PerfLoadMode.RPS:
        argv += [
            "--users", str(users),
            "--spawn-rate", str(int(task.spawn_rate or 1)),
            "--run-time", f"{int(task.run_duration or 0)}s",
        ]
    argv += ["--stop-timeout", str(LOCUST_STOP_TIMEOUT)]
    # 多进程决策: 并发达阈值时按 机器核数/配置上限/单进程承载 三者取最小(至少2进程)
    process_count = 1
    if users >= PROJECT_CONFIG.PERF_MULTIPROCESS_THRESHOLD:
        process_count = max(2, min(
            os.cpu_count() or 1,
            PROJECT_CONFIG.PERF_MAX_PROCESS,
            users // PROJECT_CONFIG.PERF_MIN_USERS_PER_PROCESS,
        ))
        argv += ["--processes", str(process_count),
                 "--master-bind-port", str(PROJECT_CONFIG.PERF_LOCUST_MASTER_PORT_BASE)]

    env: Dict[str, str] = {
        **os.environ,
        PERF_ENV_REPORT_CODE: report_code,
        PERF_ENV_PERF_CODE: task.perf_code,
        PERF_ENV_SCENE_FILE: scene_file,
        # PERF_RESULT_FILE 语义为分片目录: 各引擎进程写 result_{pid}.json, 管线合并
        PERF_ENV_RESULT_FILE: work_dir,
        PERF_ENV_VM_URL: PROJECT_CONFIG.PERF_VICTORIA_METRICS_URL,
        PERF_ENV_PUSH_INTERVAL: str(PROJECT_CONFIG.PERF_METRICS_PUSH_INTERVAL),
    }
    return {
        "argv": argv, "env": env, "work_dir": work_dir,
        "result_dir": work_dir, "log_file": log_file,
        "process_count": process_count,
        # 计划施压总时长(stepped=阶梯计划总时长): 管线等待 deadline 与报告快照口径
        "planned_duration": planned_duration,
        "target_host": _resolve_target_host(scene_payload.get("items") or []),
    }


def _collect_process_group(process: subprocess.Popen) -> List[psutil.Process]:
    """
    收集施压批次进程组快照(master 与多进程 workers), 统一以 psutil.Process 句柄登记。

    :param process: 引擎 master/单进程 Popen 句柄
    :return: 进程组列表(worker 尚未拉起时仅含 master)
    """
    master = psutil.Process(process.pid)
    group = [master]
    try:
        group.extend(master.children(recursive=True))
    except psutil.NoSuchProcess:
        pass
    return group


def _load_result_shards(result_dir: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    读取并校验引擎结果分片(result_{pid}.json, 各进程一份)。

    :param result_dir: 分片目录
    :return: (分片列表, 错误描述); 分片缺失时前者为空列表后者带原因
    """
    shard_paths = sorted(
        os.path.join(result_dir, name) for name in os.listdir(result_dir)
        if name.startswith("result_") and name.endswith(".json")
    ) if os.path.isdir(result_dir) else []
    if not shard_paths:
        return [], f"结果分片目录无分片文件[{result_dir}]"
    shards: List[Dict[str, Any]] = []
    for shard_path in shard_paths:
        try:
            with open(shard_path, "rb") as shard_handle:
                payload = orjson.loads(shard_handle.read())
            if not isinstance(payload, dict):
                raise ValueError("分片结构非法(非JSON对象)")
            shards.append(payload)
        except (orjson.JSONDecodeError, ValueError, OSError) as e:
            # 单个分片损坏不吞整批结果: 跳过并记录, 其余分片仍可聚合
            LOGGER.error(f"压测结果分片读取失败, 已跳过: {shard_path}, 错误描述: {e}")
    if not shards:
        return [], "全部结果分片损坏或为空"
    return shards, None


def _read_log_tail(log_file: str, limit: int = LOG_TAIL_LIMIT) -> str:
    """
    回读引擎日志尾部内容(失败归因用)。

    :param log_file: 引擎日志绝对路径
    :param limit: 尾部字符数
    :return: 日志尾部文本(读取失败返回空串)
    """
    try:
        with open(log_file, "rb") as log_handle:
            log_handle.seek(0, os.SEEK_END)
            size = log_handle.tell()
            log_handle.seek(max(size - limit, 0))
            return log_handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _build_report_final_fields(
        merged: Dict[str, Any],
        metrics: Dict[str, Any],
        *,
        report_status: PerfReportStatus,
        stopped_reason: PerfStoppedReason,
        error_message: Optional[str],
) -> Dict[str, Any]:
    """
    将合并快照与聚合结果映射为报告终态回填字段(PerfReportModel B/C/D组统计列)。

    :param merged: 合并分片快照(见 perf_result_aggregator.merge_result_shards)
    :param metrics: 聚合统计(见 perf_result_aggregator.compute_report_metrics)
    :param report_status: 报告终态(completed/stopped/failed)
    :param stopped_reason: 结束原因(与执行状态分离)
    :param error_message: 失败原因(正常结束为None)
    :return: 报告回填字段字典
    """
    global_view = metrics["global"]
    return {
        "status": report_status,
        "started_time": parse_iso(merged.get("started_time")),
        "finished_time": parse_iso(merged.get("finished_time")),
        "duration_seconds": int(metrics["duration_seconds"]),
        "warmup_seconds": int(merged.get("warmup_seconds") or 0),
        "total_requests": global_view["total_requests"],
        "success_requests": global_view["success_requests"],
        "fail_requests": global_view["fail_requests"],
        "error_rate": global_view["error_rate"],
        "rps": global_view["rps"],
        "success_rps": global_view["success_rps"],
        "avg_rt": global_view["avg_rt"],
        "min_rt": global_view["min_rt"],
        "max_rt": global_view["max_rt"],
        "p50": global_view["p50"],
        "p90": global_view["p90"],
        "p95": global_view["p95"],
        "p99": global_view["p99"],
        "std_dev": global_view["std_dev"],
        # 上行/下行速率依赖响应字节数统计, M1引擎分片未采集, 置0待后续版本补齐
        "sent_kb_s": 0.0,
        "received_kb_s": 0.0,
        "api_aggregations": metrics["api_aggregations"],
        "transaction_aggregations": metrics["transaction_aggregations"],
        "prepare_metrics": metrics["prepare_metrics"],
        "verify_metrics": metrics["verify_metrics"],
        "error_breakdown": metrics["error_breakdown"],
        "locust_stats": {
            "entries": merged.get("entries") or [],
            "errors": merged.get("errors") or [],
            "shards": merged.get("shards") or [],
        },
        "target_result": metrics["target_result"],
        "stopped_reason": stopped_reason,
        "error_message": error_message,
    }


async def _build_baseline_diff(report: PerfReportModel, scene: PerfSceneModel) -> Optional[Dict[str, Any]]:
    """
    计算当前报告相对场景钉选基线的退化对比(设计§5.6 第二层判定, 与 SLA/熔断职责分离)。

    基线是趋势结论而非运行结局: 仅对 completed 报告计算; 可比性前置(设计§5.7):
    同场景 + 配置指纹一致 + 双方样本量过显著性闸门, 不可比时给出可读原因
    (指纹差异明细)而非只丢一句"不可比"。

    :param report: 已完成终态回填的当前报告实例
    :param scene: 执行时装载的场景实例(基线钉选以执行时刻为准)
    :return: 基线对比结果字典(场景未钉基线或报告未完成时返回 None), 形如:
        {"comparable": true, "diff": {"p95": 12.5, "qps": -3.2, "error_rate": 0.4},
         "violations": ["P95 退化 15.0%, 超过允许阈值 10.0%"], "incomparable_reasons": []}
    """
    if not scene.baseline_report_code or report.status != PerfReportStatus.COMPLETED:
        return None
    baseline = await PerfReportModel.filter(report_code=scene.baseline_report_code, state__not=1).first()
    if baseline is None:
        return {"comparable": False, "diff": None, "violations": [],
                "incomparable_reasons": [f"基线报告[{scene.baseline_report_code}]不存在或已删除"]}
    if baseline.id == report.id:
        return {"comparable": False, "diff": None, "violations": [],
                "incomparable_reasons": ["基线不能是当前报告自身"]}
    if baseline.status != PerfReportStatus.COMPLETED:
        return {"comparable": False, "diff": None, "violations": [],
                "incomparable_reasons": [f"基线报告[{scene.baseline_report_code}]未处于完成状态, 无稳定结论可比"]}

    diffs = diff_report_pair(report, baseline)
    reasons: List[str] = summarize_report_diff(diffs)
    if int(report.total_requests or 0) < PERF_MIN_SAMPLES_FOR_COMPARE:
        reasons.append(
            f"当前报告业务请求总数[{report.total_requests}]低于显著性闸门[{PERF_MIN_SAMPLES_FOR_COMPARE}], 结论不具统计意义"
        )
    if int(baseline.total_requests or 0) < PERF_MIN_SAMPLES_FOR_COMPARE:
        reasons.append(
            f"基线报告业务请求总数[{baseline.total_requests}]低于显著性闸门[{PERF_MIN_SAMPLES_FOR_COMPARE}], 结论不具统计意义"
        )
    if reasons:
        return {"comparable": False, "diff": None, "violations": [], "incomparable_reasons": reasons}

    def _pct(current_value: float, baseline_value: float) -> Optional[float]:
        """相对变化百分比(基线为0时无从比较, 返回None由前端显示为无数据)。"""
        if not baseline_value:
            return None
        return round((current_value - baseline_value) / baseline_value * 100, 2)

    diff_result: Dict[str, Any] = {
        # P95/RPS 取相对变化百分比; 错误率取百分点差(与阈值 error_rate_increase 同为绝对口径);
        # qps 取 success_rps: 退化判定看业务吞吐, 含失败请求的 rps 会把错误放大成吞吐下降
        "p95": _pct(float(report.p95 or 0), float(baseline.p95 or 0)),
        "qps": _pct(float(report.success_rps or 0), float(baseline.success_rps or 0)),
        "error_rate": round(float(report.error_rate or 0) - float(baseline.error_rate or 0), 2),
    }
    violations: List[str] = []
    policy: Dict[str, Any] = scene.baseline_policy if isinstance(scene.baseline_policy, dict) else {}
    p95_threshold = policy.get("p95_degrade_pct")
    if p95_threshold is not None and diff_result["p95"] is not None and diff_result["p95"] > float(p95_threshold):
        violations.append(f"P95 退化 {diff_result['p95']}%, 超过允许阈值 {p95_threshold}%")
    qps_threshold = policy.get("qps_degrade_pct")
    if qps_threshold is not None and diff_result["qps"] is not None and diff_result["qps"] < -float(qps_threshold):
        violations.append(f"业务吞吐(RPS)下降 {abs(diff_result['qps'])}%, 超过允许阈值 {qps_threshold}%")
    error_threshold = policy.get("error_rate_increase")
    if error_threshold is not None and diff_result["error_rate"] > float(error_threshold):
        violations.append(f"错误率上升 {diff_result['error_rate']} 个百分点, 超过允许阈值 {error_threshold}")
    return {"comparable": True, "diff": diff_result, "violations": violations, "incomparable_reasons": []}


class PerfExecuteService:
    """压测执行业务服务：执行下发、停止链与 Celery 编排管线。"""

    @staticmethod
    async def _locate_task(task_in: PerfTaskLocate) -> PerfTaskModel:
        """
        按id或code二选一定位任务(未禁用)。

        :param task_in: 任务定位入参
        :return: 任务实例
        """
        if task_in.perf_id:
            return await PerfTaskCrud().get_by_id(perf_id=task_in.perf_id, on_error=True, state__not=1)
        if task_in.perf_code:
            return await PerfTaskCrud().get_by_code(perf_code=task_in.perf_code, on_error=True, state__not=1)
        error_message: str = "定位压测任务失败, 参数[perf_id]或[perf_code]不允许为空"
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)

    @staticmethod
    async def run_task(task_in: PerfTaskLocate) -> PerfTaskModel:
        """
        执行下发前置业务：完整性校验并原子置排队(下发 apply_async 由视图层编排)。

        :param task_in: 任务定位入参(id或code二选一)
        :return: 已置排队状态的任务实例
        """
        instance = await PerfExecuteService._locate_task(task_in)
        # 下发前就完成场景装载与组装校验: 让用户在点击时得到确定反馈, 而非排队后才发现无法施压
        scene = await PerfSceneModel.filter(scene_code=instance.scene_code, state__not=1).first()
        if scene is None:
            error_message: str = (
                f"执行压测任务失败, 任务引用的压测场景不存在或已禁用[{instance.scene_code}]"
            )
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        await _assemble_scene_payload(task=instance, scene=scene, batch_code="precheck")

        # 原子置排队: 排除执行锁定态, 与视图并发点击/引擎状态回写竞争互斥;
        # 未执行过的存量任务该列为 NULL, 而 SQL 三值逻辑下 NOT(NULL IN(...)) 恒为 UNKNOWN 会误排 NULL 行,
        # 必须显式补 IS NULL 分支(新建任务已由 create_perf_task 落 idle, 新增行不再依赖此分支)
        updated = await PerfTaskModel.filter(id=instance.id).filter(
            Q(last_execute_state=None) | ~Q(last_execute_state__in=EXECUTE_LOCKED_STATES),
        ).update(
            last_execute_state=PerfTaskStatus.QUEUED,
            last_execute_time=datetime.now(),
            last_execute_error=None,
        )
        if not updated:
            state_value = instance.last_execute_state.value if instance.last_execute_state else "无"
            error_message = f"执行压测任务失败, 记录[id={instance.id}]当前状态为[{state_value}], 不允许执行"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        LOGGER.info(f"压测任务已置排队: perf_id={instance.id}, perf_code={instance.perf_code}")
        return await PerfTaskCrud().get_by_id(perf_id=instance.id, on_error=True)

    @staticmethod
    async def stop_task(task_in: PerfTaskLocate) -> PerfTaskModel:
        """
        停止链业务：仅排队/执行中任务允许置停止中, 重复请求幂等收敛。

        引擎等待循环按 PERF_STOP_POLL_INTERVAL 感知 stopping 后杀进程组并落 stopped 终态。

        :param task_in: 任务定位入参
        :return: 已置停止中状态的任务实例
        """
        instance = await PerfExecuteService._locate_task(task_in)
        updated = await PerfTaskModel.filter(
            id=instance.id,
            last_execute_state__in=[PerfTaskStatus.QUEUED, PerfTaskStatus.RUNNING],
        ).update(last_execute_state=PerfTaskStatus.STOPPING)
        if not updated:
            fresh = await PerfTaskCrud().get_by_id(perf_id=instance.id, on_error=True)
            if fresh.last_execute_state == PerfTaskStatus.STOPPING:
                # 幂等: 停止指令已下发, 直接返回当前状态
                return fresh
            state_value = fresh.last_execute_state.value if fresh.last_execute_state else "无"
            error_message: str = f"停止压测任务失败, 记录[id={instance.id}]当前状态为[{state_value}], 不在执行中"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        LOGGER.info(f"压测任务已置停止中: perf_id={instance.id}, perf_code={instance.perf_code}")
        return await PerfTaskCrud().get_by_id(perf_id=instance.id, on_error=True)

    @staticmethod
    async def execute_pipeline(
            *,
            perf_code: str,
            celery_id: Optional[str] = None,
            execute_user: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        压测执行管线(Celery 任务编排主体)：装载场景 → 建报告 → 拉起引擎 → 等待循环
        → 分片合并聚合 → 报告落库 → 回填终态。

        等待循环每 PERF_STOP_POLL_INTERVAL 秒检查停止指令与进程退出; 结果判定以
        result_{pid}.json 分片为准(断言失败/熔断是压测数据而非管线错误), 分片缺失/
        全部损坏才置 failed。

        :param perf_code: 压测任务标识代码
        :param celery_id: Celery任务ID(报告与任务表回填溯源)
        :param execute_user: 触发人账号(报告维护字段归因)
        :return: 管线执行结果字典, 结构:
            {"success": true, "perf_code": "xxx", "report_code": "yyy",
             "status": "completed", "error": null}
        """
        task = await PerfTaskCrud().get_by_code(perf_code=perf_code, on_error=True)

        # 消费闸门: 仅排队中继续; 排队期间被撤销(stopping)收敛为stopped; 其余状态(消息重投等)跳过
        if task.last_execute_state != PerfTaskStatus.QUEUED:
            if task.last_execute_state == PerfTaskStatus.STOPPING:
                await PerfTaskModel.filter(id=task.id).update(
                    last_execute_state=PerfTaskStatus.STOPPED,
                    last_execute_time=datetime.now(),
                )
                return {
                    "success": False, "perf_code": perf_code, "report_code": None,
                    "status": PerfTaskStatus.STOPPED.value, "error": "任务在排队期间被撤销, 未执行",
                }
            state_value = task.last_execute_state.value if task.last_execute_state else "无"
            LOGGER.warning(f"压测任务状态非排队中, 跳过重复消费: perf_code={perf_code}, state={state_value}")
            return {
                "success": False, "perf_code": perf_code, "report_code": None,
                "status": state_value, "error": "任务状态非排队中, 跳过重复消费",
            }

        report_code = unique_identify()
        # 原子置执行中: 防消息重投与停止指令竞争
        updated = await PerfTaskModel.filter(
            id=task.id, last_execute_state=PerfTaskStatus.QUEUED,
        ).update(
            last_execute_state=PerfTaskStatus.RUNNING,
            last_execute_time=datetime.now(),
            last_celery_id=celery_id,
        )
        if not updated:
            error_message: str = f"压测任务[perf_code={perf_code}]状态已变更, 终止本次执行"
            LOGGER.warning(error_message)
            return {"success": False, "perf_code": perf_code, "report_code": None,
                    "status": PerfTaskStatus.IDLE.value, "error": error_message}

        # 场景装载与启动上下文: 失败(引用缺失/闸门不通过)不建报告, 任务直接置failed
        launch: Optional[Dict[str, Any]] = None
        scene: Optional[PerfSceneModel] = None
        try:
            scene = await PerfSceneModel.filter(scene_code=task.scene_code, state__not=1).first()
            if scene is None:
                raise ParameterException(
                    message=f"任务引用的压测场景不存在或已禁用[{task.scene_code}]"
                )
            scene_payload, payload_items, api_versions = await _assemble_scene_payload(
                task=task, scene=scene, batch_code=report_code,
            )
            launch = _build_launch_context(
                task=task, report_code=report_code, scene_payload=scene_payload,
            )
        except Exception as e:
            error_message = f"压测场景装载失败: {getattr(e, 'message', None) or e}"
            LOGGER.error(f"压测场景装载失败: perf_code={perf_code}, 错误描述: {e}\n{traceback.format_exc()}")
            await PerfTaskModel.filter(id=task.id).update(
                last_execute_state=PerfTaskStatus.FAILED,
                last_execute_time=datetime.now(),
                last_execute_error=error_message,
            )
            return {
                "success": False, "perf_code": perf_code, "report_code": None,
                "status": PerfTaskStatus.FAILED.value, "error": error_message,
            }

        report = await PerfReportModel.create(
            perf_id=task.id,
            perf_code=task.perf_code,
            report_code=report_code,
            batch_code=report_code,
            status=PerfReportStatus.RUNNING,
            celery_id=celery_id,
            created_user=execute_user,
            updated_user=execute_user,
            scene_id=scene.id,
            scene_code=scene.scene_code,
            scene_name=scene.scene_name,
            run_mode=scene.run_mode,
            # 基线引用随报告创建即固化(快照哲学): 事后改钉不影响本报告的对比对象记载
            baseline_report_id=scene.baseline_report_id,
            baseline_report_code=scene.baseline_report_code,
            concurrent_users=_effective_peak_users(task),
            # 目标吞吐随报告固化(负载快照): rps 报告必须可溯压测目标, 其余模式为空
            target_rps=(float(task.target_rps) if task.target_rps is not None
                        and getattr(task, "load_mode", None) == PerfLoadMode.RPS else None),
            run_duration=int(launch["planned_duration"] or 0),
            process_count=launch["process_count"],
            env_name=task.env_name,
            env_config_name=task.env_config_name,
            target_host=launch["target_host"],
            config_snapshot={
                **scene_payload,
                "perf_targets": scene.perf_targets,
                "journey": scene.journey,
            },
            scene_items_snapshot=payload_items,
            api_versions=api_versions,
            config_fingerprint=_build_config_fingerprint(scene_payload, task),
        )

        process: Optional[subprocess.Popen] = None
        stop_requested = False
        timeout_hit = False
        pipeline_error: Optional[str] = None
        try:
            with open(launch["log_file"], "ab") as log_handle:
                process = subprocess.Popen(
                    launch["argv"],
                    env=launch["env"],
                    # 引擎非tty stdin下优雅跳过键盘监听; 输出统一重定向到批次日志
                    stdin=subprocess.DEVNULL,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                )
                PERF_PROCESS_REGISTRY.register(report_code, _collect_process_group(process))
                LOGGER.info(
                    f"压测进程已启动: perf_code={perf_code}, report_code={report_code}, "
                    f"pid={process.pid}, processes={launch['process_count']}, users={_effective_peak_users(task)}"
                )
                deadline = time.monotonic() + int(launch["planned_duration"] or 0) * 2 + PIPELINE_IDLE_GRACE
                poll_interval = PROJECT_CONFIG.PERF_STOP_POLL_INTERVAL
                while True:
                    await asyncio.sleep(poll_interval)
                    # 每轮刷新进程组登记(多进程worker异步拉起, 晚于master)
                    PERF_PROCESS_REGISTRY.register(report_code, _collect_process_group(process))
                    current_state = await PerfTaskModel.filter(id=task.id).values_list(
                        "last_execute_state", flat=True,
                    )
                    if current_state and current_state[0] == PerfTaskStatus.STOPPING:
                        stop_requested = True
                        await asyncio.to_thread(PERF_PROCESS_REGISTRY.stop, report_code)
                        await asyncio.to_thread(process.wait, KILL_WAIT_TIMEOUT)
                        break
                    if process.poll() is not None:
                        break
                    if time.monotonic() > deadline:
                        timeout_hit = True
                        pipeline_error = "施压进程超过预期时长未退出, 已强制回收"
                        await asyncio.to_thread(PERF_PROCESS_REGISTRY.stop, report_code)
                        await asyncio.to_thread(process.wait, KILL_WAIT_TIMEOUT)
                        break
        except Exception as e:
            pipeline_error = f"执行管线异常: {type(e).__name__}: {e}"
            LOGGER.error(
                f"压测执行管线异常: perf_code={perf_code}, report_code={report_code}, "
                f"错误描述: {e}\n{traceback.format_exc()}"
            )
        finally:
            # 兜底回收: 异常/超时路径下进程组可能仍存活
            if process is not None and process.poll() is None:
                try:
                    await asyncio.to_thread(PERF_PROCESS_REGISTRY.stop, report_code)
                    await asyncio.to_thread(process.wait, KILL_WAIT_TIMEOUT)
                except Exception as e:
                    LOGGER.error(f"兜底回收压测进程组失败: report_code={report_code}, 错误描述: {e}")
            PERF_PROCESS_REGISTRY.unregister(report_code)

        # 结果判定: 分片存在且可解析=正常结束; 缺失/全部损坏=failed(退出码仅记录,
        # 熔断经runner.quit()提前终止时locust以非零码退出, 属正常中止而非管线错误)
        shards: List[Dict[str, Any]] = []
        shards_error: Optional[str] = None
        if launch is not None:
            shards, shards_error = _load_result_shards(launch["result_dir"])
        merged: Optional[Dict[str, Any]] = None
        metrics: Optional[Dict[str, Any]] = None
        if shards:
            merged = merge_result_shards(shards)
            metrics = compute_report_metrics(merged, scene.perf_targets)
            # unique策略多进程提示(管线持有负载上下文, 聚合器无从判定)
            if launch["process_count"] > 1 and any("dataset" in item for item in payload_items):
                has_unique = any(
                    (item.get("dataset") or {}).get("strategy") == PerfDatasetStrategy.UNIQUE.value
                    for item in payload_items
                )
                if has_unique:
                    metrics["stat_warnings"].append({
                        "type": "unique_multiprocess",
                        "text": "多进程模式下unique数据行在各进程独立分配, 跨进程可能复用同一批行",
                    })
        if merged is None:
            pipeline_status = PerfTaskStatus.FAILED
            stopped_reason = PerfStoppedReason.ENGINE_ERROR
            if not pipeline_error:
                log_tail = _read_log_tail(launch["log_file"]) if launch else ""
                exit_code = process.returncode if process is not None else "N/A"
                pipeline_error = f"引擎结果分片缺失({shards_error}), locust退出码[{exit_code}], 日志尾部: {log_tail}"
        elif stop_requested:
            pipeline_status = PerfTaskStatus.STOPPED
            stopped_reason = PerfStoppedReason.MANUAL
        elif timeout_hit or pipeline_error:
            pipeline_status = PerfTaskStatus.FAILED
            stopped_reason = PerfStoppedReason.TIMEOUT_KILL if timeout_hit else PerfStoppedReason.ENGINE_ERROR
        else:
            total_requests = sum(
                int(entry.get("num_requests") or 0) for entry in merged.get("entries") or []
            )
            if process is not None and process.returncode and not total_requests:
                # locust非零退出且零请求: 引擎在任务首请求前即崩溃(地址非法/不可达等),
                # 区别于"断言失败是压测数据"的正常运行, 必须判failed而非全零假完成
                exit_code = process.returncode
                log_tail = _read_log_tail(launch["log_file"]) if launch else ""
                pipeline_status = PerfTaskStatus.FAILED
                stopped_reason = PerfStoppedReason.ENGINE_ERROR
                pipeline_error = f"施压进程异常退出(exit={exit_code})且零请求, 日志尾部: {log_tail}"
                LOGGER.error(f"压测零请求异常退出: report_code={report_code}, {pipeline_error}")
            elif merged.get("circuit_break"):
                # 熔断是运行被主动中止, 报告数据完整有效, 执行结局仍是completed
                pipeline_status = PerfTaskStatus.COMPLETED
                stopped_reason = PerfStoppedReason.CIRCUIT_BREAK
            elif merged.get("stopped_reason") == "stopped":
                # 无人工叫停且无熔断, 分片却处于提前结束态: 引擎半程异常(如用户进程全灭)
                pipeline_status = PerfTaskStatus.FAILED
                stopped_reason = PerfStoppedReason.ENGINE_ERROR
                pipeline_error = "施压引擎提前停止(非熔断且无终止指令), 请检查引擎日志"
            else:
                pipeline_status = PerfTaskStatus.COMPLETED
                stopped_reason = PerfStoppedReason.COMPLETED

        report_status_map = {
            PerfTaskStatus.COMPLETED: PerfReportStatus.COMPLETED,
            PerfTaskStatus.STOPPED: PerfReportStatus.STOPPED,
            PerfTaskStatus.FAILED: PerfReportStatus.FAILED,
        }
        final_error = pipeline_error
        # 收尾回填(独立短事务): 回填失败不中断管线, 任务口径降级为failed防卡running
        try:
            if merged is None:
                final_error = final_error or shards_error or "压测结果分片缺失"
                await report.update_from_dict({
                    "status": PerfReportStatus.FAILED,
                    "finished_time": datetime.now(),
                    "stopped_reason": stopped_reason,
                    "error_message": final_error,
                })
            else:
                await report.update_from_dict(_build_report_final_fields(
                    merged, metrics,
                    report_status=report_status_map[pipeline_status],
                    stopped_reason=stopped_reason,
                    error_message=final_error,
                ))
            await report.save()
        except Exception as e:
            LOGGER.error(
                f"压测报告终态回填失败: report_code={report_code}, 错误描述: {e}\n{traceback.format_exc()}"
            )
            final_error = final_error or f"报告终态回填失败: {e}"
            pipeline_status = PerfTaskStatus.FAILED

        # 基线对比(独立短事务): 基线是趋势结论, 失败只记日志不改变任务执行结局
        try:
            baseline_diff = await _build_baseline_diff(report, scene)
            if baseline_diff is not None:
                await report.update_from_dict({"baseline_diff": baseline_diff})
                await report.save()
        except Exception as e:
            LOGGER.error(f"基线对比回填失败: report_code={report_code}, 错误描述: {e}\n{traceback.format_exc()}")

        try:
            task_fields: Dict[str, Any] = {
                "last_execute_state": pipeline_status,
                "last_execute_time": datetime.now(),
            }
            if final_error:
                task_fields["last_execute_error"] = final_error
            await PerfTaskModel.filter(id=task.id).update(**task_fields)
        except Exception as e:
            LOGGER.error(
                f"压测任务状态回填失败: perf_code={perf_code}, 错误描述: {e}\n{traceback.format_exc()}"
            )

        # 产物目录保留(不随管线结束删除): 报告页原始分片与引擎日志下载依赖该目录,
        # 由报告删除接口随报告生命周期一并清理
        LOGGER.info(
            f"压测管线结束: perf_code={perf_code}, report_code={report_code}, "
            f"status={pipeline_status.value}, stopped_reason={stopped_reason.value}, "
            f"success={pipeline_status != PerfTaskStatus.FAILED}"
        )
        return {
            "success": pipeline_status != PerfTaskStatus.FAILED,
            "perf_code": perf_code,
            "report_code": report_code,
            "status": pipeline_status.value,
            "error": final_error,
        }
