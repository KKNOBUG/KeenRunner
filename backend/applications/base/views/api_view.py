# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : api_view.py
@DateTime: 2025/1/27 10:15
"""
from typing import Dict, Union

from fastapi import APIRouter, Body
from fastapi.params import Form
from tortoise.expressions import Q

from backend.applications.base.schemas.api_schema import ApiCreate, ApiUpdate, ApiSelect
from backend.applications.base.services.api_crud import API_CRUD
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException
from backend.core.response.http_response import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    NotFoundResponse,
    ParameterResponse,
)

api = APIRouter()


@api.post("/create", summary="新增接口信息")
async def create_api(
        api_in: ApiCreate = Body()
):
    try:
        instance = await API_CRUD.create_api(api_in=api_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述:{e}")


@api.post("/delete", summary="删除一个接口信息")
async def delete_api(
        api_id: int = Form(..., description="接口ID")
):
    try:
        instance = await API_CRUD.delete_api(api_id)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述:{e}")


@api.post("/update", summary="更新接口信息")
async def update_user(
        api_in: ApiUpdate = Body(..., description="接口信息")
):
    try:
        instance = await API_CRUD.update_api(api_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"更新失败，异常描述:{e}")


@api.post("/get", summary="查询一个接口信息")
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
        return ParameterResponse("参数[id]和[path]不可同时为空")

    instance = await API_CRUD.select(**where)
    if not instance:
        return NotFoundResponse(message=f"接口(id={api_id},path={path})信息不存在")

    data: dict = await instance.to_dict()
    return SuccessResponse(data=data)


@api.post("/search", summary="查询多个接口信息")
async def get_apis(
        api_in: ApiSelect = Body()
):
    page = api_in.page
    page_size = api_in.page_size
    page_order = api_in.page_order
    path = api_in.path
    method = api_in.method
    summary = api_in.summary
    tags = api_in.tags
    is_deleted = api_in.is_deleted
    created_user = api_in.created_user

    q = Q()
    if path:
        q &= Q(path__contains=path)
    if method:
        q &= Q(method__contains=method)
    if summary:
        q &= Q(summary__contains=summary)
    if tags:
        q &= Q(tags__contains=tags)
    if is_deleted is not None:
        q &= Q(is_deleted=is_deleted)
    if created_user:
        q &= Q(created_user__contains=created_user)

    total, instances = await API_CRUD.list(
        page=page, page_size=page_size, search=q, order=page_order
    )
    data = [
        await obj.to_dict() for obj in instances
    ]
    return SuccessResponse(data=data)
