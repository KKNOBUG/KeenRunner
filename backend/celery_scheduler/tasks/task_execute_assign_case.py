# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : task_execute_assign_case.py
@DateTime: 2026/3/20

在 Celery Worker 后台执行单用例步骤树（SCHEDULE_EXEC 等）：
- 调用 AUTOTEST_API_STEP_CRUD.execute_single_case 写入报告/明细
- 支持 steps_execute_config、参数化 selected_dataset_names
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.applications.aotutest.schemas.autotest_step_schema import StepVariablesBase
from backend.applications.aotutest.services.autotest_step_crud import AUTOTEST_API_STEP_CRUD
from backend.celery_scheduler.celery_base import run_async
from backend.celery_scheduler.celery_worker import celery
from backend.configure import LOGGER
from backend.enums import AutoTestReportType


def _normalize_initial_variables(
        raw: Optional[List[Dict[str, Any]]],
) -> List[StepVariablesBase]:
    if not raw:
        return []
    out: List[StepVariablesBase] = []
    for item in raw:
        if isinstance(item, StepVariablesBase):
            out.append(item)
        elif isinstance(item, dict):
            out.append(StepVariablesBase.model_validate(item))
    return out


async def _execute_step_tree_impl(
        case_id: int,
        initial_variables: Optional[List[Dict[str, Any]]] = None,
        report_type: Optional[AutoTestReportType] = None,
        batch_code: Optional[str] = None,
        selected_dataset_names: Optional[List[str]] = None,
        steps_execute_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if selected_dataset_names is None:
        selected_dataset_names = []
    initial_variables = _normalize_initial_variables(initial_variables)

    exec_report_type = report_type or AutoTestReportType.SCHEDULE_EXEC

    if not selected_dataset_names:
        result = await AUTOTEST_API_STEP_CRUD.execute_single_case(
            case_id=case_id,
            initial_variables=initial_variables,
            steps_execute_config=steps_execute_config,
            report_type=exec_report_type,
            batch_code=batch_code,
            dataset_name=None,
        )
        result["parameterized"] = False
        result["dataset_name"] = None
        return {
            "parameterized": False,
            "execute_count": 1,
            "success_count": 1 if result.get("success") else 0,
            "failed_count": 0 if result.get("success") else 1,
            "passed_ratio": result.get("passed_ratio", 0.0),
            "details": [result],
            "summary": {
                "all_success": bool(result.get("success")),
            },
        }

    parameterized_execute_results: List[Dict[str, Any]] = []
    for dataset_name in selected_dataset_names:
        single_data = await AUTOTEST_API_STEP_CRUD.execute_single_case(
            case_id=case_id,
            initial_variables=initial_variables,
            steps_execute_config=steps_execute_config,
            report_type=exec_report_type,
            batch_code=batch_code,
            dataset_name=dataset_name,
        )
        single_data["dataset_name"] = dataset_name
        parameterized_execute_results.append(single_data)

    execute_count = len(parameterized_execute_results)
    success_count = sum(1 for r in parameterized_execute_results if r.get("success"))
    failed_count = execute_count - success_count
    passed_ratio = round((success_count / execute_count * 100), 2) if execute_count > 0 else 0.0

    return {
        "parameterized": True,
        "execute_count": execute_count,
        "success_count": success_count,
        "failed_count": failed_count,
        "passed_ratio": passed_ratio,
        "details": parameterized_execute_results,
        "summary": {
            "all_success": failed_count == 0,
        },
    }


@celery.task(name="backend.celery_scheduler.tasks.task_execute_assign_case.execute_step_tree_task")
def execute_step_tree_task(
        case_id: int,
        initial_variables: Optional[List[Dict[str, Any]]] = None,
        report_type: Optional[str] = None,
        batch_code: Optional[str] = None,
        selected_dataset_names: Optional[List[str]] = None,
        steps_execute_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Celery task：后台执行单用例步骤树（默认 SCHEDULE_EXEC）。

    注意：Celery task 函数是同步入口，内部通过 run_async 进入 Worker 池执行协程。
    """
    try:
        rt = AutoTestReportType.SCHEDULE_EXEC
        if report_type and isinstance(report_type, str):
            if report_type in [e.value for e in AutoTestReportType]:
                rt = AutoTestReportType(report_type)
        elif isinstance(report_type, AutoTestReportType):
            rt = report_type

        return run_async(
            _execute_step_tree_impl(
                case_id=case_id,
                initial_variables=initial_variables,
                report_type=rt,
                batch_code=batch_code,
                selected_dataset_names=selected_dataset_names,
                steps_execute_config=steps_execute_config,
            )
        )
    except Exception as e:
        LOGGER.error(f"Celery 执行步骤树失败, case_id={case_id}, err={e}")
        raise
