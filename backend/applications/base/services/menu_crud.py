# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : menu_crud.py
@DateTime: 2025/2/19 12:48
"""
from typing import Optional

from backend.applications.base.models.menu_model import Menu
from backend.applications.base.schemas.router_schema import RouterCreate, RouterUpdate
from backend.applications.base.services.scaffold import ScaffoldCrud


class MenuCrud(ScaffoldCrud[Menu, RouterCreate, RouterUpdate]):
    def __init__(self):
        super().__init__(model=Menu)

    async def get_by_id(self, menu_id: int) -> Optional[Menu]:
        return await self.model.filter(id=menu_id).first()

    async def get_by_menu_path(self, path: str) -> Optional[Menu]:
        return await self.model.filter(path=path).first()


MENU_CRUD = MenuCrud()
