# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : role_view.py
@DateTime: 2025/2/19 23:11
"""
from typing import Dict, Union

from fastapi import APIRouter, Body
from fastapi.params import Form, Query
from starlette.requests import Request
from tortoise.expressions import Q

from backend.applications.base.schemas.api_schema import ApiCreate, ApiUpdate, ApiSelect
from backend.applications.base.services.api_crud import API_CRUD
from backend.applications.base.services.role_crud import ROLE_CRUD
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException
from backend.core.response.http_response import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    NotFoundResponse,
    ParameterResponse,
)

role = APIRouter()


@role.get("/list", summary="查看角色列表")
async def list_role(
        page_num: int = Query(default=1, description="页码"),
        page_size: int = Query(default=10, description="每页数量"),
        role_name: str = Query(default="", description="角色名称，用于查询"),
):
    q = Q()
    if role_name:
        q = Q(name__contains=role_name)
    total, role_objs = await ROLE_CRUD.list(page=page_num, page_size=page_size, search=q)
    data = [await obj.to_dict() for obj in role_objs]
    return SuccessResponse(data=data, total=total)
