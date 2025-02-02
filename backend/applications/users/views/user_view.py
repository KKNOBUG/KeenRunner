# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : user_model.py
@DateTime: 2025/1/18 10:28
"""
from typing import Optional, Dict, Union

from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend.applications.users.schemas.user_schmea import UserCreate, UserUpdate
from backend.applications.users.services.user_crud import USER_CRUD
from backend.core.response.http_response import NotFoundResponse, SuccessResponse

user = APIRouter()


@user.post("/createUser", summary="User-新增用户")
async def create_user(
        user_in: UserCreate = Body()
):
    try:
        username: str = user_in.username
        user_instance = await USER_CRUD.get_by_username(username)
        if user_instance:
            return NotFoundResponse(message=f"用户(username={username})已存在")
        new_user_instance = await USER_CRUD.create_user(user_in=user_in)
        new_user_data = await new_user_instance.to_dict()
        return SuccessResponse(data=new_user_data)
    except Exception as e:
        return NotFoundResponse(message=f"新增用户失败，异常描述:{e}")


@user.post("/deleteUser", summary="User-删除一个用户")
async def delete_user(
        user_id: int = Query(..., description="用户ID")
):
    try:
        user_instance = await USER_CRUD.delete_user(user_id)
        user_data = await user_instance.to_dict()
        return SuccessResponse(data=user_data)
    except Exception as e:
        return NotFoundResponse(message=f"用户(id={user_id})不存在")


@user.post("/updateUser", summary="User-更新用户")
async def update_user(
        user_in: UserUpdate = Body(..., description="用户信息")
):
    user_id: int = user_in.id
    try:
        user_instance = await USER_CRUD.update(id=user_id, obj_in=user_in)
        user_data = await user_instance.to_dict()
        return SuccessResponse(data=user_data)
    except Exception as e:
        return NotFoundResponse(message=f"用户(id={user_id})不存在")


@user.post("/getUser", summary="User-查询一个用户")
async def get_user(
        user_id: int = Query(None, description="用户ID"),
        username: str = Query(None, description="用户名称"),
):
    # 构建查询条件，用户ID或用户名称
    where: Dict[str, Union[str, int]] = {}
    if user_id:
        where["id"] = user_id
    elif username:
        where["username"] = username

    user_instance = await USER_CRUD.get(**where)
    if not user_instance:
        return NotFoundResponse(message="用户不存在")
    user_data: dict = await user_instance.to_dict(exclude_fields=["id", "password"])
    return SuccessResponse(data=user_data)


@user.post("/getUsers", summary="User-查询多个用户")
async def get_users(
        page: int = Query(1, description="页码"),
        page_size: int = Query(10, description="每页展示数量"),
        user_id: str = Query(None, description="用户ID"),
        username: str = Query(None, description="用户名称"),
        is_active: Optional[bool] = Query(True, description="用户状态"),
        is_superuser: Optional[bool] = Query(None, description="用户类别"),
):
    q = Q()
    if user_id:
        q &= Q(id__contains=user_id)
    if username:
        q &= Q(username__contains=username)
    if is_active is not None:
        q &= Q(is_active=is_active)
    if is_superuser is not None:
        q &= Q(is_superuser=is_superuser)

    total, user_instances = await USER_CRUD.list(
        page=page, page_size=page_size, search=q
    )
    data = [
        await obj.to_dict() for obj in user_instances
    ]
    return SuccessResponse(data={"total": total, "data": data})
