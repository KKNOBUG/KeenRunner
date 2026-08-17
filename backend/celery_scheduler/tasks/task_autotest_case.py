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

from backend.applications.aotutest.models.autotest_task_model import AutoTestTaskModel
from backend.applications.aotutest.services.autotest_step_crud import AutoTestStepCrud
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

_LOG_PREFIX = "【Celery-Worker】"


def _is_only_once(task: Any) -> bool:
    """
    判断任务周期策略是否为ONLY_ONCE。

    :param task: 自动化任务模型实例
    :return: 为ONLY_ONCE时返回True
    """
    expr = getattr(task, "task_periodic_expr", None)
    value = getattr(expr, "value", None) or expr
    return (str(value).strip() if value is not None else "") == AutoTestTaskPeriodicSwitch.ONLY_ONCE.value


async def _run_autotest_task_impl(task_id: int, report_type: Optional[AutoTestReportType] = None) -> Dict[str, Any]:
    """
    执行单个自动化任务的核心逻辑，区分手动与扫描触发并写回执行状态。

    :param task_id: 自动化任务主键ID
    :param report_type: 报告类型；为ASYNC_EXEC或异步执行时根据手动执行处理
    :return: 含success、task_id及批次执行汇总的字典
    :raises Exception: 执行过程异常时重新抛出，供Celery on_failure更新记录
    """
    span_id = get_span_id_for_log()
    task = await AutoTestTaskModel.get_or_none(id=task_id)
    if not task:
        LOGGER.warning(f"{_LOG_PREFIX}【span_id={span_id}】任务不存在: task_id={task_id}")
        return {"success": False, "error": "任务不存在", "task_id": task_id}

    task_code = getattr(task, "task_code", None)
    task_name = getattr(task, "task_name", None)
    task_kwargs = getattr(task, "task_kwargs", None) or {}
    case_ids = task_kwargs.get("case_ids") if isinstance(task_kwargs, dict) else []
    if not case_ids:
        task.last_execute_time = datetime.now()
        task.last_execute_state = AutoTestTaskStatus.FAILURE
        await task.save(update_fields=["last_execute_time", "last_execute_state"])
        LOGGER.warning(
            f"{_LOG_PREFIX}【span_id={span_id}】关联用例列表为空: "
            f"task_id={task_id}, task_code={task_code}, task_name={task_name}"
        )
        return {"success": False, "error": "关联用例列表为空", "task_id": task_id}

    task.last_execute_time = datetime.now()
    task.last_execute_state = AutoTestTaskStatus.RUNNING
    await task.save(update_fields=["last_execute_time", "last_execute_state"])

    exec_report_type = AutoTestReportType.SCHEDULE_EXEC
    if report_type == AutoTestReportType.ASYNC_EXEC or (
            isinstance(report_type, str) and report_type.strip() == "异步执行"
    ):
        exec_report_type = AutoTestReportType.ASYNC_EXEC

    report_val = getattr(exec_report_type, "value", exec_report_type)
    LOGGER.info(
        f"{_LOG_PREFIX}【span_id={span_id}】开始执行自动化任务: "
        f"task_id={task_id}, task_code={task_code}, task_name={task_name}, "
        f"report_type={report_val}, case_count={len(case_ids)}, case_ids={case_ids}"
    )

    try:
        cases_execute_config = getattr(task, "cases_execute_config", None) or {}
        if not cases_execute_config and isinstance(task_kwargs, dict):
            cases_execute_config = task_kwargs.get("cases_execute_config") or {}
        started = datetime.now()
        result = await AutoTestStepCrud().batch_execute_cases(
            case_ids=case_ids,
            report_type=exec_report_type,
            initial_variables=(task_kwargs.get("initial_variables") or []) if isinstance(task_kwargs, dict) else [],
            cases_execute_config=cases_execute_config if isinstance(cases_execute_config, dict) else {},
            task_code=task_code,
        )
        elapsed = (datetime.now() - started).total_seconds()
        total_cases = int(result.get("total_cases") or 0)
        success_cases = int(result.get("success_cases") or 0)
        if 0 < total_cases == success_cases:
            task.last_execute_state = AutoTestTaskStatus.SUCCESS
        elif success_cases >= 1:
            task.last_execute_state = AutoTestTaskStatus.PARTIAL_SUCCESS
        else:
            task.last_execute_state = AutoTestTaskStatus.FAILURE
        await task.save(update_fields=["last_execute_state"])
        if exec_report_type == AutoTestReportType.SCHEDULE_EXEC and _is_only_once(task):
            task.task_enabled = False
            await task.save(update_fields=["task_enabled"])
            LOGGER.info(
                f"{_LOG_PREFIX}【span_id={span_id}】执行1次任务已关闭调度: "
                f"task_id={task_id}, task_code={task_code}"
            )
        LOGGER.info(
            f"{_LOG_PREFIX}【span_id={span_id}】自动化任务执行完成: "
            f"task_id={task_id}, task_code={task_code}, task_name={task_name}, "
            f"report_type={report_val}, batch_code={result.get('batch_code')}, "
            f"total_cases={result.get('total_cases')}, "
            f"success_cases={result.get('success_cases')}, "
            f"failed_cases={result.get('failed_cases')}, "
            f"success_rate={result.get('success_rate')}, "
            f"elapsed={elapsed:.2f}s"
        )
        # 任务体未抛异常、流程跑完
        return {"success": True, "task_id": task_id, **result}
    except Exception as e:
        LOGGER.error(
            f"{_LOG_PREFIX}【span_id={span_id}】run_autotest_task 异常: "
            f"task_id={task_id}, task_code={task_code}, task_name={task_name}, "
            f"report_type={report_val}, case_ids={case_ids}, "
            f"错误类型: {type(e).__name__}, 错误描述: {e}\n"
            f"{traceback.format_exc()}"
        )
        task.last_execute_state = AutoTestTaskStatus.FAILURE
        await task.save(update_fields=["last_execute_state"])
        if exec_report_type == AutoTestReportType.SCHEDULE_EXEC and _is_only_once(task):
            task.task_enabled = False
            await task.save(update_fields=["task_enabled"])
        # 重新抛出，让 Celery on_failure 将执行记录从「正在执行」更新为「失败」
        raise


async def _scan_and_dispatch_impl() -> Dict[str, Any]:
    """
    扫描到期的定时自动化任务，并下发run_autotest_task。

    :return: {"scanned": int, "dispatched": int}扫描与下发统计
    """
    span_id = get_span_id_for_log()
    tasks = await get_scheduled_tasks(task_type=AutoTestTaskType.AUTOTEST_API)
    LOGGER.info(
        f"{_LOG_PREFIX}【span_id={span_id}】开始扫描定时任务: "
        f"task_type={AutoTestTaskType.AUTOTEST_API.value}, candidate_count={len(tasks)}"
    )
    dispatched = 0
    for task in tasks:
        try:
            if check_task_expired(task):
                run_autotest_task.apply_async(args=[task.id], __task_id=task.id)
                dispatched += 1
                LOGGER.info(
                    f"{_LOG_PREFIX}【span_id={span_id}】扫描下发: "
                    f"task_id={task.id}, task_code={getattr(task, 'task_code', None)}, "
                    f"task_name={getattr(task, 'task_name', None)}, "
                    f"crontab={task.task_crontabs_expr}, "
                    f"periodic={task.task_periodic_expr}"
                )
            else:
                LOGGER.debug(
                    f"{_LOG_PREFIX}【span_id={span_id}】扫描未到期: "
                    f"task_id={task.id}, task_code={getattr(task, 'task_code', None)}, "
                    f"crontab={task.task_crontabs_expr}, "
                    f"last_execute_time={task.last_execute_time}"
                )
        except Exception as e:
            LOGGER.error(
                f"{_LOG_PREFIX}【span_id={span_id}】扫描异常: "
                f"task_id=[{getattr(task, 'id', None)}], "
                f"task_code={getattr(task, 'task_code', None)}, "
                f"错误类型: {type(e).__name__}, 错误描述: {e}\n{traceback.format_exc()}"
            )
    LOGGER.info(
        f"{_LOG_PREFIX}【span_id={span_id}】扫描结束: "
        f"scanned={len(tasks)}, dispatched={dispatched}"
    )
    return {"scanned": len(tasks), "dispatched": dispatched}


@celery.task(name="backend.celery_scheduler.tasks.task_autotest_case.scan_and_dispatch_autotest_tasks")
def scan_and_dispatch_autotest_tasks():
    """
    Beat入口，扫描启用中的Cron任务，到期则下发run_autotest_task。

    :return: 扫描与下发统计字典
    """
    return run_async(_scan_and_dispatch_impl())


@celery.task(name="backend.celery_scheduler.tasks.task_autotest_case.run_autotest_task")
def run_autotest_task(
        task_id: int,
        report_type: Optional[AutoTestReportType] = None,
        created_user: Optional[str] = None,
):
    """
    执行单个自动化任务，由扫描或API触发。

    :param task_id: 自动化任务主键ID
    :param report_type: 报告类型(手动异步/调度)
    :param created_user: 触发用户账号(可选)
    :return: 任务执行结果字典
    """
    # created_user 随kwargs传到Worker，供task_prerun写入执行记录；此处不参与业务执行
    _ = created_user
    return run_async(_run_autotest_task_impl(task_id, report_type=report_type))
