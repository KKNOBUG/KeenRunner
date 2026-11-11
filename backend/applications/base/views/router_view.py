# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
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
from backend.core.exceptions import DataAlreadyExistsException, DataBaseStorageException, NotFoundException
from backend.core.responses import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    DataBaseStorageResponse,
    NotFoundResponse,
)
from backend.services import DependSuperUser

router = APIRouter()


@router.post("/create", summary="新增路由", description="新增路由信息")
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
        data = await instance.to_dict(replace_fields={"id": "router_id"})
        return SuccessResponse(message="新增成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception:
        error_message: str = "新增路由失败，暂时无法完成创建，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [path={router_in.path}, method={router_in.method}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@router.delete("/delete", summary="删除路由", description="根据id删除路由信息")
async def delete_router(
        router_id: int = Query(..., description="路由ID"),
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
        data = await instance.to_dict(replace_fields={"id": "router_id"})
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "删除路由失败，暂时无法完成删除，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [router_id={router_id}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@router.post("/update", summary="更新路由", description="根据id更新路由信息")
async def update_router(
        router_in: RouterUpdate = Body(..., description="路由信息"),
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
        data = await instance.to_dict(replace_fields={"id": "router_id"})
        return SuccessResponse(message="更新成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "更新路由失败，暂时无法完成更新，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [router_id={router_in.id}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@router.get("/get", summary="查询路由", description="根据id查询路由信息")
async def get_router(
        router_id: int = Query(None, description="路由ID"),
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
            return NotFoundResponse(message=f"未找到 id 为 {router_id} 的路由，请刷新后重试")

        data: dict = await instance.to_dict(replace_fields={"id": "router_id"})
        return SuccessResponse(message="查询成功", data=data, total=1)
    except Exception:
        error_message: str = "查询路由信息失败，暂时无法获取路由数据，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [router_id={router_id}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@router.post("/search", summary="查询路由列表(Body)", description="根据条件分页查询路由列表信息(Body)")
async def get_routers(
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
        # method为CharEnumField(HTTPMethod)，仅支持等值匹配，不支持contains
        if method:
            method_value = method.value if hasattr(method, "value") else method
            q &= Q(method=method_value)
        if summary:
            q &= Q(summary__contains=summary)
        if tags:
            q &= Q(tags__contains=tags)

        total, instances = await router_crud.list(page=page, page_size=page_size, search=q, order=order)
        data = [await obj.to_dict(replace_fields={"id": "router_id"}) for obj in instances]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception:
        error_message: str = "查询路由列表失败，暂时无法获取路由数据，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [page={router_in.page}, page_size={router_in.page_size}, "
            f"path={router_in.path}, tags={router_in.tags}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@router.get("/list", summary="查询路由列表(Query)", description="根据条件分页查询路由列表信息(Query)")
async def list_router(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, le=99999, description="每页数量"),
        order: list = Query(default_factory=lambda: ["id"], description="排序字段"),
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
        data = [await obj.to_dict(replace_fields={"id": "router_id"}) for obj in router_objs]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception:
        error_message: str = "查询路由列表失败，暂时无法获取路由数据，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [page={page}, page_size={page_size}, path={path}, tags={tags}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@router.post(
    "/refresh",
    summary="刷新路由列表",
    description="重新获取项目中所有的APIRouter信息进行数据库更新",
    dependencies=[DependSuperUser],
)
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
        return SuccessResponse(message="刷新成功", data=data, total=len(data))
    except Exception:
        error_message: str = "刷新路由列表失败，暂时无法同步接口数据，请稍后重试"
        LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
        return FailureResponse(message=error_message)
