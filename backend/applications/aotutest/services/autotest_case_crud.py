# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_crud.py
@DateTime: 2025/4/28
"""
import traceback
from typing import Optional, Dict, Any, List, Set, Tuple

from tortoise.exceptions import DoesNotExist, IntegrityError, FieldError
from tortoise.expressions import Q

from backend.applications.aotutest.models.autotest_case_model import AutoTestCaseModel
from backend.applications.aotutest.models.autotest_step_model import AutoTestStepModel
from backend.applications.aotutest.schemas.autotest_case_schema import AutoTestApiCaseCreate, AutoTestApiCaseUpdate
from backend.applications.aotutest.services.autotest_tag_crud import AutoTestTagCrud
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)
from backend.enums import AutoTestCaseType, AutoTestStepType, PUBLIC_CASE_TYPES, AutoTestReqArgsType
from backend.services import get_current_username

# 列表/对象型JSON字段：schema已将空数组归一为None；payload显式给出这些字段时，None代表显式清空，需回补以落库NULL
CASE_CLEARABLE_JSON_FIELDS: Tuple[str, ...] = ("case_tags", "session_variables")


def _normalize_case_tags(case_type: Optional[AutoTestCaseType], case_tags: Optional[List[int]], *, context: str = "用例") -> Optional[List[int]]:
    """用户脚本：允许打标签，公共脚本/公共接口: 禁止打标签。"""
    if case_type in PUBLIC_CASE_TYPES:
        if case_tags:
            error_message: str = f"{context}, 用例类型为[公共脚本/公共接口]时不支持打标签"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        return None
    if not case_tags:
        error_message: str = f"{context}, 参数[case_tags]不允许为空"
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)
    return case_tags


def _readd_explicit_null_fields(payload: Any, update_dict: Dict[str, Any], field_names: Tuple[str, ...]) -> None:
    """
    回补显式置空字段到更新载荷，避免exclude_none丢弃None导致旧值残留。

    :param payload: 更新入参schema实例
    :param update_dict: model_dump产出的更新字典(就地修改)
    :param field_names: 需要回补语义的字段名集合
    :return: None
    """
    for field_name in field_names:
        if field_name in payload.model_fields_set and getattr(payload, field_name, None) is None:
            update_dict[field_name] = None


def _duplicate_case_message(case_project: Any, case_name: Any, case_type: Any, owner_user: Any) -> str:
    """构造业务唯一冲突文案。"""
    return (
        f"相同应用下同类型同所属人用例名称不允许重复, "
        f"查询条件: [case_project={case_project}, case_name={case_name}, "
        f"case_type={case_type}, owner_user={owner_user}]"
    )


class AutoTestCaseCrud(ScaffoldCrud[AutoTestCaseModel, AutoTestApiCaseCreate, AutoTestApiCaseUpdate]):

    def __init__(self):
        super().__init__(model=AutoTestCaseModel)

    async def get_by_id(self, case_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestCaseModel]:
        """
        根据主键ID查询用例。

        :param case_id: 用例主键ID
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 用例实例或None
        """
        if not case_id:
            error_message: str = "查询用例信息失败, 参数[case_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.get_or_none(id=case_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询用例信息失败, 记录[id={case_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, case_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestCaseModel]:
        """
        根据用例标识代码查询用例。

        :param case_code: 用例标识代码
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 用例实例或None
        """
        if not case_code:
            error_message: str = "查询用例信息失败, 参数[case_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(case_code=case_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询用例信息失败, 记录[code={case_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    @staticmethod
    async def get_case_ids_by_request_step(
            step_type: Optional[AutoTestStepType] = None,
            request_args_type: Optional[AutoTestReqArgsType] = None,
    ) -> Optional[List[int]]:
        """
        根据请求步骤类型与参数类型查询关联用例ID列表。

        :param step_type: 请求步骤类型；可选
        :param request_args_type: 请求参数类型；可选
        :return: 关联用例ID列表；两者皆空时返回None
        """
        if step_type is None and request_args_type is None:
            return None

        step_q = Q(
            state__not=1,
            step_type__in=[AutoTestStepType.TCP.value, AutoTestStepType.HTTP.value],
        ) & ~Q(case_id__isnull=True)
        if step_type is not None:
            step_q &= Q(step_type=step_type.value)
        if request_args_type is not None:
            step_q &= Q(request_args_type=request_args_type.value)

        case_ids: List[int] = await AutoTestStepModel.filter(step_q).distinct().values_list("case_id", flat=True)
        return case_ids

    async def _get_by_owner_key(
            self,
            case_project: int,
            case_name: str,
            case_type: Optional[AutoTestCaseType],
            owner_user: Optional[str],
            exclude_id: Optional[int] = None,
    ) -> Optional[AutoTestCaseModel]:
        """
        按业务唯一键查找用例，含软删，不滤state。

        :param case_project: 所属应用
        :param case_name: 用例名称
        :param case_type: 用例类型
        :param owner_user: 所属人员
        :param exclude_id: 更新时排除自身
        :return: 命中的用例或None
        """
        if not owner_user:
            error_message: str = "按业务唯一键查找用例失败, 所属人员不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        query = self.model.filter(
            case_project=case_project,
            case_name=case_name,
            case_type=case_type,
            owner_user=owner_user,
        )
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.first()

    async def _restore_and_overwrite_case(
            self,
            existing: AutoTestCaseModel,
            overwrite: Dict[str, Any],
    ) -> AutoTestCaseModel:
        """
        唤醒软删用例并按本次创建数据覆盖表头，不改created_user、owner_user、case_code。

        :param existing: 软删用例
        :param overwrite: 覆盖字段
        :return: 恢复后的用例
        """
        overwrite.pop("created_user", None)
        overwrite.pop("case_code", None)
        overwrite.pop("case_id", None)
        overwrite["state"] = 0
        overwrite["case_version"] = (existing.case_version or 1) + 1
        return await self.update(id=existing.id, obj_in=overwrite)

    async def create_case(self, case_in: AutoTestApiCaseCreate) -> AutoTestCaseModel:
        """
        创建用例。同应用同类型同所属人同名：启用则拒绝，软删则恢复并覆盖表头。

        :param case_in: 用例创建schema
        :return: 创建或恢复后的用例实例
        """
        case_name: str = case_in.case_name
        case_project: int = case_in.case_project
        case_type: Optional[AutoTestCaseType] = case_in.case_type
        case_tags = _normalize_case_tags(case_type, case_in.case_tags, context="新增用例信息失败")
        owner_user = get_current_username()
        if not owner_user and case_in.created_user:
            owner_user = str(case_in.created_user).strip().upper()[:16]
        if not owner_user:
            error_message: str = "新增用例信息失败, 所属人员不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        if case_tags:
            await AutoTestTagCrud().get_by_ids(tag_ids=case_tags, on_error=True, state__not=1)

        existing_case = await self._get_by_owner_key(
            case_project=case_project,
            case_name=case_name,
            case_type=case_type,
            owner_user=owner_user,
        )
        if existing_case and existing_case.state != 1:
            error_message: str = _duplicate_case_message(case_project, case_name, case_type, owner_user)
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)
        try:
            case_dict = case_in.model_dump(exclude_none=True, exclude_unset=True)
            case_dict.pop("created_user", None)
            case_dict["case_tags"] = case_tags
            if existing_case:
                instance = await self._restore_and_overwrite_case(existing_case, case_dict)
                LOGGER.info(
                    f"新增用例命中软删记录, 已恢复覆盖: id={instance.id}, "
                    f"case_project={case_project}, case_name={case_name}, owner_user={owner_user}"
                )
                return instance
            case_dict["case_version"] = 1
            case_dict["owner_user"] = owner_user
            instance = await self.create(case_dict)
            return instance
        except IntegrityError as e:
            error_message: str = f"新增用例信息失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    @staticmethod
    async def _cascade_public_api_step_project(case_instance: AutoTestCaseModel) -> None:
        """
        将公共接口请求步骤所属应用级联对齐为用例所属应用。

        :param case_instance: 更新后的用例实例(非公共接口或无应用时静默跳过)
        """
        if case_instance.case_type != AutoTestCaseType.PUBLIC_API or not case_instance.case_project:
            return
        updated_count: int = await AutoTestStepModel.filter(
            case_id=case_instance.id, state__not=1
        ).exclude(request_project_id=case_instance.case_project).update(
            request_project_id=case_instance.case_project
        )
        if updated_count:
            LOGGER.info(
                f"公共接口用例[id={case_instance.id}]级联对齐请求步骤所属应用为[{case_instance.case_project}]记录, 更新{updated_count}条"
            )

    async def update_case(self, case_in: AutoTestApiCaseUpdate) -> AutoTestCaseModel:
        """
        更新用例，根据case_id或case_code定位并递增case_version。

        :param case_in: 用例更新schema，需含case_id或case_code
        :return: 更新后的用例实例
        """
        case_id: Optional[int] = case_in.case_id
        case_code: Optional[str] = case_in.case_code
        case_type: Optional[AutoTestCaseType] = case_in.case_type

        if not case_id and not case_code:
            error_message: str = "更新用例信息失败, 参数[case_id]或[case_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if case_id:
            instance = await self.get_by_id(case_id=case_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(case_code=case_code, on_error=True, state__not=1)
            case_id = instance.id
        original_case_type: Optional[AutoTestCaseType] = instance.case_type
        update_dict = case_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"case_id", "case_code"}
        )
        _readd_explicit_null_fields(case_in, update_dict, CASE_CLEARABLE_JSON_FIELDS)

        effective_type = update_dict.get("case_type", instance.case_type)
        if effective_type in PUBLIC_CASE_TYPES:
            if update_dict.get("case_tags"):
                error_message = "更新用例信息失败, 用例类型为[公共脚本/公共接口]时不支持打标签"
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)
            update_dict["case_tags"] = None
        elif "case_tags" in update_dict or ("case_type" in update_dict and original_case_type in PUBLIC_CASE_TYPES):
            raw_tags = update_dict.get("case_tags", instance.case_tags)
            normalized_tags = _normalize_case_tags(effective_type, raw_tags, context="更新用例信息失败")
            update_dict["case_tags"] = normalized_tags
            await AutoTestTagCrud().get_by_ids(tag_ids=normalized_tags, on_error=True, state__not=1)

        if "case_name" in update_dict or "case_project" in update_dict or "case_type" in update_dict:
            case_name = update_dict.get("case_name", instance.case_name)
            case_project = update_dict.get("case_project", instance.case_project)
            unique_case_type = update_dict.get("case_type", instance.case_type)
            existing_case = await self._get_by_owner_key(
                case_project=case_project,
                case_name=case_name,
                case_type=unique_case_type,
                owner_user=instance.owner_user,
                exclude_id=case_id,
            )
            if existing_case:
                error_message: str = _duplicate_case_message(
                    case_project, case_name, unique_case_type, instance.owner_user
                )
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)

        if case_type == AutoTestCaseType.PUBLIC_API and original_case_type != AutoTestCaseType.PUBLIC_API:
            await self._validate_switch_to_public_api(instance)

        try:
            update_dict["case_version"] = instance.case_version + 1
            instance = await self.update(id=case_id, obj_in=update_dict)
            if "case_project" in update_dict or (
                    case_type == AutoTestCaseType.PUBLIC_API and original_case_type != AutoTestCaseType.PUBLIC_API
            ):
                await self._cascade_public_api_step_project(instance)
            return instance
        except DoesNotExist as e:
            error_message: str = f"更新用例信息失败, 记录[id={case_id}]或[code={case_code}]不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = f"更新用例信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_case(self, case_id: Optional[int] = None, case_code: Optional[str] = None) -> AutoTestCaseModel:
        """
        软删除用例，并软删除该用例下所有步骤；公共脚本需无引用。

        :param case_id: 用例主键ID，与case_code二选一
        :param case_code: 用例标识代码，与case_id二选一
        :return: 软删除后的用例实例
        """
        if not case_id and not case_code:
            error_message: str = "删除用例信息失败, 参数[case_id]或[case_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if case_id:
            instance = await self.get_by_id(case_id=case_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(case_code=case_code, on_error=True, state__not=1)
            case_id = instance.id

        case_type: AutoTestCaseType = instance.case_type
        if case_type in PUBLIC_CASE_TYPES:
            quote_steps_count = await AutoTestStepModel.filter(quote_case_id=case_id, state__not=1).count()
            if quote_steps_count > 0:
                error_message: str = f"删除用例信息失败, 记录[id={case_id}]存在{quote_steps_count}个引用, 无法直接删除"
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)

        from backend.applications.aotutest.services.autotest_step_crud import AutoTestStepCrud
        step_crud = AutoTestStepCrud()
        step_ids = await step_crud.model.filter(case_id=case_id, state__not=1).values_list("id", flat=True)
        await step_crud.soft_delete_batch(ids=list(step_ids))
        return await self.soft_delete(id=instance.id)

    async def select_cases(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestCaseModel]]:
        """
        根据条件分页查询用例。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询用例信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    @staticmethod
    async def _validate_switch_to_public_api(case_instance: AutoTestCaseModel) -> None:
        """
        校验切换为公共接口前存量步骤树形态是否合规。

        :param case_instance: 待切换的用例实例
        """
        root_steps: List[AutoTestStepModel] = await AutoTestStepModel.filter(
            case_id=case_instance.id, parent_step_id=None, state__not=1
        )
        if len(root_steps) != 1:
            error_message: str = (
                f"用例({case_instance.case_name})不允许切换为公共接口, "
                f"公共接口有且仅需1个请求步骤, 当前根步骤数为({len(root_steps)})"
            )
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        only_step: AutoTestStepModel = root_steps[0]
        if only_step.step_type not in (AutoTestStepType.HTTP, AutoTestStepType.TCP):
            error_message: str = (
                f"用例({case_instance.case_name})不允许切换为公共接口, "
                f"公共接口仅支持HTTP/TCP请求步骤, 当前步骤类型为({only_step.step_type})"
            )
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

    async def batch_update_or_create_cases(self, cases_data: List[AutoTestApiCaseUpdate]) -> Dict[str, Any]:
        """
        批量新增或更新用例：无case_id/case_code则新增，有则更新。

        :param cases_data: 用例更新schema列表
        :return: 含created_count、updated_count、success_detail的字典
        """
        created_count: int = 0
        updated_count: int = 0
        processed_case: Set[Tuple[Optional[int], Optional[str]]] = set()  # 用于去重（仅针对已有id的用例）
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

            if not case_id and not case_code:
                case_instance = None
            else:
                case_instance: Optional[AutoTestCaseModel] = await self.get_by_conditions(
                    only_one=True,
                    on_error=False,
                    id=case_id,
                    case_code=case_code,
                    state__not=1
                )

            if not case_instance:
                case_tags = _normalize_case_tags(case_type, case_tags, context=f"第{cid}条用例新增失败")
                if case_tags:
                    await AutoTestTagCrud().get_by_ids(tag_ids=case_tags, on_error=True, state__not=1)
                if not case_name:
                    error_message: str = f"第{cid}条用例新增失败, 参数[case_name]不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)
                if not case_project:
                    error_message: str = f"第{cid}条用例新增失败, 参数[case_project]不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)
                owner_user = get_current_username()
                if not owner_user:
                    error_message: str = f"第{cid}条用例新增失败, 所属人员不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)

                existing_case_instance: Optional[AutoTestCaseModel] = await self._get_by_owner_key(
                    case_project=case_project,
                    case_name=case_name,
                    case_type=case_type,
                    owner_user=owner_user,
                )
                create_case_dict: Dict[str, Any] = case_data.model_dump(
                    exclude_none=True,
                    exclude_unset=True,
                    exclude={"case_id", "case_code", "case_version"}
                )
                create_case_dict["case_tags"] = case_tags
                if existing_case_instance and existing_case_instance.state != 1:
                    error_message: str = (
                        f"第{cid}条用例新增失败, "
                        f"{_duplicate_case_message(case_project, case_name, case_type, owner_user)}"
                    )
                    LOGGER.error(error_message)
                    raise DataAlreadyExistsException(message=error_message)
                try:
                    if existing_case_instance:
                        new_case_instance = await self._restore_and_overwrite_case(
                            existing_case_instance, create_case_dict
                        )
                        LOGGER.info(
                            f"第{cid}条用例新增命中软删记录, 已恢复覆盖: id={new_case_instance.id}"
                        )
                    else:
                        create_case_dict["owner_user"] = owner_user
                        new_case_instance: AutoTestCaseModel = await self.create(obj_in=create_case_dict)
                except Exception as e:
                    error_message: str = f"第{cid}条用例新增失败, 错误描述: {e}"
                    LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                    raise DataBaseStorageException(message=error_message) from e

                processed_case.add((new_case_instance.id, new_case_instance.case_code))
                case_dict: Dict[str, Any] = await new_case_instance.to_dict(
                    include_fields=["case_code", "case_name", "case_project"]
                )
                if existing_case_instance:
                    updated_count += 1
                    case_dict["created"] = False
                else:
                    created_count += 1
                    case_dict["created"] = True
                case_dict["case_id"] = new_case_instance.id
                success_detail.append(case_dict)

            else:
                if case_type == AutoTestCaseType.PUBLIC_API and case_instance.case_type != AutoTestCaseType.PUBLIC_API:
                    await self._validate_switch_to_public_api(case_instance)

                update_case_dict: Dict[str, Any] = case_data.model_dump(
                    exclude_none=True,
                    exclude_unset=True,
                    exclude={"case_id", "case_code"}
                )
                _readd_explicit_null_fields(case_data, update_case_dict, CASE_CLEARABLE_JSON_FIELDS)
                if not update_case_dict:
                    processed_case.add((case_id, case_code))
                    case_dict: Dict[str, Any] = await case_instance.to_dict(
                        include_fields=["case_code", "case_name", "case_project"]
                    )
                    case_dict["created"] = False
                    case_dict["case_id"] = case_id
                    success_detail.append(case_dict)
                    continue

                effective_type = update_case_dict.get("case_type", case_instance.case_type)
                if effective_type in PUBLIC_CASE_TYPES:
                    if update_case_dict.get("case_tags"):
                        error_message = f"第{cid}条用例更新失败, 公共脚本/公共接口不支持打标签"
                        LOGGER.error(error_message)
                        raise ParameterException(message=error_message)
                    update_case_dict["case_tags"] = None
                elif "case_tags" in update_case_dict or (
                        "case_type" in update_case_dict and case_instance.case_type in PUBLIC_CASE_TYPES
                ):
                    raw_tags = update_case_dict.get("case_tags", case_instance.case_tags)
                    normalized_tags = _normalize_case_tags(
                        effective_type, raw_tags, context=f"第{cid}条用例更新失败"
                    )
                    update_case_dict["case_tags"] = normalized_tags
                    await AutoTestTagCrud().get_by_ids(tag_ids=normalized_tags, on_error=True, state__not=1)

                if "case_name" in update_case_dict or "case_project" in update_case_dict or "case_type" in update_case_dict:
                    unique_name = update_case_dict.get("case_name", case_instance.case_name)
                    unique_project = update_case_dict.get("case_project", case_instance.case_project)
                    unique_type = update_case_dict.get("case_type", case_instance.case_type)
                    existing_case_instance: Optional[AutoTestCaseModel] = await self._get_by_owner_key(
                        case_project=unique_project,
                        case_name=unique_name,
                        case_type=unique_type,
                        owner_user=case_instance.owner_user,
                        exclude_id=case_id,
                    )
                    if existing_case_instance:
                        error_message: str = (
                            f"第{cid}条用例更新失败, "
                            f"{_duplicate_case_message(unique_project, unique_name, unique_type, case_instance.owner_user)}"
                        )
                        LOGGER.error(error_message)
                        raise DataAlreadyExistsException(message=error_message)

                try:
                    update_case_dict["case_version"] = case_instance.case_version + 1
                    updated_instance: AutoTestCaseModel = await self.update(id=case_id, obj_in=update_case_dict)
                except Exception as e:
                    error_message: str = f"第{cid}条用例更新失败, 错误描述: {e}"
                    LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                    raise DataBaseStorageException(message=error_message) from e

                if "case_project" in update_case_dict or (
                        case_type == AutoTestCaseType.PUBLIC_API
                        and case_instance.case_type != AutoTestCaseType.PUBLIC_API
                ):
                    await self._cascade_public_api_step_project(updated_instance)

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
