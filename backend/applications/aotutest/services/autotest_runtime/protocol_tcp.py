# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Optional, Tuple, Union

import orjson

from backend.enums import AutoTestReqArgsType


@dataclass
class TcpParsedResponse:
    response_text: str
    response_json: Optional[Any]
    response_data: Optional[Union[str, dict, list]]


def select_tcp_payload(
        request_args_type: Optional[AutoTestReqArgsType],
        *,
        request_text: Optional[str],
        request_body: Any,
) -> Any:
    """
    按request_args_type选择TCP发送载荷，语义对齐TcpStepExecutor。

    :param request_args_type: 请求体类型
    :param request_text: 文本/XML/RAW载荷
    :param request_body: JSON载荷（可为dict/list）
    :return: 发往TCP客户端的payload
    """
    if request_args_type is None:
        return request_text if request_text not in (None, "") else request_body
    if request_args_type == AutoTestReqArgsType.RAW:
        return request_text
    if request_args_type == AutoTestReqArgsType.JSON:
        return request_body
    if request_args_type == AutoTestReqArgsType.XML:
        return request_text
    return request_text if request_text not in (None, "") else request_body


def select_tcp_debug_payload(
        request_args_type: Optional[AutoTestReqArgsType],
        *,
        request_text: Optional[str],
        request_body: Any,
) -> Any:
    """
    调试接口发送载荷：JSON将dict/list序列化为字符串（AioTcpClient对list不会走orjson）；其它类型仅取request_text。

    request_info.body 请用 build_tcp_debug_request_info_body，与引擎落库的 request_body 形态一致。

    :param request_args_type: 请求体类型
    :param request_text: 文本/XML/RAW载荷
    :param request_body: JSON载荷
    :return: 调试路径实际发送用的payload
    """
    if request_args_type == AutoTestReqArgsType.JSON:
        if isinstance(request_body, (dict, list)):
            return orjson.dumps(request_body).decode("UTF-8")
        return request_body
    return request_text


def build_tcp_debug_request_info_body(
        request_args_type: Optional[AutoTestReqArgsType],
        *,
        request_text: Optional[str],
        request_body: Any,
) -> Any:
    """
    组装TCP调试回显的request_info.body，形态对齐 execute_or_debugging 落库的 request_body。

    JSON 返回 dict/list（前端再缩进格式化）；字符串若为合法JSON则解析为对象。
    XML/RAW 返回 request_text。

    :param request_args_type: 请求体类型
    :param request_text: 文本/XML/RAW载荷
    :param request_body: JSON载荷
    :return: 回显用请求体
    """
    if request_args_type == AutoTestReqArgsType.JSON:
        if isinstance(request_body, (dict, list)):
            return request_body
        if isinstance(request_body, str) and request_body.strip():
            try:
                parsed = orjson.loads(request_body)
                if isinstance(parsed, (dict, list)):
                    return parsed
            except (orjson.JSONDecodeError, ValueError, TypeError):
                return request_body
        return request_body
    return request_text


def resolve_tcp_debug_request_extract_sources(
        *,
        request_body: Any,
        request_text: Optional[str],
) -> Tuple[Optional[Any], Optional[str]]:
    """
    调试接口历史契约下的TCP提取请求侧来源（与改造前view一致）。

    :param request_body: 请求体
    :param request_text: 请求文本
    :return: (request_json_for_extract, request_text_for_extract)
    """
    request_json_for_extract: Optional[Any] = None
    if isinstance(request_body, (dict, list)):
        request_json_for_extract = request_body
    elif isinstance(request_text, str) and request_text.strip().startswith(("{", "[")):
        try:
            parsed_request = orjson.loads(request_text)
            if isinstance(parsed_request, (dict, list)):
                request_json_for_extract = parsed_request
        except Exception:
            request_json_for_extract = None

    request_text_for_extract = request_text
    if request_text_for_extract in (None, "") and isinstance(request_body, (dict, list)):
        request_text_for_extract = orjson.dumps(request_body).decode("UTF-8")
    return request_json_for_extract, request_text_for_extract


def parse_tcp_timeouts(
        connect_timeout: Any,
        read_timeout: Any,
) -> Tuple[Optional[timedelta], Optional[timedelta]]:
    """
    将连接/读取超时秒数解析为timedelta；非法值视为None。

    :param connect_timeout: 连接超时（秒，可为数字或字符串）
    :param read_timeout: 读取超时（秒）
    :return: (connect_td, read_td)
    """
    connect_td: Optional[timedelta] = None
    if connect_timeout not in (None, ""):
        try:
            connect_td = timedelta(seconds=float(connect_timeout))
        except (TypeError, ValueError):
            connect_td = None
    read_td: Optional[timedelta] = None
    if read_timeout not in (None, ""):
        try:
            read_td = timedelta(seconds=float(read_timeout))
        except (TypeError, ValueError):
            read_td = None
    return connect_td, read_td


def parse_tcp_response(
        raw_bytes: bytes,
        *,
        encoding: str,
        response_type: str,
) -> TcpParsedResponse:
    """
    按tcp_response_type本地解析原始字节，避免解析失败时重发请求。

    :param raw_bytes: TCP响应原始字节
    :param encoding: 解码字符集
    :param response_type: json/xml/bytes/text
    :return: 解析后的文本、JSON与展示用data
    """
    response_type = (response_type or "text").strip().lower()
    try:
        response_text = raw_bytes.decode(encoding, errors="ignore")
    except Exception:
        response_text = ""
    response_json: Optional[Any] = None

    if response_type == "json":
        try:
            body_any = orjson.loads(raw_bytes) if raw_bytes else None
            response_json = body_any if isinstance(body_any, (dict, list)) else None
            if body_any is not None:
                response_text = orjson.dumps(body_any).decode("UTF-8")
        except Exception:
            response_json = None
    elif response_type == "xml":
        try:
            if raw_bytes and raw_bytes.strip():
                from lxml import etree
                parser = etree.XMLParser(recover=False, remove_blank_text=True, encoding=encoding)
                root = etree.fromstring(raw_bytes, parser=parser)
                response_text = etree.tostring(
                    root, encoding=str, pretty_print=True, xml_declaration=False
                ).strip()
        except Exception:
            pass
        response_json = None
    elif response_type == "bytes":
        response_json = None
    else:
        try:
            response_json = (
                orjson.loads(response_text)
                if response_text and response_text.strip().startswith(("{", "["))
                else None
            )
        except Exception:
            response_json = None

    response_data: Optional[Union[str, dict, list]] = (
        response_json if response_json is not None else response_text
    )
    return TcpParsedResponse(
        response_text=response_text,
        response_json=response_json,
        response_data=response_data,
    )


def resolve_tcp_request_extract_sources(
        *,
        request_body: Any,
        request_text: Optional[str],
        payload: Any,
) -> Tuple[Optional[Any], Optional[str]]:
    """
    为TCP提取/断言准备request_json与request_text来源。

    :param request_body: 原始/解析后的请求体
    :param request_text: 请求文本
    :param payload: 实际发送载荷
    :return: (request_json_for_extract, request_text_for_extract)
    """
    request_json_for_extract: Optional[Any] = None
    if isinstance(request_body, (dict, list)):
        request_json_for_extract = request_body
    elif isinstance(request_text, str) and request_text.strip().startswith(("{", "[")):
        try:
            parsed_request = orjson.loads(request_text)
            if isinstance(parsed_request, (dict, list)):
                request_json_for_extract = parsed_request
        except Exception:
            request_json_for_extract = None

    request_text_for_extract = request_text
    if request_text_for_extract in (None, ""):
        if isinstance(payload, str):
            request_text_for_extract = payload
        elif isinstance(request_body, (dict, list)):
            request_text_for_extract = orjson.dumps(request_body).decode("UTF-8")
    return request_json_for_extract, request_text_for_extract


def tcp_body_source_for_assert(response_type: str) -> str:
    """
    根据TCP响应类型选择提取断言的body_source标识。

    :param response_type: json/xml/text/bytes
    :return: body_source字符串
    """
    response_type = (response_type or "text").strip().lower()
    if response_type == "json":
        return "response json"
    if response_type == "xml":
        return "response xml"
    if response_type == "text":
        return "response text"
    return "response json"
