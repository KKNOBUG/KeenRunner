# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_crud.py
@DateTime: 2025/4/28
"""
import traceback
from typing import Optional, Dict, Any, List, Set, Union

from tortoise.exceptions import DoesNotExist, IntegrityError, FieldError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from backend import LOGGER
from backend.applications.aotutest.models.autotest_model import AutoTestApiStepInfo, AutoTestApiCaseInfo
from backend.applications.aotutest.schemas.autotest_case_schema import AutoTestApiCaseCreate, AutoTestApiCaseUpdate
from backend.applications.aotutest.services.autotest_tag_crud import AUTOTEST_API_TAG_CRUD
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    ParameterException,
    TypeRejectException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)
from backend.enums.autotest_enum import AutoTestCaseType


class AutoTestApiCaseCrud(ScaffoldCrud[AutoTestApiCaseInfo, AutoTestApiCaseCreate, AutoTestApiCaseUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestApiCaseInfo)

    async def get_by_id(self, case_id: int, on_error: bool = False) -> Optional[AutoTestApiCaseInfo]:
        if not case_id:
            error_message: str = "查询用例信息失败, 参数(case_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(id=case_id, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询用例信息失败, 用例(id={case_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, case_code: str, on_error: bool = False) -> Optional[AutoTestApiCaseInfo]:
        if not case_code:
            error_message: str = "查询用例信息失败, 参数(case_code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(case_code=case_code, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询用例信息失败, 用例(code={case_code})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True,
            on_error: bool = False
    ) -> Optional[Union[AutoTestApiCaseInfo, List[AutoTestApiCaseInfo]]]:
        try:
            stmt: QuerySet = self.model.filter(**conditions, state__not=1)
            instances = await (stmt.first() if only_one else stmt.all())
        except FieldError as e:
            error_message: str = f"查询用例信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
        except Exception as e:
            error_message: str = f"查询用例信息发生未知异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

        if not instances and on_error:
            error_message: str = f"查询用例信息失败, 条件{conditions}不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instances

    async def create_case(self, case_in: AutoTestApiCaseCreate) -> AutoTestApiCaseInfo:
        case_name: str = case_in.case_name
        case_project: int = case_in.case_project
        case_tags: List[int] = case_in.case_tags
        case_type: Optional[AutoTestCaseType] = case_in.AutoTestCaseType

        # 业务层验证: 检查标签是否全部存在
        await AUTOTEST_API_TAG_CRUD.get_by_ids(tag_ids=case_tags, on_error=True)

        # 业务层验证: 检查用例信息是否已经存在
        existing_case = await self.model.filter(case_project=case_project, case_name=case_name, state__not=1).first()
        if existing_case:
            error_message: str = (
                f"根据(case_project={case_project}, case_name={case_name}, case_type={case_type})条件查询用例信息失败, "
                f"相同应用下用例名称不允许重复"
            )
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)
        try:
            case_dict = case_in.model_dump(exclude_none=True, exclude_unset=True)
            case_dict["case_version"] = 1
            instance = await self.create(case_dict)
            return instance
        except IntegrityError as e:
            error_message: str = f"新增用例信息失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_case(self, case_in: AutoTestApiCaseUpdate) -> AutoTestApiCaseInfo:
        case_id: Optional[int] = case_in.case_id
        case_code: Optional[str] = case_in.case_code
        case_type: Optional[AutoTestCaseType] = case_in.AutoTestCaseType

        # 业务层验证：检查用例信息是否存在
        if case_id:
            instance = await self.get_by_id(case_id=case_id, on_error=True)
        else:
            instance = await self.get_by_code(case_code=case_code, on_error=True)
            case_id: int = instance.id
        update_dict = case_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"case_id", "case_code"}
        )

        # 业务层验证：检查标签是否全部存在
        if "case_tags" in update_dict:
            case_tags = update_dict.get("case_tags", instance.case_tags)
            await AUTOTEST_API_TAG_CRUD.get_by_ids(tag_ids=case_tags, on_error=True)

        # 业务层验证：检查应用ID和用例名称是否唯一
        if "case_name" in update_dict or "case_project" in update_dict:
            case_name = update_dict.get("case_name", instance.case_name)
            case_project = update_dict.get("case_project", instance.case_project)
            existing_case = await self.model.filter(
                case_project=case_project,
                case_name=case_name,
                state__not=1
            ).exclude(id=case_id).first()
            if existing_case:
                error_message: str = (
                    f"根据(case_project={case_project}, case_name={case_name}, case_type={case_type})条件检查用例信息失败, "
                    f"相同应用下用例名称不允许重复"
                )
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)

        try:
            update_dict["case_version"] = instance.case_version + 1
            instance = await self.update(id=case_id, obj_in=update_dict)
            return instance
        except DoesNotExist as e:
            error_message: str = f"更新用例信息失败, 用例(id={case_id}或code={case_code})不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = f"更新用例信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_case(self, case_id: Optional[int] = None, case_code: Optional[str] = None) -> AutoTestApiCaseInfo:
        # 业务层验证: 检查用例是否存在
        if case_id:
            instance = await self.get_by_id(case_id=case_id, on_error=True)
        else:
            instance = await self.get_by_code(case_code=case_code, on_error=True)
            case_id: int = instance.id

        # 业务层验证：检查用例是否拥有步骤
        steps_count = await AutoTestApiStepInfo.filter(case_id=case_id, state__not=1).count()
        if steps_count > 0:
            error_message: str = (
                f"根据(case_id={case_id})条件检查步骤信息失败, "
                f"用例(id={case_id})存在{steps_count}个步骤, 无法直接删除"
            )
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        # 业务层验证：检查用例是否被引用
        quote_steps_count = await AutoTestApiStepInfo.filter(quote_case_id=case_id, state__not=1).count()
        if quote_steps_count > 0:
            error_message: str = (
                f"根据(quote_case_id={case_id})条件检查步骤信息失败, "
                f"用例(id={case_id})存在{quote_steps_count}个引用, 无法直接删除"
            )
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        instance.state = 1
        await instance.save(update_fields={"state"})
        return instance

    async def select_cases(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询用例信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def batch_update_or_create_cases(self, cases_data: List[AutoTestApiCaseUpdate]) -> Dict[str, Any]:
        created_count: int = 0
        updated_count: int = 0
        processed_case: Set = set()  # 用于去重（仅针对已有id的用例）
        success_detail: List[Dict[str, Any]] = []  # 存储处理成功的用例信息（附带输入映射）

        for cid, case_data in enumerate(cases_data, start=1):
            if not isinstance(case_data, AutoTestApiCaseUpdate):
                raise TypeRejectException(
                    message=f"参数[case_data]必须是[AutoTestApiCaseUpdate]类型, 但得到[{type(case_data)}]类型"
                )

            case_id: Optional[int] = case_data.case_id
            case_code: Optional[str] = case_data.case_code
            case_name: Optional[str] = case_data.case_name
            case_tags: Optional[List[int]] = case_data.case_tags
            case_project: Optional[int] = case_data.case_project
            case_type: Optional[AutoTestCaseType] = case_data.AutoTestCaseType
            if case_id and case_code and (case_id, case_code) in processed_case:
                continue

            # 业务层验证：检查用例是否存在
            if not case_id and not case_code:
                case_instance = None
            else:
                case_instance: Optional[AutoTestApiCaseInfo] = await self.get_by_conditions(
                    only_one=True,
                    conditions={"id": case_id, "case_code": case_code}
                )

            # 用例不存在，执行新增，及验证必填字段
            if not case_instance:
                if not case_tags:
                    error_message: str = f"第({cid})条用例新增失败, 用例所属标签(case_tags)字段不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)
                if not case_name:
                    error_message: str = f"第({cid})条用例新增失败, 用例名称(case_name)字段不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)
                if not case_project:
                    error_message: str = f"第({cid})条用例新增失败, 用例所属项目(case_project)字段不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)

                # 业务层验证：检查应用ID和用例名称是否唯一
                existing_case_instance: Optional[AutoTestApiCaseInfo] = await self.get_by_conditions(
                    only_one=True,
                    conditions={"case_project": case_project, "case_name": case_name, "case_type": case_type}
                )
                if existing_case_instance:
                    error_message: str = (
                        f"第({cid})条用例新增失败, "
                        f"根据(case_project={case_project}, case_name={case_name}, case_type={case_type})条件检查用例信息失败, "
                        f"相同应用下用例名称不允许重复"
                    )
                    LOGGER.error(error_message)
                    raise DataAlreadyExistsException(message=error_message)

                create_case_dict: Dict[str, Any] = case_data.model_dump(
                    exclude_none=True,
                    exclude_unset=True,
                    exclude={"case_id", "case_code", "case_version"}
                )
                try:
                    new_case_instance: AutoTestApiCaseInfo = await self.create(obj_in=create_case_dict)
                except Exception as e:
                    error_message: str = f"第({cid})条用例新增失败, 错误描述: {e}"
                    LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                    raise DataBaseStorageException(message=error_message) from e

                processed_case.add((new_case_instance.id, new_case_instance.case_code))
                case_dict: Dict[str, Any] = await new_case_instance.to_dict(
                    include_fields=["case_code", "case_name", "case_project"]
                )
                created_count += 1
                case_dict["created"] = True
                case_dict["case_id"] = new_case_instance.id
                success_detail.append(case_dict)

            # 用例存在，执行更新
            else:
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

                # 业务层验证：检查标签是否全部存在
                if "case_tags" in update_case_dict:
                    case_tags = update_case_dict.get("case_tags", case_instance.case_tags)
                    await AUTOTEST_API_TAG_CRUD.get_by_ids(tag_ids=case_tags, on_error=True)

                # 业务层验证：检查应用ID和用例名称的唯一性
                if "case_name" in update_case_dict or "case_project" in update_case_dict:
                    existing_case_instance: Optional[AutoTestApiCaseInfo] = await self.get_by_conditions(
                        only_one=True,
                        conditions={"case_project": case_project, "case_name": case_name, "case_type": case_type, "id__not": case_id}
                    )
                    if existing_case_instance:
                        error_message: str = (
                            f"第({cid})条用例更新失败, "
                            f"根据(case_project={case_project}, case_name={case_name}, case_type={case_type})条件检查用例信息失败, "
                            f"相同应用下用例名称不允许重复"
                        )
                        LOGGER.error(error_message)
                        raise DataAlreadyExistsException(message=error_message)

                try:
                    update_case_dict["case_version"] = case_instance.case_version + 1
                    updated_instance: AutoTestApiCaseInfo = await self.update(id=case_id, obj_in=update_case_dict)
                except Exception as e:
                    error_message: str = f"第({cid})条用例更新失败, 错误描述: {e}"
                    LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                    raise DataBaseStorageException(message=error_message) from e

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
