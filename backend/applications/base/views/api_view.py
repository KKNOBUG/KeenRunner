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
from fastapi.params import Query
from tortoise.expressions import Q

from backend.applications.base.schemas.api_schema import ApiCreate, ApiUpdate
from backend.applications.base.services.api_crud import API_CRUD
from backend.core.response.base_response import (
    SuccessResponse, FailureResponse, DataAlreadyExistsResponse,
    NotFoundResponse, ParameterResponse,
)

api = APIRouter()


@api.post("/createApi", summary="Api-新增接口")
async def create_api(
        api_in: ApiCreate = Body()
):
    try:
        path: str = api_in.path
        method: str = api_in.method
        api_instance = await API_CRUD.get_by_path(path=path, method=method)
        if api_instance:
            return DataAlreadyExistsResponse(message=f"接口(path={path},method={method})已存在")

        new_api_instance = await API_CRUD.create_api(api_in=api_in)
        new_api_data = await new_api_instance.to_dict()
        return SuccessResponse(data=new_api_data)
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述:{e}")


@api.post("/deleteApi", summary="Api-删除一个接口")
async def delete_api(
        api_id: int = Query(..., description="接口ID")
):
    try:
        api_instance = await API_CRUD.delete_api(api_id)
        api_data = await api_instance.to_dict()
        return SuccessResponse(data=api_data)
    except Exception as e:
        return NotFoundResponse(message=f"接口(id={api_id})不存在")


@api.post("/updateApi", summary="Api-更新接口")
async def update_user(
        api_in: ApiUpdate = Body(..., description="用户信息")
):
    try:
        api_instance = await API_CRUD.update_api(api_in)
        api_data = await api_instance.to_dict()
        return SuccessResponse(data=api_data)
    except Exception as e:
        return NotFoundResponse(message=f"接口(id={api_in.id})不存在")


@api.post("/getApi", summary="Api-查询一个用户")
async def get_user(
        api_id: int = Query(None, description="用户ID"),
        path: str = Query(None, description="用户名称"),
):
    # 构建查询条件，用户ID或用户名称
    where: Dict[str, Union[str, int]] = {}
    if api_id:
        where["id"] = api_id
    elif path:
        where["path"] = path
    else:
        return ParameterResponse("参数id和path不可同时为空")

    api_instance = await API_CRUD.get(**where)
    if not api_instance:
        return NotFoundResponse(message="接口信息不存在")

    api_data: dict = await api_instance.to_dict(exclude_fields=["is_active"])
    return SuccessResponse(data=api_data)


@api.post("/getApis", summary="Api-查询多个接口")
async def get_apis(
        page: int = Query(1, description="页码"),
        page_size: int = Query(10, description="每页展示数量"),
        api_id: str = Query(None, description="接口ID"),
        path: str = Query(None, description="接口请求路径"),
        method: str = Query(None, description="接口请求方式"),
        summary: str = Query(None, description="接口中文别名"),
        tags: str = Query(None, description="接口所属标签"),
        is_active: Optional[bool] = Query(True, description="接口所属状态")
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
    if is_active:
        q &= Q(is_active=is_active)

    total, api_instances = await API_CRUD.list(
        page=page, page_size=page_size, search=q
    )
    data = [
        await obj.to_dict() for obj in api_instances
    ]
    return SuccessResponse(data={"total": total, "data": data})
