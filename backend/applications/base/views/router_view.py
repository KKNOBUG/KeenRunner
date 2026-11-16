# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : router_view.py
@DateTime: 2025/1/27 10:15
"""
import traceback

from fastapi import APIRouter, Body, Query
from starlette.requests import Request

from backend.applications.base.dependencies import DependRouterServices
from backend.applications.base.schemas.router_schema import RouterCreate, RouterUpdate, RouterSelect
from backend.applications.base.services.router_crud import RouterCrud
from backend.configure import LOGGER
from backend.core.exceptions import DataAlreadyExistsException, DataBaseStorageException, NotFoundException, ParameterException
from backend.core.responses import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    DataBaseStorageResponse,
    NotFoundResponse,
    ParameterResponse,
)
from backend.services import DependSuperUser

router = APIRouter()


@router.post("/create", summary="新增路由", description="新增路由信息")
async def create_router(
        router_in: RouterCreate = Body(..., description="路由信息"),
        router_crud: RouterCrud = DependRouterServices,
):
    """
    新增路由。

    :param router_in: 路由入参
    :param router_crud: 路由 CRUD 服务
    :return: 统一响应，成功时 data 为新增后的路由信息，主键字段为 router_id，total 为 1
    """
    try:
        instance = await router_crud.create_router(router_in=router_in)
        data = await router_crud.serialize_router(instance)
        return SuccessResponse(message="新增成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法新增路由，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [path={router_in.path}, method={router_in.method}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@router.delete("/delete", summary="删除路由", description="根据id删除路由信息")
async def delete_router(
        router_id: int = Query(..., description="路由ID"),
        router_crud: RouterCrud = DependRouterServices,
):
    """
    根据 ID 删除路由。

    :param router_id: 路由 ID
    :param router_crud: 路由 CRUD 服务
    :return: 统一响应，成功时 data 为被删除的路由信息，主键字段为 router_id，total 为 1
    """
    try:
        instance = await router_crud.delete_router(router_id)
        data = await router_crud.serialize_router(instance)
        return SuccessResponse(message="删除成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法删除路由，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [router_id={router_id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@router.post("/update", summary="更新路由", description="根据id更新路由信息")
async def update_router(
        router_in: RouterUpdate = Body(..., description="路由信息"),
        router_crud: RouterCrud = DependRouterServices,
):
    """
    根据 ID 更新路由。

    :param router_in: 路由入参，id 指定待更新记录
    :param router_crud: 路由 CRUD 服务
    :return: 统一响应，成功时 data 为更新后的路由信息，主键字段为 router_id，total 为 1
    """
    try:
        instance = await router_crud.update_router(router_in)
        data = await router_crud.serialize_router(instance)
        return SuccessResponse(message="更新成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法更新路由，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [router_id={router_in.id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@router.get("/get", summary="查询路由", description="根据id查询路由信息")
async def get_router(
        router_id: int = Query(None, description="路由ID"),
        router_crud: RouterCrud = DependRouterServices,
):
    """
    根据 ID 查询单条路由。

    :param router_id: 路由 ID
    :param router_crud: 路由 CRUD 服务
    :return: 统一响应，成功时 data 为路由信息，主键字段为 router_id，total 为 1
    """
    try:
        instance = await router_crud.get_by_id(router_id=router_id, on_error=True)
        data = await router_crud.serialize_router(instance)
        return SuccessResponse(message="查询成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法查询路由，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [router_id={router_id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@router.post("/search", summary="查询路由列表(Body)", description="根据条件分页查询路由列表信息(Body)")
async def get_routers(
        router_in: RouterSelect = Body(..., description="查询条件"),
        router_crud: RouterCrud = DependRouterServices,
):
    """
    按条件分页查询路由列表（Body 入参）。

    :param router_in: 路由查询入参，method 为枚举字段仅支持等值匹配
    :param router_crud: 路由 CRUD 服务
    :return: 统一响应，成功时 data 为路由列表，主键字段为 router_id，total 为总条数
    """
    try:
        total, instances = await router_crud.select_routers(router_in=router_in)
        data = [await router_crud.serialize_router(obj) for obj in instances]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception:
        error_message: str = "暂时无法查询路由列表，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [page={router_in.page}, page_size={router_in.page_size}, path={router_in.path}, tags={router_in.tags}]\n"
            f"异常回溯: {traceback.format_exc()}"
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
        router_crud: RouterCrud = DependRouterServices,
):
    """
    按条件分页查询路由列表（Query 入参）。

    :param page: 页码
    :param page_size: 每页条数
    :param order: 排序字段
    :param path: 路由请求路径
    :param summary: 路由作用简介
    :param tags: 路由所属标签
    :param router_crud: 路由 CRUD 服务
    :return: 统一响应，成功时 data 为路由列表，主键字段为 router_id，total 为总条数
    """
    try:
        router_in = RouterSelect(
            page=page, page_size=page_size, order=order, path=path, summary=summary, tags=tags
        )
        total, router_objs = await router_crud.select_routers(router_in=router_in)
        data = [await router_crud.serialize_router(obj) for obj in router_objs]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception:
        error_message: str = "暂时无法查询路由列表，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [page={page}, page_size={page_size}, path={path}, tags={tags}]\n"
            f"异常回溯: {traceback.format_exc()}"
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
        router_crud: RouterCrud = DependRouterServices,
):
    """
    刷新路由列表（仅管理员可调用），按当前应用路由同步数据库并补绑内置角色权限。

    :param request: HTTP 请求对象，用于获取 FastAPI 应用实例
    :param router_crud: 路由 CRUD 服务
    :return: 统一响应，成功时 data 为同步后的全部路由列表，主键字段为 router_id，total 为其条数
    """
    try:
        routers = await router_crud.refresh_router(app=request.app)
        data = [await router_crud.serialize_router(obj) for obj in routers]
        return SuccessResponse(message="刷新成功", data=data, total=len(data))
    except Exception:
        error_message: str = "暂时无法刷新路由列表，请稍后重试"
        LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
        return FailureResponse(message=error_message)
