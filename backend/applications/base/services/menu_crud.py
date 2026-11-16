# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : menu_crud.py
@DateTime: 2025/2/19 12:48
"""
import traceback
from typing import Any, Dict, List, Optional

from tortoise.exceptions import IntegrityError

from backend.applications.base.models.menu_model import Menu
from backend.applications.base.schemas.menu_schema import MenuCreate, MenuUpdate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import DataAlreadyExistsException, NotFoundException, ParameterException

# 菜单对外序列化口径: 主键统一为 menu_id(前端树/表单/路由侧边栏均按该字段取值)
MENU_REPLACE_FIELDS: Dict[str, str] = {"id": "menu_id"}


class MenuCrud(ScaffoldCrud[Menu, MenuCreate, MenuUpdate]):

    def __init__(self):
        super().__init__(model=Menu)

    async def get_by_id(self, menu_id: int, on_error: bool = True, **kwargs) -> Optional[Menu]:
        """
        根据主键ID查询菜单。

        :param menu_id: 菜单ID
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 菜单实例或None
        """
        if not menu_id:
            error_message: str = "查询菜单信息失败, 参数[menu_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.get_or_none(id=menu_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询菜单信息失败, 记录[id={menu_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    @staticmethod
    async def serialize_menu(instance: Menu) -> Dict[str, Any]:
        """
        按菜单对外口径序列化，主键对外为menu_id。

        :param instance: 菜单实例
        :return: 响应字典
        """
        return await instance.to_dict(replace_fields=MENU_REPLACE_FIELDS)

    async def get_user_menu_tree(self, is_admin: bool, role_ids: List[int]) -> List[Dict]:
        """
        查询用户可见菜单并组装两级树。

        :param is_admin: 是否为超管或管理员角色
        :param role_ids: 用户角色ID列表
        :return: 菜单树，节点主键字段为 menu_id，节点按 order 与 id 排序
        """
        if is_admin:
            menus: List[Menu] = await self.model.all().order_by("order", "id")
        elif role_ids:
            # 多角色菜单一次查出并去重，避免按角色逐条查询造成 N+1
            menus = await self.model.filter(
                role_menus__id__in=role_ids
            ).distinct().order_by("order", "id")
        else:
            menus = []
        children_map: Dict[int, List[Menu]] = {}
        for menu in menus:
            children_map.setdefault(menu.parent_id, []).append(menu)
        tree: List[Dict] = []
        for parent_menu in children_map.get(0, []):
            parent_menu_dict = await parent_menu.to_dict(replace_fields={"id": "menu_id"})
            parent_menu_dict["children"] = [
                await menu.to_dict(replace_fields={"id": "menu_id"})
                for menu in children_map.get(parent_menu.id, [])
            ]
            tree.append(parent_menu_dict)
        return tree

    async def get_menu_tree(self) -> List[Dict]:
        """
        构建全量菜单树，从顶级菜单递归展开。

        :return: 顶级菜单节点列表，每节点含children，节点主键字段为menu_id
        """
        # 一次查全量后按parent_id分桶组装，避免逐层级递归查库造成N+1
        all_menus: List[Menu] = await self.model.all().order_by("order", "id")
        children_map: Dict[int, List[Dict]] = {}
        for menu in all_menus:
            node: Dict = await menu.to_dict(replace_fields={"id": "menu_id"})
            node["children"] = children_map.setdefault(menu.id, [])
            children_map.setdefault(menu.parent_id, []).append(node)
        return children_map.get(0, [])

    async def get_by_menu_path(self, path: str, on_error: bool = False, **kwargs) -> Optional[Menu]:
        """
        根据菜单路径查询单条菜单。

        :param path: 菜单路径
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 菜单实例或None
        """
        if not path:
            error_message: str = "查询菜单信息失败, 参数[path]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.model.filter(path=path, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询菜单信息失败, 记录[path={path}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def create_menu(self, menu_in: MenuCreate) -> Menu:
        """
        创建菜单：校验name/path与同级path唯一性后落库。

        :param menu_in: 新增菜单入参
        :return: 新建的菜单实例
        """
        name = menu_in.name
        path = menu_in.path
        parent_id = menu_in.parent_id
        instances = await self.get_by_conditions(only_one=True, on_error=False, name=name, path=path)
        if instances:
            error_message: str = f"新增菜单信息失败, 记录[name={name}, path={path}]已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)
        # 同级path唯一：前端路由全路径由父path拼接，同级重复path会导致后注册路由不可达
        sibling = await self.get_by_conditions(only_one=True, on_error=False, parent_id=parent_id, path=path)
        if sibling:
            error_message: str = f"新增菜单信息失败, 同级菜单[parent_id={parent_id}]下路径[path={path}]已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        try:
            instance = await self.create(menu_in)
        except IntegrityError as e:
            # 并发建同名同路径/同级同路径：预校验会同时通过，靠唯一索引收敛为业务已存在
            error_message: str = f"新增菜单信息失败, 记录[name={name}, path={path}]或同级路径与已有记录冲突"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataAlreadyExistsException(message=error_message) from e
        return instance

    async def delete_menu(self, menu_id: int, **kwargs) -> Menu:
        """
        根据ID物理删除单个菜单，存在子菜单时拒绝删除。

        :param menu_id: 菜单ID
        :param kwargs: 额外查询条件
        :return: 被删除的菜单实例
        :raises ParameterException: 存在子菜单
        """
        instance = await self.get_by_id(menu_id=menu_id, on_error=True, **kwargs)
        child_count: int = await self.model.filter(parent_id=instance.id).count()
        if child_count > 0:
            error_message: str = f"删除菜单信息失败, 菜单[name={instance.name}]存在{child_count}个子菜单, 无法直接删除"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        await instance.delete()
        return instance

    async def update_menu(self, menu_in: MenuUpdate) -> Menu:
        """
        根据菜单ID更新菜单字段。

        :param menu_in: 更新入参
        :return: 更新后的菜单实例
        """
        menu_id: int = menu_in.id
        menu_if: dict = menu_in.model_dump(exclude_none=True)
        current = await self.get_by_id(menu_id=menu_id, on_error=True)
        # 换父或改路径都要重查同级唯一，否则会把菜单移到已有同path的目录下
        target_parent = menu_if.get("parent_id", current.parent_id)
        target_path = menu_if.get("path", current.path)
        sibling = await self.model.filter(parent_id=target_parent, path=target_path).exclude(id=menu_id).first()
        if sibling:
            error_message: str = f"更新菜单信息失败, 同级菜单[parent_id={target_parent}]下路径[path={target_path}]已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)
        try:
            instance = await self.update(id=menu_id, obj_in=menu_if)
        except IntegrityError as e:
            # 并发改名/改路径撞唯一索引与创建同口径，返回已存在而非服务异常
            error_message: str = f"更新菜单信息失败, 记录[id={menu_id}]的菜单名+路径或同级路径与已有记录冲突"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataAlreadyExistsException(message=error_message) from e

        return instance
