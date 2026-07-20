# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : task_execute_assign_case.py
@DateTime: 2026/3/20

指定用例步骤树异步执行任务（支持多数据源参数化与批次号归并）。
"""
from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional

from backend.applications.aotutest.schemas.autotest_step_schema import StepVariablesBase
from backend.applications.aotutest.services.autotest_step_crud import AutoTestApiStepCrud
from backend.celery_scheduler.celery_base import run_async
from backend.celery_scheduler.celery_worker import celery
from backend.configure import LOGGER
from backend.enums import AutoTestReportType
from backend.services.ctx import CTX_USERNAME


def _normalize_initial_variables(
        raw: Optional[List[Dict[str, Any]]],
) -> List[StepVariablesBase]:
    """
    将初始变量规范为 ``StepVariablesBase`` 列表。

    :param raw: 原始变量列表（dict 或已是 schema）
    :return: StepVariablesBase 列表；空入参返回 []
    """
    if not raw:
        return []
    out: List[StepVariablesBase] = []
    for item in raw:
        if isinstance(item, StepVariablesBase):
            out.append(item)
        elif isinstance(item, dict):
            out.append(StepVariablesBase.model_validate(item))
    return out


def _new_batch_code() -> str:
    """
    生成一次执行的批次号（时间戳-UUID）。

    :return: 批次号字符串
    """
    return f"{int(datetime.datetime.now().timestamp())}-{uuid.uuid4().hex.upper()}"


async def _execute_step_tree_impl(
        case_id: int,
        initial_variables: Optional[List[Dict[str, Any]]] = None,
        report_type: Optional[AutoTestReportType] = None,
        batch_code: Optional[str] = None,
        selected_dataset_names: Optional[List[str]] = None,
        steps_execute_config: Optional[Dict[str, Any]] = None,
        created_user: Optional[str] = None,
) -> Dict[str, Any]:
    """
    后台执行单用例步骤树（支持多数据源参数化）。

    Worker 无 HTTP 鉴权上下文时，用 ``created_user`` 写入 CTX_USERNAME 埋点。

    :param case_id: 用例主键 ID
    :param initial_variables: 初始会话变量列表
    :param report_type: 报告类型枚举
    :param batch_code: 批次号；为空时自动生成
    :param selected_dataset_names: 选中的数据源名称列表；空则单次执行
    :param steps_execute_config: 步骤执行环境配置覆盖
    :param created_user: 提交任务的用户账号
    :return: 含 parameterized、batch_code、执行统计与 details 的结果字典
    """
    # Worker 进程无 HTTP 鉴权上下文，用提交任务时传入的用户账号埋点
    if created_user:
        CTX_USERNAME.set(str(created_user).strip())
    if selected_dataset_names is None:
        selected_dataset_names = []
    initial_variables = _normalize_initial_variables(initial_variables)
    # 兜底：调用方未传时仍生成，保证多数据源报告可归为同一次执行
    if not batch_code:
        batch_code = _new_batch_code()

    step_crud = AutoTestApiStepCrud()
    if not selected_dataset_names:
        result = await step_crud.execute_single_case(
            case_id=case_id,
            initial_variables=initial_variables,
            steps_execute_config=steps_execute_config,
            report_type=report_type,
            batch_code=batch_code,
            dataset_name=None,
        )
        result["parameterized"] = False
        result["dataset_name"] = None
        return {
            "parameterized": False,
            "batch_code": batch_code,
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
        single_data = await step_crud.execute_single_case(
            case_id=case_id,
            initial_variables=initial_variables,
            steps_execute_config=steps_execute_config,
            report_type=report_type,
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
        "batch_code": batch_code,
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
        created_user: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Celery 同步入口：后台执行单用例步骤树（默认 SCHEDULE_EXEC）。

    内部通过 ``run_async`` 进入 Worker 池执行协程。

    :param case_id: 用例主键 ID
    :param initial_variables: 初始会话变量列表
    :param report_type: 报告类型字符串或枚举；非法时回退 SCHEDULE_EXEC
    :param batch_code: 批次号
    :param selected_dataset_names: 数据源名称列表
    :param steps_execute_config: 步骤执行环境配置
    :param created_user: 提交用户账号
    :return: 执行结果字典
    :raises Exception: 执行失败时向上抛出，供 Celery on_failure 处理
    """
    try:
        rt = AutoTestReportType.SCHEDULE_EXEC
        if report_type and isinstance(report_type, str):
            if report_type in [e.value for e in AutoTestReportType]:
                rt = AutoTestReportType(report_type)
        elif isinstance(report_type, AutoTestReportType):
            rt = report_type

        LOGGER.info(
            f"【Celery-Worker】开始执行步骤树任务: case_id={case_id}, report_type={getattr(rt, 'value', rt)}, "
            f"batch_code={batch_code}, dataset_count={len(selected_dataset_names or [])}, "
            f"has_steps_execute_config={bool(steps_execute_config)}, created_user={created_user}"
        )
        result = run_async(
            _execute_step_tree_impl(
                case_id=case_id,
                initial_variables=initial_variables,
                report_type=rt,
                batch_code=batch_code,
                selected_dataset_names=selected_dataset_names,
                steps_execute_config=steps_execute_config,
                created_user=created_user,
            )
        )
        LOGGER.info(
            f"【Celery-Worker】步骤树任务完成: case_id={case_id}, "
            f"batch_code={result.get('batch_code') if isinstance(result, dict) else batch_code}, "
            f"execute_count={result.get('execute_count') if isinstance(result, dict) else None}, "
            f"success_count={result.get('success_count') if isinstance(result, dict) else None}, "
            f"failed_count={result.get('failed_count') if isinstance(result, dict) else None}"
        )
        return result
    except Exception as e:
        LOGGER.error(
            f"【Celery-Worker】执行步骤树失败: case_id={case_id}, batch_code={batch_code}, "
            f"错误类型={type(e).__name__}, 错误描述={e}"
        )
        raise
