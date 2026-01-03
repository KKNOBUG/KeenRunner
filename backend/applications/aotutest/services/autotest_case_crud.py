# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_crud.py
@DateTime: 2025/4/28
"""
from typing import Optional, Dict, Any, List, Set

from tortoise.exceptions import DoesNotExist, IntegrityError, FieldError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from backend.applications.aotutest.models.autotest_model import AutoTestApiStepInfo, AutoTestApiCaseInfo
from backend.applications.aotutest.schemas.autotest_case_schema import AutoTestApiCaseCreate, AutoTestApiCaseUpdate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    ParameterException,
    TypeRejectException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)


class AutoTestApiCaseCrud(ScaffoldCrud[AutoTestApiCaseInfo, AutoTestApiCaseCreate, AutoTestApiCaseUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestApiCaseInfo)

    async def get_by_id(self, case_id: int, on_error: bool = False) -> Optional[AutoTestApiCaseInfo]:
        if not case_id:
            raise ParameterException(message="参数(case_id)不允许为空")
        instance = await self.model.filter(id=case_id, state__not=1).first()
        if not instance and on_error:
            raise NotFoundException(message=f"用例(id={case_id})不存在")
        return instance

    async def get_by_code(self, case_code: str, on_error: bool = False) -> Optional[AutoTestApiCaseInfo]:
        if not case_code:
            raise ParameterException(message="参数(case_code)不允许为空")
        instance = await self.model.filter(case_code=case_code, state__not=1).first()
        if not instance and on_error:
            raise NotFoundException(message=f"用例(code={case_code})不存在")
        return instance

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True,
            on_error: bool = False
    ) -> Optional[AutoTestApiCaseInfo]:
        try:
            stmt: QuerySet = self.model.filter(**conditions, state__not=1)
            instances = await (stmt.first() if only_one else stmt.all())
        except FieldError as e:
            raise ParameterException(message=f"查询'用例'异常, 错误描述: {e}")

        if not instances and on_error:
            raise NotFoundException(message=f"按条件{conditions}查询'用例'无记录")
        return instances

    async def create_case(self, case_in: AutoTestApiCaseCreate) -> AutoTestApiCaseInfo:
        case_name: str = case_in.case_name
        case_project: int = case_in.case_project
        existing_case = await self.model.filter(
            case_name=case_in.case_name,
            case_project=case_in.case_project,
            state__not=1
        ).first()
        if existing_case:
            raise DataAlreadyExistsException(message=f"应用(id={case_project})下用例名称(case_name={case_name})已存在")
        try:
            case_dict = case_in.model_dump(exclude_none=True, exclude_unset=True)
            case_dict["case_version"] = 1
            instance = await self.create(case_dict)
            return instance
        except IntegrityError as e:
            raise DataBaseStorageException(message=f"创建用例失败, 违法约束规则: {str(e)}")

    async def update_case(self, case_in: AutoTestApiCaseUpdate) -> AutoTestApiCaseInfo:
        case_id: Optional[int] = case_in.case_id
        case_code: Optional[str] = case_in.case_code
        if case_id:
            instance = await self.get_by_id(case_id=case_id, on_error=True)
        else:
            instance = await self.get_by_code(case_code=case_code, on_error=True)
            case_id: int = instance.id

        # 如果更新了用例名称或项目ID，检查唯一性
        update_dict = case_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"case_id", "case_code"}
        )
        if "case_name" in update_dict or "case_project" in update_dict:
            case_name = update_dict.get("case_name", instance.case_name)
            case_project = update_dict.get("case_project", instance.case_project)
            existing_case = await self.model.filter(
                case_name=case_name,
                case_project=case_project,
                state__not=1
            ).exclude(id=case_id).first()
            if existing_case:
                raise DataAlreadyExistsException(message=f"项目(id={case_project})下用例名称(case_name={case_name})已存在")
        try:
            update_dict["case_version"] = instance.case_version + 1
            instance = await self.update(id=case_id, obj_in=update_dict)
            return instance
        except DoesNotExist:
            raise NotFoundException(message=f"用例(id={case_id})不存在")
        except IntegrityError as e:
            raise DataBaseStorageException(message=f"更新用例失败, 违法约束规则: {str(e)}")

    async def delete_case(self, case_id: Optional[int] = None, case_code: Optional[str] = None) -> AutoTestApiCaseInfo:
        if case_id:
            instance = await self.get_by_id(case_id=case_id, on_error=True)
        else:
            instance = await self.get_by_code(case_code=case_code, on_error=True)
            case_id: int = instance.id

        # 检查是否有步骤明细关联（使用普通字段查询）
        steps_count = await AutoTestApiStepInfo.filter(case_id=case_id, state__not=1).count()
        if steps_count > 0:
            raise DataAlreadyExistsException(message=f"用例(id={case_id})存在步骤，无法删除")

        # 检查是否被其他用例引用（使用普通字段查询）
        quote_steps_count = await AutoTestApiStepInfo.filter(quote_case_id=case_id, state__not=1).count()
        if quote_steps_count > 0:
            raise DataAlreadyExistsException(message=f"用例(id={case_id})被其他用例引用，无法删除")

        instance.state = 1
        await instance.save()
        return instance

    async def select_cases(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            raise ParameterException(message=f"查询'用例'异常, 错误描述: {e}")

    async def batch_update_or_create_cases(self, cases_data: List[AutoTestApiCaseUpdate]) -> Dict[str, Any]:
        created_count: int = 0
        updated_count: int = 0
        processed_case: Set = set()  # 用于去重（仅针对已有id的用例）
        success_detail: List[Dict[str, Any]] = []  # 存储处理成功的用例信息（附带输入映射）

        for cid, case_data in enumerate(cases_data, start=1):
            if not isinstance(case_data, AutoTestApiCaseUpdate):
                raise TypeRejectException(
                    message=f"参数类型错误, 期待的是: AutoTestApiCaseUpdate类型, 得到的是{type(case_data)}类型"
                )

            case_id: Optional[int] = case_data.case_id
            case_code: Optional[str] = case_data.case_code
            case_name: Optional[str] = case_data.case_name
            case_project: Optional[str] = case_data.case_project
            # 去重：对于已有id的用例，避免重复处理
            if case_id and case_code and (case_id, case_code) in processed_case:
                continue
            # 检查用例是否存在
            if not case_id and not case_code:
                case_instance = None
            else:
                case_instance: Optional[AutoTestApiCaseInfo] = await self.get_by_conditions(
                    only_one=True,
                    conditions={"id": case_id, "case_code": case_code}
                )
            if not case_instance:
                # 用例不存在，执行新增，及验证必填字段
                if not case_name:
                    raise ParameterException(message=f"第({cid})条用例新增失败, 用例名称字段不允许为空")
                if not case_project:
                    raise ParameterException(message=f"第({cid})条用例新增失败, 用例所属项目字段不允许为空")
                # 检查用例名称和项目ID的唯一性
                existing_case_instance: Optional[AutoTestApiCaseInfo] = await self.get_by_conditions(
                    only_one=True,
                    conditions={"case_name": case_name, "case_project": case_project}
                )
                if existing_case_instance:
                    raise DataAlreadyExistsException(
                        message=f"第({cid})条用例新增失败, 项目(id={case_project})下用例名称(name={case_name})已存在"
                    )
                # 构建新增数据（id、case_code 由数据库自动生成）
                create_case_dict: Dict[str, Any] = case_data.model_dump(
                    exclude_none=True,
                    exclude_unset=True,
                    exclude={"case_id", "case_code", "case_version"}
                )
                try:
                    new_case_instance: AutoTestApiCaseInfo = await self.create(obj_in=create_case_dict)
                except Exception as e:
                    raise DataBaseStorageException(message=f"第({cid})条用例新增失败, 错误描述: {e}")
                processed_case.add((new_case_instance.id, new_case_instance.case_code))
                case_dict: Dict[str, Any] = await new_case_instance.to_dict(
                    include_fields=["case_code", "case_name", "case_project"]
                )
                created_count += 1
                case_dict["created"] = True
                case_dict["case_id"] = new_case_instance.id
                success_detail.append(case_dict)
            else:
                # 用例存在，执行更新
                # 如果没有任何可更新的字段，跳过
                update_case_dict: Dict[str, Any] = case_data.model_dump(
                    exclude_none=True,
                    exclude={"case_id", "case_code"}
                )
                if not update_case_dict:
                    processed_case.add((case_id, case_code))
                    case_dict: Dict[str, Any] = await case_instance.to_dict(
                        include_fields=["case_code", "case_name", "case_project"]
                    )
                    case_dict["created"] = False
                    case_dict["case_id"] = case_id
                    success_detail.append(case_dict)
                    continue

                # 如果更新了用例名称或项目ID，检查唯一性
                if "case_name" in update_case_dict or "case_project" in update_case_dict:
                    existing_case_instance: Optional[AutoTestApiCaseInfo] = await self.get_by_conditions(
                        only_one=True,
                        conditions={"case_name": case_name, "case_project": case_project, "id__not": case_id}
                    )
                    if existing_case_instance:
                        raise DataAlreadyExistsException(
                            message=f"第({cid})条用例新增失败, 项目(id={case_project})下用例名称(name={case_name})已存在"
                        )

                try:
                    update_case_dict["case_version"] = case_instance.case_version + 1
                    updated_instance: AutoTestApiCaseInfo = await self.update(id=case_id, obj_in=update_case_dict)
                except Exception as e:
                    raise DataBaseStorageException(message=f"第({cid})条用例更新失败, 错误描述: {e}")
                processed_case.add((case_id, case_code))
                case_dict: Dict[str, Any] = await updated_instance.to_dict(
                    include_fields=["case_code", "case_name", "case_project"]
                )
                updated_count += 1
                case_dict["created"] = False
                case_dict["case_id"] = case_id
                success_detail.append(case_dict)

        return {
            "created_count": created_count,
            "updated_count": updated_count,
            "success_detail": success_detail
        }


AUTOTEST_API_CASE_CRUD = AutoTestApiCaseCrud()
