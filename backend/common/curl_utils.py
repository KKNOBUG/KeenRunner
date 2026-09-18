# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : curl_utils.py
@DateTime: 2026/9/17 10:00
"""
import base64
import json
import shlex
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, unquote, urlsplit

from backend.enums import HTTPMethod

# 数据体选项: 多次出现时按 curl 语义用 & 拼接(--data-urlencode 不做编码, 原样保留)
_DATA_FLAGS = {"-d", "--data", "--data-raw", "--data-binary", "--data-urlencode"}
# 表单选项(form-data); @file 文件字段超出压测热路径能力, 记警告
_FORM_FLAGS = {"-F", "--form"}
# 请求头选项
_HEADER_FLAGS = {"-H", "--header"}
# 施压语义下无意义的布尔开关: 直接忽略并记入解析提示
_IGNORED_BOOL_FLAGS = {
    "--compressed", "-k", "--insecure", "-L", "--location", "-s", "--silent",
    "-v", "--verbose", "-#", "--progress-bar", "-S", "--show-error",
    "--http1.1", "--http2", "--http0.9", "-4", "--ipv4", "-6", "--ipv6",
    "--no-keepalive", "-H0",
}
# 单值选项: 语义已由环境配置承接(施压目标不落库), 仅记录提示
_TARGETED_FLAGS = {"--connect-timeout", "-m", "--max-time", "--retry", "--resolve"}
# 带取值但压测不适用的选项: 丢弃取值并提示(输出/转储类, 语义与施压无关)
_IGNORED_VALUE_FLAGS = {"-o", "--output", "--out-param", "-D", "--dump-header", "-c", "--cookie-jar"}
# 所有需要取值的选项(并集; 用于取值获取与未知选项丢弃判断)
_VALUE_FLAGS = (
    _DATA_FLAGS | _FORM_FLAGS | _HEADER_FLAGS | _TARGETED_FLAGS | _IGNORED_VALUE_FLAGS
    | {"-X", "--request", "-u", "--user", "-b", "--cookie", "--url", "-e", "--referer", "-A", "--user-agent"}
)
# 解析警告上限, 防止畸形输入刷屏
MAX_WARNINGS = 10


def _tokenize(text: str) -> List[str]:
    """
    cURL 命令词法切分: 折叠续行后按 POSIX 规则切分。

    :param text: 原始命令文本(可含反斜杠/脱字符续行与 ANSI-C 引用)
    :return: token 列表(引号已剥离); 引号不配对时退化为空白切分保住主体参数
    """
    cleaned = text.replace("\r\n", "\n").strip()
    # 反斜杠(bash)/脱字符(Windows)续行折叠为空格, 便于整体按 POSIX 词法切分
    cleaned = cleaned.replace("\\\n", " ").replace("^\n", " ")
    # 浏览器 DevTools 复制的 bash 命令使用 ANSI-C 引用($'...'), 还原为普通引号再切分
    cleaned = cleaned.replace("$'", "'").replace('$"', '"')
    try:
        return shlex.split(cleaned, posix=True)
    except ValueError:
        return cleaned.split()


def _append_warning(warnings: List[str], message: str) -> None:
    """按上限追加解析警告(超限后丢弃, 避免畸形输入刷屏)。"""
    if len(warnings) < MAX_WARNINGS:
        warnings.append(message)


def _split_kv_pairs(body: str) -> List[Tuple[str, str]]:
    """
    把 a=1&b=2 形态的数据体拆为键值对(无 = 的段跳过)。

    :param body: 数据体文本
    :return: (key, value) 列表
    """
    pairs: List[Tuple[str, str]] = []
    for segment in body.split("&"):
        if "=" in segment:
            key, _, value = segment.partition("=")
            if key:
                pairs.append((key, value))
    return pairs


def _to_pair_rows(pairs: List[Tuple[str, str]]) -> List[Dict[str, str]]:
    """键值对列表 → 容器字段行结构([{key,value,desc}], 与请求块契约同构)。"""
    return [{"key": key, "value": value, "desc": ""} for key, value in pairs]


def parse_curl_command(text: str) -> Dict[str, Any]:
    """
    解析 cURL 命令文本为压测接口草稿(纯函数, 无IO无状态)。

    输出与 PerfApiCreate 请求块同构: 主机地址不落库(施压目标由环境配置承接),
    绝对地址剥离为路径 + 端口; 不支持的选项进入 warnings 由前端回显提示。

    :param text: cURL 命令文本
    :return: 草稿字典, 结构:
        {"api_name": "...", "step_type": "HTTP请求", "request_method": "POST",
         "request_url": "/api/v1/x", "request_port": "8443",
         "request_header": [...], "request_params": [...],
         "request_form_data": [...], "request_form_urlencoded": [...],
         "request_args_type": "json", "request_body": {...}, "request_text": "...",
         "api_source": "curl", "warnings": [...]}
    :raises ValueError: 未找到请求地址或命令为空
    """
    tokens: List[str] = _tokenize(text)
    warnings: List[str] = []

    url: Optional[str] = None
    method: Optional[str] = None
    header_pairs: List[Tuple[str, str]] = []
    data_parts: List[str] = []
    form_pairs: List[Tuple[str, str]] = []
    get_mode = False
    basic_auth: Optional[str] = None
    cookie_value: Optional[str] = None

    index, total = 0, len(tokens)
    while index < total:
        token = tokens[index]
        index += 1
        if token in ("curl", "curl.exe") or token.endswith("/curl"):
            continue
        if token in _IGNORED_BOOL_FLAGS:
            _append_warning(warnings, f"已忽略选项 {token}(对压测语义无影响)")
            continue
        if token in _TARGETED_FLAGS:
            _append_warning(warnings, f"已忽略选项 {token}(连接控制由施压环境统一承接)")
            # 跳过该选项的取值
            if index < total and not tokens[index].startswith("-"):
                index += 1
            continue
        if token in _IGNORED_VALUE_FLAGS:
            _append_warning(warnings, f"已忽略选项 {token}(压测场景不适用)")
            # 跳过该选项的取值
            if index < total and not tokens[index].startswith("-"):
                index += 1
            continue

        # 选项与取值: 支持 "--flag value" 与 "--flag=value" 两种形态
        flag, value = token, None
        if flag.startswith("-") and "=" in flag:
            flag, _, value = flag.partition("=")
        if value is None and flag in _VALUE_FLAGS:
            if index < total:
                value = tokens[index]
                index += 1
            else:
                _append_warning(warnings, f"选项 {flag} 缺少取值, 已忽略")
                continue
        if value is not None and flag.startswith("-") and flag not in _VALUE_FLAGS:
            # 带取值但不在支持清单内的选项(如 --output): 丢弃取值并提示
            _append_warning(warnings, f"已忽略选项 {flag}(压测场景不适用)")
            continue

        if flag in _HEADER_FLAGS and value:
            name, separator, header_value = value.partition(":")
            if separator and name.strip():
                header_pairs.append((name.strip(), header_value.strip()))
            else:
                _append_warning(warnings, f"请求头 {value!r} 缺少冒号分隔, 已忽略")
        elif flag in _DATA_FLAGS:
            if value is not None:
                data_parts.append(value)
        elif flag in _FORM_FLAGS and value:
            name, _, field_value = value.partition("=")
            if field_value.startswith("@"):
                _append_warning(warnings, f"表单文件字段 {name} 不支持导入(压测不支持文件上传)")
            else:
                # curl -F 支持 "name=value;type=text/plain" 尾缀, 截去分号元数据
                form_pairs.append((name, field_value.partition(";")[0]))
        elif flag in ("-X", "--request") and value:
            method = value.upper()
        elif flag in ("-u", "--user") and value:
            basic_auth = value
        elif flag in ("-b", "--cookie") and value:
            cookie_value = value
        elif flag in ("-G", "--get"):
            get_mode = True
        elif flag in ("-I", "--head"):
            method = HTTPMethod.HEAD.value
        elif flag in ("-e", "--referer") and value:
            header_pairs.append(("Referer", value))
        elif flag in ("-A", "--user-agent") and value:
            header_pairs.append(("User-Agent", value))
        elif flag == "--url" and value:
            url = value
        elif not flag.startswith("-") and url is None:
            # 首个非选项参数即请求地址
            url = token
        elif flag.startswith("-"):
            # 未识别的选项兜底提示, 避免静默丢弃让用户误以为已生效
            _append_warning(warnings, f"已忽略未识别选项 {flag}")

    if not url:
        raise ValueError("cURL 命令中未找到请求地址")

    # 数据体与请求方法: 有数据体未显式指定方法时按 curl 语义为 POST
    body_text = "&".join(data_parts) if data_parts else None
    if method is None:
        method = HTTPMethod.POST.value if (body_text or form_pairs) and not get_mode else HTTPMethod.GET.value

    # -G: 数据体转查询串
    query_pairs: List[Tuple[str, str]] = []
    if get_mode and body_text:
        query_pairs.extend(_split_kv_pairs(body_text))
        body_text = None

    # 地址拆解: 主机不落库, 路径 + 端口 + 查询串拆分回显
    parts = urlsplit(url)
    request_url = parts.path or "/"
    request_port: Optional[str] = str(parts.port) if parts.port and parts.port not in (80, 443) else None
    if parts.query:
        query_pairs.extend(parse_qsl(parts.query, keep_blank_values=True))
    if parts.scheme or parts.hostname:
        _append_warning(warnings, "已剥离主机地址, 施压目标由执行环境的APP节点配置解析")
    path_tail = [seg for seg in parts.path.split("/") if seg]
    suggested_name = unquote_safe(path_tail[-1]) if path_tail else (parts.hostname or "cURL导入接口")

    if basic_auth:
        encoded = base64.b64encode(basic_auth.encode("utf-8")).decode("ascii")
        header_pairs.append(("Authorization", f"Basic {encoded}"))
    if cookie_value and not any(name.lower() == "cookie" for name, _ in header_pairs):
        header_pairs.append(("Cookie", cookie_value))

    # 数据体归位: 按 Content-Type 分派载体字段(与 PerfApiForm 的 bodyType 编辑形态一一对应)
    content_type = next((v for k, v in header_pairs if k.lower() == "content-type"), "")
    request_body: Optional[Dict[str, Any]] = None
    request_text: Optional[str] = None
    request_form_urlencoded: Optional[List[Dict[str, str]]] = None
    request_form_data: Optional[List[Dict[str, str]]] = _to_pair_rows(form_pairs) if form_pairs else None
    args_type = "none"
    if form_pairs:
        args_type = "form-data"
    elif body_text is not None:
        if "application/json" in content_type or "json" in content_type:
            try:
                request_body = json.loads(body_text)
                args_type = "json"
            except json.JSONDecodeError:
                request_text = body_text
                args_type = "raw"
                _append_warning(warnings, "请求体不是合法JSON, 已按raw文本导入")
        elif "xml" in content_type:
            request_text = body_text
            args_type = "xml"
        elif "x-www-form-urlencoded" in content_type:
            request_form_urlencoded = _to_pair_rows(_split_kv_pairs(body_text))
            args_type = "x-www-form-urlencoded"
        else:
            request_text = body_text
            args_type = "raw"
    if "multipart/form-data" in content_type and not form_pairs:
        _append_warning(warnings, "Content-Type为multipart但未解析到-F表单字段")

    return {
        "api_name": suggested_name or "cURL导入接口",
        "step_type": "HTTP请求",
        "request_method": method,
        "request_url": request_url,
        "request_port": request_port,
        "request_header": _to_pair_rows(header_pairs) or None,
        "request_params": _to_pair_rows(query_pairs) or None,
        "request_form_data": request_form_data,
        "request_form_urlencoded": request_form_urlencoded,
        "request_args_type": args_type,
        "request_body": request_body,
        "request_text": request_text,
        "api_source": "curl",
        "warnings": warnings,
    }


def unquote_safe(value: str) -> str:
    """
    路径段解码展示名(非法序列原样返回, 保证建议名称不因畸形编码失败)。

    :param value: 路径段文本
    :return: 解码后的展示文本
    """
    try:
        return unquote(value, errors="strict")
    except Exception:
        return value
