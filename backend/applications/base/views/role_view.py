# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : role_view.py
@DateTime: 2025/2/19 23:11
"""
import traceback

from fastapi import APIRouter, Body, Depends
from fastapi.params import Query, Form
from tortoise.expressions import Q

from backend.applications.base.dependencies import get_role_crud
from backend.applications.base.schemas.role_schema import (
    RoleCreate,
    RoleUpdate,
    RoleUpdateMenusRouters,
    RoleBatchDelete,
)
from backend.applications.base.services.role_crud import RoleCrud
from backend.applications.user.models.user_model import User
from backend.configure import LOGGER
from backend.core.exceptions import DataAlreadyExistsException, ParameterException, NotFoundException
from backend.core.responses import SuccessResponse, DataAlreadyExistsResponse, FailureResponse, ParameterResponse, NotFoundResponse
from backend.services import DependAuth

role = APIRouter()


@role.post("/create", summary="创建角色")
async def create_role(
        role_in: RoleCreate,
        current_user: User = DependAuth,
        role_crud: RoleCrud = Depends(get_role_crud),
):
    try:
        instance = await role_crud.create_role(role_in=role_in, created_user=current_user.username)
        data: dict = await instance.to_dict()
        return SuccessResponse(data=data)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=e.message)


@role.delete("/delete", summary="删除角色", description="根据id删除角色信息")
async def delete_role_one(
        role_id: int = Query(..., description="角色ID"),
        role_crud: RoleCrud = Depends(get_role_crud),
):
    try:
        instance = await role_crud.delete_role(role_id=role_id)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except ParameterException as e:
        return ParameterResponse(message=e.message)
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述:{e}")


@role.post("/deletes", summary="批量删除角色", description="根据角色ID或代码列表删除")
async def delete_roles_batch(
        body_in: RoleBatchDelete = Body(..., description="批量删除参数"),
        role_crud: RoleCrud = Depends(get_role_crud),
):
    try:
        count = await role_crud.delete_roles(
            role_ids=body_in.role_ids,
            role_codes=body_in.role_codes,
        )
        LOGGER.info(f"批量删除角色成功, 数量: {count}")
        return SuccessResponse(message="删除成功", data={"affected": count}, total=count)
    except Exception as e:
        LOGGER.error(f"批量删除角色失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述:{e}")


@role.post("/update", summary="更新角色", description="根据id更新角色信息")
async def update_role(
        role_in: RoleUpdate,
        current_user: User = DependAuth,
        role_crud: RoleCrud = Depends(get_role_crud),
):
    update_dict = role_in.model_dump(exclude_unset=True, exclude={"id"})
    update_dict["updated_user"] = current_user.username
    instance = await role_crud.update(id=role_in.id, obj_in=update_dict)
    data: dict = await instance.to_dict()
    return SuccessResponse(data=data)


@role.get("/get", summary="查看角色")
async def get_role_by(
        code: str = Form(default=None, description="角色名称"),
        name: str = Form(default=None, description="角色代码"),
        role_crud: RoleCrud = Depends(get_role_crud),
):
    where: dict = {}
    if code:
        where[code] = code
    if name:
        where[name] = name
    instances = await role_crud.get_by_conditions(only_one=True, **where)
    data = [await obj.to_dict() for obj in instances]
    return SuccessResponse(data=data)


@role.get("/list", summary="查看角色列表")
async def list_role(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        order: list = Query(default=["id"], description="排序字段"),
        name: str = Query(default="", description="角色名称，用于查询"),
        role_crud: RoleCrud = Depends(get_role_crud),
):
    q = Q()
    if name:
        q = Q(name__contains=name)
    total, role_objs = await role_crud.list(
        page=page, page_size=page_size, search=q, order=order
    )
    data = [await obj.to_dict() for obj in role_objs]
    return SuccessResponse(data=data, total=total)


@role.get("/authorized", summary="查看角色权限")
async def get_role_authorized(
        id: int = Query(..., description="角色ID"),
        role_crud: RoleCrud = Depends(get_role_crud),
):
    role_obj = await role_crud.get_or_error(id=id)
    data = await role_obj.to_dict(m2m=True)
    return SuccessResponse(data=data)


@role.post("/authorized", summary="更新角色权限")
async def update_role_authorized(
        role_in: RoleUpdateMenusRouters,
        role_crud: RoleCrud = Depends(get_role_crud),
):
    role_obj = await role_crud.get_or_none(id=role_in.id)
    await role_crud.update_roles(role=role_obj, menu_ids=role_in.menu_ids, router_infos=role_in.router_infos)
    return SuccessResponse()
