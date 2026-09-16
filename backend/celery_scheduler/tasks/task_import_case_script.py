# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : task_import_case_script.py
@DateTime: 2026/9/16
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.applications.autotest.dependencies import AutoTestServices, get_autotest_api_services
from backend.applications.autotest.services.autotest_case_excel_service import import_script_rows
from backend.celery_scheduler.celery_base import run_async
from backend.celery_scheduler.celery_worker import celery
from backend.configure import LOGGER
from backend.services.ctx import CTX_USERNAME


async def _import_case_scripts_impl(rows: List[Dict[str, Any]], file_name: Optional[str], created_user: Optional[str]) -> Dict[str, Any]:
    """
    异步导入实现，行级匹配校验通过后单事务落库(存在更新或恢复覆盖、不存在新增)。

    rows为视图层模板解析与行格式校验通过的快照；行级匹配不合规时整批取消落库(与同步导入一致的全有或全无语义)，
    明细随结果落入执行记录供异步中心追溯。

    :param rows: 模板解析行列表
    :param file_name: 导入模板文件名(仅作元信息随结果落入执行记录)
    :param created_user: 提交用户账号
    :return: 含total_cases/success_cases/created_count/updated_count/invalid的结果字典
    """
    # Worker 进程无 HTTP 鉴权上下文，用提交任务时传入的用户账号埋点(行级匹配与落库按所属人owner_user定位)
    if created_user:
        CTX_USERNAME.set(str(created_user).strip())
    services: AutoTestServices = await get_autotest_api_services()

    result, invalid = await import_script_rows(rows=rows, services=services)
    if invalid:
        return {
            "total_cases": len(rows),
            "success_cases": 0,
            "failed_cases": len(rows),
            "file_name": file_name,
            "invalid": invalid,
        }
    created_count: int = result.get("created_count", 0)
    updated_count: int = result.get("updated_count", 0)
    return {
        "total_cases": len(rows),
        "success_cases": created_count + updated_count,
        "failed_cases": 0,
        "created_count": created_count,
        "updated_count": updated_count,
        "file_name": file_name,
    }


@celery.task(name="backend.celery_scheduler.tasks.task_import_case_script.import_case_scripts_task")
def import_case_scripts_task(
        rows: List[Dict[str, Any]],
        file_name: Optional[str] = None,
        created_user: Optional[str] = None,
        report_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Celery同步入口，后台按模板解析行导入公共接口脚本。

    :param rows: 视图层模板解析并校验通过的行列表
    :param file_name: 导入模板文件名
    :param created_user: 提交用户账号
    :param report_type: 报告类型快照(供Worker写执行记录；任务体本身不消费)
    :return: 导入结果字典(落入task_summary)
    :raises Exception: 任务级失败时向上抛出，供Celery on_failure处理
    """
    try:
        LOGGER.info(
            f"【Celery-Worker】开始导入公共接口脚本任务: 行数={len(rows or [])}, "
            f"file_name={file_name}, created_user={created_user}, report_type={report_type}"
        )
        result = run_async(_import_case_scripts_impl(
            rows=rows or [],
            file_name=file_name,
            created_user=created_user,
        ))
        LOGGER.info(
            f"【Celery-Worker】导入公共接口脚本任务完成: total_cases={result.get('total_cases')}, "
            f"success_cases={result.get('success_cases')}, failed_cases={result.get('failed_cases')}"
        )
        return result
    except Exception as e:
        LOGGER.error(
            f"【Celery-Worker】导入公共接口脚本任务失败: 行数={len(rows or [])}, "
            f"错误类型={type(e).__name__}, 错误描述={e}"
        )
        raise
