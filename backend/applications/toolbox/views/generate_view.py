# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : generate_view.py
@DateTime: 2025/2/28 14:43
"""
from typing import Any, Dict

from fastapi import APIRouter, Body

from backend.applications.toolbox.schemas.generate_schema import GenerateVirtualInfo
from backend.applications.toolbox.services.generate_service import generate_virtual_info
from backend.core.responses import SuccessResponse

generate = APIRouter()


@generate.post("/create_info", summary="新增虚拟信息", description="随机生成虚拟信息")
async def generate_info(
        generate_in: GenerateVirtualInfo = Body(..., description="虚拟信息生成条件"),
):
    """
    随机生成虚拟信息。

    :param generate_in: 虚拟信息生成入参
    :return: 统一响应，data 含人员、时间与随机标识三类生成结果
    """
    data: Dict[str, Any] = generate_virtual_info(generate_in=generate_in)
    return SuccessResponse(message="生成成功", data=data)
