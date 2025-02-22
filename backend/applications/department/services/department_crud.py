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
from tortoise.expressions import Q

from backend.applications.department.models.dept_model import Department
from backend.applications.department.schemas.department_schema import DepartmentCreate, DepartmentUpdate
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException
from backend.applications.base.services.scaffold import ScaffoldCrud


class DepartmentCrud(ScaffoldCrud[Department, DepartmentCreate, DepartmentUpdate]):
    def __init__(self):
        super().__init__(model=Department)

    async def get_by_id(self, department_id: int) -> Optional[Department]:
        return await self.model.filter(id=department_id).first()

    async def get_by_name(self, name: str) -> Optional[Department]:
        return await self.model.filter(name=name).first()

    async def get_by_code(self, code: str) -> Optional[Department]:
        return await self.model.filter(code=code).first()

    async def create_department(self, department_in: DepartmentCreate) -> Department:
        code = department_in.code
        name = department_in.name
        instances = await self.model.filter(code=code, name=name).all()
        if instances:
            raise DataAlreadyExistsException(message=f"部门(code={code},name={name})信息已存在")

        instance = await self.create(department_in)
        return instance

    async def delete_department(self, department_id: int) -> Optional[Department]:
        instance = await self.query(department_id)
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

    async def get_dept_tree(self, name):
        q = Q()
        # 获取所有未被软删除的部门
        q &= Q(is_deleted=False)
        if name:
            q &= Q(name__contains=name)
        all_dept = await self.model.filter(q).order_by("order")

        # 辅助函数，用于递归构建部门树
        def build_tree(parent_id):
            return [
                {
                    "id": dept.id,
                    "code": dept.code,
                    "name": dept.name,
                    "description": dept.description,
                    "order": dept.order,
                    "parent_id": dept.parent_id,
                    "children": build_tree(dept.id),  # 递归构建子部门
                }
                for dept in all_dept
                if dept.parent_id == parent_id
            ]

        # 从顶级部门（parent_id=0）开始构建部门树
        dept_tree = build_tree(0)
        return dept_tree


DEPT_CRUD = DepartmentCrud()
