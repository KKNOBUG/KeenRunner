# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : menu_view.py
@DateTime: 2025/2/19 12:46
"""
import traceback

from fastapi import APIRouter, Body, Query, Depends

from backend.applications.base.dependencies import get_menu_crud
from backend.applications.base.schemas.menu_schema import MenuCreate, MenuUpdate
from backend.applications.base.services.menu_crud import MenuCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    ParameterException,
    NotFoundException,
    DataAlreadyExistsException
)
from backend.core.responses import (
    NotFoundResponse,
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    DataAlreadyExistsResponse
)

menu = APIRouter()

def _norm_menu_type(v) -> str:
    """
    规范化菜单类型值。

    :param v: 原始菜单类型（可为枚举、字符串或None）
    :return: 规范化后的菜单类型字符串
    """
    if v is None:
        return ""
    if hasattr(v, "value"):
        return str(v.value)
    return str(v)

def _filter_menu_tree(nodes: list, *, name_kw: str, type_kw: str) -> list:
    """
    根据名称子串、类型筛选菜单树：节点自身命中或子树有命中则保留。

    :param nodes: 菜单树节点列表
    :param name_kw: 菜单名称关键字
    :param type_kw: 菜单类型关键字
    :return: 筛选后的菜单树
    """
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

@menu.post("/list", summary="查看菜单列表", description="根据name或type查询菜单信息")
async def list_menus(
        name: str = Query(default="", description="菜单名称(子串匹配)"),
        menu_type: str = Query(default="", description="菜单类型：catalog/menu"),
        menu_crud: MenuCrud = Depends(get_menu_crud),
):
    """
    查看菜单列表。

    :param name: 菜单名称（子串匹配）
    :param menu_type: 菜单类型
    :param menu_crud: 菜单CRUD服务
    :return: 统一HTTP响应
    """

    async def get_menu_with_children(menu_id: int):
        """
        递归获取菜单及其子菜单。

        :param menu_id: 菜单ID
        :return: 含 children 的菜单字典，或未找到时的响应
        """
        menu = await menu_crud.get_by_id(menu_id=menu_id, on_error=False)
        if not menu:
            return NotFoundResponse(message=f"记录[id={menu_id}]信息不存在")

        menu_dict = await menu.to_dict()
        child_menus = await menu_crud.model.filter(parent_id=menu_id).order_by("order")
        menu_dict["children"] = [await get_menu_with_children(child.id) for child in child_menus]
        return menu_dict

    try:
        parent_menus = await menu_crud.model.filter(parent_id=0).order_by("order")
        res_menu = [await get_menu_with_children(menu.id) for menu in parent_menus]
        res_menu = [m for m in res_menu if isinstance(m, dict)]
        nk = name.strip() if name else ""
        tk = menu_type.strip() if menu_type else ""
        if nk or tk:
            res_menu = _filter_menu_tree(res_menu, name_kw=nk, type_kw=tk)
        LOGGER.info(f"查询菜单列表成功, 数量: {len(res_menu)}")
        return SuccessResponse(message="查询成功", data=res_menu, total=len(res_menu))
    except Exception as e:
        LOGGER.error(f"查询菜单列表失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")

@menu.get("/get", summary="查看菜单", description="根据id查询菜单信息")
async def get_menu(
        menu_id: int = Query(..., description="菜单id"),
        menu_crud: MenuCrud = Depends(get_menu_crud),
):
    """
    查看菜单。

    :param menu_id: 菜单ID
    :param menu_crud: 菜单CRUD服务
    :return: 统一HTTP响应
    """
    try:
        result = await menu_crud.get_by_id(menu_id=menu_id, on_error=True)
        data = await result.to_dict()
        LOGGER.info(f"查询菜单成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询菜单失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")

@menu.post("/create", summary="创建菜单")
async def create_menu(
        menu_in: MenuCreate = Body(..., description="菜单信息"),
        menu_crud: MenuCrud = Depends(get_menu_crud),
):
    """
    创建菜单。

    :param menu_in: 菜单入参
    :param menu_crud: 菜单CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await menu_crud.create_menu(menu_in=menu_in)
        data = await instance.to_dict()
        LOGGER.info(f"创建菜单成功, 结果明细: {data}")
        return SuccessResponse(message="新增成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"创建菜单失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {e}")

@menu.post("/update", summary="更新菜单", description="根据id更新菜单信息")
async def update_menu(
        menu_in: MenuUpdate = Body(..., description="菜单信息"),
        menu_crud: MenuCrud = Depends(get_menu_crud),
):
    """
    更新菜单。

    :param menu_in: 菜单入参
    :param menu_crud: 菜单CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await menu_crud.update_menu(menu_in=menu_in)
        data = await instance.to_dict()
        LOGGER.info(f"更新菜单成功, 结果明细: {data}")
        return SuccessResponse(message="更新成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"更新菜单失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {e}")

@menu.delete("/delete", summary="删除菜单", description="根据id删除菜单信息")
async def delete_menu(
        id: int = Query(..., description="菜单id"),
        menu_crud: MenuCrud = Depends(get_menu_crud),
):
    """
    删除菜单。

    :param id: 菜单ID
    :param menu_crud: 菜单CRUD服务
    :return: 统一HTTP响应
    """
    child_menu_count = await menu_crud.model.filter(parent_id=id).count()
    if child_menu_count > 0:
        return FailureResponse(message="不能删除带有子菜单的菜单")
    try:
        instance = await menu_crud.delete_menu(menu_id=id)
        data = await instance.to_dict()
        LOGGER.info(f"删除菜单成功, 结果明细: {data}")
        return SuccessResponse(message="删除成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"删除菜单失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")
