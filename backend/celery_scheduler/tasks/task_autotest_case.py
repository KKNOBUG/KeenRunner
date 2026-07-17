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
from typing import Any, Dict, List, Optional

from backend.celery_scheduler.celery_base import (
    run_async,
    get_span_id_for_log,
    get_step_crud,
    get_task_model,
    get_task_status_enum,
    get_report_type_enum,
    get_scheduler_value,
    get_scheduled_tasks,
    check_task_expired,
)
from backend.celery_scheduler.celery_worker import celery
from backend.configure import LOGGER
from backend.enums import AutoTestReportType


async def _run_autotest_task_impl(task_id: int, report_type: Optional[AutoTestReportType] = None) -> Dict[str, Any]:
    """
    执行单个自动化任务：更新任务状态、批量执行用例、写回执行结果；datetime 调度执行后自动关闭。
    - 前端「执行」按钮触发的为手动调度，使用 ASYNC_EXEC（异步执行）
    - 定时扫描「启动」触发的为定时调度，使用 SCHEDULE_EXEC（定时执行）

    :param task_id: 业务任务 ID
    :param report_type: 报告类型（可选）。传入「异步执行」或 ASYNC_EXEC 时为异步执行，否则为定时执行
    :return: 包含 success、task_id、result/error 的字典
    """
    Model = get_task_model()
    Status = get_task_status_enum()
    ReportType = get_report_type_enum()
    span_id: str = get_span_id_for_log()
    task = await Model.get_or_none(id=task_id)
    if not task:
        LOGGER.warning(f"【Krun-Celery-Worker】【span_id={span_id}】任务不存在: task_id={task_id}")
        return {"success": False, "error": "任务不存在", "task_id": task_id}

    task_kwargs = getattr(task, "task_kwargs", None) or {}
    case_ids = task_kwargs.get("case_ids") if isinstance(task_kwargs, dict) else []
    if not task_kwargs or not case_ids:
        task.last_execute_time = datetime.now()
        task.last_execute_state = Status.FAILURE
        await task.save(update_fields=["last_execute_time", "last_execute_state"])
        LOGGER.warning(f"【Krun-Celery-Worker】【span_id={span_id}】关联用例列表为空: task_id={task_id}")
        return {"success": False, "error": "关联用例列表为空", "task_id": task_id}

    task.last_execute_time = datetime.now()
    task.last_execute_state = Status.RUNNING
    await task.save(update_fields=["last_execute_time", "last_execute_state"])
    try:
        crud = get_step_crud()
        # 仅当显式传入「异步执行」时为异步；其余（含定时扫描触发）为定时执行
        exec_report_type = ReportType.SCHEDULE_EXEC
        if report_type == ReportType.ASYNC_EXEC or (isinstance(report_type, str) and report_type.strip() == "异步执行"):
            exec_report_type = ReportType.ASYNC_EXEC
        initial_variables = (task_kwargs.get("initial_variables") or []) if isinstance(task_kwargs, dict) else []
        task_code = getattr(task, "task_code", None)
        cases_execute_config = getattr(task, "cases_execute_config", None) or {}
        if not cases_execute_config and isinstance(task_kwargs, dict):
            cases_execute_config = task_kwargs.get("cases_execute_config") or {}
        result = await crud.batch_execute_cases(
            case_ids=case_ids,
            report_type=exec_report_type,
            initial_variables=initial_variables,
            cases_execute_config=cases_execute_config if isinstance(cases_execute_config, dict) else {},
            task_code=task_code,
        )
        all_ok = result.get("summary", {}).get("all_success", False)
        task.last_execute_state = Status.SUCCESS if all_ok else Status.FAILURE
        await task.save(update_fields=["last_execute_state"])
        # datetime 调度为一次性任务，执行完毕后终止（关闭调度）
        if get_scheduler_value(getattr(task, "task_scheduler", None)) == "datetime":
            task.task_enabled = False
            await task.save(update_fields=["task_enabled"])
        batch_code = result.get("batch_code") if isinstance(result, dict) else None
        return {
            "success": True,
            "task_id": task_id,
            "batch_code": batch_code,
            "result": result,
        }
    except Exception as e:
        LOGGER.error(
            f"【Krun-Celery-Worker】【span_id={span_id}】函数run_autotest_task执行异常:"
            f"task_id=[{task_id}], "
            f"错误类型: {type(e).__name__}, "
            f"错误描述: {e}, \n"
            f"错误回溯: {traceback.format_exc()}"
        )
        task.last_execute_state = Status.FAILURE
        await task.save(update_fields=["last_execute_state"])
        # datetime 调度为一次性任务，执行失败也终止
        if get_scheduler_value(getattr(task, "task_scheduler", None)) == "datetime":
            task.task_enabled = False
            await task.save(update_fields=["task_enabled"])
        return {"success": False, "error": str(e), "task_id": task_id}


async def _scan_and_dispatch_impl() -> Dict[str, Any]:
    """扫描到期任务并逐个下发 run_autotest_task。"""
    span_id: str = get_span_id_for_log()
    tasks = await get_scheduled_tasks(task_type="autotest")
    dispatched = 0
    for task in tasks:
        try:
            due = await check_task_expired(task)
            if due:
                run_autotest_task.apply_async(
                    args=[task.id],
                    __task_id=task.id,
                )
                dispatched += 1
                LOGGER.info(
                    f"【Krun-Celery-Worker】【span_id={span_id}】扫描下发任务: "
                    f"task_id={task.id}, scheduler={getattr(task, 'task_scheduler', None)}, "
                    f"crontab={getattr(task, 'task_crontabs_expr', None)}, "
                    f"datetime={getattr(task, 'task_datetime_expr', None)}"
                )
            else:
                LOGGER.info(
                    f"【Krun-Celery-Worker】【span_id={span_id}】扫描未到期: "
                    f"task_id={task.id}, scheduler={getattr(task, 'task_scheduler', None)}, "
                    f"crontab={getattr(task, 'task_crontabs_expr', None)}, "
                    f"datetime={getattr(task, 'task_datetime_expr', None)}, "
                    f"last_execute_time={getattr(task, 'last_execute_time', None)}"
                )
        except Exception as e:
            task_id = getattr(task, "id", None)
            LOGGER.error(
                f"【Krun-Celery-Worker】【span_id={span_id}】函数scan_and_dispatch_autotest_tasks执行异常:"
                f"task_id=[{task_id}], "
                f"错误类型: {type(e).__name__}, "
                f"错误描述: {e}, \n"
                f"错误回溯: {traceback.format_exc()}"
            )
    return {"scanned": len(tasks), "dispatched": dispatched}


@celery.task(name="backend.celery_scheduler.tasks.task_autotest_case.execute_batch_cases_task")
def execute_batch_cases_task(
        case_ids: List[int],
        initial_variables: Optional[List[Dict[str, Any]]] = None,
        env_name: Optional[str] = None,
        report_type: Optional[str] = None,
):
    """
    批量执行用例，供 API 或其它任务调用。

    :param case_ids: 用例 ID 列表
    :param initial_variables: 初始变量（可选）
    :param env_name: 执行环境（可选）
    :param report_type: 报告类型（可选，默认异步执行）
    """
    crud = get_step_crud()
    rt = get_report_type_enum()
    report_type = report_type or getattr(rt, "ASYNC_EXEC", "异步执行")
    if isinstance(report_type, str) and hasattr(rt, "ASYNC_EXEC"):
        report_type = rt.ASYNC_EXEC
    return run_async(
        crud.batch_execute_cases(
            case_ids=case_ids,
            initial_variables=initial_variables or [],
            env_name=env_name,
            report_type=report_type,
        )
    )


@celery.task(name="backend.celery_scheduler.tasks.task_autotest_case.scan_and_dispatch_autotest_tasks")
def scan_and_dispatch_autotest_tasks():
    """定时扫描：从库中读取启用且配置了调度的任务，到期则下发 run_autotest_task。"""
    return run_async(_scan_and_dispatch_impl())


@celery.task(name="backend.celery_scheduler.tasks.task_autotest_case.run_autotest_task")
def run_autotest_task(task_id: int, report_type: Optional[AutoTestReportType] = None):
    """执行单个自动化任务（由扫描或 API 触发）；执行记录由 Worker 的 task_prerun/on_success/on_failure 维护。"""
    return run_async(_run_autotest_task_impl(task_id, report_type=report_type))
