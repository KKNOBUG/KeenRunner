# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : department_crud.py
@DateTime: 2025/2/3 16:31
"""
from typing import Optional

from tortoise.exceptions import DoesNotExist

from backend.applications.department.models.department_model import Department
from backend.applications.department.schemas.department_schema import DepartmentCreate, DepartmentUpdate
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException
from backend.services.base_crud import BaseCrud


class DepartmentCrud(BaseCrud[Department, DepartmentCreate, DepartmentUpdate]):
    def __init__(self):
        super().__init__(model=Department)

    async def get_by_id(self, department_id: int) -> Optional[Department]:
        return await self.model.filter(id=department_id).first()

    async def get_by_name(self, name: str) -> Optional[Department]:
        return await self.model.filter(name=name).first()

    async def get_by_initiator(self, initiator: str) -> Optional[Department]:
        return await self.model.filter(initiator=initiator).first()

    async def create_department(self, department_in: DepartmentCreate) -> Department:
        name = department_in.name
        initiator = department_in.initiator
        instances = await self.model.filter(name=name, initiator=initiator).all()
        if instances:
            raise DataAlreadyExistsException(message=f"部门(name={name},initiator={initiator})信息已存在")

        instance = await self.create(department_in)
        return instance

    async def delete_department(self, department_id: int) -> Optional[Department]:
        instance = await self.select(department_id)
        if not instance:
            raise NotFoundException(message=f"部门(id={department_id})信息不存在")

        instance.is_deleted = 1
        await instance.save()
        return instance

    async def update_department(self, department_in: DepartmentCreate) -> Department:
        department_id: int = department_in.id
        department_if: dict = {
            key: value for key, value in department_in.items()
            if value is not None
        }
        try:
            instance = await self.update(id=department_id, obj_in=department_if)
        except DoesNotExist as e:
            raise NotFoundException(message=f"部门(id={department_id})信息不存在")

        data = await instance.to_dict()
        return data


DEPARTMENT_CRUD = DepartmentCrud()
