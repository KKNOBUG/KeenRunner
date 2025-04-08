# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : file_size_enum.py
@DateTime: 2025/4/7 22:05
"""
from backend.enums.base_enum_cls import StringEnum


class FileSizeEum(StringEnum):
    """
    文件的体积限制枚举值
    """
    TINY = "tiny"
    MICRO = "micro"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    HUGE = "huge"
