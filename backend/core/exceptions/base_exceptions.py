# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : base_exceptions.py
@DateTime: 2025/1/13 13:45
"""
import json

from backend.enums.base_error_enum import BaseErrorEnum


class BaseExceptions(Exception):

    def __init__(self, code: str = BaseErrorEnum.BASE999.code,
                 message: str = BaseErrorEnum.BASE999.value,
                 errenum: BaseErrorEnum = None) -> None:
        self.code = code
        self.message = message

        if errenum:
            self.code = self.code or errenum.code
            self.message = self.message or errenum.value

        self._error = json.dumps(
            {"错误代码": self.code, "错误信息": self.message}, ensure_ascii=False
        )

    def __str__(self):
        return self._error


class NotImplementedException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE100)
        kwargs.setdefault("code", BaseErrorEnum.BASE100.code)
        super().__init__(**kwargs)


class UndefinedConfigException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE101)
        kwargs.setdefault("code", BaseErrorEnum.BASE101.code)
        super().__init__(**kwargs)
