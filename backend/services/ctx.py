# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : dependency.py
@DateTime: 2025/2/18 19:03
"""
import contextvars
from typing import Optional

CTX_USER_ID: contextvars.ContextVar[int] = contextvars.ContextVar("user_id", default=0)
CTX_USERNAME: contextvars.ContextVar[str] = contextvars.ContextVar("username", default="")


def get_current_username() -> Optional[str]:
    """
    获取当前请求上下文中的用户账号（大写，适配 created_user/updated_user 字段）。
    无登录上下文（如部分 Celery 任务）时返回 None。
    """
    name = (CTX_USERNAME.get("") or "").strip()
    if not name:
        return None
    # MaintainMixin.created_user / updated_user 长度为 16
    return name.upper()[:16]
