# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : menu_crud.py
@DateTime: 2025/2/19 12:48
"""
from typing import Optional

from tortoise.exceptions import DoesNotExist

from backend.applications.base.models.menu_model import Menu
from backend.applications.base.schemas.menu_schema import MenuCreate, MenuUpdate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import DataAlreadyExistsException, NotFoundException, ParameterException

class MenuCrud(ScaffoldCrud[Menu, MenuCreate, MenuUpdate]):

    def __init__(self):
        super().__init__(model=Menu)

    async def get_by_id(self, menu_id: int, on_error: bool = True, **kwargs) -> Optional[Menu]:
        """
        根据主键ID查询菜单。

        :param menu_id: 菜单ID
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 菜单实例或None
        :raises ParameterException: menu_id为空
        :raises NotFoundException: on_error为True且菜单不存在
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

    async def get_by_menu_path(self, path: str, on_error: bool = False, **kwargs) -> Optional[Menu]:
        """
        根据菜单路径查询单条菜单。

        :param path: 菜单路径
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 菜单实例或None
        :raises ParameterException: path为空
        :raises NotFoundException: on_error为True且菜单不存在
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
        创建菜单：校验name/path唯一性后落库。

        :param menu_in: 新增菜单入参
        :return: 新建的菜单实例
        :raises DataAlreadyExistsException: name或path已存在
        """
        name = menu_in.name
        path = menu_in.path
        instances = await self.get_by_conditions(only_one=True, on_error=False, name=name, path=path)
        if instances:
            error_message: str = f"新增菜单信息失败, 记录[name={name}, path={path}]已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        instance = await self.create(menu_in)
        return instance

    async def delete_menu(self, menu_id: int, **kwargs) -> Menu:
        """
        根据ID物理删除单个菜单。

        :param menu_id: 菜单ID
        :param kwargs: 额外查询条件
        :return: 被删除的菜单实例
        :raises NotFoundException: 菜单不存在
        """
        instance = await self.get_by_id(menu_id=menu_id, on_error=True, **kwargs)
        await instance.delete()
        return instance

    async def update_menu(self, menu_in: MenuUpdate) -> Menu:
        """
        根据菜单ID更新菜单字段。

        :param menu_in: 更新入参
        :return: 更新后的菜单实例
        :raises NotFoundException: 菜单不存在
        """
        menu_id: int = menu_in.id
        menu_if: dict = menu_in.model_dump(exclude_none=True)
        try:
            instance = await self.update(id=menu_id, obj_in=menu_if)
        except DoesNotExist as e:
            error_message: str = f"更新菜单信息失败, 记录[id={menu_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)

        return instance
