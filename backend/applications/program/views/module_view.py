# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : module_view.py
@DateTime: 2025/4/5 13:14
"""

from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend.applications.program.schemas.module_schema import (
    ModuleCreate, ModuleUpdate, ModuleSelect
)
from backend.applications.program.services.module_crud import MODULE_CRUD
from backend.applications.user.services.user_crud import USER_CRUD
from backend.core.exceptions.base_exceptions import (
    DataAlreadyExistsException,
    NotFoundException
)
from backend.core.response.http_response import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    NotFoundResponse,
)

module = APIRouter()


@module.post("/create", summary="新增模块信息")
async def create_module(
        module_in: ModuleCreate = Body(...)
):
    try:
        instance = await MODULE_CRUD.create_module(module_in=module_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述:{e}")


@module.delete("/delete", summary="删除模块信息", description="根据id删除模块信息")
async def delete_module(
        module_id: int = Query(..., description="模块ID"),
):
    try:
        instance = await MODULE_CRUD.delete_module(module_id=module_id)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述:{e}")


@module.post("/update", summary="更新模块信息", description="根据id更新模块信息")
async def update_module(
        module_in: ModuleUpdate = Body(..., description="模块信息")
):
    try:
        instance = await MODULE_CRUD.update_module(module_in=module_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"更新失败，异常描述:{e}")


@module.get("/get", summary="查询模块信息", description="根据id查询模块信息")
async def get_module(
        module_id: int = Query(..., description="项目ID"),
):
    instance = await MODULE_CRUD.get_by_id(module_id=module_id)
    if not instance:
        return NotFoundResponse(message=f"模块(id={module_id})信息不存在")

    data: dict = await instance.to_dict()
    return SuccessResponse(data=data)


@module.get("/list", summary="查询模块列表", description="支持分页按条件查询模块列表信息（Body）")
async def list_module(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        order: list = Query(default=["id"], description="排序字段"),
        name: str = Query(default=None, description="模块名称"),
        dev_owner_name: str = Query(default=None, description="模块开发负责人"),
        test_owner_name: str = Query(default=None, description="模块测试负责人"),
        project_name: str = Query(default=None, description="项目名称"),
        project_state: int = Query(default=None, description="项目状态"),
):
    q = Q()
    if name:
        q &= Q(name__contains=name)
    if dev_owner_name:
        dev_owner_ids = await USER_CRUD.model.filter(alias__contains=dev_owner_name).values_list("id")
        q &= Q(dev_owner_id__contains=dev_owner_ids)
    if test_owner_name:
        test_owner_ids = await USER_CRUD.model.filter(alias__contains=test_owner_name).values_list("id", flat=True)
        q &= Q(test_owner_id__in=test_owner_ids)
    if project_name:
        q &= Q(project__name__in=project_name)
    if project_state:
        q &= Q(project__state=project_state)

    total, instances = await MODULE_CRUD.list(
        page=page, page_size=page_size, search=q, order=order, related=["dev_owner", "test_owner", "project"]
    )
    data = [
        await obj.to_dict(fk=True) for obj in instances
    ]
    return SuccessResponse(data=data)
