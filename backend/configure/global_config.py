# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : global_config.py
@DateTime: 2025/1/16 15:30
"""
from backend.core.decorators.block import singleton


@singleton
class GlobalConfig:
    ...


GLOBAL_CONFIG = GlobalConfig()
