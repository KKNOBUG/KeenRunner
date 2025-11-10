# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_crud.py
@DateTime: 2025/4/28
"""
from typing import Optional

from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.expressions import Q

from backend.applications.aotutest.models.autotest_model import (
    AutoTestStepInfo, AutoTestStepType, AutoTestCaseInfo, AutoTestStepMapping
)
from backend.applications.aotutest.schemas.autotest_step_schema import AutoTestStepCreate, AutoTestStepUpdate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException


class AutoTestStepCrud(ScaffoldCrud[AutoTestStepInfo, AutoTestStepCreate, AutoTestStepUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestStepInfo)

    async def get_by_id(self, step_id: int) -> Optional[AutoTestStepInfo]:
        """根据ID查询步骤明细"""
        return await self.model.filter(id=step_id).prefetch_related(
            "step_type", "quote_case"
        ).first()

    async def create_step(self, step_in: AutoTestStepCreate) -> AutoTestStepInfo:
        """创建步骤明细"""
        # 检查步骤类型是否存在
        step_type = await AutoTestStepType.filter(id=step_in.step_type_id).first()
        if not step_type:
            raise NotFoundException(message=f"步骤类型(id={step_in.step_type_id})信息不存在")

        # 如果指定了引用用例，检查引用用例是否存在
        if step_in.quote_case_id:
            quote_case = await AutoTestCaseInfo.filter(id=step_in.quote_case_id).first()
            if not quote_case:
                raise NotFoundException(message=f"引用用例(id={step_in.quote_case_id})信息不存在")

        try:
            instance = await self.create(step_in)
            # 重新加载关联数据
            return await self.get_by_id(instance.id)
        except IntegrityError as e:
            raise DataAlreadyExistsException(message=f"创建步骤明细失败: {str(e)}")

    async def update_step(self, step_in: AutoTestStepUpdate) -> AutoTestStepInfo:
        """更新步骤明细"""
        step_id = step_in.id
        instance = await self.query(step_id)
        if not instance:
            raise NotFoundException(message=f"步骤明细(id={step_id})信息不存在")

        # 构建更新字典
        update_dict = {
            key: value for key, value in step_in.model_dump(exclude_unset=True, exclude={"id"}).items()
            if value is not None
        }

        # 如果更新了步骤类型ID，检查步骤类型是否存在
        if "step_type_id" in update_dict:
            step_type = await AutoTestStepType.filter(id=update_dict["step_type_id"]).first()
            if not step_type:
                raise NotFoundException(message=f"步骤类型(id={update_dict['step_type_id']})信息不存在")

        # 如果更新了引用用例ID，检查引用用例是否存在
        if "quote_case_id" in update_dict and update_dict["quote_case_id"]:
            quote_case = await AutoTestCaseInfo.filter(id=update_dict["quote_case_id"]).first()
            if not quote_case:
                raise NotFoundException(message=f"引用用例(id={update_dict['quote_case_id']})信息不存在")

        try:
            instance = await self.update(id=step_id, obj_in=update_dict)
            # 重新加载关联数据
            return await self.get_by_id(instance.id)
        except DoesNotExist:
            raise NotFoundException(message=f"步骤明细(id={step_id})信息不存在")
        except IntegrityError as e:
            raise DataAlreadyExistsException(message=f"更新步骤明细失败: {str(e)}")

    async def delete_step(self, step_id: int) -> AutoTestStepInfo:
        """删除步骤明细"""
        instance = await self.query(step_id)
        if not instance:
            raise NotFoundException(message=f"步骤明细(id={step_id})信息不存在")

        # 检查是否有步骤映射关联
        mappings_count = await AutoTestStepMapping.filter(step_info__id=step_id).count()
        if mappings_count > 0:
            raise DataAlreadyExistsException(
                message=f"步骤明细(id={step_id})存在步骤映射，无法删除"
            )

        await instance.delete()
        return instance

    async def select_steps(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        """按条件查询步骤明细"""
        return await self.list(
            page=page,
            page_size=page_size,
            search=search,
            order=order,
            related=["step_type", "quote_case"]
        )


AUTO_TEST_STEP_CRUD = AutoTestStepCrud()
