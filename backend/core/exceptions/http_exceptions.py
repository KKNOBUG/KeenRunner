# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : http_exceptions.py
@DateTime: 2025/1/17 22:30
"""
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from backend.core.response.base_response import (
    ParameterResponse, ForbiddenResponse, NotFoundResponse,
    MethodNotAllowedResponse, RequestTimeoutResponse, LimiterResponse,
    InternalErrorResponse, BadGatewayResponse, GatewayTimeoutResponse,
    FailureResponse,
)


# 请求参数验证错误异常封装
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_message: str = ""
    for error in exc.errors():
        error_message += ".".join(error.get("loc")) + ":" + error.get("msg")

    return ParameterResponse


# HTTP请求异常封装
async def http_exception_handler(request: Request, exc: HTTPException):
    print("request:", type(request), request)
    print("exc:", type(exc), exc)
    print("exc.status_code:", type(exc.status_code), exc.status_code)

    if exc.status_code == status.HTTP_403_FORBIDDEN:
        return ForbiddenResponse(message=f"请求服务 {request.method} 不被接受")

    elif exc.status_code == status.HTTP_404_NOT_FOUND:
        return NotFoundResponse(message=f"请求服务 {request.url.path} 不可访达")

    elif exc.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
        return MethodNotAllowedResponse(message=f"请求服务 {request.method} 不被允许")

    elif exc.status_code == status.HTTP_408_REQUEST_TIMEOUT:
        return RequestTimeoutResponse(message=f"请求服务 {request.method} 等待超时")

    elif exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        return LimiterResponse(message=f"请求速度 {request.method} 不被允许")

    elif exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
        return InternalErrorResponse()

    elif exc.status_code == status.HTTP_502_BAD_GATEWAY:
        return BadGatewayResponse()

    elif exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
        return GatewayTimeoutResponse()

    else:
        return FailureResponse(message=str(exc))


async def app_exception_handler(request: Request, exc: Exception):
    return FailureResponse(message="服务器发生未知错误，请稍后重试，或点击右上角加入答疑群")
