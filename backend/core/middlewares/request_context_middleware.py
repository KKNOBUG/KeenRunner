# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : request_context_middleware.py
@DateTime: 2026/5/29
"""
from fastapi import Request

from backend.common.request_context import (
    apply_response_trace_headers,
    clear_trace_context,
    enter_server_span,
)


async def request_context_middleware(request: Request, call_next):
    """
    最外层中间件：解析 X-Trace-ID（可选），为本次入站 HTTP 分配 SpanID，响应头回传 X-Span-ID。
    """
    snapshot, tokens = enter_server_span(request)
    try:
        response = await call_next(request)
        apply_response_trace_headers(response.headers, snapshot)
        return response
    finally:
        clear_trace_context(tokens)
