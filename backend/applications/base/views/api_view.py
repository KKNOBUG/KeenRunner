# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : api_view.py
@DateTime: 2025/1/27 10:15
"""
from fastapi import APIRouter, Body, Query
from starlette.requests import Request
from tortoise.expressions import Q

from backend.applications.base.schemas.api_schema import ApiCreate, ApiUpdate, ApiSelect
from backend.applications.base.services.api_crud import API_CRUD
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException
from backend.core.response.http_response import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    NotFoundResponse,
)

api = APIRouter()


@api.post("/create", summary="新增API信息")
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


@api.delete("/delete", summary="删除API信息", description="根据id删除API信息")
async def delete_api(
        api_id: int = Query(..., description="接口ID")
):
    try:
        instance = await API_CRUD.delete_api(api_id)
        return SuccessResponse(data=instance)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述:{e}")


@api.post("/update", summary="更新API信息", description="根据id更新API信息")
async def update_user(
        api_in: ApiUpdate = Body(..., description="接口信息")
):
    try:
        instance = await API_CRUD.update_api(api_in)
        return SuccessResponse(data=instance)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"更新失败，异常描述:{e}")


@api.get("/get", summary="查询API信息", description="根据id查询API信息")
async def get_user(
        api_id: int = Query(None, description="接口ID"),
):
    instance = await API_CRUD.query(id=api_id)
    if not instance:
        return NotFoundResponse(message=f"接口(id={api_id})信息不存在")

    data: dict = await instance.to_dict()
    return SuccessResponse(data=data)


@api.post("/search", summary="查询API列表", description="支持分页按条件查询API列表信息（Body）")
async def get_apis(
        api_in: ApiSelect = Body()
):
    page = api_in.page
    page_size = api_in.page_size
    order = api_in.order
    id = api_in.id
    path = api_in.path
    method = api_in.method
    summary = api_in.summary
    tags = api_in.tags

    q = Q()
    if id:
        q &= Q(id__contains=id)
    if path:
        q &= Q(path__contains=path)
    if method:
        q &= Q(method__contains=method)
    if summary:
        q &= Q(summary__contains=summary)
    if tags:
        q &= Q(tags__contains=tags)

    total, instances = await API_CRUD.list(
        page=page, page_size=page_size, search=q, order=order
    )
    data = [
        await obj.to_dict() for obj in instances
    ]
    return SuccessResponse(data=data)


@api.get("/list", summary="查询API列表", description="支持分页按条件查询API列表信息（Query）")
async def list_api(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        order: list = Query(default=["id"], description="排序字段"),
        path: str = Query(None, description="API路径"),
        summary: str = Query(None, description="API简介"),
        tags: str = Query(None, description="API模块"),
):
    q = Q()
    if path:
        q &= Q(path__contains=path)
    if summary:
        q &= Q(summary__contains=summary)
    if tags:
        q &= Q(tags__contains=tags)
    total, api_objs = await API_CRUD.list(
        page=page, page_size=page_size, search=q, order=order
    )
    data = [await obj.to_dict() for obj in api_objs]
    return SuccessResponse(data=data, total=total)


@api.post("/refresh", summary="刷新API列表", description="重新获取项目中所有的APIRouter信息进行数据库更新")
async def refresh_api(request: Request):
    app = request.app
    data = await API_CRUD.refresh_api(app=app)
    return SuccessResponse(data=data)
