# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : env_view.py
@DateTime: 2025/4/2 20:07
"""

from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend.applications.program.schemas.env_schema import (
    EnvCreate, EnvUpdate, EnvSelect
)
from backend.applications.program.services.env_crud import ENV_CRUD
from backend.core.exceptions.base_exceptions import (
    DataAlreadyExistsException,
    NotFoundException
)
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    NotFoundResponse,
)

env = APIRouter()


@env.post("/create", summary="新增环境信息")
async def create_env(
        env_in: EnvCreate = Body(...)
):
    try:
        instance = await ENV_CRUD.create_env(env_in=env_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述:{e}")


@env.delete("/delete", summary="删除环境信息", description="根据id删除环境信息")
async def delete_env(
        env_id: int = Query(..., description="环境ID"),
):
    try:
        instance = await ENV_CRUD.delete_env(env_id=env_id)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述:{e}")


@env.post("/update", summary="更新环境信息", description="根据id更新环境信息")
async def update_env(
        env_in: EnvUpdate = Body(..., description="项目信息")
):
    try:
        instance = await ENV_CRUD.update_env(env_in=env_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"更新失败，异常描述:{e}")


@env.get("/get", summary="查询环境信息", description="根据id查询环境信息")
async def get_env(
        env_id: int = Query(..., description="环境ID"),
):
    instance = await ENV_CRUD.query(id=env_id)
    if not instance:
        return NotFoundResponse(message=f"环境(id={env_id})信息不存在")

    data: dict = await instance.to_dict()
    return SuccessResponse(data=data)


@env.get("/list", summary="查询环境列表", description="支持分页按条件查询环境列表信息（Body）")
async def list_env(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        order: list = Query(default=["id"], description="排序字段"),
        project_id: int = Query(default=None, description="应用ID"),
        name: str = Query(default=None, description="环境名称"),
        host: str = Query(default=None, description="环境地址"),
        port: int = Query(default=None, description="环境端口"),
):
    q = Q()
    if project_id:
        q &= Q(project_id=project_id)
    if name:
        q &= Q(name__contains=name)
    if host:
        q &= Q(host__contain=host)
    if port:
        q &= Q(port__contain=port)

    total, instances = await ENV_CRUD.list(
        page=page, page_size=page_size, search=q, order=order, related=["project"]
    )
    data = [
        await obj.to_dict(
            fk=True,
            fk_include_fields=["code", "name"]
        ) for obj in instances
    ]
    return SuccessResponse(data=data)
