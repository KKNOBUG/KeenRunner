# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : menu_view.py
@DateTime: 2025/2/19 12:46
"""
import traceback

from fastapi import APIRouter, Body, Query

from backend.applications.base.dependencies import DependMenuServices
from backend.applications.base.schemas.menu_schema import MenuCreate, MenuUpdate
from backend.applications.base.services.menu_crud import MenuCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    ParameterException,
    NotFoundException,
    DataAlreadyExistsException,
    DataBaseStorageException,
)
from backend.core.responses import (
    NotFoundResponse,
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    DataAlreadyExistsResponse,
    DataBaseStorageResponse,
)

menu = APIRouter()


def _norm_menu_type(v) -> str:
    """
    将菜单类型归一为字符串，兼容枚举与字符串存储。

    :param v: 原始菜单类型
    :return: 归一后的菜单类型字符串，空值归一为空串
    """
    if v is None:
        return ""
    if hasattr(v, "value"):
        return str(v.value)
    return str(v)


def _filter_menu_tree(nodes: list, *, name_kw: str, type_kw: str) -> list:
    """
    根据名称子串与类型筛选菜单树，节点自身或子树命中均保留祖先链路。

    :param nodes: 菜单树节点列表，每项含 children
    :param name_kw: 菜单名称关键字，空串表示不筛选
    :param type_kw: 菜单类型关键字，空串表示不筛选
    :return: 筛选后的菜单树，节点结构保持不变
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


@menu.post("/create", summary="新增菜单", description="新增菜单信息")
async def create_menu(
        menu_in: MenuCreate = Body(..., description="菜单信息"),
        menu_crud: MenuCrud = DependMenuServices,
):
    """
    新增菜单。

    :param menu_in: 菜单入参（名称、类型、路径、组件、父级等）
    :param menu_crud: 菜单 CRUD 服务
    :return: 统一响应，成功时 data 为新增后的菜单信息，主键字段为 menu_id，total 为 1
    """
    try:
        instance = await menu_crud.create_menu(menu_in=menu_in)
        data = await menu_crud.serialize_menu(instance)
        return SuccessResponse(message="新增成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法新增菜单，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [name={menu_in.name}, menu_type={menu_in.menu_type}, path={menu_in.path}, parent_id={menu_in.parent_id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@menu.delete("/delete", summary="删除菜单", description="根据id删除菜单信息")
async def delete_menu(
        id: int = Query(..., description="菜单id"),
        menu_crud: MenuCrud = DependMenuServices,
):
    """
    根据 ID 删除菜单。

    :param id: 菜单 ID
    :param menu_crud: 菜单 CRUD 服务
    :return: 统一响应，成功时 data 为被删除的菜单信息，主键字段为 menu_id，total 为 1
    """
    try:
        instance = await menu_crud.delete_menu(menu_id=id)
        data = await menu_crud.serialize_menu(instance)
        return SuccessResponse(message="删除成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法删除菜单，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [menu_id={id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@menu.post("/update", summary="更新菜单", description="根据id更新菜单信息")
async def update_menu(
        menu_in: MenuUpdate = Body(..., description="菜单信息"),
        menu_crud: MenuCrud = DependMenuServices,
):
    """
    根据 ID 更新菜单。

    :param menu_in: 菜单入参，id 指定待更新记录
    :param menu_crud: 菜单 CRUD 服务
    :return: 统一响应，成功时 data 为更新后的菜单信息，主键字段为 menu_id，total 为 1
    """
    try:
        instance = await menu_crud.update_menu(menu_in=menu_in)
        data = await menu_crud.serialize_menu(instance)
        return SuccessResponse(message="更新成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法更新菜单，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [menu_id={menu_in.id}, name={menu_in.name}, path={menu_in.path}, parent_id={menu_in.parent_id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@menu.post("/list", summary="查询菜单列表", description="根据name或type查询菜单信息")
async def list_menu(
        name: str = Query(default="", description="菜单名称(子串匹配)"),
        menu_type: str = Query(default="", description="菜单类型：catalog/menu"),
        menu_crud: MenuCrud = DependMenuServices,
):
    """
    查询菜单树并按名称、类型可选筛选。

    :param name: 菜单名称，子串匹配
    :param menu_type: 菜单类型（catalog/menu），等值匹配
    :param menu_crud: 菜单 CRUD 服务
    :return: 统一响应，成功时 data 为菜单树，节点主键字段为 menu_id，total 为筛选后的顶级节点数
    """
    try:
        res_menu = await menu_crud.get_menu_tree()
        nk = name.strip() if name else ""
        tk = menu_type.strip() if menu_type else ""
        if nk or tk:
            res_menu = _filter_menu_tree(res_menu, name_kw=nk, type_kw=tk)
        return SuccessResponse(message="查询成功", data=res_menu, total=len(res_menu))
    except Exception:
        error_message: str = "暂时无法查询菜单列表，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [name={name}, menu_type={menu_type}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@menu.get("/get", summary="查询菜单", description="根据id查询菜单信息")
async def get_menu(
        menu_id: int = Query(..., description="菜单id"),
        menu_crud: MenuCrud = DependMenuServices,
):
    """
    根据 ID 查询单条菜单。

    :param menu_id: 菜单 ID
    :param menu_crud: 菜单 CRUD 服务
    :return: 统一响应，成功时 data 为菜单信息，主键字段为 menu_id，total 为 1
    """
    try:
        result = await menu_crud.get_by_id(menu_id=menu_id, on_error=True)
        data = await menu_crud.serialize_menu(result)
        return SuccessResponse(message="查询成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法查询菜单，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [menu_id={menu_id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)
