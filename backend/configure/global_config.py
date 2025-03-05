# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : global_config.py
@DateTime: 2025/1/16 15:30
"""
from typing import Dict, Any


class GlobalConfig:
    ROUTE_ALIAS: Dict[str, Any] = {}
    DATE_FORMAT: str = "%Y-%m-%d"
    TIME_FORMAT: str = "%H:%M:%S"
    DATETIME_SCHEMA: str = "%Y%m%d%H%M%S"
    DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"


GLOBAL_CONFIG = GlobalConfig()
