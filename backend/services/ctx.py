# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : dependency.py
@DateTime: 2025/2/18 19:03
"""
import contextvars
from typing import Optional

CTX_USER_ID: contextvars.ContextVar[int] = contextvars.ContextVar("user_id", default=0)
CTX_USERNAME: contextvars.ContextVar[str] = contextvars.ContextVar("username", default="")


def normalize_username(username: Optional[str]) -> str:
    """归属账号统一口径：去空白、转大写并截断到16位。"""
    return str(username or "").strip().upper()[:16]


def get_current_username() -> Optional[str]:
    """获取当前请求上下文中的用户账号。"""
    name = normalize_username(CTX_USERNAME.get(""))
    if not name:
        return None
    return name
