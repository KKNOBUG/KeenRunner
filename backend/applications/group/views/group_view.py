# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : group_view.py
@DateTime: 2025/2/5 13:35
"""
from typing import Dict, Union

from fastapi import APIRouter, Body
from fastapi.params import Form
from tortoise.expressions import Q

from backend.applications.group.schemas.group_schema import (
    GroupCreate, GroupUpdate, GroupSelect
)
from backend.applications.group.services.group_crud import GROUP_CRUD
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

group = APIRouter()


@group.post("/create", summary="新增小组信息")
async def create_group(
        group_in: GroupCreate = Body()
):
    try:
        instance = await GROUP_CRUD.create_group(group_in=group_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述:{e}")


@group.post("/delete", summary="删除一个小组信息")
async def delete_group(
        group_id: int = Form(..., description="小组ID")
):
    try:
        instance = await GROUP_CRUD.delete_group(group_id)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述:{e}")


@group.post("/update", summary="更新小组信息")
async def update_group(
        group_in: GroupUpdate = Body(..., description="小组信息")
):
    try:
        instance = await GROUP_CRUD.update_group(group_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"更新失败，异常描述:{e}")


@group.post("/get", summary="查询一个小组信息")
async def get_group(
        group_id: int = Form(None, description="小组ID"),
        name: str = Form(None, description="小组名称"),
):
    # 构建查询条件，小组ID或小组名称
    where: Dict[str, Union[str, int]] = {}
    if group_id:
        where["id"] = group_id
    elif name:
        where["name"] = name
    else:
        return ParameterResponse("参数[id]和[name]不可同时为空")

    instance = await GROUP_CRUD.select(**where)
    if not instance:
        return NotFoundResponse(message=f"小组(id={group_id},name={name})信息不存在")

    data: dict = await instance.to_dict()
    return SuccessResponse(data=data)


@group.post("/search", summary="查询多个小组信息")
async def get_groups(
        group_in: GroupSelect = Body()
):
    page = group_in.page
    page_size = group_in.page_size
    page_order = group_in.page_order
    name = group_in.name
    initiator = group_in.initiator
    is_deleted = group_in.is_deleted
    created_user = group_in.created_user
    updated_user = group_in.updated_user

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

    total, instances = await GROUP_CRUD.list(
        page=page, page_size=page_size, search=q, order=page_order
    )
    data = [
        await obj.to_dict() for obj in instances
    ]
    return SuccessResponse(data=data)
