# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : base_response.py
@DateTime: 2025/1/16 16:14
"""
from typing import Optional, Union, List, Any, Dict

from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse

from backend.enums.app_enum import Code, Status, Message


class BaseResponse(JSONResponse):
    http_status_code = 200
    code: Code = Code.CODE200
    status: Status = Status.SUCCESS
    message: Optional[str] = None
    data: Optional[Union[str, List, Dict[str, Any]]] = None

    def __init__(self,
                 http_status_code: Optional[int] = None,
                 code: Optional[Code] = None,
                 status: Optional[Status] = None,
                 message: Optional[str] = None,
                 data: Optional[dict] = None, **kwargs):

        if http_status_code and isinstance(http_status_code, int):
            self.http_status_code = http_status_code

        if code and isinstance(code, Code):
            self.code = code.value

        if status and isinstance(status, Status):
            self.status = status.value

        if message and isinstance(message, str):
            self.message = message
        elif message and isinstance(message, Message):
            self.message = message.value

        if data and isinstance(data, (int, str, list, dict)):
            self.data = data

        resp = dict(
            code=self.code,
            status=self.status,
            message=self.message,
            data=self.data,
        )
        super(BaseResponse, self).__init__(
            status_code=self.http_status_code,
            content=jsonable_encoder(resp),
            **kwargs
        )


class SuccessResponse(BaseResponse):
    code = Code.CODE200
    status = Status.SUCCESS
    message = Message.MESSAGE200
    data = {}

    def __init__(self, message: Optional[str] = None, data: Optional[Union[int, str, List, Dict[str, Any]]] = None):
        super(SuccessResponse, self).__init__(message=message, data=data)


class FailureResponse(BaseResponse):
    code = Code.CODE999
    status = Status.FAILURE
    message = Message.MESSAGE999
    data = {}

    def __init__(self, message: Optional[str] = None, data: Optional[Union[int, str, List, Dict[str, Any]]] = None):
        super(FailureResponse, self).__init__(message=message, data=data)


class BadReqResponse(BaseResponse):
    code = Code.CODE400
    status = Status.FAILURE
    message = "请求失败"
    data = {}

    def __init__(self, message: Optional[str] = None, data: Optional[Union[int, str, List, Dict[str, Any]]] = None):
        super(BadReqResponse, self).__init__(message=message, data=data)


class ParameterResponse(BaseResponse):
    code = Code.CODE400
    status = Status.FAILURE
    message = Message.MESSAGE400
    data = {}

    def __init__(self, message: Optional[str] = None, data: Optional[Union[int, str, List, Dict[str, Any]]] = None):
        super(ParameterResponse, self).__init__(message=message, data=data)


class FileExtensionResponse(BaseResponse):
    code = Code.CODE400
    status = Status.FAILURE
    message = "文件扩展名不符合规范"
    data = {}

    def __init__(self, message: Optional[str] = None, data: Optional[Union[int, str, List, Dict[str, Any]]] = None):
        super(FileExtensionResponse, self).__init__(message=message, data=data)


class FileTooManyResponse(BaseResponse):
    code = Code.CODE400
    status = Status.FAILURE
    message = "文件数量过多或体积过大"
    data = {}

    def __init__(self, message: Optional[str] = None, data: Optional[Union[int, str, List, Dict[str, Any]]] = None):
        super(FileTooManyResponse, self).__init__(message=message, data=data)


class UnauthorizedResponse(BaseResponse):
    code = Code.CODE401
    status = Status.FAILURE
    message = Message.MESSAGE401
    data = {}

    def __init__(self, message: Optional[str] = None, data: Optional[Union[int, str, List, Dict[str, Any]]] = None):
        super(UnauthorizedResponse, self).__init__(message=message, data=data)


class ForbiddenResponse(BaseResponse):
    code = Code.CODE403
    status = Status.FAILURE
    message = Message.MESSAGE403
    data = {}

    def __init__(self, message: Optional[str] = None, data: Optional[Union[int, str, List, Dict[str, Any]]] = None):
        super(ForbiddenResponse, self).__init__(message=message, data=data)


class NotFoundResponse(BaseResponse):
    code = Code.CODE404
    status = Status.FAILURE
    message = Message.MESSAGE404
    data = {}

    def __init__(self, message: Optional[str] = None, data: Optional[Union[int, str, List, Dict[str, Any]]] = None):
        super(NotFoundResponse, self).__init__(message=message, data=data)


class MethodNotAllowedResponse(BaseResponse):
    code = Code.CODE405
    status = Status.FAILURE
    message = Message.MESSAGE405
    data = {}

    def __init__(self, message: Optional[str] = None, data: Optional[Union[int, str, List, Dict[str, Any]]] = None):
        super(MethodNotAllowedResponse, self).__init__(message=message, data=data)


class RequestTimeoutResponse(BaseResponse):
    code = Code.CODE408
    status = Status.FAILURE
    message = Message.MESSAGE408
    data = {}

    def __init__(self, message: Optional[str] = None, data: Optional[Union[int, str, List, Dict[str, Any]]] = None):
        super(RequestTimeoutResponse, self).__init__(message=message, data=data)


class LimiterResponse(BaseResponse):
    code = Code.CODE429
    status = Status.FAILURE
    message = Message.MESSAGE429
    data = {}

    def __init__(self, message: Optional[str] = None, data: Optional[Union[int, str, List, Dict[str, Any]]] = None):
        super(LimiterResponse, self).__init__(message=message, data=data)


class InternalErrorResponse(BaseResponse):
    code = Code.CODE500
    status = Status.FAILURE
    message = Message.MESSAGE500
    data = {}

    def __init__(self, message: Optional[str] = None, data: Optional[Union[int, str, List, Dict[str, Any]]] = None):
        super(InternalErrorResponse, self).__init__(message=message, data=data)


class BadGatewayResponse(BaseResponse):
    code = Code.CODE502
    status = Status.FAILURE
    message = Message.MESSAGE502
    data = {}

    def __init__(self, message: Optional[str] = None, data: Optional[Union[int, str, List, Dict[str, Any]]] = None):
        super(BadGatewayResponse, self).__init__(message=message, data=data)


class GatewayTimeoutResponse(BaseResponse):
    code = Code.CODE504
    status = Status.FAILURE
    message = Message.MESSAGE504
    data = {}

    def __init__(self, message: Optional[str] = None, data: Optional[Union[int, str, List, Dict[str, Any]]] = None):
        super(GatewayTimeoutResponse, self).__init__(message=message, data=data)
