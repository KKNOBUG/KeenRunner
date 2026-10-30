# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : permission_action.py
@DateTime: 2026/10/28
"""
from typing import Optional, Tuple

# ==================== 常量：接口行为类型 ====================
ACTION_OPS: str = "ops"
ACTION_READ: str = "read"
ACTION_CREATE: str = "create"
ACTION_UPDATE: str = "update"
ACTION_DELETE: str = "delete"
ACTION_UPLOAD: str = "upload"
ACTION_EXECUTE: str = "execute"
ACTION_UNKNOWN: str = "unknown"
ACTION_DOWNLOAD: str = "download"

# 判定优先级：靠前优先匹配
ACTION_RULES: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("刷新",), ACTION_OPS),
    (("查询",), ACTION_READ),
    (("更新",), ACTION_UPDATE),
    (("新增",), ACTION_CREATE),
    (("导入", "上传"), ACTION_UPLOAD),
    (("导出", "下载"), ACTION_DOWNLOAD),
    (("注销", "删除", "批量删除",), ACTION_DELETE),
    (("执行", "调试", "启动", "停止"), ACTION_EXECUTE),
)

ALL_SUMMARY_PREFIXES: Tuple[str, ...] = tuple(
    prefix for prefixes, _ in ACTION_RULES for prefix in prefixes
)

# 审计只记录会改变数据或触发执行的行为，查询/下载/未知不落库，避免日志膨胀
AUDITED_ACTIONS: frozenset = frozenset({
    ACTION_CREATE,
    ACTION_UPDATE,
    ACTION_DELETE,
    ACTION_EXECUTE,
    ACTION_UPLOAD,
    ACTION_OPS,
})


def classify_summary_action(summary: Optional[str], method: Optional[str]) -> str:
    """
    按 summary 前缀识别接口行为；DELETE 方法视为删除，GET 无法匹配时回落为查询。

    :param summary: 接口摘要
    :param method: HTTP 方法
    :return: 行为类型(ACTION_* 常量之一)
    """
    text: str = (summary or "").strip()
    method_text: str = str(method or "").upper()

    if method_text == "DELETE":
        return ACTION_DELETE
    for prefixes, action in ACTION_RULES:
        if any(text.startswith(prefix) for prefix in prefixes):
            return action
    if method_text == "GET":
        return ACTION_READ
    return ACTION_UNKNOWN