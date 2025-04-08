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
            {"code": self.code, "message": self.message}, ensure_ascii=False
        )

    def __str__(self):
        return self._error


class ImportedException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE100)
        kwargs.setdefault("code", BaseErrorEnum.BASE100.code)
        super().__init__(**kwargs)


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


class UploadFileException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE104)
        kwargs.setdefault("code", BaseErrorEnum.BASE104.code)
        super().__init__(**kwargs)


class DownloadFileException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE105)
        kwargs.setdefault("code", BaseErrorEnum.BASE105.code)
        super().__init__(**kwargs)


class TypeRejectException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE106)
        kwargs.setdefault("code", BaseErrorEnum.BASE106.code)
        super().__init__(**kwargs)


class FileExtensionException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE107)
        kwargs.setdefault("code", BaseErrorEnum.BASE107.code)
        super().__init__(**kwargs)


class FileTooManyException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE108)
        kwargs.setdefault("code", BaseErrorEnum.BASE108.code)
        super().__init__(**kwargs)


class FileInvalidException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE109)
        kwargs.setdefault("code", BaseErrorEnum.BASE109.code)
        super().__init__(**kwargs)


class DataNotStandardizedException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE110)
        kwargs.setdefault("code", BaseErrorEnum.BASE110.code)
        super().__init__(**kwargs)


class DataBaseStorageException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE300)
        kwargs.setdefault("code", BaseErrorEnum.BASE300.code)
        super().__init__(**kwargs)


class DataAlreadyExistsException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE301)
        kwargs.setdefault("code", BaseErrorEnum.BASE301.code)
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


class SyntaxException(BaseExceptions):
    def __init__(self, **kwargs):
        kwargs.setdefault("errenum", BaseErrorEnum.BASE999)
        kwargs.setdefault("code", BaseErrorEnum.BASE999.code)
        super().__init__(**kwargs)
