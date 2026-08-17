# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

from backend.enums import AutoTestReqArgsType


@dataclass
class HttpBodyPayloads:
    json_payload: Optional[Any] = None
    data_payload: Optional[Any] = None
    content_payload: Optional[Any] = None
    file_payload: Optional[Any] = None
    headers: Optional[Dict[str, Any]] = None


def assemble_http_body_payloads(
        request_args_type: Optional[AutoTestReqArgsType],
        *,
        request_text: Optional[str],
        request_body: Any,
        form_data: Optional[Dict[str, Any]],
        form_files: Optional[Dict[str, Any]],
        urlencoded: Optional[Dict[str, Any]],
        headers: Optional[Dict[str, Any]],
) -> HttpBodyPayloads:
    """
    按request_args_type装配HTTP请求体字段；XML缺省时补齐Content-Type。

    :param request_args_type: 请求体类型枚举，None时走兼容推断
    :param request_text: 文本/XML/RAW请求体
    :param request_body: JSON请求体
    :param form_data: form-data字段
    :param form_files: form-data文件字段
    :param urlencoded: x-www-form-urlencoded字段
    :param headers: 请求头（可能就地补Content-Type）
    :return: 装配后的载荷与（可能更新后的）headers
    """
    json_payload: Optional[Any] = None
    data_payload: Optional[Any] = None
    content_payload: Optional[Any] = None
    file_payload: Optional[Any] = None
    out_headers = headers

    if request_args_type is None:
        # 未配置时保持兼容：优先raw -> form-data -> urlencoded作为data，若有request_body且未产生data则作为json
        if request_text:
            data_payload = request_text
        elif form_data or form_files:
            data_payload = form_data
            file_payload = form_files if form_files else None
        elif urlencoded:
            data_payload = urlencoded
        if request_body and not data_payload:
            json_payload = request_body
    elif request_args_type in (AutoTestReqArgsType.NONE, AutoTestReqArgsType.PARAMS):
        pass
    elif request_args_type == AutoTestReqArgsType.RAW:
        data_payload = request_text
    elif request_args_type == AutoTestReqArgsType.JSON:
        json_payload = request_body
    elif request_args_type == AutoTestReqArgsType.XML:
        content_payload = request_text
        if out_headers is None:
            out_headers = {}
        has_content_type = any(k.lower() == "content-type" for k in out_headers)
        if not has_content_type:
            out_headers["Content-Type"] = "application/xml; charset=utf-8"
    elif request_args_type == AutoTestReqArgsType.FORM_DATA:
        data_payload = form_data
        file_payload = form_files if form_files else None
    elif request_args_type == AutoTestReqArgsType.X_WWW_FORM_URLENCODED:
        data_payload = urlencoded

    return HttpBodyPayloads(
        json_payload=json_payload,
        data_payload=data_payload,
        content_payload=content_payload,
        file_payload=file_payload,
        headers=out_headers,
    )


def encode_http_header_values(headers: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    对请求头字符串值做UTF-8百分号编码，避免中文等非ASCII导致发送失败。

    :param headers: 原始请求头
    :return: 编码后的请求头；入参为空则原样返回
    """
    if not headers:
        return headers
    return {
        key: quote(value, encoding="utf-8", safe=":/?#[]@!$&'()*+,;=-._~%")
        if isinstance(value, str) else value
        for key, value in headers.items()
    }


def build_httpx_request_kwargs(
        *,
        headers: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        json_data: Optional[Any] = None,
        content: Optional[Any] = None,
        files: Optional[Any] = None,
        timeout: Optional[Any] = None,
        encode_headers: bool = True,
) -> Dict[str, Any]:
    """
    组装httpx.request可用的kwargs，过滤None，可选编码headers。

    :param headers: 请求头
    :param params: 查询参数
    :param data: 非JSON请求体
    :param json_data: JSON请求体
    :param content: 原始内容（如XML）
    :param files: 上传文件
    :param timeout: 超时配置
    :param encode_headers: 是否对header值做百分号编码
    :return: 可直接传给httpx的关键字参数
    """
    kwargs: Dict[str, Any] = {
        "headers": headers,
        "params": params,
        "data": data,
        "json": json_data,
        "content": content,
        "files": files,
    }
    if timeout is not None:
        kwargs["timeout"] = timeout
    kwargs = {key: value for key, value in kwargs.items() if value is not None}
    if encode_headers and kwargs.get("headers"):
        kwargs["headers"] = encode_http_header_values(kwargs["headers"])
    return kwargs


def infer_http_actual_body(
        *,
        request_args_type: Optional[AutoTestReqArgsType],
        json_payload: Optional[Any],
        content_payload: Optional[Any],
        data_payload: Optional[Any],
        file_payload: Optional[Any],
        form_data: Optional[Dict[str, Any]],
        form_files: Optional[Dict[str, Any]],
) -> Tuple[str, Any]:
    """
    推断调试回显用的实际请求体类型与内容。

    :param request_args_type: 请求体类型
    :param json_payload: JSON载荷
    :param content_payload: XML等content载荷
    :param data_payload: data载荷
    :param file_payload: 文件载荷
    :param form_data: form-data字典（兼容推断用）
    :param form_files: form文件字典（兼容推断用）
    :return: (body_type, body)
    """
    actual_body_type = "none"
    actual_body: Any = None
    if json_payload is not None:
        actual_body_type = "json"
        actual_body = json_payload
    elif content_payload is not None:
        actual_body_type = "xml"
        actual_body = content_payload
    elif data_payload is not None:
        if request_args_type == AutoTestReqArgsType.FORM_DATA:
            actual_body_type = "form-data"
        elif request_args_type == AutoTestReqArgsType.X_WWW_FORM_URLENCODED:
            actual_body_type = "x-www-form-urlencoded"
        elif request_args_type == AutoTestReqArgsType.RAW:
            actual_body_type = "text"
        else:
            actual_body_type = "form-data" if (form_data or form_files) else "x-www-form-urlencoded"
        actual_body = data_payload
    if file_payload is not None:
        # 与历史调试接口保持一致：直接展开合并（非dict时由调用方失败路径承接）
        actual_body = actual_body or {}
        actual_body = {**actual_body, "__files": file_payload}
    return actual_body_type, actual_body


def format_byte_size(size: int) -> str:
    """
    将字节数格式化为可读字符串。

    :param size: 字节数
    :return: 如12.34KB或512B
    """
    return f"{size / 1024:.2f}KB" if size > 1024 else f"{size}B"


def is_absolute_http_url(url: Optional[str]) -> bool:
    """判断是否已是带协议的绝对HTTP/HTTPS地址。"""
    return (url or "").strip().lower().startswith(("http://", "https://"))


def build_absolute_http_url(host: str, port: Optional[str], path: str) -> str:
    """
    将环境host/port与相对路径拼成绝对HTTP URL。

    path 为/或空时表示站点根路径，结果带末尾斜杠，避免 httpx 收到无协议的空 URL。

    :param host: 主机（可带或不带协议）
    :param port: 端口字符串，可空
    :param path: 相对路径
    :return: 绝对URL
    """
    host = (host or "").strip().rstrip("/").rstrip(":")
    port = (str(port).strip() if port is not None and str(port).strip() else "")
    path = (path or "").lstrip("/")
    if not host.lower().startswith(("http://", "https://")):
        host = f"http://{host}"
    origin = f"{host}:{port}" if port else host
    return f"{origin}/{path}" if path else f"{origin}/"
