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

from backend.applications.autotest.models.autotest_task_model import AutoTestTaskModel
from backend.applications.autotest.services.autotest_step_crud import AutoTestStepCrud
from backend.applications.autotest.services.autotest_task_schedule import (
    fetch_schedulable_tasks,
    is_task_due,
)
from backend.celery_scheduler.celery_base import (
    get_span_id_for_log,
    run_async,
)
from backend.celery_scheduler.celery_worker import celery
from backend.configure import LOGGER
from backend.enums import (
    AutoTestReportType,
    AutoTestTaskStatus,
    AutoTestTaskType,
)

_LOG_PREFIX = "【Celery-Worker】"


def _should_close_schedule(task: Any) -> bool:
    """
    判断调度执行结束后是否应关闭调度：ONLY_ONCE且全部触发日期时间均已被派发执行。

    :param task: 自动化任务模型实例
    :return: 应关闭为True
    """
    from backend.applications.autotest.services.autotest_task_schedule import TaskSchedule
    schedule_obj = TaskSchedule.from_expr(
        periodic=getattr(task, "task_periodic_expr", None),
        schedule=getattr(task, "task_schedule_expr", None),
    )
    if schedule_obj is None or not schedule_obj.is_only_once:
        return False
    # 以“本次执行启动时刻(last_execute_time)”为基准判定：触发点由扫描逐点派发，
    # worker启动执行时已先回填该时刻，若其已越过最后一个触发点，说明全部触发点均已消费；
    # 若用墙钟now判断，单次执行耗时跨越下一个未触发触发点时会把未派发的触发点一并误杀
    last_run = getattr(task, "last_execute_time", None)
    if last_run is None:
        return False
    if getattr(last_run, "tzinfo", None):
        last_run = last_run.replace(tzinfo=None)
    return schedule_obj.is_completed(last_run)


async def _run_autotest_task_impl(task_id: int, report_type: Optional[AutoTestReportType] = None, execute_user: Optional[str] = None) -> Dict[str, Any]:
    """
    执行单个自动化任务的核心逻辑，区分手动与扫描触发并写回执行状态。

    :param task_id: 自动化任务主键ID
    :param report_type: 报告类型；为ASYNC_EXEC或异步执行时根据手动执行处理
    :param execute_user: 手动触发人账号；定时触发时为空，回退取任务维护人(配置即触发)
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
    # 执行人归因链：手动执行取触发人；调度触发回退维护人(启停调度会刷新维护人，最近操作者即归因对象)
    last_execute_user = execute_user or getattr(task, "updated_user", None) or None
    case_ids = getattr(task, "task_case_ids", None) or []
    if not case_ids:
        task.last_execute_time = datetime.now()
        task.last_execute_state = AutoTestTaskStatus.FAILURE
        task.last_execute_user = last_execute_user
        await task.save(update_fields=["last_execute_time", "last_execute_state", "last_execute_user"])
        LOGGER.warning(
            f"{_LOG_PREFIX}【span_id={span_id}】关联用例列表为空: "
            f"task_id={task_id}, task_code={task_code}, task_name={task_name}"
        )
        return {"success": False, "error": "关联用例列表为空", "task_id": task_id}

    task.last_execute_time = datetime.now()
    task.last_execute_state = AutoTestTaskStatus.RUNNING
    task.last_execute_user = last_execute_user
    await task.save(update_fields=["last_execute_time", "last_execute_state", "last_execute_user"])

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
        # 获取initial_variables
        task_kwargs = getattr(task, "task_kwargs", None) or {}
        initial_variables = (task_kwargs.get("initial_variables") or []) if isinstance(task_kwargs, dict) else []
        started = datetime.now()
        result = await AutoTestStepCrud().batch_execute_cases(
            case_ids=case_ids,
            report_type=exec_report_type,
            initial_variables=initial_variables,
            cases_execute_config=cases_execute_config if isinstance(cases_execute_config, dict) else {},
            task_code=task_code,
            dataset_enabled=bool(getattr(task, "dataset_enabled", False)),
            # 执行模式取自任务配置(并行执行/串行执行)：造数依赖类任务配置串行以保持用例先后顺序
            execute_mode=getattr(task, "task_execute_mode", None),
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
        if exec_report_type == AutoTestReportType.SCHEDULE_EXEC and _should_close_schedule(task):
            task.task_enabled = False
            await task.save(update_fields=["task_enabled"])
            LOGGER.info(
                f"{_LOG_PREFIX}【span_id={span_id}】执行1次任务已全部触发并关闭调度: "
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
        if exec_report_type == AutoTestReportType.SCHEDULE_EXEC and _should_close_schedule(task):
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
    tasks = await fetch_schedulable_tasks(task_type=AutoTestTaskType.AUTOTEST_API)
    LOGGER.info(
        f"{_LOG_PREFIX}【span_id={span_id}】开始扫描定时任务: "
        f"task_type={AutoTestTaskType.AUTOTEST_API.value}, candidate_count={len(tasks)}"
    )
    dispatched = 0
    for task in tasks:
        try:
            if is_task_due(task):
                run_autotest_task.apply_async(args=[task.id], __task_id=task.id)
                dispatched += 1
                LOGGER.info(
                    f"{_LOG_PREFIX}【span_id={span_id}】扫描下发: "
                    f"task_id={task.id}, task_code={getattr(task, 'task_code', None)}, "
                    f"task_name={getattr(task, 'task_name', None)}, "
                    f"schedule={task.task_schedule_expr}, "
                    f"periodic={task.task_periodic_expr}"
                )
            else:
                LOGGER.debug(
                    f"{_LOG_PREFIX}【span_id={span_id}】扫描未到期: "
                    f"task_id={task.id}, task_code={getattr(task, 'task_code', None)}, "
                    f"schedule={task.task_schedule_expr}, "
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
    Beat入口，扫描启用中的定时任务，到期则下发run_autotest_task。

    :return: 扫描与下发统计字典
    """
    return run_async(_scan_and_dispatch_impl())


@celery.task(
    name="backend.celery_scheduler.tasks.task_autotest_case.run_autotest_task",
    # 失败/超时即ack终结消息：失败结果已落record并回填任务状态，重新执行只会重复写记录且依旧失败；
    # worker进程崩溃/硬时限杀进程(WorkerLostError)由task_reject_on_worker_lost重投，优先于本参数
    acks_on_failure_or_timeout=True,
    # 任务级时限覆盖全局(3300/3600)：整批任务绑定多脚本串行数小时为正常场景；软时限向任务抛出
    # SoftTimeLimitExceeded后会被单用例兜底捕获(信号仅发一次)，整批的强制停止依赖硬时限兜底
    soft_time_limit=25200,
    time_limit=28800,
)
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
    # created_user 随kwargs传到Worker：task_prerun写入执行记录，并回填任务表last_execute_user(定时触发为空时由impl回退维护人)
    return run_async(_run_autotest_task_impl(task_id, report_type=report_type, execute_user=created_user))
