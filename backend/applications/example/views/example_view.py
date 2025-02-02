# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : example_view.py
@DateTime: 2025/1/17 21:51
"""
from fastapi import APIRouter

from backend.core.response.http_response import (
    FailureResponse, SuccessResponse
)

example = APIRouter()

data: list = [
    {
        "id": 1,
        "name": "张三",
        "age": 18,
        "gender": "男",
        "phone": "15600001234",
        "address": "上海市浦东新区"
    },
    {
        "id": 2,
        "name": "李四",
        "age": 19,
        "gender": "女",
        "phone": "16600001234",
        "address": "上海市黄浦区"
    },
    {
        "id": 3,
        "name": "王五",
        "age": 20,
        "gender": "女",
        "phone": "18800001234",
        "address": "上海市静安区"
    }
]


@example.get("/{pk}", summary="示例-单个查询")
async def get_example(pk: int):
    if not (0 < pk < 4):
        return FailureResponse()
    return SuccessResponse(data=[d for d in data if d["id"] == pk][0])


@example.post("/list", summary="示例-查询列表")
async def get_example_list():
    return SuccessResponse(data=data)
