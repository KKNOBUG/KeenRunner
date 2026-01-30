# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : global_config.py
@DateTime: 2025/1/16 15:30
"""
from functools import lru_cache
from typing import Dict, Any

from pydantic_settings import BaseSettings


class GlobalConfig(BaseSettings):
    ROUTER_SUMMARY: Dict[str, Any] = {}
    ROUTER_TAGS: Dict[str, Any] = {}
    DATE_FORMAT: str = "%Y-%m-%d"
    TIME_FORMAT: str = "%H:%M:%S"
    DATETIME_FORMAT1: str = "%Y%m%d%H%M%S"
    DATETIME_FORMAT2: str = "%Y-%m-%d %H:%M:%S"


@lru_cache(maxsize=1)
def get_global_config():
    return GlobalConfig()


GLOBAL_CONFIG = get_global_config()
