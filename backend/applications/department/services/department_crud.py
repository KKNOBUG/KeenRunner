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
        """
        根据主键ID查询部门。

        :param department_id: 部门ID
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 部门实例或None
        :raises ParameterException: department_id为空
        :raises NotFoundException: on_error为True且部门不存在
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
        :raises ParameterException: code为空
        :raises NotFoundException: on_error为True且部门不存在
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
        部门最多两级：parent_id只能为 0 或顶级部门id。
        """
        if parent_id == 0:
            return
        if department_id is not None and parent_id == department_id:
            error_message: str = "校验父级部门失败, 父级部门不能为自身"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        parent = await self.get_by_id(parent_id, on_error=True)
        if parent.is_deleted:
            error_message: str = f"校验父级部门失败, 记录[id={parent_id}]不存在或已删除"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if parent.parent_id != 0:
            error_message: str = "校验父级部门失败, 子部门不允许再添加子部门, 父级只能选择顶级部门"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

    async def create_department(self, department_in: DepartmentCreate, created_user: Optional[str] = None) -> Department:
        """
        创建部门：校验父级与唯一性，落库并写入闭包表。

        :param department_in: 新增部门入参
        :param created_user: 可选，覆盖created_user字段
        :return: 新建的部门实例
        :raises ParameterException: 父级不合法
        :raises DataAlreadyExistsException: code或name已存在
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
        if created_user is not None:
            instance.created_user = created_user
            await instance.save(update_fields=["created_user"])
        await self.update_dept_closure(instance)
        return instance

    async def delete_department(self, department_id: int) -> Optional[Department]:
        """
        软删除单个部门并清除闭包表中以该节点为descendant的关系。

        :param department_id: 部门ID
        :return: 更新后的部门实例
        :raises NotFoundException: 部门不存在
        """
        instance = await self.get_by_id(department_id)
        instance.is_deleted = 1
        await instance.save()
        # 删除关系
        await DeptStruct.filter(descendant=department_id).delete()
        return instance

    async def update_department(self, department_in: DepartmentUpdate, updated_user: Optional[str] = None) -> Department:
        """
        更新部门：可变更父级(重建闭包表)及基础字段。

        :param department_in: 更新入参
        :param updated_user: 可选，写入updated_user
        :return: 更新后的部门实例
        :raises NotFoundException: 部门不存在
        :raises ParameterException: 父级变更不合法或含子部门的顶级部门不能降为子部门
        """
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
                    error_message: str = "更新部门信息失败, 含有子部门的顶级部门不能设置为子部门"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)
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
            error_message: str = f"更新部门信息失败, 记录[id={department_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)

    async def get_dept_tree(self, name: Optional[str] = None) -> List[dict]:
        """
        构建未删除部门的树形结构(从parent_id=0 递归)。

        :param name: 可选，根据名称模糊过滤后再建树
        :return: 顶级部门节点列表，每节点含children
        """
        q = Q()
        # 获取所有未被软删除的部门
        q &= Q(is_deleted=False)
        if name:
            q &= Q(name__contains=name)
        all_dept = await self.model.filter(q).order_by("order")

        # 辅助函数，用于递归构建部门树
        def build_tree(parent_id: int) -> List[dict]:
            """
            递归组装指定parent_id下的子树节点。

            :param parent_id: 父部门ID，0 表示顶级
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

    async def delete_departments(self, department_ids: Optional[List[int]]) -> int:
        """
        根据ID列表软删除部门(与单笔delete_department行为一致)。

        :param department_ids: 部门ID列表
        :return: 实际删除成功的条数
        """
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
