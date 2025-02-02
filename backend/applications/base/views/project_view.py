# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : project_view.py
@DateTime: 2025/2/2 13:36
"""
from typing import Optional

from fastapi import APIRouter, Body, Form
from tortoise.expressions import Q

from backend.applications.base.schemas.project_schema import ProjectCreate, ProjectUpdate
from backend.applications.base.services.project_crud import PROJECT_CRUD
from backend.core.response.http_response import (
    DataAlreadyExistsResponse,
    SuccessResponse,
    FailureResponse,
    NotFoundResponse,
)

project = APIRouter()


@project.post("/createProject", summary="Base-新增项目信息")
async def create_project(
        project_in: ProjectCreate = Body()
):
    try:
        name: str = project_in.name
        project_instance = await PROJECT_CRUD.get_by_name(name=name)
        if project_instance:
            return DataAlreadyExistsResponse(message=f"项目(name={name})已存在")

        new_project_instance = await PROJECT_CRUD.create_project(api_in=project_in)
        new_project_data = await new_project_instance.to_dict()
        return SuccessResponse(data=new_project_data)
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述:{e}")


@project.post("/deleteProject", summary="Base-删除一个项目信息")
async def delete_api(
        project_id: int = Form(..., description="项目ID")
):
    try:
        instance = await PROJECT_CRUD.delete_project(project_id)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except Exception as e:
        return NotFoundResponse(message=f"项目(id={project_id})不存在")


@project.post("/updateProject", summary="Base-更新项目信息")
async def update_user(
        project_in: ProjectUpdate = Body(..., description="项目信息")
):
    try:
        instance = await PROJECT_CRUD.update_project(project_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except Exception as e:
        return NotFoundResponse(message=f"项目(id={project_in.id})不存在")


@project.post("/getProject", summary="Base-查询一个项目信息")
async def get_user(
        project_id: int = Form(..., description="项目ID")
):
    instance = await PROJECT_CRUD.get(id=project_id)
    if not instance:
        return NotFoundResponse(message="项目信息不存在")

    data: dict = await instance.to_dict()
    return SuccessResponse(data=data)


@project.post("/getProjects", summary="Base-查询多个项目信息")
async def get_apis(
        page: int = Form(1, description="页码"),
        page_size: int = Form(10, description="每页展示数量"),
        project_id: str = Form(None, description="项目ID"),
        name: str = Form(None, description="项目名称"),
        initiator: str = Form(None, description="项目负责人"),
        test_captain: str = Form(None, description="测试负责人"),
        dev_captain: str = Form(None, description="开发负责人"),
        release: str = Form(None, description="项目版本"),
        is_active: Optional[bool] = Form(True, description="项目所属状态")
):
    q = Q()
    if project_id:
        q &= Q(id__contains=project_id)
    if name:
        q &= Q(name__contains=name)
    if initiator:
        q &= Q(initiator__contains=initiator)
    if test_captain:
        q &= Q(test_captain__contains=test_captain)
    if dev_captain:
        q &= Q(dev_captain__contains=dev_captain)
    if release:
        q &= Q(release__contains=release)

    q &= Q(is_active=is_active)

    total, instances = await PROJECT_CRUD.list(
        page=page, page_size=page_size, search=q
    )
    data = [
        await obj.to_dict() for obj in instances
    ]
    return SuccessResponse(data=data)
