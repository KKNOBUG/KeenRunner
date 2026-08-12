# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_datagram_diff_view.py
@DateTime: 2026/8/11
"""
from fastapi import APIRouter

from backend.applications.aotutest.schemas.autotest_datagram_diff_schema import RepDiffRequest
from backend.applications.aotutest.services.autotest_runtime.datagram.message_diff import compare_messages
from backend.configure import LOGGER
from backend.core.responses import FailureResponse, SuccessResponse

rep_diff_router = APIRouter()


@rep_diff_router.post(
    "/compare",
    summary="报文比对",
    description="比对左右报文并返回对齐后的逐行差异结果",
)
async def compare_datagram(body: RepDiffRequest):
    """
    单组报文比对接口，供工具箱或前端调试页调用。

    :param body: 左右报文与顺序控制开关
    :return: SuccessResponse/FailureResponse
    """
    try:
        result = compare_messages(
            left_text=body.left_text,
            right_text=body.right_text,
            order_control=body.datagram_field_sorted,
        )
        return SuccessResponse(message="比对成功", data=result.model_dump(), total=1)
    except Exception as e:
        LOGGER.error(f"报文比对失败: {e}")
        return FailureResponse(message=f"报文比对失败, 错误描述: {e}")
