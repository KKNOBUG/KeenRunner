# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : generate_view.py
@DateTime: 2025/2/28 14:43
"""
from typing import List

from fastapi import APIRouter, Body

from backend.applications.toolbox.schemas.generate_schema import GeneratePerson
from backend.core.response.http_response import SuccessResponse
from backend import GENERATE

generate = APIRouter()


@generate.post("/person", summary="生成虚拟人员信息")
async def generate_person(req_in: GeneratePerson = Body(...)):
    data: List[dict] = []
    number: int = req_in.number
    minAge: int = req_in.minAge
    maxAge: int = req_in.maxAge
    option: List[str] = req_in.option
    for i in range(number):
        info = GENERATE.generate_information(minAge=minAge, maxAge=maxAge, convert="capitalize")
        data.append({k: v for k, v in info.items() if k in option})

    return SuccessResponse(data=data)
