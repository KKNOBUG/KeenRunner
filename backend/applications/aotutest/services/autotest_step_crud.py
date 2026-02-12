# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_crud.py
@DateTime: 2025/4/28
"""
import datetime
import traceback
import uuid
from typing import Optional, List, Dict, Any, Set

from tortoise.exceptions import DoesNotExist, IntegrityError, FieldError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet
from tortoise.transactions import in_transaction

from backend import LOGGER
from backend.applications.aotutest.models.autotest_model import (
    AutoTestApiStepInfo,
    AutoTestApiCaseInfo,
)
from backend.applications.aotutest.schemas.autotest_case_schema import AutoTestApiCaseUpdate
from backend.applications.aotutest.schemas.autotest_step_schema import (
    AutoTestApiStepCreate,
    AutoTestApiStepUpdate,
    AutoTestStepTreeUpdateItem
)
from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
from backend.applications.aotutest.services.autotest_report_crud import AUTOTEST_API_REPORT_CRUD
from backend.applications.aotutest.services.autotest_detail_crud import AUTOTEST_API_DETAIL_CRUD
from backend.applications.aotutest.services.autotest_step_engine import AutoTestStepExecutionEngine
from backend.applications.aotutest.services.autotest_tool_service import AutoTestToolService
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)
from backend.enums.autotest_enum import AutoTestCaseType, AutoTestStepType, AutoTestReportType


class AutoTestApiStepCrud(ScaffoldCrud[AutoTestApiStepInfo, AutoTestApiStepCreate, AutoTestApiStepUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestApiStepInfo)

    async def get_by_id(self, step_id: int, on_error: bool = False) -> Optional[AutoTestApiStepInfo]:
        if not step_id:
            error_message: str = "查询步骤信息失败, 参数(step_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(id=step_id, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询步骤信息失败, 步骤(id={step_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, step_code: str, on_error: bool = False) -> Optional[AutoTestApiStepInfo]:
        if not step_code:
            error_message: str = "查询步骤信息失败, 参数(step_code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(step_code=step_code, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询步骤信息失败, 步骤(code={step_code})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True,
            on_error: bool = False
    ) -> Optional[AutoTestApiStepInfo]:
        try:
            stmt: QuerySet = self.model.filter(**conditions, state__not=1)
            instances = await (stmt.first() if only_one else stmt.all())
        except FieldError as e:
            error_message: str = f"查询步骤信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
        except Exception as e:
            error_message: str = f"查询步骤信息发生未知异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

        if not instances and on_error:
            error_message: str = f"查询步骤信息失败, 条件{conditions}不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instances

    async def get_by_case_id(
            self,
            case_id: Optional[int] = None,
            case_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        # 业务层验证：检查用例是否存在
        if case_id:
            case_instance = await AUTOTEST_API_CASE_CRUD.get_by_id(case_id=case_id, on_error=True)
        else:
            case_instance = await AUTOTEST_API_CASE_CRUD.get_by_code(case_code=case_code, on_error=True)
            case_id: int = case_instance.id

        # 获取所有根步骤（没有父步骤的步骤）
        root_steps: List = await self.model.filter(
            case_id=case_id,
            parent_step_id__isnull=True,
            state__not=1
        ).order_by("step_no").all()
        root_index = [step.step_no for step in root_steps]
        LOGGER.info(f"获取用例(case_id={case_id})根步骤成功, 共计: {len(root_steps)}个, 根步骤序号: {root_index}")

        # 步骤计数器：用于统计该用例拥有的步骤总数
        # direct_steps: 直接属于该用例的步骤数（根步骤, parent_step_id 为 None）
        # child_steps: 所有子步骤数（递归统计, 不包括根步骤, parent_step_id 不为 None）
        # quote_steps: 引用用例的步骤数
        # total_step: 总步骤数（direct_steps + child_steps + quote_steps）
        step_counter = {
            "direct_steps": 0,
            "child_steps": 0,
            "quote_steps": 0,
            "total_steps": 0
        }

        # 递归构建步骤树
        async def build_step_tree(step: AutoTestApiStepInfo, is_quote: bool = False) -> Dict[str, Any]:
            # 统计步骤数量
            step_counter["total_steps"] += 1
            if is_quote:
                # 引用步骤及其所有子步骤都计入 quote_steps
                step_counter["quote_steps"] += 1
            else:
                # 非引用步骤：根据是否有父步骤判断是根步骤还是子步骤
                if step.parent_step_id is None:
                    # 根步骤（parent_step_id 为 None）
                    step_counter["direct_steps"] += 1
                else:
                    # 子步骤（parent_step_id 不为 None）
                    step_counter["child_steps"] += 1

            # 获取步骤基本信息
            step_dict = await step.to_dict(
                exclude_fields={
                    "state",
                    "created_user", "updated_user",
                    "created_time", "updated_time",
                    "reserve_1", "reserve_2", "reserve_3"
                },
                replace_fields={"id": "step_id"}
            )
            LOGGER.info(f"获取步骤(step_id={step.id}, step_no={step.step_no})基本信息完成")
            # 获取用例信息（业务层手动查询）
            if step.case_id:
                case = await AUTOTEST_API_CASE_CRUD.get_by_id(case_id=step.case_id, on_error=True)
                step_dict["case"] = await case.to_dict(
                    exclude_fields={
                        "state",
                        "created_user", "updated_user",
                        "created_time", "updated_time",
                        "reserve_1", "reserve_2", "reserve_3"
                    },
                    replace_fields={"id": "case_id"}
                )
                LOGGER.info(f"获取步骤(step_id={step.id}, step_no={step.step_no})所属用例信息完成")

            # 获取子步骤（递归构建）
            children: List = await self.model.filter(parent_step_id=step.id, state__not=1).order_by("step_no").all()
            if children:
                LOGGER.info(f"- 获取步骤(step_id={step.id}, step_no={step.step_no})所有子步骤(递归构建)开始 -")
                step_dict["children"] = [await build_step_tree(child, is_quote=is_quote) for child in children]
                LOGGER.info(f"- 获取步骤(step_id={step.id}, step_no={step.step_no})所有子步骤(递归构建)完成 -")
            else:
                step_dict["children"] = []

            # 业务层验证：是否引用了公共用例
            if not step.quote_case_id:
                step_dict["quote_steps"] = []
                step_dict["quote_case"] = None
                return step_dict

            # 业务层验证：检查引用的公共用例是否存在
            quote_case = await AUTOTEST_API_CASE_CRUD.get_by_id(case_id=step.quote_case_id, on_error=False)
            if not quote_case:
                step_dict["quote_steps"] = []
                step_dict["quote_case"] = None
                return step_dict

            # 获取引用的公共用例的所有步骤(包含子步骤, 递归构建)
            quote_case_root_steps: List = await self.model.filter(
                case_id=step.quote_case_id,
                parent_step_id__isnull=True,
                state__not=1
            ).order_by("step_no").all()
            LOGGER.info(
                f"= 获取步骤(step_id={step.id}, step_no={step.step_no})引用用例的所有步骤(包含子步骤, 递归构建)开始 =")
            step_dict["quote_steps"] = [await build_step_tree(quote, is_quote=True) for quote in quote_case_root_steps]
            step_dict["quote_case"] = await quote_case.to_dict(
                exclude_fields={
                    "state",
                    "created_user", "updated_user",
                    "created_time", "updated_time",
                    "reserve_1", "reserve_2", "reserve_3"
                },
                replace_fields={"id": "case_id"}
            )
            LOGGER.info(
                "= 获取步骤(step_id={step.id}, step_no={step.step_no})引用用例的所有步骤(包含子步骤, 递归构建)完成 =")
            return step_dict

        # 构建所有根步骤的树
        result = []
        for root_id, root_step in enumerate(root_steps, start=1):
            LOGGER.info(f">>>>>>>>>>>>>>> 构建第{root_id}个根步骤树结构: ")
            result.append(await build_step_tree(root_step))

        # 没有测试步骤明细时将测试用例本身添加到返回结果
        if not result:
            result.append({
                "case": await case_instance.to_dict(
                    exclude_fields={
                        "state",
                        "created_user", "updated_user",
                        "created_time", "updated_time",
                        "reserve_1", "reserve_2", "reserve_3"
                    },
                    replace_fields={"id": "case_id"}
                )
            })
        result.append(step_counter)
        return result

    async def create_step(self, step_in: AutoTestApiStepCreate) -> AutoTestApiStepInfo:
        # 业务层验证：检查用例是否存在
        case_id: int = step_in.case_id
        step_no: int = step_in.step_no
        await AUTOTEST_API_CASE_CRUD.get_by_id(case_id=case_id, on_error=True)

        # 业务层验证：如果指定了父步骤，检查父步骤是否存在
        if step_in.parent_step_id:
            parent_step_id: int = step_in.parent_step_id
            parent_step = await self.get_by_id(step_id=parent_step_id, on_error=True)

            # 业务层验证：确保父步骤属于同一个用例
            if parent_step.case_id != step_in.case_id:
                error_message: str = (
                    f"根据(step_id={parent_step_id})条件检查步骤信息失败, "
                    f"父级步骤(case_id={parent_step.case_id})和当前步骤(case_id={case_id})不一致"
                )
                LOGGER.error(error_message)
                raise NotFoundException(message=error_message)

        # 业务层验证：如果指定了引用用例，检查引用用例是否存在
        if step_in.quote_case_id:
            quote_case_id: int = step_in.quote_case_id
            quote_case = await AUTOTEST_API_CASE_CRUD.get_by_id(case_id=quote_case_id, on_error=False)
            if not quote_case:
                error_message: str = (
                    f"根据(case_id={quote_case_id})条件检查用例信息失败, "
                    f"步骤序号(step_no={step_no})引用公共用例(case_id={quote_case_id})不存在"
                )
                LOGGER.error(error_message)
                raise NotFoundException(message=error_message)

        # 业务层验证：检查同一用例下步骤序号是否已存在
        existing_step = await self.model.filter(case_id=case_id, step_no=step_no, state__not=1).first()
        if existing_step:
            error_message: str = (
                f"根据(case_id={case_id}, step_no={step_no})条件检查步骤信息失败, 同一用例下步骤序号不允许重复"
            )
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        try:
            step_dict = step_in.model_dump(exclude_none=True, exclude_unset=True)
            instance = await self.create(step_dict)
            return instance
        except IntegrityError as e:
            error_message: str = f"新增步骤信息失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_step(self, step_in: AutoTestApiStepUpdate) -> AutoTestApiStepInfo:
        step_id: Optional[int] = step_in.step_id
        step_code: Optional[str] = step_in.step_code

        # 业务层验证：检查步骤信息是否存在
        if step_id:
            instance = await self.get_by_id(step_id=step_id, on_error=True)
        else:
            instance = await self.get_by_code(step_code=step_code, on_error=True)
            step_id: int = instance.id

        update_dict: Dict[str, Any] = step_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"step_id", "step_code"}
        )
        if not update_dict:
            return instance

        # 业务层验证：如果更新了步骤序号，检查是否冲突
        if "step_no" in update_dict:
            case_id = update_dict.get("case_id", instance.case_id)
            step_no = update_dict.get("step_no", instance.step_no)
            existing_step = await self.model.filter(
                case_id=case_id,
                step_no=step_no,
                state__not=1
            ).exclude(id=step_id).first()
            if existing_step:
                error_message: str = (
                    f"根据(case_id={case_id}, step_no={step_no})条件检查步骤信息失败, 同一用例下步骤序号不允许重复"
                )
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)

        # 业务层验证：如果更新了用例ID，检查用例是否存在
        if "case_id" in update_dict:
            case_id: int = update_dict.get("case_id", instance.case_id)
            await AUTOTEST_API_CASE_CRUD.get_by_id(case_id=case_id, on_error=True)

        # 业务层验证：如果更新了父步骤ID，检查父步骤是否存在
        if "parent_step_id" in update_dict:
            parent_step_id: Optional[int] = update_dict["parent_step_id"]
            if parent_step_id:
                parent_step: AutoTestApiStepInfo = await self.model.filter(
                    id=parent_step_id,
                    state__not=1,
                    case_type=AutoTestCaseType.PRIVATE_SCRIPT.value,
                    step_type__in=[AutoTestStepType.IF.value, AutoTestStepType.LOOP.value]
                ).first()
                if not parent_step:
                    error_message: str = (
                        f"根据(id={parent_step_id}, case_type=用户脚本, step_type__in=[条件分支, 循环结构])条件检查步骤信息失败, "
                        f"父级步骤(id={parent_step_id})不存在"
                    )
                    LOGGER.error(error_message)
                    raise NotFoundException(message=error_message)

                # 业务层验证：确保父步骤属于同一个用例
                case_id: int = update_dict.get("case_id", instance.case_id)
                if parent_step.case_id != case_id:
                    error_message: str = f"父级步骤(case_id={parent_step.case_id})和当前步骤(case_id={case_id})不一致"
                    LOGGER.error(error_message)
                    raise NotFoundException(message=error_message)

                # 业务层验证：检查是否形成循环引用
                if parent_step.id == step_id:
                    error_message: str = f"父级步骤(id={parent_step.id})和当前步骤(id={step_id})冲突, 不能将自身设置为父级步骤"
                    LOGGER.error(error_message)
                    raise DataBaseStorageException(message=error_message)

                # 业务层验证：检查循环引用（防止父步骤的父步骤链中包含当前步骤）
                visited: Set = set()
                current_parent_id = parent_step.parent_step_id
                while current_parent_id:
                    if current_parent_id == step_id:
                        error_message: str = f"父级步骤(id={parent_step.id})和当前步骤(id={step_id})冲突, 不能将自身设置为父级步骤"
                        LOGGER.error(error_message)
                        raise DataBaseStorageException(message=error_message)
                    if current_parent_id in visited:
                        break
                    visited.add(current_parent_id)
                    parent = await self.get_by_id(step_id=current_parent_id, on_error=False)
                    if not parent:
                        break
                    current_parent_id = parent.parent_step_id

        # 业务层验证：如果更新了引用用例ID，检查引用公共用例是否存在
        if "quote_case_id" in update_dict and update_dict["quote_case_id"]:
            quote_case_id: int = update_dict["quote_case_id"]
            quote_case = await AUTOTEST_API_CASE_CRUD.get_by_conditions(
                only_one=True,
                conditions={"id": quote_case_id, "case_type": AutoTestCaseType.PRIVATE_SCRIPT.value}
            )
            if not quote_case:
                error_message: str = f"根据(id={quote_case_id}, case_type=用户脚本)条件检查用例信息失败, 引用公共用例信息不存在"
                LOGGER.error(error_message)
                raise NotFoundException(message=error_message)

        try:
            instance = await self.update(id=step_id, obj_in=update_dict)
            return instance
        except DoesNotExist as e:
            error_message: str = f"更新步骤信息失败, 步骤(id={step_id}或code={step_code})不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = f"更新步骤信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_step(self, step_id: Optional[int] = None, step_code: Optional[str] = None) -> AutoTestApiStepInfo:
        # 业务层验证：检查步骤信息是否存在
        if step_id:
            instance = await self.get_by_id(step_id=step_id, on_error=True)
        else:
            instance = await self.get_by_code(step_code=step_code, on_error=True)
            step_id: int = instance.id

        # 业务层验证：检查步骤是否拥有子步骤
        children_count = await self.model.filter(parent_step_id=step_id, state__not=1).count()
        if children_count > 0:
            error_message: str = (
                f"根据(parent_step_id={step_id}, case_type=用户脚本)条件检查步骤信息失败, "
                f"步骤(id={step_id})存在{children_count}个子级步骤, 无法直接删除"
            )
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        # 软删除
        instance.state = 1
        await instance.save()
        return instance

    async def delete_steps_recursive(
            self,
            step_id: Optional[int] = None,
            step_code: Optional[str] = None,
            parent_step_id: Optional[int] = None,
            case_id: Optional[int] = None,
            exclude_step: Optional[Set[tuple]] = None
    ) -> int:
        deleted_count: int = 0
        if exclude_step is None:
            exclude_step = set()

        async def delete_step_and_children(step_instance: AutoTestApiStepInfo) -> int:
            deleted: int = 0
            # 先删除所有子步骤（软删除）
            children = await self.model.filter(parent_step_id=step_instance.id, state__not=1).all()
            for child in children:
                deleted += await delete_step_and_children(step_instance=child)
            # 然后删除当前步骤（软删除）
            if (step_instance.id, step_instance.step_code) not in exclude_step:
                step_instance.state = 1
                await step_instance.save()
                deleted += 1
                LOGGER.warning(
                    f"警告: 删除步骤(step_id={step_instance.id}, "
                    f"step_no={step_instance.step_no}, step_code={step_instance.step_code})成功"
                )
            return deleted

        async with in_transaction():
            # 根据参数类型执行不同的删除逻辑
            if step_id is not None or step_code is not None:
                # 单步骤删除
                conditions = {"state__not": 1}
                if step_id is not None:
                    conditions["id"] = step_id
                if step_code is not None:
                    conditions["step_code"] = step_code

                step = await self.get_by_conditions(conditions=conditions, only_one=True, on_error=True)
                if step:
                    LOGGER.warning("单个步骤删除: ")
                    deleted_count = await delete_step_and_children(step_instance=step)

            elif parent_step_id is not None:
                # 删除指定父步骤下的所有子步骤
                existing_steps = await self.model.filter(
                    parent_step_id=parent_step_id,
                    state__not=1
                ).all()
                LOGGER.warning("删除指定父级步骤下所有的子级步骤: ")
                for step in existing_steps:
                    if (step.id, step.step_code) not in exclude_step:
                        deleted_count += await delete_step_and_children(step_instance=step)

            elif case_id is not None:
                # 删除指定用例下的所有根步骤（parent_step_id为None的步骤）
                existing_steps = await self.model.filter(
                    case_id=case_id,
                    parent_step_id__isnull=True,
                    state__not=1
                ).all()
                LOGGER.warning("删除指定用例下的所有根步骤(parent_step_id为None的步骤): ")
                for step in existing_steps:
                    if (step.id, step.step_code) not in exclude_step:
                        deleted_count += await delete_step_and_children(step_instance=step)

        return deleted_count

    async def select_steps(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询步骤信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def batch_update_or_create_steps(
            self,
            steps_data: List[AutoTestStepTreeUpdateItem],
            parent_step_id: Optional[int] = None
    ) -> Dict[str, Any]:
        created_count: int = 0
        updated_count: int = 0
        success_detail: List[Dict[str, Any]] = []
        processed_step_codes: Dict[int, Set] = {}
        allowed_children_types = {AutoTestStepType.LOOP, AutoTestStepType.IF}
        for sid, step_data in enumerate(steps_data, start=1):
            case_id: Optional[int] = step_data.case_id
            step_id: Optional[int] = step_data.step_id
            step_no: Optional[int] = step_data.step_no
            step_code: Optional[str] = step_data.step_code
            if step_id:
                step_instance: Optional[AutoTestApiStepInfo] = await self.get_by_id(step_id=step_id, on_error=True)
                step_code = step_instance.step_code
            elif step_code:
                step_instance: Optional[AutoTestApiStepInfo] = await self.get_by_code(
                    step_code=step_code,
                    on_error=True
                )
                step_id = step_instance.id
            else:
                step_instance = None

            # 步骤不存在，执行新增，及验证必填字段
            if not step_instance:
                if not case_id:
                    error_message: str = f"第({sid})条步骤新增失败, 步骤所属用例(case_id)字段不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)
                if not step_no:
                    error_message: str = f"第({sid})条步骤新增失败, 步骤序号(step_no)字段不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)
                if not step_data.step_type:
                    error_message: str = f"第({sid})条步骤新增失败, 步骤类型(step_type)字段不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)

                # 业务层验证: 检查用例是否存在
                await AUTOTEST_API_CASE_CRUD.get_by_id(case_id=step_data.case_id, on_error=True)

                # 业务层验证: 检查同一用例下步骤序号是否已存在
                existing_step_instance: Optional[AutoTestApiStepInfo] = await self.get_by_conditions(
                    only_one=True,
                    on_error=False,
                    conditions={"case_id": case_id, "step_no": step_no, "step_code": step_code},
                )
                if existing_step_instance:
                    error_message: str = (
                        f"第({sid})步骤新增失败, "
                        f"根据(case_id={case_id}, step_no={step_no})条件查询步骤信息失败, "
                        f"用一用例下步骤序号不允许重复"
                    )
                    LOGGER.error(error_message)
                    raise DataAlreadyExistsException(message=error_message)

                # 业务层验证: 验证父步骤
                final_parent_step_id = parent_step_id if parent_step_id is not None else step_data.parent_step_id
                if final_parent_step_id:
                    parent_step = await self.get_by_conditions(
                        only_one=True,
                        on_error=False,
                        conditions={"id": final_parent_step_id}
                    )
                    if not parent_step:
                        error_message: str = (
                            f"第({sid})步骤新增失败, "
                            f"根据(step_id={final_parent_step_id})条件查询步骤信息失败, "
                            f"父级步骤不存在"
                        )
                        LOGGER.error(error_message)
                        raise NotFoundException(message=error_message)

                    # 业务层验证: 确保父步骤属于同一个用例
                    if parent_step.case_id != step_data.case_id:
                        error_message: str = f"父级步骤(case_id={parent_step.case_id})和当前步骤(case_id={case_id})不一致"
                        LOGGER.error(error_message)
                        raise DataAlreadyExistsException(message=error_message)

                    # 业务层验证: 验证父步骤类型(只有循环结构和条件分支允许拥有子级步骤)
                    if parent_step.step_type not in allowed_children_types:
                        error_message: str = (
                            f"第({sid})步骤新增失败, "
                            f"父级步骤(id={final_parent_step_id})的类型({parent_step.step_type})不允许包含子步骤"
                            f"(仅允许'循环结构'和'条件分支'类型的步骤包含子步骤)"
                        )
                        LOGGER.error(error_message)
                        raise ParameterException(message=error_message)

                create_step_dict: Dict[str, Any] = step_data.model_dump(
                    exclude_none=True,
                    exclude={"id", "case", "children", "quote_steps", "quote_case", "step_code"},
                )
                if final_parent_step_id is not None:
                    create_step_dict["parent_step_id"] = final_parent_step_id

                try:
                    new_step_instance: AutoTestApiStepInfo = await self.create(create_step_dict)
                except Exception as e:
                    error_message: str = f"第({sid})条步骤新增失败, 错误描述: {e}"
                    LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                    raise DataBaseStorageException(message=error_message) from e

                processed_step_codes.setdefault(new_step_instance.case_id, set()).add(new_step_instance.step_code)
                step_dict: Dict[str, Any] = await new_step_instance.to_dict(
                    include_fields=["step_no", "step_code", "step_name"]
                )
                created_count += 1
                step_dict["created"] = True
                step_dict["step_id"] = new_step_instance.id
                success_detail.append(step_dict)

                # 递归处理子步骤
                children: List[AutoTestStepTreeUpdateItem] = step_data.children
                if children:
                    child_result = await self.batch_update_or_create_steps(
                        steps_data=children,
                        parent_step_id=new_step_instance.id,
                    )
                    created_count += child_result["created_count"]
                    updated_count += child_result["updated_count"]
                    processed_step_codes[case_id].update(child_result["process_detail"][case_id])
                    success_detail.extend(child_result.get("success_detail", []))

            # 步骤存在，执行更新
            else:
                update_dict = step_data.model_dump(
                    exclude={"id", "case", "children", "quote_steps", "quote_case", "step_code"},
                    exclude_none=True
                )
                if "parent_step_id" not in step_data.model_dump(exclude_unset=True) and parent_step_id is not None:
                    update_dict["parent_step_id"] = parent_step_id
                elif step_data.parent_step_id is not None:
                    update_dict["parent_step_id"] = step_data.parent_step_id
                elif step_data.parent_step_id is None and parent_step_id is None:
                    # 明确设置为None（根步骤）
                    update_dict["parent_step_id"] = None

                # 业务层验证：如果更新了步骤序号，检查是否冲突
                if "step_no" in update_dict:
                    case_id = update_dict.get("case_id", step_instance.case_id)
                    step_no = update_dict.get("step_no", step_instance.step_no)
                    existing_step_instance = await self.model.filter(
                        case_id=case_id,
                        step_no=step_no,
                        step_code=step_code,
                        state__not=1
                    ).exclude(step_code=step_code).first()
                    if existing_step_instance:
                        error_message: str = (
                            f"第({sid})步骤更新失败, "
                            f"根据(case_id={case_id}, step_no={step_no}, step_code={step_code})条件查询步骤信息失败, "
                            f"同一用例下步骤序号不允许重复"
                        )
                        LOGGER.error(error_message)
                        raise DataBaseStorageException(message=error_message)

                # 业务层验证：如果更新了用例ID，检查用例是否存在
                if "case_id" in update_dict:
                    case_id: int = update_dict.get("case_id", step_instance.case_id)
                    case: Optional[AutoTestApiCaseInfo] = await AUTOTEST_API_CASE_CRUD.get_by_id(
                        case_id=case_id, on_error=False)
                    if not case:
                        error_message: str = (
                            f"第({sid})步骤更新失败, "
                            f"根据(case_id={case_id})条件查询用例信息失败, "
                            f"所属用例信息不存在"
                        )
                        LOGGER.error(error_message)
                        raise NotFoundException(message=error_message)

                # 业务层验证：如果更新了父步骤ID，检查父步骤是否存在
                if "parent_step_id" in update_dict and update_dict["parent_step_id"]:
                    parent_step_id: int = update_dict["parent_step_id"]
                    parent_step = await self.get_by_id(step_id=parent_step_id, on_error=False)
                    if not parent_step:
                        error_message: str = (
                            f"第({sid})步骤更新失败, "
                            f"根据(step_id={parent_step_id})条件查询步骤信息失败, "
                            f"父级步骤信息不存在"
                        )
                        LOGGER.error(error_message)
                        raise NotFoundException(message=error_message)

                    # 业务层验证：确保父步骤属于同一个用例
                    case_id = update_dict.get("case_id", step_instance.case_id)
                    if parent_step.case_id != case_id:
                        error_message: str = (
                            f"第({sid})步骤更新失败, "
                            f"父级步骤(id={parent_step_id})和当前步骤(id={case_id})不一致"
                        )
                        LOGGER.error(error_message)
                        raise DataBaseStorageException(message=error_message)

                    # 业务层验证：验证父步骤类型(只有循环结构和条件分支允许拥有子级步骤)
                    if parent_step.step_type not in allowed_children_types:
                        error_message: str = (
                            f"第({sid})步骤更新失败, "
                            f"父级步骤(id={parent_step_id})的类型({parent_step.step_type})不允许包含子步骤"
                            f"(仅允许'循环结构'和'条件分支'类型的步骤包含子步骤)"
                        )
                        LOGGER.error(error_message)
                        raise ParameterException(message=error_message)

                    # 业务层验证：检查是否形成循环引用（包括深层循环引用）
                    if parent_step.id == step_id:
                        error_message: str = (
                            f"第({sid})步骤更新失败, "
                            f"父级步骤(id={parent_step_id})和当前步骤(id={step_id})冲突, "
                            f"不能将自身设置为父步骤"
                        )
                        LOGGER.error(error_message)
                        raise DataBaseStorageException(message=error_message)

                    # 业务层验证：检查深层循环引用（防止父步骤的父步骤链中包含当前步骤）
                    visited: Set = set()
                    current_parent_id = parent_step.parent_step_id
                    while current_parent_id:
                        if current_parent_id == step_id:
                            error_message: str = (
                                f"第({sid})步骤更新失败, "
                                f"父级步骤(id={parent_step_id})和当前步骤(id={step_id})冲突, "
                                f"不能将自身设置为父步骤"
                            )
                            LOGGER.error(error_message)
                            raise DataBaseStorageException(message=error_message)
                        if current_parent_id in visited:
                            break
                        visited.add(current_parent_id)
                        parent = await self.get_by_id(step_id=current_parent_id, on_error=False)
                        if not parent:
                            break
                        current_parent_id = parent.parent_step_id
                    # 如果检测到循环引用，跳过当前步骤的更新
                    if current_parent_id == step_id:
                        continue

                # 业务层验证：如果更新了引用用例ID，检查引用用例是否存在
                if "quote_case_id" in update_dict and update_dict["quote_case_id"]:
                    quote_case_id: int = update_dict["quote_case_id"]
                    await AUTOTEST_API_CASE_CRUD.get_by_id(case_id=quote_case_id, on_error=True)

                try:
                    updated_instance = await self.update(id=step_id, obj_in=update_dict)
                except Exception as e:
                    error_message: str = f"第({sid})步骤更新失败, 错误描述: {e}"
                    LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                    raise DataBaseStorageException(message=error_message) from e

                processed_step_codes.setdefault(updated_instance.case_id, set()).add(updated_instance.step_code)
                step_dict: Dict[str, Any] = await updated_instance.to_dict(
                    include_fields=["step_no", "step_code", "step_name"]
                )
                updated_count += 1
                step_dict["created"] = False
                step_dict["step_id"] = step_id
                success_detail.append(step_dict)
                # 递归处理子步骤
                children: List[AutoTestStepTreeUpdateItem] = step_data.children
                if children:
                    child_result = await self.batch_update_or_create_steps(
                        steps_data=children,
                        parent_step_id=step_id,
                    )
                    created_count += child_result["created_count"]
                    updated_count += child_result["updated_count"]
                    processed_step_codes[case_id].update(child_result["process_detail"][case_id])
                    success_detail.extend(child_result.get("success_detail", []))

        return {
            "created_count": created_count,
            "updated_count": updated_count,
            "process_detail": processed_step_codes,
            "success_detail": success_detail
        }

    async def execute_single_case(
            self,
            case_id: int,
            report_type: AutoTestReportType,
            initial_variables: Optional[List[Dict[str, Any]]] = None,
            env_name: Optional[str] = None,
            task_code: Optional[str] = None,
            batch_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        if initial_variables is None:
            initial_variables = []
        if not isinstance(initial_variables, list):
            initial_variables = []

        # 1. 查询用例信息
        case_instance = await AUTOTEST_API_CASE_CRUD.get_by_id(case_id=case_id, on_error=True)
        case_dict = await case_instance.to_dict(
            include_fields={"id", "case_code", "case_name"},
            replace_fields={"id": "case_id"}
        )
        LOGGER.info(f"查询用例信息(case_id={case_id})成功, 结果: {case_dict}")

        # 2. 查询步骤树数据
        tree_data_count: Dict[str, Any] = {}
        tree_data = await self.get_by_case_id(case_id)
        if "total_steps" in tree_data[-1]:
            tree_data_count = tree_data.pop(-1)
        if not tree_data_count or tree_data_count.get("total_steps") == 0:
            error_message: str = f"查询步骤为空, 用例(case_id={case_id})没有任何可执行的根步骤"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 3. 规范化步骤数据
        LOGGER.info(f"查询步骤树数据(case_id={case_id})成功, 结果: {tree_data_count}")
        tree_data = [AutoTestToolService.normalize_step(step) for step in tree_data]

        # 4. 合并会话变量：用例级 session_variables → 步骤树中收集的 session_variables → 入参 initial_variables（同 key 后者覆盖）
        merge_all_variables: Dict[str, Any] = {}
        case_session_variables = getattr(case_instance, "session_variables", None) or []
        all_step_session_variables = AutoTestToolService.collect_session_variables(tree_data)
        for item in case_session_variables:
            if isinstance(item, dict) and item.get("key"):
                merge_all_variables[item["key"]] = item
        for item in all_step_session_variables:
            if isinstance(item, dict) and "key" in item:
                merge_all_variables[item.get("key")] = item
        for item in initial_variables:
            if isinstance(item, dict) and "key" in item:
                merge_all_variables[item.get("key")] = item
        initial_variables = list(merge_all_variables.values())
        LOGGER.info(f"步骤树数据规范检查成功, 收集会话变量成功")

        # 5. 获取根步骤
        root_steps = [s for s in tree_data if s.get("parent_step_id") is None]
        if not root_steps:
            error_message: str = f"获取用例(case_id={case_id})根步骤失败, 没有任何可执行的根步骤"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 6. 执行用例（延后落库）：执行阶段不持事务，落库阶段单事务，保证「要么全部成功要么全部失败」且不长时间占锁
        engine = AutoTestStepExecutionEngine(save_report=True, task_code=task_code, batch_code=batch_code, defer_save=True)
        results, logs, report_code, statistics, session_variables, report_create_for_defer, pending_details_for_defer = await engine.execute_case(
            case=case_dict,
            steps=root_steps,
            initial_variables=initial_variables,
            env_name=env_name,
            report_type=report_type,
        )
        if report_create_for_defer is not None and pending_details_for_defer is not None:
            try:
                async with in_transaction():
                    report_instance = await AUTOTEST_API_REPORT_CRUD.create_report(report_create_for_defer)
                    created_report_code = report_instance.report_code
                    for detail_create in (pending_details_for_defer or []):
                        detail_with_report = detail_create.model_copy(update={"report_code": created_report_code})
                        await AUTOTEST_API_DETAIL_CRUD.create_detail(detail_with_report)
                    case_state = statistics.get("failed_steps", 0) == 0
                    case_last_time = report_create_for_defer.case_ed_time
                    await AUTOTEST_API_CASE_CRUD.update_case(AutoTestApiCaseUpdate(
                        case_id=case_id,
                        case_state=case_state,
                        case_last_time=case_last_time,
                    ))
            except Exception as e:
                LOGGER.error(f"执行或调试步骤树(运行模式)时发生未知异常，错误描述: {e}\n{traceback.format_exc()}")

            # 返回运行模式的简化结果
            result_data = {
                "success": statistics.get("failed_steps", 0) == 0,
                "total_steps": statistics.get("total_steps", 0),
                "success_steps": statistics.get("success_steps", 0),
                "failed_steps": statistics.get("failed_steps", 0),
                "pass_ratio": statistics.get("pass_ratio", 0.0),
                "report_code": created_report_code,
                "saved_to_database": True,
                "case_id": case_id,
                "case_code": case_dict.get("case_code"),
                "case_name": case_dict.get("case_name"),
            }

            return result_data

    async def batch_execute_cases(
            self,
            case_ids: List[int],
            report_type: AutoTestReportType,
            initial_variables: Optional[List[Dict[str, Any]]] = None,
            env_name: Optional[str] = None,
            task_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        if initial_variables is None:
            initial_variables = []
        if not isinstance(initial_variables, list):
            initial_variables = []

        total_cases: int = len(case_ids)
        success_cases: int = 0
        failed_cases: int = 0
        results: List[Dict[str, Any]] = []
        LOGGER.info(f"{'= ' * 20}批量执行开始{'= ' * 20}")
        LOGGER.info(f"本次批量执行的用例ID列表: {case_ids}")
        batch_code: str = f"{int(datetime.datetime.now().timestamp())}-{uuid.uuid4().hex.upper()}"
        for case_id in case_ids:
            try:
                # 每个用例独立开启事务执行
                LOGGER.info(f"==========> 执行用例ID: {case_id} 开始")
                result = await self.execute_single_case(
                    case_id=case_id,
                    initial_variables=initial_variables,
                    env_name=env_name,
                    report_type=report_type,
                    task_code=task_code,
                    batch_code=batch_code,
                )
                result["error"] = None
                results.append(result)
                if result.get("success", False):
                    success_cases += 1
                else:
                    failed_cases += 1
            except Exception as e:
                # 记录失败信息，但不影响其他用例的执行
                error_message: str = f"执行用例ID: {case_id} 异常, 错误描述: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                failed_cases += 1
                results.append({
                    "case_id": case_id,
                    "success": False,
                    "error": error_message,
                    "saved_to_database": False
                })
            LOGGER.info(f"==========> 执行用例ID: {case_id} 结束")
        LOGGER.info(f"{'= ' * 20}批量执行结束{'= ' * 20}")
        return {
            "total_cases": total_cases,
            "success_cases": success_cases,
            "failed_cases": failed_cases,
            "results": results,
            "summary": {
                "success_rate": success_cases / total_cases if total_cases > 0 else 0.0,
                "all_success": failed_cases == 0
            }
        }


AUTOTEST_API_STEP_CRUD = AutoTestApiStepCrud()
