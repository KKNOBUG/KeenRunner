# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : menu_view.py
@DateTime: 2025/2/19 12:46
"""

from fastapi import APIRouter, Query, Depends

from backend.applications.base.dependencies import get_menu_crud
from backend.applications.base.schemas.menu_schema import MenuCreate, MenuUpdate
from backend.applications.base.services.menu_crud import MenuCrud
from backend.core.exceptions import ParameterException, NotFoundException
from backend.core.responses import NotFoundResponse, SuccessResponse, FailureResponse, ParameterResponse

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
        name: str = Query(default="", description="菜单名称（子串匹配）"),
        menu_type: str = Query(default="", description="菜单类型：catalog / menu"),
        menu_crud: MenuCrud = Depends(get_menu_crud),
):
    async def get_menu_with_children(menu_id: int):
        menu = await menu_crud.get_by_id(menu_id=menu_id, on_error=False)
        if not menu:
            return NotFoundResponse(message=f"菜单(id={menu_id})信息不存在")

        menu_dict = await menu.to_dict()
        child_menus = await menu_crud.model.filter(parent_id=menu_id).order_by("order")
        menu_dict["children"] = [await get_menu_with_children(child.id) for child in child_menus]
        return menu_dict

    parent_menus = await menu_crud.model.filter(parent_id=0).order_by("order")
    res_menu = [await get_menu_with_children(menu.id) for menu in parent_menus]
    res_menu = [m for m in res_menu if isinstance(m, dict)]
    nk = name.strip() if name else ""
    tk = menu_type.strip() if menu_type else ""
    if nk or tk:
        res_menu = _filter_menu_tree(res_menu, name_kw=nk, type_kw=tk)
    return SuccessResponse(message="查询成功", data=res_menu, total=len(res_menu))


@menu.get("/get", summary="查看菜单", description="根据id查询菜单信息")
async def get_menu(
        menu_id: int = Query(..., description="菜单id"),
        menu_crud: MenuCrud = Depends(get_menu_crud),
):
    try:
        result = await menu_crud.get_by_id(menu_id=menu_id, on_error=True)
        return SuccessResponse(message="查询成功", data=result, total=1)
    except ParameterException as e:
        return ParameterResponse(message=e.message)
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        return FailureResponse(message=f"查询失败，异常描述:{e}")


@menu.post("/create", summary="创建菜单")
async def create_menu(
        menu_in: MenuCreate,
        menu_crud: MenuCrud = Depends(get_menu_crud),
):
    try:
        instance = await menu_crud.create_menu(menu_in=menu_in)
        data = await instance.to_dict()
        return SuccessResponse(message="新增成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=e.message)
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述:{e}")


@menu.post("/update", summary="更新菜单", description="根据id更新菜单信息")
async def update_menu(
        menu_in: MenuUpdate,
        menu_crud: MenuCrud = Depends(get_menu_crud),
):
    try:
        instance = await menu_crud.update_menu(menu_in=menu_in)
        data = await instance.to_dict()
        return SuccessResponse(message="更新成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        return FailureResponse(message=f"更新失败，异常描述:{e}")


@menu.delete("/delete", summary="删除菜单", description="根据id删除菜单信息")
async def delete_menu(
        id: int = Query(..., description="菜单id"),
        menu_crud: MenuCrud = Depends(get_menu_crud),
):
    child_menu_count = await menu_crud.model.filter(parent_id=id).count()
    if child_menu_count > 0:
        return FailureResponse(message="不能删除带有子菜单的菜单")
    try:
        instance = await menu_crud.delete_menu(menu_id=id)
        data = await instance.to_dict()
        return SuccessResponse(message="删除成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=e.message)
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
