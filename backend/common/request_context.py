# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : request_context.py
@DateTime: 2026/5/29
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Dict, Mapping, MutableMapping, Optional, Tuple, Union

from starlette.requests import Request

HEADER_TRACE_ID = "X-Trace-ID"
HEADER_SPAN_ID = "X-Span-ID"
HEADER_PARENT_SPAN_ID = "X-Parent-Span-ID"

_MISSING = "-"

_TRACE_ID: ContextVar[str] = ContextVar("trace_id", default="")
_SPAN_ID: ContextVar[str] = ContextVar("span_id", default="")
_PARENT_SPAN_ID: ContextVar[str] = ContextVar("parent_span_id", default="")


@dataclass(frozen=True)
class TraceSnapshot:
    """当前请求的追踪快照。"""

    trace_id: str
    span_id: str
    parent_span_id: str = ""


def new_span_id() -> str:
    """
    生成SpanID，16位hex，与OpenTelemetry span_id长度一致。

    :return: 16位十六进制字符串
    """
    return uuid.uuid4().hex[:16]


def _sync_celery_local(trace_id: str, span_id: str) -> None:
    """
    将trace_id与span_id同步到Celery线程本地上下文。

    :param trace_id: 追踪ID
    :param span_id: 当前SpanID
    """
    try:
        from backend.celery_scheduler.celery_base import LOCAL_CONTEXT_VAR

        LOCAL_CONTEXT_VAR.trace_id = trace_id or None
        LOCAL_CONTEXT_VAR.span_id = span_id or None
    except Exception:
        pass


def get_trace_id() -> str:
    """
    获取当前上下文的TraceID，缺失时回落Celery本地或占位符。

    :return: TraceID字符串；无值时为-
    """
    tid = _TRACE_ID.get()
    if tid:
        return tid
    try:
        from backend.celery_scheduler.celery_base import LOCAL_CONTEXT_VAR

        legacy = getattr(LOCAL_CONTEXT_VAR, "trace_id", None)
        if legacy:
            return str(legacy)
    except Exception:
        pass
    return _MISSING


def get_span_id() -> str:
    """
    获取当前上下文的SpanID，缺失时回落Celery本地或占位符。

    :return: SpanID字符串；无值时为-
    """
    sid = _SPAN_ID.get()
    if sid:
        return sid
    try:
        from backend.celery_scheduler.celery_base import LOCAL_CONTEXT_VAR

        legacy = getattr(LOCAL_CONTEXT_VAR, "span_id", None)
        if legacy:
            return str(legacy)
    except Exception:
        pass
    return _MISSING


def get_parent_span_id() -> str:
    """
    获取当前上下文的ParentSpanID。

    :return: ParentSpanID；无值时为空字符串
    """
    return _PARENT_SPAN_ID.get() or ""


def get_trace_snapshot() -> TraceSnapshot:
    """
    组装当前追踪快照。

    :return: TraceSnapshot实例
    """
    return TraceSnapshot(
        trace_id=get_trace_id(),
        span_id=get_span_id(),
        parent_span_id=get_parent_span_id(),
    )


def bind_trace_context(
        trace_id: str,
        span_id: str,
        parent_span_id: str = "",
) -> Tuple[Token, Token, Token]:
    """
    绑定Trace与Span到当前上下文，并同步Celery本地变量。

    :param trace_id: 追踪ID
    :param span_id: 当前SpanID
    :param parent_span_id: 父SpanID
    :return: 用于reset的ContextVar token元组
    """
    _sync_celery_local(trace_id, span_id)
    return (
        _TRACE_ID.set(trace_id or ""),
        _SPAN_ID.set(span_id or ""),
        _PARENT_SPAN_ID.set(parent_span_id or ""),
    )


def clear_trace_context(tokens: Tuple[Token, Token, Token]) -> None:
    """
    按token恢复绑定前的追踪上下文。

    :param tokens: bind_trace_context返回的token元组
    """
    trace_t, span_t, parent_t = tokens
    _TRACE_ID.reset(trace_t)
    _SPAN_ID.reset(span_t)
    _PARENT_SPAN_ID.reset(parent_t)


def _header_value(request: Request, name: str) -> str:
    """
    读取请求头并截断到128字符。

    :param request: Starlette请求对象
    :param name: 请求头名称
    :return: 去空白后的头值；缺失时为空字符串
    """
    return (request.headers.get(name) or "").strip()[:128]


def _incoming_trace_id(request: Request) -> str:
    """
    解析入站X-Trace-ID；未传时返回空字符串。

    :param request: Starlette请求对象
    :return: TraceID或空字符串
    """
    return _header_value(request, HEADER_TRACE_ID)


def _incoming_parent_span_id(request: Request) -> str:
    """
    解析入站父Span，优先X-Parent-Span-ID，其次X-Span-ID。

    :param request: Starlette请求对象
    :return: ParentSpanID或空字符串
    """
    parent = _header_value(request, HEADER_PARENT_SPAN_ID)
    if not parent:
        parent = _header_value(request, HEADER_SPAN_ID)
    return parent


def enter_server_span(request: Request) -> Tuple[TraceSnapshot, Tuple[Token, Token, Token]]:
    """
    为入站HTTP分配SpanID，TraceID仅使用客户端传入的X-Trace-ID。

    :param request: Starlette请求对象
    :return: (TraceSnapshot, bind_trace_context的token元组)
    """
    trace_id = _incoming_trace_id(request)
    parent_span_id = _incoming_parent_span_id(request)
    span_id = new_span_id()
    tokens = bind_trace_context(trace_id, span_id, parent_span_id)
    return TraceSnapshot(trace_id=trace_id, span_id=span_id, parent_span_id=parent_span_id), tokens


def enter_celery_span(
        trace_id: str = "",
        parent_span_id: str = "",
        span_id: str = "",
) -> Tuple[TraceSnapshot, Tuple[Token, Token, Token]]:
    """
    在Celery Worker中绑定追踪上下文。

    消息头含span_id时复用；否则为本任务新建SpanID。

    :param trace_id: 追踪ID
    :param parent_span_id: 父SpanID
    :param span_id: 可复用的SpanID；为空则新建
    :return: (TraceSnapshot, bind_trace_context的token元组)
    """
    tid = (trace_id or "").strip()
    sid = (span_id or "").strip() or new_span_id()
    tokens = bind_trace_context(tid, sid, (parent_span_id or "").strip())
    parent = (parent_span_id or "").strip()
    return TraceSnapshot(trace_id=tid, span_id=sid, parent_span_id=parent), tokens


def _is_inside_celery_worker() -> bool:
    """
    判断当前是否处于Celery任务执行上下文。

    :return: 在Worker任务内为True，否则为False
    """
    try:
        from celery._state import get_current_task

        return get_current_task() is not None
    except Exception:
        return False


def celery_dispatch_trace_headers() -> Dict[str, str]:
    """
    组装下发Celery消息头中的追踪字段。

    HTTP上下文透传trace_id与当前span_id；Worker内再下发时透传trace_id与parent_span_id。

    :return: 可写入Celery headers的字典
    """
    headers: Dict[str, str] = {}
    trace_id = get_trace_id()
    if trace_id and trace_id != _MISSING:
        headers["trace_id"] = trace_id
    span_id = get_span_id()
    if span_id == _MISSING:
        return headers
    if _is_inside_celery_worker():
        headers["parent_span_id"] = span_id
    else:
        headers["span_id"] = span_id
    return headers


def _extract_celery_trace_fields(request_dict: Mapping[str, Any]) -> Tuple[str, str, str]:
    """
    从Celery请求字典或其嵌套headers中提取追踪字段。

    :param request_dict: Celery任务请求相关字典
    :return: (trace_id, span_id, parent_span_id)
    """
    trace_id = (request_dict.get("trace_id") or "").strip()
    span_id = (request_dict.get("span_id") or "").strip()
    parent_span_id = (request_dict.get("parent_span_id") or "").strip()
    nested = request_dict.get("headers")
    if isinstance(nested, dict):
        inner = nested.get("headers") if isinstance(nested.get("headers"), dict) else nested
        if isinstance(inner, dict):
            trace_id = trace_id or (inner.get("trace_id") or "").strip()
            span_id = span_id or (inner.get("span_id") or "").strip()
            parent_span_id = parent_span_id or (inner.get("parent_span_id") or "").strip()
    return trace_id, span_id, parent_span_id


def apply_response_trace_headers(headers: MutableMapping[str, str], snapshot: TraceSnapshot) -> None:
    """
    将追踪快照写入HTTP响应头。

    :param headers: 可变响应头映射
    :param snapshot: 当前TraceSnapshot
    """
    if snapshot.trace_id:
        headers[HEADER_TRACE_ID] = snapshot.trace_id
    if snapshot.span_id and snapshot.span_id != _MISSING:
        headers[HEADER_SPAN_ID] = snapshot.span_id
    if snapshot.parent_span_id:
        headers[HEADER_PARENT_SPAN_ID] = snapshot.parent_span_id


def propagate_trace_headers(
        headers: Optional[Union[Mapping[str, Any], MutableMapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    为出站HTTP组装追踪头，透传X-Trace-ID并将当前Span写入X-Parent-Span-ID。

    :param headers: 已有请求头；为空时从空字典开始
    :return: 合并追踪字段后的请求头字典
    """
    out: Dict[str, Any] = dict(headers or {})
    trace_id = get_trace_id()
    span_id = get_span_id()
    if not trace_id or trace_id == _MISSING:
        return out

    def _has(name: str) -> bool:
        """判断输出头中是否已存在同名键（忽略大小写）。"""
        lower = name.lower()
        return any(k.lower() == lower for k in out)

    if not _has(HEADER_TRACE_ID):
        out[HEADER_TRACE_ID] = trace_id
    if span_id and span_id != _MISSING and not _has(HEADER_PARENT_SPAN_ID):
        out[HEADER_PARENT_SPAN_ID] = span_id
    return out
