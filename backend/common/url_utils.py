# -*- coding: utf-8 -*-
"""
HTTP 地址拼接通用工具。

原为 autotest_runtime/protocol_http.py 内部函数, 因功能用例执行、用例调试与压测
施压三条链路均以同一口径把「环境 host/port + 相对路径」拼成绝对地址, 上移到 common
层共用, 避免性能测试模块为两个纯函数反向依赖 autotest 业务包。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : url_utils.py
@DateTime: 2026/9/15 10:20
"""
from __future__ import annotations

from typing import Optional


def is_absolute_http_url(url: Optional[str]) -> bool:
    """判断是否已是带协议的绝对HTTP/HTTPS地址。"""
    return (url or "").strip().lower().startswith(("http://", "https://"))


def build_absolute_http_url(host: str, port: Optional[str], path: str) -> str:
    """
    将环境host/port与相对路径拼成绝对HTTP URL。

    path为空或/时表示根路径，结果带末尾斜杠。

    :param host: 主机（可带或不带协议）
    :param port: 端口字符串，可空
    :param path: 相对路径
    :return: 绝对URL
    :example:
        >>> build_absolute_http_url("127.0.0.1", "8000", "/api/users")
        'http://127.0.0.1:8000/api/users'
    """
    host = (host or "").strip().rstrip("/").rstrip(":")
    port = (str(port).strip() if port is not None and str(port).strip() else "")
    path = (path or "").lstrip("/")
    if not host.lower().startswith(("http://", "https://")):
        host = f"http://{host}"
    origin = f"{host}:{port}" if port else host
    return f"{origin}/{path}" if path else f"{origin}/"
