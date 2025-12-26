# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_crud.py
@DateTime: 2025/4/28
"""
from typing import Optional, Dict, Any, List, Set

from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from backend.applications.aotutest.schemas.autotest_case_schema import AutoTestApiCaseCreate, AutoTestApiCaseUpdate
from backend.applications.aotutest.models.autotest_model import AutoTestApiStepInfo, AutoTestApiCaseInfo
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException


class AutoTestApiCaseCrud(ScaffoldCrud[AutoTestApiCaseInfo, AutoTestApiCaseCreate, AutoTestApiCaseUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestApiCaseInfo)

    async def get_by_id(self, case_id: int) -> Optional[AutoTestApiCaseInfo]:
        """根据ID查询用例信息"""
        return await self.model.filter(id=case_id, state__not=1).first()

    async def get_by_code(self, case_code: str) -> Optional[AutoTestApiCaseInfo]:
        """根据code查询用例信息"""
        return await self.model.filter(case_code=case_code, state__not=1).first()

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True,
    ) -> Optional[AutoTestApiCaseInfo]:
        """根据条件查询用例信息"""
        stmt: QuerySet = self.model.filter(**conditions, state__not=1)
        return await (stmt.first() if only_one else stmt.all())

    async def create_case(self, case_in: AutoTestApiCaseCreate) -> AutoTestApiCaseInfo:
        """创建用例信息"""
        # 检查用例名称和项目ID的唯一性
        existing_case = await self.model.filter(case_name=case_in.case_name, case_project=case_in.case_project).first()
        if existing_case:
            raise DataAlreadyExistsException(
                message=f"项目(id={case_in.case_project})下用例名称(case_name={case_in.case_name})已存在"
            )
        try:
            case_dict = case_in.dict()
            case_dict["case_version"] = 1
            instance = await self.create(case_dict)
            return instance
        except IntegrityError as e:
            raise DataAlreadyExistsException(message=f"创建用例失败: {str(e)}")

    async def update_case(self, case_in: AutoTestApiCaseUpdate) -> AutoTestApiCaseInfo:
        """更新用例信息"""
        case_id = case_in.case_id
        instance = await self.query(case_id)
        if not instance:
            raise NotFoundException(message=f"用例(id={case_id})信息不存在")

        # 构建更新字典
        update_dict = {
            key: value for key, value in case_in.model_dump(exclude_unset=True, exclude={"id"}).items()
            if value is not None
        }

        # 如果更新了用例名称或项目ID，检查唯一性
        if "case_name" in update_dict or "case_project" in update_dict:
            case_name = update_dict.get("case_name", instance.case_name)
            case_project = update_dict.get("case_project", instance.case_project)
            existing_case = await self.model.filter(
                case_name=case_name,
                case_project=case_project
            ).exclude(id=case_id).first()
            if existing_case:
                raise DataAlreadyExistsException(
                    message=f"项目(id={case_project})下用例名称(case_name={case_name})已存在"
                )
        try:
            update_dict["case_version"] = instance.case_version + 1
            instance = await self.update(id=case_id, obj_in=update_dict)
            return instance
        except DoesNotExist:
            raise NotFoundException(message=f"用例(id={case_id})信息不存在")
        except IntegrityError as e:
            raise DataAlreadyExistsException(message=f"更新用例失败: {str(e)}")

    async def delete_case(self, case_id: int) -> AutoTestApiCaseInfo:
        """删除用例信息"""
        instance = await self.query(case_id)
        if not instance:
            raise NotFoundException(message=f"用例(id={case_id})信息不存在")

        # 检查是否有步骤明细关联（使用普通字段查询）
        steps_count = await AutoTestApiStepInfo.filter(case_id=case_id, state__not=1).count()
        if steps_count > 0:
            raise DataAlreadyExistsException(
                message=f"用例(id={case_id})存在步骤明细，无法删除"
            )

        # 检查是否被其他用例引用（使用普通字段查询）
        quote_steps_count = await AutoTestApiStepInfo.filter(quote_case_id=case_id, state__not=1).count()
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

    async def batch_update_or_create_cases(self, cases_data: List[AutoTestApiCaseUpdate]) -> Dict[str, Any]:
        created_count: int = 0
        updated_count: int = 0
        processed_case_ids: Set = set()  # 用于去重（仅针对已有id的用例）
        passed_cases: List[Dict[str, Any]] = []  # 存储处理成功的用例信息（附带输入映射）
        failed_cases: List[Dict[str, Any]] = []

        for case_data in cases_data:
            if not isinstance(case_data, AutoTestApiCaseUpdate):
                continue
            case_id: Optional[int] = case_data.case_id
            case_code: Optional[str] = case_data.case_code
            case_name: Optional[str] = case_data.case_name
            case_project: Optional[str] = case_data.case_project
            # 去重：对于已有id的用例，避免重复处理
            if case_id and case_code and (case_id, case_code) in processed_case_ids:
                continue
            try:
                # 检查用例是否存在
                if not case_id and not case_code:
                    instance = None
                else:
                    instance: Optional[AutoTestApiCaseInfo] = await self.get_by_conditions(
                        only_one=True,
                        conditions={"id": case_id, "case_code": case_code}
                    )
                if not instance:
                    # 用例不存在，执行新增，及验证必填字段
                    if not case_name:
                        failed_cases.append({"case_id": case_id, "reason": "新增用例时，用例名称字段不能为空"})
                        continue
                    if not case_project:
                        failed_cases.append({"case_id": case_id, "reason": "新增用例时，用例所属项目字段不能为空"})
                        continue
                    # 检查用例名称和项目ID的唯一性
                    existing_case: Optional[AutoTestApiCaseInfo] = await self.model.filter(
                        case_name=case_name,
                        case_project=case_project,
                        state__not=1
                    ).first()
                    if existing_case:
                        failed_cases.append({
                            "case_id": case_id,
                            "reason": f"项目(id={case_project})下用例名称(name={case_name})已存在，无法新增"
                        })
                        continue
                    # 构建新增数据（id、case_code 由数据库自动生成）
                    create_dict: Dict[str, Any] = {
                        "case_name": case_name,
                        "case_project": case_project,
                        "case_desc": case_data.case_desc,
                        "case_tags": case_data.case_tags,
                        "case_steps": case_data.case_steps
                    }
                    # 执行新增
                    new_instance: AutoTestApiCaseInfo = await self.create(create_dict)
                    processed_case_ids.add((new_instance.id, new_instance.case_code))
                    case_dict: Dict[str, Any] = await new_instance.to_dict(
                        include_fields=["case_code", "case_name"]
                    )
                    created_count += 1
                    case_dict["created"] = True
                    case_dict["case_id"] = new_instance.id
                    passed_cases.append(case_dict)
                else:
                    # 用例存在，执行更新
                    # 如果没有任何可更新的字段，跳过
                    if not case_data:
                        processed_case_ids.add((case_id, case_code))
                        case_dict: Dict[str, Any] = await instance.to_dict(
                            include_fields=["case_code", "case_name"]
                        )
                        case_dict["created"] = False
                        case_dict["case_id"] = case_id
                        passed_cases.append(case_dict)
                        continue

                    # 如果更新了用例名称或项目ID，检查唯一性
                    if "case_name" in case_data or "case_project" in case_data:
                        existing_case: Optional[AutoTestApiCaseInfo] = await self.model.filter(
                            case_name=case_name,
                            case_project=case_project,
                            state__not=1
                        ).exclude(id=case_id).first()
                        if existing_case:
                            failed_cases.append({
                                "case_id": case_id,
                                "reason": f"项目(id={case_project})下用例名称(name={case_name})已存在"
                            })
                            continue

                    # 执行更新
                    case_data.case_version = instance.case_version + 1
                    case_data: Dict[str, Any] = case_data.model_dump(
                        exclude_unset=True,
                        exclude={"id", "state", "case_id", "case_code", "created_user", "created_time"},
                    )
                    updated_instance: AutoTestApiCaseInfo = await self.update(id=case_id, obj_in=case_data)
                    processed_case_ids.add((case_id, case_code))
                    case_dict: Dict[str, Any] = await updated_instance.to_dict(
                        include_fields=["case_code", "case_name"]
                    )
                    updated_count += 1
                    case_dict["created"] = True
                    case_dict["case_id"] = case_id
                    passed_cases.append(case_dict)
            except Exception as e:
                failed_cases.append({"case_id": case_id, "reason": str(e)})

        return {
            "created_count": created_count,
            "updated_count": updated_count,
            "failed_cases": failed_cases,
            "passed_cases": passed_cases
        }


AUTOTEST_API_CASE_CRUD = AutoTestApiCaseCrud()
