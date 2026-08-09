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

from tortoise.expressions import Q

from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.department.models.dept_model import Department, DeptStruct
from backend.applications.department.schemas.department_schema import DepartmentCreate, DepartmentUpdate, DepartmentBatchDelete
from backend.configure import LOGGER
from backend.core.exceptions import DataAlreadyExistsException, NotFoundException, ParameterException


class DepartmentCrud(ScaffoldCrud[Department, DepartmentCreate, DepartmentUpdate]):

    def __init__(self):
        super().__init__(model=Department)

    async def get_by_id(self, department_id: int, on_error: bool = True, **kwargs) -> Optional[Department]:
        """
        根据主键ID查询部门。

        :param department_id: 部门ID
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 部门实例或None
        """
        if not department_id:
            error_message: str = "查询部门信息失败, 参数[department_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.get_or_none(id=department_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询部门信息失败, 记录[id={department_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, code: str, on_error: bool = False, **kwargs) -> Optional[Department]:
        """
        根据部门代码查询单条部门。

        :param code: 部门代码
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 部门实例或None
        """
        if not code:
            error_message: str = "查询部门信息失败, 参数[code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.model.filter(code=code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询部门信息失败, 记录[code={code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_name(self, name: str) -> List[Department]:
        """
        根据部门名称精确查询，可能返回多条。

        :param name: 部门名称
        :return: 匹配的部门列表(无匹配时为空列表)
        """
        result = await self.get_by_conditions(only_one=False, on_error=False, name=name)
        return result if isinstance(result, list) else ([] if result is None else [result])

    async def _validate_parent_id(self, parent_id: int, *, department_id: Optional[int] = None) -> None:
        """
        部门最多两级：parent_id只能为0或顶级部门id。
        """
        if parent_id == 0:
            return
        if department_id is not None and parent_id == department_id:
            error_message: str = "校验父级部门失败, 父级部门不能为自身"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        parent = await self.get_by_id(parent_id, on_error=True, state=0)
        if parent.parent_id != 0:
            error_message: str = "校验父级部门失败, 子部门不允许再添加子部门, 父级只能选择顶级部门"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

    async def create_department(self, department_in: DepartmentCreate) -> Department:
        """
        创建部门：校验父级与唯一性，落库并写入闭包表。

        :param department_in: 新增部门入参
        :return: 新建的部门实例
        """
        await self._validate_parent_id(department_in.parent_id)
        code = department_in.code
        name = department_in.name
        instances = await self.get_by_conditions(only_one=True, on_error=False, code=code, name=name)
        if instances:
            error_message: str = f"创建部门信息失败, 记录[code={code},name={name}]信息已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        instance = await self.create(department_in)
        await self.update_dept_closure(instance)
        return instance

    async def delete_department(self, department_id: int) -> Optional[Department]:
        """
        软删除单个部门并清除闭包表中以该节点为descendant的关系。

        :param department_id: 部门ID
        :return: 更新后的部门实例
        """
        instance = await self.soft_delete(id=department_id)
        await DeptStruct.filter(descendant=department_id).delete()
        return instance

    async def update_department(self, department_in: DepartmentUpdate) -> Department:
        """
        更新部门：可变更父级(重建闭包表)及基础字段。

        :param department_in: 更新部门入参
        :return: 更新后的部门实例
        """
        department_id: int = department_in.id
        instance = await self.get_by_id(department_id=department_id)
        new_parent_id = (
            department_in.parent_id
            if department_in.parent_id is not None
            else instance.parent_id
        )
        await self._validate_parent_id(new_parent_id, department_id=department_id)

        parent_changed = new_parent_id != instance.parent_id
        if parent_changed:
            child_count = await self.model.filter(parent_id=department_id, state=0).count()
            if child_count > 0 and new_parent_id != 0:
                error_message: str = "更新部门信息失败, 含有子部门的顶级部门不能设置为子部门"
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)
            # 先清旧闭包，字段更新后再按新parent_id重建
            await DeptStruct.filter(ancestor=instance.id).delete()
            await DeptStruct.filter(descendant=instance.id).delete()

        instance = await self.update(id=department_id, obj_in=department_in)
        if parent_changed:
            await self.update_dept_closure(instance)
        return instance

    async def get_dept_tree(self, name: Optional[str] = None) -> List[dict]:
        """
        构建未删除部门的树形结构(从parent_id=0递归)。

        :param name: 可选，根据名称模糊过滤后再建树
        :return: 顶级部门节点列表，每节点含children
        """
        # 获取所有未被软删除的部门
        q = Q(state=0)
        if name:
            q &= Q(name__contains=name)
        all_dept = await self.model.filter(q).order_by("order")

        # 辅助函数，用于递归构建部门树
        def build_tree(parent_id: int) -> List[dict]:
            """
            递归组装指定parent_id下的子树节点。

            :param parent_id: 父部门ID，0表示顶级
            :return: 子节点字典列表
            """
            fmt = lambda x: datetime.datetime.strftime(x, "%Y-%m-%d %H:%M:%S") if isinstance(x, datetime.datetime) else x
            return [
                {
                    "id": dept.id,
                    "code": dept.code,
                    "name": dept.name,
                    "description": dept.description,
                    "order": dept.order,
                    "parent_id": dept.parent_id,
                    "state": dept.state,
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
    async def update_dept_closure(cls, obj: Department) -> None:
        """
        为部门节点重建闭包表记录：继承父级祖先链并追加自身。

        :param obj: 已落库的部门实例(含id、parent_id)
        :return: None
        """
        parent_depts = await DeptStruct.filter(descendant=obj.parent_id).all()
        dept_struct_objs: List[DeptStruct] = []
        # 插入父级关系
        for item in parent_depts:
            dept_struct_objs.append(DeptStruct(ancestor=item.ancestor, descendant=obj.id, level=item.level + 1))
        # 插入自身
        dept_struct_objs.append(DeptStruct(ancestor=obj.id, descendant=obj.id, level=0))
        # 创建关系
        await DeptStruct.bulk_create(dept_struct_objs)

    async def delete_departments(self, department_in: DepartmentBatchDelete) -> List[int]:
        """
        根据ID列表软删除部门。

        :param department_in: 含department_ids的批量删除入参
        :return: 实际删除成功的条数
        """
        department_ids: Optional[List[int]] = department_in.user_ids
        if not department_ids:
            return []

        deleted_ids: List[int] = []
        for did in deleted_ids:
            try:
                await self.delete_department(int(did))
                deleted_ids.append(int(did))
            except NotFoundException:
                continue
        return deleted_ids
