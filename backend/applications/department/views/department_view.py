# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : department_view.py
@DateTime: 2025/2/3 18:21
"""
from typing import Dict, Union

from fastapi import APIRouter, Body
from fastapi.params import Form
from tortoise.expressions import Q

from backend.applications.department.schemas.department_schema import (
    DepartmentCreate, DepartmentUpdate, DepartmentSelect
)
from backend.applications.department.services.department_crud import DEPARTMENT_CRUD
from backend.core.exceptions.base_exceptions import (
    DataAlreadyExistsException,
    NotFoundException
)
from backend.core.response.http_response import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    NotFoundResponse,
    ParameterResponse,
)

department = APIRouter()


@department.post("/create", summary="新增部门信息")
async def create_api(
        department_in: DepartmentCreate = Body()
):
    try:
        instance = await DEPARTMENT_CRUD.create_department(department_in=department_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述:{e}")


@department.post("/delete", summary="删除一个部门信息")
async def delete_api(
        department_id: int = Form(..., description="部门ID")
):
    try:
        instance = await DEPARTMENT_CRUD.delete_department(department_id)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述:{e}")


@department.post("/update", summary="更新部门信息")
async def update_user(
        department_in: DepartmentUpdate = Body(..., description="部门信息")
):
    try:
        instance = await DEPARTMENT_CRUD.update_department(department_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"更新失败，异常描述:{e}")


@department.post("/get", summary="查询一个部门信息")
async def get_user(
        department_id: int = Form(None, description="部门ID"),
        name: str = Form(None, description="部门名称"),
):
    # 构建查询条件，用户ID或用户名称
    where: Dict[str, Union[str, int]] = {}
    if department_id:
        where["id"] = department_id
    elif name:
        where["name"] = name
    else:
        return ParameterResponse("参数[id]和[name]不可同时为空")

    instance = await DEPARTMENT_CRUD.select(**where)
    if not instance:
        return NotFoundResponse(message=f"部门(id={department_id},name={name})信息不存在")

    data: dict = await instance.to_dict()
    return SuccessResponse(data=data)


@department.post("/search", summary="Department-查询多个部门信息")
async def get_apis(
        department_in: DepartmentSelect = Body()
):
    page = department_in.page
    page_size = department_in.page_size
    page_order = department_in.page_order
    name = department_in.name
    initiator = department_in.initiator
    is_deleted = department_in.is_deleted
    created_user = department_in.created_user
    updated_user = department_in.updated_user

    q = Q()
    if name:
        q &= Q(name__contains=name)
    if initiator:
        q &= Q(initiator_contains=initiator)
    if is_deleted is not None:
        q &= Q(is_deleted=is_deleted)
    if created_user:
        q &= Q(created_user__contains=created_user)
    if updated_user:
        q &= Q(updated_user__contains=updated_user)

    total, instances = await DEPARTMENT_CRUD.list(
        page=page, page_size=page_size, search=q, order=page_order
    )
    data = [
        await obj.to_dict() for obj in instances
    ]
    return SuccessResponse(data=data)
