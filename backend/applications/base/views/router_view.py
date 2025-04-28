# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : router_view.py
@DateTime: 2025/1/27 10:15
"""
from fastapi import APIRouter, Body, Query
from starlette.requests import Request
from tortoise.expressions import Q

from backend.applications.base.schemas.router_schema import RouterCreate, RouterUpdate, RouterSelect
from backend.applications.base.services.router_crud import ROUTER_CRUD
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    NotFoundResponse,
)

router = APIRouter()


@router.post("/create", summary="新增路由信息")
async def create_router(
        router_in: RouterCreate = Body()
):
    try:
        instance = await ROUTER_CRUD.create_router(router_in=router_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述:{e}")


@router.delete("/delete", summary="删除路由信息", description="根据id删除路由信息")
async def delete_router(
        router_id: int = Query(..., description="接口ID")
):
    try:
        instance = await ROUTER_CRUD.delete_router(router_id)
        return SuccessResponse(data=instance)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述:{e}")


@router.post("/update", summary="更新路由信息", description="根据id更新路由信息")
async def update_user(
        router_in: RouterUpdate = Body(..., description="接口信息")
):
    try:
        instance = await ROUTER_CRUD.update_router(router_in)
        return SuccessResponse(data=instance)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"更新失败，异常描述:{e}")


@router.get("/get", summary="查询路由信息", description="根据id查询路由信息")
async def get_user(
        router_id: int = Query(None, description="接口ID"),
):
    instance = await ROUTER_CRUD.query(id=router_id)
    if not instance:
        return NotFoundResponse(message=f"接口(id={router_id})信息不存在")

    data: dict = await instance.to_dict()
    return SuccessResponse(data=data)


@router.post("/search", summary="查询路由列表", description="支持分页按条件查询路由列表信息（Body）")
async def get_routers(
        router_in: RouterSelect = Body()
):
    page = router_in.page
    page_size = router_in.page_size
    order = router_in.order
    id = router_in.id
    path = router_in.path
    method = router_in.method
    summary = router_in.summary
    tags = router_in.tags

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

    total, instances = await ROUTER_CRUD.list(
        page=page, page_size=page_size, search=q, order=order
    )
    data = [
        await obj.to_dict() for obj in instances
    ]
    return SuccessResponse(data=data)


@router.get("/list", summary="查询路由列表", description="支持分页按条件查询路由列表信息（Query）")
async def list_router(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        order: list = Query(default=["id"], description="排序字段"),
        path: str = Query(None, description="路由请求路径"),
        summary: str = Query(None, description="路由作用简介"),
        tags: str = Query(None, description="路由所属标签"),
):
    q = Q()
    if path:
        q &= Q(path__contains=path)
    if summary:
        q &= Q(summary__contains=summary)
    if tags:
        q &= Q(tags__contains=tags)
    total, router_objs = await ROUTER_CRUD.list(
        page=page, page_size=page_size, search=q, order=order
    )
    data = [await obj.to_dict() for obj in router_objs]
    return SuccessResponse(data=data, total=total)


@router.post("/refresh", summary="刷新路由列表", description="重新获取项目中所有的APIRouter信息进行数据库更新")
async def refresh_router(request: Request):
    app = request.app
    data = await ROUTER_CRUD.refresh_router(app=app)
    return SuccessResponse(data=data)
