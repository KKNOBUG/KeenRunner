# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : task_export_case_script.py
@DateTime: 2026/8/1

公共接口脚本异步导出任务：导出数量超过阈值时由视图层下发，复制模板副本写入数据行并落盘，
并将文件名/路径写入任务返回值（经 Worker on_success 落入 task_summary，供执行记录展示）。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from backend.applications.aotutest.dependencies import get_autotest_api_services
from backend.applications.aotutest.services.autotest_case_excel_service import (
    prepare_script_export_rows,
    build_script_workbook,
    build_script_file_name,
)
from backend.celery_scheduler.celery_base import run_async
from backend.celery_scheduler.celery_worker import celery
from backend.configure import LOGGER, PROJECT_CONFIG


async def _export_case_scripts_impl(case_ids: List[int], created_user: Optional[str]) -> Dict[str, Any]:
    """
    异步导出实现：加载校验合规用例 → 复制模板副本写入数据行 → 落盘到下载目录。

    :param case_ids: 用例主键列表
    :param created_user: 提交用户账号（仅作元信息随结果落入执行记录）
    :return: 含 file_name/file_path/case_count 等的结果字典
    :raises ValueError: 无合规用例可导出时
    """
    services = await get_autotest_api_services()
    rows, invalid = await prepare_script_export_rows(case_ids=case_ids, services=services)
    # 视图层下发前已全量校验；此处防御任务排队期间用例被改类型/步骤
    if invalid:
        LOGGER.warning(f"【Celery-Worker】异步导出脚本跳过不合规用例: {invalid}")
    if not rows:
        raise ValueError("无可导出的合规用例")

    workbook = build_script_workbook(rows)
    file_name = build_script_file_name(created_user)
    download_dir = os.path.join(PROJECT_CONFIG.OUTPUT_DOWNLOAD_DIR, "autotest_export")
    os.makedirs(download_dir, exist_ok=True)
    file_path = os.path.join(download_dir, file_name)
    workbook.save(file_path)
    return {
        "file_name": file_name,
        "file_path": file_path,
        "case_count": len(rows),
        "skipped_invalid_count": len(invalid),
        "created_user": created_user,
    }


@celery.task(name="backend.celery_scheduler.tasks.task_export_case_script.export_case_scripts_task")
def export_case_scripts_task(
        case_ids: List[int],
        created_user: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Celery 同步入口：后台导出公共接口脚本为模板 xlsx。

    :param case_ids: 用例主键列表
    :param created_user: 提交用户账号
    :return: 导出结果字典（落入 task_summary）
    :raises Exception: 导出失败时向上抛出，供 Celery on_failure 处理
    """
    try:
        LOGGER.info(f"【Celery-Worker】开始导出公共接口脚本任务: 数量={len(case_ids or [])}, created_user={created_user}")
        result = run_async(_export_case_scripts_impl(case_ids=case_ids or [], created_user=created_user))
        LOGGER.info(
            f"【Celery-Worker】导出公共接口脚本任务完成: file_name={result.get('file_name')}, "
            f"case_count={result.get('case_count')}, skipped_invalid_count={result.get('skipped_invalid_count')}"
        )
        return result
    except Exception as e:
        LOGGER.error(
            f"【Celery-Worker】导出公共接口脚本失败: 数量={len(case_ids or [])}, "
            f"错误类型={type(e).__name__}, 错误描述={e}"
        )
        raise
