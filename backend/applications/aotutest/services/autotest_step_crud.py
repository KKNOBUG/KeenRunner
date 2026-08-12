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
from typing import Optional, List, Dict, Any, Set, Tuple

from tortoise.exceptions import DoesNotExist, IntegrityError, FieldError
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from backend.applications.aotutest.models.autotest_model import (
    AutoTestApiStepInfo,
    AutoTestApiCaseInfo,
)
from backend.applications.aotutest.schemas.autotest_case_schema import AutoTestApiCaseUpdate
from backend.applications.aotutest.schemas.autotest_step_schema import (
    AutoTestApiStepCreate,
    AutoTestApiStepUpdate,
    AutoTestCaseStepTreeLoadResult,
    AutoTestStepTreeUpdateItem,
    StepTreeCounter,
    StepVariablesBase,
    StepsExecuteConfigBase,
    step_tree_item_from_storage,
    step_variables_list_from_storage,
)
from backend.applications.aotutest.services.autotest_case_crud import AutoTestApiCaseCrud, _readd_explicit_null_fields
from backend.applications.aotutest.services.autotest_detail_crud import AutoTestApiDetailCrud
from backend.applications.aotutest.services.autotest_report_crud import AutoTestApiReportCrud
from backend.applications.aotutest.services.autotest_step_engine import AutoTestStepExecutionEngine
from backend.applications.aotutest.services.autotest_tool_service import AutoTestToolService
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)
from backend.enums import AutoTestCaseType, AutoTestStepType, AutoTestReportType, PUBLIC_CASE_TYPES

STEP_CLEARABLE_JSON_FIELDS: Tuple[str, ...] = (
    "request_header", "request_params", "request_form_data", "request_form_urlencoded", "request_form_file", "request_body",
    "session_variables", "defined_variables", "extract_variables", "assert_validators", "database_operates", "redis_operates",
    "loop_conditions",
)


class AutoTestApiStepCrud(ScaffoldCrud[AutoTestApiStepInfo, AutoTestApiStepCreate, AutoTestApiStepUpdate]):

    def __init__(self):
        """
        初始化CRUD，绑定模型AutoTestApiStepInfo。
        """
        super().__init__(model=AutoTestApiStepInfo)

    async def get_by_id(self, step_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestApiStepInfo]:
        """
        根据主键ID查询步骤。

        :param step_id: 步骤主键ID
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 步骤实例或None
        """
        if not step_id:
            error_message: str = "查询步骤信息失败, 参数[step_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.model.filter(id=step_id, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询步骤信息失败, 记录[id={step_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, step_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestApiStepInfo]:
        """
        根据步骤标识代码查询步骤。

        :param step_code: 步骤标识代码
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 步骤实例或None
        """
        if not step_code:
            error_message: str = "查询步骤信息失败, 参数[step_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(step_code=step_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询步骤信息失败, 记录[code={step_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_case_id(self, case_id: Optional[int] = None, case_code: Optional[str] = None) -> AutoTestCaseStepTreeLoadResult:
        """
        根据用例ID或case_code获取该用例的步骤树(含引用脚本步骤及统计)。

        :param case_id: 用例主键ID，与case_code二选一
        :param case_code: 用例标识代码，与case_id二选一
        :return: AutoTestCaseStepTreeLoadResult(根步骤为AutoTestStepTreeUpdateItem)
        """
        case_crud = AutoTestApiCaseCrud()
        if case_id:
            case_instance = await case_crud.get_by_id(case_id=case_id, on_error=True, state__not=1)
        else:
            case_instance = await case_crud.get_by_code(case_code=case_code, on_error=True, state__not=1)
            case_id: int = case_instance.id

        # 获取所有根步骤（没有父步骤的步骤）
        root_steps: List[AutoTestApiStepInfo] = await self.model.filter(
            case_id=case_id,
            parent_step_id__isnull=True,
            state__not=1
        ).order_by("step_no").all()
        root_index = [step.step_no for step in root_steps]
        LOGGER.info(f"获取用例[case_id={case_id}]根步骤成功, 共计: {len(root_steps)}个, 根步骤序号: {root_index}")

        # 步骤计数器：用于统计该用例拥有的步骤总数
        # direct_steps: 直接属于该用例的步骤数（根步骤, parent_step_id为None）
        # child_steps: 所有子步骤数（递归统计, 不包括根步骤, parent_step_id不为None）
        # quote_steps: 引用脚本的步骤数
        # total_step: 总步骤数（direct_steps + child_steps + quote_steps）
        step_counter = {
            "direct_steps": 0,
            "child_steps": 0,
            "quote_steps": 0,
            "total_steps": 0
        }

        # 递归构建步骤树
        async def build_step_tree(step: AutoTestApiStepInfo, is_quote: bool = False) -> Dict[str, Any]:
            """递归构建单步及其子步骤、引用脚本步骤的树形字典。"""
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
            LOGGER.info(f"获取步骤[step_id={step.id}, step_no={step.step_no}]基本信息完成")
            # 获取用例信息（业务层手动查询）
            if step.case_id:
                case = await case_crud.get_by_id(case_id=step.case_id, on_error=True, state__not=1)
                step_dict["case"] = await case.to_dict(
                    exclude_fields={
                        "state",
                        "created_user", "updated_user",
                        "created_time", "updated_time",
                        "reserve_1", "reserve_2", "reserve_3"
                    },
                    replace_fields={"id": "case_id"}
                )
                LOGGER.info(f"获取步骤[step_id={step.id}, step_no={step.step_no}]所属用例信息完成")

            # 获取子步骤（递归构建）
            children: List[AutoTestApiStepInfo] = await self.model.filter(
                parent_step_id=step.id,
                state__not=1
            ).order_by("branch_index", "step_no").all()
            if step.step_type == AutoTestStepType.IF and step.branch_items:
                from collections import defaultdict
                grouped = defaultdict(list)
                for child in children:
                    grouped[child.branch_index if child.branch_index is not None else 0].append(child)
                branches_with_children = []
                for i, branch_meta in enumerate(step.branch_items):
                    branch_dict = dict(branch_meta) if isinstance(branch_meta, dict) else branch_meta
                    branch_children = grouped.get(i, [])
                    branch_dict["branch_children"] = [await build_step_tree(c, is_quote=is_quote) for c in branch_children]
                    branches_with_children.append(branch_dict)
                step_dict["branch_items"] = branches_with_children
                step_dict["children"] = []
            elif children:
                LOGGER.info(f"==*== 获取步骤[step_id={step.id}, step_no={step.step_no}]所有子步骤(递归构建)开始 ==*==")
                step_dict["children"] = [await build_step_tree(child, is_quote=is_quote) for child in children]
                LOGGER.info(f"==*== 获取步骤[step_id={step.id}, step_no={step.step_no}]所有子步骤(递归构建)完成 ==*==")
            else:
                step_dict["children"] = []

            if not step.quote_case_id:
                step_dict["quote_steps"] = []
                step_dict["quote_case"] = None
                return step_dict

            quote_case = await case_crud.get_by_id(case_id=step.quote_case_id, on_error=False, state__not=1)
            if not quote_case:
                step_dict["quote_steps"] = []
                step_dict["quote_case"] = None
                return step_dict

            # 获取引用的公共脚本的所有步骤(包含子步骤, 递归构建)
            quote_case_root_steps: List[AutoTestApiStepInfo] = await self.model.filter(
                case_id=step.quote_case_id,
                parent_step_id__isnull=True,
                state__not=1
            ).order_by("step_no").all()
            LOGGER.info(f"==*== 获取步骤[step_id={step.id}, step_no={step.step_no}]引用脚本的所有步骤(包含子步骤, 递归构建)开始 ==*==")
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
            LOGGER.info(f"==*== 获取步骤[step_id={step.id}, step_no={step.step_no}]引用脚本的所有步骤(包含子步骤, 递归构建)完成 ==*==")
            return step_dict

        # 构建所有根步骤的树
        result = []
        for root_id, root_step in enumerate(root_steps, start=1):
            LOGGER.info(f"==> 构建第{root_id}个根步骤树结构: ")
            result.append(await build_step_tree(root_step))

        # 没有测试步骤明细时将测试用例本身添加到返回结果（历史：单节点仅含case）
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
        meta = StepTreeCounter(**step_counter)
        raw_roots = result
        case_only: Optional[AutoTestApiCaseUpdate] = None
        if len(raw_roots) == 1 and isinstance(raw_roots[0], dict) and list(raw_roots[0].keys()) == ["case"]:
            case_only = AutoTestApiCaseUpdate.model_validate(raw_roots[0]["case"])
            root_models: List[AutoTestStepTreeUpdateItem] = []
        else:
            root_models = [step_tree_item_from_storage(r) for r in raw_roots]
        return AutoTestCaseStepTreeLoadResult(
            root_steps=root_models,
            step_counter=meta,
            case_only_when_no_steps=case_only,
        )

    async def get_request_step_project_ids(self, case_id: Optional[int] = None, case_code: Optional[str] = None) -> List[int]:
        """
        从步骤树提取请求相关步骤所选应用ID并去重。

        :param case_id: 用例主键ID，与case_code二选一
        :param case_code: 用例标识代码，与case_id二选一
        :return: 去重后的project_id列表(升序)
        """
        load = await self.get_by_case_id(case_id=case_id, case_code=case_code)
        project_ids: Set[int] = set()

        def _norm_step_type(st: Any) -> Optional[AutoTestStepType]:
            """将原始step_type规范为枚举；非法则返回None。"""
            if st is None:
                return None
            if isinstance(st, AutoTestStepType):
                return st
            try:
                return AutoTestStepType(st)
            except (ValueError, TypeError):
                return None

        def recursive_require_project_ids(step: AutoTestStepTreeUpdateItem) -> None:
            """
            递归收集HTTP/TCP/DB/Redis步骤上的project_id到外层集合。
            """
            st_e = _norm_step_type(step.step_type)
            if st_e in (AutoTestStepType.HTTP, AutoTestStepType.TCP):
                request_project_id = step.request_project_id
                if request_project_id:
                    try:
                        project_ids.add(int(request_project_id))
                    except Exception:
                        pass
            elif st_e == AutoTestStepType.DATABASE:
                for db_operate in step.database_operates or []:
                    project_id = db_operate.project_id
                    if project_id:
                        try:
                            project_ids.add(int(project_id))
                        except Exception:
                            pass
            elif st_e == AutoTestStepType.REDIS:
                for redis_operate in step.redis_operates or []:
                    project_id = redis_operate.project_id
                    if project_id:
                        try:
                            project_ids.add(int(project_id))
                        except Exception:
                            pass
            for child in step.children or []:
                recursive_require_project_ids(child)
            for quote_step in step.quote_steps or []:
                recursive_require_project_ids(quote_step)

        for node in load.root_steps:
            recursive_require_project_ids(node)

        return sorted(project_ids)

    async def get_copy_tree(self, case_id: Optional[int] = None, case_code: Optional[str] = None) -> Dict[str, Any]:
        """
        获取用例步骤树完整副本，用于复制后编辑且尚未落库。

        :param case_id: 用例主键ID，与case_code二选一
        :param case_code: 用例标识代码，与case_id二选一
        :return: {"case": {...}, "steps": [...]}，case中case_id/case_code置空
        """
        load = await self.get_by_case_id(case_id=case_id, case_code=case_code)

        def strip_step_for_copy_model(step: AutoTestStepTreeUpdateItem) -> AutoTestStepTreeUpdateItem:
            """
            在模型上递归移除step_id、step_code、parent_step_id、step_no；case内case_id/case_code置空。
            """
            case_block = step.case
            if isinstance(case_block, dict):
                case_block = {**case_block, "case_id": None, "case_code": None}
            children = [strip_step_for_copy_model(c) for c in (step.children or [])]
            quotes = [strip_step_for_copy_model(q) for q in (step.quote_steps or [])]
            return step.model_copy(
                update={
                    "step_id": None,
                    "step_no": None,
                    "step_code": None,
                    "parent_step_id": None,
                    "case": case_block,
                    "children": children or None,
                    "quote_steps": quotes or None,
                }
            )

        if load.case_only_when_no_steps is not None:
            c = load.case_only_when_no_steps.model_copy(update={"case_id": None, "case_code": None})
            return {"case": c.model_dump(mode="json"), "steps": []}

        steps: List[Dict[str, Any]] = []
        case_info: Optional[Dict[str, Any]] = None
        for root in load.root_steps:
            stripped = strip_step_for_copy_model(root)
            steps.append(stripped.model_dump(mode="json"))
            if case_info is None and stripped.case is not None and isinstance(stripped.case, dict):
                case_info = {**stripped.case, "case_id": None, "case_code": None}

        return {"case": case_info or {}, "steps": steps}

    async def create_step(self, step_in: AutoTestApiStepCreate) -> AutoTestApiStepInfo:
        """
        创建单条步骤，校验用例存在、父步骤存在且同用例，若同用例下step_no已存在则恢复并更新。

        :param step_in: 步骤创建schema
        :return: 创建后的步骤实例
        """
        case_id: int = step_in.case_id
        step_no: int = step_in.step_no
        case_crud = AutoTestApiCaseCrud()
        await case_crud.get_by_id(case_id=case_id, on_error=True, state__not=1)

        if step_in.parent_step_id:
            parent_step_id: int = step_in.parent_step_id
            parent_step = await self.get_by_id(step_id=parent_step_id, on_error=True, state__not=1)

            if parent_step.case_id != step_in.case_id:
                error_message: str = (
                    f"根据(step_id={parent_step_id})条件检查步骤信息失败, "
                    f"父级步骤(case_id={parent_step.case_id})和当前步骤(case_id={case_id})不一致"
                )
                LOGGER.error(error_message)
                raise NotFoundException(message=error_message)

        if step_in.quote_case_id:
            quote_case_id: int = step_in.quote_case_id
            quote_case = await case_crud.get_by_id(case_id=quote_case_id, on_error=False, state__not=1)
            if not quote_case:
                error_message: str = (
                    f"根据(case_id={quote_case_id})条件检查用例信息失败, "
                    f"步骤序号(step_no={step_no})引用公共脚本(case_id={quote_case_id})不存在"
                )
                LOGGER.error(error_message)
                raise NotFoundException(message=error_message)

        step_dict = step_in.model_dump(exclude_none=True, exclude_unset=True)
        existing_step = await self.model.filter(case_id=case_id, step_no=step_no).first()
        if not existing_step:
            try:
                instance: AutoTestApiStepInfo = await self.create(step_dict)
                return instance
            except IntegrityError as e:
                error_message: str = f"新增步骤信息失败, 违反约束规则: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise DataBaseStorageException(message=error_message) from e

        try:
            step_dict["state"] = 0
            instance: AutoTestApiStepInfo = await self.update(id=existing_step.id, obj_in=step_dict)
            return instance
        except (DoesNotExist, IntegrityError) as e:
            error_message: str = f"新增(更新)步骤信息异常, 违反约束规则或空指针异常: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_step(self, step_in: AutoTestApiStepUpdate) -> AutoTestApiStepInfo:
        """
        更新单条步骤，支持根据step_id或step_code定位；校验step_no唯一、父步骤存在且无循环引用。

        :param step_in: 步骤更新schema
        :return: 更新后的步骤实例
        """
        step_id: Optional[int] = step_in.step_id
        step_code: Optional[str] = step_in.step_code

        if step_id:
            instance = await self.get_by_id(step_id=step_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(step_code=step_code, on_error=True, state__not=1)
            step_id: int = instance.id

        update_dict: Dict[str, Any] = step_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"step_id", "step_code"}
        )
        _readd_explicit_null_fields(step_in, update_dict, STEP_CLEARABLE_JSON_FIELDS)
        if not update_dict:
            return instance

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

        if "case_id" in update_dict:
            case_id: int = update_dict.get("case_id", instance.case_id)
            await AutoTestApiCaseCrud().get_by_id(case_id=case_id, on_error=True, state__not=1)

        if "parent_step_id" in update_dict:
            parent_step_id: Optional[int] = update_dict["parent_step_id"]
            if parent_step_id:
                parent_step: AutoTestApiStepInfo = await self.model.filter(
                    id=parent_step_id,
                    state__not=1,
                    step_type__in=[AutoTestStepType.IF.value, AutoTestStepType.LOOP.value]
                ).first()
                if not parent_step:
                    error_message: str = (
                        f"根据(id={parent_step_id}, step_type__in=[条件分支, 循环结构])条件检查父级步骤信息失败, "
                        f"记录[id={parent_step_id}]不存在"
                    )
                    LOGGER.error(error_message)
                    raise NotFoundException(message=error_message)

                case_id: int = update_dict.get("case_id", instance.case_id)
                if parent_step.case_id != case_id:
                    error_message: str = f"父级步骤(case_id={parent_step.case_id})和当前步骤(case_id={case_id})不一致"
                    LOGGER.error(error_message)
                    raise NotFoundException(message=error_message)

                if parent_step.id == step_id:
                    error_message: str = f"父级步骤(id={parent_step.id})和当前步骤(id={step_id})冲突, 不能将自身设置为父级步骤"
                    LOGGER.error(error_message)
                    raise DataBaseStorageException(message=error_message)

                visited: Set[int] = set()
                current_parent_id = parent_step.parent_step_id
                while current_parent_id:
                    if current_parent_id == step_id:
                        error_message: str = f"父级步骤(id={parent_step.id})和当前步骤(id={step_id})冲突, 不能将自身设置为父级步骤"
                        LOGGER.error(error_message)
                        raise DataBaseStorageException(message=error_message)
                    if current_parent_id in visited:
                        break
                    visited.add(current_parent_id)
                    parent = await self.get_by_id(step_id=current_parent_id, on_error=False, state__not=1)
                    if not parent:
                        break
                    current_parent_id = parent.parent_step_id

        if "quote_case_id" in update_dict and update_dict["quote_case_id"]:
            quote_case_id: int = update_dict["quote_case_id"]
            quote_case = await AutoTestApiCaseCrud().get_by_conditions(
                only_one=True,
                on_error=False,
                id=quote_case_id,
                case_type__in=[t.value for t in PUBLIC_CASE_TYPES],
                state__not=1,
            )
            if not quote_case:
                error_message: str = f"根据(id={quote_case_id}, case_type=公共脚本/公共接口)条件检查用例信息失败, 引用公共用例信息不存在"
                LOGGER.error(error_message)
                raise NotFoundException(message=error_message)

        try:
            instance = await self.update(id=step_id, obj_in=update_dict)
            return instance
        except DoesNotExist as e:
            error_message: str = f"更新步骤信息失败, 记录[id={step_id}]或[code={step_code}]不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = f"更新步骤信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_step(self, step_id: Optional[int] = None, step_code: Optional[str] = None) -> AutoTestApiStepInfo:
        """
        软删除单条步骤，需无子步骤。

        :param step_id: 步骤主键ID，与step_code二选一
        :param step_code: 步骤标识代码，与step_id二选一
        :return: 软删除后的步骤实例
        """
        if step_id:
            instance = await self.get_by_id(step_id=step_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(step_code=step_code, on_error=True, state__not=1)
            step_id: int = instance.id

        children_count = await self.model.filter(parent_step_id=step_id, state__not=1).count()
        if children_count > 0:
            error_message: str = (
                f"根据(parent_step_id={step_id})条件检查步骤信息失败, "
                f"记录[id={step_id}]存在{children_count}个子级步骤, 无法直接删除"
            )
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        instance = await self.soft_delete(id=instance.id)
        # 同步硬删除该步骤关联的数据源与数据生成记录（延迟导入避免循环依赖）
        from backend.applications.aotutest.services.autotest_data_source_crud import delete_step_create
        await delete_step_create(case_id=instance.case_id, step_code_list=[instance.step_code])
        return instance

    async def delete_steps_recursive(
            self,
            step_id: Optional[int] = None,
            step_code: Optional[str] = None,
            parent_step_id: Optional[int] = None,
            case_id: Optional[int] = None,
            exclude_step: Optional[Set[Tuple[Optional[int], Optional[str]]]] = None
    ) -> int:
        """
        递归软删除步骤：可根据step_id/step_code删单步及其子步骤，或根据parent_step_id/case_id批量删。

        :param step_id: 单步主键ID，与step_code二选一时删除该步及所有子步骤
        :param step_code: 单步标识代码，与step_id二选一
        :param parent_step_id: 指定父步骤ID时，删除该父步骤下所有子步骤
        :param case_id: 指定用例ID时，删除该用例下所有根步骤(及子步骤)
        :param exclude_step: 不删除的 (step_id, step_code) 集合
        :return: 实际软删除的步骤数量
        """
        deleted_count: int = 0
        if exclude_step is None:
            exclude_step = set()
        # 记录本次软删除的步骤，根据用例归类，事务提交后同步清理其数据源
        deleted_by_case: Dict[int, List[str]] = {}

        async def delete_step_and_children(step_instance: AutoTestApiStepInfo) -> int:
            """递归软删除当前步骤及其所有子步骤，返回本次删除数量。"""
            deleted: int = 0
            # 先删除所有子步骤（软删除）
            children = await self.model.filter(parent_step_id=step_instance.id, state__not=1).all()
            for child in children:
                deleted += await delete_step_and_children(step_instance=child)
            # 然后删除当前步骤（软删除）
            if (step_instance.id, step_instance.step_code) not in exclude_step:
                await self.soft_delete(id=step_instance.id)
                deleted += 1
                deleted_by_case.setdefault(step_instance.case_id, []).append(step_instance.step_code)
                LOGGER.warning(
                    f"警告: 删除步骤(step_id={step_instance.id}, "
                    f"step_no={step_instance.step_no}, step_code={step_instance.step_code})成功"
                )
            return deleted

        async with in_transaction():
            # 根据参数类型执行不同的删除逻辑
            if step_id is not None or step_code is not None:
                # 单步骤删除
                conditions: Dict[str, Any] = {"state__not": 1}
                if step_id is not None:
                    conditions["id"] = step_id
                if step_code is not None:
                    conditions["step_code"] = step_code

                step = await self.get_by_conditions(only_one=True, on_error=True, **conditions)
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

        # 步骤软删除提交后，同步清理对应用例下被删步骤的数据源与数据生成记录
        if deleted_by_case:
            from backend.applications.aotutest.services.autotest_data_source_crud import delete_step_create
            for ds_case_id, step_codes in deleted_by_case.items():
                await delete_step_create(case_id=ds_case_id, step_code_list=step_codes)

        return deleted_count

    async def select_steps(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestApiStepInfo]]:
        """
        根据条件分页查询步骤列表。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: 由 (总条数, 当前页记录列表) 组成的元组
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询步骤信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    @classmethod
    def _iter_tree_steps(cls, steps_data):
        """
        深度优先遍历步骤树全部节点(含children与branch_items.branch_children)。
        """
        for step_data in steps_data or []:
            yield step_data
            yield from cls._iter_tree_steps(getattr(step_data, "children", None))
            for branch in getattr(step_data, "branch_items", None) or []:
                yield from cls._iter_tree_steps(getattr(branch, "branch_children", None))

    @classmethod
    def _validate_public_family_tree(
            cls,
            steps_data: List["AutoTestStepTreeUpdateItem"],
            case_type: "AutoTestCaseType",
            case_project: Optional[int] = None,
    ) -> None:
        """
        校验公共家族步骤树约束：全树不允许引用步骤与数据源绑定。

        :param steps_data: 根级步骤树项列表
        :param case_type: 当前用例目标类型(必为公共家族成员)
        :param case_project: 当前用例所属应用ID(公共接口一致性校验使用)
        """
        if case_type == AutoTestCaseType.PUBLIC_API:
            cls._validate_public_api_tree(steps_data)
            # 所属应用自动对齐用例（前端已只读锁定；API 直调无论入参缺失或不一致，在此强制一致）
            if case_project and len(steps_data) == 1:
                only_step = steps_data[0]
                if getattr(only_step, "request_project_id", None) != case_project:
                    LOGGER.info(
                        f"公共接口请求步骤所属应用自动对齐用例所属应用: "
                        f"{getattr(only_step, 'request_project_id', None)} -> {case_project}"
                    )
                    only_step.request_project_id = case_project
        for step_data in cls._iter_tree_steps(steps_data):
            if step_data.step_type == AutoTestStepType.QUOTE:
                error_message: str = f"用例类型为({case_type.value})时不允许引用其他脚本"
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)
            if getattr(step_data, "data_source_id", None):
                error_message: str = f"用例类型为({case_type.value})时不允许绑定数据源"
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)

    @staticmethod
    def _validate_public_api_tree(steps_data: List["AutoTestStepTreeUpdateItem"]) -> None:
        """
        校验公共接口步骤树形态：仅1个HTTP/TCP根步骤且无子级与数据源。

        :param steps_data: 根级步骤树项列表
        """
        if len(steps_data) != 1:
            error_message: str = f"公共接口用例有且仅需 1 个请求步骤，当前提交({len(steps_data)})步"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        only_step = steps_data[0]
        if only_step.step_type not in (AutoTestStepType.HTTP, AutoTestStepType.TCP):
            error_message: str = f"公共接口用例仅支持HTTP/TCP请求步骤，当前步骤类型为({only_step.step_type})"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if getattr(only_step, "children", None) or getattr(only_step, "branch_items", None):
            error_message: str = "公共接口用例的请求步骤不允许携带子级结构"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if getattr(only_step, "data_source_id", None):
            error_message: str = "公共接口用例不允许绑定数据源"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

    async def batch_update_or_create_steps(
            self,
            steps_data: List[AutoTestStepTreeUpdateItem],
            parent_step_id: Optional[int] = None,
            branch_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        批量新增或更新步骤树：无step_id/step_code则新增，有则更新；递归处理children/branch_items。

        :param steps_data: 步骤树项列表，每项可为AutoTestStepTreeUpdateItem
        :param parent_step_id: 当前层级的父步骤ID，用于新增时挂载
        :param branch_index: 当前层级所属分支序号(条件分支子步骤使用)
        :return: 包含created_count、updated_count、process_detail、success_detail的字典
        """
        created_count: int = 0
        updated_count: int = 0
        success_detail: List[Dict[str, Any]] = []
        processed_step_codes: Dict[int, Set[str]] = {}
        allowed_children_types = {AutoTestStepType.LOOP, AutoTestStepType.IF}
        case_crud = AutoTestApiCaseCrud()

        # 公共家族约束（仅根级调用校验）：公共脚本/公共接口均不可引用其他脚本、全树不可绑定数据源；
        # 公共接口另有形态约束（有且仅有 1 个 HTTP/TCP 根步骤）。
        # 与用例保存同事务执行（用例更新在前），此处读到的是目标类型，校验失败抛异常由上层事务回滚。
        if parent_step_id is None and branch_index is None and steps_data:
            root_case_id: Optional[int] = steps_data[0].case_id
            if root_case_id:
                root_case = await case_crud.get_by_id(case_id=root_case_id, on_error=False, state__not=1)
                if root_case and root_case.case_type in PUBLIC_CASE_TYPES:
                    self._validate_public_family_tree(steps_data, root_case.case_type, root_case.case_project)

        for sid, step_data in enumerate(steps_data, start=1):
            case_id: Optional[int] = step_data.case_id
            step_id: Optional[int] = step_data.step_id
            step_no: Optional[int] = step_data.step_no
            step_code: Optional[str] = step_data.step_code
            if step_id:
                step_instance: Optional[AutoTestApiStepInfo] = await self.get_by_id(step_id=step_id, on_error=True, state__not=1)
                step_code = step_instance.step_code
            elif step_code:
                step_instance: Optional[AutoTestApiStepInfo] = await self.get_by_code(
                    step_code=step_code,
                    on_error=True,
                    state__not=1,
                )
                step_id = step_instance.id
            else:
                step_instance = None

            # 步骤不存在，执行新增，及验证必填字段
            if not step_instance:
                if not case_id:
                    error_message: str = f"第{sid}条步骤新增失败, 参数[case_id]不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)
                if not step_no:
                    error_message: str = f"第{sid}条步骤新增失败, 参数[step_no]不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)
                if not step_data.step_type:
                    error_message: str = f"第{sid}条步骤新增失败, 参数[step_type]不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)

                case_instance = await case_crud.get_by_id(case_id=step_data.case_id, on_error=True, state__not=1)

                existing_step_instance: Optional[AutoTestApiStepInfo] = await self.get_by_conditions(
                    only_one=True,
                    on_error=False,
                    state__not=1,
                    case_id=case_id,
                    step_no=step_no,
                    step_code=step_code,
                )
                if existing_step_instance:
                    error_message: str = (
                        f"第{sid}步骤新增失败, "
                        f"根据(case_id={case_id}, step_no={step_no})条件查询步骤信息失败, "
                        f"同一用例下步骤序号不允许重复"
                    )
                    LOGGER.error(error_message)
                    raise DataAlreadyExistsException(message=error_message)

                final_parent_step_id = parent_step_id if parent_step_id is not None else step_data.parent_step_id
                if final_parent_step_id:
                    parent_step = await self.get_by_id(
                        step_id=final_parent_step_id,
                        on_error=False,
                        state__not=1,
                    )
                    if not parent_step:
                        error_message: str = (
                            f"第{sid}步骤新增失败, "
                            f"根据(step_id={final_parent_step_id})条件查询步骤信息失败, "
                            f"父级步骤不存在"
                        )
                        LOGGER.error(error_message)
                        raise NotFoundException(message=error_message)

                    if parent_step.case_id != step_data.case_id:
                        error_message: str = f"父级步骤(case_id={parent_step.case_id})和当前步骤(case_id={case_id})不一致"
                        LOGGER.error(error_message)
                        raise DataAlreadyExistsException(message=error_message)

                    if parent_step.step_type not in allowed_children_types:
                        error_message: str = (
                            f"第{sid}步骤新增失败, "
                            f"父级步骤(id={final_parent_step_id})的类型({parent_step.step_type})不允许包含子步骤"
                            f"(仅允许'循环结构'和'条件分支'类型的步骤包含子步骤)"
                        )
                        LOGGER.error(error_message)
                        raise ParameterException(message=error_message)

                create_step_dict: Dict[str, Any] = step_data.model_dump(
                    exclude_none=True,
                    exclude={"id", "case", "children", "quote_steps", "quote_case", "step_code", "branch_items"},
                )
                create_step_dict["step_is_skipped"] = bool(getattr(step_data, "step_is_skipped", False))
                if final_parent_step_id is not None:
                    create_step_dict["parent_step_id"] = final_parent_step_id
                # branch_index 仅条件分支相关步骤持有(从0开始)：分支子步骤取所属分支序号，
                # 条件分支步骤本身归一化为0；其余步骤不写入(落库为 NULL)
                if branch_index is not None:
                    create_step_dict["branch_index"] = branch_index
                elif step_data.step_type == AutoTestStepType.IF:
                    create_step_dict["branch_index"] = 0

                if step_data.step_type == AutoTestStepType.IF and step_data.branch_items:
                    create_step_dict["branch_items"] = [
                        b.model_dump(exclude={"branch_children"}) for b in step_data.branch_items
                    ]
                    create_step_dict.pop("loop_conditions", None)

                try:
                    new_step_instance: AutoTestApiStepInfo = await self.create(create_step_dict)
                except Exception as e:
                    error_message: str = f"第{sid}条步骤新增失败, 错误描述: {e}"
                    LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                    raise DataBaseStorageException(message=error_message) from e

                # 复制来的步骤携带数据源时，同步复制为新步骤的独立数据源（仅复制解析数据，文件字段置空）
                source_data_source_id = getattr(step_data, "data_source_id", None)
                if source_data_source_id:
                    from backend.applications.aotutest.services.autotest_data_source_crud import AutoTestDataSourceCrud
                    new_data_source_id: Optional[int] = None
                    try:
                        new_data_source_id = await AutoTestDataSourceCrud().copy_data_source_for_step(
                            case_id=new_step_instance.case_id,
                            case_code=case_instance.case_code,
                            step_id=new_step_instance.id,
                            step_code=new_step_instance.step_code,
                            source_data_source_id=source_data_source_id,
                        )
                    except Exception as e:
                        LOGGER.error(
                            f"复制步骤数据源失败(step_code={new_step_instance.step_code}, "
                            f"source_data_source_id={source_data_source_id}), 错误描述: {e}\n{traceback.format_exc()}"
                        )
                    if new_data_source_id:
                        new_step_instance.data_source_id = new_data_source_id
                    else:
                        # 源数据源不存在或复制失败：清空新步骤数据源指针，避免展开面板查询报错
                        new_step_instance.data_source_id = None
                        new_step_instance.data_source_name = None
                        new_step_instance.data_source_desc = None
                    await new_step_instance.save()

                processed_step_codes.setdefault(new_step_instance.case_id, set()).add(new_step_instance.step_code)
                step_dict: Dict[str, Any] = await new_step_instance.to_dict(
                    include_fields=["step_no", "step_code", "step_name"]
                )
                created_count += 1
                step_dict["created"] = True
                step_dict["step_id"] = new_step_instance.id
                success_detail.append(step_dict)

                # 递归处理子步骤
                if step_data.step_type == AutoTestStepType.IF and step_data.branch_items:
                    for bi, branch in enumerate(step_data.branch_items):
                        if branch.branch_children:
                            child_result = await self.batch_update_or_create_steps(
                                steps_data=branch.branch_children,
                                parent_step_id=new_step_instance.id,
                                branch_index=bi,
                            )
                            created_count += child_result["created_count"]
                            updated_count += child_result["updated_count"]
                            processed_step_codes[case_id].update(child_result["process_detail"][case_id])
                            success_detail.extend(child_result.get("success_detail", []))
                else:
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
                    exclude={"id", "case", "children", "quote_steps", "quote_case", "step_code", "branch_items"},
                    exclude_none=True
                )
                _readd_explicit_null_fields(step_data, update_dict, STEP_CLEARABLE_JSON_FIELDS)
                # step_is_skipped=False 需显式落库（exclude_none 会保留 False，此处再兜底一次）
                update_dict["step_is_skipped"] = bool(getattr(step_data, "step_is_skipped", False))
                if "parent_step_id" not in step_data.model_dump(exclude_unset=True) and parent_step_id is not None:
                    update_dict["parent_step_id"] = parent_step_id
                elif step_data.parent_step_id is not None:
                    update_dict["parent_step_id"] = step_data.parent_step_id
                elif step_data.parent_step_id is None and parent_step_id is None:
                    # 明确设置为None（根步骤）
                    update_dict["parent_step_id"] = None
                # branch_index 仅条件分支相关步骤持有(从0开始)：分支子步骤取所属分支序号，条件分支步骤本身归一化为0；
                # 其余步骤显式重置为 NULL，避免步骤移出分支后残留旧值
                if branch_index is not None:
                    update_dict["branch_index"] = branch_index
                elif step_data.step_type == AutoTestStepType.IF:
                    update_dict["branch_index"] = 0
                else:
                    update_dict["branch_index"] = None

                if step_data.step_type == AutoTestStepType.IF and step_data.branch_items:
                    update_dict["branch_items"] = [
                        b.model_dump(exclude={"branch_children"}) for b in step_data.branch_items
                    ]
                    update_dict.pop("loop_conditions", None)

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
                            f"第{sid}步骤更新失败, "
                            f"根据(case_id={case_id}, step_no={step_no}, step_code={step_code})条件查询步骤信息失败, "
                            f"同一用例下步骤序号不允许重复"
                        )
                        LOGGER.error(error_message)
                        raise DataBaseStorageException(message=error_message)

                if "case_id" in update_dict:
                    case_id: int = update_dict.get("case_id", step_instance.case_id)
                    case: Optional[AutoTestApiCaseInfo] = await case_crud.get_by_id(
                        case_id=case_id,
                        on_error=False,
                        state__not=1
                    )
                    if not case:
                        error_message: str = (
                            f"第{sid}步骤更新失败, "
                            f"根据(case_id={case_id})条件查询用例信息失败, "
                            f"所属用例信息不存在"
                        )
                        LOGGER.error(error_message)
                        raise NotFoundException(message=error_message)

                if "parent_step_id" in update_dict and update_dict["parent_step_id"]:
                    parent_step_id: int = update_dict["parent_step_id"]
                    parent_step = await self.get_by_id(step_id=parent_step_id, on_error=False, state__not=1)
                    if not parent_step:
                        error_message: str = (
                            f"第{sid}步骤更新失败, "
                            f"根据(step_id={parent_step_id})条件查询步骤信息失败, "
                            f"父级步骤信息不存在"
                        )
                        LOGGER.error(error_message)
                        raise NotFoundException(message=error_message)

                    case_id = update_dict.get("case_id", step_instance.case_id)
                    if parent_step.case_id != case_id:
                        error_message: str = (
                            f"第{sid}步骤更新失败, "
                            f"父级步骤(id={parent_step_id})和当前步骤(id={case_id})不一致"
                        )
                        LOGGER.error(error_message)
                        raise DataBaseStorageException(message=error_message)

                    if parent_step.step_type not in allowed_children_types:
                        error_message: str = (
                            f"第{sid}步骤更新失败, "
                            f"父级步骤(id={parent_step_id})的类型({parent_step.step_type})不允许包含子步骤"
                            f"(仅允许'循环结构'和'条件分支'类型的步骤包含子步骤)"
                        )
                        LOGGER.error(error_message)
                        raise ParameterException(message=error_message)

                    if parent_step.id == step_id:
                        error_message: str = (
                            f"第{sid}步骤更新失败, "
                            f"父级步骤(id={parent_step_id})和当前步骤(id={step_id})冲突, "
                            f"不能将自身设置为父步骤"
                        )
                        LOGGER.error(error_message)
                        raise DataBaseStorageException(message=error_message)

                    visited: Set[int] = set()
                    current_parent_id = parent_step.parent_step_id
                    while current_parent_id:
                        if current_parent_id == step_id:
                            error_message: str = (
                                f"第{sid}步骤更新失败, "
                                f"父级步骤(id={parent_step_id})和当前步骤(id={step_id})冲突, "
                                f"不能将自身设置为父步骤"
                            )
                            LOGGER.error(error_message)
                            raise DataBaseStorageException(message=error_message)
                        if current_parent_id in visited:
                            break
                        visited.add(current_parent_id)
                        parent = await self.get_by_id(step_id=current_parent_id, on_error=False, state__not=1)
                        if not parent:
                            break
                        current_parent_id = parent.parent_step_id
                    # 如果检测到循环引用，跳过当前步骤的更新
                    if current_parent_id == step_id:
                        continue

                if "quote_case_id" in update_dict and update_dict["quote_case_id"]:
                    quote_case_id: int = update_dict["quote_case_id"]
                    await case_crud.get_by_id(case_id=quote_case_id, on_error=True, state__not=1)

                try:
                    updated_instance = await self.update(id=step_id, obj_in=update_dict)
                except Exception as e:
                    error_message: str = f"第{sid}步骤更新失败, 错误描述: {e}"
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
                # 递归处理子步骤（条件分支: 差量替换; 其他: 增量）
                if step_data.step_type == AutoTestStepType.IF and step_data.branch_items:
                    # 收集本次提交仍存在的子步骤ID，仅软删除不再存在的旧子步骤，
                    # 避免把待更新的子步骤先删除导致后续根据 step_id 更新时查不到
                    retained_child_ids: Set[int] = set()
                    for branch in step_data.branch_items:
                        for child in (branch.branch_children or []):
                            if getattr(child, "step_id", None):
                                retained_child_ids.add(child.step_id)
                    stale_children_qs = self.model.filter(parent_step_id=step_id)
                    if retained_child_ids:
                        stale_children_qs = stale_children_qs.exclude(id__in=retained_child_ids)
                    stale_ids = await stale_children_qs.values_list("id", flat=True)
                    if stale_ids:
                        await self.model.filter(id__in=list(stale_ids)).delete()
                    for bi, branch in enumerate(step_data.branch_items):
                        if branch.branch_children:
                            child_result = await self.batch_update_or_create_steps(
                                steps_data=branch.branch_children,
                                parent_step_id=step_id,
                                branch_index=bi,
                            )
                            created_count += child_result["created_count"]
                            updated_count += child_result["updated_count"]
                            processed_step_codes[case_id].update(child_result["process_detail"][case_id])
                            success_detail.extend(child_result.get("success_detail", []))
                else:
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
            initial_variables: Optional[List[StepVariablesBase]] = None,
            steps_execute_config: Optional[Dict[str, StepsExecuteConfigBase]] = None,
            task_code: Optional[str] = None,
            batch_code: Optional[str] = None,
            dataset_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行单个用例：创建报告、拉取步骤树、调用执行引擎并写明细。

        :param case_id: 用例主键ID
        :param report_type: 报告类型枚举
        :param initial_variables: 初始变量列表，每项含key、value、desc
        :param steps_execute_config: 执行配置
        :param task_code: 任务标识代码，可选
        :param batch_code: 批次标识代码，可选
        :param dataset_name: 参数化执行时本次数据集名称，写入报告；数据由HTTP步骤执行器内查表获取
        :return: 含success、步骤指标(total/success/failed_steps、passed_ratio%)、report_code等
        """
        if not initial_variables or not isinstance(initial_variables, list):
            LOGGER.info(f"初始化变量[initial_variables]为空或非列表类型")
            initial_variables = []

        # 1. 查询用例信息
        case_crud = AutoTestApiCaseCrud()
        case_instance = await case_crud.get_by_id(case_id=case_id, on_error=True, state__not=1)
        case_dict = await case_instance.to_dict(
            include_fields={"id", "case_code", "case_name"},
            replace_fields={"id": "case_id"}
        )
        LOGGER.info(f"查询用例[id={case_id}]成功, 结果: {case_dict}")

        # 2. 查询步骤树数据（边界层已 model_validate）
        load: AutoTestCaseStepTreeLoadResult = await self.get_by_case_id(case_id)
        tree_data_count: Dict[str, int] = load.step_counter.model_dump()
        if load.step_counter.total_steps == 0:
            error_message: str = f"查询步骤为空, 用例[id={case_id}]没有任何可执行的根步骤"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        LOGGER.info(f"查询用例[id={case_id}]步骤树数据成功, 结果: {tree_data_count}")

        def _merge_session_variables(*parts: List[StepVariablesBase]) -> List[StepVariablesBase]:
            """根据key合并多段会话变量，后者覆盖前者。"""
            merged: Dict[str, StepVariablesBase] = {}
            for part in parts:
                for it in part:
                    if it.key:
                        merged[it.key] = it
            return list(merged.values())

        merge_all_variables: List[StepVariablesBase] = _merge_session_variables(
            step_variables_list_from_storage(getattr(case_instance, "session_variables", None)),
            AutoTestToolService.collect_session_variables(load.root_steps),
            list(initial_variables or []),
        )
        LOGGER.info(f"检查用例[id={case_id}]步骤树数据规范成功, 收集会话变量成功")

        # 5. 获取根步骤（执行前在引擎内统一 prepare）
        root_steps: List[AutoTestStepTreeUpdateItem] = [s for s in load.root_steps if s.parent_step_id is None]
        if not root_steps:
            error_message: str = f"获取用例[id={case_id}]根步骤失败, 没有任何可执行的根步骤"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 6. 执行用例（延后落库）：执行阶段不持事务，落库阶段单事务，保证「要么全部成功要么全部失败」且不长时间占锁
        engine = AutoTestStepExecutionEngine(save_report=True, task_code=task_code, batch_code=batch_code)
        results, logs, _, statistics, session_variables, defer_create_report, pending_create_details = await engine.execute_case(
            case=case_dict,
            steps=root_steps,
            initial_variables=merge_all_variables,
            steps_execute_config=steps_execute_config,
            report_type=report_type,
            dataset_name=dataset_name,
        )
        async with in_transaction():
            report_instance = await AutoTestApiReportCrud().create_report(report_in=defer_create_report)
            for detail_create in (pending_create_details or []):
                await AutoTestApiDetailCrud().create_detail(detail_in=detail_create)
            case_state = statistics.get("failed_steps", 0) == 0
            case_last_time = defer_create_report.case_ed_time
            await case_crud.update_case(AutoTestApiCaseUpdate(
                case_id=case_id,
                case_state=case_state,
                case_last_time=case_last_time,
            ))
        # 单次用例结果：步骤级指标用 *_steps / passed_ratio；success 表示本轮用例是否通过
        return {
            "success": statistics.get("failed_steps", 0) == 0,
            "total_steps": statistics.get("total_steps", 0),
            "success_steps": statistics.get("success_steps", 0),
            "failed_steps": statistics.get("failed_steps", 0),
            "passed_ratio": statistics.get("passed_ratio", 0.0),
            "report_code": report_instance.report_code,
            "saved_to_database": True,
            "case_id": case_id,
            "case_code": case_dict.get("case_code"),
            "case_name": case_dict.get("case_name"),
        }

    @staticmethod
    def _aggregate_case_runs(
            case_id: int,
            case_results: List[Dict[str, Any]],
            *,
            case_ok: bool,
            empty_error: str,
    ) -> Dict[str, Any]:
        """
        将同一用例多轮执行结果汇总为统一字段。

        """
        if not case_results:
            return {
                "case_id": case_id,
                "case_code": None,
                "case_name": None,
                "success": False,
                "error": empty_error,
                "saved_to_database": False,
                "execute_runs": 0,
                "total_steps": 0,
                "success_steps": 0,
                "failed_steps": 0,
                "passed_ratio": 0.0,
                "report_code": None,
            }
        last = case_results[-1]
        total_steps = sum(int(r.get("total_steps") or 0) for r in case_results)
        success_steps = sum(int(r.get("success_steps") or 0) for r in case_results)
        failed_steps = sum(int(r.get("failed_steps") or 0) for r in case_results)
        return {
            "case_id": last.get("case_id", case_id),
            "case_code": last.get("case_code"),
            "case_name": last.get("case_name"),
            "success": case_ok,
            "error": "",
            "saved_to_database": all(bool(r.get("saved_to_database")) for r in case_results),
            "execute_runs": len(case_results),
            "total_steps": total_steps,
            "success_steps": success_steps,
            "failed_steps": failed_steps,
            "passed_ratio": round(success_steps / total_steps * 100, 2) if total_steps > 0 else 0.0,
            "report_code": last.get("report_code"),
        }

    async def batch_execute_cases(
            self,
            case_ids: List[int],
            report_type: AutoTestReportType,
            initial_variables: Optional[List[StepVariablesBase]] = None,
            steps_execute_config: Optional[Dict[str, StepsExecuteConfigBase]] = None,
            cases_execute_config: Optional[Dict[str, Any]] = None,
            task_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        批量执行多个用例并汇总成功失败与明细。

        :param case_ids: 用例主键ID列表
        :param report_type: 报告类型枚举
        :param initial_variables: 初始变量列表，每项含key、value、desc
        :param steps_execute_config: 全部用例共用的执行配置
        :param cases_execute_config: 根据case_id的执行配置，优先于steps_execute_config
        :param task_code: 任务标识代码，可选
        :return: 批次汇总字典
        """
        if not initial_variables or not isinstance(initial_variables, list):
            initial_variables = []

        total_cases: int = len(case_ids)
        success_cases: int = 0
        failed_cases: int = 0
        results: List[Dict[str, Any]] = []
        LOGGER.info(f"{'= ' * 20}批量执行开始{'= ' * 20}")
        LOGGER.info(f"本次批量执行的用例ID列表: {case_ids}")
        batch_code: str = f"{int(datetime.datetime.now().timestamp())}-{uuid.uuid4().hex.upper()}"
        cases_cfg_map: Dict[str, Any] = cases_execute_config if isinstance(cases_execute_config, dict) else {}

        for case_id in case_ids:
            try:
                case_cfg = (cases_cfg_map.get(str(case_id)) or cases_cfg_map.get(case_id) or {})
                if not isinstance(case_cfg, dict):
                    case_cfg = {}
                per_steps_cfg = case_cfg.get("steps_execute_config") or steps_execute_config
                dataset_names = case_cfg.get("selected_dataset_names") or []
                if not isinstance(dataset_names, list):
                    dataset_names = []
                dataset_names = [str(x) for x in dataset_names if x is not None and str(x).strip()]

                raw_exec_count = case_cfg.get("execute_count", 1)
                try:
                    execute_count = int(raw_exec_count)
                except (TypeError, ValueError):
                    execute_count = 1
                execute_count = max(1, min(execute_count, 9999))

                LOGGER.info(
                    f"==> 执行[id={case_id}]开始: "
                    f"[execute_count={execute_count}, datasets={len(dataset_names)}]"
                )
                case_results: List[Dict[str, Any]] = []
                if dataset_names:
                    # 总轮次 = 执行次数 × 数据源数
                    total_runs = execute_count * len(dataset_names)
                    run_idx = 0
                    for _ in range(execute_count):
                        for ds_name in dataset_names:
                            run_idx += 1
                            one = await self.execute_single_case(
                                case_id=case_id,
                                initial_variables=initial_variables,
                                steps_execute_config=per_steps_cfg,
                                report_type=report_type,
                                task_code=task_code,
                                batch_code=batch_code,
                                dataset_name=ds_name,
                            )
                            case_results.append(one)
                            LOGGER.info(
                                f"用例[id={case_id}]第[{run_idx + 1}/{execute_count}]次执行完成: "
                                f"[dataset={ds_name}, success={one.get('success', False)}]"
                            )
                    empty_error = "未执行任何数据集"
                elif execute_count > 1:
                    for run_idx in range(execute_count):
                        one = await self.execute_single_case(
                            case_id=case_id,
                            initial_variables=initial_variables,
                            steps_execute_config=per_steps_cfg,
                            report_type=report_type,
                            task_code=task_code,
                            batch_code=batch_code,
                        )
                        case_results.append(one)
                        LOGGER.info(
                            f"用例[id={case_id}]第[{run_idx + 1}/{execute_count}]次执行完成: "
                            f"[success={one.get('success', False)}]"
                        )
                    empty_error = "未执行任何次数"
                else:
                    case_results.append(await self.execute_single_case(
                        case_id=case_id,
                        initial_variables=initial_variables,
                        steps_execute_config=per_steps_cfg,
                        report_type=report_type,
                        task_code=task_code,
                        batch_code=batch_code,
                    ))
                    empty_error = "未执行"

                case_ok = bool(case_results) and all(r.get("success") for r in case_results)
                result = self._aggregate_case_runs(
                    case_id, case_results, case_ok=case_ok, empty_error=empty_error,
                )
                results.append(result)
                if result.get("success"):
                    success_cases += 1
                else:
                    failed_cases += 1
            except Exception as e:
                error_message: str = f"执行用例[id={case_id}]异常, 错误描述: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                failed_cases += 1
                results.append(self._aggregate_case_runs(
                    case_id, [], case_ok=False, empty_error=error_message,
                ))
            LOGGER.info(f"==> 执行用例[id={case_id}]结束")
        LOGGER.info(f"{'= ' * 20}批量执行结束{'= ' * 20}")
        success_rate = round(success_cases / total_cases * 100, 2) if total_cases > 0 else 0.0
        return {
            "batch_code": batch_code,
            "total_cases": total_cases,
            "success_cases": success_cases,
            "failed_cases": failed_cases,
            "success_rate": success_rate,
            "results": results,
        }
