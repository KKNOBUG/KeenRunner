# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : role_crud.py
@DateTime: 2025/2/19 23:08
"""
from typing import List, Optional, Dict, Any

from tortoise.exceptions import DoesNotExist

from backend.applications.base.models.menu_model import Menu
from backend.applications.base.models.role_model import Role
from backend.applications.base.models.router_model import Router
from backend.applications.base.schemas.role_schema import (
    RoleCreate,
    RoleUpdate
)
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import DataAlreadyExistsException, ParameterException, NotFoundException


class RoleCrud(ScaffoldCrud[Role, RoleCreate, RoleUpdate]):
    def __init__(self):
        super().__init__(model=Role)

    async def get_by_id(self, role_id: int, on_error: bool = False, is_active: bool = True) -> Optional[Role]:
        if not role_id:
            error_message: str = "查询角色信息失败, 参数(role_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        kwargs: Dict[str, Any] = {"id": role_id}
        if is_active:
            kwargs["state__not"] = 1
        instance = await self.model.filter(**kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询角色信息失败, 角色(id={role_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, role_code: str, on_error: bool = False, is_active: bool = True) -> Optional[Role]:
        if not role_code:
            error_message: str = "查询角色信息失败, 参数(role_code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        kwargs: Dict[str, Any] = {"code": role_code}
        if is_active:
            kwargs["state__not"] = 1
        instance = await self.model.filter(**kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询角色信息失败, 角色(code={role_code})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_name(self, role_name: str, on_error: bool = False, is_active: bool = True) -> Optional[Role]:
        if not role_name:
            error_message: str = "查询角色信息失败, 参数(role_name)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        kwargs: Dict[str, Any] = {"name": role_name}
        if is_active:
            kwargs["state__not"] = 1
        instance = await self.model.filter(**kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询角色信息失败, 角色(name={role_name})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def is_exist(self, name: str) -> bool:
        return await self.model.filter(name=name).exists()

    async def create_role(self, role_in: RoleCreate, created_user: Optional[str] = None) -> Role:
        code = role_in.code
        name = role_in.name
        instances = await self.model.filter(code=code, name=name).all()
        if instances:
            raise DataAlreadyExistsException(message=f"角色(code={code},name={name})信息已存在")

        instance = await self.create(role_in)
        if created_user is not None:
            instance.created_user = created_user
            await instance.save(update_fields=["created_user"])
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

    async def delete_roles(
            self,
            role_ids: Optional[List[int]] = None,
            role_codes: Optional[List[str]] = None,
    ) -> int:
        """按 ID 或 code 列表删除角色（物理删除，与单笔 remove 一致）。"""
        n = 0
        if role_ids:
            for rid in role_ids:
                try:
                    await self.remove(id=int(rid))
                    n += 1
                except (DoesNotExist, Exception):
                    continue
        elif role_codes:
            for code in role_codes:
                obj = await self.get_by_code(role_code=code)
                if obj:
                    try:
                        await self.remove(id=obj.id)
                        n += 1
                    except Exception:
                        continue
        return n


ROLE_CRUD = RoleCrud()
