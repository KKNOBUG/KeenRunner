# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
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
    将菜单类型统一归一为字符串。

    兼容枚举取 value、字符串与 None（归一为空串），使筛选时可以直接比较。

    :param v: 原始菜单类型
    :return: 归一后的菜单类型字符串
    """
    if v is None:
        return ""
    if hasattr(v, "value"):
        return str(v.value)
    return str(v)


def _filter_menu_tree(nodes: list, *, name_kw: str, type_kw: str) -> list:
    """
    根据名称子串与类型筛选菜单树。

    节点自身命中或子树命中均保留，保证命中节点的祖先链路完整；无筛选条件时原样返回。

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
        menu_crud: MenuCrud = Depends(get_menu_crud),
):
    """
    新增菜单。

    :param menu_in: 菜单入参（名称、类型、路径、组件、父级等）
    :param menu_crud: 菜单 CRUD 服务
    :return: 统一响应，成功时 data 为新增后的菜单信息，主键字段为 menu_id，total 为 1
    """
    try:
        instance = await menu_crud.create_menu(menu_in=menu_in)
        data = await instance.to_dict(replace_fields={"id": "menu_id"})
        return SuccessResponse(message="新增成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception:
        error_message: str = "新增菜单失败，暂时无法完成创建，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [name={menu_in.name}, menu_type={menu_in.menu_type}, "
            f"path={menu_in.path}, parent_id={menu_in.parent_id}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@menu.delete("/delete", summary="删除菜单", description="根据id删除菜单信息")
async def delete_menu(
        id: int = Query(..., description="菜单id"),
        menu_crud: MenuCrud = Depends(get_menu_crud),
):
    """
    根据 ID 删除菜单。

    存在子菜单时拒绝删除，避免产生孤儿节点。

    :param id: 菜单 ID
    :param menu_crud: 菜单 CRUD 服务
    :return: 统一响应，成功时 data 为被删除的菜单信息，主键字段为 menu_id，total 为 1
    """
    try:
        # 子菜单预检同样纳入 try，避免查询报错时游离于统一异常处理与日志之外
        child_menu_count = await menu_crud.model.filter(parent_id=id).count()
        if child_menu_count > 0:
            return FailureResponse(message="不能删除带有子菜单的菜单")
        instance = await menu_crud.delete_menu(menu_id=id)
        data = await instance.to_dict(replace_fields={"id": "menu_id"})
        return SuccessResponse(message="删除成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "删除菜单失败，暂时无法完成删除，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [menu_id={id}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@menu.post("/update", summary="更新菜单", description="根据id更新菜单信息")
async def update_menu(
        menu_in: MenuUpdate = Body(..., description="菜单信息"),
        menu_crud: MenuCrud = Depends(get_menu_crud),
):
    """
    根据 ID 更新菜单。

    :param menu_in: 菜单入参，id 指定待更新记录
    :param menu_crud: 菜单 CRUD 服务
    :return: 统一响应，成功时 data 为更新后的菜单信息，主键字段为 menu_id，total 为 1
    """
    try:
        instance = await menu_crud.update_menu(menu_in=menu_in)
        data = await instance.to_dict(replace_fields={"id": "menu_id"})
        return SuccessResponse(message="更新成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "更新菜单失败，暂时无法完成更新，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [menu_id={menu_in.id}, name={menu_in.name}, path={menu_in.path}, parent_id={menu_in.parent_id}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@menu.post("/list", summary="查询菜单列表", description="根据name或type查询菜单信息")
async def list_menu(
        name: str = Query(default="", description="菜单名称(子串匹配)"),
        menu_type: str = Query(default="", description="菜单类型：catalog/menu"),
        menu_crud: MenuCrud = Depends(get_menu_crud),
):
    """
    查询菜单树。

    从顶级菜单递归装配 children，再可选地按名称子串与菜单类型筛选；结果中
    total 为筛选后的顶级节点数。

    :param name: 菜单名称，子串匹配
    :param menu_type: 菜单类型（catalog/menu），等值匹配
    :param menu_crud: 菜单 CRUD 服务
    :return: 统一响应，成功时 data 为菜单树，节点主键字段为 menu_id
    """

    async def get_menu_with_children(menu_id: int):
        """
        递归获取菜单及其子菜单。

        :param menu_id: 菜单 ID
        :return: 含 children 的菜单字典；记录缺失时返回 NotFoundResponse，由调用方过滤
        """
        menu = await menu_crud.get_by_id(menu_id=menu_id, on_error=False)
        if not menu:
            return NotFoundResponse(message=f"记录[id={menu_id}]信息不存在")

        menu_dict = await menu.to_dict(replace_fields={"id": "menu_id"})
        child_menus = await menu_crud.model.filter(parent_id=menu_id).order_by("order")
        menu_dict["children"] = [await get_menu_with_children(child.id) for child in child_menus]
        return menu_dict

    try:
        parent_menus = await menu_crud.model.filter(parent_id=0).order_by("order")
        res_menu = [await get_menu_with_children(menu.id) for menu in parent_menus]
        # 过滤掉记录缺失时返回的 NotFoundResponse，只保留真实菜单节点
        res_menu = [m for m in res_menu if isinstance(m, dict)]
        nk = name.strip() if name else ""
        tk = menu_type.strip() if menu_type else ""
        if nk or tk:
            res_menu = _filter_menu_tree(res_menu, name_kw=nk, type_kw=tk)
        return SuccessResponse(message="查询成功", data=res_menu, total=len(res_menu))
    except Exception:
        error_message: str = "查询菜单列表失败，暂时无法获取菜单数据，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [name={name}, menu_type={menu_type}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@menu.get("/get", summary="查询菜单", description="根据id查询菜单信息")
async def get_menu(
        menu_id: int = Query(..., description="菜单id"),
        menu_crud: MenuCrud = Depends(get_menu_crud),
):
    """
    根据 ID 查询单条菜单。

    :param menu_id: 菜单 ID
    :param menu_crud: 菜单 CRUD 服务
    :return: 统一响应，成功时 data 为菜单对象序列化结果，主键字段为 id，total 为 1
    """
    try:
        result = await menu_crud.get_by_id(menu_id=menu_id, on_error=True)
        return SuccessResponse(message="查询成功", data=result, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "查询菜单信息失败，暂时无法获取菜单数据，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [menu_id={menu_id}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)
