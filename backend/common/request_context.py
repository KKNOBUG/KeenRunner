# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : request_context.py
@DateTime: 2026/5/29

轻量分布式追踪：X-Trace-ID + X-Span-ID + X-Parent-Span-ID。
- TraceID：仅来自请求头 X-Trace-ID，未传则由后端留空（日志为 -）
- SpanID：每个入站 HTTP、Celery 任务由服务端分配，经 X-Span-ID 回传/下发
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
    trace_id: str
    span_id: str
    parent_span_id: str = ""


def new_span_id() -> str:
    """生成 SpanID（16 位 hex，与 OpenTelemetry span_id 长度一致）。"""
    return uuid.uuid4().hex[:16]


def _sync_celery_local(trace_id: str, span_id: str) -> None:
    try:
        from backend.celery_scheduler.celery_base import LOCAL_CONTEXT_VAR

        LOCAL_CONTEXT_VAR.trace_id = trace_id or None
        LOCAL_CONTEXT_VAR.span_id = span_id or None
    except Exception:
        pass


def get_trace_id() -> str:
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
    return _PARENT_SPAN_ID.get() or ""


def get_trace_snapshot() -> TraceSnapshot:
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
    """绑定 Trace/Span 到当前上下文，返回用于 reset 的 token 元组。"""
    _sync_celery_local(trace_id, span_id)
    return (
        _TRACE_ID.set(trace_id or ""),
        _SPAN_ID.set(span_id or ""),
        _PARENT_SPAN_ID.set(parent_span_id or ""),
    )


def clear_trace_context(tokens: Tuple[Token, Token, Token]) -> None:
    trace_t, span_t, parent_t = tokens
    _TRACE_ID.reset(trace_t)
    _SPAN_ID.reset(span_t)
    _PARENT_SPAN_ID.reset(parent_t)


def _header_value(request: Request, name: str) -> str:
    return (request.headers.get(name) or "").strip()[:128]


def _incoming_trace_id(request: Request) -> str:
    """仅解析 X-Trace-ID，未传则返回空字符串。"""
    return _header_value(request, HEADER_TRACE_ID)


def _incoming_parent_span_id(request: Request) -> str:
    parent = _header_value(request, HEADER_PARENT_SPAN_ID)
    if not parent:
        parent = _header_value(request, HEADER_SPAN_ID)
    return parent


def enter_server_span(request: Request) -> Tuple[TraceSnapshot, Tuple[Token, Token, Token]]:
    """为当前入站 HTTP 分配 SpanID；TraceID 仅使用客户端传入的 X-Trace-ID。"""
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
    Celery Worker 绑定追踪上下文。
    - 消息头含 span_id 时复用（HTTP 直连下发）
    - 否则为本任务新建 SpanID
    """
    tid = (trace_id or "").strip()
    sid = (span_id or "").strip() or new_span_id()
    tokens = bind_trace_context(tid, sid, (parent_span_id or "").strip())
    parent = (parent_span_id or "").strip()
    return TraceSnapshot(trace_id=tid, span_id=sid, parent_span_id=parent), tokens


def _is_inside_celery_worker() -> bool:
    try:
        from celery._state import get_current_task

        return get_current_task() is not None
    except Exception:
        return False


def celery_dispatch_trace_headers() -> Dict[str, str]:
    """
    下发 Celery 时写入消息头追踪字段。
    - HTTP 上下文：透传 trace_id（若有）与当前 span_id（子任务复用同一 Span）
    - Celery 内再下发：仅透传 trace_id 与 parent_span_id，子任务新建 Span
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
    出站 HTTP：有 TraceID 时透传 X-Trace-ID，当前 Span 作为 X-Parent-Span-ID。
    """
    out: Dict[str, Any] = dict(headers or {})
    trace_id = get_trace_id()
    span_id = get_span_id()
    if not trace_id or trace_id == _MISSING:
        return out

    def _has(name: str) -> bool:
        lower = name.lower()
        return any(k.lower() == lower for k in out)

    if not _has(HEADER_TRACE_ID):
        out[HEADER_TRACE_ID] = trace_id
    if span_id and span_id != _MISSING and not _has(HEADER_PARENT_SPAN_ID):
        out[HEADER_PARENT_SPAN_ID] = span_id
    return out
