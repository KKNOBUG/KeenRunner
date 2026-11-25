# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : security_view.py
@DateTime: 2026/11/25 10:00
"""
import traceback

from fastapi import APIRouter

from backend.configure import LOGGER
from backend.core.responses import FailureResponse, SuccessResponse
from backend.services.transport_crypto import get_public_key_pem

# 仅认证端点：公钥供所有登录用户加密环境配置密码，不做 RBAC 鉴权，也不能被角色绑定
security_self = APIRouter()


@security_self.post("/get_public_key", summary="查询传输加密公钥", description="返回环境配置密码传输加密使用的RSA公钥")
async def get_public_key():
    """
    查询传输加密公钥（PEM），前端用于加密环境配置密码。

    :return: 统一响应，成功时 data 为 {public_key_pem}
    """
    try:
        return SuccessResponse(message="查询公钥成功", data={"public_key_pem": get_public_key_pem()}, total=1)
    except Exception:
        error_message: str = "查询公钥失败，请稍后重试"
        LOGGER.error(f"{error_message}\n异常回溯: {traceback.format_exc()}")
        return FailureResponse(message=error_message)