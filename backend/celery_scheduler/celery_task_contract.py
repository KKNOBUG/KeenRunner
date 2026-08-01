# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import mimetypes
import os
from typing import Any, Dict, List, Optional

from backend.configure import PROJECT_CONFIG
from backend.enums import AutoTestTaskType

# Celery 注册名 → 任务类型 / 默认展示名
CELERY_TASK_META: Dict[str, Dict[str, Any]] = {
    "backend.celery_scheduler.tasks.task_autotest_case.run_autotest_task": {
        "task_type": AutoTestTaskType.AUTOTEST_API,
        "task_name": "用例编排",
    },
    "backend.celery_scheduler.tasks.task_autotest_case.scan_and_dispatch_autotest_tasks": {
        "task_type": AutoTestTaskType.SCHEDULE_SCAN,
        "task_name": "调度扫描",
    },
    "backend.celery_scheduler.tasks.task_execute_assign_case.execute_step_tree_task": {
        "task_type": AutoTestTaskType.CASE_STEP_EXEC,
        "task_name": "用例执行",
    },
    "backend.celery_scheduler.tasks.task_export_case_datagram.export_testcases_task": {
        "task_type": AutoTestTaskType.EXPORT_CASE_DATA,
        "task_name": "导出用例数据",
    },
    "backend.celery_scheduler.tasks.task_export_case_script.export_case_scripts_task": {
        "task_type": AutoTestTaskType.EXPORT_CASE_SCRIPT,
        "task_name": "导出公共接口",
    },
}


def resolve_task_meta(celery_task_name: Optional[str]) -> Dict[str, Any]:
    """按Celery任务名解析task_type/默认task_name。"""
    if not celery_task_name:
        return {}
    return dict(CELERY_TASK_META.get(celery_task_name) or {})


def path_to_storage_key(file_path: str) -> str:
    """绝对路径 → 相对 OUTPUT_DOWNLOAD_DIR 的 storage_key。"""
    if not file_path:
        return ""
    abs_path = os.path.abspath(file_path)
    root = os.path.abspath(PROJECT_CONFIG.OUTPUT_DOWNLOAD_DIR)
    if abs_path == root or abs_path.startswith(root + os.sep):
        return os.path.relpath(abs_path, root).replace("\\", "/")
    return f"autotest_export/{os.path.basename(abs_path)}"


def resolve_storage_path(storage_key: str) -> str:
    """storage_key → 绝对路径（限制在下载根目录内）。"""
    key = (storage_key or "").strip().lstrip("/").replace("\\", "/")
    if not key or ".." in key.split("/"):
        raise ValueError("非法 storage_key")
    root = os.path.abspath(PROJECT_CONFIG.OUTPUT_DOWNLOAD_DIR)
    full = os.path.abspath(os.path.join(root, key))
    if full != root and not full.startswith(root + os.sep):
        raise ValueError("storage_key 越界")
    return full


def _to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list, str, int, float, bool)):
        try:
            return json.loads(json.dumps(value, ensure_ascii=False, default=str))
        except Exception:
            return {"value": str(value)}
    return {"value": str(value)}


def _is_envelope(value: Any) -> bool:
    return (
            isinstance(value, dict)
            and "attachments" in value
            and "raw" in value
            and "success" in value
    )


def _build_attachment(
        *,
        name: str,
        storage_key: str,
        key: str = "main",
        content_type: Optional[str] = None,
        size: Optional[int] = None,
        expires_at: Optional[str] = None,
        file_path: Optional[str] = None,
) -> Dict[str, Any]:
    if size is None and file_path and os.path.isfile(file_path):
        size = os.path.getsize(file_path)
    if not content_type:
        guessed, _ = mimetypes.guess_type(name or storage_key)
        content_type = guessed or "application/octet-stream"
    return {
        "key": key or "main",
        "name": name or os.path.basename(storage_key) or "download.bin",
        "storage_key": storage_key,
        "content_type": content_type,
        "size": size,
        "expires_at": expires_at,
    }


def _attachments_from_raw(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return []
    existing = raw.get("attachments")
    if isinstance(existing, list) and existing:
        out: List[Dict[str, Any]] = []
        for idx, item in enumerate(existing):
            if not isinstance(item, dict):
                continue
            storage_key = item.get("storage_key") or path_to_storage_key(str(item.get("file_path") or ""))
            if not storage_key:
                continue
            out.append(
                _build_attachment(
                    key=str(item.get("key") or (f"a{idx}" if idx else "main")),
                    name=str(item.get("name") or os.path.basename(storage_key)),
                    storage_key=storage_key,
                    content_type=item.get("content_type"),
                    size=item.get("size"),
                    expires_at=item.get("expires_at"),
                    file_path=item.get("file_path"),
                )
            )
        if out:
            return out
    file_path = raw.get("file_path")
    file_name = raw.get("file_name")
    if not file_path and not file_name:
        return []
    path = str(file_path or "")
    name = str(file_name or (os.path.basename(path) if path else "download.bin"))
    storage_key = path_to_storage_key(path) if path else f"autotest_export/{name}"
    return [_build_attachment(name=name, storage_key=storage_key, file_path=path or None)]


def normalize_task_summary(retval: Any, *, pipeline_ok: bool = True) -> Dict[str, Any]:
    """将任务返回值规范为信封；原文进入raw。"""
    data = _to_jsonable(retval)
    if _is_envelope(data):
        attachments = data.get("attachments")
        if not isinstance(attachments, list):
            attachments = _attachments_from_raw(data.get("raw"))
        success = bool(pipeline_ok) if data.get("success") is None else bool(data.get("success"))
        return {
            "success": success,
            "error": data.get("error"),
            "message": data.get("message"),
            "batch_code": data.get("batch_code"),
            "attachments": attachments,
            "raw": data.get("raw") if data.get("raw") is not None else {},
        }

    raw = data if data is not None else {}
    if not isinstance(raw, (dict, list)):
        raw = {"value": raw}
    raw_dict = raw if isinstance(raw, dict) else {}

    error = raw_dict.get("error")
    error = str(error) if error is not None else None
    message = raw_dict.get("message")
    if message is not None:
        message = str(message)
    elif not pipeline_ok:
        message = error or "执行失败"

    batch_code = raw_dict.get("batch_code")
    return {
        "success": bool(pipeline_ok),
        "error": error,
        "message": message,
        "batch_code": str(batch_code) if batch_code is not None else None,
        "attachments": _attachments_from_raw(raw),
        "raw": raw,
    }


def list_attachments_from_summary(task_summary: Any) -> List[Dict[str, Any]]:
    """从已落库task_summary取attachments。"""
    if not isinstance(task_summary, dict):
        return []
    items = task_summary.get("attachments")
    if isinstance(items, list) and items:
        return [a for a in items if isinstance(a, dict)]
    source = task_summary.get("raw") if "raw" in task_summary else task_summary
    return _attachments_from_raw(source)
