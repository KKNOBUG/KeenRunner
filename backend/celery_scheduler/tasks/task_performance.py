# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : task_performance.py
@DateTime: 2026/9/14 15:30

性能压测执行任务：把单个负载预设交给 PerfExecuteService 编排管线，并做外层异常兜底与状态回填。
"""
from __future__ import annotations

import traceback
from datetime import datetime
from typing import Any, Dict, Optional

from backend.applications.performance.services.perf_execute_service import PerfExecuteService
from backend.celery_scheduler.celery_base import get_span_id_for_log
from backend.celery_scheduler.celery_worker import celery
from backend.common import AsyncEventLoopContextIOPool
from backend.configure import LOGGER
from backend.enums import PerfPresetStatus

# 与 celery_worker 一致的前缀，便于按前缀检索同一 worker 进程内的日志
_LOG_PREFIX = "【Celery-Worker】"


async def _run_perf_preset_impl(preset_code: str, celery_id: Optional[str], execute_user: Optional[str]) -> Dict[str, Any]:
    """
    执行单个负载预设的核心逻辑, 委托执行服务编排管线并做外层兜底。

    :param preset_code: 负载预设标识代码
    :param celery_id: Celery任务ID(透传至报告与负载预设表回填)
    :param execute_user: 触发人账号
    :return: 管线执行结果字典(见 PerfExecuteService.execute_pipeline)
    :raises Exception: 外层兜底后的残余异常, 交由 Celery on_failure 记录
    """
    span_id = get_span_id_for_log()
    try:
        result = await PerfExecuteService.execute_pipeline(
            preset_code=preset_code,
            celery_id=celery_id,
            execute_user=execute_user,
        )
        LOGGER.info(
            f"{_LOG_PREFIX}【span_id={span_id}】负载预设执行完成: "
            f"preset_code={preset_code}, report_code={result.get('report_code')}, "
            f"status={result.get('status')}, success={result.get('success')}, "
            f"error={result.get('error')}"
        )
        return result
    except Exception as e:
        # execute_pipeline 内部已全量兜底置failed; 此处为极端场景(如DB不可达)的最终防线:
        # 直改负载预设表状态(不依赖报告), 保证负载预设不卡 running
        LOGGER.error(
            f"{_LOG_PREFIX}【span_id={span_id}】run_perf_preset 异常: "
            f"preset_code={preset_code}, 错误类型: {type(e).__name__}, 错误描述: {e}\n"
            f"{traceback.format_exc()}"
        )
        try:
            from backend.applications.performance.models.perf_load_preset_model import PerfLoadPresetModel

            # 只覆盖仍处于非终态的预设：已落到完成/失败/停止的记录不再改写，避免迟到的异常覆盖真实终态
            await PerfLoadPresetModel.filter(preset_code=preset_code).exclude(
                last_execute_state__in=[PerfPresetStatus.COMPLETED, PerfPresetStatus.FAILED, PerfPresetStatus.STOPPED],
            ).update(
                last_execute_state=PerfPresetStatus.FAILED,
                last_execute_time=datetime.now(),
                last_execute_error=f"执行管线异常: {type(e).__name__}: {e}",
            )
        except Exception as fallback_error:
            LOGGER.error(
                f"{_LOG_PREFIX}【span_id={span_id}】负载预设兜底状态回填失败: "
                f"preset_code={preset_code}, 错误描述: {fallback_error}\n{traceback.format_exc()}"
            )
        raise


@celery.task(
    name="backend.celery_scheduler.tasks.task_performance.run_perf_preset",
    # 失败/超时即ack终结消息: 失败结果已落报告并回填负载预设状态, 重新执行只会重复压测;
    # worker进程崩溃/硬时限杀进程(WorkerLostError)由task_reject_on_worker_lost重投,
    # 重投消息被execute_pipeline消费闸门拦截(状态非queued), 不会重复施压
    acks_on_failure_or_timeout=True,
    # 任务级时限覆盖全局(3300/3600): 施压时长上限PERF_RUN_DURATION_MAX=28800, 叠加
    # 启动/收尾开销后软时限9h抛SoftTimeLimitExceeded(管线异常分支兜底置failed),
    # 硬时限10h与broker visibility_timeout对齐兜底
    soft_time_limit=32400,
    time_limit=36000,
)
def run_perf_preset(preset_code: str, created_user: Optional[str] = None):
    """
    执行单个负载预设，由 /perf/load_preset/run 接口下发。

    任务ID取当前 Celery request.id，透传到报告与负载预设表回填执行观测（不在入参中传递）。

    :param preset_code: 负载预设标识代码
    :param created_user: 触发用户账号(报告执行人归因)
    :return: 管线执行结果字典
    """
    return AsyncEventLoopContextIOPool.run_in_pool(
        _run_perf_preset_impl(preset_code, run_perf_preset.request.id, created_user)
    )
