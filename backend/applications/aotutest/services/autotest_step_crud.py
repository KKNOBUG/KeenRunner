# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_crud.py
@DateTime: 2025/4/28
"""
from typing import Optional, List, Dict, Any

from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.expressions import Q

from backend.applications.aotutest.models.autotest_model import (
    AutoTestApiStepInfo, AutoTestApiCaseInfo
)
from backend.applications.aotutest.schemas.autotest_step_schema import AutoTestApiStepCreate, AutoTestApiStepUpdate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException


class AutoTestApiStepCrud(ScaffoldCrud[AutoTestApiStepInfo, AutoTestApiStepCreate, AutoTestApiStepUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestApiStepInfo)

    async def get_by_id(self, step_id: int) -> Optional[AutoTestApiStepInfo]:
        """根据ID查询步骤明细"""
        return await self.model.filter(id=step_id, state=-1).first()

    async def get_by_case_id(self, case_id: int) -> List[Dict[str, Any]]:
        """
        根据用例ID获取所有步骤（包含所有子步骤、引用测试用例中的步骤）
        核心功能：通过测试用例信息id查询所拥有的所有子级步骤
        """
        # 业务层验证：检查用例是否存在
        case = await AutoTestApiCaseInfo.filter(id=case_id, state=-1).first()
        if not case:
            raise NotFoundException(message=f"用例(id={case_id})信息不存在")

        # 获取所有根步骤（没有父步骤的步骤）
        root_steps = await self.model.filter(
            case_id=case_id,
            parent_step_id__isnull=True,
            state=-1
        ).order_by("step_no").all()

        # 递归构建步骤树
        async def build_step_tree(step: AutoTestApiStepInfo) -> Dict[str, Any]:
            # 获取步骤基本信息
            step_dict = await step.to_dict(fk=False)

            # 获取用例信息（业务层手动查询）
            if step.case_id:
                case = await AutoTestApiCaseInfo.filter(id=step.case_id, state=-1).first()
                if case:
                    step_dict["case"] = await case.to_dict()

            # 获取子步骤
            children = await self.model.filter(
                parent_step_id=step.id,
                state=-1
            ).order_by("step_no").all()

            if children:
                step_dict["children"] = [await build_step_tree(child) for child in children]
            else:
                step_dict["children"] = []

            # 如果引用了其他用例，获取引用用例的所有步骤（包含子步骤）
            if step.quote_case_id:
                # 业务层验证：检查引用用例是否存在
                quote_case = await AutoTestApiCaseInfo.filter(id=step.quote_case_id, state=-1).first()
                if quote_case:
                    # 递归获取引用用例的所有根步骤
                    quote_case_root_steps = await self.model.filter(
                        case_id=step.quote_case_id,
                        parent_step_id__isnull=True,
                        state=-1
                    ).order_by("step_no").all()

                    quote_steps = []
                    for quote_step in quote_case_root_steps:
                        quote_steps.append(await build_step_tree(quote_step))

                    step_dict["quote_steps"] = quote_steps
                    # 添加引用用例的基本信息
                    step_dict["quote_case"] = await quote_case.to_dict()
                else:
                    step_dict["quote_steps"] = []
                    step_dict["quote_case"] = None
            else:
                step_dict["quote_steps"] = []
                step_dict["quote_case"] = None

            return step_dict

        # 构建所有根步骤的树
        result = []
        for root_step in root_steps:
            result.append(await build_step_tree(root_step))

        return result

    async def create_step(self, step_in: AutoTestApiStepCreate) -> AutoTestApiStepInfo:
        """创建步骤明细"""
        # 业务层验证：检查用例是否存在
        case = await AutoTestApiCaseInfo.filter(id=step_in.case_id, state=-1).first()
        if not case:
            raise NotFoundException(message=f"用例(id={step_in.case_id})信息不存在")

        # 业务层验证：如果指定了父步骤，检查父步骤是否存在
        if step_in.parent_step_id:
            parent_step = await self.model.filter(id=step_in.parent_step_id, state=-1).first()
            if not parent_step:
                raise NotFoundException(message=f"父级步骤(id={step_in.parent_step_id})信息不存在")
            # 确保父步骤属于同一个用例
            if parent_step.case_id != step_in.case_id:
                raise NotFoundException(
                    message=f"父级步骤(id={step_in.parent_step_id})与当前用例(id={step_in.case_id})不匹配"
                )

        # 业务层验证：如果指定了引用用例，检查引用用例是否存在
        if step_in.quote_case_id:
            quote_case = await AutoTestApiCaseInfo.filter(id=step_in.quote_case_id, state=-1).first()
            if not quote_case:
                raise NotFoundException(message=f"引用用例(id={step_in.quote_case_id})信息不存在")

        # 检查同一用例下步骤序号是否已存在
        existing_step = await self.model.filter(
            case_id=step_in.case_id,
            step_no=step_in.step_no,
            state=-1
        ).first()
        if existing_step:
            raise DataAlreadyExistsException(
                message=f"用例(id={step_in.case_id})下步骤序号(step_no={step_in.step_no})已存在"
            )

        try:
            instance = await self.create(step_in)
            # 重新加载步骤数据
            return await self.get_by_id(instance.id)
        except IntegrityError as e:
            raise DataAlreadyExistsException(message=f"创建步骤明细失败: {str(e)}")

    async def update_step(self, step_in: AutoTestApiStepUpdate) -> AutoTestApiStepInfo:
        """更新步骤明细"""
        step_id = step_in.id
        instance = await self.query(step_id)
        if not instance or instance.state != -1:
            raise NotFoundException(message=f"步骤明细(id={step_id})信息不存在")

        # 构建更新字典
        update_dict = {
            key: value for key, value in step_in.model_dump(exclude_unset=True, exclude={"id"}).items()
            if value is not None
        }

        # 如果更新了步骤序号，检查是否冲突
        if "step_no" in update_dict:
            case_id = update_dict.get("case_id", instance.case_id)
            existing_step = await self.model.filter(
                case_id=case_id,
                step_no=update_dict["step_no"],
                state=-1
            ).exclude(id=step_id).first()
            if existing_step:
                raise DataAlreadyExistsException(
                    message=f"用例(id={case_id})下步骤序号(step_no={update_dict['step_no']})已存在"
                )

        # 业务层验证：如果更新了用例ID，检查用例是否存在
        if "case_id" in update_dict:
            case = await AutoTestApiCaseInfo.filter(id=update_dict["case_id"], state=-1).first()
            if not case:
                raise NotFoundException(message=f"用例(id={update_dict['case_id']})信息不存在")

        # 业务层验证：如果更新了父步骤ID，检查父步骤是否存在
        if "parent_step_id" in update_dict:
            if update_dict["parent_step_id"]:
                parent_step = await self.model.filter(id=update_dict["parent_step_id"], state=-1).first()
                if not parent_step:
                    raise NotFoundException(message=f"父级步骤(id={update_dict['parent_step_id']})信息不存在")
                # 确保父步骤属于同一个用例
                case_id = update_dict.get("case_id", instance.case_id)
                if parent_step.case_id != case_id:
                    raise NotFoundException(
                        message=f"父级步骤(id={update_dict['parent_step_id']})与当前用例(id={case_id})不匹配"
                    )
                # 检查是否形成循环引用
                if parent_step.id == step_id:
                    raise DataAlreadyExistsException(message="不能将自身设置为父步骤")
                # 检查循环引用（防止父步骤的父步骤链中包含当前步骤）
                visited = set()
                current_parent_id = parent_step.parent_step_id
                while current_parent_id:
                    if current_parent_id == step_id:
                        raise DataAlreadyExistsException(message="检测到循环引用，无法更新步骤")
                    if current_parent_id in visited:
                        break
                    visited.add(current_parent_id)
                    parent = await self.model.filter(id=current_parent_id, state=-1).first()
                    if not parent:
                        break
                    current_parent_id = parent.parent_step_id

        # 业务层验证：如果更新了引用用例ID，检查引用用例是否存在
        if "quote_case_id" in update_dict and update_dict["quote_case_id"]:
            quote_case = await AutoTestApiCaseInfo.filter(id=update_dict["quote_case_id"], state=-1).first()
            if not quote_case:
                raise NotFoundException(message=f"引用用例(id={update_dict['quote_case_id']})信息不存在")

        try:
            instance = await self.update(id=step_id, obj_in=update_dict)
            # 重新加载步骤数据
            return await self.get_by_id(instance.id)
        except DoesNotExist:
            raise NotFoundException(message=f"步骤明细(id={step_id})信息不存在")
        except IntegrityError as e:
            raise DataAlreadyExistsException(message=f"更新步骤明细失败: {str(e)}")

    async def delete_step(self, step_id: int) -> AutoTestApiStepInfo:
        """删除步骤明细（软删除）"""
        instance = await self.query(step_id)
        if not instance or instance.state != -1:
            raise NotFoundException(message=f"步骤明细(id={step_id})信息不存在")

        # 检查是否有子步骤
        children_count = await self.model.filter(parent_step_id=step_id, state=-1).count()
        if children_count > 0:
            raise DataAlreadyExistsException(
                message=f"步骤明细(id={step_id})存在子步骤，无法删除"
            )

        # 软删除
        instance.state = 1
        await instance.save()
        return instance

    async def select_steps(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        """按条件查询步骤明细"""
        # 默认只查询未删除的记录
        search &= Q(state=-1)
        return await self.list(
            page=page,
            page_size=page_size,
            search=search,
            order=order
        )


AUTOTEST_API_STEP_CRUD = AutoTestApiStepCrud()

