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


class SerializerException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE102)
        kwargs.setdefault("code", BaseErrorEnum.BASE102.code)
        super().__init__(**kwargs)


class MaxTimeoutException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE103)
        kwargs.setdefault("code", BaseErrorEnum.BASE103.code)
        super().__init__(**kwargs)


class ReadFileException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE104)
        kwargs.setdefault("code", BaseErrorEnum.BASE104.code)
        super().__init__(**kwargs)


class TypeRejectException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE105)
        kwargs.setdefault("code", BaseErrorEnum.BASE105.code)
        super().__init__(**kwargs)


class ParameterException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE400)
        kwargs.setdefault("code", BaseErrorEnum.BASE400.code)
        super().__init__(**kwargs)


class NotFoundException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE404)
        kwargs.setdefault("code", BaseErrorEnum.BASE404.code)
        super().__init__(**kwargs)


class ReqInvalidException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE500)
        kwargs.setdefault("code", BaseErrorEnum.BASE500.code)
        super().__init__(**kwargs)


class ResInvalidException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE502)
        kwargs.setdefault("code", BaseErrorEnum.BASE502.code)
        super().__init__(**kwargs)
