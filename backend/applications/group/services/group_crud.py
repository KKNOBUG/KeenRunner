# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : group_crud.py
@DateTime: 2025/2/5 13:47
"""
from typing import Optional

from tortoise.exceptions import DoesNotExist

from backend.applications.group.models.group_model import Group
from backend.applications.group.schemas.group_schema import GroupCreate, GroupUpdate
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException
from backend.services.base_crud import BaseCrud


class GroupCrud(BaseCrud[Group, GroupCreate, GroupUpdate]):
    def __init__(self):
        super().__init__(model=Group)

    async def get_by_id(self, group_id: int) -> Optional[Group]:
        return await self.model.filter(id=group_id).first()

    async def get_by_name(self, name: str) -> Optional[Group]:
        return await self.model.filter(name=name).first()

    async def get_by_initiator(self, initiator: str) -> Optional[Group]:
        return await self.model.filter(initiator=initiator).first()

    async def get_by_created_user(self, created_user: str) -> Optional[Group]:
        return await self.model.filter(created_user=created_user).first()

    async def get_by_updated_user(self, updated_user: str) -> Optional[Group]:
        return await self.model.filter(updated_user=updated_user).first()

    async def create_group(self, group_in: GroupCreate) -> Group:
        name = group_in.name
        initiator = group_in.initiator
        instances = await self.model.filter(name=name, initiator=initiator).all()
        if instances:
            raise DataAlreadyExistsException(message=f"小组(name={name},initiator={initiator})信息已存在")

        instance = await self.create(group_in)
        return instance

    async def delete_group(self, group_id: int) -> Optional[Group]:
        instance = await self.select(group_id)
        if not instance:
            raise NotFoundException(message=f"小组(id={group_id})信息不存在")

        instance.is_deleted = 1
        await instance.save()
        return instance

    async def update_group(self, group_in: GroupCreate) -> Group:
        group_id: int = group_in.id
        group_if: dict = {
            key: value for key, value in group_in.items()
            if value is not None
        }
        try:
            instance = await self.update(id=group_id, obj_in=group_if)
        except DoesNotExist as e:
            raise NotFoundException(message=f"小组(id={group_id})信息不存在")

        data = await instance.to_dict()
        return data


GROUP_CRUD = GroupCrud()
