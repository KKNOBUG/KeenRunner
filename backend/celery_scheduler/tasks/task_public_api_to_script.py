# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : task_public_api_to_script.py
@DateTime: 2026/9/16
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from tortoise.transactions import in_transaction

from backend.applications.autotest.dependencies import AutoTestServices, get_autotest_api_services
from backend.applications.autotest.schemas.autotest_case_schema import AutoTestCaseUpdate
from backend.applications.autotest.schemas.autotest_step_schema import (
    AutoTestStepTreeUpdateItem,
    AutoTestStepTreeUpdateList,
)
from backend.applications.autotest.services.autotest_tool_service import AutoTestToolService
from backend.celery_scheduler.celery_base import run_async
from backend.celery_scheduler.celery_worker import celery
from backend.configure import LOGGER
from backend.enums import AutoTestCaseType, AutoTestStepType
from backend.services.ctx import CTX_USERNAME

# 生成脚本沿用源接口的表头字段白名单：执行快照字段(case_state/case_last_time/case_version)与
# 归属字段(owner_user)不复制，新脚本以全新状态落库；case_steps为结构计数随整树副本沿用
# (前端保存链路始终提交case_steps=totalSteps，后端树保存不重算，缺失会导致列表步骤数显示为0)
CASE_COPY_HEADER_KEYS: tuple = ("case_desc", "session_variables", "case_steps")
# 名称追加时间戳后缀的预留长度：毫秒级时间戳格式YYYYMMDDHHMMSSfff共17字符+分隔符1字符
NAME_TIMESTAMP_SUFFIX_LENGTH: int = 21
# 时间戳候选名撞名重试次数：同毫秒极端撞名时重新取当前时间重试，耗尽后由落库查重兜底
# (启用态同名报失败进明细，软删同名复活覆盖，业务等价生成成功)
NAME_TIMESTAMP_RETRY_TIMES: int = 3


def _assign_step_nos(steps: List[AutoTestStepTreeUpdateItem], counter: int) -> int:
    """
    按前序遍历为步骤树补全step_no(全树连续递增，对齐前端assignStepNumbers的编号顺序)。

    get_copy_tree副本已剥离step_no，而batch_update_or_create_steps新增分支要求step_no必填；
    条件分支子步骤按branch_items分支序串联(与branch_index升序一致)，与前端保存链路保持同一顺序。

    :param steps: 当前层级的步骤树列表
    :param counter: 起始编号
    :return: 分配后的下一个可用编号
    """
    for step in steps:
        step.step_no = counter
        counter += 1
        if step.step_type == AutoTestStepType.IF and step.branch_items:
            branch_children: List[AutoTestStepTreeUpdateItem] = []
            for branch in step.branch_items:
                if branch.branch_children:
                    branch_children.extend(branch.branch_children)
            counter = _assign_step_nos(branch_children, counter)
        if step.children:
            counter = _assign_step_nos(step.children, counter)
    return counter


def _recursive_update_case_id(steps: List[AutoTestStepTreeUpdateItem], case_id: int) -> None:
    """
    递归将步骤树各节点case_id回填为新脚本用例ID(含条件分支子步骤)。

    :param steps: 根级步骤树列表
    :param case_id: 新脚本用例主键
    :return: None
    """
    for step in steps:
        step.case_id = case_id
        if step.children:
            _recursive_update_case_id(step.children, case_id)
        if step.branch_items:
            for branch in step.branch_items:
                if branch.branch_children:
                    _recursive_update_case_id(branch.branch_children, case_id)


async def _resolve_script_name(services: AutoTestServices, case_project: int, case_name: str, case_type: str) -> str:
    """
    解析生成脚本名称：脚本名称=接口名称；同应用下已有同名记录(含软删、按唯一性分组)时按「{接口名称}-{时间戳}」命名。

    查重范围必须与 AutoTestCaseCrud._get_by_owner_key 的唯一性分组一致：公共脚本与用户脚本同组，
    组内(含跨这两类)同名即视为冲突；若仍按精确单一类型查重，会漏判异类型同名脚本，
    导致返回原名后落库时被 batch_update_or_create_cases 判重失败(部分成功)。

    :param services: 自动化测试CRUD服务聚合
    :param case_project: 脚本所属应用ID
    :param case_name: 公共接口名称
    :param case_type: 目标脚本类型(用户脚本/公共脚本)
    :return: 生成脚本名称
    """
    # 与 _get_by_owner_key 保持一致的分组查重：脚本类型按整组(公共脚本+用户脚本)比对，其余类型按精确类型
    script_group = (AutoTestCaseType.PUBLIC_SCRIPT.value, AutoTestCaseType.PRIVATE_SCRIPT.value)
    ct_val = getattr(case_type, "value", case_type)
    type_scope = list(script_group) if ct_val in script_group else [ct_val]
    exists = await services.case_curd.model.filter(
        case_project=case_project,
        case_type__in=type_scope,
        case_name=case_name
    ).exists()
    if not exists:
        return case_name
    # 截断基础名称为时间戳后缀预留长度，防止拼接后超长触发数据库截断异常
    base_name = case_name[: 255 - NAME_TIMESTAMP_SUFFIX_LENGTH]
    candidate = base_name
    for _ in range(NAME_TIMESTAMP_RETRY_TIMES):
        candidate = f"{base_name}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        exists_candidate = await services.case_curd.model.filter(
            case_project=case_project,
            case_name=candidate
        ).exists()
        if not exists_candidate:
            break
    return candidate


async def _generate_single_script(
        services: AutoTestServices,
        *,
        case_id: int,
        case_name: str,
        new_case_name: str,
        case_project: int,
        case_type: str,
        case_attr: str,
        case_tags: Optional[List[int]],
) -> Dict[str, Any]:
    """
    单接口复制生成脚本：整树副本覆盖表头后按「新增用例+整树落库」既有写路径持久化(不修改源接口)。

    :param services: 自动化测试CRUD服务聚合
    :param case_id: 公共接口用例主键
    :param case_name: 公共接口用例名称
    :param new_case_name: 生成脚本名称
    :param case_project: 脚本所属应用ID
    :param case_type: 脚本类型(用户脚本/公共脚本)
    :param case_attr: 用例属性(正案例/反案例)
    :param case_tags: 脚本所属标签
    :return: {"case_id", "case_name", "source_case_id", "source_case_name"}生成结果
    :raises NotFoundException: 源接口或步骤树查询失败
    :raises ValueError: 步骤树为空/结构校验失败/新用例ID未返回
    :raises Exception: 落库校验或存储失败(事务回滚)
    """
    copy_data = await services.step_curd.get_copy_tree(case_id=case_id)
    steps_data = copy_data.get("steps") or []
    if not steps_data:
        raise ValueError("用例无步骤，无法生成脚本")

    # 表头覆盖：身份字段置空走新增，弹窗配置覆盖类型/属性/标签/应用，其余沿用白名单
    source_case_block: Dict[str, Any] = dict(copy_data.get("case") or {})
    new_case_block: Dict[str, Any] = {key: source_case_block.get(key) for key in CASE_COPY_HEADER_KEYS}
    new_case_block.update({
        "case_id": None,
        "case_code": None,
        "case_name": new_case_name,
        "case_type": case_type,
        "case_attr": case_attr,
        "case_tags": case_tags,
        "case_project": case_project,
    })
    tree_in = AutoTestStepTreeUpdateList(
        case=AutoTestCaseUpdate.model_validate(new_case_block),
        steps=[AutoTestStepTreeUpdateItem.model_validate(step) for step in steps_data],
    )
    # 防御校验：复制源为合规公共接口，正常必然通过，此处对齐视图保存入口做结构兜底
    is_valid, error_msg = AutoTestToolService.validate_step_tree_structure(tree_in.steps)
    if not is_valid:
        raise ValueError(f"步骤树结构校验失败: {error_msg}")
    _assign_step_nos(tree_in.steps, 1)
    async with in_transaction():
        case_result = await services.case_curd.batch_update_or_create_cases([tree_in.case])
        new_case_id: Optional[int] = (case_result.get("success_detail") or [{}])[0].get("case_id")
        if not new_case_id:
            raise ValueError("脚本用例落库失败, 未获取到新用例ID")
        _recursive_update_case_id(tree_in.steps, new_case_id)
        await services.step_curd.batch_update_or_create_steps(tree_in.steps)
    LOGGER.info(
        f"【Celery-Worker】公共接口转脚本成功: "
        f"case_id={case_id}, case_name={case_name}, "
        f"new_case_id={new_case_id}, new_case_name={new_case_name}"
    )
    return {
        "case_id": case_id,
        "case_name": case_name,
        "new_case_id": new_case_id,
        "new_case_name": new_case_name,
    }


async def _generate_case_scripts_impl(
        case_ids: List[int],
        case_project: int,
        case_type: str,
        case_attr: str,
        case_tags: Optional[List[int]],
        created_user: Optional[str],
) -> Dict[str, Any]:
    """
    公共接口转脚本异步实现：逐接口复制生成为仅含当前接口的独立脚本用例。

    :param case_ids: 公共接口用例主键列表
    :param case_project: 脚本所属应用ID
    :param case_type: 脚本类型(用户脚本/公共脚本)
    :param case_attr: 用例属性(正案例/反案例)
    :param case_tags: 脚本所属标签(用户脚本必选)
    :param created_user: 提交用户账号
    :return: 批次字段total_cases/success_cases/failed_cases/success_rate(%)及生成明细
    """
    # Worker 进程无 HTTP 鉴权上下文，用提交任务时传入的用户账号埋点(owner_user/created_user)
    if created_user:
        CTX_USERNAME.set(str(created_user).strip())
    services = await get_autotest_api_services()

    created_cases: List[Dict[str, Any]] = []
    failed_details: List[Dict[str, Any]] = []
    unique_ids = list(dict.fromkeys(case_ids or []))
    for case_id in unique_ids:
        case_name = str(case_id)
        try:
            # 防御校验：视图下发后任务排队期间用例可能被删除或改类型，此处按当前库内状态复核
            case_instance = await services.case_curd.get_by_id(case_id=case_id, state__not=1)
            if not case_instance:
                failed_details.append({"case_id": case_id, "case_name": case_name, "reason": "用例不存在"})
                continue
            case_name = case_instance.case_name or case_name
            if case_instance.case_type != AutoTestCaseType.PUBLIC_API:
                failed_details.append({"case_id": case_id, "case_name": case_name, "reason": "非公共接口用例"})
                continue
            new_case_name = await _resolve_script_name(
                services=services,
                case_project=case_project,
                case_name=case_name,
                case_type=case_type
            )
            created = await _generate_single_script(
                services=services,
                case_id=case_id,
                case_name=case_name,
                new_case_name=new_case_name,
                case_project=case_project,
                case_type=case_type,
                case_attr=case_attr,
                case_tags=case_tags,
            )
            created_cases.append(created)
        except Exception as e:
            # 单接口失败仅记录明细并继续，保证其余接口正常生成(部分成功语义)
            failed_details.append({"case_id": case_id, "case_name": case_name, "reason": str(e)})
            LOGGER.error(f"【Celery-Worker】公共接口转脚本失败: case_id={case_id}, 错误类型={type(e).__name__}, 错误描述={e}")

    total_cases = len(unique_ids)
    success_cases = len(created_cases)
    return {
        "total_cases": total_cases,
        "success_cases": success_cases,
        "failed_cases": total_cases - success_cases,
        "success_rate": round(success_cases / total_cases * 100, 2) if total_cases else 0.0,
        "created_cases": created_cases,
        "failed_details": failed_details,
    }


@celery.task(name="backend.celery_scheduler.tasks.task_public_api_to_script.generate_case_scripts_task")
def generate_case_scripts_task(
        case_ids: List[int],
        case_project: int,
        case_type: str,
        case_attr: str,
        case_tags: Optional[List[int]] = None,
        created_user: Optional[str] = None,
        report_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Celery同步入口，后台将勾选的公共接口逐个复制生成为独立脚本用例。

    :param case_ids: 公共接口用例主键列表
    :param case_project: 脚本所属应用ID
    :param case_type: 脚本类型(用户脚本/公共脚本)
    :param case_attr: 用例属性(正案例/反案例)
    :param case_tags: 脚本所属标签(用户脚本必选)
    :param created_user: 提交用户账号
    :param report_type: 报告类型快照(供Worker写执行记录；任务体本身不消费)
    :return: 生成结果字典(落入task_summary)
    :raises Exception: 任务级失败时向上抛出，供Celery on_failure处理
    """
    try:
        LOGGER.info(
            f"【Celery-Worker】开始公共接口转脚本任务: 数量={len(case_ids or [])}, "
            f"case_project={case_project}, case_type={case_type}, case_attr={case_attr}, "
            f"created_user={created_user}, report_type={report_type}"
        )
        result = run_async(_generate_case_scripts_impl(
            case_ids=case_ids or [],
            case_project=case_project,
            case_type=case_type,
            case_attr=case_attr,
            case_tags=case_tags,
            created_user=created_user,
        ))
        LOGGER.info(
            f"【Celery-Worker】公共接口转脚本任务完成: total_cases={result.get('total_cases')}, "
            f"success_cases={result.get('success_cases')}, failed_cases={result.get('failed_cases')}"
        )
        return result
    except Exception as e:
        LOGGER.error(f"【Celery-Worker】公共接口转脚本任务失败: 数量={len(case_ids or [])}, 错误类型={type(e).__name__}, 错误描述={e}")
        raise
