# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : task_execute_assign_case.py
@DateTime: 2026/3/20
"""
from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional

from backend.applications.aotutest.schemas.autotest_step_schema import StepVariablesBase
from backend.applications.aotutest.services.autotest_step_crud import AutoTestStepCrud
from backend.celery_scheduler.celery_base import run_async
from backend.celery_scheduler.celery_worker import celery
from backend.configure import LOGGER
from backend.enums import AutoTestReportType
from backend.services.ctx import CTX_USERNAME


def _normalize_initial_variables(raw: Optional[List[Dict[str, Any]]]) -> List[StepVariablesBase]:
    """
    将初始变量规范为StepVariablesBase列表。

    :param raw: 原始变量列表(dict或已是schema)
    :return: StepVariablesBase列表；空入参返回[]
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
    生成一次执行的批次号(时间戳-UUID)。

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
    后台执行单用例步骤树，支持多数据源参数化。

    :param case_id: 用例主键ID
    :param initial_variables: 初始会话变量列表
    :param report_type: 报告类型枚举
    :param batch_code: 批次号；为空时自动生成
    :param selected_dataset_names: 选中的数据源名称列表；空则单次执行
    :param steps_execute_config: 步骤执行环境配置覆盖
    :param created_user: 提交任务的用户账号
    :return: 批次字段total_cases/success_cases/failed_cases/success_rate(%)；details[]为各轮execute_single_case(含步骤级*_steps/passed_ratio)
    """
    # Worker 进程无 HTTP 鉴权上下文，用提交任务时传入的用户账号埋点
    if created_user:
        CTX_USERNAME.set(str(created_user).strip())
    if selected_dataset_names is None:
        selected_dataset_names = []
    initial_variables = _normalize_initial_variables(initial_variables)
    if not batch_code:
        batch_code = _new_batch_code()

    step_crud = AutoTestStepCrud()
    if not selected_dataset_names:
        result = await step_crud.execute_single_case(
            case_id=case_id,
            initial_variables=initial_variables,
            steps_execute_config=steps_execute_config,
            report_type=report_type,
            batch_code=batch_code,
            dataset_name=None,
        )
        result["dataset_name"] = None
        case_ok = bool(result.get("success"))
        return {
            "parameterized": False,
            "batch_code": batch_code,
            "total_cases": 1,
            "success_cases": 1 if case_ok else 0,
            "failed_cases": 0 if case_ok else 1,
            "success_rate": 100.0 if case_ok else 0.0,
            "execute_runs": 1,
            "details": [result],
        }

    details: List[Dict[str, Any]] = []
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
        details.append(single_data)

    execute_runs = len(details)
    success_runs = sum(1 for r in details if r.get("success"))
    case_ok = execute_runs > 0 and success_runs == execute_runs
    return {
        "parameterized": True,
        "batch_code": batch_code,
        "total_cases": 1,
        "success_cases": 1 if case_ok else 0,
        "failed_cases": 0 if case_ok else 1,
        "success_rate": 100.0 if case_ok else 0.0,
        "execute_runs": execute_runs,
        "details": details,
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
    Celery同步入口，后台执行单用例步骤树(默认SCHEDULE_EXEC)。

    :param case_id: 用例主键ID
    :param initial_variables: 初始会话变量列表
    :param report_type: 报告类型字符串或枚举；非法时回退SCHEDULE_EXEC
    :param batch_code: 批次号
    :param selected_dataset_names: 数据源名称列表
    :param steps_execute_config: 步骤执行环境配置
    :param created_user: 提交用户账号
    :return: 执行结果字典
    :raises Exception: 执行失败时向上抛出，供Celery on_failure处理
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
            f"total_cases={result.get('total_cases') if isinstance(result, dict) else None}, "
            f"success_cases={result.get('success_cases') if isinstance(result, dict) else None}, "
            f"failed_cases={result.get('failed_cases') if isinstance(result, dict) else None}, "
            f"success_rate={result.get('success_rate') if isinstance(result, dict) else None}, "
            f"execute_runs={result.get('execute_runs') if isinstance(result, dict) else None}"
        )
        return result
    except Exception as e:
        LOGGER.error(
            f"【Celery-Worker】执行步骤树失败: case_id={case_id}, batch_code={batch_code}, "
            f"错误类型={type(e).__name__}, 错误描述={e}"
        )
        raise
