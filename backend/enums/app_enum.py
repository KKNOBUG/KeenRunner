# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : app_enum.py
@DateTime: 2025/1/16 16:15
"""
from .base_enum_cls import StringEnum
from .base_error_enum import BaseErrorEnum


class Code(StringEnum):
    CODE200 = BaseErrorEnum.BASE000.code
    CODE999 = BaseErrorEnum.BASE999.code

    CODE400 = BaseErrorEnum.BASE400.code
    CODE401 = BaseErrorEnum.BASE401.code
    CODE403 = BaseErrorEnum.BASE403.code
    CODE404 = BaseErrorEnum.BASE404.code
    CODE405 = BaseErrorEnum.BASE405.code
    CODE429 = BaseErrorEnum.BASE429.code

    CODE500 = BaseErrorEnum.BASE500.code
    CODE502 = BaseErrorEnum.BASE502.code
    CODE504 = BaseErrorEnum.BASE504.code


class Message(StringEnum):
    MESSAGE200 = BaseErrorEnum.BASE000.value
    MESSAGE999 = BaseErrorEnum.BASE999.value

    MESSAGE400 = BaseErrorEnum.BASE400.value
    MESSAGE401 = BaseErrorEnum.BASE401.value
    MESSAGE403 = BaseErrorEnum.BASE403.value
    MESSAGE404 = BaseErrorEnum.BASE404.value
    MESSAGE405 = BaseErrorEnum.BASE405.value
    MESSAGE429 = BaseErrorEnum.BASE429.value

    MESSAGE500 = BaseErrorEnum.BASE500.value
    MESSAGE502 = BaseErrorEnum.BASE502.value
    MESSAGE504 = BaseErrorEnum.BASE504.value


class Status(StringEnum):
    SUCCESS = 'success'
    FAILURE = 'failure'
