# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : role_crud.py
@DateTime: 2025/2/19 23:08
"""
from typing import Optional, List

from backend.applications.base.models.role_model import Role
from backend.applications.base.schemas.role_schema import (
    BaseRole,
    RoleCreate,
    RoleUpdate,
    RoleUpdateMenusApis
)
from backend.applications.base.services.scaffold import ScaffoldCrud


class RoleCrud(ScaffoldCrud[Role, RoleCreate, RoleUpdate]):
    def __init__(self):
        super().__init__(model=Role)

    async def get_by_id(self, role_id: int) -> Optional[Role]:
        return await self.model.filter(id=role_id).first()

    async def get_by_code(self, code: str) -> Optional[Role]:
        return await self.model.filter(code=code).first()

    async def get_by_name(self, name: str) -> Optional[Role]:
        return await self.model.filter(name=name).first()


ROLE_CRUD = RoleCrud()
