# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : http_exceptions.py
@DateTime: 2025/1/17 22:30
"""
import traceback

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from loguru import logger as LOGGER
from starlette.exceptions import HTTPException
from tortoise.exceptions import DoesNotExist

from backend.core.exceptions.base_exceptions import NoPermissionException
from backend.core.responses import (
    BaseResponse,
    ParameterResponse,
    ForbiddenResponse,
    UnauthorizedResponse,
    NotFoundResponse,
    MethodNotAllowedResponse,
    RequestTimeoutResponse,
    LimiterResponse,
    InternalErrorResponse,
    BadGatewayResponse,
    GatewayTimeoutResponse,
    FailureResponse,
)


# 当 FastAPI 在解析和验证请求数据时发现问题，会触发 RequestValidationError 异常
async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> BaseResponse:
    error_message: str = ""
    for error in exc.errors():
        error_message += ".".join(map(str, error.get("loc"))) + ":" + error.get("msg") + "; "

    return ParameterResponse(message=error_message.strip())


# 当 FastAPI 在解析和验证响应数据时发现问题，会触发 ResponseValidationError 异常
async def response_validation_exception_handler(request: Request, exc: ResponseValidationError) -> BaseResponse:
    error_message: str = ""
    for error in exc.errors():
        error_message += ".".join(map(str, error.get("loc"))) + ":" + error.get("msg") + "; "

    return ParameterResponse(message=error_message.strip())


# 当发生 HTTP 相关的异常时，如 403 禁止访问、404 未找到等，会触发 HTTPException 异常
async def http_exception_handler(request: Request, exc: HTTPException) -> BaseResponse:
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        return UnauthorizedResponse(
            http_status_code=status.HTTP_401_UNAUTHORIZED,
            message=str(exc.detail) if hasattr(exc, "detail") else str(exc),
        )

    if exc.status_code == status.HTTP_403_FORBIDDEN:
        detail = str(exc.detail) if hasattr(exc, "detail") and exc.detail else None
        # 403 拒绝事件必须进审计：响应回到中间件后只剩响应体，拒绝信号在此写入共享的 request.state
        request.state.audit_denied = True
        return ForbiddenResponse(message=detail or f"请求服务 {request.method} 未被授权")

    elif exc.status_code == status.HTTP_404_NOT_FOUND:
        return NotFoundResponse(message=f"请求资源 {request.url.path} 不可访达")

    elif exc.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
        return MethodNotAllowedResponse(message=f"请求方式 {request.method} 不被允许")

    elif exc.status_code == status.HTTP_408_REQUEST_TIMEOUT:
        return RequestTimeoutResponse(message=f"请求数据 {request.method} 等待超时")

    elif exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        return LimiterResponse(message=f"请求速度 {request.method} 不被允许")

    elif exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
        return InternalErrorResponse()

    elif exc.status_code == status.HTTP_502_BAD_GATEWAY:
        return BadGatewayResponse()

    elif exc.status_code == status.HTTP_504_GATEWAY_TIMEOUT:
        return GatewayTimeoutResponse()

    else:
        # 仅回传状态码，避免 exc.detail 携带内部细节
        return FailureResponse(message=f"请求处理失败, 状态码: {exc.status_code}", data=exc.detail)


async def no_permission_exception_handler(request: Request, exc: NoPermissionException) -> BaseResponse:
    """业务层拒绝数据越权操作时统一返回403，避免被通用异常处理成500。"""
    # 与接口权限拒绝同口径标记，由审计中间件统一落库
    request.state.audit_denied = True
    return ForbiddenResponse(message=exc.message)


# 当使用 Tortoise ORM 进行数据库查询时，如果查询结果为空，会触发 DoesNotExist 异常
async def null_point_exception_handler(request: Request, exc: DoesNotExist) -> BaseResponse:
    # ORM 原文含模型名与查询条件，只写日志；用户侧统一为可理解的业务提示
    error_message: str = "查询目标数据不存在或已被删除，请刷新后重试"
    LOGGER.error(
        f"{error_message}, "
        f"关键字段: [method={request.method}, path={request.url.path}]\n"
        f"{traceback.format_exc()}"
    )
    return NotFoundResponse(message=error_message)


# 当发生未被其他特定异常处理器处理的异常时，会触发此函数
async def app_exception_handler(request: Request, exc: Exception) -> BaseResponse:
    """未预期异常统一兜底：完整堆栈只写服务端日志，响应体不携带任何回溯内容。"""
    error_message: str = "服务器发生未知错误，请稍后重试，或点击右上角二维码加入答疑群"
    LOGGER.error(
        f"{error_message}, "
        f"关键字段: [method={request.method}, path={request.url.path}, exception_type={type(exc).__name__}]\n"
        f"{traceback.format_exc()}"
    )
    return FailureResponse(message=error_message)
