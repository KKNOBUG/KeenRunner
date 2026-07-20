# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_crud.py
@DateTime: 2025/4/28
"""
import traceback
from typing import Optional, Dict, Any, List, Set

from tortoise.exceptions import DoesNotExist, IntegrityError, FieldError
from tortoise.expressions import Q

from backend.applications.aotutest.models.autotest_model import AutoTestApiStepInfo, AutoTestApiCaseInfo
from backend.applications.aotutest.schemas.autotest_case_schema import AutoTestApiCaseCreate, AutoTestApiCaseUpdate
from backend.applications.aotutest.services.autotest_tag_crud import AutoTestApiTagCrud
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)
from backend.enums import AutoTestCaseType


class AutoTestApiCaseCrud(ScaffoldCrud[AutoTestApiCaseInfo, AutoTestApiCaseCreate, AutoTestApiCaseUpdate]):
    """用例 CRUD 与批量更新相关业务。"""

    def __init__(self):
        """初始化 CRUD，绑定模型 AutoTestApiCaseInfo。"""
        super().__init__(model=AutoTestApiCaseInfo)

    async def get_by_id(self, case_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestApiCaseInfo]:
        """
        按主键 ID 查询用例。

        :param case_id: 用例主键 ID
        :param on_error: 未找到时是否抛出 NotFoundException
        :param kwargs: 额外过滤条件
        :return: 用例实例或 None
        :raises ParameterException: case_id 为空
        :raises NotFoundException: on_error 为 True 且记录不存在
        """
        if not case_id:
            error_message: str = "查询用例信息失败, 参数(case_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.get_or_none(id=case_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询用例信息失败, 用例(id={case_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, case_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestApiCaseInfo]:
        """
        按用例标识代码查询用例。

        :param case_code: 用例标识代码
        :param on_error: 未找到时是否抛出 NotFoundException
        :param kwargs: 额外过滤条件
        :return: 用例实例或 None
        :raises ParameterException: case_code 为空
        :raises NotFoundException: on_error 为 True 且记录不存在
        """
        if not case_code:
            error_message: str = "查询用例信息失败, 参数(case_code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(case_code=case_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询用例信息失败, 用例(code={case_code})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def create_case(self, case_in: AutoTestApiCaseCreate) -> AutoTestApiCaseInfo:
        """
        创建用例，校验标签存在及同项目下用例名唯一。

        :param case_in: 用例创建 schema
        :return: 创建后的用例实例
        :raises ParameterException: 参数异常
        :raises NotFoundException: 标签不存在
        :raises DataAlreadyExistsException: 同项目下用例名重复
        :raises DataBaseStorageException: 违反数据库约束
        """
        case_name: str = case_in.case_name
        case_project: int = case_in.case_project
        case_tags: List[int] = case_in.case_tags
        case_type: Optional[AutoTestCaseType] = case_in.case_type

        # 业务层验证: 检查标签是否全部存在
        await AutoTestApiTagCrud().get_by_ids(tag_ids=case_tags, on_error=True, state__not=1)

        # 业务层验证: 检查用例信息是否已经存在
        existing_case = await self.get_by_conditions(
            only_one=True,
            on_error=False,
            case_project=case_project,
            case_name=case_name,
            state__not=1
        )
        if existing_case:
            error_message: str = (
                f"根据条件(case_project={case_project}, case_name={case_name}, case_type={case_type})查询用例信息失败, "
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
        """
        更新用例，按 case_id 或 case_code 定位并递增 case_version。

        :param case_in: 用例更新 schema，需含 case_id 或 case_code
        :return: 更新后的用例实例
        :raises NotFoundException: 用例不存在
        :raises DataAlreadyExistsException: 同项目下用例名重复
        :raises DataBaseStorageException: 违反数据库约束
        """
        case_id: Optional[int] = case_in.case_id
        case_code: Optional[str] = case_in.case_code
        case_type: Optional[AutoTestCaseType] = case_in.case_type

        # 业务层验证：检查用例信息是否存在
        if case_id:
            instance = await self.get_by_id(case_id=case_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(case_code=case_code, on_error=True, state__not=1)
            case_id: int = instance.id
        update_dict = case_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"case_id", "case_code"}
        )

        # 业务层验证：检查标签是否全部存在
        if "case_tags" in update_dict:
            case_tags = update_dict.get("case_tags", instance.case_tags)
            await AutoTestApiTagCrud().get_by_ids(tag_ids=case_tags, on_error=True, state__not=1)

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
        """
        删除用例：先硬删关联步骤，再删除用例；公共脚本需无引用。

        :param case_id: 用例主键 ID，与 case_code 二选一
        :param case_code: 用例标识代码，与 case_id 二选一
        :return: 删除后的用例实例
        :raises NotFoundException: 用例不存在
        :raises DataAlreadyExistsException: 公共脚本仍被引用
        """
        # 业务层验证: 检查用例是否存在
        if case_id:
            instance = await self.get_by_id(case_id=case_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(case_code=case_code, on_error=True, state__not=1)
            case_id: int = instance.id

        case_type: AutoTestCaseType = instance.case_type
        if case_type == AutoTestCaseType.PUBLIC_SCRIPT:
            # 业务层验证：检查用例是否被引用
            quote_steps_count = await AutoTestApiStepInfo.filter(quote_case_id=case_id, state__not=1).count()
            if quote_steps_count > 0:
                error_message: str = (
                    f"根据(quote_case_id={case_id})条件检查步骤信息失败, "
                    f"用例(id={case_id})存在{quote_steps_count}个引用, 无法直接删除"
                )
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)

        # 业务层验证：检查用例是否拥有步骤
        await AutoTestApiStepInfo.filter(case_id=case_id, state__not=1).delete()
        await instance.delete()
        return instance

    async def select_cases(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        """
        分页查询用例列表。

        :param search: Tortoise Q 查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)
        :raises ParameterException: 查询字段非法
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询用例信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def batch_update_or_create_cases(self, cases_data: List[AutoTestApiCaseUpdate]) -> Dict[str, Any]:
        """
        批量新增或更新用例：无 case_id/case_code 则新增，有则更新。

        :param cases_data: 用例更新 schema 列表
        :return: 含 created_count、updated_count、success_detail 的字典
        :raises TypeRejectException: 列表项类型非法
        :raises ParameterException: 必填字段缺失
        :raises DataAlreadyExistsException: 同项目下用例名重复
        :raises DataBaseStorageException: 数据库写入异常
        """
        created_count: int = 0
        updated_count: int = 0
        processed_case: Set = set()  # 用于去重（仅针对已有id的用例）
        success_detail: List[Dict[str, Any]] = []  # 存储处理成功的用例信息（附带输入映射）

        for cid, case_data in enumerate(cases_data, start=1):
            case_id: Optional[int] = case_data.case_id
            case_code: Optional[str] = case_data.case_code
            case_name: Optional[str] = case_data.case_name
            case_tags: Optional[List[int]] = case_data.case_tags
            case_project: Optional[int] = case_data.case_project
            case_type: Optional[AutoTestCaseType] = case_data.case_type
            if case_id and case_code and (case_id, case_code) in processed_case:
                continue

            # 业务层验证：检查用例是否存在
            if not case_id and not case_code:
                case_instance = None
            else:
                case_instance: Optional[AutoTestApiCaseInfo] = await self.get_by_conditions(
                    only_one=True,
                    on_error=False,
                    id=case_id,
                    case_code=case_code,
                    state__not=1
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
                    on_error=False,
                    case_project=case_project,
                    case_name=case_name,
                    case_type=case_type,
                    state__not=1
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
                    exclude_unset=True,
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
                    await AutoTestApiTagCrud().get_by_ids(tag_ids=case_tags, on_error=True, state__not=1)

                # 业务层验证：检查应用ID和用例名称的唯一性（排除当前记录）
                if "case_name" in update_case_dict or "case_project" in update_case_dict:
                    existing_case_instance: Optional[AutoTestApiCaseInfo] = await self.model.filter(
                        case_project=case_project, case_name=case_name, state__not=1
                    ).exclude(id=case_id).first()
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
