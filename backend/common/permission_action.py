# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : permission_action.py
@DateTime: 2026/10/28
"""
from typing import Dict, Optional

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

# 审计日志仅记录会改变数据或存在数据外流的动作；
AUDITED_ACTIONS: frozenset = frozenset({
    ACTION_UPDATE,
    ACTION_CREATE,
    ACTION_UPLOAD,
    ACTION_DOWNLOAD,
    ACTION_DELETE,
    ACTION_EXECUTE,
})

# ==================== 路径动词 -> 接口行为 ====================
# 单一事实源：一个动词只归属一种行为，禁止同一动词出现在多个分组。
# 新增动词必须同步 backend/README.md「接口路径与行为规范」。
VERB_ACTIONS: Dict[str, str] = {
    # 新增
    "create": ACTION_CREATE,
    "add": ACTION_CREATE,
    "copy": ACTION_CREATE,
    "duplicate": ACTION_CREATE,
    "generate": ACTION_CREATE,
    "register": ACTION_CREATE,
    # 更新
    "update": ACTION_UPDATE,
    "save": ACTION_UPDATE,
    "move": ACTION_UPDATE,
    "pin": ACTION_UPDATE,
    "bind": ACTION_UPDATE,
    "unbind": ACTION_UPDATE,
    "transfer": ACTION_UPDATE,
    "authorized": ACTION_UPDATE,
    "reset": ACTION_UPDATE,
    "assign": ACTION_UPDATE,
    "enable": ACTION_UPDATE,
    "disable": ACTION_UPDATE,
    # 删除
    "delete": ACTION_DELETE,
    "deletes": ACTION_DELETE,
    "remove": ACTION_DELETE,
    "clear": ACTION_DELETE,
    "logout": ACTION_DELETE,
    "revoke": ACTION_DELETE,
    # 上传
    "upload": ACTION_UPLOAD,
    "import": ACTION_UPLOAD,
    "parse": ACTION_UPLOAD,
    # 下载
    "download": ACTION_DOWNLOAD,
    "export": ACTION_DOWNLOAD,
    # 执行
    "run": ACTION_EXECUTE,
    "start": ACTION_EXECUTE,
    "stop": ACTION_EXECUTE,
    "debug": ACTION_EXECUTE,
    "debugging": ACTION_EXECUTE,
    "execute": ACTION_EXECUTE,
    "compare": ACTION_EXECUTE,
    "precheck": ACTION_EXECUTE,
    "test": ACTION_EXECUTE,
    "connection": ACTION_EXECUTE,
    "login": ACTION_EXECUTE,
    # 查询
    "search": ACTION_READ,
    "list": ACTION_READ,
    "get": ACTION_READ,
    "query": ACTION_READ,
    "validate": ACTION_READ,
    "build": ACTION_READ,
    "read": ACTION_READ,
    "fetch": ACTION_READ,
    # 运维
    "refresh": ACTION_OPS,
}


def last_path_verb(path: Optional[str]) -> Optional[str]:
    """忽略查询串与首尾斜杠后取末段，按 '_' 分词取位置最后的已知动词；无动词返回 None。"""
    segment: str = str(path or "").split("?", 1)[0].strip("/")
    segment = segment.rsplit("/", 1)[-1] if segment else ""
    for token in reversed(segment.split("_")):
        if token in VERB_ACTIONS:
            return token
    return None


def derive_action(method: Optional[str], path: Optional[str]) -> str:
    """
    按 HTTP 方法与路径末段动词推导接口行为，运行时唯一判定入口。

    规则：DELETE 一律删除；末段最后一个动词决定行为；GET 无动词回落查询；
    其余无动词视为无法识别，由调用方记录 ERROR 日志。

    :param method: HTTP 方法
    :param path: 路由路径
    :return: 行为类型(ACTION_* 常量之一)
    """
    method_text: str = str(method or "").upper()
    if method_text == "DELETE":
        return ACTION_DELETE
    verb: Optional[str] = last_path_verb(path)
    if verb is not None:
        return VERB_ACTIONS[verb]
    if method_text == "GET":
        return ACTION_READ
    return ACTION_UNKNOWN
