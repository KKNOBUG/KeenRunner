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

from backend.applications.aotutest.schemas.autotest_case_schema import AutoTestCaseCreate, AutoTestCaseUpdate
from backend.applications.aotutest.models.autotest_model import AutoTestStepMapping, AutoTestStepInfo, AutoTestCaseInfo
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException


class AutoTestCaseCrud(ScaffoldCrud[AutoTestCaseInfo, AutoTestCaseCreate, AutoTestCaseUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestCaseInfo)

    async def get_by_id(self, case_id: int) -> Optional[AutoTestCaseInfo]:
        """根据ID查询用例信息"""
        return await self.model.filter(id=case_id, state=-1).first()

    async def create_case(self, case_in: AutoTestCaseCreate) -> AutoTestCaseInfo:
        """创建用例信息"""
        # 检查用例名称和项目ID的唯一性
        existing_case = await self.model.filter(case_name=case_in.case_name, project_id=case_in.project_id).first()
        if existing_case:
            raise DataAlreadyExistsException(
                message=f"项目(id={case_in.project_id})下用例名称(case_name={case_in.case_name})已存在"
            )

        try:
            case_dict = case_in.dict()
            case_dict["case_version"] = 1
            instance = await self.create(case_dict)
            return instance
        except IntegrityError as e:
            raise DataAlreadyExistsException(message=f"创建用例失败: {str(e)}")

    async def update_case(self, case_in: AutoTestCaseUpdate) -> AutoTestCaseInfo:
        """更新用例信息"""
        case_id = case_in.id
        instance = await self.query(case_id)
        if not instance:
            raise NotFoundException(message=f"用例(id={case_id})信息不存在")

        # 构建更新字典
        update_dict = {
            key: value for key, value in case_in.model_dump(exclude_unset=True, exclude={"id"}).items()
            if value is not None
        }

        # 如果更新了用例名称或项目ID，检查唯一性
        if "case_name" in update_dict or "project_id" in update_dict:
            case_name = update_dict.get("case_name", instance.case_name)
            project_id = update_dict.get("project_id", instance.project_id)
            existing_case = await self.model.filter(case_name=case_name, project_id=project_id).exclude(
                id=case_id).first()
            if existing_case:
                raise DataAlreadyExistsException(
                    message=f"项目(id={project_id})下用例名称(case_name={case_name})已存在"
                )
        try:
            update_dict["case_version"] = instance.case_version + 1
            instance = await self.update(id=case_id, obj_in=update_dict)
            return instance
        except DoesNotExist:
            raise NotFoundException(message=f"用例(id={case_id})信息不存在")
        except IntegrityError as e:
            raise DataAlreadyExistsException(message=f"更新用例失败: {str(e)}")

    async def delete_case(self, case_id: int) -> AutoTestCaseInfo:
        """删除用例信息"""
        instance = await self.query(case_id)
        if not instance:
            raise NotFoundException(message=f"用例(id={case_id})信息不存在")

        # 检查是否有步骤映射关联
        mappings_count = await AutoTestStepMapping.filter(case__id=case_id).count()
        if mappings_count > 0:
            raise DataAlreadyExistsException(
                message=f"用例(id={case_id})存在步骤映射，无法删除"
            )

        # 检查是否被其他用例引用
        quote_steps_count = await AutoTestStepInfo.filter(quote_case__id=case_id).count()
        if quote_steps_count > 0:
            raise DataAlreadyExistsException(
                message=f"用例(id={case_id})被其他用例引用，无法删除"
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


AUTO_TEST_CASE_CRUD = AutoTestCaseCrud()
