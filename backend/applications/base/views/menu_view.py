# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : menu_view.py
@DateTime: 2025/2/19 12:46
"""
from fastapi import APIRouter, Query

from backend.applications.base.schemas.menu_schema import MenuCreate, MenuUpdate
from backend.applications.base.services.menu_crud import MENU_CRUD
from backend.core.response.http_response import NotFoundResponse, SuccessResponse, FailureResponse

menu = APIRouter()


@menu.post("/list", summary="查看菜单列表")
async def list_menu(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        order: list = Query(default=["id"], description="排序字段"),
):
    async def get_menu_with_children(menu_id: int):
        menu = await MENU_CRUD.get_by_id(menu_id=menu_id)
        if not menu:
            return NotFoundResponse(message=f"菜单(id={menu_id})信息不存在")

        menu_dict = await menu.to_dict()
        child_menus = await MENU_CRUD.model.filter(parent_id=menu_id).order_by("order")
        menu_dict["children"] = [await get_menu_with_children(child.id) for child in child_menus]
        return menu_dict

    parent_menus = await MENU_CRUD.model.filter(parent_id=0).order_by("order")
    res_menu = [await get_menu_with_children(menu.id) for menu in parent_menus]
    return SuccessResponse(data=res_menu, total=len(res_menu))


@menu.post("/get", summary="查看菜单")
async def get_menu(
        menu_id: int = Query(..., description="菜单id"),
):
    result = await MENU_CRUD.get(id=menu_id)
    return SuccessResponse(data=result)


@menu.post("/create", summary="创建菜单")
async def create_menu(
        menu_in: MenuCreate,
):
    data = await MENU_CRUD.create(obj_in=menu_in)
    return SuccessResponse(data=data)


@menu.post("/update", summary="更新菜单")
async def update_menu(
        menu_in: MenuUpdate,
):
    data = await MENU_CRUD.update(id=menu_in.id, obj_in=menu_in)
    return SuccessResponse(data=data)


@menu.post("/delete", summary="删除菜单")
async def delete_menu(
        id: int = Query(..., description="菜单id"),
):
    child_menu_count = await MENU_CRUD.model.filter(parent_id=id).count()
    if child_menu_count > 0:
        return FailureResponse(message="不能删除带有子菜单的菜单")
    await MENU_CRUD.remove(id=id)
    return SuccessResponse(data="Deleted Success")


