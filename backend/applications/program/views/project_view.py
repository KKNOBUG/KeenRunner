# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : project_view.py
@DateTime: 2025/3/15 15:07
"""
from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend.applications.program.schemas.project_schema import (
    ProjectCreate, ProjectUpdate, ProjectSelect
)
from backend.applications.program.services.project_crud import PROJECT_CRUD
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

project = APIRouter()


@project.post("/create", summary="新增项目信息")
async def create_project(
        project_in: ProjectCreate = Body(...)
):
    try:
        instance = await PROJECT_CRUD.create_project(project_in=project_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述:{e}")


@project.delete("/delete", summary="删除项目", description="根据id删除项目信息")
async def delete_project(
        project_id: int = Query(..., description="项目ID"),
):
    try:
        instance = await PROJECT_CRUD.delete_project(project_id)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述:{e}")


@project.post("/update", summary="更新项目信息", description="根据id更新项目信息")
async def update_project(
        project_in: ProjectUpdate = Body(..., description="项目信息")
):
    try:
        instance = await PROJECT_CRUD.update_project(project_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"更新失败，异常描述:{e}")


@project.get("/get", summary="查询项目信息", description="根据id查询项目信息")
async def get_project(
        project_id: int = Query(..., description="项目ID"),
):
    instance = await PROJECT_CRUD.query(id=project_id)
    if not instance:
        return NotFoundResponse(message=f"项目(id={project_id})信息不存在")

    data: dict = await instance.to_dict()
    return SuccessResponse(data=data)


@project.get("/list", summary="查询项目列表", description="支持分页按条件查询项目列表信息（Body）")
async def list_project(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        order: list = Query(default=["id"], description="排序字段"),
        name: str = Query(default=None, description="项目名称"),
        state: int = Query(default=None, description="项目状态"),
):
    q = Q()
    if name:
        q &= Q(name__contains=name)
    if state:
        q &= Q(state=state)

    total, instances = await PROJECT_CRUD.list(
        page=page, page_size=page_size, search=q, order=order, related=["dev_owner", "test_owner"]
    )
    data = [
        await obj.to_dict(
            fk=True,
            fk_include_fields=["id", "username", "alias", "phone", "email"]
        ) for obj in instances
    ]
    return SuccessResponse(data=data)


@project.post("/search", summary="查询项目列表", description="支持分页按条件查询项目列表信息（Body）")
async def search_project(
        project_in: ProjectSelect = Body()
):
    page = project_in.page
    page_size = project_in.page_size
    order = project_in.order
    code = project_in.code
    name = project_in.name
    state = project_in.state
    dev_owner = project_in.dev_owner
    test_owner = project_in.test_owner
    created_user = project_in.created_user
    updated_user = project_in.updated_user

    q = Q()
    if code:
        q &= Q(code__contains=code)
    if name:
        q &= Q(name__contains=name)
    if state:
        q &= Q(state=state)
    if dev_owner:
        q &= Q(dev_owner_id=dev_owner)
    if test_owner:
        q &= Q(test_owner_id=test_owner)
    if created_user:
        q &= Q(created_user__contains=created_user)
    if updated_user:
        q &= Q(updated_user__contains=updated_user)

    total, instances = await PROJECT_CRUD.list(
        page=page, page_size=page_size, search=q, order=order, related=["dev_owner", "test_owner"]
    )
    data = [
        await obj.to_dict(
            fk=True,
            fk_include_fields=["id", "username", "alias", "phone", "email"]
        ) for obj in instances
    ]
    return SuccessResponse(data=data)
