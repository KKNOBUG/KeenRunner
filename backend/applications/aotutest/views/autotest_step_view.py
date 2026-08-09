# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_view.py
@DateTime: 2025/4/28
"""
import traceback
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Set

from fastapi import APIRouter, Body, Query, Depends
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from backend.applications.aotutest.dependencies import AutoTestApiServices, get_autotest_api_services
from backend.applications.aotutest.models.autotest_model import AutoTestApiCaseInfo
from backend.applications.aotutest.schemas.autotest_case_schema import AutoTestApiCaseUpdate
from backend.applications.aotutest.schemas.autotest_step_schema import (
    AutoTestApiStepCreate,
    AutoTestApiStepUpdate,
    AutoTestApiStepSelect,
    AutoTestBatchExecuteCases,
    AutoTestStepTreeUpdateItem,
    AutoTestStepTreeUpdateList,
    AutoTestHttpDebugRequest,
    AutoTestTcpDebugRequest,
    AutoTestStepTreeExecute,
    AutoTestPythonCodeDebugRequest,
    AutoTestRedisDebugRequest,
    StepVariablesBase,
    StepsExecuteConfigBase,
)
from backend.applications.aotutest.services.autotest_data_source_crud import delete_step_create
from backend.applications.aotutest.services.autotest_step_debug_service import StepDebugService, StepDebugException
from backend.applications.aotutest.services.autotest_step_engine import AutoTestStepExecutionEngine
from backend.applications.aotutest.services.autotest_tool_service import AutoTestToolService
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    TypeRejectException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)
from backend.core.responses import (
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    NotFoundResponse,
    DataBaseStorageResponse,
    DataAlreadyExistsResponse,
    BadReqResponse
)
from backend.enums import AutoTestReportType, AutoTestStepType

autotest_step = APIRouter()


@autotest_step.post("/create", summary="新增步骤", description="新增步骤信息")
async def create_step(
        step_in: AutoTestApiStepCreate = Body(..., description="步骤信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    新增步骤。

    :param step_in: 步骤入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.step_curd.create_step(step_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "step_id"}
        )
        return SuccessResponse(message="新增成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增步骤失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {e}")


@autotest_step.delete("/delete", summary="删除步骤", description="根据id或code删除步骤信息")
async def delete_step(
        step_id: Optional[int] = Query(None, description="步骤ID"),
        step_code: Optional[str] = Query(None, description="步骤标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code删除步骤。

    :param step_id: 步骤主键ID
    :param step_code: 步骤业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.step_curd.delete_step(step_id=step_id, step_code=step_code)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "step_id"}
        )
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code删除步骤信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@autotest_step.post("/update", summary="更新步骤", description="根据id或code更新步骤信息")
async def update_step(
        step_in: AutoTestApiStepUpdate = Body(..., description="步骤信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code更新步骤。

    :param step_in: 步骤入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.step_curd.update_step(step_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "step_id"}
        )
        return SuccessResponse(message="更新成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code更新步骤信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {e}")


@autotest_step.get("/get", summary="查询步骤", description="根据id或code查询步骤信息")
async def get_step(
        step_id: Optional[int] = Query(None, description="步骤ID"),
        step_code: Optional[str] = Query(None, description="步骤标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code查询步骤。

    :param step_id: 步骤主键ID
    :param step_code: 步骤业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if step_id:
            instance = await services.step_curd.get_by_id(step_id=step_id, on_error=True, state__not=1)
        else:
            instance = await services.step_curd.get_by_code(step_code=step_code, on_error=True, state__not=1)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "step_id"}
        )
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询步骤信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_step.post("/search", summary="查询步骤列表", description="根据条件分页查询步骤列表信息(Body)")
async def search_steps(
        step_in: AutoTestApiStepSelect = Body(..., description="查询条件"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据条件查询步骤。

    :param step_in: 步骤入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if step_in.step_id:
            q &= Q(id=step_in.step_id)
        if step_in.step_no:
            q &= Q(step_no=step_in.step_no)
        if step_in.step_name:
            q &= Q(step_name=step_in.step_name)
        if step_in.step_type:
            q &= Q(step_type=step_in.step_type.value)
        if step_in.case_id:
            q &= Q(case_id=step_in.case_id)
        if step_in.parent_step_id is not None:
            if step_in.parent_step_id == 0:
                q &= Q(parent_step_id__isnull=True)
            else:
                q &= Q(parent_step_id=step_in.parent_step_id)
        if step_in.quote_case_id:
            q &= Q(quote_case_id=step_in.quote_case_id)
        q &= Q(state=step_in.state)
        total, instances = await services.step_curd.select_steps(
            search=q,
            page=step_in.page,
            page_size=step_in.page_size,
            order=step_in.order
        )
        data = [
            await obj.to_dict(
                exclude_fields={
                    "state",
                    "created_user", "updated_user",
                    "created_time", "updated_time",
                    "reserve_1", "reserve_2", "reserve_3"
                },
                replace_fields={"id": "step_id"}
            ) for obj in instances
        ]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件分页查询步骤列表信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_step.get("/tree", summary="查询步骤树结构", description="根据用例id或code查询步骤树结构")
async def get_step_tree(
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code查询步骤树。

    :param case_id: 用例主键ID
    :param case_code: 用例业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        load = await services.step_curd.get_by_case_id(case_id=case_id, case_code=case_code)
        if load.root_steps:
            data = [s.model_dump(mode="json") for s in load.root_steps]
        elif load.case_only_when_no_steps is not None:
            data = [{"case": load.case_only_when_no_steps.model_dump(mode="json")}]
        else:
            data = []
        total = load.step_counter.total_steps
        return SuccessResponse(message="查询成功", data=data, total=total)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据用例id或code查询步骤树结构失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_step.get("/copy_tree", summary="查询步骤树结构(副本)", description="根据用例id或code查询步骤树结构(返回未保存的副本)")
async def copy_step_tree(
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    复制用例步骤树（返回未保存的副本）。

    :param case_id: 用例主键ID
    :param case_code: 用例业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if not case_id and not case_code:
            return BadReqResponse(message="参数[case_id, case_code]不允许为空")
        copy_data = await services.step_curd.get_copy_tree(case_id=case_id, case_code=case_code)
        return SuccessResponse(message="复制成功", data=copy_data)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据用例id或code查询步骤树结构(返回未保存的副本)失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"复制失败，异常描述: {str(e)}")


@autotest_step.post("/update_or_create_tree", summary="更新步骤树结构", description="更新或创建用例级步骤树结构")
async def batch_update_steps_tree(
        tree_in: AutoTestStepTreeUpdateList = Body(..., description="步骤树数据(包含case和steps)"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    更新用例级步骤树。

    :param tree_in: 步骤树入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        # 获取用例信息和步骤数据
        case_data: AutoTestApiCaseUpdate = tree_in.case
        steps_data: List[AutoTestStepTreeUpdateItem] = tree_in.steps

        # 1. 校验步骤树结构合法性
        is_valid, error_msg = AutoTestToolService.validate_step_tree_structure(steps_data)
        if not is_valid:
            error_message: str = f"步骤树结构校验失败: {error_msg}"
            LOGGER.error(error_message)
            return BadReqResponse(message=f"步骤树结构校验失败", data=error_msg)

        # 1.5 校验HTTP/TCP步骤的数据源场景列名一致性
        def _collect_http_tcp_with_ds(steps: List[AutoTestStepTreeUpdateItem]) -> List[AutoTestStepTreeUpdateItem]:
            """递归收集步骤树中拥有data_source_id的HTTP/TCP步骤。"""
            collected: List[AutoTestStepTreeUpdateItem] = []
            for s in steps:
                if s.step_type and str(s.step_type) in (str(AutoTestStepType.HTTP), str(AutoTestStepType.TCP)):
                    if s.data_source_id:
                        collected.append(s)
                if s.children:
                    collected.extend(_collect_http_tcp_with_ds(s.children))
            return collected

        http_tcp_steps = _collect_http_tcp_with_ds(steps_data)
        if http_tcp_steps:
            ds_ids = list({s.data_source_id for s in http_tcp_steps if s.data_source_id})
            ds_records = await services.data_source_curd.model.filter(
                id__in=ds_ids, state__not=1
            ).all()
            ds_map = {ds.id: ds for ds in ds_records}

            baseline_names: Optional[List[str]] = None
            baseline_step_label: Optional[str] = None
            for s in http_tcp_steps:
                ds = ds_map.get(s.data_source_id)
                if not ds:
                    continue
                current_names = ds.dataset_names if isinstance(ds.dataset_names, list) else []
                step_label = s.step_name or s.step_code or f"步骤ID:{s.step_id}"
                if baseline_names is None:
                    baseline_names = current_names
                    baseline_step_label = step_label
                elif current_names != baseline_names:
                    error_detail = (
                        f"步骤[{step_label}]的数据源场景列名与步骤[{baseline_step_label}]不一致: "
                        f"前者: {current_names}, 后者: {baseline_names}"
                    )
                    LOGGER.error(error_detail)
                    return BadReqResponse(message="数据源场景列名不一致，请先统一各步骤数据源的场景列", data=error_detail)

        try:
            # 2. 使用事务执行批量更新/新增
            async with in_transaction():
                # 2.1 处理用例信息
                cases_data: List[AutoTestApiCaseUpdate] = [case_data]
                if cases_data:
                    case_result: Dict[str, Any] = await services.case_curd.batch_update_or_create_cases(cases_data)
                    created_case_count: int = case_result['created_count']
                    updated_case_count: int = case_result['updated_count']
                    success_case_detail: List[Dict[str, Any]] = case_result['success_detail']
                    LOGGER.info(
                        f"用例处理完成："
                        f"新增用例: {created_case_count}个, "
                        f"更新用例: {updated_case_count}个, "
                        f"成功明细: {success_case_detail}"
                    )

                    # 获取处理成功的用例ID，用于关联步骤
                    if success_case_detail and len(success_case_detail) > 0:
                        successful_case: Dict[str, Any] = success_case_detail[0]
                        successful_case_id: Optional[int] = successful_case.get("case_id")
                        if successful_case_id:
                            # 递归更新步骤数据中的case_id
                            def recursive_update_case_id(
                                    steps: List[AutoTestStepTreeUpdateItem], relevant_case_id: int
                            ) -> None:
                                """
                                递归将步骤树中各节点的case_id更新为目标用例ID。

                                :param steps: 步骤列表
                                :param relevant_case_id: 目标用例ID
                                """
                                for step in steps:
                                    step.case_id = relevant_case_id
                                    if step.children:
                                        recursive_update_case_id(step.children, relevant_case_id)
                                    if step.branch_items:
                                        for branch in step.branch_items:
                                            if branch.branch_children:
                                                recursive_update_case_id(branch.branch_children, relevant_case_id)

                            recursive_update_case_id(steps_data, successful_case_id)
                # 2.2 批量更新/新增步骤信息（递归处理）
                step_result: Dict[str, Any] = await services.step_curd.batch_update_or_create_steps(steps_data)
                deleted_step_count: int = 0
                created_step_count: int = step_result['created_count']
                updated_step_count: int = step_result['updated_count']
                process_step_count: Dict[str, Set[str]] = step_result['process_detail']
                success_step_detail: List[Dict[str, Any]] = step_result['success_detail']
                # 2.3 删除多余步骤（硬删除步骤表记录，并清理关联数据源/生成记录）
                if process_step_count:
                    for case_id, step_codes in process_step_count.items():
                        actual_step_codes = await services.step_curd.model.filter(
                            case_id=case_id
                        ).values_list("step_code", flat=True)
                        missing_step_codes: Set[str] = set(actual_step_codes) - step_codes
                        if missing_step_codes:
                            deleted_step_count += len(missing_step_codes)
                            LOGGER.warning(
                                f"删除更新后多余步骤: "
                                f"步骤(case_id={case_id}, step_code__in={list(missing_step_codes)})已被硬删除"
                            )
                            await services.step_curd.model.filter(step_code__in=missing_step_codes).delete()
                            # 同步硬删除被删步骤关联的数据源与数据生成记录
                            await delete_step_create(case_id=case_id, step_code_list=list(missing_step_codes))
                # 2.4 步骤全部删除：当 steps 为空且用例已存在时，硬删除该用例下所有步骤
                elif success_case_detail and len(success_case_detail) > 0:
                    successful_case_id: Optional[int] = success_case_detail[0].get("case_id")
                    if successful_case_id:
                        step_codes = await services.step_curd.model.filter(
                            case_id=successful_case_id
                        ).values_list("step_code", flat=True)
                        deleted_step_count = len(step_codes)
                        if deleted_step_count > 0:
                            await services.step_curd.model.filter(case_id=successful_case_id).delete()
                            await delete_step_create(
                                case_id=successful_case_id,
                                step_code_list=list(step_codes),
                            )
                            LOGGER.warning(
                                f"步骤已全部删除: 用例(case_id={successful_case_id})下 "
                                f"{deleted_step_count} 个步骤已被硬删除"
                            )
                LOGGER.info(
                    f"步骤处理完成："
                    f"新增步骤: {created_step_count}个, "
                    f"更新步骤: {updated_step_count}个, "
                    f"删除步骤: {deleted_step_count}个, "
                    f"成功明细: {success_step_detail}"
                )
                # 6. 构建返回结果
                return SuccessResponse(message="更新用例及步骤树成功", data={"cases": case_result, "steps": step_result})
        except (TypeRejectException, NotFoundException, ParameterException, DataBaseStorageException, DataAlreadyExistsException):
            # 业务异常交由外层统一映射为对应 Response，此处仅触发事务回滚
            raise
        except Exception as e:
            # 事务会自动回滚
            LOGGER.error(
                f"发生未知错误，事务已回滚, "
                f"错误类型: {type(e).__name__}, "
                f"异常描述: {e}, \n"
                f"错误回溯: {traceback.format_exc()}"
            )
            raise
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except TypeRejectException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"更新或创建用例级步骤树结构失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新用例及步骤树失败，异常描述: {e}")


@autotest_step.post("/validate_tree", summary="查询步骤树结构校验结果", description="校验步骤树结构JSON合法性")
async def validate_step_tree(
        steps_in: List[AutoTestStepTreeUpdateItem] = Body(..., description="待校验的步骤树根步骤列表"),
        deep_validate: bool = Query(True, description="是否做深度校验(执行器字段+变量引用链)"),
):
    """
    校验步骤树JSON合法性。

    :param steps_in: 步骤树入参
    :param deep_validate: 是否深度校验
    :return: 统一HTTP响应
    """
    try:
        # 第2层：树结构校验
        is_valid_structure, structure_error = AutoTestToolService.validate_step_tree_structure(steps_in)

        field_errors: List[Dict[str, Any]] = []
        variable_errors: List[Dict[str, Any]] = []
        if deep_validate:
            # 第3层：执行器字段校验
            field_errors = AutoTestToolService.validate_executor_fields(steps_in)
            # 第4层：变量引用链校验
            variable_errors = AutoTestToolService.validate_variable_flow(steps_in)

        is_valid: bool = is_valid_structure and not field_errors and not variable_errors

        total_steps: int = 0
        step_types: List[str] = []
        walk: List[AutoTestStepTreeUpdateItem] = list(steps_in)
        while walk:
            node = walk.pop()
            total_steps += 1
            step_types.append(str(node.step_type) if node.step_type else "N/A")
            if node.children:
                walk.extend(node.children)
            if node.quote_steps:
                walk.extend(node.quote_steps)

        has_container: bool = any(
            str(s.step_type) in (str(AutoTestStepType.LOOP), str(AutoTestStepType.IF))
            for s in steps_in
        )

        result_data: Dict[str, Any] = {
            "is_valid": is_valid,
            "structure_errors": structure_error if not is_valid_structure else None,
            "field_errors": field_errors,
            "variable_errors": variable_errors,
            "summary": {
                "total_steps": total_steps,
                "step_types": step_types,
                "has_container": has_container,
            },
        }
        message: str = "步骤树校验通过" if is_valid else "步骤树校验未通过"
        return SuccessResponse(message=message, data=result_data)
    except Exception as e:
        LOGGER.error(f"校验步骤树异常，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"校验步骤树异常，异常描述: {e}")


@autotest_step.post("/http_debugging", summary="调试HTTP请求", description="调试HTTP请求步骤")
async def debug_http_request(
        debug_in: AutoTestHttpDebugRequest = Body(..., description="HTTP请求步骤数据"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    HTTP请求调试。

    :param debug_in: 步骤调试入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        data = await StepDebugService.debug_http(debug_in, services)
        return SuccessResponse(message="HTTP请求调试完成", data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except StepDebugException as e:
        return FailureResponse(message=e.message, data=e.data)
    except Exception as e:
        LOGGER.error(f"HTTP请求调试失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"HTTP请求调试失败，异常描述: {e}")


@autotest_step.post("/tcp_debugging", summary="调试TCP请求", description="调试TCP请求步骤")
async def debug_tcp_request(
        debug_in: AutoTestTcpDebugRequest = Body(..., description="TCP请求步骤数据"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    TCP请求调试。

    :param debug_in: 步骤调试入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        data = await StepDebugService.debug_tcp(debug_in, services)
        return SuccessResponse(message="TCP请求调试完成", data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except StepDebugException as e:
        return FailureResponse(message=e.message, data=e.data)
    except Exception as e:
        LOGGER.error(f"TCP请求调试失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"TCP请求调试失败，异常描述: {e}")


@autotest_step.post("/python_code_debugging", summary="调试Python代码请求", description="调试Python代码步骤")
async def debug_python_code(
        debug_in: AutoTestPythonCodeDebugRequest = Body(..., description="Python代码步骤数据"),
):
    """
    Python代码调试。

    :param debug_in: 步骤调试入参
    :return: 统一HTTP响应
    """
    try:
        data = await StepDebugService.debug_python(debug_in)
        return SuccessResponse(message="Python代码调试成功", data=data, total=1)
    except StepDebugException as e:
        return FailureResponse(message=e.message, data=e.data)
    except Exception as e:
        response_data = {
            "异常描述": f"【Python代码调试】异常, {e}",
            "错误类型": f"{type(e).__name__}",
            "错误时间": f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "错误回溯": f"{traceback.format_exc()}",
        }
        LOGGER.error(f"【Python代码调试】异常: {e}\n{traceback.format_exc()}")
        return FailureResponse(message="Python代码调试异常", data=response_data)


@autotest_step.post("/redis_debugging", summary="调试Redis请求", description="调试Redis请求步骤")
async def debug_redis_request(
        debug_in: AutoTestRedisDebugRequest = Body(..., description="Redis请求步骤数据"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    Redis请求调试。

    :param debug_in: 步骤调试入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        data = await StepDebugService.debug_redis(debug_in, services)
        return SuccessResponse(message="Redis请求调试完成", data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except StepDebugException as e:
        return FailureResponse(message=e.message, data=e.data)
    except Exception as e:
        LOGGER.error(f"Redis请求调试失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"Redis请求调试失败，异常描述: {e}")


@autotest_step.post("/execute_or_debugging", summary="执行步骤树结构", description="执行或调试步骤树结构")
async def execute_step_tree(
        exec_in: AutoTestStepTreeExecute = Body(..., description="步骤树数据"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    执行或调试步骤树。无steps为运行模式，有steps为调试模式。

    :param exec_in: 业务入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        case_id: int = exec_in.case_id
        steps: Optional[List[AutoTestStepTreeUpdateItem]] = exec_in.steps
        initial_variables: Optional[List[StepVariablesBase]] = exec_in.initial_variables
        steps_execute_config: Optional[Dict[str, StepsExecuteConfigBase]] = exec_in.steps_execute_config
        selected_dataset_names: Optional[List[str]] = exec_in.selected_dataset_names

        # 无 steps → 运行模式；有 steps → 调试模式
        is_run_mode = case_id is not None and (steps is None or len(steps) == 0)
        is_debug_mode = case_id is not None and steps is not None and len(steps) > 0
        if not is_run_mode and not is_debug_mode:
            return BadReqResponse(
                message="必须提供case_id参数，运行模式不传递steps，调试模式需要传递steps"
            )

        def serialize_result(r: Any) -> Dict[str, Any]:
            """递归序列化步骤执行结果（含children）。"""
            return {
                "case_id": r.case_id,
                "step_id": r.step_id,
                "step_no": r.step_no,
                "step_code": r.step_code,
                "step_name": r.step_name,
                "step_type": r.step_type.value if r.step_type else None,
                "success": r.success,
                "message": r.message,
                "error": r.error,
                "elapsed": r.elapsed,
                "extract_variables": r.extract_variables,
                "assert_validators": r.assert_validators,
                "response": r.response,
                "children": [serialize_result(c) for c in r.children],
            }

        # ========== 运行模式（本项目：同步执行已保存步骤树）==========
        if is_run_mode:
            try:
                if not selected_dataset_names:
                    batch_code: str = f"{int(datetime.now().timestamp())}-{uuid.uuid4().hex.upper()}"
                    result_data: Dict[str, Any] = await services.step_curd.execute_single_case(
                        case_id=case_id,
                        steps_execute_config=steps_execute_config,
                        initial_variables=initial_variables,
                        report_type=AutoTestReportType.SYNC_EXEC,
                        batch_code=batch_code,
                    )
                    total_steps: int = int(result_data.get("total_steps") or 0)
                    success_steps: int = int(result_data.get("success_steps") or 0)
                    failed_steps: int = int(result_data.get("failed_steps") or 0)
                    passed_ratio: float = float(result_data.get("passed_ratio") or 0.0)
                    return SuccessResponse(
                        message=(
                            f"执行完成, 共{total_steps}步骤, 成功{success_steps}步, "
                            f"失败{failed_steps}步, 步骤通过率: {passed_ratio}%"
                        ),
                        data=result_data,
                        total=1,
                    )

                # 参数化驱动：本项目按数据集同步循环执行
                details: List[Dict[str, Any]] = []
                batch_code: str = f"{int(datetime.now().timestamp())}-{uuid.uuid4().hex.upper()}"
                for dataset_name in selected_dataset_names:
                    single_data = await services.step_curd.execute_single_case(
                        case_id=case_id,
                        steps_execute_config=steps_execute_config,
                        initial_variables=initial_variables or [],
                        report_type=AutoTestReportType.SYNC_EXEC,
                        batch_code=batch_code,
                        dataset_name=dataset_name,
                    )
                    single_data["dataset_name"] = dataset_name
                    details.append(single_data)
                execute_runs: int = len(details)
                success_runs: int = sum(1 for r in details if r.get("success"))
                failed_runs: int = execute_runs - success_runs
                case_ok: bool = execute_runs > 0 and failed_runs == 0
                success_rate: float = 100.0 if case_ok else 0.0
                return SuccessResponse(
                    message=(
                        f"参数化执行完成, 共{execute_runs}次运行, 成功{success_runs}次, "
                        f"失败{failed_runs}次, 用例成功率: {success_rate}%"
                    ),
                    data={
                        "parameterized": True,
                        "batch_code": batch_code,
                        "total_cases": 1,
                        "success_cases": 1 if case_ok else 0,
                        "failed_cases": 0 if case_ok else 1,
                        "success_rate": success_rate,
                        "execute_runs": execute_runs,
                        "details": details,
                    },
                    total=execute_runs,
                )
            except NotFoundException as e:
                return NotFoundResponse(message=str(e.message))
            except ParameterException as e:
                return BadReqResponse(message=str(e.message))
            except Exception as e:
                error_message: str = (
                    f"执行步骤过程中发生异常，事务已回滚: "
                    f"用例ID: {case_id}, "
                    f"错误类型: {type(e).__name__}, "
                    f"异常描述: {e}"
                )
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                return FailureResponse(message=f"执行步骤过程中发生异常，事务已回滚: {str(e)}")

        # ========== 调试模式 ==========
        case_info: Optional[Dict[str, Any]] = None
        if steps and getattr(steps[0], "case", None) and isinstance(steps[0].case, dict):
            first_step: Dict[str, Any] = steps[0].case
            case_info = {
                "case_id": first_step.get("case_id"),
                "case_code": first_step.get("case_code"),
                "case_name": first_step.get("case_name"),
            }
        if not case_info:
            case_instance: AutoTestApiCaseInfo = await services.case_curd.get_by_id(
                case_id=case_id,
                on_error=True,
                state__not=1
            )
            case_info = {
                "case_id": case_id,
                "case_code": case_instance.case_code,
                "case_name": case_instance.case_name,
            }

        collected_session_variables: List[StepVariablesBase] = AutoTestToolService.collect_session_variables(steps)
        merged_map: Dict[str, StepVariablesBase] = {}
        for var in collected_session_variables:
            if var.key:
                merged_map[var.key] = var
        for var in (initial_variables or []):
            if var.key:
                merged_map[var.key] = var
        merged_variables: List[StepVariablesBase] = list(merged_map.values())
        all_root_steps: List[AutoTestStepTreeUpdateItem] = [step for step in steps if step.parent_step_id is None]
        if not all_root_steps:
            return BadReqResponse(message="没有可执行的根步骤")

        if selected_dataset_names:
            if len(selected_dataset_names) != 1:
                return BadReqResponse(message="调试模式下 selected_dataset_names 必须且只能选择一条数据集")
            debug_dataset_name: str = selected_dataset_names[0]
        else:
            debug_dataset_name: Optional[str] = None

        batch_code: str = f"{int(datetime.now().timestamp())}-{uuid.uuid4().hex.upper()}"
        engine = AutoTestStepExecutionEngine(save_report=True, batch_code=batch_code)
        results, logs, report_code, statistics, session_variables, defer_create_report, pending_create_details = await engine.execute_case(
            case=case_info,
            steps=all_root_steps,
            report_type=AutoTestReportType.DEBUG_EXEC,
            steps_execute_config=steps_execute_config,
            initial_variables=merged_variables,
            dataset_name=debug_dataset_name,
        )
        async with in_transaction():
            report_instance = await services.report_curd.create_report(report_in=defer_create_report)
            for detail_create in (pending_create_details or []):
                await services.detail_curd.create_detail(detail_in=detail_create)
            case_state: bool = statistics.get("failed_steps", 0) == 0
            case_last_time: str = defer_create_report.case_ed_time
            await services.case_curd.update_case(AutoTestApiCaseUpdate(
                case_id=case_id,
                case_state=case_state,
                case_last_time=case_last_time,
            ))

        final_m: Dict[str, StepVariablesBase] = {}
        for it in merged_variables:
            if it.key:
                final_m[it.key] = it
        for it in (session_variables or []):
            if isinstance(it, StepVariablesBase) and it.key:
                final_m[it.key] = it
        final_session_variables = [v.model_dump(mode="json") for v in final_m.values()]

        total_steps: int = statistics.get("total_steps", 0)
        success_steps: int = statistics.get("success_steps", 0)
        failed_steps: int = statistics.get("failed_steps", 0)
        passed_ratio: float = statistics.get("passed_ratio", 0.0)
        result_data = {
            "total_steps": total_steps,
            "failed_steps": failed_steps,
            "passed_ratio": passed_ratio,
            "success_steps": success_steps,
            "success": failed_steps == 0,
            "results": [serialize_result(r) for r in results],
            "logs": {str(k): v for k, v in logs.items()},
            "session_variables": final_session_variables,
            "saved_to_database": True,
            "batch_code": batch_code,
            "report_code": report_code or getattr(report_instance, "report_code", None),
        }
        return SuccessResponse(
            message=(
                f"调试完成, 共{total_steps}步骤, 成功{success_steps}步, "
                f"失败{failed_steps}步, 成功率: {passed_ratio}%"
            ),
            data=result_data,
            total=1,
        )
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"执行或调试步骤树失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"执行或调试步骤树失败，异常描述: {e}")


@autotest_step.post("/batch_execute", summary="执行批量用例", description="批量异步执行用例")
async def batch_execute_cases(
        batch_in: AutoTestBatchExecuteCases = Body(..., description="批量执行请求参数"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    批量执行用例。

    :param batch_in: 业务入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        case_ids = batch_in.case_ids
        initial_variables = batch_in.initial_variables or []
        if batch_in.env_name:
            LOGGER.warning(
                f"批量执行入参[env_name={batch_in.env_name}]暂未接入执行引擎, "
                f"请通过步骤执行配置steps_execute_config指定环境"
            )

        exec_result = await services.step_curd.batch_execute_cases(
            case_ids=case_ids,
            initial_variables=initial_variables,
            report_type=AutoTestReportType.ASYNC_EXEC,
        )
        LOGGER.info(f"批量执行用例任务挂载成功, case_ids={case_ids}")
        return SuccessResponse(message="任务挂载成功, 请稍候至报告中心查看结果", data=exec_result)
    except Exception as e:
        LOGGER.error(f"批量执行用例失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"批量执行失败，异常描述: {e}")
