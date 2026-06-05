# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : menu_view.py
@DateTime: 2025/2/19 12:46
"""

from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend.applications.base.schemas.menu_schema import MenuCreate, MenuUpdate, MenuSelect
from backend.applications.base.services.menu_crud import MENU_CRUD
from backend.core.exceptions import ParameterException, NotFoundException
from backend.core.responses import NotFoundResponse, SuccessResponse, FailureResponse, ParameterResponse

menu = APIRouter()


@menu.post("/list", summary="查看菜单列表")
async def list_menu(
        name: str = Query(default="", description="菜单名称（子串匹配）"),
        menu_type: str = Query(default="", description="菜单类型：catalog / menu"),
):
    res_menu = await MENU_CRUD.get_menu_tree(name=name, menu_type=menu_type)
    return SuccessResponse(message="查询成功", data=res_menu, total=len(res_menu))


@menu.post("/search", summary="查询菜单列表", description="支持分页按条件查询菜单列表信息（Body）")
async def search_menu(menu_in: MenuSelect = Body()):
    q = Q()
    if menu_in.name:
        q &= Q(name__contains=menu_in.name)
    if menu_in.menu_type:
        q &= Q(menu_type=menu_in.menu_type)
    if menu_in.path:
        q &= Q(path__contains=menu_in.path)
    if menu_in.parent_id is not None:
        q &= Q(parent_id=menu_in.parent_id)
    if menu_in.is_hidden is not None:
        q &= Q(is_hidden=menu_in.is_hidden)

    total, instances = await MENU_CRUD.list(
        page=menu_in.page, page_size=menu_in.page_size, search=q, order=menu_in.order
    )
    data = [await obj.to_dict() for obj in instances]
    if data:
        menu_ids = [item["id"] for item in data]
        parent_ids_with_children = set(
            await MENU_CRUD.model.filter(parent_id__in=menu_ids).values_list("parent_id", flat=True)
        )
        for item in data:
            item["has_children"] = item["id"] in parent_ids_with_children
    return SuccessResponse(message="查询成功", data=data, total=total)


@menu.get("/get", summary="查看菜单", description="根据id查询菜单信息")
async def get_menu(menu_id: int = Query(..., description="菜单id")):
    try:
        result = await MENU_CRUD.get_by_id(menu_id=menu_id, on_error=True)
        return SuccessResponse(message="查询成功", data=result, total=1)
    except ParameterException as e:
        return ParameterResponse(message=e.message)
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        return FailureResponse(message=f"查询失败，异常描述:{e}")


@menu.post("/create", summary="创建菜单")
async def create_menu(menu_in: MenuCreate):
    try:
        data = await MENU_CRUD.create_menu(menu_in=menu_in)
        return SuccessResponse(message="新增成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=e.message)
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述:{e}")


@menu.post("/update", summary="更新菜单", description="根据id更新菜单信息")
async def update_menu(menu_in: MenuUpdate):
    try:
        data = await MENU_CRUD.update_menu(menu_in=menu_in)
        return SuccessResponse(message="更新成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        return FailureResponse(message=f"更新失败，异常描述:{e}")


@menu.delete("/delete", summary="删除菜单", description="根据id删除菜单信息")
async def delete_menu(id: int = Query(..., description="菜单id")):
    child_menu_count = await MENU_CRUD.model.filter(parent_id=id).count()
    if child_menu_count > 0:
        return FailureResponse(message="不能删除带有子菜单的菜单")
    try:
        instance = await MENU_CRUD.delete_menu(menu_id=id)
        data = await instance.to_dict()
        return SuccessResponse(message="删除成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=e.message)
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
