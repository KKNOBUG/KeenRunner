# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : department_crud.py
@DateTime: 2025/2/3 16:31
"""
import datetime
from typing import Optional, List

from tortoise.exceptions import DoesNotExist
from tortoise.expressions import Q

from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.department.models.dept_model import Department, DeptStruct
from backend.applications.department.schemas.department_schema import DepartmentCreate, DepartmentUpdate
from backend.configure import LOGGER
from backend.core.exceptions import DataAlreadyExistsException, NotFoundException, ParameterException


class DepartmentCrud(ScaffoldCrud[Department, DepartmentCreate, DepartmentUpdate]):
    def __init__(self):
        super().__init__(model=Department)

    async def get_by_id(self, department_id: int, on_error: bool = True, **kwargs) -> Optional[Department]:
        if not department_id:
            error_message: str = "查询部门信息失败, 参数(department_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.get_or_none(id=department_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询部门信息失败, 部门(id={department_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, code: str, on_error: bool = False, **kwargs) -> Optional[Department]:
        if not code:
            error_message: str = "查询部门信息失败, 参数(code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.model.filter(code=code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询部门信息失败, 部门(code={code})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_name(self, name: str) -> Optional[Department]:
        return await self.get_by_conditions(only_one=False, on_error=False, name=name)

    async def _validate_parent_id(self, parent_id: int, *, department_id: Optional[int] = None) -> None:
        """部门最多两级：parent_id 只能为 0 或顶级部门 id。"""
        if parent_id == 0:
            return
        if department_id is not None and parent_id == department_id:
            raise ParameterException(message="父级部门不能为自身")
        parent = await self.get_by_id(parent_id, on_error=True)
        if parent.is_deleted:
            raise ParameterException(message=f"父级部门(id={parent_id})不存在或已删除")
        if parent.parent_id != 0:
            raise ParameterException(message="子部门不允许再添加子部门，父级只能选择顶级部门")

    async def create_department(self, department_in: DepartmentCreate, created_user: Optional[str] = None) -> Department:
        await self._validate_parent_id(department_in.parent_id)
        code = department_in.code
        name = department_in.name
        instances = await self.get_by_conditions(only_one=True, on_error=False, code=code, name=name)
        if instances:
            raise DataAlreadyExistsException(message=f"部门(code={code},name={name})信息已存在")

        instance = await self.create(department_in)
        if created_user is not None:
            instance.created_user = created_user
            await instance.save(update_fields=["created_user"])
        await self.update_dept_closure(instance)
        return instance

    async def delete_department(self, department_id: int) -> Optional[Department]:
        instance = await self.get_by_id(department_id)
        instance.is_deleted = 1
        await instance.save()
        # 删除关系
        await DeptStruct.filter(descendant=department_id).delete()
        return instance

    async def update_department(self, department_in: DepartmentUpdate, updated_user: Optional[str] = None) -> Department:
        department_id: int = department_in.id
        try:
            instance = await self.get_by_id(department_id=department_id)
            new_parent_id = (
                department_in.parent_id
                if department_in.parent_id is not None
                else instance.parent_id
            )
            await self._validate_parent_id(new_parent_id, department_id=department_id)
            if new_parent_id != instance.parent_id:
                child_count = await self.model.filter(
                    parent_id=department_id, is_deleted=False
                ).count()
                if child_count > 0 and new_parent_id != 0:
                    raise ParameterException(message="含有子部门的顶级部门不能设置为子部门")
                await DeptStruct.filter(ancestor=instance.id).delete()
                await DeptStruct.filter(descendant=instance.id).delete()
                instance.parent_id = new_parent_id
                await self.update_dept_closure(instance)
            # 更新部门信息
            update_dict = department_in.model_dump(exclude_unset=True, exclude={"id"})
            if updated_user is not None:
                update_dict["updated_user"] = updated_user
            await instance.update_from_dict(update_dict)
            await instance.save()
            return instance
        except DoesNotExist as e:
            raise NotFoundException(message=f"部门(id={department_id})信息不存在")

    async def get_dept_tree(self, name):
        q = Q()
        # 获取所有未被软删除的部门
        q &= Q(is_deleted=False)
        if name:
            q &= Q(name__contains=name)
        all_dept = await self.model.filter(q).order_by("order")

        # 辅助函数，用于递归构建部门树
        def build_tree(parent_id):
            fmt = lambda x: datetime.datetime.strftime(x, "%Y-%m-%d %H:%M:%S") if isinstance(x, datetime.datetime) else x
            return [
                {
                    "id": dept.id,
                    "code": dept.code,
                    "name": dept.name,
                    "description": dept.description,
                    "order": dept.order,
                    "parent_id": dept.parent_id,
                    "created_time": fmt(dept.created_time),
                    "updated_time": fmt(dept.updated_time),
                    "created_user": dept.created_user,
                    "updated_user": dept.updated_user,
                    "children": build_tree(dept.id),  # 递归构建子部门
                }
                for dept in all_dept
                if dept.parent_id == parent_id
            ]

        # 从顶级部门（parent_id=0）开始构建部门树
        dept_tree = build_tree(0)
        return dept_tree

    @classmethod
    async def update_dept_closure(cls, obj: Department):
        parent_depts = await DeptStruct.filter(descendant=obj.parent_id).all()
        dept_struct_objs: List[DeptStruct] = []
        # 插入父级关系
        for item in parent_depts:
            dept_struct_objs.append(DeptStruct(ancestor=item.ancestor, descendant=obj.id, level=item.level + 1))
        # 插入自身x
        dept_struct_objs.append(DeptStruct(ancestor=obj.id, descendant=obj.id, level=0))
        # 创建关系
        await DeptStruct.bulk_create(dept_struct_objs)

    async def delete_departments(self, department_ids: Optional[List[int]]) -> int:
        """按 ID 列表软删除部门（与单笔 delete_department 行为一致）。"""
        if not department_ids:
            return 0
        n = 0
        for did in department_ids:
            try:
                await self.delete_department(int(did))
                n += 1
            except NotFoundException:
                continue
        return n
