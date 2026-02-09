# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_tool_view
@DateTime: 2026/1/17 16:13
"""
import inspect
import traceback
from typing import Any, Dict, List

from fastapi import APIRouter

from backend import LOGGER
from backend.common.generate_utils import GenerateUtils
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
)

autotest_tool = APIRouter()


def _get_func_desc(attr_name: str) -> str:
    """从 GenerateUtils 获取属性/方法的 doc 作为简短说明，无则返回空字符串。"""
    if not hasattr(GenerateUtils, attr_name):
        return ""
    attr = getattr(GenerateUtils, attr_name)
    # 可能是 property，取 fget 的 doc
    if isinstance(attr, property) and attr.fget is not None:
        doc = inspect.getdoc(attr.fget)
    else:
        doc = inspect.getdoc(attr)
    if doc:
        first_line = doc.strip().split("\n")[0].strip()
        return first_line[:200] if len(first_line) > 200 else first_line
    return ""


# 公共函数列表：name 与 execute_func_string 解析格式一致
FUNC_LIST: List[Dict[str, Any]] = [
    {"name": "generate_country()", "desc": ""},
    {"name": "generate_province()", "desc": ""},
    {"name": "generate_city()", "desc": ""},
    {"name": "generate_district()", "desc": ""},
    {"name": "generate_address()", "desc": ""},
    {"name": "generate_company()", "desc": ""},
    {"name": "generate_email()", "desc": ""},
    {"name": "generate_job()", "desc": ""},
    {"name": "generate_name()", "desc": ""},
    {"name": "generate_week_number()", "desc": ""},
    {"name": "generate_week_name()", "desc": ""},
    {"name": "generate_day()", "desc": ""},
    {"name": "generate_am_or_pm()", "desc": ""},
    {"name": "generate_uuid()", "desc": ""},
    {"name": "generate_phone()", "desc": ""},
    {"name": "generate_ident_card_number()", "desc": ""},
    {"name": "generate_ident_card_number_condition(min_age=18, max_age=65)", "desc": ""},
    {"name": 'generate_ident_card_birthday(ident_card_number="310224199508081212")', "desc": ""},
    {"name": 'generate_ident_card_gender(ident_card_number="310224199508081212")', "desc": ""},
    {"name": "generate_string(length=6, digit=False, char=False, chinese=False)", "desc": ""},
    {"name": "generate_global_serial_number()", "desc": ""},
    {"name": "generate_information(minAge=18, maxAge=60)", "desc": ""},
    {"name": "generate_datetime(year=0, month=0, day=0, hour=0, minute=0, second=0, fmt=52, isMicrosecond=False)", "desc": ""},
]


def _build_func_list_with_desc() -> List[Dict[str, Any]]:
    """为 FUNC_LIST 中每项补全 desc（从 GenerateUtils 反射）。"""
    result: List[Dict[str, Any]] = []
    for item in FUNC_LIST:
        name = item["name"]
        func_name = name.split("(")[0].strip() if "(" in name else name
        desc = item.get("desc") or _get_func_desc(func_name)
        result.append({"name": name, "desc": desc})
    return result


@autotest_tool.get("/get", summary="API自动化测试-辅助函数查询")
async def get_func_info():
    try:
        func_list = _build_func_list_with_desc()
        LOGGER.info("辅助函数查询成功")
        return SuccessResponse(message="查询成功", data=func_list, total=len(func_list))
    except Exception as e:
        LOGGER.error(f"辅助函数查询失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")
