# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : __init__.py
@DateTime: 2025/12/28 16:15
"""
from backend.applications.aotutest.services.autotest_runtime.datagram.json_replace import JsonDatagram
from backend.applications.aotutest.services.autotest_runtime.datagram.xml_replace import XmlDatagram

__all__ = ["JsonDatagram", "XmlDatagram"]
