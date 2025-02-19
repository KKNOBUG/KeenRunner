# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : user_model.py
@DateTime: 2025/1/18 10:28
"""
from typing import Dict, Union

from fastapi import APIRouter, Body, Query, Form
from tortoise.expressions import Q

from backend.applications.user.schemas.user_schema import UserCreate, UserUpdate, UserSelect
from backend.applications.user.services.user_crud import USER_CRUD
from backend.core.exceptions.base_exceptions import (
    DataAlreadyExistsException,
    NotFoundException
)
from backend.core.response.http_response import (
    NotFoundResponse,
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    DataAlreadyExistsResponse,
)

user = APIRouter()


@user.post("/create", summary="新增用户")
async def create_user(
        user_in: UserCreate = Body()
):
    try:
        instance = await USER_CRUD.create_user(user_in=user_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述:{e}")


@user.post("/delete", summary="删除一个用户")
async def delete_user(
        user_id: int = Query(..., description="用户ID")
):
    try:
        instance = await USER_CRUD.delete_user(user_id)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述:{e}")


@user.post("/update", summary="更新用户")
async def update_user(
        user_in: UserUpdate = Body(..., description="用户信息")
):
    user_id: int = user_in.id
    try:
        instance = await USER_CRUD.update(id=user_id, obj_in=user_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"更新失败，异常描述:{e}")


@user.post("/byId", summary="查询一个用户")
async def get_user_by_id(
        user_id: int = Form(..., description="用户ID"),
):
    instance = await USER_CRUD.select(id=user_id)
    if not instance:
        return NotFoundResponse(message=f"用户(id={user_id})信息不存在")

    data: dict = await instance.to_dict(exclude_fields=["password"])
    return SuccessResponse(data=data)


@user.post("/byUsername", summary="查询一个用户")
async def get_user_by_username(
        username: str = Form(None, description="用户名称"),
):
    instance = await USER_CRUD.select(username=username)
    if not instance:
        return NotFoundResponse(message=f"用户(username={username})信息不存在")

    data: dict = await instance.to_dict(exclude_fields=["password"])
    return SuccessResponse(data=data)


@user.post("/search", summary="查询多个用户")
async def get_users(
        user_in: UserSelect = Body()
):
    page = user_in.page
    page_size = user_in.page_size
    page_order = user_in.page_order
    username = user_in.username
    alias = user_in.alias
    phone = user_in.phone
    is_admin = user_in.is_admin
    is_deleted = user_in.is_deleted
    created_user = user_in.created_user
    updated_user = user_in.updated_user

    q = Q()
    if username:
        q &= Q(username__contains=username)
    if alias:
        q &= Q(alias__contains=alias)
    if phone:
        q &= Q(phone__contains=phone)
    if is_admin is not None:
        q &= Q(is_admin=is_admin)
    if is_deleted is not None:
        q &= Q(is_deleted=is_deleted)
    if created_user:
        q &= Q(created_user__contains=created_user)
    if updated_user:
        q &= Q(updated_user__contains=updated_user)

    total, instances = await USER_CRUD.list(
        page=page, page_size=page_size, search=q, order=page_order
    )
    data = [
        await obj.to_dict() for obj in instances
    ]
    return SuccessResponse(data=data)
