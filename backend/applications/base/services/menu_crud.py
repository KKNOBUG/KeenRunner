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
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException


class MenuCrud(ScaffoldCrud[Menu, MenuCreate, MenuUpdate]):
    def __init__(self):
        super().__init__(model=Menu)

    async def get_by_id(self, menu_id: int) -> Optional[Menu]:
        return await self.model.filter(id=menu_id).first()

    async def get_by_menu_path(self, path: str) -> Optional[Menu]:
        return await self.model.filter(path=path).first()

    async def create_menu(self, menu_in: MenuCreate) -> Menu:
        name = menu_in.name
        path = menu_in.path
        instances = await self.model.filter(name=name, path=path).all()
        if instances:
            raise DataAlreadyExistsException(message=f"菜单(name={name},path={path})信息已存在")

        instance = await self.create(menu_in)
        return instance

    async def delete_menu(self, menu_id: int) -> Menu:
        instance = await self.query(menu_id)
        if not instance:
            raise NotFoundException(message=f"菜单(id={menu_id})信息不存在")

        await instance.delete()
        data = await instance.to_dict()
        return data

    async def update_menu(self, menu_in: MenuUpdate) -> Menu:
        menu_id: int = menu_in.id
        menu_if: dict = {
            key: value for key, value in menu_in.dict().items()
            if value is not None
        }
        try:
            instance = await self.update(id=menu_id, obj_in=menu_if)
        except DoesNotExist as e:
            raise NotFoundException(message=f"菜单(id={menu_id})信息不存在")

        return instance


MENU_CRUD = MenuCrud()
