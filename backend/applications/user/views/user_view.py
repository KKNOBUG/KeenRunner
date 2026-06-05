# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : user_view.py
@DateTime: 2025/1/18 10:28
"""
import traceback

from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend.applications.department.services.department_crud import DEPT_CRUD
from backend.applications.user.schemas.user_schema import (
    UserCreate,
    UserUpdate,
    UserSelect,
    UpdatePassword,
    UserBatchDelete,
)
from backend.applications.user.services.user_crud import USER_CRUD
from backend.configure import LOGGER
from backend.core.exceptions import (
    DataAlreadyExistsException,
    NotFoundException,
    ParameterException
)
from backend.core.responses import (
    NotFoundResponse,
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    DataAlreadyExistsResponse,
)
from backend.services import CTX_USER_ID, DependAuth, verify_password, get_password_hash

user_public = APIRouter()
user_secure = APIRouter()


@user_public.post("/create", summary="新增用户")
async def create_user(user_in: UserCreate = Body()):
    try:
        instance = await USER_CRUD.create_user(user_in=user_in)
        data = await instance.to_dict(exclude_fields=["password"])
        return SuccessResponse(message="新增成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=e.message)
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述:{e}")


@user_secure.delete("/delete", summary="删除用户", description="根据id删除用户信息")
async def delete_user(user_id: int = Query(..., description="用户ID")):
    try:
        instance = await USER_CRUD.delete_user(user_id)
        data = await instance.to_dict(exclude_fields=["password"])
        return SuccessResponse(message="删除成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=e.message)
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述:{e}")


@user_secure.post("/deletes", summary="按id列表删除用户")
async def delete_users(user_in: UserBatchDelete = Body(..., description="用户信息")):
    try:
        deleted_ids = await USER_CRUD.delete_users(user_in=user_in)
        deleted_num = len(deleted_ids)
        LOGGER.info(f"按id列表删除用户成功, 数量: {deleted_num}")
        return SuccessResponse(message="删除成功", data={"deleted_ids": deleted_ids}, total=deleted_num)
    except Exception as e:
        LOGGER.error(f"按id列表删除用户失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败, 异常描述: {e}")


@user_secure.post("/update", summary="更新用户", description="根据id更新用户信息")
async def update_user(user_in: UserUpdate = Body(..., description="用户信息")):
    user_id: int = user_in.user_id
    try:
        instance = await USER_CRUD.update_user(user_in=user_in)
        await USER_CRUD.update_roles(instance, user_in.role_ids)
        data = await instance.to_dict(exclude_fields=["password"])
        return SuccessResponse(message="更新成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        return FailureResponse(message=f"更新失败，异常描述:{e}")


@user_secure.get("/get", summary="查询用户信息", description="根据id查询用户信息")
async def get_user(user_id: int = Query(..., description="用户ID")):
    instance = await USER_CRUD.get_by_id(user_id=user_id, state__not=1)
    if not instance:
        return NotFoundResponse(message=f"用户(id={user_id})信息不存在")
    data: dict = await instance.to_dict(m2m=True, exclude_fields=["password"])
    dept_id = data.pop("dept_id", None)
    data["dept"] = await (await DEPT_CRUD.get_or_error(id=dept_id)).to_dict() if dept_id else {}
    return SuccessResponse(data=data)


@user_secure.get("/byUsername", summary="查询用户信息", description="根据用户名查询用户信息")
async def get_user_by_username(username: str = Query(..., description="用户名称")):
    instance = await USER_CRUD.get_by_username(username=username)
    if not instance:
        return NotFoundResponse(message=f"用户(username={username})信息不存在")
    data: dict = await instance.to_dict(exclude_fields=["password"])
    return SuccessResponse(message="查询成功", data=data, total=1)


@user_secure.get("/list", summary="查询用户列表", description="支持分页按条件查询用户列表信息（Query）")
async def list_user(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        order: list = Query(default=["id"], description="排序字段"),
        username: str = Query(default=None, description="用户账号，用于搜索"),
        alias: str = Query(default=None, description="用户名称，用于搜索"),
        email: str = Query(default=None, description="邮箱地址"),
        phone: str = Query(default=None, description="用户电话"),
        gender: int = Query(default=None, description="用户性别: 0未知 1男 2女"),
        user_type: int = Query(default=None, description="用户类型：0xx 1xx 2xx"),
        is_active: bool = Query(default=None, description="是否激活"),
        is_superuser: bool = Query(default=None, description="是否为超级管理员"),
        dept_id: int = Query(default=None, description="部门ID"),
):
    q = Q()
    if username:
        q &= Q(username__contains=username)
    if alias:
        q &= Q(alias__contains=alias)
    if email:
        q &= Q(email__contains=email)
    if phone:
        q &= Q(phone__contains=phone)
    if gender is not None:
        q &= Q(gender=gender)
    if user_type is not None:
        q &= Q(user_type=user_type)
    if is_active is not None:
        q &= Q(is_active=is_active)
    if is_superuser is not None:
        q &= Q(is_superuser=is_superuser)
    if dept_id is not None:
        q &= Q(dept_id=dept_id)
    q &= Q(state=0)
    total, user_objs = await USER_CRUD.list(
        page=page, page_size=page_size, order=order, search=q
    )
    data = [
        await obj.to_dict(
            m2m=True,
            exclude_fields=["password"],
        ) for obj in user_objs
    ]
    for item in data:
        dept_id = item.pop("dept_id", None)
        item["dept"] = await (await DEPT_CRUD.get_or_error(id=dept_id)).to_dict() if dept_id else {}

    return SuccessResponse(data=data, total=total)


@user_secure.post("/search", summary="查询用户列表", description="支持分页按条件查询用户列表信息（Body）")
async def get_users(user_in: UserSelect = Body()):
    q = Q()
    if user_in.username:
        q &= Q(username__contains=user_in.username)
    if user_in.alias:
        q &= Q(alias__contains=user_in.alias)
    if user_in.email:
        q &= Q(email__contains=user_in.email)
    if user_in.phone:
        q &= Q(phone__contains=user_in.phone)
    if user_in.motto:
        q &= Q(motto__contains=user_in.motto)
    if user_in.address:
        q &= Q(address__contains=user_in.address)
    if user_in.gender is not None:
        q &= Q(gender=user_in.gender)
    if user_in.user_type is not None:
        q &= Q(user_type=user_in.user_type)
    if user_in.emergency_name:
        q &= Q(emergency_name__contains=user_in.emergency_name)
    if user_in.emergency_phone:
        q &= Q(emergency_phone__contains=user_in.emergency_phone)
    if user_in.is_active is not None:
        q &= Q(is_active=user_in.is_active)
    if user_in.is_superuser is not None:
        q &= Q(is_superuser=user_in.is_superuser)
    if user_in.dept_id is not None:
        q &= Q(dept_id=user_in.dept_id)
    if user_in.state is not None:
        q &= Q(state=user_in.state)
    else:
        q &= Q(state=0)
    total, instances = await USER_CRUD.list(
        page=user_in.page, page_size=user_in.page_size, search=q, order=user_in.order
    )
    data = [
        await obj.to_dict(
            m2m=True,
            exclude_fields=["password"],
        ) for obj in instances
    ]
    for item in data:
        dept_id = item.pop("dept_id", None)
        item["dept"] = await (await DEPT_CRUD.get_or_error(id=dept_id)).to_dict() if dept_id else {}

    return SuccessResponse(message="查询成功", data=data, total=total)


@user_secure.post("/update_password", summary="修改密码", dependencies=[DependAuth])
async def update_user_password(req_in: UpdatePassword):
    user_id = CTX_USER_ID.get()
    instance = await USER_CRUD.get_or_error(user_id)
    verified = verify_password(req_in.old_password, instance.password)
    if not verified:
        return FailureResponse(message="旧密码验证错误")
    instance.password = get_password_hash(req_in.new_password)
    await instance.save()
    data = await instance.to_dict(exclude_fields=["password"])
    return SuccessResponse(message="修改成功", data=data, total=1)


@user_secure.post("/reset_password", summary="重置密码")
async def reset_password(user_id: int = Body(..., description="用户ID", embed=True)):
    data = await USER_CRUD.reset_password(user_id)
    return SuccessResponse(message="重置密码", data=data, total=1)
