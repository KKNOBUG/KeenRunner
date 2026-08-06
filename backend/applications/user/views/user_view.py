# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : user_view.py
@DateTime: 2025/1/18 10:28
"""
import traceback

from fastapi import APIRouter, Body, Query, Depends
from tortoise.expressions import Q

from backend.applications.department.dependencies import get_dept_crud
from backend.applications.department.services.department_crud import DepartmentCrud
from backend.applications.user.dependencies import get_user_crud
from backend.applications.user.schemas.user_schema import (
    UserCreate,
    UserUpdate,
    UserSelect,
    UpdatePassword,
    UserBatchDelete,
)
from backend.applications.user.services.user_crud import UserCrud
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
from backend.services import CTX_USER_ID, verify_password, get_password_hash

user_public = APIRouter()
user_secure = APIRouter()

@user_public.post("/create", summary="新增用户")
async def create_user(
        user_in: UserCreate = Body(..., description="用户信息"),
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    新增用户。

    :param user_in: 用户入参
    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await user_crud.create_user(user_in=user_in)
        data = await instance.to_dict(exclude_fields=["password"])
        LOGGER.info(f"新增用户成功, 结果明细: {data}")
        return SuccessResponse(message="新增成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增用户失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {e}")

@user_secure.delete("/delete", summary="删除用户", description="根据id删除用户信息")
async def delete_user(
        user_id: int = Query(..., description="用户ID"),
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    删除用户。

    :param user_id: 用户ID
    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await user_crud.delete_user(user_id)
        data = await instance.to_dict(exclude_fields=["password"])
        LOGGER.info(f"删除用户成功, 结果明细: {data}")
        return SuccessResponse(message="删除成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"删除用户失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")

@user_secure.post("/deletes", summary="批量删除用户", description="根据id列表批量删除用户信息")
async def delete_users(
        user_in: UserBatchDelete = Body(..., description="用户信息"),
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    根据id列表删除用户。

    :param user_in: 用户入参
    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
    """
    try:
        deleted_ids = await user_crud.delete_users(user_in=user_in)
        deleted_num = len(deleted_ids)
        LOGGER.info(f"根据id列表删除用户成功, 数量: {deleted_num}")
        return SuccessResponse(message="删除成功", data={"deleted_ids": deleted_ids}, total=deleted_num)
    except Exception as e:
        LOGGER.error(f"根据id列表删除用户失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")

@user_secure.post("/update", summary="更新用户", description="根据id更新用户信息")
async def update_user(
        user_in: UserUpdate = Body(..., description="用户信息"),
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    更新用户。

    :param user_in: 用户入参
    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
    """
    user_id: int = user_in.user_id
    try:
        instance = await user_crud.update_user(user_in=user_in)
        await user_crud.update_roles(instance, user_in.role_ids)
        data = await instance.to_dict(exclude_fields=["password"])
        LOGGER.info(f"更新用户成功, user_id: {user_id}, 结果明细: {data}")
        return SuccessResponse(message="更新成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"更新用户失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {e}")

@user_secure.get("/get", summary="查询用户信息", description="根据id查询用户信息")
async def get_user(
        user_id: int = Query(..., description="用户ID"),
        user_crud: UserCrud = Depends(get_user_crud),
        dept_crud: DepartmentCrud = Depends(get_dept_crud),
):
    """
    查询用户信息。

    :param user_id: 用户ID
    :param user_crud: 用户CRUD服务
    :param dept_crud: 部门CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await user_crud.get_by_id(user_id=user_id, state__not=1)
        if not instance:
            return NotFoundResponse(message=f"用户(id={user_id})信息不存在")
        data: dict = await instance.to_dict(m2m=True, exclude_fields=["password"])
        dept_id = data.pop("dept_id", None)
        data["dept"] = await (await dept_crud.get_or_error(id=dept_id)).to_dict() if dept_id else {}
        LOGGER.info(f"查询用户成功, user_id: {user_id}")
        return SuccessResponse(message="查询成功", data=data)
    except Exception as e:
        LOGGER.error(f"查询用户失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")

@user_secure.get("/byUsername", summary="查询用户信息", description="根据用户名查询用户信息")
async def get_user_by_username(
        username: str = Query(..., description="用户名称"),
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    查询用户信息。

    :param username: 用户账号
    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await user_crud.get_by_username(username=username)
        if not instance:
            return NotFoundResponse(message=f"用户(username={username})信息不存在")
        data: dict = await instance.to_dict(exclude_fields=["password"])
        LOGGER.info(f"根据用户名查询用户成功, username: {username}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except Exception as e:
        LOGGER.error(f"根据用户名查询用户失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")

@user_secure.get("/list", summary="查询用户列表", description="根据条件分页查询用户列表信息(Query)")
async def list_users(
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
        user_crud: UserCrud = Depends(get_user_crud),
        dept_crud: DepartmentCrud = Depends(get_dept_crud),
):
    """
    查询用户列表。

    :param page: 页码
    :param page_size: 每页条数
    :param order: 排序字段
    :param username: 用户账号
    :param alias: 查询参数
    :param email: 查询参数
    :param phone: 查询参数
    :param gender: 查询参数
    :param user_type: 查询参数
    :param is_active: 查询参数
    :param is_superuser: 查询参数
    :param dept_id: 主键 ID
    :param user_crud: 用户CRUD服务
    :param dept_crud: 部门CRUD服务
    :return: 统一HTTP响应
    """
    try:
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
        total, user_objs = await user_crud.list(
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
            item["dept"] = await (await dept_crud.get_or_error(id=dept_id)).to_dict() if dept_id else {}

        LOGGER.info(f"查询用户列表成功, 数量: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception as e:
        LOGGER.error(f"查询用户列表失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")

@user_secure.post("/search", summary="查询用户列表", description="根据条件分页查询用户列表信息(Body)")
async def search_users(
        user_in: UserSelect = Body(..., description="查询条件"),
        user_crud: UserCrud = Depends(get_user_crud),
        dept_crud: DepartmentCrud = Depends(get_dept_crud),
):
    """
    查询用户列表。

    :param user_in: 用户入参
    :param user_crud: 用户CRUD服务
    :param dept_crud: 部门CRUD服务
    :return: 统一HTTP响应
    """
    try:
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
        total, instances = await user_crud.list(
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
            item["dept"] = await (await dept_crud.get_or_error(id=dept_id)).to_dict() if dept_id else {}

        LOGGER.info(f"查询用户列表成功, 数量: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception as e:
        LOGGER.error(f"查询用户列表失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")

@user_secure.post("/update_password", summary="修改密码", description="根据当前登录用户ID修改密码")
async def update_user_password(
        password_in: UpdatePassword = Body(..., description="修改密码入参"),
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    修改密码。

    :param password_in: 修改密码入参
    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
    """
    try:
        user_id = CTX_USER_ID.get()
        instance = await user_crud.get_or_error(user_id)
        verified = verify_password(password_in.old_password, instance.password)
        if not verified:
            return FailureResponse(message="旧密码验证错误")
        instance.password = get_password_hash(password_in.new_password)
        await instance.save()
        data = await instance.to_dict(exclude_fields=["password"])
        LOGGER.info(f"修改密码成功, user_id: {user_id}")
        return SuccessResponse(message="修改成功", data=data, total=1)
    except Exception as e:
        LOGGER.error(f"修改密码失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"修改失败，异常描述: {e}")

@user_secure.post("/reset_password", summary="重置密码")
async def reset_password(
        user_id: int = Body(..., description="用户ID", embed=True),
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    重置密码。

    :param user_id: 用户ID
    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
    """
    try:
        data = await user_crud.reset_password(user_id)
        LOGGER.info(f"重置密码成功, user_id: {user_id}")
        return SuccessResponse(message="重置成功", data=data, total=1)
    except Exception as e:
        LOGGER.error(f"重置密码失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"重置失败，异常描述: {e}")

@user_secure.post("/logout", summary="用户登出", description="退出当前登录用户")
async def logout(
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    用户登出。

    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
    """
    user_id = CTX_USER_ID.get()
    try:
        await user_crud.logout(user_id=user_id)
        LOGGER.info(f"用户登出成功, user_id: {user_id}")
        return SuccessResponse(message="登出成功")
    except Exception as e:
        LOGGER.error(f"用户登出失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"登出失败，异常描述: {e}")
