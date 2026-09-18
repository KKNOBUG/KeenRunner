# -*- coding: utf-8 -*-
"""
数据作业Celery任务: 复用功能执行链跑脚本用例N轮(prepare造数/verify校验/cleanup清理)。

作业与压测热路径零交集, 固定走 {port}_perf 队列(路由见 celery_config.task_routes),
避免长时造数占用默认队列拖慢功能任务。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : task_perf_data_job.py
@DateTime: 2026/9/17 17:55
"""
from __future__ import annotations

import traceback
from typing import Any, Dict, Optional

from backend.applications.performance.services.perf_job_service import PerfJobService
from backend.celery_scheduler.celery_base import (
    get_span_id_for_log,
    run_async,
)
from backend.celery_scheduler.celery_worker import celery
from backend.configure import LOGGER

_LOG_PREFIX = "【Celery-Worker】"


async def _run_perf_data_job_impl(job_code: str, celery_id: Optional[str],
                                  created_user: Optional[str]) -> Dict[str, Any]:
    """
    执行单个数据作业的核心逻辑, 委托作业服务编排执行链并做外层兜底。

    :param job_code: 数据作业标识代码
    :param celery_id: Celery任务ID(回填作业执行观测)
    :param created_user: 触发人账号(执行归因)
    :return: 作业执行结果字典(见 PerfJobService.execute_job)
    :raises Exception: 外层兜底后的残余异常, 交由 Celery on_failure 记录
    """
    span_id = get_span_id_for_log()
    try:
        result = await PerfJobService.execute_job(
            job_code=job_code,
            celery_id=celery_id,
            created_user=created_user,
        )
        LOGGER.info(
            f"{_LOG_PREFIX}【span_id={span_id}】数据作业执行完成: "
            f"job_code={job_code}, status={result.get('status')}, "
            f"skipped={result.get('skipped', False)}, "
            f"result_rows={result.get('result_rows')}, report_code={result.get('report_code')}"
        )
        return result
    except Exception as e:
        # execute_job 内部已兜底置failed; 此处为极端场景(如DB不可达)的最终防线:
        # 异常上抛由 Celery on_failure 记录, claim_running闸门保证重投不会双跑
        LOGGER.error(
            f"{_LOG_PREFIX}【span_id={span_id}】run_perf_data_job 异常: "
            f"job_code={job_code}, 错误类型: {type(e).__name__}, 错误描述: {e}\n"
            f"{traceback.format_exc()}"
        )
        raise


@celery.task(
    name="backend.celery_scheduler.tasks.task_perf_data_job.run_perf_data_job",
    # 失败/超时即ack终结消息: 失败结果已落作业表并回填failed, 消息重投会被
    # claim_running闸门拦截(状态非pending), 不会重复造数;
    # worker进程崩溃/硬时限杀进程(WorkerLostError)由task_reject_on_worker_lost重投,
    # 重投消息同样被闸门拦截
    acks_on_failure_or_timeout=True,
    # 任务级时限覆盖全局: loop_times上限1000轮×每轮完整功能执行, 与压测任务同量级;
    # 软时限抛SoftTimeLimitExceeded后服务层兜底置failed, 硬时限与broker
    # visibility_timeout(36000)对齐
    soft_time_limit=32400,
    time_limit=36000,
)
def run_perf_data_job(job_code: str, created_user: Optional[str] = None):
    """
    执行单个数据作业，由 /perf/job/run 接口下发。

    :param job_code: 数据作业标识代码
    :param created_user: 触发用户账号(执行归因)
    :return: 作业执行结果字典
    """
    return run_async(_run_perf_data_job_impl(job_code, run_perf_data_job.request.id, created_user))
