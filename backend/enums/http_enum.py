# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : http_enum.py
@DateTime: 2025/1/13 12:57
"""
from backend.enums.base_enum_cls import BaseEnumCls


class HTTPMethod(BaseEnumCls):
    """
    HTTP请求方式枚举
    """
    GET = "GET"
    HEAD = "HEAD"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"
    CONNECT = "CONNECT"
    TRACE = "TRACE"


if __name__ == '__main__':
    print(HTTPMethod.GET in HTTPMethod.get_members())
    print(HTTPMethod.GET.value)
