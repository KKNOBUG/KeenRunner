# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : role_crud.py
@DateTime: 2025/2/19 23:08
"""
from typing import Optional, List

from backend.applications.base.models.router_model import Router
from backend.applications.base.models.menu_model import Menu
from backend.applications.base.models.role_model import Role
from backend.applications.base.schemas.role_schema import (
    BaseRole,
    RoleCreate,
    RoleUpdate,
    RoleUpdateMenusRouters
)
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException


class RoleCrud(ScaffoldCrud[Role, RoleCreate, RoleUpdate]):
    def __init__(self):
        super().__init__(model=Role)

    async def get_by_id(self, role_id: int) -> Optional[Role]:
        return await self.model.filter(id=role_id).first()

    async def get_by_code(self, code: str) -> Optional[Role]:
        return await self.model.filter(code=code).first()

    async def get_by_name(self, name: str) -> Optional[Role]:
        return await self.model.filter(name=name).first()

    async def is_exist(self, name: str) -> bool:
        return await self.model.filter(name=name).exists()

    async def create_role(self, role_in: RoleCreate) -> Role:
        code = role_in.code
        name = role_in.name
        instances = await self.model.filter(code=code, name=name).all()
        if instances:
            raise DataAlreadyExistsException(message=f"角色(code={code},name={name})信息已存在")

        instance = await self.create(role_in)
        return instance

    @classmethod
    async def update_roles(cls, role: Role, menu_ids: List[int], router_infos: List[dict]) -> None:
        await role.menus.clear()
        for menu_id in menu_ids:
            menu_obj = await Menu.filter(id=menu_id).first()
            await role.menus.add(menu_obj)

        await role.routers.clear()
        for item in router_infos:
            router_obj = await Router.filter(path=item.get("path"), method=item.get("method")).first()
            await role.routers.add(router_obj)


ROLE_CRUD = RoleCrud()
