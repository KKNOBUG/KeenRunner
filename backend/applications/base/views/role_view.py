# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : role_view.py
@DateTime: 2025/2/19 23:11
"""
from fastapi import APIRouter
from fastapi.params import Query, Form
from tortoise.expressions import Q

from backend.applications.base.schemas.role_schema import RoleCreate, RoleUpdate, RoleUpdateMenusRouters
from backend.applications.base.services.role_crud import ROLE_CRUD
from backend.core.response.http_response import SuccessResponse, DataAlreadyExistsResponse

role = APIRouter()


@role.post("/create", summary="创建角色")
async def create_role(role_in: RoleCreate):
    if await ROLE_CRUD.is_exist(name=role_in.name):
        return DataAlreadyExistsResponse(message="角色名称已经存在")

    instance = await ROLE_CRUD.create_role(role_in=role_in)
    data: dict = await instance.to_dict()
    return SuccessResponse(data=data)


@role.delete("/delete", summary="删除角色", description="根据id删除角色信息")
async def delete_role(
        role_id: int = Query(..., description="角色ID"),
):
    instance = await ROLE_CRUD.remove(id=role_id)
    data: dict = await instance.to_dict()
    return SuccessResponse(data=data)


@role.post("/update", summary="更新角色", description="根据id更新角色信息")
async def update_role(role_in: RoleUpdate):
    instance = await ROLE_CRUD.update(id=role_in.id, obj_in=role_in)
    data: dict = await instance.to_dict()
    return SuccessResponse(data=data)


@role.get("/get", summary="查看角色")
async def get_role_by(
        code: str = Form(default=None, description="角色名称"),
        name: str = Form(default=None, description="角色代码"),
):
    where: dict = {}
    if code:
        where[code] = code
    if name:
        where[name] = name
    instances = await ROLE_CRUD.select(**where)
    data = [await obj.to_dict() for obj in instances]
    return SuccessResponse(data=data)


@role.get("/list", summary="查看角色列表")
async def list_role(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        order: list = Query(default=["id"], description="排序字段"),
        role_name: str = Query(default="", description="角色名称，用于查询"),
):
    q = Q()
    if role_name:
        q = Q(name__contains=role_name)
    total, role_objs = await ROLE_CRUD.list(
        page=page, page_size=page_size, search=q, order=order
    )
    data = [await obj.to_dict() for obj in role_objs]
    return SuccessResponse(data=data, total=total)


@role.get("/authorized", summary="查看角色权限")
async def get_role_authorized(id: int = Query(..., description="角色ID")):
    role_obj = await ROLE_CRUD.get(id=id)
    data = await role_obj.to_dict(m2m=True)
    return SuccessResponse(data=data)


@role.post("/authorized", summary="更新角色权限")
async def update_role_authorized(role_in: RoleUpdateMenusRouters):
    role_obj = await ROLE_CRUD.get(id=role_in.id)
    await ROLE_CRUD.update_roles(role=role_obj, menu_ids=role_in.menu_ids, router_infos=role_in.router_infos)
    return SuccessResponse()
