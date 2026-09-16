# # -*- coding: utf-8 -*-
# """
# 压测执行 Celery 编排任务：消费 {port}_perf 专用队列(见 celery_config.task_routes),
# worker 以 concurrency=1 串行消费, 同一时间单机仅一个压测批次。
#
# 任务体为薄编排：消费闸门与全部管线逻辑在 PerfExecuteService.execute_pipeline,
# 本层仅负责 Celery 上下文(任务ID透传)与外层兜底(任何异常保证任务表不卡 running)。
#
# @Author  : yangkai
# @Email   : 807440781@qq.com
# @Project : Krun
# @Module  : task_performance.py
# @DateTime: 2026/9/14 15:30
# """
# from __future__ import annotations
#
# import traceback
# from datetime import datetime
# from typing import Any, Dict, Optional
#
# from backend.applications.performance.services.perf_execute_service import PerfExecuteService
# from backend.celery_scheduler.celery_base import (
#     get_span_id_for_log,
#     run_async,
# )
# from backend.celery_scheduler.celery_worker import celery
# from backend.configure import LOGGER
# from backend.enums import PerfTaskStatus
#
# _LOG_PREFIX = "【Celery-Worker】"
#
#
# async def _run_perf_task_impl(perf_code: str, celery_id: Optional[str], execute_user: Optional[str]) -> Dict[str, Any]:
#     """
#     执行单个压测任务的核心逻辑, 委托执行服务编排管线并做外层兜底。
#
#     :param perf_code: 压测任务标识代码
#     :param celery_id: Celery任务ID(透传至报告与任务表回填)
#     :param execute_user: 触发人账号
#     :return: 管线执行结果字典(见 PerfExecuteService.execute_pipeline)
#     :raises Exception: 外层兜底后的残余异常, 交由 Celery on_failure 记录
#     """
#     span_id = get_span_id_for_log()
#     try:
#         result = await PerfExecuteService.execute_pipeline(
#             perf_code=perf_code,
#             celery_id=celery_id,
#             execute_user=execute_user,
#         )
#         LOGGER.info(
#             f"{_LOG_PREFIX}【span_id={span_id}】压测任务执行完成: "
#             f"perf_code={perf_code}, report_code={result.get('report_code')}, "
#             f"status={result.get('status')}, success={result.get('success')}, "
#             f"error={result.get('error')}"
#         )
#         return result
#     except Exception as e:
#         # execute_pipeline 内部已全量兜底置failed; 此处为极端场景(如DB不可达)的最终防线:
#         # 直改任务表状态(不依赖报告), 保证任务不卡 running
#         LOGGER.error(
#             f"{_LOG_PREFIX}【span_id={span_id}】run_perf_task 异常: "
#             f"perf_code={perf_code}, 错误类型: {type(e).__name__}, 错误描述: {e}\n"
#             f"{traceback.format_exc()}"
#         )
#         try:
#             from backend.applications.performance.models.perf_task_model import PerfTaskModel
#
#             await PerfTaskModel.filter(perf_code=perf_code).exclude(
#                 last_execute_state__in=[PerfTaskStatus.COMPLETED, PerfTaskStatus.FAILED, PerfTaskStatus.STOPPED],
#             ).update(
#                 last_execute_state=PerfTaskStatus.FAILED,
#                 last_execute_time=datetime.now(),
#                 last_execute_error=f"执行管线异常: {type(e).__name__}: {e}",
#             )
#         except Exception as fallback_error:
#             LOGGER.error(
#                 f"{_LOG_PREFIX}【span_id={span_id}】压测任务兜底状态回填失败: "
#                 f"perf_code={perf_code}, 错误描述: {fallback_error}\n{traceback.format_exc()}"
#             )
#         raise
#
#
# @celery.task(
#     name="backend.celery_scheduler.tasks.task_performance.run_perf_task",
#     # 失败/超时即ack终结消息: 失败结果已落报告并回填任务状态, 重新执行只会重复压测;
#     # worker进程崩溃/硬时限杀进程(WorkerLostError)由task_reject_on_worker_lost重投,
#     # 重投消息被execute_pipeline消费闸门拦截(状态非queued), 不会重复施压
#     acks_on_failure_or_timeout=True,
#     # 任务级时限覆盖全局(3300/3600): 施压时长上限PERF_RUN_DURATION_MAX=28800, 叠加
#     # 启动/收尾开销后软时限9h抛SoftTimeLimitExceeded(管线异常分支兜底置failed),
#     # 硬时限10h与broker visibility_timeout对齐兜底
#     soft_time_limit=32400,
#     time_limit=36000,
# )
# def run_perf_task(perf_code: str, created_user: Optional[str] = None):
#     """
#     执行单个压测任务，由 /perf/task/run 接口下发。
#
#     :param perf_code: 压测任务标识代码
#     :param created_user: 触发用户账号(报告执行人归因)
#     :return: 管线执行结果字典
#     """
#     return run_async(_run_perf_task_impl(perf_code, run_perf_task.request.id, created_user))
