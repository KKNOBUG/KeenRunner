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

from backend.core.exceptions.base_exceptions import BaseExceptions, NoPermissionException
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


async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> BaseResponse:
    """
    将请求参数校验失败汇总为参数错误响应。

    错误明细按字段路径与提示依次拼接，让前端能直接定位到出错字段。

    :param request: 当前请求，处理器签名需要但本函数未使用
    :param exc: Pydantic 请求校验异常，errors 提供字段位置与提示
    :return: 参数错误响应，message 为拼接后的校验明细
    """
    error_message: str = ""
    for error in exc.errors():
        error_message += ".".join(map(str, error.get("loc"))) + ":" + error.get("msg") + "; "

    return ParameterResponse(message=error_message.strip())


async def response_validation_exception_handler(request: Request, exc: ResponseValidationError) -> BaseResponse:
    """
    将响应模型校验失败汇总为参数错误响应。

    与请求校验使用同一拼接规则，便于区分是入参还是出参与响应模型不符。

    :param request: 当前请求，处理器签名需要但本函数未使用
    :param exc: Pydantic 响应校验异常，errors 提供字段位置与提示
    :return: 参数错误响应，message 为拼接后的校验明细
    """
    error_message: str = ""
    for error in exc.errors():
        error_message += ".".join(map(str, error.get("loc"))) + ":" + error.get("msg") + "; "

    return ParameterResponse(message=error_message.strip())


async def http_exception_handler(request: Request, exc: HTTPException) -> BaseResponse:
    """
    将 Starlette HTTPException 映射为项目统一响应。

    401 与 403 保留原始 detail；404、405、408、429 按请求方法或路径生成可读提示；
    500、502、504 使用固定文案；其余状态码的 message 只暴露状态码。
    403 分支会写入 request.state.audit_denied，供审计中间件统一落库。

    :param request: 当前请求，提供方法、路径与审计标记的存放位置
    :param exc: Starlette HTTP 异常，携带状态码与 detail
    :return: 与状态码对应的统一响应
    """
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
        # 未知状态码：message 只暴露状态码，detail 仍通过 data 透传，保持既有响应契约
        return FailureResponse(message=f"请求处理失败, 状态码: {exc.status_code}", data=exc.detail)


async def no_permission_exception_handler(request: Request, exc: NoPermissionException) -> BaseResponse:
    """
    将业务层数据越权拒绝统一转为 403 响应。

    与接口权限拒绝同口径标记 request.state.audit_denied，由审计中间件统一落库；
    单独处理可避免该异常被通用兜底处理器转成 500。

    :param request: 当前请求，用于写入审计拒绝标记
    :param exc: 业务层越权异常，message 为可直接展示的中文提示
    :return: 403 响应
    """
    request.state.audit_denied = True
    return ForbiddenResponse(message=exc.message)


async def base_exceptions_handler(request: Request, exc: BaseExceptions) -> BaseResponse:
    """
    将项目自定义业务异常映射为统一失败响应。

    业务异常属于可预期失败，只记录告警与错误码，不输出堆栈；
    响应沿用失败响应的状态码与错误码，提示文案取自异常携带的业务提示。

    :param request: 当前请求，用于日志记录请求方法与路径
    :param exc: 项目自定义异常，携带业务错误码与可读提示
    :return: 失败响应，message 为异常携带的业务提示
    """
    LOGGER.warning(
        f"{exc.message}, "
        f"关键字段: [method={request.method}, path={request.url.path}, "
        f"code={exc.code}, exception_type={type(exc).__name__}]"
    )
    return FailureResponse(message=exc.message)


async def null_point_exception_handler(request: Request, exc: DoesNotExist) -> BaseResponse:
    """
    将 Tortoise 查询结果为空转为 404 响应。

    查询结果为空属于可预期情况，只记录告警，不输出堆栈；
    ORM 原文包含模型名与查询条件，不返回给用户。

    :param request: 当前请求，用于日志记录请求方法与路径
    :param exc: ORM 的 DoesNotExist 异常
    :return: 404 响应
    """
    error_message: str = "查询目标数据不存在或已被删除，请刷新后重试"
    LOGGER.warning(
        f"{error_message}, "
        f"关键字段: [method={request.method}, path={request.url.path}, "
        f"exception_type={type(exc).__name__}]"
    )
    return NotFoundResponse(message=error_message)


async def app_exception_handler(request: Request, exc: Exception) -> BaseResponse:
    """
    未预期异常的最终兜底处理。

    完整堆栈只写服务端日志，响应体不携带任何回溯内容与异常原文。

    :param request: 当前请求，用于日志记录请求方法与路径
    :param exc: 未被其他处理器匹配的异常
    :return: 失败响应，提示用户稍后重试
    """
    error_message: str = "服务器发生未知错误，请稍后重试，或点击右上角二维码加入答疑群"
    LOGGER.error(
        f"{error_message}, "
        f"关键字段: [method={request.method}, path={request.url.path}, exception_type={type(exc).__name__}]\n"
        f"{traceback.format_exc()}"
    )
    return FailureResponse(message=error_message)
