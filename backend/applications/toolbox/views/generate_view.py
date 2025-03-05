# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : generate_view.py
@DateTime: 2025/2/28 14:43
"""
from typing import List, Dict, Any

from fastapi import APIRouter, Body

from backend.applications.toolbox.schemas.generate_schema import GenerateVirtualInfo
from backend.core.response.http_response import SuccessResponse
from backend import GENERATE

generate = APIRouter()


@generate.post("/info", summary="随机生成虚拟信息")
async def generate_info(rq_in: GenerateVirtualInfo = Body(...)):
    data: Dict[str, Any] = {}
    number: int = rq_in.number
    minAge: int = rq_in.minAge
    maxAge: int = rq_in.maxAge
    personOption: List[str] = rq_in.personOption
    datetimeOption: List[str] = rq_in.datetimeOption
    randomOption: List[str] = rq_in.randomOption

    # 随机人员
    for x in range(number):
        info = GENERATE.generate_information(minAge=minAge, maxAge=maxAge, convert="capitalize")
        data.setdefault("person", []).append({k: v for k, v in info.items() if k in personOption})

    # 随机时间
    formats: Dict[int, str] = {
        11: "Y",
        12: "M",
        13: "D",
        14: "H",
        15: "M",
        16: "S",

        21: "YMD1",
        22: "YMD2",
        23: "YMD3",

        31: "HMS1",
        32: "HMS2",
        33: "HMS3",

        41: "YMDHMS1",
        42: "YMDHMS2",
        43: "YMDHMS3",

        51: "YMDHMSF1",
        52: "YMDHMSF2",
        53: "YMDHMSF3",
    }
    for y in datetimeOption:
        if y == "now":
            for key, value in formats.items():
                item = GENERATE.generate_datetime(fmt=key, isMicrosecond=key > 50)
                data.setdefault(y, {}).setdefault(value, item)
        elif y == "history":
            year = GENERATE.generate_random_number(-50, -10)
            month = GENERATE.generate_random_number(-12, -1)
            day = GENERATE.generate_random_number(-31, -1)
            hour = GENERATE.generate_random_number(-60, -1)
            minute = GENERATE.generate_random_number(-60, -1)
            second = GENERATE.generate_random_number(-60, -1)
            for key, value in formats.items():
                item = GENERATE.generate_datetime(
                    year=year, month=month, day=day,
                    hour=hour, minute=minute, second=second,
                    fmt=key, isMicrosecond=key > 50)
                data.setdefault(y, {}).setdefault(value, item)
        elif y == "future":
            year = GENERATE.generate_random_number(5, 50)
            month = GENERATE.generate_random_number(1, 12)
            day = GENERATE.generate_random_number(1, 31)
            hour = GENERATE.generate_random_number(1, 60)
            minute = GENERATE.generate_random_number(1, 60)
            second = GENERATE.generate_random_number(1, 60)
            for key, value in formats.items():
                item = GENERATE.generate_datetime(
                    year=year, month=month, day=day,
                    hour=hour, minute=minute, second=second,
                    fmt=key, isMicrosecond=key > 50)
                data.setdefault(y, {}).setdefault(value, item)

    # 随机数字
    for z in randomOption:
        if z == "uuid":
            data[z] = [GENERATE.generate_uuid for _ in range(number)]
        elif z == "timestamp":
            data[z] = [GENERATE.generate_timestamp for _ in range(number)]
        elif z == "global":
            data[z] = [GENERATE.generate_global_serial_number for _ in range(number)]
        elif z == "random":
            data[z] = [GENERATE.generate_string(length=GENERATE.generate_random_number(6, 30))]

    return SuccessResponse(data=data)
