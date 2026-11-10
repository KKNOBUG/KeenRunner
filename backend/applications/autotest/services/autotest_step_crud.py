# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_step_crud.py
@DateTime: 2025/4/28
"""
import asyncio
import datetime
import traceback
import uuid
from typing import Optional, List, Dict, Any, Set, Tuple

from tortoise.exceptions import DoesNotExist, IntegrityError, FieldError
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from backend.applications.autotest.models.autotest_case_model import AutoTestCaseModel
from backend.applications.autotest.models.autotest_data_source_model import AutoTestDataSourceModel
from backend.applications.autotest.models.autotest_step_model import AutoTestStepModel
from backend.applications.autotest.schemas.autotest_case_schema import AutoTestCaseUpdate
from backend.applications.autotest.schemas.autotest_step_schema import (
    AutoTestStepCreate,
    AutoTestStepUpdate,
    AutoTestCaseStepTreeLoadResult,
    AutoTestStepTreeUpdateItem,
    StepTreeCounter,
    StepVariablesBase,
    StepsExecuteConfigBase,
    step_tree_item_from_storage,
    step_variables_list_from_storage,
)
from backend.applications.autotest.services.autotest_case_crud import AutoTestCaseCrud
from backend.applications.autotest.services.autotest_detail_crud import AutoTestDetailCrud
from backend.applications.autotest.services.autotest_report_crud import AutoTestReportCrud
from backend.applications.autotest.services.autotest_scope_guard import (
    CASE_TAG,
    assert_case_writable,
    assert_parent_readable,
)
from backend.applications.autotest.services.autotest_step_engine import AutoTestStepExecutionEngine
from backend.applications.autotest.services.autotest_tool_service import AutoTestToolService
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)
from backend.enums import (
    AutoTestCaseType,
    AutoTestStepType,
    AutoTestReportType,
    AutoTestTaskExecuteMode,
    AutoTestSessionTransfer,
    PUBLIC_CASE_TYPES
)
from backend.services import DataScope

# 支持“显式置空”回写的 JSON 类字段白名单：更新时显式传 null 需回补为 None，
# 否则 model_dump(exclude_none=True) 会丢弃 null 导致旧值残留（见 ScaffoldCrud.explicit_restored_null_fields）
STEP_CLEARABLE_JSON_FIELDS: Tuple[str, ...] = (
    "request_header", "request_params", "request_form_data", "request_form_urlencoded", "request_form_file", "request_body",
    "session_variables", "defined_variables", "extract_variables", "assert_validators", "database_operates", "redis_operates",
    "loop_conditions", "loop_index", "loop_key", "loop_value",
    "tcp_response_end_symbol",
)


async def _load_case_dataset_names(case_id: int) -> List[str]:
    """
    加载用例下所有数据源登记的数据场景名称（去重并保持首次出现顺序）。

    仅统计未软删（state≠1）的数据源，按创建时间升序逐条读取 dataset_names；
    每个名称经 str().strip() 后过滤空值，同名场景只保留第一次出现。

    :param case_id: 用例主键ID
    :return: 数据场景名称列表；无数据源时返回空列表
    """
    rows = await AutoTestDataSourceModel.filter(case_id=case_id, state__not=1).order_by("created_time").all()
    merged: List[str] = []
    seen: Set[str] = set()
    for row in rows:
        if isinstance(row.dataset_names, list):
            for name in row.dataset_names:
                name_str = str(name).strip()
                if name_str and name_str not in seen:
                    seen.add(name_str)
                    merged.append(name_str)
    return merged


async def _get_case_cached(
        case_cache: Dict[int, AutoTestCaseModel],
        case_crud: AutoTestCaseCrud,
        case_id: int,
        on_error: bool,
) -> Optional[AutoTestCaseModel]:
    """
    按 case_id 获取未软删的用例并缓存，同一保存调用内复用已查实例，减少长事务内重复查询。

    :param case_cache: 用例实例缓存（调用方创建并递归传递共享；未命中不缓存 None，避免把“查不到”固定进缓存）
    :param case_crud: 用例CRUD实例
    :param case_id: 用例主键ID
    :param on_error: 未找到时是否抛出异常
    :return: 用例实例或None
    :raises NotFoundException: on_error=True 且用例不存在（由 AutoTestCaseCrud 抛出）
    """
    if case_id in case_cache:
        return case_cache[case_id]
    instance = await case_crud.get_by_id(case_id=case_id, on_error=on_error, state__not=1)
    if instance:
        case_cache[case_id] = instance
    return instance


class AutoTestStepCrud(ScaffoldCrud[AutoTestStepModel, AutoTestStepCreate, AutoTestStepUpdate]):
    """
    自动化测试步骤的读写入口：单条增删改查、整树保存、引用链展开与用例执行编排。

    职责边界：
    - 步骤无独立归属，读写范围一律跟随父用例（父资源族）收敛，权限判定经 autotest_scope_guard；
    - 整树读取递归展开引用用例（quote_steps），并按 branch_index 还原条件分支的 branch_items 结构；
    - 整树保存负责结构约束校验、数据源复制与分支差量淘汰；step_no 唯一性留给调用方（步骤树保存视图）
      在整树写完后调 assert_step_no_unique 做终态校验；
    - 用例执行负责“执行阶段不持事务、报告与明细单事务落库”的编排，执行细节由步骤引擎承担。
    """

    def __init__(self):
        """
        初始化CRUD，绑定模型 AutoTestStepModel；list/create/update/soft_delete_batch 等通用能力由基类提供。
        """
        super().__init__(model=AutoTestStepModel)

    async def get_by_id(self, step_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestStepModel]:
        """
        根据主键ID查询步骤。

        :param step_id: 步骤主键ID
        :param on_error: 未找到时是否抛出异常
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

    async def get_by_code(self, step_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestStepModel]:
        """
        根据步骤标识代码查询步骤。

        :param step_code: 步骤标识代码
        :param on_error: 未找到时是否抛出异常
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

    async def get_by_unique(self, step_id: int, step_code: str, **kwargs) -> Optional[AutoTestStepModel]:
        """
        按 step_id 优先、否则 step_code 定位步骤（两者同时传入时只按 step_id 查）。

        定位失败一律抛异常（内部固定 on_error=True）：step_id 与 step_code 均未提供时抛 ParameterException，
        记录不存在时由 get_by_id/get_by_code 抛 NotFoundException。
        是否过滤软删记录由调用方通过 kwargs（如 state__not=1）传入，本方法不隐含该条件。

        :param step_id: 步骤主键ID
        :param step_code: 步骤标识代码（首尾空白会被去除）
        :param kwargs: 额外过滤条件，原样透传给 get_by_id/get_by_code
        :return: 步骤实例（on_error=True 保证不会返回 None）
        :raises ParameterException: step_id 与 step_code 同时为空
        :raises NotFoundException: 指定记录不存在
        """
        if step_id:
            return await self.get_by_id(step_id=step_id, on_error=True, **kwargs)
        step_code = (step_code or "").strip()
        if step_code:
            return await self.get_by_code(step_code=step_code, on_error=True, **kwargs)
        raise ParameterException(message="查询步骤信息失败, 参数[step_id, step_code]不允许同时为空")

    async def get_case_tree(
            self,
            case_id: Optional[int] = None,
            case_code: Optional[str] = None,
            scope: Optional[DataScope] = None,
    ) -> AutoTestCaseStepTreeLoadResult:
        """
        读取单个用例的步骤树（根步骤按 step_no 升序），包含引用链展开与步骤统计。

        结构约定：
        - 条件分支（IF）步骤的 branch_items 按 branch_index 分组挂 branch_children，children 恒为空列表；
        - 引用壳步骤（quote_case_id 非空）额外挂 quote_steps（被引用用例的根步骤树）与 quote_case（引用用例信息）；
        - 用例下无任何启用步骤时返回单节点 {"case": ...}，由 case_only_when_no_steps 承载，供前端空树编辑。

        统计口径（step_counter）：引用壳步骤不计数，实际计入的是被引用用例的内部步骤（quote_steps），
        即 total_steps = direct_steps + child_steps + quote_steps。

        :param case_id: 用例主键ID，与case_code二选一（同时传入时以case_id为准）
        :param case_code: 用例标识代码，与case_id二选一
        :param scope: 数据权限上下文，传入时校验用例所属人的读范围（步骤权限跟随所属用例，公共用例不受限）
        :return: AutoTestCaseStepTreeLoadResult（root_steps 为 AutoTestStepTreeUpdateItem 列表）
        :raises ParameterException: case_id 与 case_code 同时为空
        :raises NotFoundException: 所属用例不存在；引用用例缺失不抛错，仅置空 quote_case/quote_steps
        """
        case_crud = AutoTestCaseCrud()
        if case_id:
            case_instance: Optional[AutoTestCaseModel] = await case_crud.get_by_id(case_id=case_id, on_error=True, state__not=1)
        else:
            case_instance: Optional[AutoTestCaseModel] = await case_crud.get_by_code(case_code=case_code, on_error=True, state__not=1)
            case_id: int = case_instance.id

        # 公共脚本/公共接口对所有用户可见，不随数据范围收窄；步骤权限跟随所属用例（父资源族）
        await assert_parent_readable(scope, CASE_TAG, case_instance, "用例")

        from collections import defaultdict
        roots_by_case: Dict[int, List[AutoTestStepModel]] = defaultdict(list)
        children_by_parent: Dict[int, List[AutoTestStepModel]] = defaultdict(list)
        loaded_case_ids: Set[int] = set()

        async def ensure_case_steps_loaded(target_case_id: int) -> None:
            """懒加载指定用例的全部启用步骤并入内存分组；已加载的用例直接跳过，引用链递归时按需触发。"""
            if target_case_id in loaded_case_ids:
                return
            loaded_case_ids.add(target_case_id)
            case_steps: List[AutoTestStepModel] = await self.model.filter(case_id=target_case_id, state__not=1).all()
            for s in case_steps:
                if s.parent_step_id is None:
                    roots_by_case[target_case_id].append(s)
                else:
                    children_by_parent[s.parent_step_id].append(s)

        await ensure_case_steps_loaded(case_id)
        root_steps: List[AutoTestStepModel] = sorted(roots_by_case.get(case_id, []), key=lambda s: s.step_no)
        root_index = [step.step_no for step in root_steps]
        LOGGER.info(f"获取用例[case_id={case_id}]根步骤成功, 共计: {len(root_steps)}个, 根步骤序号: {root_index}")

        # 用例字典缓存：同用例下所有步骤共用同一份用例信息，避免逐步骤重复查询
        case_dict_cache: Dict[int, Dict[str, Any]] = {
            case_id: await case_instance.to_dict(
                exclude_fields={
                    "state",
                    "created_user", "updated_user",
                    "created_time", "updated_time",
                    "reserve_1", "reserve_2", "reserve_3"
                },
                replace_fields={"id": "case_id"}
            )
        }

        async def get_case_dict(target_case_id: int, on_error: bool) -> Optional[Dict[str, Any]]:
            """按case_id获取用例字典(缓存优先)，未命中时查库并回填缓存；出口返回副本避免多步骤共享同一字典对象。"""
            if target_case_id in case_dict_cache:
                return dict(case_dict_cache[target_case_id])
            case: Optional[AutoTestCaseModel] = await case_crud.get_by_id(case_id=target_case_id, on_error=on_error, state__not=1)
            if not case:
                return None
            case_dict = await case.to_dict(
                exclude_fields={
                    "state",
                    "created_user", "updated_user",
                    "created_time", "updated_time",
                    "reserve_1", "reserve_2", "reserve_3"
                },
                replace_fields={"id": "case_id"}
            )
            case_dict_cache[target_case_id] = case_dict
            return dict(case_dict)

        # 步骤计数器（引用壳不计数）
        # direct_steps: 当前用例的根步骤数（parent_step_id 为 None 且非引用壳）
        # child_steps: 当前用例树内的子步骤数（parent_step_id 不为 None，不含引用链内步骤）
        # quote_steps: 引用链内被引用用例的步骤数（is_quote=True 时计入）
        # total_steps: 总步骤数 = direct_steps + child_steps + quote_steps（引用壳本身不计数，实际执行的是被引用步骤）
        step_counter = {
            "direct_steps": 0,
            "child_steps": 0,
            "quote_steps": 0,
            "total_steps": 0
        }

        # 递归构建步骤树
        async def build_step_tree(step: AutoTestStepModel, is_quote: bool = False) -> Dict[str, Any]:
            """递归构建单步及其子步骤、引用脚本步骤的树形字典并统计各类步骤数量。"""
            # 引用壳步骤不计数：壳本身不执行，实际执行的是被引用用例的内部步骤(quote_steps)，避免双重计数
            if not step.quote_case_id:
                step_counter["total_steps"] += 1
                if is_quote:
                    step_counter["quote_steps"] += 1
                elif step.parent_step_id is None:
                    step_counter["direct_steps"] += 1
                else:
                    step_counter["child_steps"] += 1

            # 获取步骤基本信息(内存序列化, 无DB查询)
            step_dict = await step.to_dict(
                exclude_fields={
                    "state",
                    "created_user", "updated_user",
                    "created_time", "updated_time",
                    "reserve_1", "reserve_2", "reserve_3"
                },
                replace_fields={"id": "step_id"}
            )
            # 获取用例信息（同用例缓存复用，不再逐步骤查库）
            if step.case_id:
                step_dict["case"] = await get_case_dict(step.case_id, on_error=True)

            # 获取子步骤（内存分组读取，递归构建）
            children: List[AutoTestStepModel] = sorted(
                children_by_parent.get(step.id, []),
                key=lambda s: (s.branch_index is not None, s.branch_index or 0, s.step_no)
            )
            if step.step_type == AutoTestStepType.IF and step.branch_items:
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
                step_dict["children"] = [await build_step_tree(child, is_quote=is_quote) for child in children]
            else:
                step_dict["children"] = []

            if not step.quote_case_id:
                step_dict["quote_steps"] = []
                step_dict["quote_case"] = None
                return step_dict

            quote_case_dict = await get_case_dict(step.quote_case_id, on_error=False)
            if not quote_case_dict:
                step_dict["quote_steps"] = []
                step_dict["quote_case"] = None
                return step_dict

            # 获取引用的公共脚本的所有步骤(包含子步骤, 递归构建)
            await ensure_case_steps_loaded(step.quote_case_id)
            quote_case_root_steps: List[AutoTestStepModel] = sorted(
                roots_by_case.get(step.quote_case_id, []), key=lambda s: s.step_no
            )
            step_dict["quote_steps"] = [await build_step_tree(quote, is_quote=True) for quote in quote_case_root_steps]
            step_dict["quote_case"] = quote_case_dict
            return step_dict

        # 构建所有根步骤的树
        result = []
        for root_id, root_step in enumerate(root_steps, start=1):
            result.append(await build_step_tree(root_step))

        # 用例下没有任何启用步骤时，回退为仅含 case 的单节点结构，
        # 最终由 case_only_when_no_steps 字段承载，供前端以空树编辑用例本身
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
        case_only: Optional[AutoTestCaseUpdate] = None
        # 单节点且仅含 case 键 → 走“无步骤”分支，避免把用例信息误解析为步骤项
        if len(raw_roots) == 1 and isinstance(raw_roots[0], dict) and list(raw_roots[0].keys()) == ["case"]:
            case_only = AutoTestCaseUpdate.model_validate(raw_roots[0]["case"])
            root_models: List[AutoTestStepTreeUpdateItem] = []
        else:
            root_models = [step_tree_item_from_storage(r) for r in raw_roots]
        return AutoTestCaseStepTreeLoadResult(
            root_steps=root_models,
            step_counter=meta,
            case_only_when_no_steps=case_only,
        )

    async def get_copy_tree(
            self,
            case_id: Optional[int] = None,
            case_code: Optional[str] = None,
            scope: Optional[DataScope] = None,
    ) -> Dict[str, Any]:
        """
        读取用例步骤树并剔除标识字段，生成“复制后尚未落库”的编辑副本。

        返回结构与步骤树接口一致，但所有节点的 step_id/step_code/parent_step_id/step_no 以及
        data_source_id/data_source_name/data_source_desc 均置空，case 块中的 case_id/case_code 也置空；
        复制得到的树首次保存时全部按新增处理。

        :param case_id: 用例主键ID，与case_code二选一
        :param case_code: 用例标识代码，与case_id二选一
        :param scope: 数据权限上下文，传入时校验用例所属人的读范围
        :return: {"case": {...}, "steps": [...]}；用例无步骤时为 {"case": {...}, "steps": []}
        """
        load = await self.get_case_tree(case_id=case_id, case_code=case_code, scope=scope)

        def strip_step_for_copy_model(step: AutoTestStepTreeUpdateItem) -> AutoTestStepTreeUpdateItem:
            """
            递归返回脱敏后的节点副本（不修改入参）：清空 step_id/step_code/parent_step_id/step_no、
            data_source_id/data_source_name/data_source_desc，case 块清空 case_id/case_code；
            children/branch_children/quote_steps 一并递归处理。
            """
            case_block = step.case
            if isinstance(case_block, dict):
                case_block = {**case_block, "case_id": None, "case_code": None}
            children = [strip_step_for_copy_model(c) for c in (step.children or [])]
            quotes = [strip_step_for_copy_model(q) for q in (step.quote_steps or [])]
            branches = [
                branch.model_copy(update={
                    "branch_children": [strip_step_for_copy_model(child) for child in (branch.branch_children or [])] or None,
                })
                for branch in (step.branch_items or [])
            ]
            return step.model_copy(
                update={
                    "step_id": None,
                    "step_no": None,
                    "step_code": None,
                    "parent_step_id": None,
                    "data_source_id": None,
                    "data_source_name": None,
                    "data_source_desc": None,
                    "case": case_block,
                    "children": children or None,
                    "quote_steps": quotes or [],
                    "branch_items": branches or None,
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

    async def get_cases_splice_tree(
            self,
            case_ids: Optional[List[int]] = None,
            case_codes: Optional[List[str]] = None,
            scope: Optional[DataScope] = None,
    ) -> Tuple[Dict[str, Any], int]:
        """
        批量读取多个用例的步骤树，并按入参顺序拼接为单一节点列表。

        同一用例的多棵根步骤节点在 details 中连续排列；indexes 记录 case_id（字符串形式）
        -> 该用例节点在 details 中的下标区间，供前端按用例定位/裁剪节点；
        total_steps 取各用例 step_counter.total_steps 之和（引用壳不计数）。

        :param case_ids: 用例主键ID列表，与case_codes二选一（同时传递时以case_ids为准，重复ID去重保序）
        :param case_codes: 用例标识代码列表，与case_ids二选一（重复编码去重保序）
        :param scope: 数据权限上下文，传入时逐个校验用例所属人的读范围
        :return: ({"details": [...], "indexes": {...}}, 所有用例步骤总数)
        :raises ParameterException: case_ids 与 case_codes 同时为空
        :raises NotFoundException: 任一所选用例不存在（首个异常立即上抛，其余并发任务继续执行但结果被丢弃）
        """
        if not case_ids and not case_codes:
            error_message: str = "参数[case_ids, case_codes]不允许同时为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        if case_ids:
            targets: List[Tuple[Optional[int], Optional[str]]] = [(tid, None) for tid in dict.fromkeys(case_ids)]
        else:
            targets: List[Tuple[Optional[int], Optional[str]]] = [(None, tcd) for tcd in dict.fromkeys(case_codes)]

        # 各用例步骤树相互独立，并发加载以摊薄逐步骤查询的往返开销；
        # gather 结果与 targets 顺序严格一致，保证拼接顺序稳定；
        # 任一用例查询异常（如不存在）会立即抛出，其余任务不会被取消（仍在后台跑完，仅结果被丢弃），
        # 对外表现与串行一致：首个异常上抛，不返回部分结果。
        loads = await asyncio.gather(*[
            self.get_case_tree(case_id=target_id, case_code=target_code, scope=scope)
            for target_id, target_code in targets
        ])

        total_steps: int = 0
        indexes: Dict[str, List[int]] = {}
        details: List[Dict[str, Any]] = []
        for (target_id, target_code), load in zip(targets, loads):
            start_index: int = len(details)
            if load.root_steps:
                details.extend(s.model_dump(mode="json") for s in load.root_steps)
                resolved_case_id: Optional[int] = load.root_steps[0].case_id
            elif load.case_only_when_no_steps is not None:
                details.append({"case": load.case_only_when_no_steps.model_dump(mode="json")})
                resolved_case_id = load.case_only_when_no_steps.case_id
            else:
                resolved_case_id = target_id
            indexes[str(resolved_case_id)] = list(range(start_index, len(details)))
            # 步数统计取步骤树口径（引用壳不计数），与步骤树接口的 step_counter 保持一致
            total_steps += load.step_counter.total_steps

        LOGGER.info(f"多用例步骤树拼接完成: 用例数={len(targets)}, 拼接节点数={len(details)}, 步骤总数={total_steps}")
        return {"details": details, "indexes": indexes}, total_steps

    async def get_step_usage_projects(
            self,
            case_id: Optional[int] = None,
            case_code: Optional[str] = None,
            scope: Optional[DataScope] = None,
    ) -> List[int]:
        """
        从用例步骤树中提取请求类步骤所选用的应用ID集合（升序去重）。

        覆盖范围：HTTP/TCP 步骤的 request_project_id；数据库/Redis 步骤每个操作的 project_id。
        非法（非整数）应用ID直接报错，避免静默跳过后削弱父应用可读校验。

        :param case_id: 用例主键ID，与case_code二选一
        :param case_code: 用例标识代码，与case_id二选一
        :param scope: 数据权限上下文，传入时校验用例所属人的读范围
        :return: 去重后的project_id列表（升序）
        :raises ParameterException: 步骤中的应用ID不是有效整数
        """
        load = await self.get_case_tree(case_id=case_id, case_code=case_code, scope=scope)
        project_ids: Set[int] = set()

        def _collect_project_id(raw_project_id: Any) -> None:
            """收集合法应用ID；非法数据显式失败，避免跳过后削弱父应用可读校验。"""
            if not raw_project_id:
                return
            try:
                project_ids.add(int(raw_project_id))
            except (TypeError, ValueError) as exc:
                error_message: str = f"提取步骤所属应用失败, 应用ID[{raw_project_id}]不是有效整数"
                LOGGER.error(error_message)
                raise ParameterException(message=error_message) from exc

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
                _collect_project_id(step.request_project_id)
            elif st_e == AutoTestStepType.DATABASE:
                for db_operate in step.database_operates or []:
                    _collect_project_id(db_operate.project_id)
            elif st_e == AutoTestStepType.REDIS:
                for redis_operate in step.redis_operates or []:
                    _collect_project_id(redis_operate.project_id)
            for child in step.children or []:
                recursive_require_project_ids(child)
            for quote_step in step.quote_steps or []:
                recursive_require_project_ids(quote_step)

        for node in load.root_steps:
            recursive_require_project_ids(node)

        return sorted(project_ids)

    async def create_step(self, step_in: AutoTestStepCreate, scope: DataScope) -> AutoTestStepModel:
        """
        创建单条步骤。

        校验顺序：用例存在且当前用户可写（步骤归属跟随用例）→ 父步骤存在且同用例
        → 引用用例存在（仅校验存在性，不限制用例类型，与 update_step 不同）
        → 同用例同 step_no 已存在时转为“恢复并更新”（state 置 0，且不覆盖原 created_user）。

        :param step_in: 步骤创建schema
        :param scope: 数据权限上下文，步骤归属跟随用例所属人
        :return: 创建或恢复后的步骤实例
        :raises NotFoundException: 用例、父步骤或引用用例不存在
        :raises NoPermissionException: 当前用户不在用例的写入范围内（由 assert_case_writable 抛出）
        :raises DataBaseStorageException: 落库冲突（唯一键或外键无效）
        """
        case_id: int = step_in.case_id
        step_no: int = step_in.step_no
        case_crud = AutoTestCaseCrud()
        case_instance = await case_crud.get_by_id(case_id=case_id, on_error=True, state__not=1)
        # 步骤无独立归属，读写范围一律按父用例资源族收敛
        await assert_case_writable(scope, case_instance, "新增步骤")

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
                    f"步骤序号(step_no={step_no})引用公共脚本/接口(case_id={quote_case_id})不存在"
                )
                LOGGER.error(error_message)
                raise NotFoundException(message=error_message)

        step_dict = step_in.model_dump(exclude_none=True, exclude_unset=True)
        existing_step = await self.model.filter(case_id=case_id, step_no=step_no).first()
        if not existing_step:
            try:
                instance: AutoTestStepModel = await self.create(step_dict)
                return instance
            except IntegrityError as e:
                error_message: str = "新增步骤信息失败，步骤序号可能重复或关联用例、父步骤、引用用例无效，请检查步骤配置后重试"
                LOGGER.error(
                    f"{error_message}, "
                    f"关键字段: [case_id={case_id}, step_no={step_no}, "
                    f"parent_step_id={step_in.parent_step_id}, quote_case_id={step_in.quote_case_id}]\n"
                    f"{traceback.format_exc()}"
                )
                raise DataBaseStorageException(message=error_message) from e

        # 命中的存量记录可能是已软删步骤（step_no 定位未过滤 state）：走恢复更新，不新建记录
        try:
            # 恢复软删步骤不得覆盖原创建人
            step_dict.pop("created_user", None)
            step_dict["state"] = 0
            instance: AutoTestStepModel = await self.update(id=existing_step.id, obj_in=step_dict)
            return instance
        except (DoesNotExist, IntegrityError) as e:
            error_message: str = "新增步骤信息失败，目标步骤可能已被删除或步骤数据与现有记录冲突，请刷新后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [case_id={case_id}, step_no={step_no}, step_id={existing_step.id}]\n"
                f"{traceback.format_exc()}"
            )
            raise DataBaseStorageException(message=error_message) from e

    async def update_step(self, step_in: AutoTestStepUpdate, scope: DataScope) -> AutoTestStepModel:
        """
        更新单条步骤（按 step_id 优先、否则 step_code 定位）。

        校验顺序：定位步骤 → 目标用例存在且当前用户可写（含迁移后的目标用例）
        → step_no 在用例内不重复 → 父步骤必须存在、同用例、类型为条件分支/循环结构且不构成环
        → 引用用例必须存在且属于公共家族（公共脚本/公共接口）。

        显式传 null 的 JSON 字段会回补为 None（STEP_CLEARABLE_JSON_FIELDS），避免 exclude_none 导致旧值残留。
        边界：更新字典为空时直接返回原实例，不落库、也不触发用例存在性与写权限校验。

        :param step_in: 步骤更新schema
        :param scope: 数据权限上下文，步骤归属跟随用例所属人(含迁移后的目标用例)
        :return: 更新后的步骤实例（空更新时为原实例）
        :raises NotFoundException: 步骤/用例/父步骤不存在，或引用用例不是公共家族用例
        :raises DataAlreadyExistsException: 同用例下 step_no 重复
        :raises DataBaseStorageException: 父步骤指向自身/成环，或落库冲突
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
        self.explicit_restored_null_fields(
            payload=step_in,
            update_dict=update_dict,
            field_names=STEP_CLEARABLE_JSON_FIELDS
        )
        if not update_dict:
            # 空更新直接返回原实例：不落库，也不触发用例存在性与写权限校验
            return instance

        target_case = await AutoTestCaseCrud().get_by_id(
            case_id=step_in.case_id or instance.case_id, on_error=True, state__not=1
        )
        # 迁移目标用例同样按用例资源族校验读写范围
        await assert_case_writable(scope, target_case, "更新步骤")

        if "step_no" in update_dict:
            case_id = update_dict.get("case_id", instance.case_id)
            step_no = update_dict.get("step_no", instance.step_no)
            existing_step = await self.model.filter(
                case_id=case_id,
                step_no=step_no,
                state__not=1
            ).exclude(id=step_id).first()
            if existing_step:
                error_message: str = f"根据(case_id={case_id}, step_no={step_no})条件检查步骤信息失败, 同一用例下步骤序号不允许重复"
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)

        if "parent_step_id" in update_dict:
            parent_step_id: Optional[int] = update_dict["parent_step_id"]
            if parent_step_id:
                parent_step: AutoTestStepModel = await self.model.filter(
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
            quote_case = await AutoTestCaseCrud().get_by_conditions(
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
            error_message: str = "更新步骤信息失败，目标步骤不存在或已被删除，请刷新后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [step_id={step_id}, step_code={step_code}]\n"
                f"{traceback.format_exc()}"
            )
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = "更新步骤信息失败，步骤序号可能重复或关联用例、父步骤、引用用例无效，请检查步骤配置后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [step_id={step_id}, step_code={step_code}, case_id={instance.case_id}]\n"
                f"{traceback.format_exc()}"
            )
            raise DataBaseStorageException(message=error_message) from e

    async def delete_step(
            self,
            scope: DataScope,
            step_id: Optional[int] = None,
            step_code: Optional[str] = None,
    ) -> AutoTestStepModel:
        """
        物理删除单条步骤（存在未软删子步骤时拒绝）。

        删除后同步硬删该步骤关联的数据源记录与本地文件：清理入口按 step_code 匹配，
        case_id 仅用于日志定位（见 AutoTestDataSourceCrud.delete_step_data_sources）。
        注意：单条删除为物理删除，软删语义只保留在批量删除与淘汰链路。

        :param scope: 数据权限上下文，步骤归属跟随用例所属人
        :param step_id: 步骤主键ID，与step_code二选一
        :param step_code: 步骤标识代码，与step_id二选一
        :return: 删除前的步骤实例快照
        :raises DataAlreadyExistsException: 该步骤仍存在子步骤
        """
        if step_id:
            instance = await self.get_by_id(step_id=step_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(step_code=step_code, on_error=True, state__not=1)
            step_id: int = instance.id

        case_instance = await AutoTestCaseCrud().get_by_id(case_id=instance.case_id, on_error=True, state__not=1)
        await assert_case_writable(scope, case_instance, "删除步骤")

        children_count = await self.model.filter(parent_step_id=step_id, state__not=1).count()
        if children_count > 0:
            error_message: str = (
                f"根据(parent_step_id={step_id})条件检查步骤信息失败, "
                f"记录[id={step_id}]存在{children_count}个子级步骤, 无法直接删除"
            )
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        # 单删步骤与单删用例一致为物理删除，软删语义仅保留在批量与淘汰链路
        await instance.delete()
        # 同步硬删除该步骤关联的数据源（局部导入：仅删除链路需要，避免文件顶部长期耦合）
        from backend.applications.autotest.services.autotest_data_source_crud import AutoTestDataSourceCrud
        await AutoTestDataSourceCrud().delete_step_data_sources(case_id=instance.case_id, step_code_list=[instance.step_code])
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
        递归软删除步骤树（state=1），返回实际删除数量。

        三种定位方式互斥，按优先级判定：step_id/step_code（单步及其子树）
        → parent_step_id（该父步骤下所有子步骤）→ case_id（用例下所有根步骤及其子树）；
        三者均未提供时不删除任何节点，直接返回 0。

        实现要点：先后序收集待删节点（先子后父），再单次批量软删；
        相比逐节点软删省去 N 次更新往返（收集阶段仍需逐层查询子节点）。
        事务边界：收集与软删在同一事务内提交，数据源清理在事务提交后执行（不在事务内）。

        :param step_id: 单步主键ID，与step_code二选一时删除该步及所有子步骤
        :param step_code: 单步标识代码，与step_id二选一
        :param parent_step_id: 指定父步骤ID时，删除该父步骤下所有子步骤
        :param case_id: 指定用例ID时，删除该用例下所有根步骤(及子步骤)
        :param exclude_step: 不删除的 (step_id, step_code) 集合(仅跳过节点自身，不阻断其子树收集)
        :return: 实际软删除的步骤数量
        :raises NotFoundException: step_id/step_code 定位不到步骤
        """
        if exclude_step is None:
            exclude_step = set()
        # 记录本次软删除的步骤，根据用例归类，事务提交后同步清理其数据源
        deleted_by_case: Dict[int, List[str]] = {}
        # 后序收集待删步骤(先子后父，与原逐条软删顺序一致)，exclude_step仅跳过节点自身
        pending_steps: List[AutoTestStepModel] = []

        async def collect_step_and_children(step_instance: AutoTestStepModel) -> None:
            """后序收集当前步骤及其所有子步骤(先子后父)，exclude_step仅跳过节点自身、不阻断子树收集。"""
            children = await self.model.filter(parent_step_id=step_instance.id, state__not=1).all()
            for child in children:
                await collect_step_and_children(step_instance=child)
            if (step_instance.id, step_instance.step_code) not in exclude_step:
                pending_steps.append(step_instance)

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
                    await collect_step_and_children(step_instance=step)

            elif parent_step_id is not None:
                # 删除指定父步骤下的所有子步骤
                existing_steps = await self.model.filter(
                    parent_step_id=parent_step_id,
                    state__not=1
                ).all()
                LOGGER.warning("删除指定父级步骤下所有的子级步骤: ")
                for step in existing_steps:
                    if (step.id, step.step_code) not in exclude_step:
                        await collect_step_and_children(step_instance=step)

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
                        await collect_step_and_children(step_instance=step)

            # 子树收集完成后单次批量软删，与delete_case的步骤批量软删语义一致
            deleted_count: int = 0
            if pending_steps:
                await self.soft_delete_batch(ids=[step.id for step in pending_steps])
                deleted_count = len(pending_steps)
                for step_instance in pending_steps:
                    deleted_by_case.setdefault(step_instance.case_id, []).append(step_instance.step_code)
                    LOGGER.warning(
                        f"警告: 删除步骤(step_id={step_instance.id}, "
                        f"step_no={step_instance.step_no}, step_code={step_instance.step_code})成功"
                    )

        # 步骤软删除提交后，同步清理对应用例下被删步骤的数据源
        if deleted_by_case:
            from backend.applications.autotest.services.autotest_data_source_crud import AutoTestDataSourceCrud
            data_source_curd = AutoTestDataSourceCrud()
            for ds_case_id, step_codes in deleted_by_case.items():
                await data_source_curd.delete_step_data_sources(case_id=ds_case_id, step_code_list=step_codes)

        return deleted_count

    async def select_steps(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestStepModel]]:
        """
        根据条件分页查询步骤列表。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: 由 (总条数, 当前页记录列表) 组成的元组
        :raises ParameterException: 查询或排序条件包含模型不支持的字段
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = "查询步骤信息失败，查询或排序条件包含不支持的字段，请调整筛选或排序条件"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    @classmethod
    def _iter_tree_steps(cls, steps_data):
        """
        深度优先遍历步骤树的全部节点（先自身，再 children，最后 branch_items.branch_children）。

        不进入 quote_steps：引用链属于被引用用例的树，不参与当前用例的公共家族校验。

        :param steps_data: 根级或某一层的步骤项列表，None/空列表直接结束
        :return: 生成器，逐项产出步骤项
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
        校验公共家族（公共脚本/公共接口）步骤树约束，并在公共接口场景下就地修正所属应用。

        校验项：全树不允许出现引用步骤（QUOTE_PUBLIC_SCRIPT/QUOTE_PUBLIC_API），不允许绑定数据源；
        公共接口额外要求“有且仅有 1 个 HTTP/TCP 根步骤”。
        副作用（非纯校验）：公共接口且仅有 1 个根步骤时，把该步骤的 request_project_id 强制对齐为用例所属应用
        （前端已只读锁定，这里兜底 API 直调传入缺失或不一致的值）。

        :param steps_data: 根级步骤树项列表
        :param case_type: 当前用例目标类型(必为公共家族成员)
        :param case_project: 当前用例所属应用ID(公共接口一致性校验与对齐使用)
        :return: None
        :raises ParameterException: 出现引用步骤、数据源绑定或公共接口形态不合法
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
            if step_data.step_type in (AutoTestStepType.QUOTE_PUBLIC_SCRIPT, AutoTestStepType.QUOTE_PUBLIC_API):
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
        校验公共接口步骤树形态：有且仅有 1 个 HTTP/TCP 根步骤，且不携带子级结构与数据源。

        :param steps_data: 根级步骤树项列表
        :return: None
        :raises ParameterException: 根步骤数量、类型或结构不符合公共接口约束
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
            parent_step_instance: Optional[AutoTestStepModel] = None,
            case_cache: Optional[Dict[int, AutoTestCaseModel]] = None,
    ) -> Dict[str, Any]:
        """
        递归保存步骤树：按 step_id/step_code 判定新增或更新，并处理条件分支、数据源复制与递归子节点。

        定位与归属：step_id 优先、其次 step_code；定位到的步骤必须属于入参 case_id，否则拒绝
        （禁止借 step_id 把他人步骤跨用例迁走）。
        结构约束：父步骤必须存在、同用例且类型为循环结构/条件分支；新增时 step_no、step_type 必填。
        branch_index 约定：分支子步骤写入所属分支序号（从 0 起），条件分支步骤自身归一化为 0，
        其余步骤新增时不写入、更新时显式置 NULL（避免步骤移出分支后残留旧值）。
        条件分支子步骤为“差量替换”：不在本次提交中的旧子步骤会被物理删除，并同步硬删其数据源；
        其他子步骤为增量新增/更新。
        step_no 唯一性不在逐个节点拦截，由调用方（步骤树保存视图）在整树写完后调 assert_step_no_unique 终态校验。

        :param steps_data: 当前层级的步骤项列表
        :param parent_step_id: 当前层级的父步骤ID（递归传入，优先于节点自带的 parent_step_id）
        :param branch_index: 当前层级所属分支序号（条件分支子步骤使用）
        :param parent_step_instance: 当前层级父步骤实例（递归时由上层传入，命中时复用免重复查询）
        :param case_cache: 用例实例缓存（根级调用自动创建，递归共享，同一用例整树只查一次）
        :return: {"created_count": 新增数, "updated_count": 更新数,
                 "process_detail": {case_id: 本次处理的 step_code 集合}, "success_detail": 节点摘要列表}
        :raises ParameterException: 跨用例迁移、必填字段缺失、父步骤类型不允许包含子步骤
        :raises DataAlreadyExistsException: 新增时父步骤与当前步骤不属于同一用例
        :raises NotFoundException: 定位的步骤、用例、父步骤或引用用例不存在
        :raises DataBaseStorageException: 落库失败
        """
        # 本层及递归子层的累计指标：成功计数、节点摘要、按用例归集的已处理 step_code
        created_count: int = 0
        updated_count: int = 0
        success_detail: List[Dict[str, Any]] = []
        processed_step_codes: Dict[int, Set[str]] = {}
        # 仅循环结构与条件分支允许包含子步骤（新增与更新共用该白名单）
        allowed_children_types = {AutoTestStepType.LOOP, AutoTestStepType.IF}
        case_crud = AutoTestCaseCrud()
        # 同一保存调用内同一用例只查一次，降低整树保存长事务内的重复查询
        case_cache: Dict[int, AutoTestCaseModel] = {} if case_cache is None else case_cache

        # 公共家族约束（仅根级调用校验）：公共脚本/公共接口均不可引用其他脚本、全树不可绑定数据源；
        # 公共接口另有形态约束（有且仅有 1 个 HTTP/TCP 根步骤）。
        # 与用例保存同事务执行（用例更新在前），此处读到的是目标类型，校验失败抛异常由上层事务回滚。
        if parent_step_id is None and branch_index is None and steps_data:
            root_case_id: Optional[int] = steps_data[0].case_id
            if root_case_id:
                root_case = await _get_case_cached(
                    case_cache=case_cache,
                    case_crud=case_crud,
                    case_id=root_case_id,
                    on_error=False,
                )
                if root_case and root_case.case_type in PUBLIC_CASE_TYPES:
                    self._validate_public_family_tree(steps_data, root_case.case_type, root_case.case_project)

        for sid, step_data in enumerate(steps_data, start=1):
            case_id: Optional[int] = step_data.case_id
            step_id: Optional[int] = step_data.step_id
            step_no: Optional[int] = step_data.step_no
            step_code: Optional[str] = step_data.step_code
            if step_id:
                step_instance: Optional[AutoTestStepModel] = await self.get_by_id(step_id=step_id, on_error=True, state__not=1)
                step_code = step_instance.step_code
            elif step_code:
                step_instance: Optional[AutoTestStepModel] = await self.get_by_code(
                    step_code=step_code,
                    on_error=True,
                    state__not=1,
                )
                step_id = step_instance.id
            else:
                step_instance = None

            # 步骤只属于定位到的那条用例：跨用例传入 step_id 会把他人步骤迁走，必须前置拒绝
            if step_instance and step_data.case_id and int(step_instance.case_id or 0) != int(step_data.case_id):
                error_message: str = (
                    f"第{sid}步骤更新失败, 步骤[{step_code}]不属于用例[case_id={step_data.case_id}], "
                    f"不允许跨用例迁移"
                )
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)

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

                case_instance = await _get_case_cached(
                    case_cache=case_cache,
                    case_crud=case_crud,
                    case_id=step_data.case_id,
                    on_error=True,
                )

                parent_step: Optional[AutoTestStepModel] = None
                final_parent_step_id = parent_step_id if parent_step_id is not None else step_data.parent_step_id
                if final_parent_step_id:
                    # 递归调用时父实例已由上层传入，命中即复用，避免每个子节点重复查询同一父步骤
                    if parent_step_instance is not None and final_parent_step_id == parent_step_instance.id:
                        parent_step = parent_step_instance
                    else:
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
                    new_step_instance: AutoTestStepModel = await self.create(create_step_dict)
                except Exception as e:
                    error_message: str = f"第{sid}条步骤新增失败，步骤数据无效或暂时无法保存，请检查步骤配置后重试"
                    LOGGER.error(
                        f"{error_message}, "
                        f"关键字段: [case_id={case_id}, step_no={step_no}, "
                        f"parent_step_id={final_parent_step_id}, step_type={step_data.step_type}]\n"
                        f"{traceback.format_exc()}"
                    )
                    raise DataBaseStorageException(message=error_message) from e

                # 复制来的步骤携带数据源时，同步复制为新步骤的独立数据源（仅复制解析数据，文件字段置空）；
                # 复制失败不中断整树保存，仅记日志并清空新步骤的数据源指针
                source_data_source_id = getattr(step_data, "data_source_id", None)
                if source_data_source_id:
                    # 局部导入：仅数据源复制链路需要
                    from backend.applications.autotest.services.autotest_data_source_crud import AutoTestDataSourceCrud
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
                                parent_step_instance=new_step_instance,
                                case_cache=case_cache,
                            )
                            created_count += child_result["created_count"]
                            updated_count += child_result["updated_count"]
                            processed_step_codes[case_id].update(child_result["process_detail"].get(case_id, set()))
                            success_detail.extend(child_result.get("success_detail", []))
                else:
                    children: List[AutoTestStepTreeUpdateItem] = step_data.children
                    if children:
                        child_result = await self.batch_update_or_create_steps(
                            steps_data=children,
                            parent_step_id=new_step_instance.id,
                            parent_step_instance=new_step_instance,
                            case_cache=case_cache,
                        )
                        created_count += child_result["created_count"]
                        updated_count += child_result["updated_count"]
                        processed_step_codes[case_id].update(child_result["process_detail"].get(case_id, set()))
                        success_detail.extend(child_result.get("success_detail", []))

            # 步骤存在，执行更新
            else:
                update_dict = step_data.model_dump(
                    exclude_none=True,
                    exclude_unset=True,
                    exclude={"id", "case", "children", "quote_steps", "quote_case", "step_code", "branch_items"},
                )
                self.explicit_restored_null_fields(
                    payload=step_data,
                    update_dict=update_dict,
                    field_names=STEP_CLEARABLE_JSON_FIELDS
                )
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

                # step_no 唯一性改由整树写完后的终态校验保证，不在更新途中逐步拦截（理由同新增分支）
                if "case_id" in update_dict:
                    case_id: int = update_dict.get("case_id", step_instance.case_id)
                    case: Optional[AutoTestCaseModel] = await _get_case_cached(
                        case_cache=case_cache,
                        case_crud=case_crud,
                        case_id=case_id,
                        on_error=False,
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
                    # 目标父与递归传入的父实例一致时直接复用，避免每个子节点重复查询同一父步骤
                    if parent_step_instance is not None and parent_step_id == parent_step_instance.id:
                        parent_step = parent_step_instance
                    else:
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
                    # 防御兜底：环判定已在 while 内对同一条件提前抛错，此处理论上不可达
                    if current_parent_id == step_id:
                        continue

                if "quote_case_id" in update_dict and update_dict["quote_case_id"]:
                    quote_case_id: int = update_dict["quote_case_id"]
                    await _get_case_cached(
                        case_cache=case_cache,
                        case_crud=case_crud,
                        case_id=quote_case_id,
                        on_error=True,
                    )

                try:
                    # step_instance 已在本层定位时查得，复用实例完成更新，避免scaffold.update内部重复SELECT
                    self.fill_updated_user(update_dict)
                    updated_instance = step_instance.update_from_dict(update_dict)
                    await updated_instance.save()
                except Exception as e:
                    error_message: str = f"第{sid}步骤更新失败，步骤数据无效或暂时无法保存，请检查步骤配置后重试"
                    LOGGER.error(
                        f"{error_message}, "
                        f"关键字段: [step_id={step_id}, step_code={step_code}, "
                        f"case_id={step_instance.case_id}, step_no={step_data.step_no}]\n"
                        f"{traceback.format_exc()}"
                    )
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
                    # 收集本次提交仍存在的子步骤ID，仅淘汰其余旧子步骤；
                    # 必须先排除待更新项再删除，否则后续按 step_id 更新时会因查不到而报错
                    retained_child_ids: Set[int] = set()
                    for branch in step_data.branch_items:
                        for child in (branch.branch_children or []):
                            if getattr(child, "step_id", None):
                                retained_child_ids.add(child.step_id)
                    stale_children_qs = self.model.filter(parent_step_id=step_id)
                    # 差量淘汰：保留集之外的旧子步骤（含历史软删残留）一律物理删除
                    if retained_child_ids:
                        stale_children_qs = stale_children_qs.exclude(id__in=retained_child_ids)
                    stale_rows: List[Dict[str, Any]] = await stale_children_qs.values(
                        "id", "step_code", "case_id"
                    )
                    if stale_rows:
                        await self.model.filter(id__in=[row["id"] for row in stale_rows]).delete()
                        # 分支子步骤同属淘汰步骤：同步硬删其数据源，避免残留孤儿数据源
                        from backend.applications.autotest.services.autotest_data_source_crud import AutoTestDataSourceCrud
                        await AutoTestDataSourceCrud().delete_step_data_sources(
                            case_id=int(stale_rows[0]["case_id"] or 0),
                            step_code_list=[row["step_code"] for row in stale_rows if row["step_code"]],
                        )
                    for bi, branch in enumerate(step_data.branch_items):
                        if branch.branch_children:
                            child_result = await self.batch_update_or_create_steps(
                                steps_data=branch.branch_children,
                                parent_step_id=step_id,
                                branch_index=bi,
                                parent_step_instance=updated_instance,
                                case_cache=case_cache,
                            )
                            created_count += child_result["created_count"]
                            updated_count += child_result["updated_count"]
                            processed_step_codes[case_id].update(child_result["process_detail"].get(case_id, set()))
                            success_detail.extend(child_result.get("success_detail", []))
                else:
                    children: List[AutoTestStepTreeUpdateItem] = step_data.children
                    if children:
                        child_result = await self.batch_update_or_create_steps(
                            steps_data=children,
                            parent_step_id=step_id,
                            parent_step_instance=updated_instance,
                            case_cache=case_cache,
                        )
                        created_count += child_result["created_count"]
                        updated_count += child_result["updated_count"]
                        processed_step_codes[case_id].update(child_result["process_detail"].get(case_id, set()))
                        success_detail.extend(child_result.get("success_detail", []))

        return {
            "created_count": created_count,
            "updated_count": updated_count,
            "process_detail": processed_step_codes,
            "success_detail": success_detail
        }

    async def assert_step_no_unique(self, case_id: int) -> None:
        """
        断言同一用例下 step_no 全局唯一，重复即抛异常触发外层事务回滚。

        只统计未软删（state≠1）的步骤；整树保存过程中新增/更新可能瞬时出现重复序号
        （如节点互换 step_no），因此不在写入途中拦截，而由调用方在整树写完后调用本方法做终态校验。

        :param case_id: 用例主键ID
        :return: None
        :raises DataAlreadyExistsException: 同一用例下存在重复 step_no
        """
        step_nos: List[int] = await self.model.filter(
            case_id=case_id, state__not=1
        ).values_list("step_no", flat=True)
        seen: Set[int] = set()
        duplicates: Set[int] = set()
        for step_no in step_nos:
            if step_no in seen:
                duplicates.add(step_no)
            seen.add(step_no)
        if duplicates:
            error_message: str = f"用例(case_id={case_id})步骤序号重复, 重复的step_no={sorted(duplicates)}, 同一用例下步骤序号必须唯一"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

    async def execute_single_case(
            self,
            case_id: int,
            report_type: AutoTestReportType,
            initial_variables: Optional[List[StepVariablesBase]] = None,
            steps_execute_config: Optional[Dict[str, StepsExecuteConfigBase]] = None,
            task_code: Optional[str] = None,
            batch_code: Optional[str] = None,
            dataset_name: Optional[str] = None,
            round_no: Optional[int] = None,
            preloaded_case: Optional[AutoTestCaseModel] = None,
            preloaded_tree: Optional[AutoTestCaseStepTreeLoadResult] = None,
            inherited_variables: Optional[List[StepVariablesBase]] = None,
    ) -> Dict[str, Any]:
        """
        执行单个用例：引擎执行不持事务，报告、明细与用例状态单事务落库。

        执行流程：
        1) 取用例（可复用调用方预载实例）并推导用例级变量池传递开关；
        2) 取步骤树（可复用预载结果），步骤数为 0 直接拒绝；
        3) 聚合会话变量（见下方优先级说明）；
        4) 调引擎执行（save_report=True 仅生成报告/明细快照，执行期不落库）；
        5) 单事务写入报告与明细，并回写用例状态（failed_steps==0 即成功）与最近执行时间。

        异常行为：本方法不吞异常；执行期或落库期异常由调用方 _execute_one_case 统一兜底为失败结果。

        :param case_id: 用例主键ID
        :param report_type: 报告类型枚举
        :param initial_variables: 任务级初始变量列表，每项含key、value、desc（字典项在此边界转为StepVariablesBase）
        :param steps_execute_config: 执行配置（key 为 step_id 或 @@步骤名，DB/Redis 多操作再拼 _@@序号）
        :param task_code: 任务标识代码，可选
        :param batch_code: 批次标识代码，可选
        :param dataset_name: 参数化执行时本次数据集名称，写入报告；数据由HTTP步骤执行器内查表获取
        :param round_no: 执行轮次(外层执行次数序号, 1起)，写入报告供执行历史按轮次下钻；单次执行为空
        :param preloaded_case: 调用方已查询的用例实例，传入时跳过用例查询(多轮执行复用)
        :param preloaded_tree: 调用方已加载的步骤树数据，传入时跳过步骤树查询(多轮执行复用)
        :param inherited_variables: 变量池传递模式下上一条数据源执行后的累积变量池，合并优先级最高(后者同名覆盖)
        :return: 含 success、total_steps/success_steps/failed_steps/passed_ratio、report_code、
                 saved_to_database、case_id/case_code/case_name、session_variables、session_transfer 的字典
        :raises ParameterException: 步骤树无任何可执行步骤
        :raises NotFoundException: 用例不存在（未预载时）
        :raises DataBaseStorageException: 报告或明细落库失败（整事务回滚）
        """
        if not initial_variables or not isinstance(initial_variables, list):
            LOGGER.info(f"初始化变量[initial_variables]为空或非列表类型")
            initial_variables = []

        # 1.查询用例信息(调用方已预载时直接复用，多轮执行不重复查询)
        case_crud = AutoTestCaseCrud()
        case_instance = (
            preloaded_case if preloaded_case is not None
            else await case_crud.get_by_id(case_id=case_id, on_error=True, state__not=1)
        )
        case_dict = await case_instance.to_dict(
            include_fields={"id", "case_code", "case_name"},
            replace_fields={"id": "case_id"}
        )
        LOGGER.info(f"查询用例[id={case_id}]成功, 结果: {case_dict}")

        # 变量池传递为用例级全局设置：从用例实例推导开关，供调用方决定是否串联累积池到下一条数据源
        session_transfer_enabled: bool = getattr(
            case_instance, "session_transfer", AutoTestSessionTransfer.DISABLE
        ) == AutoTestSessionTransfer.ENABLED

        # 2.查询步骤树数据(调用方已预载时直接复用，多轮执行不重复查询)
        load: AutoTestCaseStepTreeLoadResult = (
            preloaded_tree if preloaded_tree is not None else await self.get_case_tree(case_id)
        )
        tree_data_count: Dict[str, int] = load.step_counter.model_dump()
        if load.step_counter.total_steps == 0:
            error_message: str = f"查询步骤为空, 用例[id={case_id}]没有任何可执行的根步骤"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        LOGGER.info(f"查询用例[id={case_id}]步骤树数据成功, 结果: {tree_data_count}")

        def _merge_session_variables(*parts: List[StepVariablesBase]) -> List[StepVariablesBase]:
            """按 key 合并多段会话变量，后者覆盖前者；key 为空的项直接丢弃。"""
            merged: Dict[str, StepVariablesBase] = {}
            for part in parts:
                for it in part:
                    if it.key:
                        merged[it.key] = it
            return list(merged.values())

        # 3.聚合会话变量：按用例级变量池 → 步骤树 session_variables → initial_variables → inherited_variables
        # 依次合并，inherited_variables(上一条数据源累积池)放末位，同名变量覆盖前序来源。
        # 任务侧 task_kwargs 的 initial_variables 为 JSON 字典列表，统一在此边界转 StepVariablesBase：
        # dict 项对引擎按 key 查找不可见(isinstance 过滤)，且会使变量池合并的 item.key 访问直接报错
        merge_all_variables: List[StepVariablesBase] = _merge_session_variables(
            step_variables_list_from_storage(getattr(case_instance, "session_variables", None)),
            AutoTestToolService.collect_session_variables(load.root_steps),
            step_variables_list_from_storage(initial_variables),
            list(inherited_variables or []),
        )
        LOGGER.info(f"检查用例[id={case_id}]步骤树数据规范成功, 收集会话变量成功")

        # 4.获取根步骤（仅保留 parent_step_id 为 None 的节点，避免重复执行子节点）
        root_steps: List[AutoTestStepTreeUpdateItem] = [s for s in load.root_steps if s.parent_step_id is None]
        if not root_steps:
            error_message: str = f"获取用例[id={case_id}]根步骤失败, 没有任何可执行的根步骤"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 5.执行用例（延迟落库）：执行阶段不持事务，落库阶段在同一事务内完成，
        # 保证「报告 + 明细 + 用例状态」要么全部成功要么全部失败，且全程不长时间占锁
        engine = AutoTestStepExecutionEngine(save_report=True, task_code=task_code, batch_code=batch_code)
        # save_report=True：引擎只返回 defer_create_report 与 pending_create_details 快照，不在执行期落库
        results, logs, _, statistics, engine_session_variables, defer_create_report, pending_create_details = await engine.execute_case(
            case=case_dict,
            steps=root_steps,
            initial_variables=merge_all_variables,
            steps_execute_config=steps_execute_config,
            report_type=report_type,
            dataset_name=dataset_name,
        )
        # 轮次号由调用方(批次循环)传入后补入报告快照: 引擎不感知批次轮次结构
        if defer_create_report is not None and round_no:
            defer_create_report.round_no = round_no
        async with in_transaction():
            # 报告 → 明细 → 用例状态三段同事务：任一步失败整体回滚，避免出现“有报告无明细”或状态错位
            report_instance = await AutoTestReportCrud().create_report(report_in=defer_create_report)
            await AutoTestDetailCrud().create_details(details_in=list(pending_create_details or []))
            # 用例状态取步级统计：无失败步骤即成功；最近执行时间取报告快照中的用例最晚结束时间
            case_state = statistics.get("failed_steps", 0) == 0
            case_last_time = defer_create_report.case_ed_time
            await case_crud.update_case(AutoTestCaseUpdate(
                case_id=case_id,
                case_state=case_state,
                case_last_time=case_last_time,
            ), scope=DataScope.system())
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
            # 执行后变量池(字典列表)：供变量池传递模式下串联下一条数据源；调用方消费后应剔除以免膨胀批量结果
            "session_variables": [v.model_dump() for v in (engine_session_variables or [])],
            # 用例级变量池传递开关：调用方据此决定是否将本条累积池串联给下一条数据源
            "session_transfer": session_transfer_enabled,
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

        口径：步数按轮次累加（total/success/failed），passed_ratio 按累计步数重算；
        success 直接取 case_ok（调用方对全部轮次取 AND），不在本方法内重算；
        用例标识与 report_code 取最后一轮；error 仅在无轮次结果时填充失败原因，
        有结果时置空（具体失败以各轮结果与报告为准）。

        :param case_id: 用例主键ID
        :param case_results: 多轮执行结果列表
        :param case_ok: 用例整体是否成功
        :param empty_error: 轮次结果为空时的失败原因
        :return: 聚合后的单用例结果字典（含 execute_runs 实际轮次）
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
        # 用例标识与报告号取最后一轮（同一用例各轮一致），步数则逐轮累加
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
            dataset_enabled: bool = False,
            execute_mode: Optional[AutoTestTaskExecuteMode] = None,
    ) -> Dict[str, Any]:
        """
        批量执行多个用例并汇总成功失败与明细。

        批次标识 batch_code 每次调用重新生成（时间戳-uuid），贯穿本批次所有报告与明细。
        用例间执行顺序：execute_mode=PARALLEL 时并发派发（gather 保序，results 与 case_ids 顺序一致），
        其余（为空/串行）逐个顺序执行；用例内多轮始终串行。
        汇总口径：success_cases/failed_cases 按单用例聚合结果的 success 计数（与步数无关），
        success_rate 为用例维度百分比；单用例异常已在 _execute_one_case 内兜底，不会中断整批。

        :param case_ids: 用例主键ID列表
        :param report_type: 报告类型枚举
        :param initial_variables: 初始变量列表，每项含key、value、desc
        :param steps_execute_config: 全部用例共用的执行配置
        :param cases_execute_config: 按用例覆盖的执行配置（键为 case_id 的字符串或整数形式，
                 支持 execute_count 与 steps_execute_config 两个字段，优先于 steps_execute_config）
        :param task_code: 任务标识代码，可选
        :param dataset_enabled: 任务级数据源全局开关；启用时各用例自动纳入其全部数据场景执行
        :param execute_mode: 任务执行模式(并行执行/串行执行)；为空或串行时用例间顺序执行，并行时用例间并发执行(用例内多轮仍串行)
        :return: 含 batch_code、total_cases、success_cases、failed_cases、success_rate、results 的批次汇总字典
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

        # 并行执行模式判定：StringEnum继承str，枚举与存量字符串值等价比较；为空时视为串行(历史调用兼容)
        is_parallel: bool = execute_mode == AutoTestTaskExecuteMode.PARALLEL
        if is_parallel:
            # 用例间无先后依赖时并行执行：单次并发派发全部用例，gather保序使汇总结果顺序与串行一致
            results = list(await asyncio.gather(*[
                self._execute_one_case(
                    case_id=case_id,
                    report_type=report_type,
                    initial_variables=initial_variables,
                    steps_execute_config=steps_execute_config,
                    cases_cfg_map=cases_cfg_map,
                    task_code=task_code,
                    batch_code=batch_code,
                    dataset_enabled=dataset_enabled,
                ) for case_id in case_ids
            ]))
        else:
            for case_id in case_ids:
                results.append(await self._execute_one_case(
                    case_id=case_id,
                    report_type=report_type,
                    initial_variables=initial_variables,
                    steps_execute_config=steps_execute_config,
                    cases_cfg_map=cases_cfg_map,
                    task_code=task_code,
                    batch_code=batch_code,
                    dataset_enabled=dataset_enabled,
                ))
        for result in results:
            if result.get("success"):
                success_cases += 1
            else:
                failed_cases += 1

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

    async def _execute_one_case(
            self,
            case_id: int,
            report_type: AutoTestReportType,
            initial_variables: List[StepVariablesBase],
            steps_execute_config: Optional[Dict[str, StepsExecuteConfigBase]],
            cases_cfg_map: Dict[str, Any],
            task_code: Optional[str],
            batch_code: str,
            dataset_enabled: bool,
    ) -> Dict[str, Any]:
        """
        执行单个用例的全部轮次（执行次数 × 数据场景）并聚合为统一结果。

        分支口径：
        - 存在数据场景：外层按执行次数、内层按场景执行，round_no 为执行次数序号（与执行历史“第N次执行”对齐）；
        - 无数据场景且执行次数 > 1：按执行次数逐轮执行，round_no 从 1 递增；
        - 其余：单次执行，round_no=1。
        execute_count 非法时回落 1，并裁剪到 [1, 9999]。

        用例与步骤树仅预载一次供多轮复用；单用例异常兜底为失败结果（空轮次），不中断批次内其他用例。
        用例级变量池传递开关开启时，累积范围仅限同一轮次内的多条数据源（后者同名覆盖前者），
        跨轮次重置回初始池；已串联的 session_variables 会从单轮结果中剔除，避免膨胀批量结果。

        :param case_id: 用例主键ID
        :param report_type: 报告类型枚举
        :param initial_variables: 初始变量列表，每项含key、value、desc
        :param steps_execute_config: 全部用例共用的执行配置
        :param cases_cfg_map: 按case_id的执行配置映射，优先于steps_execute_config
        :param task_code: 任务标识代码，可选
        :param batch_code: 批次标识代码
        :param dataset_enabled: 任务级数据源全局开关
        :return: 单用例聚合结果字典（含 execute_runs 实际轮次）
        """
        try:
            # 用例级配置：键兼容 str/int 两种 case_id 写法；非 dict 视为未配置
            case_cfg = (cases_cfg_map.get(str(case_id)) or cases_cfg_map.get(case_id) or {})
            if not isinstance(case_cfg, dict):
                case_cfg = {}
            # 用例级步骤配置优先；缺省（None）才回落全局配置
            per_steps_cfg = case_cfg.get("steps_execute_config")
            if per_steps_cfg is None:
                per_steps_cfg = steps_execute_config
            # 显式空字典与缺省配置都表示无覆盖，不能继续向下游传递None
            per_steps_cfg = per_steps_cfg or {}
            # dataset_enabled为任务级全局开关(独立字段)：启用时各用例自动纳入其全部数据场景(去重，保持出现顺序)
            dataset_names = await _load_case_dataset_names(case_id) if dataset_enabled else []
            if not isinstance(dataset_names, list):
                dataset_names = []
            dataset_names = [str(x) for x in dataset_names if x is not None and str(x).strip()]

            raw_exec_count = case_cfg.get("execute_count", 1)
            try:
                execute_count = int(raw_exec_count)
            except (TypeError, ValueError):
                execute_count = 1
            # 执行次数限制在 1..9999，避免非法/极端配置放大轮次
            execute_count = max(1, min(execute_count, 9999))

            # 预载用例与步骤树各一次：同一用例多轮执行(执行次数×数据场景)复用，不再每轮重复加载
            preloaded_case = await AutoTestCaseCrud().get_by_id(case_id=case_id, on_error=True, state__not=1)
            preloaded_tree = await self.get_case_tree(case_id)

            LOGGER.info(
                f"==> 执行[id={case_id}]开始: "
                f"[execute_count={execute_count}, datasets={len(dataset_names)}]"
            )
            case_results: List[Dict[str, Any]] = []
            # 下方三个分支的正常路径都至少执行一轮，empty_error 仅在异常空结果时进入汇总
            if dataset_names:
                # 总轮次 = 执行次数 × 数据源数；外层为轮次号, 与执行历史"第N次执行"下钻口径一致
                for round_no in range(1, execute_count + 1):
                    # 变量池传递按轮次重置：累积范围仅限同一轮次内的多条数据源
                    inherited_variables: List[StepVariablesBase] = []
                    for ds_name in dataset_names:
                        one = await self.execute_single_case(
                            case_id=case_id,
                            initial_variables=initial_variables,
                            steps_execute_config=per_steps_cfg,
                            report_type=report_type,
                            task_code=task_code,
                            batch_code=batch_code,
                            dataset_name=ds_name,
                            round_no=round_no,
                            preloaded_case=preloaded_case,
                            preloaded_tree=preloaded_tree,
                            inherited_variables=inherited_variables or None,
                        )
                        # 串联决策读取本条执行返回的用例级开关，避免额外查询用例表
                        inherited_variables = (
                            step_variables_list_from_storage(one.get("session_variables"))
                            if one.get("session_transfer") else []
                        )
                        # 累积池已串联给下一条数据源，剔除后避免膨胀批量执行结果
                        one.pop("session_variables", None)
                        case_results.append(one)
                        LOGGER.info(
                            f"用例[id={case_id}]第[{round_no}/{execute_count}]次执行完成: "
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
                        round_no=run_idx + 1,
                        preloaded_case=preloaded_case,
                        preloaded_tree=preloaded_tree,
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
                    round_no=1,
                    preloaded_case=preloaded_case,
                    preloaded_tree=preloaded_tree,
                ))
                empty_error = "未执行"

            case_ok = bool(case_results) and all(r.get("success") for r in case_results)
            result = self._aggregate_case_runs(
                case_id, case_results, case_ok=case_ok, empty_error=empty_error,
            )
        except Exception as e:
            error_message: str = "执行用例失败，暂时无法完成用例执行，请稍后重试"
            LOGGER.error(f"{error_message}, 关键字段: [case_id={case_id}]\n{traceback.format_exc()}")
            result = self._aggregate_case_runs(
                case_id=case_id,
                case_results=[],
                case_ok=False,
                empty_error=error_message,
            )
        LOGGER.info(f"==> 执行用例[id={case_id}]结束")
        return result
