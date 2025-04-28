# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : runcode_view.py
@DateTime: 2025/2/23 12:08
"""
from fastapi import APIRouter

from backend.applications.toolbox.schemas.runcode_schema import CodeRequest
from backend.applications.toolbox.services.runcode import run_python_code
from backend.core.exceptions.base_exceptions import SyntaxException, MaxTimeoutException, ReqInvalidException
from backend.core.responses.http_response import (
    SuccessResponse,
    BadReqResponse,
    RequestTimeoutResponse,
    SyntaxErrorResponse,
    InternalErrorResponse
)

runcode = APIRouter()


@runcode.post("/python", summary="执行python代码")
async def run_code(request: CodeRequest):
    try:
        execution_result = await run_python_code(request.code)
        return SuccessResponse(
            data={
                "result": execution_result["result"],
                "error": execution_result["error"]
            }
        )
    except SyntaxException as ste:
        return SyntaxErrorResponse(message=ste.message)
    except MaxTimeoutException as mte:
        return RequestTimeoutResponse(message=mte.message)
    except ReqInvalidException as rile:
        return BadReqResponse(message=rile.message)
    except Exception as e:
        return InternalErrorResponse(data=str(e))
