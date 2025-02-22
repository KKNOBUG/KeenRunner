# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : user_model.py
@DateTime: 2025/1/18 10:28
"""
from fastapi import APIRouter, Body, Query, Form
from tortoise.expressions import Q

from backend.applications.department.services.department_crud import DEPT_CRUD
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


@user.delete("/delete", summary="删除用户")
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
        await USER_CRUD.update_roles(instance, user_in.role_ids)
        return SuccessResponse(data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"更新失败，异常描述:{e}")


@user.get("/get", summary="查看用户")
async def get_user(
        user_id: int = Query(..., description="用户ID"),
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
    instance = await USER_CRUD.model.filter(username=username).first()
    if not instance:
        return NotFoundResponse(message=f"用户(username={username})信息不存在")

    data: dict = await instance.to_dict(exclude_fields=["password"])
    return SuccessResponse(data=data)


@user.get("/list", summary="查看用户列表")
async def list_user(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        order: list = Query(default=["id"], description="排序字段"),
        username: str = Query(default=None, description="用户名称，用于搜索"),
        email: str = Query(default=None, description="邮箱地址"),
        dept_id: int = Query(default=None, description="部门ID"),
):
    q = Q()
    if username:
        q &= Q(username__contains=username)
    if email:
        q &= Q(email__contains=email)
    if dept_id is not None:
        q &= Q(dept_id=dept_id)
    total, user_objs = await USER_CRUD.list(
        page=page, page_size=page_size, order=order, search=q
    )
    data = [await obj.to_dict(m2m=True, exclude_fields=["password"]) for obj in user_objs]
    for item in data:
        dept_id = item.pop("dept_id", None)
        item["dept"] = await (await DEPT_CRUD.get(id=dept_id)).to_dict() if dept_id else {}

    return SuccessResponse(data=data, total=total)


@user.post("/search", summary="查询多个用户")
async def get_users(
        user_in: UserSelect = Body()
):
    page = user_in.page
    page_size = user_in.page_size
    order = user_in.order
    username = user_in.username
    alias = user_in.alias
    email = user_in.email
    phone = user_in.phone
    state = user_in.state
    is_admin = user_in.is_admin
    is_superuser = user_in.is_superuser
    created_user = user_in.created_user
    updated_user = user_in.updated_user

    q = Q()
    if username:
        q &= Q(username__contains=username)
    if alias:
        q &= Q(alias__contains=alias)
    if email:
        q &= Q(email__contains=email)
    if phone:
        q &= Q(phone__contains=phone)
    if is_admin is not None:
        q &= Q(state=state)
    if is_admin is not None:
        q &= Q(is_admin=is_admin)
    if is_superuser is not None:
        q &= Q(is_superuser=is_superuser)
    if created_user:
        q &= Q(created_user__contains=created_user)
    if updated_user:
        q &= Q(updated_user__contains=updated_user)

    total, instances = await USER_CRUD.list(
        page=page, page_size=page_size, search=q, order=order
    )
    data = [
        await obj.to_dict() for obj in instances
    ]
    return SuccessResponse(data=data)


@user.post("/reset_password", summary="重置密码")
async def reset_password(user_id: int = Body(..., description="用户ID", embed=True)):
    data = await USER_CRUD.reset_password(user_id)
    return SuccessResponse(data=data)
