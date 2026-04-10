# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : auth_middleware
@DateTime: 2026/3/25 15:40
"""
from __future__ import annotations

from typing import Iterable

from fastapi import Request

from backend.configure import PROJECT_CONFIG
from backend.core.responses import UnauthorizedResponse
from backend.services import AuthControl


def _normalize_path(path: str) -> str:
    """对结尾‘/’符号进行统一化，使白名单/路径匹配稳定。"""
    if path != "/" and path.endswith("/"):
        return path.rstrip("/")
    return path


def _rule_matches(rule: str, request_method: str, request_path: str) -> bool:
    """
    rule format:
      - "METHOD /path" (exact)
      - "METHOD /path/*" (prefix)
      - METHOD can be "*" to match any
    """
    rule = rule.strip()
    if not rule:
        return False

    parts = rule.split(" ", 1)
    if len(parts) != 2:
        return False

    rule_method, rule_path_pattern = parts
    rule_method = rule_method.upper()

    if rule_method != "*" and rule_method != request_method:
        return False

    rule_path_pattern = _normalize_path(rule_path_pattern)

    # prefix match: /static/* => /static/<anything>
    if rule_path_pattern.endswith("/*"):
        base = rule_path_pattern[: -len("/*")]
        base = _normalize_path(base)
        return request_path == base or request_path.startswith(base + "/")

    # exact match
    return request_path == rule_path_pattern


def _is_whitelisted(whitelist: Iterable[str], request_method: str, request_path: str) -> bool:
    for rule in whitelist:
        if _rule_matches(rule, request_method=request_method, request_path=request_path):
            return True
    return False


async def auth_middleware(request: Request, call_next):
    request_method = request.method.upper()
    request_path = _normalize_path(request.url.path)

    # 允许CORS前置请求
    if request_method == "OPTIONS":
        return await call_next(request)

    whitelist = [
        # login
        "POST /base/auth/access_token",

        # root
        "GET /",

        # openapi/docs
        f"GET {PROJECT_CONFIG.APP_DOCS_URL}",
        f"GET {PROJECT_CONFIG.APP_REDOC_URL}",
        f"GET {PROJECT_CONFIG.APP_OPENAPI_URL}",

        # static assets
        "* /static/*",
    ]

    if _is_whitelisted(whitelist=whitelist, request_method=request_method, request_path=request_path):
        return await call_next(request)

    token = request.headers.get("token")
    if not token:
        return UnauthorizedResponse(message="请求服务鉴权失败, 请携带有效 Token 进行访问")

    # 对( RBAC发生在依赖权限中)进行认证
    try:
        await AuthControl.is_authed(token)
    except Exception as e:
        # 统一以未认证返回，避免调试模式下泄露异常细节
        return UnauthorizedResponse(message="请求服务鉴权已过期, 请重新登录获取有效 Token 后进行访问")
    return await call_next(request)
