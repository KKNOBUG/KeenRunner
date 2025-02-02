# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : api_view.py
@DateTime: 2025/1/27 10:15
"""
from typing import Dict, Union, Optional

from fastapi import APIRouter, Body
from fastapi.params import Form
from tortoise.expressions import Q

from backend.applications.base.schemas.api_schema import ApiCreate, ApiUpdate
from backend.applications.base.services.api_crud import API_CRUD
from backend.core.response.http_response import (
    SuccessResponse, FailureResponse, DataAlreadyExistsResponse,
    NotFoundResponse, ParameterResponse,
)

api = APIRouter()


@api.post("/createApi", summary="Base-新增接口信息")
async def create_api(
        api_in: ApiCreate = Body()
):
    try:
        path: str = api_in.path
        method: str = api_in.method
        instance = await API_CRUD.get_by_path(path=path, method=method)
        if instance:
            return DataAlreadyExistsResponse(message=f"接口(path={path},method={method})已存在")

        new_instance = await API_CRUD.create_api(api_in=api_in)
        data = await new_instance.to_dict()
        return SuccessResponse(data=data)
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述:{e}")


@api.post("/deleteApi", summary="Base-删除一个接口信息")
async def delete_api(
        api_id: int = Form(..., description="接口ID")
):
    try:
        instance = await API_CRUD.delete_api(api_id)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except Exception as e:
        return NotFoundResponse(message=f"接口(id={api_id})不存在")


@api.post("/updateApi", summary="Base-更新接口信息")
async def update_user(
        api_in: ApiUpdate = Body(..., description="接口信息")
):
    try:
        instance = await API_CRUD.update_api(api_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except Exception as e:
        return NotFoundResponse(message=f"接口(id={api_in.id})不存在")


@api.post("/getApi", summary="Base-查询一个接口信息")
async def get_user(
        api_id: int = Form(None, description="接口ID"),
        path: str = Form(None, description="接口路径"),
):
    # 构建查询条件，用户ID或用户名称
    where: Dict[str, Union[str, int]] = {}
    if api_id:
        where["id"] = api_id
    elif path:
        where["path"] = path
    else:
        return ParameterResponse("参数id和path不可同时为空")

    instance = await API_CRUD.get(**where)
    if not instance:
        return NotFoundResponse(message="接口信息不存在")

    data: dict = await instance.to_dict(exclude_fields=["is_active"])
    return SuccessResponse(data=data)


@api.post("/getApis", summary="Base-查询多个接口信息")
async def get_apis(
        page: int = Form(1, description="页码"),
        page_size: int = Form(10, description="每页展示数量"),
        api_id: str = Form(None, description="接口ID"),
        path: str = Form(None, description="接口请求路径"),
        method: str = Form(None, description="接口请求方式"),
        summary: str = Form(None, description="接口中文别名"),
        tags: str = Form(None, description="接口所属标签"),
        is_active: Optional[bool] = Form(True, description="接口所属状态")
):
    q = Q()
    if api_id:
        q &= Q(id__contains=api_id)
    if path:
        q &= Q(path__contains=path)
    if method:
        q &= Q(method__contains=method)
    if summary:
        q &= Q(summary__contains=summary)
    if tags:
        q &= Q(tags__contains=tags)

    q &= Q(is_active=is_active)

    total, instances = await API_CRUD.list(
        page=page, page_size=page_size, search=q
    )
    data = [
        await obj.to_dict() for obj in instances
    ]
    return SuccessResponse(data=data)
