# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : task_autotest_case
@DateTime: 2026/2/1 16:10
"""
from __future__ import annotations

import traceback
from datetime import datetime
from typing import Any, Dict, Optional

from backend.applications.aotutest.models.autotest_model import AutoTestApiTaskInfo
from backend.applications.aotutest.services.autotest_step_crud import AutoTestApiStepCrud
from backend.celery_scheduler.celery_base import (
    check_task_expired,
    get_scheduled_tasks,
    get_span_id_for_log,
    run_async,
)
from backend.celery_scheduler.celery_worker import celery
from backend.configure import LOGGER
from backend.enums import (
    AutoTestReportType,
    AutoTestTaskPeriodicSwitch,
    AutoTestTaskStatus,
    AutoTestTaskType,
)


def _is_only_once(task: Any) -> bool:
    expr = getattr(task, "task_periodic_expr", None)
    value = getattr(expr, "value", None) or expr
    return (str(value).strip() if value is not None else "") == AutoTestTaskPeriodicSwitch.ONLY_ONCE.value


async def _run_autotest_task_impl(
    task_id: int,
    report_type: Optional[AutoTestReportType] = None,
) -> Dict[str, Any]:
    """
    执行单个自动化任务。
    - 手动「执行」：ASYNC_EXEC，不因「执行1次」关闭调度
    - 扫描触发：SCHEDULE_EXEC；若 task_periodic_expr=执行1次，执行后关闭调度
    """
    span_id = get_span_id_for_log()
    task = await AutoTestApiTaskInfo.get_or_none(id=task_id)
    if not task:
        LOGGER.warning(f"【Krun-Celery-Worker】【span_id={span_id}】任务不存在: task_id={task_id}")
        return {"success": False, "error": "任务不存在", "task_id": task_id}

    task_kwargs = getattr(task, "task_kwargs", None) or {}
    case_ids = task_kwargs.get("case_ids") if isinstance(task_kwargs, dict) else []
    if not case_ids:
        task.last_execute_time = datetime.now()
        task.last_execute_state = AutoTestTaskStatus.FAILURE
        await task.save(update_fields=["last_execute_time", "last_execute_state"])
        LOGGER.warning(f"【Krun-Celery-Worker】【span_id={span_id}】关联用例列表为空: task_id={task_id}")
        return {"success": False, "error": "关联用例列表为空", "task_id": task_id}

    task.last_execute_time = datetime.now()
    task.last_execute_state = AutoTestTaskStatus.RUNNING
    await task.save(update_fields=["last_execute_time", "last_execute_state"])

    exec_report_type = AutoTestReportType.SCHEDULE_EXEC
    if report_type == AutoTestReportType.ASYNC_EXEC or (
        isinstance(report_type, str) and report_type.strip() == "异步执行"
    ):
        exec_report_type = AutoTestReportType.ASYNC_EXEC

    try:
        cases_execute_config = getattr(task, "cases_execute_config", None) or {}
        if not cases_execute_config and isinstance(task_kwargs, dict):
            cases_execute_config = task_kwargs.get("cases_execute_config") or {}
        result = await AutoTestApiStepCrud().batch_execute_cases(
            case_ids=case_ids,
            report_type=exec_report_type,
            initial_variables=(task_kwargs.get("initial_variables") or []) if isinstance(task_kwargs, dict) else [],
            cases_execute_config=cases_execute_config if isinstance(cases_execute_config, dict) else {},
            task_code=getattr(task, "task_code", None),
        )
        all_ok = result.get("summary", {}).get("all_success", False)
        task.last_execute_state = AutoTestTaskStatus.SUCCESS if all_ok else AutoTestTaskStatus.FAILURE
        await task.save(update_fields=["last_execute_state"])
        if exec_report_type == AutoTestReportType.SCHEDULE_EXEC and _is_only_once(task):
            task.task_enabled = False
            await task.save(update_fields=["task_enabled"])
            LOGGER.info(
                f"【Krun-Celery-Worker】【span_id={span_id}】执行1次任务已关闭调度: task_id={task_id}"
            )
        return {
            "success": True,
            "task_id": task_id,
            "batch_code": result.get("batch_code") if isinstance(result, dict) else None,
            "result": result,
        }
    except Exception as e:
        LOGGER.error(
            f"【Krun-Celery-Worker】【span_id={span_id}】run_autotest_task 异常: "
            f"task_id=[{task_id}], 错误类型: {type(e).__name__}, 错误描述: {e}\n"
            f"{traceback.format_exc()}"
        )
        task.last_execute_state = AutoTestTaskStatus.FAILURE
        await task.save(update_fields=["last_execute_state"])
        if exec_report_type == AutoTestReportType.SCHEDULE_EXEC and _is_only_once(task):
            task.task_enabled = False
            await task.save(update_fields=["task_enabled"])
        return {"success": False, "error": str(e), "task_id": task_id}


async def _scan_and_dispatch_impl() -> Dict[str, Any]:
    """扫描到期任务并下发 run_autotest_task。"""
    span_id = get_span_id_for_log()
    tasks = await get_scheduled_tasks(task_type=AutoTestTaskType.AUTOTEST_API)
    dispatched = 0
    for task in tasks:
        try:
            if check_task_expired(task):
                run_autotest_task.apply_async(args=[task.id], __task_id=task.id)
                dispatched += 1
                LOGGER.info(
                    f"【Krun-Celery-Worker】【span_id={span_id}】扫描下发: "
                    f"task_id={task.id}, crontab={task.task_crontabs_expr}, "
                    f"periodic={task.task_periodic_expr}"
                )
            else:
                LOGGER.debug(
                    f"【Krun-Celery-Worker】【span_id={span_id}】扫描未到期: "
                    f"task_id={task.id}, crontab={task.task_crontabs_expr}, "
                    f"last_execute_time={task.last_execute_time}"
                )
        except Exception as e:
            LOGGER.error(
                f"【Krun-Celery-Worker】【span_id={span_id}】扫描异常: "
                f"task_id=[{getattr(task, 'id', None)}], "
                f"错误类型: {type(e).__name__}, 错误描述: {e}\n{traceback.format_exc()}"
            )
    return {"scanned": len(tasks), "dispatched": dispatched}


@celery.task(name="backend.celery_scheduler.tasks.task_autotest_case.scan_and_dispatch_autotest_tasks")
def scan_and_dispatch_autotest_tasks():
    """Beat 入口：扫描启用中的 Cron 任务，到期则下发 run_autotest_task。"""
    return run_async(_scan_and_dispatch_impl())


@celery.task(name="backend.celery_scheduler.tasks.task_autotest_case.run_autotest_task")
def run_autotest_task(task_id: int, report_type: Optional[AutoTestReportType] = None):
    """执行单个自动化任务（扫描或 API 触发）；执行记录由 Worker 信号维护。"""
    return run_async(_run_autotest_task_impl(task_id, report_type=report_type))
