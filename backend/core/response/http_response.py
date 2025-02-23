# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : http_response.py
@DateTime: 2025/2/1 21:43
"""
from typing import Optional, Union, List, Any, Dict

from backend.core.response.base_response import BaseResponse
from backend.enums.app_enum import Code, Status, Message

DataType = Optional[Union[int, str, List, Dict[str, Any]]]


class SuccessResponse(BaseResponse):
    code = Code.CODE200
    status = Status.SUCCESS
    message = Message.MESSAGE200
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(SuccessResponse, self).__init__(message=message, data=data, total=total)


class FailureResponse(BaseResponse):
    code = Code.CODE999
    status = Status.FAILURE
    message = Message.MESSAGE999
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(FailureResponse, self).__init__(message=message, data=data, total=total)


class BadReqResponse(BaseResponse):
    code = Code.CODE400
    status = Status.FAILURE
    message = "请求失败"
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(BadReqResponse, self).__init__(message=message, data=data, total=total)


class SyntaxErrorResponse(BaseResponse):
    code = Code.CODE999
    status = Status.FAILURE
    message = "语法错误"
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(SyntaxErrorResponse, self).__init__(message=message, data=data, total=total)


class ParameterResponse(BaseResponse):
    code = Code.CODE400
    status = Status.FAILURE
    message = Message.MESSAGE400
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(ParameterResponse, self).__init__(message=message, data=data, total=total)


class FileExtensionResponse(BaseResponse):
    code = Code.CODE400
    status = Status.FAILURE
    message = "文件扩展名不符合规范"
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(FileExtensionResponse, self).__init__(message=message, data=data, total=total)


class FileTooManyResponse(BaseResponse):
    code = Code.CODE400
    status = Status.FAILURE
    message = "文件数量过多或体积过大"
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(FileTooManyResponse, self).__init__(message=message, data=data, total=total)


class DataAlreadyExistsResponse(BaseResponse):
    code = Code.CODE400
    status = Status.FAILURE
    message = "数据或文件已存在"
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(DataAlreadyExistsResponse, self).__init__(message=message, data=data, total=total)


class UnauthorizedResponse(BaseResponse):
    code = Code.CODE401
    status = Status.FAILURE
    message = Message.MESSAGE401
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(UnauthorizedResponse, self).__init__(message=message, data=data, total=total)


class ForbiddenResponse(BaseResponse):
    code = Code.CODE403
    status = Status.FAILURE
    message = Message.MESSAGE403
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(ForbiddenResponse, self).__init__(message=message, data=data, total=total)


class NotFoundResponse(BaseResponse):
    code = Code.CODE404
    status = Status.FAILURE
    message = Message.MESSAGE404
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(NotFoundResponse, self).__init__(message=message, data=data, total=total)


class MethodNotAllowedResponse(BaseResponse):
    code = Code.CODE405
    status = Status.FAILURE
    message = Message.MESSAGE405
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(MethodNotAllowedResponse, self).__init__(message=message, data=data, total=total)


class RequestTimeoutResponse(BaseResponse):
    code = Code.CODE408
    status = Status.FAILURE
    message = Message.MESSAGE408
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(RequestTimeoutResponse, self).__init__(message=message, data=data, total=total)


class LimiterResponse(BaseResponse):
    code = Code.CODE429
    status = Status.FAILURE
    message = Message.MESSAGE429
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(LimiterResponse, self).__init__(message=message, data=data, total=total)


class InternalErrorResponse(BaseResponse):
    code = Code.CODE500
    status = Status.FAILURE
    message = Message.MESSAGE500
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(InternalErrorResponse, self).__init__(message=message, data=data, total=total)


class BadGatewayResponse(BaseResponse):
    code = Code.CODE502
    status = Status.FAILURE
    message = Message.MESSAGE502
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(BadGatewayResponse, self).__init__(message=message, data=data, total=total)


class GatewayTimeoutResponse(BaseResponse):
    code = Code.CODE504
    status = Status.FAILURE
    message = Message.MESSAGE504
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(GatewayTimeoutResponse, self).__init__(message=message, data=data, total=total)
