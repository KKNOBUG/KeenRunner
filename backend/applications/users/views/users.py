# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : user_model.py
@DateTime: 2025/1/18 10:28
"""

from fastapi import APIRouter, Body, Query

from backend.applications.users.schemas.user_schmeas import UserCreate
from backend.applications.users.services.user_crud import USER_CRUD
from backend.core.response.base_response import NotFoundResponse, SuccessResponse

user = APIRouter()


@user.post("/createUser", summary="user-创建用户")
async def create_user(
        user_in: UserCreate = Body()
):
    user_instance = await USER_CRUD.get_by_username(user_in.username)
    if user_instance:
        return NotFoundResponse(message="用户已存在")
    new_user_instance = await USER_CRUD.create_user(user_in=user_in)
    return SuccessResponse(data=new_user_instance)


@user.post("/getUser", summary="user-查询用户")
async def get_user(
        user_id: int = Query()
):
    user_instance = await USER_CRUD.get(id=user_id)
    if user_instance:
        return NotFoundResponse(message="用户不存在")
    user_data: dict = await user_instance.to_dict(exclude_fields=["id", "password"])
    return SuccessResponse(data=user_data)
