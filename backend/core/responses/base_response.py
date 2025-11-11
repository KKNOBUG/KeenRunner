# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : base_response.py
@DateTime: 2025/1/16 16:14
"""
import json
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
    total: Optional[int] = None

    def __init__(self,
                 http_status_code: Optional[int] = None,
                 code: Optional[Code] = None,
                 status: Optional[Status] = None,
                 message: Optional[str] = None,
                 data: Optional[dict] = None,
                 total: Optional[int] = None, **kwargs):

        if http_status_code and isinstance(http_status_code, int):
            self.http_status_code = http_status_code

        if code and isinstance(code, Code):
            self.code = code.value

        if status and isinstance(status, Status):
            self.status = status.value

        if message and isinstance(message, str):
            status: bool = "错误代码" in message and "错误信息" in message
            self.message = json.loads(message)["错误信息"] if status else message
        elif message and isinstance(message, Message):
            self.message = message.value

        if data or isinstance(data, (int, str, list, dict)):
            self.data = data

        if total or isinstance(total, (int, float)):
            self.total = total

        resp = dict(
            code=self.code,
            status=self.status,
            message=self.message,
            data=data,
            total=total
        )

        super(BaseResponse, self).__init__(
            status_code=self.http_status_code,
            content=jsonable_encoder(resp),
            **kwargs
        )
