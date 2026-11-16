# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : department_crud.py
@DateTime: 2025/2/3 16:31
"""
import traceback
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.department.models.dept_model import Department, DeptStruct
from backend.applications.department.schemas.department_schema import (
    DepartmentBatchDelete,
    DepartmentCreate,
    DepartmentSelect,
    DepartmentUpdate,
)
from backend.applications.user.models.user_model import User
from backend.configure import LOGGER
from backend.configure.global_config import GlobalConfig
from backend.core.exceptions import DataAlreadyExistsException, NotFoundException, ParameterException

# 部门对外序列化口径: 主键统一为 dept_id(前端树/下拉/表单均按该字段取值)
DEPARTMENT_REPLACE_FIELDS: Dict[str, str] = {"id": "dept_id"}


class DepartmentCrud(ScaffoldCrud[Department, DepartmentCreate, DepartmentUpdate]):

    def __init__(self):
        super().__init__(model=Department)

    async def get_by_id(self, department_id: int, on_error: bool = True, **kwargs) -> Optional[Department]:
        """
        根据主键ID查询部门。

        :param department_id: 部门ID
        :param on_error: 未找到时是否抛出异常
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
        :param on_error: 未找到时是否抛出异常
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

    @staticmethod
    async def serialize_department(instance: Department) -> Dict[str, Any]:
        """
        按部门对外口径序列化，主键对外为dept_id。

        :param instance: 部门实例
        :return: 响应字典
        """
        return await instance.to_dict(replace_fields=DEPARTMENT_REPLACE_FIELDS)

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
        校验父级部门，部门最多两级。

        :param parent_id: 父部门ID，0 表示顶级
        :param department_id: 当前部门ID，更新时用于拦截父级设为自身
        :raises ParameterException: 父级为自身或父级不是顶级部门
        :raises NotFoundException: 父级部门不存在或已软删除
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
        :raises ParameterException: 父级部门不合法
        :raises DataAlreadyExistsException: 部门代码或名称已存在
        """
        await self._validate_parent_id(department_in.parent_id)
        code = department_in.code
        name = department_in.name
        # code 与 name 各自唯一，合取查询会漏掉单字段冲突，必须按并集取回后分别判定
        conflicts = await self.model.filter(Q(code=code) | Q(name=name)).only("code", "name").limit(2)
        if any(item.code == code for item in conflicts):
            error_message: str = f"创建部门信息失败, 部门代码[code={code}]已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)
        if any(item.name == name for item in conflicts):
            error_message: str = f"创建部门信息失败, 部门名称[name={name}]已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        try:
            # 部门主记录与闭包关系必须同时提交，任一步失败均回滚，避免残留半完成部门
            async with in_transaction():
                instance = await self.create(department_in)
                await self.update_dept_closure(instance)
        except IntegrityError as e:
            # 并发创建同 code/name：预校验会同时通过，靠唯一索引收敛为业务已存在
            error_message: str = f"创建部门信息失败, 记录[code={code},name={name}]信息已存在"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataAlreadyExistsException(message=error_message) from e
        return instance

    async def _assert_departments_not_referenced(self, targets: List[Department]) -> None:
        """
        批量校验部门不存在引用关系：启用的子部门、未删除的用户。

        :param targets: 待删除部门实例列表，按入参顺序逐条校验
        :raises ParameterException: 存在启用子部门或在用用户
        """
        if not targets:
            return

        # parent_id 与 krun_user.dept_id 均无外键约束，物理删除后引用方会指向不存在的部门，只能应用层前置拦截
        target_ids: List[int] = [instance.id for instance in targets]
        child_rows = await self.model.filter(parent_id__in=target_ids, state=0).values("parent_id")
        user_rows = await User.filter(dept_id__in=target_ids, state=0).values("dept_id")
        child_counter: Counter = Counter(row["parent_id"] for row in child_rows)
        user_counter: Counter = Counter(row["dept_id"] for row in user_rows)

        for instance in targets:
            child_count: int = child_counter[instance.id]
            if child_count > 0:
                error_message: str = f"删除部门信息失败, 部门[name={instance.name}]存在{child_count}个子部门, 无法直接删除"
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)

            user_count: int = user_counter[instance.id]
            if user_count > 0:
                error_message: str = f"删除部门信息失败, 部门[name={instance.name}]存在{user_count}个用户, 无法直接删除"
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)

    async def delete_department(self, department_id: int) -> Optional[Department]:
        """
        物理删除单个部门：存在子部门或在用用户时拒绝，事务内同步清理闭包表关系。

        :param department_id: 部门ID
        :return: 被删除的部门实例
        :raises ParameterException: 存在启用子部门或在用用户
        :raises NotFoundException: 部门不存在或已软删除
        """
        instance = await self.get_by_id(department_id=department_id, on_error=True, state=0)
        await self._assert_departments_not_referenced([instance])
        async with in_transaction() as conn:
            # 闭包表无外键约束，与部门删除同事务清理，避免残留关系使部门树层级错乱
            await DeptStruct.filter(Q(ancestor=instance.id) | Q(descendant=instance.id)).using_db(conn).delete()
            await instance.delete(using_db=conn)
        return instance

    async def update_department(self, department_in: DepartmentUpdate) -> Department:
        """
        更新部门：可变更父级与基础字段，父级变更时重建闭包表。

        :param department_in: 更新部门入参
        :return: 更新后的部门实例
        :raises ParameterException: 父级部门不合法或含子部门的顶级部门被设为子部门
        :raises DataAlreadyExistsException: 部门代码或名称已存在
        :raises NotFoundException: 部门不存在或已软删除
        :raises DataBaseStorageException: 并发修改存在冲突
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

        try:
            # 闭包重建与字段更新同事务：唯一冲突回滚时不能丢失旧闭包
            async with in_transaction():
                if parent_changed:
                    # 先清旧闭包，字段更新后再按新parent_id重建
                    await DeptStruct.filter(ancestor=instance.id).delete()
                    await DeptStruct.filter(descendant=instance.id).delete()
                instance = await self.update(id=department_id, obj_in=department_in)
                if parent_changed:
                    await self.update_dept_closure(instance)
        except IntegrityError as e:
            # 并发改同 code/name：靠唯一索引收敛为业务已存在；局部更新时入参字段为空，用实例当前值兜底
            conflict_code: Optional[str] = department_in.code or instance.code
            conflict_name: Optional[str] = department_in.name or instance.name
            error_message: str = f"更新部门信息失败, 记录[code={conflict_code}, name={conflict_name}]信息已存在"
            LOGGER.error(
                f"{error_message}\n"
                f"异常回溯: {traceback.format_exc()}"
            )
            raise DataAlreadyExistsException(message=error_message) from e
        return instance

    async def get_dept_tree(self, name: Optional[str] = None) -> List[dict]:
        """
        构建未删除部门的树形结构，从顶级部门递归展开。

        :param name: 名称包含匹配的过滤条件，不传则返回全量
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
            return [
                {
                    # 与部门其它接口一致统一返回dept_id，前端树/下拉均按该字段取值
                    "dept_id": dept.id,
                    "code": dept.code,
                    "name": dept.name,
                    "description": dept.description,
                    "order": dept.order,
                    "parent_id": dept.parent_id,
                    "state": dept.state,
                    "created_time": GlobalConfig.format_datetime(dept.created_time, formatter=GlobalConfig.DATETIME_FORMAT2),
                    "updated_time": GlobalConfig.format_datetime(dept.updated_time, formatter=GlobalConfig.DATETIME_FORMAT2),
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

    async def select_departments(self, department_in: DepartmentSelect) -> Tuple[int, List[Department]]:
        """
        按条件分页查询部门列表，固定只查未删除部门。

        :param department_in: 部门查询入参
        :return: 记录总数与当前页部门列表
        """
        # code/name/description 为包含匹配，created_user/updated_user 为等值匹配，state 入参不参与过滤
        search = Q(state=0)
        if department_in.code:
            search &= Q(code__contains=department_in.code)
        if department_in.name:
            search &= Q(name__contains=department_in.name)
        if department_in.description:
            search &= Q(description__contains=department_in.description)
        if department_in.created_user:
            search &= Q(created_user=department_in.created_user)
        if department_in.updated_user:
            search &= Q(updated_user=department_in.updated_user)
        return await self.list(
            page=department_in.page,
            page_size=department_in.page_size,
            search=search,
            order=department_in.order,
        )

    async def delete_departments(self, department_in: DepartmentBatchDelete) -> List[int]:
        """
        根据ID列表软删除部门；软删与物理删同样拒绝存在子部门或在用用户的部门。

        :param department_in: 含department_ids的批量删除入参
        :return: 实际删除成功的部门ID列表
        :raises ParameterException: 存在启用子部门或在用用户
        """
        department_ids: Optional[List[int]] = department_in.department_ids
        if not department_ids:
            return []

        # 去重后一次查出目标部门，先全量校验引用关系，避免前序节点已软删、后续节点被拦截时留下部分成功
        target_ids: List[int] = list(dict.fromkeys(int(department_id) for department_id in department_ids))
        instances = await self.model.filter(id__in=target_ids, state=0)
        instance_index: Dict[int, Department] = {instance.id: instance for instance in instances}
        targets: List[Department] = [instance_index[did] for did in target_ids if did in instance_index]
        if not targets:
            return []

        await self._assert_departments_not_referenced(targets)
        deleted_ids: List[int] = [instance.id for instance in targets]
        update_fields: Dict[str, Any] = self.soft_delete_values()
        async with in_transaction() as conn:
            # 闭包表无外键约束，与软删同事务清理，避免残留关系使部门树层级错乱
            await self.model.filter(id__in=deleted_ids, state=0).using_db(conn).update(**update_fields)
            await DeptStruct.filter(descendant__in=deleted_ids).using_db(conn).delete()
        return deleted_ids
