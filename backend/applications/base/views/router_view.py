# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : router_view.py
@DateTime: 2025/1/27 10:15
"""
import traceback

from fastapi import APIRouter, Body, Query, Depends
from starlette.requests import Request
from tortoise.expressions import Q

from backend.applications.base.dependencies import get_router_crud
from backend.applications.base.schemas.router_schema import RouterCreate, RouterUpdate, RouterSelect
from backend.applications.base.services.router_crud import RouterCrud
from backend.configure import LOGGER
from backend.core.exceptions import DataAlreadyExistsException, NotFoundException
from backend.core.responses import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    NotFoundResponse,
)

router = APIRouter()

@router.post("/create", summary="新增路由信息")
async def create_router(
        router_in: RouterCreate = Body(..., description="路由信息"),
        router_crud: RouterCrud = Depends(get_router_crud),
):
    """
    新增路由信息。

    :param router_in: 路由入参
    :param router_crud: 路由CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await router_crud.create_router(router_in=router_in)
        data = await instance.to_dict()
        LOGGER.info(f"新增路由成功, 结果明细: {data}")
        return SuccessResponse(message="新增成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增路由失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {e}")

@router.delete("/delete", summary="删除路由信息", description="根据id删除路由信息")
async def delete_router(
        router_id: int = Query(..., description="接口ID"),
        router_crud: RouterCrud = Depends(get_router_crud),
):
    """
    删除路由信息。

    :param router_id: 路由ID
    :param router_crud: 路由CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await router_crud.delete_router(router_id)
        data = await instance.to_dict()
        LOGGER.info(f"删除路由成功, 结果明细: {data}")
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"删除路由失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")

@router.post("/update", summary="更新路由信息", description="根据id更新路由信息")
async def update_router(
        router_in: RouterUpdate = Body(..., description="接口信息"),
        router_crud: RouterCrud = Depends(get_router_crud),
):
    """
    更新路由信息。

    :param router_in: 路由入参
    :param router_crud: 路由CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await router_crud.update_router(router_in)
        data = await instance.to_dict()
        LOGGER.info(f"更新路由成功, 结果明细: {data}")
        return SuccessResponse(message="更新成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"更新路由失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {e}")

@router.get("/get", summary="查询路由信息", description="根据id查询路由信息")
async def get_router(
        router_id: int = Query(..., description="接口ID"),
        router_crud: RouterCrud = Depends(get_router_crud),
):
    """
    查询路由信息。

    :param router_id: 路由ID
    :param router_crud: 路由CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await router_crud.get_or_none(id=router_id)
        if not instance:
            return NotFoundResponse(message=f"记录[id={router_id}]信息不存在")

        data: dict = await instance.to_dict()
        LOGGER.info(f"查询路由成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except Exception as e:
        LOGGER.error(f"查询路由失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")

@router.post("/search", summary="查询路由列表", description="根据条件分页查询路由列表信息(Body)")
async def search_routers(
        router_in: RouterSelect = Body(..., description="查询条件"),
        router_crud: RouterCrud = Depends(get_router_crud),
):
    """
    查询路由列表。

    :param router_in: 路由查询入参
    :param router_crud: 路由CRUD服务
    :return: 统一HTTP响应
    """
    try:
        page = router_in.page
        page_size = router_in.page_size
        order = router_in.order
        path = router_in.path
        method = router_in.method
        summary = router_in.summary
        tags = router_in.tags

        q = Q()
        if path:
            q &= Q(path__contains=path)
        if method:
            q &= Q(method__contains=method)
        if summary:
            q &= Q(summary__contains=summary)
        if tags:
            q &= Q(tags__contains=tags)

        total, instances = await router_crud.list(page=page, page_size=page_size, search=q, order=order)
        data = [await obj.to_dict() for obj in instances]
        LOGGER.info(f"查询路由列表成功, 数量: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception as e:
        LOGGER.error(f"查询路由列表失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")

@router.get("/list", summary="查询路由列表", description="根据条件分页查询路由列表信息(Query)")
async def list_routers(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        order: list = Query(default=["id"], description="排序字段"),
        path: str = Query(None, description="路由请求路径"),
        summary: str = Query(None, description="路由作用简介"),
        tags: str = Query(None, description="路由所属标签"),
        router_crud: RouterCrud = Depends(get_router_crud),
):
    """
    查询路由列表。

    :param page: 页码
    :param page_size: 每页条数
    :param order: 排序字段
    :param path: 路由请求路径
    :param summary: 路由作用简介
    :param tags: 路由所属标签
    :param router_crud: 路由CRUD服务
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if path:
            q &= Q(path__contains=path)
        if summary:
            q &= Q(summary__contains=summary)
        if tags:
            q &= Q(tags__contains=tags)
        total, router_objs = await router_crud.list(
            page=page, page_size=page_size, search=q, order=order
        )
        data = [await obj.to_dict() for obj in router_objs]
        LOGGER.info(f"查询路由列表成功, 数量: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception as e:
        LOGGER.error(f"查询路由列表失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")

@router.post("/refresh", summary="刷新路由列表", description="重新获取项目中所有的APIRouter信息进行数据库更新")
async def refresh_router(
        request: Request,
        router_crud: RouterCrud = Depends(get_router_crud),
):
    """
    刷新路由列表。

    :param request: HTTP 请求对象
    :param router_crud: 路由CRUD服务
    :return: 统一HTTP响应
    """
    try:
        app = request.app
        data = await router_crud.refresh_router(app=app)
        LOGGER.info(f"刷新路由列表成功, 数量: {len(data)}")
        return SuccessResponse(message="刷新成功", data=data, total=len(data))
    except Exception as e:
        LOGGER.error(f"刷新路由列表失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"刷新失败，异常描述: {e}")
