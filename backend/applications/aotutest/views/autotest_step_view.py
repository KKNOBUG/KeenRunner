# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_view.py
@DateTime: 2025/4/28
"""
import time
import traceback
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Union
from urllib.parse import quote

import httpx
import orjson
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
    RedisOperates,
    StepVariablesBase,
    StepExtractVariableItem,
    StepAssertValidatorItem,
    StepsExecuteConfigBase,
)
from backend.applications.aotutest.services.autotest_data_source_crud import delete_step_create
from backend.applications.aotutest.services.autotest_step_engine import AutoTestStepExecutionEngine
from backend.applications.aotutest.services.autotest_tool_service import AutoTestToolService
from backend.common import AioTcpClient, TcpFrameMode, AsyncTcpUtils
from backend.common.cache.redis_connection_pool import get_app_redis_pool
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    TypeRejectException,
    DataBaseStorageException,
    DataAlreadyExistsException,
    ReqInvalidException,
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
from backend.enums import AutoTestReportType, AutoTestReqArgsType, AutoTestStepType, AutoTestConfigNodeType
from backend.services.ctx import get_current_username

autotest_step = APIRouter()


@autotest_step.post("/create", summary="新增步骤")
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
        LOGGER.info(f"新增步骤成功, 结果明细: {data}")
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
        LOGGER.info(f"根据id或code删除步骤成功, 结果明细: {data}")
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
        LOGGER.error(f"根据id或code删除步骤失败，异常描述: {e}\n{traceback.format_exc()}")
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
        LOGGER.info(f"根据id或code更新步骤成功, 结果明细: {data}")
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
        LOGGER.error(f"根据id或code更新步骤失败，异常描述: {e}\n{traceback.format_exc()}")
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
        LOGGER.info(f"根据id或code查询步骤成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询步骤失败，异常描述: {e}\n{traceback.format_exc()}")
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
        LOGGER.info(f"根据条件查询步骤成功, 结果数量: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件查询步骤失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_step.get("/tree", summary="查询步骤树", description="根据用例id或code查询步骤树")
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
        LOGGER.info(f"根据id或code查询步骤树成功, 结果明细: {load.step_counter.model_dump()}")
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
        LOGGER.error(f"根据id或code查询步骤树失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_step.get("/copy_tree", summary="复制步骤树", description="复制用例步骤树(返回未保存的副本)")
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
        LOGGER.info("复制用例步骤树成功")
        return SuccessResponse(message="复制成功", data=copy_data)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"复制用例步骤树失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"复制失败，异常描述: {str(e)}")


@autotest_step.post("/update_or_create_tree", summary="更新步骤树", description="更新或创建用例级步骤树")
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
                # 2.3 删除多余步骤
                if process_step_count:
                    for case_id, step_codes in process_step_count.items():
                        actual_step_codes = await services.step_curd.model.filter(
                            case_id=case_id, state__not=1
                        ).values_list("step_code", flat=True)
                        missing_step_codes: Set[str] = set(actual_step_codes) - step_codes
                        if missing_step_codes:
                            deleted_step_count += len(missing_step_codes)
                            LOGGER.warning(
                                f"删除更新后多余步骤: "
                                f"步骤(case_id={case_id}, step_code__in={list(missing_step_codes)})已被清理"
                            )
                            await services.step_curd.model.filter(step_code__in=missing_step_codes).delete()
                            # 同步清理被删步骤关联的数据源与数据生成记录
                            await delete_step_create(case_id=case_id, step_code_list=list(missing_step_codes))
                # 2.4 步骤全部删除：当 steps 为空且用例已存在时，软删除该用例下所有步骤
                elif success_case_detail and len(success_case_detail) > 0:
                    successful_case_id: Optional[int] = success_case_detail[0].get("case_id")
                    if successful_case_id:
                        deleted_step_count = await services.step_curd.delete_steps_recursive(
                            case_id=successful_case_id
                        )
                        if deleted_step_count > 0:
                            LOGGER.warning(f"步骤已全部删除: 用例(case_id={successful_case_id})下 {deleted_step_count} 个步骤已被软删除")
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
        LOGGER.error(f"更新用例及步骤树失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新用例及步骤树失败，异常描述: {e}")


@autotest_step.post("/validate_tree", summary="校验步骤树", description="校验步骤树JSON合法性")
async def validate_step_tree(
        steps: List[AutoTestStepTreeUpdateItem] = Body(..., description="待校验的步骤树根步骤列表"),
        deep_validate: bool = Query(True, description="是否做深度校验(执行器字段+变量引用链)"),
):
    """
    校验步骤树JSON合法性。

    :param steps: 步骤树入参
    :param deep_validate: 是否深度校验
    :return: 统一HTTP响应
    """
    try:
        # 第2层：树结构校验
        is_valid_structure, structure_error = AutoTestToolService.validate_step_tree_structure(steps)

        field_errors: List[Dict[str, Any]] = []
        variable_errors: List[Dict[str, Any]] = []
        if deep_validate:
            # 第3层：执行器字段校验
            field_errors = AutoTestToolService.validate_executor_fields(steps)
            # 第4层：变量引用链校验
            variable_errors = AutoTestToolService.validate_variable_flow(steps)

        is_valid: bool = is_valid_structure and not field_errors and not variable_errors

        # 摘要
        def _count_steps(items: List[AutoTestStepTreeUpdateItem]) -> int:
            """
            递归统计步骤树节点总数（含children/quote_steps）。

            :param items: 步骤列表
            :return: 节点总数
            """
            total: int = 0
            for s in items:
                total += 1
                total += _count_steps(s.children or [])
                total += _count_steps(s.quote_steps or [])
            return total

        step_types: List[str] = []

        def _collect_types(items: List[AutoTestStepTreeUpdateItem]) -> None:
            """
            递归收集步骤树中各节点的step_type到外层step_types。

            :param items: 步骤列表
            """
            for s in items:
                step_types.append(str(s.step_type) if s.step_type else "N/A")
                _collect_types(s.children or [])
                _collect_types(s.quote_steps or [])

        _collect_types(steps)
        has_container: bool = any(
            str(s.step_type) in (str(AutoTestStepType.LOOP), str(AutoTestStepType.IF))
            for s in steps
        )

        result_data: Dict[str, Any] = {
            "is_valid": is_valid,
            "structure_errors": structure_error if not is_valid_structure else None,
            "field_errors": field_errors,
            "variable_errors": variable_errors,
            "summary": {
                "total_steps": _count_steps(steps),
                "step_types": step_types,
                "has_container": has_container,
            },
        }
        message: str = "步骤树校验通过" if is_valid else "步骤树校验未通过"
        return SuccessResponse(message=message, data=result_data)
    except Exception as e:
        LOGGER.error(f"校验步骤树异常，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"校验步骤树异常，异常描述: {e}")


@autotest_step.post("/http_debugging", summary="调试HTTP请求")
async def debug_http_request(
        step_data: AutoTestHttpDebugRequest = Body(..., description="HTTP请求步骤数据"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    HTTP请求调试。

    :param step_data: 步骤调试入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        # 提取请求参数（使用 Pydantic 模型，自动验证）
        env_id: int = step_data.env_id
        step_name: str = step_data.step_name
        request_project_id: int = step_data.request_project_id
        request_config_name: str = step_data.request_config_name
        request_args_type: Optional[AutoTestReqArgsType] = step_data.request_args_type

        request_url: str = step_data.request_url.lstrip("/")
        request_method: str = (step_data.request_method or "GET").upper()
        request_header: Optional[List[Dict[str, Any]]] = step_data.request_header
        request_params: Optional[List[Dict[str, Any]]] = step_data.request_params
        request_form_data: Optional[List[Dict[str, Any]]] = step_data.request_form_data
        request_form_file: Optional[List[Dict[str, Any]]] = step_data.request_form_file
        request_form_urlencoded: Optional[List[Dict[str, Any]]] = step_data.request_form_urlencoded
        request_body: Optional[Dict[str, Any]] = step_data.request_body
        request_text: Optional[str] = step_data.request_text

        session_variables: List[StepVariablesBase] = step_data.session_variables or []
        defined_variables: List[StepVariablesBase] = step_data.defined_variables or []
        extract_variables: List[StepExtractVariableItem] = step_data.extract_variables or []
        assert_validators: List[StepAssertValidatorItem] = step_data.assert_validators or []

        # 将defined/session变量合并为查找dict（提取/断言用）及StepVariablesBase列表（占位符解析用）
        merged_all_variables: Dict[str, Any] = {}
        for item in defined_variables:
            if isinstance(item, StepVariablesBase) and item.key:
                merged_all_variables[item.key] = item.value
        for item in session_variables:
            if isinstance(item, StepVariablesBase) and item.key:
                merged_all_variables[item.key] = item.value
        initial_var_models: List[StepVariablesBase] = [
            StepVariablesBase(key=k, value=v, desc="") for k, v in merged_all_variables.items()
        ]

        # 处理请求主机域名
        if request_url and not request_url.lower().startswith("http"):
            try:
                env_config_instance = await services.env_config_curd.get_by_conditions(
                    only_one=True,
                    on_error=False,
                    state__not=1,
                    env_id=env_id,
                    project_id=request_project_id,
                    config_name=request_config_name,
                    config_type=AutoTestConfigNodeType.API
                )
                if not env_config_instance:
                    return NotFoundResponse(message=f"HTTP请求调试失败, 目标环境下[{request_config_name}]配置不存在")
                execute_env_host: str = env_config_instance.config_host.strip().rstrip("/").rstrip(":")
                execute_env_port: str = env_config_instance.config_port
                if not execute_env_host or not execute_env_port:
                    return NotFoundResponse(message=f"HTTP请求调试失败, 目标环境下[{request_config_name}]配置不完整")
                if not execute_env_port:
                    request_url = f"{execute_env_host}/{request_url}"
                else:
                    request_url = f"{execute_env_host}:{execute_env_port}/{request_url}"
            except Exception as e:
                LOGGER.error(f"HTTP请求调试失败, 异常描述: {e}\n{traceback.format_exc()}")
                return FailureResponse(message=f"HTTP请求调试失败，异常描述: {e}")

        # 记录执行日志，用于前端反馈
        debugging_logs: List[str] = []

        # 日志辅助函数：添加时间戳和步骤名称
        def append_debugging_log(message: str) -> None:
            """
            将带时间戳与步骤名的调试日志追加到debugging_logs。

            :param message: 日志内容
            """
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            debugging_logs.append(f"[{timestamp}] [{step_name}] {message}")

        append_debugging_log(
            message=f"【HTTP请求】调试开始: \n\t"
                    f"环境ID: {env_id}\n\t"
                    f"应用ID: {request_project_id}\n\t"
                    f"配置名称: {request_config_name}\n\t"
                    f"请求方法: {request_method}\n\t"
                    f"请求地址: {request_url}"
        )
        # 解析请求参数（列表格式）及request_body、request_text中的占位符
        finished_variables: List[StepVariablesBase] = AutoTestToolService.resolve_placeholders(
            value=initial_var_models,
            logger_object=append_debugging_log,
            finished_variables={}
        )
        headers_list = AutoTestToolService.resolve_placeholders(
            value=request_header,
            logger_object=append_debugging_log,
            finished_variables=finished_variables
        )
        params_list = AutoTestToolService.resolve_placeholders(
            value=request_params,
            logger_object=append_debugging_log,
            finished_variables=finished_variables
        )
        form_data_list = AutoTestToolService.resolve_placeholders(
            value=request_form_data,
            logger_object=append_debugging_log,
            finished_variables=finished_variables
        )
        urlencoded_list = AutoTestToolService.resolve_placeholders(
            value=request_form_urlencoded,
            logger_object=append_debugging_log,
            finished_variables=finished_variables
        )
        form_files_list = AutoTestToolService.resolve_placeholders(
            value=request_form_file,
            logger_object=append_debugging_log,
            finished_variables=finished_variables
        )
        if request_body is not None:
            request_body = AutoTestToolService.resolve_placeholders(
                value=request_body,
                logger_object=append_debugging_log,
                finished_variables=finished_variables
            )
        if request_text is not None:
            if request_args_type == AutoTestReqArgsType.XML:
                request_text = AutoTestToolService.resolve_xml_placeholders(
                    xml_text=request_text,
                    logger_object=append_debugging_log,
                    finished_variables=finished_variables,
                )
            else:
                request_text = AutoTestToolService.resolve_placeholders(
                    value=request_text,
                    logger_object=append_debugging_log,
                    finished_variables=finished_variables
                )

        # 将列表格式转换为字典格式（用于HTTP请求）
        headers = AutoTestToolService.convert_list_to_dict_for_http(headers_list)
        params = AutoTestToolService.convert_list_to_dict_for_http(params_list)
        form_data = AutoTestToolService.convert_list_to_dict_for_http(form_data_list)
        urlencoded = AutoTestToolService.convert_list_to_dict_for_http(urlencoded_list)
        form_files = AutoTestToolService.convert_list_to_dict_for_http(form_files_list)

        # 处理请求体
        data_payload: Optional[Any] = None
        json_payload: Optional[Any] = None
        file_payload: Optional[Any] = None
        content_payload: Optional[Any] = None
        if request_args_type is None:
            # 未配置时保持兼容：优先 raw -> form-data -> urlencoded 作为 data，若有 request_body 则作为 json
            if request_text:
                data_payload = request_text
            elif form_data or form_files:
                data_payload = form_data
                file_payload = form_files if form_files else None
            elif urlencoded:
                data_payload = urlencoded
            if request_body and not data_payload:
                json_payload = request_body
        elif request_args_type == AutoTestReqArgsType.NONE or request_args_type == AutoTestReqArgsType.PARAMS:
            # 无请求体或仅查询参数
            pass
        elif request_args_type == AutoTestReqArgsType.RAW:
            data_payload = request_text
        elif request_args_type == AutoTestReqArgsType.JSON:
            json_payload = request_body
        elif request_args_type == AutoTestReqArgsType.XML:
            content_payload = request_text
            if headers is None:
                headers = {}
            has_content_type = any(k.lower() == "content-type" for k in headers)
            if not has_content_type:
                headers["Content-Type"] = "application/xml; charset=utf-8"
        elif request_args_type == AutoTestReqArgsType.FORM_DATA:
            data_payload = form_data
            file_payload = form_files if form_files else None
        elif request_args_type == AutoTestReqArgsType.X_WWW_FORM_URLENCODED:
            data_payload = urlencoded

        # 构建请求参数
        request_kwargs = {
            "headers": headers if headers else None,
            "params": params if params else None,
        }

        if json_payload is not None:
            request_kwargs["json"] = json_payload
        elif content_payload is not None:
            request_kwargs["content"] = content_payload
        elif data_payload is not None:
            request_kwargs["data"] = data_payload
        if file_payload is not None:
            request_kwargs["files"] = file_payload

        # 过滤None值
        request_kwargs = {k: v for k, v in request_kwargs.items() if v is not None}
        raw_headers: Dict[str, Any] = request_kwargs.get("headers") or {}
        if raw_headers:
            # 对请求头中的中文进行 UTF-8 百分号编码
            encoded_headers: Dict[str, Any] = {
                key: quote(value, encoding="utf-8", safe=':/?#[]@!$&\'()*+,;=-._~%')
                if isinstance(value, str) else value for key, value in raw_headers.items()
            }
            if encoded_headers:
                # 把编码后的 headers 放回 kwargs
                request_kwargs["headers"] = encoded_headers

        # 记录开始时间
        start_time = time.time()
        # 发送HTTP请求
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            try:
                response = await client.request(
                    method=request_method,
                    url=request_url,
                    **request_kwargs
                )
            except httpx.TimeoutException:
                return FailureResponse(message="请求超时，请检查URL是否可访问或网络连接是否正常")
            except httpx.ConnectError as e:
                return FailureResponse(message=f"连接失败: {str(e)}")
            except httpx.RequestError as e:
                return FailureResponse(message=f"请求失败: {str(e)}")
            except Exception as e:
                error_message: str = (
                    f"【HTTP请求】调试异常, "
                    f"错误类型: {type(e).__name__}, "
                    f"错误描述: {e}"
                )
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                return FailureResponse(message=f"HTTP请求调试异常", data=error_message)

        # 计算耗时
        duration = int((time.time() - start_time) * 1000)  # 转换为毫秒
        append_debugging_log(
            message=f"【HTTP请求】调试完成: \n\t"
                    f"状态描述: {response.reason_phrase}\n\t"
                    f"状态代码: {response.status_code}\n\t"
                    f"响应字符: {response.encoding}\n\t"
                    f"响应版本: {response.http_version}\n\t"
                    f"响应耗时: {duration}ms"
        )

        # 解析响应数据
        response_json = None
        response_data = None
        response_text = response.text
        response_headers = dict(response.headers)
        try:
            # 尝试解析为JSON
            response_json = response.json()
            response_data = response_json
        except (ValueError, orjson.JSONDecodeError):
            response_data = response_text

        # 解析Cookies
        response_cookies = {}
        if response.cookies:
            for cookie in response.cookies.jar:
                response_cookies[cookie.name] = cookie.value

        # 计算响应大小
        response_size = len(response.content)
        size_str = f"{response_size / 1024:.2f}KB" if response_size > 1024 else f"{response_size}B"

        # 处理数据提取（使用与步骤引擎共用的工具方法）
        request_json_for_extract = json_payload if isinstance(json_payload, (dict, list)) else None
        if request_json_for_extract is None and isinstance(request_body, (dict, list)):
            request_json_for_extract = request_body
        request_text_for_extract = request_text if request_text not in (None, "") else (
            data_payload if isinstance(data_payload, str) else None
        )
        request_cookies_for_extract = AutoTestToolService.parse_cookie_header(headers)
        extract_data, extract_results = AutoTestToolService.run_extract_variables(
            extract_variables=extract_variables or [],
            response_text=response_text,
            response_json=response_json,
            response_headers=response_headers,
            response_cookies=response_cookies,
            request_text=request_text_for_extract,
            request_json=request_json_for_extract,
            request_headers=headers,
            request_cookies=request_cookies_for_extract,
            session_variables_lookup=merged_all_variables,
            log_callback=lambda message: append_debugging_log(message=message),
        )
        for extract_key, extract_value in extract_data.items():
            finished_variables.append(StepVariablesBase(key=extract_key, value=extract_value, desc=""))
        # 处理断言验证（使用与步骤引擎共用的工具方法）
        validator_results = AutoTestToolService.run_assert_validators(
            assert_validators=assert_validators or [],
            response_text=response_text,
            response_json=response_json,
            response_headers=response_headers,
            response_cookies=response_cookies,
            request_text=request_text_for_extract,
            request_json=request_json_for_extract,
            request_headers=headers,
            request_cookies=request_cookies_for_extract,
            session_variables_lookup=merged_all_variables,
            log_callback=lambda message: append_debugging_log(message=message),
            finished_variables=finished_variables,
            is_core_engine=False,
        )

        # 构建返回数据（包含处理后的请求信息，用于前端展示实际发送的报文）
        # 确定实际发送的请求体类型和内容
        actual_body_type = "none"
        actual_body = None
        if json_payload is not None:
            actual_body_type = "json"
            actual_body = json_payload
        elif content_payload is not None:
            actual_body_type = "xml"
            actual_body = content_payload
        elif data_payload is not None:
            if request_args_type == AutoTestReqArgsType.FORM_DATA:
                actual_body_type = "form-data"
            elif request_args_type == AutoTestReqArgsType.X_WWW_FORM_URLENCODED:
                actual_body_type = "x-www-form-urlencoded"
            elif request_args_type == AutoTestReqArgsType.RAW:
                actual_body_type = "text"
            else:
                actual_body_type = "form-data" if (form_data or form_files) else "x-www-form-urlencoded"
            actual_body = data_payload
        if file_payload is not None:
            actual_body = actual_body or {}
            actual_body = {**actual_body, "__files": file_payload}
        result_data = {
            "status": response.status_code,
            "headers": dict(response.headers),
            "cookies": response_cookies,
            "data": response_data,
            "duration": duration,
            "size": size_str,
            "extract_results": extract_results,
            "validator_results": validator_results,
            "logs": debugging_logs,
            "request_info": {
                "url": request_url,
                "method": request_method,
                "headers": headers or {},
                "params": params,
                "body_type": actual_body_type,
                "body": actual_body,
                "request_text": request_text
            }
        }
        LOGGER.info(f"HTTP请求调试完成: {request_method} {request_url}, 状态码: {response.status_code}, 耗时: {duration}ms")

        return SuccessResponse(message="HTTP请求调试完成", data=result_data)
    except Exception as e:
        LOGGER.error(f"HTTP请求调试失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"HTTP请求调试失败，异常描述: {e}")


@autotest_step.post("/tcp_debugging", summary="调试TCP请求")
async def debug_tcp_request(
        step_data: AutoTestTcpDebugRequest = Body(..., description="TCP请求步骤数据"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    TCP请求调试。

    :param step_data: 步骤调试入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        env_id: int = step_data.env_id
        step_name: str = step_data.step_name
        request_project_id: int = step_data.request_project_id
        request_config_name: str = step_data.request_config_name
        request_args_type: Optional[AutoTestReqArgsType] = step_data.request_args_type
        request_text: Optional[str] = step_data.request_text
        request_body: Any = step_data.request_body

        session_variables: List[StepVariablesBase] = step_data.session_variables or []
        defined_variables: List[StepVariablesBase] = step_data.defined_variables or []
        extract_variables: List[StepExtractVariableItem] = step_data.extract_variables or []
        assert_validators: List[StepAssertValidatorItem] = step_data.assert_validators or []

        # 合并变量池（同 HTTP 调试）
        merge_all_variables: Dict[str, Any] = {}
        for item in defined_variables:
            if isinstance(item, StepVariablesBase) and item.key:
                merge_all_variables[item.key] = item.value
        for item in session_variables:
            if isinstance(item, StepVariablesBase) and item.key:
                merge_all_variables[item.key] = item.value
        initial_var_models: List[StepVariablesBase] = [
            StepVariablesBase(key=k, value=v, desc="") for k, v in merge_all_variables.items()
        ]

        # 记录执行日志，用于前端反馈
        debugging_logs: List[str] = []

        # 日志辅助函数：添加时间戳和步骤名称
        def append_debugging_log(message: str) -> None:
            """
            将带时间戳与步骤名的调试日志追加到debugging_logs。

            :param message: 日志内容
            """
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            debugging_logs.append(f"[{timestamp}] [{step_name}] {message}")

        append_debugging_log(
            message=f"TCP请求调试开始: \n\t"
                    f"环境ID: {env_id}\n\t"
                    f"应用ID: {request_project_id}\n\t"
                    f"配置名称: {request_config_name}\n\t"
                    f"请求体类型: {request_args_type}\n\t"
                    f"目标地址: 由环境配置解析(config_host/config_port)"
        )
        append_debugging_log(message="【参数替换】开始: ")

        finished_variables = AutoTestToolService.resolve_placeholders(
            value=initial_var_models,
            logger_object=append_debugging_log,
            finished_variables={}
        )
        if request_args_type == AutoTestReqArgsType.JSON:
            request_body = AutoTestToolService.resolve_placeholders(
                value=request_body,
                logger_object=append_debugging_log,
                finished_variables=finished_variables,
            )
        elif request_text is not None:
            if request_args_type == AutoTestReqArgsType.XML:
                request_text = AutoTestToolService.resolve_xml_placeholders(
                    xml_text=request_text,
                    logger_object=append_debugging_log,
                    finished_variables=finished_variables,
                )
            else:
                request_text = AutoTestToolService.resolve_placeholders(
                    value=request_text,
                    logger_object=append_debugging_log,
                    finished_variables=finished_variables
                )
        append_debugging_log(message="【参数替换】结束")

        # 根据env_id + 应用 + 配置名解析host/port（与 HTTP 调试一致，不使用 request_url/request_port）
        host: str = ""
        port: Optional[str] = None
        try:
            env_config_instance = await services.env_config_curd.get_by_conditions(
                only_one=True,
                on_error=False,
                state__not=1,
                env_id=env_id,
                project_id=request_project_id,
                config_name=request_config_name,
                config_type=AutoTestConfigNodeType.API
            )
            if not env_config_instance:
                msg = f"TCP请求调试失败, 环境配置[{request_config_name}]不存在"
                append_debugging_log(message=msg)
                return NotFoundResponse(message=msg)
            host: str = (env_config_instance.config_host or "").strip().replace("http://", "").replace("https://", "")
            port: str = (env_config_instance.config_port or "").strip()
            append_debugging_log(message=f"解析请求信息(host={host}, port={port})成功")
        except Exception as e:
            error_message: str = f"解析请求信息失败, 终止调试: {e}"
            append_debugging_log(message=error_message)
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            return FailureResponse(message=error_message)

        if not host or not port:
            return FailureResponse(
                message="TCP请求调试失败, 目标服务器地址或端口未配置(请检查该环境下的API环境配置中的config_host/config_port)"
            )

        # 发送TCP请求：json 发 request_body，xml/raw 发 request_text
        if request_args_type == AutoTestReqArgsType.JSON:
            if isinstance(request_body, (dict, list)):
                payload: Any = orjson.dumps(request_body).decode("UTF-8")
            else:
                payload = request_body
        else:
            payload = request_text

        # TCP 配置（与 TcpStepExecutor 一致，不再硬编码）
        tcp_frame_mode = (step_data.tcp_frame_mode or "length_prefix_json").strip().lower()
        frame_mode = TcpFrameMode.RAW if tcp_frame_mode == "raw" else TcpFrameMode.LENGTH_PREFIX_JSON
        length_field_size = step_data.tcp_length_field_size or 8
        encoding = step_data.tcp_encoding or "utf-8"
        max_response_bytes = step_data.tcp_max_response_bytes or (10 * 1024 * 1024)
        response_type = (step_data.tcp_response_type or "text").strip().lower()

        def _to_timedelta(v: Any) -> Optional[timedelta]:
            if v is None or v == "":
                return None
            try:
                return timedelta(seconds=float(v))
            except Exception:
                return None

        connect_td = _to_timedelta(step_data.tcp_connect_timeout)
        read_td = _to_timedelta(step_data.tcp_read_timeout)

        start_time = time.time()
        async with AioTcpClient(
                timeout=read_td or timedelta(seconds=30),
                connect_timeout=connect_td,
                length_field_size=int(length_field_size),
                max_response_bytes=int(max_response_bytes),
        ) as client:
            try:
                utils: AsyncTcpUtils = await client.tcp(
                    host=host,
                    port=int(port),
                    data=payload,
                    frame_mode=frame_mode,
                    encoding=encoding,
                    connect_timeout=connect_td,
                    read_timeout=read_td,
                )
                raw_bytes = await utils.bytes_resp()
            except ReqInvalidException as e:
                LOGGER.error(f"{e.message}\n{traceback.format_exc()}")
                return FailureResponse(message="TCP请求调试异常", data=str(e.message))
            except Exception as e:
                error_message: str = (
                    f"【TCP请求调试】请求目标服务器发生未知错误,"
                    f"错误类型: {type(e).__name__},"
                    f"异常描述: {e}"
                )
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                return FailureResponse(message="TCP请求调试异常", data=error_message)

        # 解析响应：与 TcpStepExecutor 一致，根据 response_type 本地解析
        duration = int((time.time() - start_time) * 1000)
        append_debugging_log(message=f"TCP请求调试完成: 耗时: {duration}ms")
        try:
            response_text: str = raw_bytes.decode(encoding, errors="ignore")
        except Exception:
            response_text = ""
        response_json: Optional[Any] = None

        if response_type == "json":
            try:
                body_any = orjson.loads(raw_bytes) if raw_bytes else None
                response_json = body_any if isinstance(body_any, (dict, list)) else None
                if body_any is not None:
                    response_text = orjson.dumps(body_any).decode("UTF-8")
            except Exception:
                response_json = None
        elif response_type == "xml":
            try:
                if raw_bytes and raw_bytes.strip():
                    from lxml import etree
                    parser = etree.XMLParser(recover=False, remove_blank_text=True, encoding=encoding)
                    root = etree.fromstring(raw_bytes, parser=parser)
                    response_text = etree.tostring(root, encoding=str, pretty_print=True, xml_declaration=False).strip()
            except Exception:
                pass
            response_json = None
        elif response_type == "bytes":
            response_json = None
        else:  # text
            try:
                response_json = orjson.loads(response_text) if response_text and response_text.strip().startswith(("{", "[")) else None
            except Exception:
                response_json = None

        response_data: Optional[Union[str, Dict[str, Any]]] = response_json if response_json is not None else response_text

        # 变量提取 / 断言（同 HTTP 调试）
        request_json_for_extract: Optional[Union[List[Any], Dict[str, Any]]] = None
        if isinstance(request_body, (dict, list)):
            request_json_for_extract = request_body
        elif isinstance(request_text, str) and request_text.strip().startswith(("{", "[")):
            try:
                parsed_request = orjson.loads(request_text)
                if isinstance(parsed_request, (dict, list)):
                    request_json_for_extract = parsed_request
            except Exception:
                request_json_for_extract = None
        request_text_for_extract = request_text
        if request_text_for_extract in (None, "") and isinstance(request_body, (dict, list)):
            request_text_for_extract = orjson.dumps(request_body).decode("UTF-8")
        extract_data, extract_results = AutoTestToolService.run_extract_variables(
            extract_variables=extract_variables or [],
            response_text=response_text,
            response_json=response_json,
            response_headers=None,
            response_cookies=None,
            request_text=request_text_for_extract,
            request_json=request_json_for_extract,
            request_headers=None,
            request_cookies=None,
            session_variables_lookup=merge_all_variables,
            log_callback=lambda message: append_debugging_log(message=message),
        )
        for extract_key, extract_value in extract_data.items():
            finished_variables.append(StepVariablesBase(key=extract_key, value=extract_value, desc=""))
        validator_results = AutoTestToolService.run_assert_validators(
            assert_validators=assert_validators or [],
            response_text=response_text,
            response_json=response_json,
            response_headers=None,
            response_cookies=None,
            request_text=request_text_for_extract,
            request_json=request_json_for_extract,
            request_headers=None,
            request_cookies=None,
            session_variables_lookup=merge_all_variables,
            log_callback=lambda message: append_debugging_log(message=message),
            finished_variables=finished_variables,
            is_core_engine=False,
        )

        size = len(raw_bytes)
        size_str = f"{size / 1024:.2f}KB" if size > 1024 else f"{size}B"
        result_data = {
            "status": None,
            "headers": {},
            "cookies": {},
            "data": response_data,
            "duration": duration,
            "size": size_str,
            "extract_results": extract_results,
            "validator_results": validator_results,
            "logs": debugging_logs,
            "request_info": {
                "url": f"{host}:{port}",
                "method": "TCP",
                "headers": {},
                "params": {},
                "body_type": request_args_type,
                "body": payload,
            }
        }
        LOGGER.info(f"TCP请求调试完成: 耗时: {duration}ms")
        return SuccessResponse(message="TCP请求调试完成", data=result_data)
    except Exception as e:
        LOGGER.error(f"TCP请求调试失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"TCP请求调试失败，异常描述: {e}")


@autotest_step.post("/python_code_debugging", summary="调试Python代码")
async def debug_python_code(
        step_data: AutoTestPythonCodeDebugRequest = Body(..., description="Python代码步骤数据"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    Python代码调试。

    :param step_data: 步骤调试入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        # 提取请求参数
        code = step_data.code
        step_name = step_data.step_name or "代码请求(Python)调试"
        # defined_variables、session_variables 必须是列表格式
        defined_variables: List[StepVariablesBase] = step_data.defined_variables or []
        session_variables: List[StepVariablesBase] = step_data.session_variables or []
        assert_validators: List[StepAssertValidatorItem] = step_data.assert_validators or []

        # 合并变量到执行上下文（列表格式）
        # 如果存在相同的key，使用 defined_variables 中的值（优先级更高）
        merge_all_variables: Dict[str, Any] = {}
        for item in defined_variables:
            if isinstance(item, StepVariablesBase) and item.key:
                merge_all_variables[item.key] = item.value
        for item in session_variables:
            if isinstance(item, StepVariablesBase) and item.key:
                merge_all_variables[item.key] = item.value
        initial_variables: List[StepVariablesBase] = [
            StepVariablesBase(key=k, value=v, desc="") for k, v in merge_all_variables.items()
        ]
        # 创建执行上下文（使用虚拟的case_id和case_code）
        from backend.applications.aotutest.services.autotest_step_engine import StepExecutionContext, StepExecutionError, StepExecutionResult
        async with StepExecutionContext(case_id=0, case_code="DEBUG", initial_variables=initial_variables) as context:
            try:
                # 执行Python代码
                debugging_return: Dict[str, Any] = {}
                validator_result: List[Dict[str, Any]] = []
                debugging_result = StepExecutionResult(
                    case_id=0,
                    step_code="DEBUG",
                    step_id=None,
                    step_no=None,
                    step_name=step_name,
                    step_type=AutoTestStepType.PYTHON,
                    success=True
                )
                executive_namespace: Dict[str, Any] = context.clone_state()
                executive_result: Dict[str, Any] = context.run_python_code(code, namespace=executive_namespace, step_result=debugging_result)
                if assert_validators:
                    for vc in assert_validators:
                        source: str = (vc.source or "").strip().lower()
                        if source and source not in ("session_variables", "变量池"):
                            raise StepExecutionError(f"【代码请求(Python)】数据源类型 {source} 不被允许")

                    session_lookup_map: Dict[str, Any] = {}
                    session_lookup_map.update(AutoTestToolService.list_to_dict(defined_variables))
                    session_lookup_map.update(AutoTestToolService.list_to_dict(session_variables))
                    session_lookup_map.update(executive_result or {})
                    validator_result = AutoTestToolService.run_assert_validators(
                        assert_validators=assert_validators,
                        response_text=None,
                        response_json=None,
                        response_headers=None,
                        response_cookies=None,
                        session_variables_lookup=session_lookup_map,
                        log_callback=lambda msg: context.log(msg),
                        finished_variables=context,
                        is_core_engine=True,
                    )
                    assert_failed_number: int = sum(
                        1 for valid in validator_result if not valid.get("success", True)
                    )
                    if assert_failed_number > 0:
                        debugging_result = {
                            "result": executive_result,
                            "assert_validators": validator_result,
                            "error": f"【断言验证】- 共计: {assert_failed_number}个断言验证未通过, 详情见报告明细",
                        }
                        LOGGER.info(f"Python代码调试失败(断言未通过): {step_name}")
                        return FailureResponse(message="Python代码调试失败", data=debugging_result)

                debugging_return["result"] = executive_result
                debugging_return["assert_validators"] = validator_result
                LOGGER.info(f"Python代码调试成功: {step_name}")
                return SuccessResponse(message="Python代码调试成功", data=debugging_return, total=1)
            except StepExecutionError as e:
                # 构建失败响应
                debugging_return["error"] = str(e)
                LOGGER.error(f"【Python代码调试】失败, 错误回溯: {traceback.format_exc()}")
                return FailureResponse(message="Python代码调试失败", data=debugging_return)

    except Exception as e:
        response_data = {
            "异常描述": f"【Python代码调试】异常, {e}",
            "错误类型": f"{type(e).__name__}",
            "错误时间": f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "错误回溯": f"{traceback.format_exc()}",
        }
        LOGGER.error(f"【Python代码调试】异常: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"Python代码调试异常", data=response_data)


def _has_effective_redis_result(command_results: Optional[List[Any]]) -> bool:
    """
    判断 Redis 命令结果列表中是否存在有效（非空）结果。

    :param command_results: 命令返回值列表
    :return: 存在有效结果则为 True
    """
    if not command_results:
        return False
    for result in command_results:
        if result is None:
            continue
        if isinstance(result, (list, tuple, dict)) and len(result) == 0:
            continue
        if isinstance(result, str) and not str(result).strip():
            continue
        return True
    return False


@autotest_step.post("/redis_debugging", summary="调试Redis请求")
async def debug_redis_request(
        step_data: AutoTestRedisDebugRequest = Body(..., description="Redis请求步骤数据"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    Redis请求调试。

    :param step_data: 步骤调试入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        env_id: int = step_data.env_id
        step_name: str = step_data.step_name
        redis_operates: List[RedisOperates] = step_data.redis_operates or []
        redis_searched: bool = bool(step_data.redis_searched)
        session_variables: List[StepVariablesBase] = step_data.session_variables or []
        defined_variables: List[StepVariablesBase] = step_data.defined_variables or []
        extract_variables: List[StepExtractVariableItem] = step_data.extract_variables or []
        assert_validators: List[StepAssertValidatorItem] = step_data.assert_validators or []

        merge_all_variables: Dict[str, Any] = {}
        for item in defined_variables:
            if isinstance(item, StepVariablesBase) and item.key:
                merge_all_variables[item.key] = item.value
        for item in session_variables:
            if isinstance(item, StepVariablesBase) and item.key:
                merge_all_variables[item.key] = item.value
        initial_var_models: List[StepVariablesBase] = [
            StepVariablesBase(key=k, value=v, desc="") for k, v in merge_all_variables.items()
        ]

        debugging_logs: List[str] = []

        def append_debugging_log(message: str) -> None:
            """
            将带时间戳与步骤名的调试日志追加到debugging_logs。

            :param message: 日志内容
            """
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            debugging_logs.append(f"[{timestamp}] [{step_name}] {message}")

        env_instance = await services.env_enum_curd.get_by_id(env_id=env_id, on_error=False, state__not=1)
        if not env_instance:
            msg = f"Redis请求调试失败, 环境ID[{env_id}]不存在"
            append_debugging_log(message=msg)
            return NotFoundResponse(message=msg)
        env_name: str = str(env_instance.env_name or "").strip()
        if not env_name:
            return FailureResponse(message="参数[env_name]不允许为空")

        append_debugging_log(
            message=f"Redis请求调试开始: \n\t"
                    f"环境ID: {env_id}\n\t"
                    f"环境名称: {env_name}\n\t"
                    f"操作条数: {len(redis_operates)}\n\t"
                    f"查到即止: {redis_searched}"
        )
        append_debugging_log(message="【参数替换】开始: ")

        finished_variables = AutoTestToolService.resolve_placeholders(
            value=initial_var_models,
            logger_object=append_debugging_log,
            finished_variables={}
        )

        pool_manager = get_app_redis_pool()
        redis_operates_request: List[Dict[str, Any]] = []
        redis_operates_response: List[Dict[str, Any]] = []
        mark_extract_variables: List[Dict[str, Any]] = []
        start_time = time.time()

        for redis_idx, redis_operate in enumerate(redis_operates):
            operate_no: str = f"第{redis_idx + 1}条Redis配置"
            config_host: Optional[str] = None
            config_port: Optional[str] = None
            operate_name: str = redis_operate.name
            operate_expr: str = redis_operate.expr
            operate_project_id: Optional[int] = redis_operate.project_id
            operate_project_name: str = redis_operate.project_name
            operate_variable_name: str = redis_operate.variable_name
            operate_config_name: str = redis_operate.config_name
            operate_database_name: str = redis_operate.database_name
            operate_desc: Optional[str] = redis_operate.desc
            operate_result_count: str = f"{operate_variable_name}_count"

            try:
                operate_expr = AutoTestToolService.resolve_placeholders(
                    value=operate_expr,
                    logger_object=append_debugging_log,
                    finished_variables=finished_variables
                )
                operate_config_name = AutoTestToolService.resolve_placeholders(
                    value=operate_config_name,
                    logger_object=append_debugging_log,
                    finished_variables=finished_variables
                )
                operate_project_name = AutoTestToolService.resolve_placeholders(
                    value=operate_project_name,
                    logger_object=append_debugging_log,
                    finished_variables=finished_variables
                )
                operate_database_name = AutoTestToolService.resolve_placeholders(
                    value=operate_database_name,
                    logger_object=append_debugging_log,
                    finished_variables=finished_variables
                )
                operate_variable_name = AutoTestToolService.resolve_placeholders(
                    value=operate_variable_name,
                    logger_object=append_debugging_log,
                    finished_variables=finished_variables
                )
                operate_result_count = f"{operate_variable_name}_count"

                if not operate_project_id and operate_project_name.strip():
                    project_instance = await services.project_curd.get_by_name(
                        operate_project_name.strip(), on_error=False
                    )
                    if not project_instance:
                        msg = f"{operate_no}：应用(project_name={operate_project_name!r})不存在"
                        append_debugging_log(message=msg)
                        return NotFoundResponse(message=msg)
                    operate_project_id = project_instance.id
                if not operate_project_id:
                    return FailureResponse(message=f"{operate_no}：参数[project_id]不允许为空")
                if not operate_config_name:
                    return FailureResponse(message=f"{operate_no}：参数[config_name]不允许为空")
                if not operate_database_name:
                    return FailureResponse(message=f"{operate_no}：参数[database_name]不允许为空")
                if not operate_expr:
                    return FailureResponse(message=f"{operate_no}：参数[expr]不允许为空")
                if not operate_variable_name:
                    return FailureResponse(message=f"{operate_no}：参数[variable_name]不允许为空")

                env_config_instance = await services.env_config_curd.get_by_conditions(
                    only_one=True,
                    on_error=False,
                    state__not=1,
                    env_id=env_id,
                    project_id=operate_project_id,
                    config_name=operate_config_name,
                    config_type=AutoTestConfigNodeType.REDIS
                )
                if not env_config_instance:
                    msg = f"{operate_no}：环境配置[{operate_config_name}]不存在"
                    append_debugging_log(message=msg)
                    return NotFoundResponse(message=msg)
                config_host = env_config_instance.config_host
                config_port = env_config_instance.config_port
                if env_config_instance.database_name:
                    operate_database_name = str(env_config_instance.database_name).strip()

                append_debugging_log(
                    message=f"{operate_no}：解析配置成功(host={config_host}, port={config_port}, db={operate_database_name})"
                )

                redis_client = await pool_manager.get_or_create_client(
                    app_id=str(operate_project_id),
                    env=env_name,
                    config_name=operate_config_name,
                    db_name=operate_database_name,
                )
                expr_executive_result: Dict[str, Any] = await pool_manager.execute_commands(
                    client=redis_client,
                    expr=operate_expr,
                )
                redis_data: Optional[List[Any]] = expr_executive_result.get("redis_data")
                redis_count: Optional[int] = expr_executive_result.get("redis_count")

                mark_extract_variables.append({
                    "index": redis_idx,
                    "name": operate_variable_name,
                    "source": "Redis请求",
                    "scope": "ALL",
                    "expr": "Redis命令",
                    "extract_value": redis_data,
                    "success": True,
                    "error": "",
                })
                mark_extract_variables.append({
                    "index": redis_idx,
                    "name": operate_result_count,
                    "source": "Redis请求",
                    "scope": "ALL",
                    "expr": "Redis命令",
                    "extract_value": redis_count,
                    "success": True,
                    "error": "",
                })
                append_debugging_log(
                    message=f"{operate_no}：已自动写入变量池 variable_name={operate_variable_name}, "
                            f"{operate_result_count}={redis_count}"
                )

                redis_operates_request.append({
                    "index": redis_idx,
                    "name": operate_name,
                    "env_name": env_name,
                    "expr": operate_expr,
                    "project_id": operate_project_id,
                    "project_name": operate_project_name,
                    "variable_name": [operate_variable_name, operate_result_count],
                    "config_name": operate_config_name,
                    "database_name": operate_database_name,
                    "desc": operate_desc,
                })
                redis_operates_response.append({
                    "index": redis_idx,
                    "name": operate_name,
                    "variable_name": [operate_variable_name, operate_result_count],
                    "redis_meta": {
                        "env_name": env_name,
                        "project_id": operate_project_id,
                        "project_name": operate_project_name,
                        "config_name": operate_config_name,
                        "database_name": operate_database_name,
                        "config_host": config_host,
                        "config_port": config_port,
                    },
                    "redis_data": redis_data,
                    "redis_count": redis_count,
                })
                append_debugging_log(message=f"{operate_no}：执行完成, 命令数={redis_count}")

                if redis_searched and _has_effective_redis_result(redis_data):
                    append_debugging_log(
                        message=f"【Redis请求】查到即止：{operate_no}已返回有效结果，已终止后续命令"
                    )
                    break
            except Exception as e:
                error_message: str = f"{operate_no}：执行失败, {e}"
                append_debugging_log(message=error_message)
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                redis_operates_request.append({
                    "index": redis_idx,
                    "name": operate_name,
                    "env_name": env_name,
                    "expr": operate_expr,
                    "project_id": operate_project_id,
                    "project_name": operate_project_name,
                    "variable_name": [operate_variable_name, operate_result_count],
                    "config_name": operate_config_name,
                    "database_name": operate_database_name,
                    "desc": operate_desc,
                })
                redis_operates_response.append({
                    "index": redis_idx,
                    "name": operate_name,
                    "variable_name": [operate_variable_name, operate_result_count],
                    "redis_meta": {
                        "env_name": env_name,
                        "project_id": operate_project_id,
                        "project_name": operate_project_name,
                        "config_name": operate_config_name,
                        "database_name": operate_database_name,
                        "config_host": config_host,
                        "config_port": config_port,
                    },
                    "redis_data": None,
                    "redis_count": None,
                    "error": error_message,
                })
                return FailureResponse(message=error_message, data={"logs": debugging_logs})

        duration = int((time.time() - start_time) * 1000)
        response_text_str = orjson.dumps(redis_operates_response, default=str).decode("UTF-8")
        append_debugging_log(message=f"Redis请求调试完成: 耗时: {duration}ms")

        for extract_item in mark_extract_variables:
            if isinstance(extract_item, dict) and extract_item.get("success") and extract_item.get("name") is not None:
                merge_all_variables[extract_item["name"]] = extract_item.get("extract_value")
                finished_variables.append(
                    StepVariablesBase(key=str(extract_item["name"]), value=extract_item.get("extract_value"), desc="")
                )

        extract_data, extract_results = AutoTestToolService.run_extract_variables(
            extract_variables=extract_variables,
            response_text=response_text_str,
            response_json=redis_operates_response,
            response_headers=None,
            response_cookies=None,
            session_variables_lookup=merge_all_variables,
            log_callback=lambda message: append_debugging_log(message=message),
        )
        extract_results = mark_extract_variables + (extract_results or [])
        for extract_key, extract_value in extract_data.items():
            finished_variables.append(StepVariablesBase(key=extract_key, value=extract_value, desc=""))
        validator_results = AutoTestToolService.run_assert_validators(
            assert_validators=assert_validators,
            response_text=response_text_str,
            response_json=redis_operates_response,
            response_headers=None,
            response_cookies=None,
            session_variables_lookup=merge_all_variables,
            log_callback=lambda message: append_debugging_log(message=message),
            finished_variables=finished_variables,
            is_core_engine=False,
        )

        size = len(response_text_str.encode("utf-8"))
        size_str = f"{size / 1024:.2f}KB" if size > 1024 else f"{size}B"
        result_data = {
            "status": None,
            "headers": {},
            "cookies": {},
            "data": redis_operates_response,
            "duration": duration,
            "size": size_str,
            "extract_results": extract_results,
            "validator_results": validator_results,
            "logs": debugging_logs,
            "request_info": {
                "request_env_name": env_name,
                "redis_operates": redis_operates_request,
                "redis_searched": redis_searched,
            }
        }
        LOGGER.info(f"Redis请求调试完成: 耗时: {duration}ms")
        return SuccessResponse(message="Redis请求调试完成", data=result_data)
    except Exception as e:
        LOGGER.error(f"Redis请求调试失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"Redis请求调试失败，异常描述: {e}")


def _serialize_for_celery_initial_variables(
        items: Optional[List[StepVariablesBase]],
) -> List[Dict[str, Any]]:
    """
    将初始变量列表序列化为Celery可传递的纯dict列表。

    :param items: StepVariablesBase或dict列表
    :return: 序列化后的变量列表
    """
    if not items:
        return []
    out: List[Dict[str, Any]] = []
    for it in items:
        if hasattr(it, "model_dump"):
            out.append(it.model_dump())
        elif isinstance(it, dict):
            out.append(it)
        else:
            out.append(dict(it))
    return out


def _serialize_for_celery_steps_execute_config(
        cfg: Optional[Dict[str, StepsExecuteConfigBase]],
) -> Optional[Dict[str, Any]]:
    """
    将步骤执行配置序列化为Celery可传递的纯dict。

    :param cfg: 步骤执行配置映射
    :return: 序列化后的配置，空则返回None
    """
    if not cfg:
        return None
    serialized: Dict[str, Any] = {}
    for key, val in cfg.items():
        if hasattr(val, "model_dump"):
            serialized[key] = val.model_dump()
        elif isinstance(val, dict):
            serialized[key] = val
        else:
            serialized[key] = val
    return serialized


@autotest_step.post("/execute_or_debugging", summary="执行步骤树", description="执行或调试步骤树")
async def execute_step_tree(
        execute_in: AutoTestStepTreeExecute = Body(..., description="步骤树数据"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    执行或调试步骤树。

    :param execute_in: 业务入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        case_id: int = execute_in.case_id
        execute_type: AutoTestReportType = execute_in.execute_type
        steps: Optional[List[AutoTestStepTreeUpdateItem]] = execute_in.steps
        initial_variables: Optional[List[StepVariablesBase]] = execute_in.initial_variables
        steps_execute_config: Optional[Dict[str, StepsExecuteConfigBase]] = execute_in.steps_execute_config
        selected_dataset_names: Optional[List[str]] = execute_in.selected_dataset_names

        if execute_type == AutoTestReportType.SYNC_EXEC:
            return SuccessResponse(message="同步执行暂未开放", data=None, total=0)

        # 序列化执行结果
        def serialize_result(r: Any) -> Dict[str, Any]:
            """
            将步骤执行结果对象递归序列化为可返回的字典。

            :param r: 单步执行结果
            :return: 序列化后的结果字典（含 children）
            """
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

        # ========== SCHEDULE_EXEC：Celery 后台执行 ==========
        if execute_type == AutoTestReportType.SCHEDULE_EXEC:
            try:
                from backend.celery_scheduler.tasks.task_execute_assign_case import execute_step_tree_task

                # 与 ASYNC_EXEC / 任务批量执行一致：同一次触发共用 batch_code，
                # 多数据源时各报告才能归为「同一次执行」。
                batch_code: str = f"{int(datetime.now().timestamp())}-{uuid.uuid4().hex.upper()}"
                celery_kwargs: Dict[str, Any] = {
                    "case_id": case_id,
                    "initial_variables": _serialize_for_celery_initial_variables(initial_variables),
                    "report_type": AutoTestReportType.SCHEDULE_EXEC.value,
                    "batch_code": batch_code,
                    "selected_dataset_names": list(selected_dataset_names or []),
                    "steps_execute_config": _serialize_for_celery_steps_execute_config(steps_execute_config),
                    "created_user": get_current_username(),
                }
                apply_async_result = execute_step_tree_task.apply_async(
                    kwargs=celery_kwargs,
                    expires=3600,
                )
                exec_result = {
                    "celery_task_id": apply_async_result.task_id,
                    "task_state": apply_async_result.state,
                    "case_id": case_id,
                    "batch_code": batch_code,
                    "execute_type": execute_type.value,
                }
                return SuccessResponse(
                    message="任务已提交后台执行, 请稍候至报告中心查看结果",
                    data=exec_result,
                    total=1,
                )
            except Exception as e:
                LOGGER.error(f"提交定时执行任务失败, case_id={case_id}, err={e}\n{traceback.format_exc()}")
                return FailureResponse(message=f"提交后台执行失败，异常描述: {e}")

        # ========== ASYNC_EXEC：运行模式（同步执行已保存步骤树）==========
        if execute_type == AutoTestReportType.ASYNC_EXEC:
            try:
                # 参数化执行：根据 selected_dataset_names 长度循环，每次将 dataset_name 传入执行逻辑；数据在 HTTP 步骤执行器内根据 case_id/step_no/step_code/dataset_name 查表获取
                if not selected_dataset_names:
                    # 普通单次执行（无选中数据集）
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

                # 参数化驱动执行（选中数据）；批次级用用例指标，details 内为各轮步骤指标
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

        # ========== DEBUG_EXEC：调试模式 ==========
        if execute_type == AutoTestReportType.DEBUG_EXEC:
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

            def merged_variables(*variables: List[StepVariablesBase]) -> List[StepVariablesBase]:
                """
                根据 key 合并多组变量，后者覆盖前者。

                :param variables: 多组 StepVariablesBase 列表
                :return: 去重合并后的变量列表
                """
                merged: Dict[str, StepVariablesBase] = {}
                builtin_merged_append = merged.__setitem__
                for variable in variables:
                    for var in variable:
                        key: str = var.key
                        key and builtin_merged_append(key, var)
                return list(merged.values())

            collected_session_variables: List[StepVariablesBase] = AutoTestToolService.collect_session_variables(steps)
            merged_variables: List[StepVariablesBase] = merged_variables(collected_session_variables, initial_variables)
            all_root_steps: List[AutoTestStepTreeUpdateItem] = [step for step in steps if step.parent_step_id is None]
            if not all_root_steps:
                return BadReqResponse(message="没有可执行的根步骤")

            # 6. 调试模式执行：选中的数据集名称必须且只能有一条，数据在 HTTP 步骤执行器内根据 case_id/step_no/step_code/dataset_name 查表获取
            if selected_dataset_names:
                if len(selected_dataset_names) != 1:
                    return BadReqResponse(message="调试模式下 selected_dataset_names 必须且只能选择一条数据集")
                debug_dataset_name: str = selected_dataset_names[0]
            else:
                debug_dataset_name: Optional[str] = None
            # 与 ASYNC_EXEC / SCHEDULE_EXEC 一致：调试落库报告写入 batch_code，供历史记录根据批次聚合
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
            # 7. 获取最终会话变量：merged_variables 与引擎返回的 session_variables（均为模型列表）根据 key 合并
            final_m: Dict[str, StepVariablesBase] = {}
            for it in merged_variables:
                if it.key:
                    final_m[it.key] = it
            for it in (session_variables or []):
                if isinstance(it, StepVariablesBase) and it.key:
                    final_m[it.key] = it
            final_session_variables = [v.model_dump(mode="json") for v in final_m.values()]

            # 8. 返回调试模式的详细结果
            total_steps: int = statistics.get("total_steps", 0)
            success_steps: int = statistics.get("success_steps", 0)
            failed_steps: int = statistics.get("failed_steps", 0)
            passed_ratio: float = statistics.get("passed_ratio", 0.0)
            result_data = {
                "total_steps": total_steps,
                "success_steps": success_steps,
                "failed_steps": failed_steps,
                "passed_ratio": passed_ratio,
                "success": failed_steps == 0,
                "results": [serialize_result(r) for r in results],
                "logs": {str(k): v for k, v in logs.items()},
                "session_variables": final_session_variables,
                "saved_to_database": True,
                "batch_code": batch_code,
                "report_code": report_code,
            }
            return SuccessResponse(
                message=(
                    f"调试完成, 共{total_steps}步骤, 成功{success_steps}步, "
                    f"失败{failed_steps}步, 步骤通过率: {passed_ratio}%"
                ),
                data=result_data,
                total=total_steps,
            )

        return BadReqResponse(message=f"不支持的执行类型: {execute_type}")
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"执行或调试步骤树失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"执行或调试步骤树失败，异常描述: {e}")


@autotest_step.post("/batch_execute", summary="批量执行用例")
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
        env_name = batch_in.env_name
        initial_variables = batch_in.initial_variables if batch_in.initial_variables is not None else []
        if not isinstance(initial_variables, list):
            initial_variables = []
        if not case_ids or len(case_ids) == 0:
            return BadReqResponse(message="参数[case_ids]不允许为空")

        # 异步执行
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
