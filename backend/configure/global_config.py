# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : global_config.py
@DateTime: 2025/1/16 15:30
"""
from functools import lru_cache

from pydantic_settings import BaseSettings


class GlobalConfig(BaseSettings):
    """全局常量配置（日期格式等）；运行时路由元数据见 router_registry.py。"""

    DATE_FORMAT: str = "%Y-%m-%d"
    TIME_FORMAT: str = "%H:%M:%S"
    DATETIME_FORMAT1: str = "%Y%m%d%H%M%S"
    DATETIME_FORMAT2: str = "%Y-%m-%d %H:%M:%S"


@lru_cache(maxsize=1)
def get_global_config() -> GlobalConfig:
    return GlobalConfig()


GLOBAL_CONFIG = get_global_config()
