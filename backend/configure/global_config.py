# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : global_config.py
@DateTime: 2025/1/16 15:30
"""
import datetime
from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings


class GlobalConfig(BaseSettings):
    """全局常量配置（日期格式等）。"""

    DATE_FORMAT: str = "%Y-%m-%d"
    TIME_FORMAT: str = "%H:%M:%S"
    DATETIME_FORMAT1: str = "%Y%m%d%H%M%S"
    DATETIME_FORMAT2: str = "%Y-%m-%d %H:%M:%S"

    @classmethod
    def format_datetime(cls, value: Any, formatter: str) -> Any:
        """
        将时间对象格式化为指定格式的字符串，非时间值原样返回。

        :param value: 字段值
        :param formatter: 格式值
        :return: 格式化结果
        """
        if isinstance(value, datetime.datetime):
            return value.strftime(format=formatter)
        return value


@lru_cache(maxsize=1)
def get_global_config() -> GlobalConfig:
    return GlobalConfig()


GLOBAL_CONFIG = get_global_config()
