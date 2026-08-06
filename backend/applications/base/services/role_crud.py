# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : role_crud.py
@DateTime: 2025/2/19 23:08
"""
from typing import List, Optional

from tortoise.exceptions import DoesNotExist

from backend.applications.base.models.menu_model import Menu
from backend.applications.base.models.role_model import Role
from backend.applications.base.models.router_model import Router
from backend.applications.base.schemas.role_schema import RoleCreate, RoleUpdate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import DataAlreadyExistsException, ParameterException, NotFoundException

class RoleCrud(ScaffoldCrud[Role, RoleCreate, RoleUpdate]):

    def __init__(self):
        super().__init__(model=Role)

    async def get_by_id(self, role_id: int, on_error: bool = False, **kwargs) -> Optional[Role]:
        """
        根据主键ID查询角色。

        :param role_id: 角色ID
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 角色实例或None
        :raises ParameterException: role_id为空
        :raises NotFoundException: on_error为True且角色不存在
        """
        if not role_id:
            error_message: str = "查询角色信息失败, 参数[role_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.get_or_none(id=role_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询角色信息失败, 记录[id={role_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, role_code: str, on_error: bool = False, **kwargs) -> Optional[Role]:
        """
        根据角色编码查询单条角色。

        :param role_code: 角色编码
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 角色实例或None
        :raises ParameterException: role_code为空
        :raises NotFoundException: on_error为True且角色不存在
        """
        if not role_code:
            error_message: str = "查询角色信息失败, 参数[role_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.get_by_conditions(only_one=True, on_error=False, code=role_code, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询角色信息失败, 记录[code={role_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_name(self, role_name: str, on_error: bool = False, **kwargs) -> Optional[Role]:
        """
        根据角色名称查询单条角色。

        :param role_name: 角色名称
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 角色实例或None
        :raises ParameterException: role_name为空
        :raises NotFoundException: on_error为True且角色不存在
        """
        if not role_name:
            error_message: str = "查询角色信息失败, 参数[role_name]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.get_by_conditions(only_one=True, on_error=False, name=role_name, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询角色信息失败, 记录[name={role_name}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def is_exist(self, name: str, **kwargs) -> bool:
        """
        判断指定名称的角色是否存在。

        :param name: 角色名称
        :param kwargs: 额外过滤条件
        :return: 存在返回True，否则False
        """
        return await self.model.filter(name=name, **kwargs).exists()

    async def create_role(self, role_in: RoleCreate, created_user: Optional[str] = None) -> Role:
        """
        创建角色：校验code/name唯一性后落库，可选写入创建人。

        :param role_in: 新增角色入参
        :param created_user: 创建人；非None时覆盖写入created_user
        :return: 新建的角色实例
        :raises DataAlreadyExistsException: code或name已存在
        """
        code = role_in.code
        name = role_in.name
        instances = await self.get_by_conditions(only_one=True, on_error=False, code=code, name=name)
        if instances:
            error_message: str = f"创建角色信息失败, 记录[code={code}, name={name}]信息已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        instance = await self.create(role_in)
        if created_user is not None:
            instance.created_user = created_user
            await instance.save(update_fields=["created_user"])
        return instance

    async def update_roles(self, role: Role, menu_ids: List[int], router_infos: List[dict]) -> None:
        """
        重置角色的菜单与路由关联：先清空再根据入参重新绑定。

        :param role: 角色实例
        :param menu_ids: 菜单ID列表
        :param router_infos: 路由信息列表，每项含path、method
        :return: None
        """
        await role.menus.clear()
        for menu_id in menu_ids:
            menu_obj = await Menu.filter(id=menu_id).first()
            if menu_obj:
                await role.menus.add(menu_obj)

        await role.routers.clear()
        for item in router_infos:
            router_obj = await Router.filter(path=item.get("path"), method=item.get("method")).first()
            if router_obj:
                await role.routers.add(router_obj)

    async def delete_role(self, role_id: int, **kwargs) -> Role:
        """
        根据ID物理删除单个角色。

        :param role_id: 角色ID
        :param kwargs: 额外查询条件
        :return: 被删除的角色实例
        :raises NotFoundException: 角色不存在
        """
        instance = await self.get_by_id(role_id=role_id, on_error=True, **kwargs)
        await instance.delete()
        return instance

    async def delete_roles(self, role_ids: Optional[List[int]] = None, role_codes: Optional[List[str]] = None) -> int:
        """
        根据ID或code列表物理删除角色。

        :param role_ids: 角色ID列表
        :param role_codes: 角色编码列表
        :return: 实际删除的记录数
        """
        n = 0
        if role_ids:
            for rid in role_ids:
                try:
                    await self.remove_or_error(id=int(rid))
                    n += 1
                except DoesNotExist:
                    continue
        elif role_codes:
            for code in role_codes:
                obj = await self.get_by_code(role_code=code, state__not=1)
                if obj:
                    try:
                        await self.remove_or_error(id=obj.id)
                        n += 1
                    except DoesNotExist:
                        continue
        return n
