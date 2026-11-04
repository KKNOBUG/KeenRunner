# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : auth_middleware
@DateTime: 2026/3/25 15:40
"""
from __future__ import annotations

from typing import Iterable

from fastapi import Request, status
from starlette.exceptions import HTTPException

from backend.configure import LOGGER, PROJECT_CONFIG
from backend.core.responses import InternalErrorResponse, UnauthorizedResponse
from backend.services import AuthControl

# 公开入口白名单：登录、根路径、文档与静态资源；
PUBLIC_WHITELIST: tuple[str, ...] = (
    # login
    "POST /user/login",
    "POST /user/transfer_login",

    # root
    "GET /",

    # openapi/docs
    f"GET {PROJECT_CONFIG.APP_DOCS_URL}",
    f"GET {PROJECT_CONFIG.APP_REDOC_URL}",
    f"GET {PROJECT_CONFIG.APP_OPENAPI_URL}",

    # static assets
    "* /static/*",
)

# 幂等登出允许失效凭证完成本地退出；
OPTIONAL_AUTH_WHITELIST: tuple[str, ...] = (
    # logout
    "POST /user/logout",
)


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
    request_method: str = request.method.upper()
    request_path: str = _normalize_path(request.url.path)
    # 允许CORS前置请求
    if request_method == "OPTIONS":
        return await call_next(request)

    if _is_whitelisted(whitelist=PUBLIC_WHITELIST, request_method=request_method, request_path=request_path):
        return await call_next(request)

    is_optional_auth = _is_whitelisted(
        whitelist=OPTIONAL_AUTH_WHITELIST,
        request_method=request_method,
        request_path=request_path,
    )
    token = request.headers.get("token")
    if not token:
        if is_optional_auth:
            return await call_next(request)
        return UnauthorizedResponse(
            http_status_code=status.HTTP_401_UNAUTHORIZED,
            message="请求服务鉴权失败, 请携带有效 Token 进行访问",
        )

    try:
        # 此处只做认证；接口授权(RBAC)由路由依赖完成；
        await AuthControl.is_authed(request=request, token=token)
    except HTTPException as e:
        if e.status_code == 401:
            if is_optional_auth:
                return await call_next(request)
            return UnauthorizedResponse(
                http_status_code=status.HTTP_401_UNAUTHORIZED,
                message=str(e.detail),
            )
        LOGGER.error(f"请求服务鉴权异常, 请稍后重试: {e.detail}")
        return InternalErrorResponse(message="请求服务鉴权异常, 请稍后重试")
    except Exception as e:
        LOGGER.error(f"请求服务鉴权异常, 请稍后重试: {e!r}")
        return InternalErrorResponse(message="请求服务鉴权异常, 请稍后重试")
    return await call_next(request)
