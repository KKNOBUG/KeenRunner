# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : task_autotest_step_tree.py
@DateTime: 2026/3/20

在 Celery Worker 后台执行“单用例步骤树运行(可参数化数据集)”：
- 调用 AUTOTEST_API_STEP_CRUD.execute_single_case 写入报告/明细
- 参数化：按 selected_dataset_names 逐个 dataset_name 执行
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.applications.aotutest.services.autotest_step_crud import AUTOTEST_API_STEP_CRUD
from backend.celery_scheduler.celery_base import run_async
from backend.celery_scheduler.celery_worker import celery
from backend.configure import LOGGER
from backend.enums import AutoTestReportType


async def _execute_step_tree_impl(
        case_id: int,
        env_name: Optional[str] = None,
        initial_variables: Optional[List[Dict[str, Any]]] = None,
        report_type: Optional[AutoTestReportType] = None,
        batch_code: Optional[str] = None,
        selected_dataset_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if initial_variables is None or not isinstance(initial_variables, list):
        initial_variables = []
    if selected_dataset_names is None:
        selected_dataset_names = []

    exec_report_type = report_type or AutoTestReportType.ASYNC_EXEC

    # 非参数化：仅执行一次
    if not selected_dataset_names:
        result = await AUTOTEST_API_STEP_CRUD.execute_single_case(
            case_id=case_id,
            env_name=env_name,
            initial_variables=initial_variables,
            report_type=exec_report_type,
            batch_code=batch_code,
            dataset_name=None,
        )
        # execute_single_case 返回值不含 dataset_name，这里补充便于前端/调试
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

    # 参数化：按 dataset_name 逐个执行（与原同步逻辑保持一致：串行执行，便于事务与 DB 压力控制）
    parameterized_execute_results: List[Dict[str, Any]] = []
    for dataset_name in selected_dataset_names:
        single_data = await AUTOTEST_API_STEP_CRUD.execute_single_case(
            case_id=case_id,
            env_name=env_name,
            initial_variables=initial_variables,
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


@celery.task(name="backend.celery_scheduler.tasks.task_autotest_step_tree.execute_step_tree_task")
def execute_step_tree_task(
        case_id: int,
        env_name: Optional[str] = None,
        initial_variables: Optional[List[Dict[str, Any]]] = None,
        report_type: Optional[str] = None,
        batch_code: Optional[str] = None,
        selected_dataset_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Celery task：参数化执行单用例步骤树。

    注意：Celery task 函数是同步入口，内部通过 run_async 进入 Worker 池执行协程。
    """
    try:
        rt = AutoTestReportType.ASYNC_EXEC
        if report_type and isinstance(report_type, str):
            # report_type 可能从 JSON 透传为字符串，这里做兼容映射
            if report_type in [e.value for e in AutoTestReportType]:
                rt = AutoTestReportType(report_type)
        elif isinstance(report_type, AutoTestReportType):
            rt = report_type

        return run_async(
            _execute_step_tree_impl(
                case_id=case_id,
                env_name=env_name,
                initial_variables=initial_variables,
                report_type=rt,
                batch_code=batch_code,
                selected_dataset_names=selected_dataset_names,
            )
        )
    except Exception as e:
        LOGGER.error(f"Celery 执行步骤树失败, case_id={case_id}, err={e}")
        raise
