# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : protocol_tcp.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, Optional, Tuple, Union

import orjson

from backend.common import TcpFrameMode
from backend.enums import (
    AutoTestReqArgsType,
    AutoTestTcpConnectType,
    AutoTestTcpDatagramLength,
    AutoTestTcpEndSymbol,
    AutoTestTcpRadix,
)

# TCP单次响应最大读取字节数：对齐JMeter不向用户暴露，超出即按响应异常截断处理
TCP_MAX_RESPONSE_BYTES: int = 10 * 1024 * 1024

# 长度前缀进制映射：枚举展示值 → 数字进制（对齐JMeter：前缀为文本数字）
TCP_RADIX_BASE: Dict[str, int] = {
    AutoTestTcpRadix.DECIMAL.value: 10,
    AutoTestTcpRadix.HEX.value: 16,
}

# 结束符展示值 → 真实字节序列；数据库与前端存展示值，收发时经此注册表映射（请求结束符为枚举下拉）
TCP_END_SYMBOL_BYTES: Dict[str, Optional[bytes]] = {
    AutoTestTcpEndSymbol.NONE.value: None,
    AutoTestTcpEndSymbol.CRLF.value: b"\r\n",
    AutoTestTcpEndSymbol.CR.value: b"\r",
    AutoTestTcpEndSymbol.LF.value: b"\n",
}

# 响应结束符自定义文本的转义序列映射（对齐JMeter EOL自定义输入）
TCP_RESPONSE_END_SYMBOL_ESCAPES: Dict[str, bytes] = {
    "r": b"\r",
    "n": b"\n",
    "t": b"\t",
    "0": b"\x00",
    "\\": b"\\",
}


def parse_response_end_symbol(raw: Any) -> Optional[bytes]:
    """
    解析响应结束符自定义文本为字节序列。

    规则：无/空 → None（不使用，RAW读至EOF）；\\r\\n、\\n、\\r、\\t、\\0、\\xHH等转义序列 → 对应字节；其余按字面字符（UTF-8编码）。

    :param raw: 用户输入文本（兼容存量枚举展示值）
    :return: 结束符字节序列；不使用返回None
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text == AutoTestTcpEndSymbol.NONE.value:
        return None
    out = bytearray()
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt in TCP_RESPONSE_END_SYMBOL_ESCAPES:
                out += TCP_RESPONSE_END_SYMBOL_ESCAPES[nxt]
                i += 2
                continue
            if nxt in ("x", "X") and i + 3 < len(text):
                try:
                    out.append(int(text[i + 2:i + 4], 16))
                    i += 4
                    continue
                except ValueError:
                    pass
        out += ch.encode("utf-8")
        i += 1
    return bytes(out)


@dataclass
class TcpFrameConfig:
    """TCP帧配置推导结果（执行引擎与调试服务共用，单一事实源）。"""
    frame_mode: TcpFrameMode
    radix: int
    radix_length: int
    include_length_prefix: bool
    request_end_symbol: Optional[bytes]
    response_end_symbol: Optional[bytes]
    encoding: str
    hex_string: bool
    send_only: bool
    long_connection: bool


def tcp_enum_value(raw: Any) -> Optional[str]:
    """
    读取枚举或字符串字段的展示值；空串归一为None。

    :param raw: 枚举成员、字符串或None
    :return: 枚举值字符串或None
    """
    if raw is None:
        return None
    value = raw.value if isinstance(raw, Enum) else str(raw)
    return value or None


def resolve_tcp_frame_config(step: Any) -> TcpFrameConfig:
    """
    按TCP步骤字段组合推导帧配置；

    进制数≠不使用 → 长度前缀（结束符字段保留但不参与成帧计算）；进制数=不使用且配置了结束符 → 结束符；均未配置 → RAW

    :param step: 步骤对象
    :return: 帧配置对象
    """
    radix_value = tcp_enum_value(getattr(step, "tcp_radix", None)) or AutoTestTcpRadix.NONE.value
    datagram_value = tcp_enum_value(getattr(step, "tcp_datagram_length", None)) or AutoTestTcpDatagramLength.EXCLUDE.value
    request_symbol = tcp_enum_value(getattr(step, "tcp_request_end_symbol", None)) or AutoTestTcpEndSymbol.NONE.value
    # 响应结束符为自定义文本：无/空→None；非空即结束符模式（对齐JMeter EOL）
    response_symbol_bytes = parse_response_end_symbol(getattr(step, "tcp_response_end_symbol", None))
    connect_type_value = tcp_enum_value(getattr(step, "tcp_connect_type", None)) or AutoTestTcpConnectType.SHORT.value
    encoding = (getattr(step, "tcp_encoding", None) or "utf-8").strip() or "utf-8"

    if radix_value != AutoTestTcpRadix.NONE.value:
        frame_mode = TcpFrameMode.LENGTH_PREFIX
    elif request_symbol != AutoTestTcpEndSymbol.NONE.value or response_symbol_bytes is not None:
        frame_mode = TcpFrameMode.TERMINATOR
    else:
        frame_mode = TcpFrameMode.RAW

    return TcpFrameConfig(
        frame_mode=frame_mode,
        radix=TCP_RADIX_BASE.get(radix_value, 10),
        radix_length=int(getattr(step, "tcp_radix_length", None) or 8),
        include_length_prefix=(datagram_value == AutoTestTcpDatagramLength.INCLUDE.value),
        request_end_symbol=TCP_END_SYMBOL_BYTES.get(request_symbol),
        response_end_symbol=response_symbol_bytes,
        encoding=encoding,
        hex_string=bool(getattr(step, "tcp_hex_string", False)),
        send_only=(connect_type_value == AutoTestTcpConnectType.SEND_ONLY.value),
        long_connection=(connect_type_value == AutoTestTcpConnectType.LONG.value),
    )


@dataclass
class TcpParsedResponse:
    """TCP响应解析结果。"""
    response_text: str
    response_json: Optional[Any]
    response_data: Optional[Union[str, dict, list]]


def select_tcp_payload(
        request_args_type: Optional[AutoTestReqArgsType],
        *,
        request_text: Optional[str],
        request_body: Any,
        serialize_json: bool = False,
) -> Any:
    """
    按请求体类型选择TCP载荷；调试路径可将JSON对象序列化为字符串。

    :param request_args_type: 请求体类型
    :param request_text: 文本/XML/RAW载荷
    :param request_body: JSON载荷（可为dict/list）
    :param serialize_json: True时JSON/未知类型对象转UTF-8 JSON字符串（仅调试发送需要）
    :return: 发往TCP客户端的payload
    """
    if request_args_type == AutoTestReqArgsType.JSON:
        payload = request_body
    elif request_args_type in (AutoTestReqArgsType.RAW, AutoTestReqArgsType.XML):
        payload = request_text
    else:
        payload = request_text if request_text not in (None, "") else request_body
    if serialize_json and isinstance(payload, (dict, list)):
        return orjson.dumps(payload).decode("UTF-8")
    return payload


def build_tcp_debug_request_info_body(
        request_args_type: Optional[AutoTestReqArgsType],
        *,
        request_text: Optional[str],
        request_body: Any,
) -> Any:
    """
    组装TCP调试回显的请求体，形态对齐引擎落库的request_body。

    JSON返回原始对象供前端格式化，XML/RAW返回文本。

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
        hex_string: bool = False,
) -> TcpParsedResponse:
    """
    解析TCP响应原始字节：文本解码后对JSON形态自动识别，避免解析失败时重发请求。

    :param raw_bytes: TCP响应原始字节
    :param encoding: 解码字符集
    :param hex_string: 启用后响应字节转大写HEX字符串
    :return: 解析后的文本、JSON与展示用data
    """
    if hex_string:
        response_text = raw_bytes.hex().upper() if raw_bytes else ""
        return TcpParsedResponse(response_text=response_text, response_json=None, response_data=response_text)

    try:
        response_text = raw_bytes.decode(encoding, errors="ignore")
    except Exception:
        response_text = ""
    response_json: Optional[Any] = None
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
        payload: Any = None,
) -> Tuple[Optional[Any], Optional[str]]:
    """
    为TCP提取/断言准备request_json与request_text来源。

    执行期传实际发送payload（用于request_text为空时回落），调试期不传payload。

    :param request_body: 原始/解析后的请求体
    :param request_text: 请求文本
    :param payload: 实际发送载荷；调试路径可为None
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
