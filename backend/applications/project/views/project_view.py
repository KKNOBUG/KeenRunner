# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : project_view.py
@DateTime: 2025/2/2 13:36
"""

from fastapi import APIRouter, Body, Form
from tortoise.expressions import Q

from backend.applications.project.schemas.project_schema import ProjectCreate, ProjectUpdate, ProjectSelect
from backend.applications.project.services.project_crud import PROJECT_CRUD
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException
from backend.core.response.http_response import (
    DataAlreadyExistsResponse,
    SuccessResponse,
    FailureResponse,
    NotFoundResponse,
)

project = APIRouter()


@project.post("/createProject", summary="Project-新增项目信息")
async def create_project(
        project_in: ProjectCreate = Body()
):
    try:
        instance = await PROJECT_CRUD.create_project(api_in=project_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述:{e}")


@project.post("/deleteProject", summary="Project-删除一个项目信息")
async def delete_api(
        project_id: int = Form(..., description="项目ID")
):
    try:
        instance = await PROJECT_CRUD.delete_project(project_id)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述:{e}")


@project.post("/updateProject", summary="Project-更新项目信息")
async def update_user(
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


@project.post("/getProject", summary="Project-查询一个项目信息")
async def get_user(
        project_id: int = Form(..., description="项目ID")
):
    instance = await PROJECT_CRUD.select(id=project_id)
    if not instance:
        return NotFoundResponse(message="项目信息不存在")

    data: dict = await instance.to_dict()
    return SuccessResponse(data=data)


@project.post("/getProjects", summary="Project-查询多个项目信息")
async def get_apis(
        project_in: ProjectSelect = Body()
):
    page = project_in.page
    page_size = project_in.page_size
    page_order = project_in.page_order
    name = project_in.name
    initiator = project_in.initiator
    test_department_id = project_in.test_department_id
    dev_department_id = project_in.dev_department_id
    is_deleted = project_in.is_deleted
    created_user = project_in.created_user
    updated_user = project_in.updated_user

    q = Q()
    if name:
        q &= Q(name__contains=name)
    if initiator:
        q &= Q(initiator__contains=initiator)
    if test_department_id:
        q &= Q(test_department_id=test_department_id)
    if dev_department_id:
        q &= Q(dev_department_id=dev_department_id)
    if is_deleted is not None:
        q &= Q(is_deleted=is_deleted)
    if created_user:
        q &= Q(created_user__contains=created_user)
    if updated_user:
        q &= Q(updated_user__contains=updated_user)

    total, instances = await PROJECT_CRUD.list(
        page=page, page_size=page_size, search=q, order=page_order
    )
    data = [
        await obj.to_dict() for obj in instances
    ]
    return SuccessResponse(data=data)
