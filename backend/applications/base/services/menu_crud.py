# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : menu_crud.py
@DateTime: 2025/2/19 12:48
"""
from typing import List, Optional

from tortoise.exceptions import DoesNotExist

from backend.applications.base.models.menu_model import Menu
from backend.applications.base.schemas.menu_schema import MenuCreate, MenuUpdate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import DataAlreadyExistsException, NotFoundException, ParameterException


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


class MenuCrud(ScaffoldCrud[Menu, MenuCreate, MenuUpdate]):
    def __init__(self):
        super().__init__(model=Menu)

    async def get_by_id(self, menu_id: int, on_error: bool = True, **kwargs) -> Optional[Menu]:
        if not menu_id:
            error_message: str = "查询菜单信息失败, 参数(menu_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.get_or_none(id=menu_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询菜单信息失败, 菜单(id={menu_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_menu_path(self, path: str, on_error: bool = False, **kwargs) -> Optional[Menu]:
        if not path:
            error_message: str = "查询菜单信息失败, 参数(path)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.model.filter(path=path, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询菜单信息失败, 菜单(path={path})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def create_menu(self, menu_in: MenuCreate) -> Menu:
        name = menu_in.name
        path = menu_in.path
        instances = await self.get_by_conditions(only_one=True, on_error=False, name=name, path=path)
        if instances:
            raise DataAlreadyExistsException(message=f"菜单(name={name},path={path})信息已存在")

        instance = await self.create(menu_in)
        return instance

    async def delete_menu(self, menu_id: int, **kwargs) -> Menu:
        instance = await self.get_by_id(menu_id=menu_id, on_error=True, **kwargs)
        await instance.delete()
        return instance

    async def update_menu(self, menu_in: MenuUpdate) -> Menu:
        menu_id: int = menu_in.id
        menu_if: dict = menu_in.model_dump(exclude_none=True)
        try:
            instance = await self.update(id=menu_id, obj_in=menu_if)
        except DoesNotExist as e:
            raise NotFoundException(message=f"菜单(id={menu_id})信息不存在")

        return instance

    async def get_menu_tree(self, name: str = "", menu_type: str = "") -> List[dict]:
        all_menus = await self.model.all().order_by("order")
        menu_dicts: dict[int, dict] = {}
        for menu in all_menus:
            menu_dicts[menu.id] = await menu.to_dict()
            menu_dicts[menu.id]["children"] = []

        roots: List[dict] = []
        for menu in all_menus:
            node = menu_dicts[menu.id]
            if menu.parent_id == 0:
                roots.append(node)
            else:
                parent = menu_dicts.get(menu.parent_id)
                if parent is not None:
                    parent["children"].append(node)

        nk = name.strip() if name else ""
        tk = menu_type.strip() if menu_type else ""
        if nk or tk:
            roots = _filter_menu_tree(roots, name_kw=nk, type_kw=tk)
        return roots


MENU_CRUD = MenuCrud()
