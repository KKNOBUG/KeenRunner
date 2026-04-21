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
from backend.core.responses import NotFoundResponse, SuccessResponse, FailureResponse

menu = APIRouter()


def _norm_menu_type(v) -> str:
    if v is None:
        return ""
    if hasattr(v, "value"):
        return str(v.value)
    return str(v)


def _filter_menu_tree(nodes: list, *, name_kw: str, type_kw: str) -> list:
    """按名称子串、类型筛选树：节点自身命中或子树有命中则保留。"""
    if not name_kw and not type_kw:
        return nodes
    out = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        raw_children = node.get("children") or []
        if isinstance(raw_children, dict):
            raw_children = [raw_children]
        children = _filter_menu_tree(list(raw_children), name_kw=name_kw, type_kw=type_kw)
        nm = node.get("name") or ""
        mt = _norm_menu_type(node.get("menu_type"))
        name_ok = (not name_kw) or (name_kw in nm)
        type_ok = (not type_kw) or (mt == type_kw)
        self_ok = name_ok and type_ok
        if self_ok or children:
            out.append({**node, "children": children})
    return out


@menu.post("/list", summary="查看菜单列表")
async def list_menu(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        order: list = Query(default=["id"], description="排序字段"),
        name: str = Query(default="", description="菜单名称（子串匹配）"),
        menu_type: str = Query(default="", description="菜单类型：catalog / menu"),
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
    res_menu = [m for m in res_menu if isinstance(m, dict)]
    nk = name.strip() if name else ""
    tk = menu_type.strip() if menu_type else ""
    if nk or tk:
        res_menu = _filter_menu_tree(res_menu, name_kw=nk, type_kw=tk)
    return SuccessResponse(data=res_menu, total=len(res_menu))


@menu.get("/get", summary="查看菜单", description="根据id查询菜单信息")
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


@menu.post("/update", summary="更新菜单", description="根据id更新菜单信息")
async def update_menu(
        menu_in: MenuUpdate,
):
    data = await MENU_CRUD.update(id=menu_in.id, obj_in=menu_in)
    return SuccessResponse(data=data)


@menu.delete("/delete", summary="删除菜单", description="根据id删除菜单信息")
async def delete_menu(
        id: int = Query(..., description="菜单id"),
):
    child_menu_count = await MENU_CRUD.model.filter(parent_id=id).count()
    if child_menu_count > 0:
        return FailureResponse(message="不能删除带有子菜单的菜单")
    instance = await MENU_CRUD.remove(id=id)
    data = await instance.to_dict()
    return SuccessResponse(data=data)
