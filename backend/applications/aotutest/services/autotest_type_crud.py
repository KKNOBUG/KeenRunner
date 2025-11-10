# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_crud.py
@DateTime: 2025/4/28
"""
from typing import Optional

from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.expressions import Q

from backend.applications.aotutest.schemas.autotest_type_schema import (
    AutoTestTypeCreate,
    AutoTestTypeUpdate,
    AutoTestTypeSelect
)
from backend.applications.aotutest.models.autotest_model import AutoTestStepType, AutoTestStepInfo
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException


class AutoTestTypeCrud(ScaffoldCrud[AutoTestStepType, AutoTestTypeCreate, AutoTestTypeUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestStepType)

    async def get_by_id(self, case_id: int) -> Optional[AutoTestStepType]:
        """根据ID查询用例信息"""
        return await self.model.filter(id=case_id, state=-1).first()

    async def create_type(self, type_in: AutoTestTypeCreate) -> AutoTestStepType:
        """创建步骤类型信息"""
        existing_type = await self.model.filter(type_name=type_in.type_name).first()
        if existing_type:
            raise DataAlreadyExistsException(
                message=f"用例步骤类型(id={type_in.type_name})已存在"
            )

        try:
            instance = await self.create(type_in)
            return instance
        except IntegrityError as e:
            raise DataAlreadyExistsException(message=f"创建用例失败: {str(e)}")

    async def update_type(self, type_in: AutoTestTypeUpdate) -> AutoTestStepType:
        """更新步骤类型信息"""
        type_id = type_in.id
        instance = await self.query(type_id)
        if not instance:
            raise NotFoundException(message=f"用例步骤类型(id={type_id})信息不存在")

        try:
            instance = await self.update(id=type_id, obj_in=type_in.dict(exclude_unset=True, exclude={"id"}))
            return instance
        except DoesNotExist:
            raise NotFoundException(message=f"用例步骤类型(id={type_id})信息不存在")
        except IntegrityError as e:
            raise DataAlreadyExistsException(message=f"更新用例失败: {str(e)}")

    async def delete_type(self, type_id: int) -> AutoTestStepType:
        """删除用例信息"""
        instance = await self.query(type_id)
        if not instance:
            raise NotFoundException(message=f"用例步骤类型(id={type_id})信息不存在")

        # 检查是否被其他用例引用
        quote_steps_count = await AutoTestStepInfo.filter(step_type__id=type_id).count()
        if quote_steps_count > 0:
            raise DataAlreadyExistsException(
                message=f"用例步骤类型(id={type_id})被其他用例引用，无法删除"
            )

        instance.state = 1
        await instance.save()
        return instance

    async def select_cases(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        """按条件查询用例信息"""
        return await self.list(
            page=page,
            page_size=page_size,
            search=search,
            order=order
        )


AUTO_TEST_TYPE_CRUD = AutoTestTypeCrud()
