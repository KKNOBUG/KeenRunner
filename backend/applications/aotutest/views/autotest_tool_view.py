# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_tool_view
@DateTime: 2026/1/17 16:13
"""

from typing import List

from fastapi import APIRouter

from backend import LOGGER
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
)

autotest_tool = APIRouter()


@autotest_tool.get("/get", summary="API自动化测试-辅助函数查询")
async def get_func_info():
    try:
        func: List[str] = [
            "generate_country()",
            "generate_province()",
            "generate_city()",
            "generate_district()",
            "generate_address()",
            "generate_company()",
            "generate_email()",
            "generate_job()",
            "generate_name()",
            "generate_week_number()",
            "generate_week_name()",
            "generate_day()",
            "generate_am_or_pm()",
            "generate_uuid()",
            "generate_phone()",
            "generate_ident_card_number()",
            'generate_ident_card_birthday(ident_card_number="310224199508081212")',
            'generate_ident_card_gender(ident_card_number="310224199508081212")',
            'generate_string(length=1, digit=False, char=False, chinese=False")',
            'generate_global_serial_number(channel_no="300103")',
            'generate_information(min_age=18, max_age=60)',
            'generate_datetime(year=0, month=0, day=0, hour=0, minute=0, second=0, fmt=52, is_microsecond=False)',
        ]
        LOGGER.info(f"辅助函数查询成功")
        return SuccessResponse(message="查询成功", data=func, total=len(func))
    except Exception as e:
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")
