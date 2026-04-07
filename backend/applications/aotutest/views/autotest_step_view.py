# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_view.py
@DateTime: 2025/4/28
"""

import json
import time
import traceback
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Union

import httpx
from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from backend import LOGGER
from backend.applications.aotutest.models.autotest_model import AutoTestApiEnvInfo
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
)
from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
from backend.applications.aotutest.services.autotest_detail_crud import AUTOTEST_API_DETAIL_CRUD
from backend.applications.aotutest.services.autotest_report_crud import AUTOTEST_API_REPORT_CRUD
from backend.applications.aotutest.services.autotest_step_crud import AUTOTEST_API_STEP_CRUD
from backend.applications.aotutest.services.autotest_step_engine import AutoTestStepExecutionEngine
from backend.applications.aotutest.services.autotest_tool_service import AutoTestToolService
from backend.common.request.tcp_async_utils import AioTcpClient, TcpFrameMode, AsyncTcpUtils
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    ParameterException,
    TypeRejectException,
    DataBaseStorageException,
    DataAlreadyExistsException, ReqInvalidException,
)
from backend.core.responses.http_response import (
    BadReqResponse,
    SuccessResponse,
    FailureResponse,
    NotFoundResponse,
    ParameterResponse,
    DataBaseStorageResponse,
    DataAlreadyExistsResponse,
)
from backend.enums.autotest_enum import AutoTestReportType, AutoTestReqArgsType

autotest_step = APIRouter()


@autotest_step.post("/create", summary="API自动化测试-新增步骤")
async def create_step(
        step_in: AutoTestApiStepCreate = Body(..., description="步骤信息")
):
    try:
        instance = await AUTOTEST_API_STEP_CRUD.create_step(step_in)
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
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增步骤失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败, 异常描述: {e}")


@autotest_step.delete("/delete", summary="API自动化测试-按id或code删除步骤")
async def delete_step(
        step_id: Optional[int] = Query(None, description="步骤ID"),
        step_code: Optional[str] = Query(None, description="步骤标识代码"),
):
    try:
        instance = await AUTOTEST_API_STEP_CRUD.delete_step(step_id=step_id, step_code=step_code)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "step_id"}
        )
        LOGGER.info(f"按id或code删除步骤成功, 结果明细: {data}")
        return SuccessResponse(message="删除成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code删除步骤失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@autotest_step.post("/update", summary="API自动化测试-按id或code更新步骤")
async def update_step(
        step_in: AutoTestApiStepUpdate = Body(..., description="步骤信息")
):
    try:
        instance = await AUTOTEST_API_STEP_CRUD.update_step(step_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "step_id"}
        )
        LOGGER.info(f"按id或code更新步骤成功, 结果明细: {data}")
        return SuccessResponse(message="更新成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code更新步骤失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"修改失败，异常描述: {e}")


@autotest_step.get("/get", summary="API自动化测试-按id或code查询步骤")
async def get_step(
        step_id: Optional[int] = Query(None, description="步骤ID"),
        step_code: Optional[str] = Query(None, description="步骤标识代码"),
):
    try:
        if step_id:
            instance = await AUTOTEST_API_STEP_CRUD.get_by_id(step_id=step_id, on_error=True)
        else:
            instance = await AUTOTEST_API_STEP_CRUD.get_by_code(step_code=step_code, on_error=True)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "step_id"}
        )
        LOGGER.info(f"按id或code查询步骤成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code查询步骤失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_step.post("/search", summary="API自动化测试-按条件查询步骤")
async def search_steps(
        step_in: AutoTestApiStepSelect = Body(..., description="查询条件")
):
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
        total, instances = await AUTOTEST_API_STEP_CRUD.select_steps(
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
        LOGGER.info(f"按条件查询步骤成功, 结果数量: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按条件查询步骤失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_step.get("/tree", summary="API自动化测试-按id或code查询步骤树")
async def get_step_tree(
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
):
    try:
        tree_data = await AUTOTEST_API_STEP_CRUD.get_by_case_id(case_id=case_id, case_code=case_code)
        step_counter: Dict[str, Any] = tree_data.pop(-1)
        LOGGER.info(f"按id或code查询步骤树成功, 结果明细: {step_counter}")
        return SuccessResponse(message="查询成功", data=tree_data, total=step_counter["total_steps"])
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code查询步骤树失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_step.get("/copy_tree", summary="API自动化测试-复制用例步骤树（返回未保存的副本）")
async def copy_step_tree(
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
):
    """
    复制指定用例的步骤树，返回 { case, steps }，不包含 step_id、step_code 等更新必填项。

    前端两种使用场景（同一接口，不同用法）：
    1. 用例管理「复制」：使用 case + steps，创建新用例编辑页（路由跳转），保存时按新增逻辑
    2. 步骤明细「复制指定脚本」：仅使用 steps，将步骤插入当前用例的步骤树
    """
    try:
        if not case_id and not case_code:
            return BadReqResponse(message="必须提供 case_id 或 case_code 参数")
        copy_data = await AUTOTEST_API_STEP_CRUD.get_copy_tree(case_id=case_id, case_code=case_code)
        LOGGER.info("复制用例步骤树成功")
        return SuccessResponse(message="复制成功", data=copy_data)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"复制用例步骤树失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"复制失败，异常描述: {str(e)}")


@autotest_step.post("/update_or_create_tree", summary="API自动化测试-更新用例级步骤树")
async def batch_update_steps_tree(
        data: AutoTestStepTreeUpdateList = Body(..., description="步骤树数据(包含case和steps)")
):
    """
    批量更新测试用例和步骤信息

    核心功能：
    1. 根据case_id和case_code判断是新增还是更新(如果有case_id和case_code说明存在用例，是更新动作，但是步骤中可能会存在新增)
    2. 校验步骤树结构合法性（自循环引用、结构合法性）
    3. 接收嵌套结构的步骤树数据
    4. 提取并去重测试用例信息，批量更新或新增
    5. 递归处理所有层级的步骤，批量更新或新增
    6. 验证用例信息和步骤信息的关联正确性
    7. 使用事务保证原子性（要么全部成功，要么全部回滚）

    入参格式：
    - case: 用例信息（AutoTestApiCaseUpdate格式）
    - steps: 步骤树数据（数组格式）

    返回格式：
    - 成功：返回更新成功的提示 + 影响的用例数 / 步骤数 + 详细的用例和步骤信息
    - 失败：返回失败原因
    """
    try:
        # 获取用例信息和步骤数据
        case_data: AutoTestApiCaseUpdate = data.case
        steps_data: List[AutoTestStepTreeUpdateItem] = data.steps

        # 1. 校验步骤树结构合法性
        is_valid, error_msg = AutoTestToolService.validate_step_tree_structure(steps_data)
        if not is_valid:
            error_message: str = f"步骤树结构校验失败: {error_msg}"
            LOGGER.error(error_message)
            return BadReqResponse(message=f"步骤树结构校验失败", data=error_msg)

        try:
            # 2. 使用事务执行批量更新/新增
            async with in_transaction():
                # 2.1 处理用例信息
                cases_data: List[AutoTestApiCaseUpdate] = [case_data]
                if cases_data:
                    case_result: Dict[str, Any] = await AUTOTEST_API_CASE_CRUD.batch_update_or_create_cases(cases_data)
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
                                for step in steps:
                                    step.case_id = relevant_case_id
                                    if step.children:
                                        recursive_update_case_id(step.children, relevant_case_id)

                            recursive_update_case_id(steps_data, successful_case_id)
                # 2.2 批量更新/新增步骤信息（递归处理）
                step_result: Dict[str, Any] = await AUTOTEST_API_STEP_CRUD.batch_update_or_create_steps(steps_data)
                deleted_step_count: int = 0
                created_step_count: int = step_result['created_count']
                updated_step_count: int = step_result['updated_count']
                process_step_count: Dict[str, Set] = step_result['process_detail']
                success_step_detail: List[Dict[str, Any]] = step_result['success_detail']
                # 2.3 删除多余步骤
                if process_step_count:
                    for case_id, step_codes in process_step_count.items():
                        actual_step_codes = await AUTOTEST_API_STEP_CRUD.model.filter(
                            case_id=case_id, state__not=1
                        ).values_list("step_code", flat=True)
                        missing_step_codes: set = set(actual_step_codes) - step_codes
                        if missing_step_codes:
                            deleted_step_count += len(missing_step_codes)
                            LOGGER.warning(
                                f"删除更新后多余步骤: "
                                f"步骤(case_id={case_id}, step_code__in={list(missing_step_codes)})已被清理"
                            )
                            await AUTOTEST_API_STEP_CRUD.model.filter(step_code__in=missing_step_codes).update(state=1)
                # 2.4 步骤全部删除：当 steps 为空且用例已存在时，软删除该用例下所有步骤
                elif success_case_detail and len(success_case_detail) > 0:
                    successful_case_id: Optional[int] = success_case_detail[0].get("case_id")
                    if successful_case_id:
                        deleted_step_count = await AUTOTEST_API_STEP_CRUD.delete_steps_recursive(
                            case_id=successful_case_id
                        )
                        if deleted_step_count > 0:
                            LOGGER.warning(
                                f"步骤已全部删除: 用例(case_id={successful_case_id})下 {deleted_step_count} 个步骤已被软删除"
                            )
                LOGGER.info(
                    f"步骤处理完成："
                    f"新增步骤: {created_step_count}个, "
                    f"更新步骤: {updated_step_count}个, "
                    f"删除步骤: {deleted_step_count}个, "
                    f"成功明细: {success_step_detail}"
                )
                # 6. 构建返回结果
                return SuccessResponse(
                    message="更新用例及步骤树成功",
                    data={"cases": case_result, "steps": step_result}
                )
        except (
                TypeRejectException,
                NotFoundException, ParameterException,
                DataBaseStorageException, DataAlreadyExistsException,
        ) as e:
            return FailureResponse(message=e.message)
        except Exception as e:
            # 事务会自动回滚
            LOGGER.error(
                f"发生未知错误，事务已回滚, "
                f"错误类型: {type(e).__name__}, "
                f"错误描述: {e}, \n"
                f"错误回溯: {traceback.format_exc()}"
            )
            raise
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"更新用例及步骤树异常，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新用例及步骤树异常", data=str(e))


@autotest_step.post("/http_debugging", summary="API自动化测试-HTTP请求调试")
async def debug_http_request(
        step_data: AutoTestHttpDebugRequest = Body(..., description="HTTP请求步骤数据")
):
    try:
        # 提取请求参数（使用 Pydantic 模型，自动验证）
        env_name = step_data.env_name
        step_name = step_data.step_name
        request_url = step_data.request_url.lstrip("/")
        request_method = (step_data.request_method or "GET").upper()
        request_header = step_data.request_header or []
        request_params = step_data.request_params or []
        request_form_data = step_data.request_form_data or []
        request_form_file = step_data.request_form_file or []
        request_form_urlencoded = step_data.request_form_urlencoded or []
        request_body: Optional[Dict[str, Any]] = step_data.request_body
        request_text: Optional[str] = step_data.request_text
        request_project_id: int = step_data.request_project_id
        request_args_type: Optional[AutoTestReqArgsType] = step_data.request_args_type
        session_variables: List[Dict[str, Any]] = step_data.session_variables or []
        defined_variables: List[Dict[str, Any]] = step_data.defined_variables or []
        extract_variables: List[Dict[str, Any]] = step_data.extract_variables or []
        assert_validators: List[Dict[str, Any]] = step_data.assert_validators or []

        # 确保是列表格式
        if not isinstance(request_header, list):
            request_header = []
        if not isinstance(request_params, list):
            request_params = []
        if not isinstance(request_form_data, list):
            request_form_data = []
        if not isinstance(request_form_urlencoded, list):
            request_form_urlencoded = []
        if not isinstance(request_form_file, list):
            request_form_file = []
        if not isinstance(session_variables, list):
            session_variables = []
        if not isinstance(defined_variables, list):
            defined_variables = []
        if not isinstance(extract_variables, list):
            extract_variables = []
        if not isinstance(assert_validators, list):
            assert_validators = []

        # 将列表格式的 defined_variables\session_variables 转换为字典格式（用于变量查找）
        merge_all_variables: Dict[str, Any] = {}
        for item in defined_variables:
            if isinstance(item, dict) and item.get("key"):
                merge_all_variables[item["key"]] = item
        for item in session_variables:
            if isinstance(item, dict) and item.get("key"):
                merge_all_variables[item["key"]] = item
        initial_variables = list(merge_all_variables.values())

        # 处理请求主机域名
        if request_url and not request_url.lower().startswith("http"):
            try:
                from backend.applications.aotutest.services.autotest_env_crud import AUTOTEST_API_ENV_CRUD
                env_instance: AutoTestApiEnvInfo = await AUTOTEST_API_ENV_CRUD.get_by_conditions(
                    only_one=True,
                    on_error=False,
                    conditions={"project_id": request_project_id, "env_name": env_name},
                )
                if not env_instance:
                    return FailureResponse(
                        message=f"HTTP请求调试失败, 环境(project_id={request_project_id}, env_name={env_name})配置不存在"
                    )
                execute_env_host: str = env_instance.env_host.strip().rstrip("/").rstrip(":")
                execute_env_port: int = env_instance.env_port
                if not execute_env_host or not execute_env_port:
                    return FailureResponse(
                        message=f"HTTP请求调试失败, 环境(project_id={request_project_id}, env_name={env_name})配置不正确"
                    )
                if not execute_env_port:
                    request_url = f"{execute_env_host}/{request_url}"
                else:
                    request_url = f"{execute_env_host}:{execute_env_port}/{request_url}"

            except Exception as e:
                LOGGER.error(f"HTTP请求调试失败, 异常描述: {e}\n{traceback.format_exc()}")
                return FailureResponse(f"HTTP请求调试异常, 错误描述: {e}")

        # 日志辅助函数：添加时间戳和步骤名称
        def format_log(message: str) -> str:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return f"[{timestamp}] [{step_name}] {message}"

        # 记录执行日志，用于前端反馈
        logs = [
            format_log(f"HTTP请求调试开始: \n请求方法: {request_method}\n请求地址: {request_url}"),
            format_log(f"参数替换开始: "),
        ]

        # 解析请求参数（列表格式）及 request_body、request_text 中的占位符
        finished_variables = AutoTestToolService.resolve_placeholders(initial_variables, logs.append, False, finished_variables={})
        headers_list = AutoTestToolService.resolve_placeholders(request_header, logs.append, False, finished_variables=finished_variables)
        params_list = AutoTestToolService.resolve_placeholders(request_params, logs.append, False, finished_variables=finished_variables)
        form_data_list = AutoTestToolService.resolve_placeholders(request_form_data, logs.append, False, finished_variables=finished_variables)
        urlencoded_list = AutoTestToolService.resolve_placeholders(request_form_urlencoded, logs.append, False, finished_variables=finished_variables)
        form_files_list = AutoTestToolService.resolve_placeholders(request_form_file, logs.append, False, finished_variables=finished_variables)
        if request_body is not None:
            request_body = AutoTestToolService.resolve_placeholders(request_body, logs.append, False, finished_variables=finished_variables)
        if request_text is not None:
            request_text = AutoTestToolService.resolve_placeholders(request_text, logs.append, False, finished_variables=finished_variables)

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
        elif request_args_type == AutoTestReqArgsType.FORM_DATA:
            data_payload = form_data
            file_payload = form_files if form_files else None
        elif request_args_type == AutoTestReqArgsType.X_WWW_FORM_URLENCODED:
            data_payload = urlencoded

        # 构建请求参数
        logs.append(format_log("参数替换结束"))
        request_kwargs = {
            "headers": headers if headers else None,
            "params": params if params else None,
        }

        if json_payload is not None:
            request_kwargs["json"] = json_payload
        elif data_payload is not None:
            request_kwargs["data"] = data_payload
        if file_payload is not None:
            request_kwargs["files"] = file_payload

        # 过滤None值
        request_kwargs = {k: v for k, v in request_kwargs.items() if v is not None}

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
                    f"【HTTP请求调试】请求服务器发生未知错误, "
                    f"错误类型: {type(e).__name__}, "
                    f"错误描述: {e}"
                )
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                return FailureResponse(message=f"HTTP请求调试异常", data=error_message)

        # 计算耗时
        duration = int((time.time() - start_time) * 1000)  # 转换为毫秒
        logs.append(format_log(f"HTTP请求调试完成: 状态码 {response.status_code}, 耗时 {duration}ms"))

        # 解析响应数据
        response_json = None
        response_data = None
        response_text = response.text
        response_headers = dict(response.headers)
        try:
            # 尝试解析为JSON
            response_json = response.json()
            response_data = response_json
        except (ValueError, json.JSONDecodeError):
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
        _, extract_results = AutoTestToolService.run_extract_variables(
            extract_variables=extract_variables or [],
            response_text=response_text,
            response_json=response_json,
            response_headers=response_headers,
            response_cookies=response_cookies,
            session_variables_lookup=merge_all_variables,
            log_callback=lambda msg: logs.append(format_log(msg)),
        )

        # 处理断言验证（使用与步骤引擎共用的工具方法）
        validator_results = AutoTestToolService.run_assert_validators(
            assert_validators=assert_validators or [],
            response_text=response_text,
            response_json=response_json,
            response_headers=response_headers,
            response_cookies=response_cookies,
            session_variables_lookup=merge_all_variables,
            log_callback=lambda msg: logs.append(format_log(msg)),
        )

        # 构建返回数据（包含处理后的请求信息，用于前端展示实际发送的报文）
        # 确定实际发送的请求体类型和内容
        actual_body_type = "none"
        actual_body = None
        if json_payload is not None:
            actual_body_type = "json"
            actual_body = json_payload
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
            "logs": logs,
            "request_info": {
                "url": request_url,
                "method": request_method,
                "headers": headers or {},
                "params": params,
                "body_type": actual_body_type,
                "body": actual_body
            }
        }

        LOGGER.info(f"HTTP调试请求成功: {request_method} {request_url}, 状态码: {response.status_code}, 耗时: {duration}ms")

        return SuccessResponse(message="HTTP调试请求成功", data=result_data)
    except Exception as e:
        LOGGER.error(f"HTTP请求调试失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"HTTP请求调试失败，异常描述: {e}")


@autotest_step.post("/tcp_debugging", summary="API自动化测试-TCP请求调试")
async def debug_tcp_request(
        step_data: AutoTestTcpDebugRequest = Body(..., description="TCP请求步骤数据")
):
    try:
        env_name: str = step_data.env_name
        step_name: str = step_data.step_name
        request_url: str = (step_data.request_url or "").strip()
        request_port: str = step_data.request_port
        request_text: str = step_data.request_text
        request_project_id: int = step_data.request_project_id
        # TCP 调试场景下，报文统一以字符串形式存储在 request_text 中，request_args_type 固定为 RAW
        request_args_type: Optional[AutoTestReqArgsType] = step_data.request_args_type
        session_variables: List[Dict[str, Any]] = step_data.session_variables or []
        defined_variables: List[Dict[str, Any]] = step_data.defined_variables or []
        extract_variables: List[Dict[str, Any]] = step_data.extract_variables or []
        assert_validators: List[Dict[str, Any]] = step_data.assert_validators or []

        if not isinstance(session_variables, list):
            session_variables = []
        if not isinstance(defined_variables, list):
            defined_variables = []
        if not isinstance(extract_variables, list):
            extract_variables = []
        if not isinstance(assert_validators, list):
            assert_validators = []

        # 合并变量池（同 HTTP 调试）
        merge_all_variables: Dict[str, Any] = {}
        for item in defined_variables:
            if isinstance(item, dict) and item.get("key"):
                merge_all_variables[item["key"]] = item
        for item in session_variables:
            if isinstance(item, dict) and item.get("key"):
                merge_all_variables[item["key"]] = item
        initial_variables = list(merge_all_variables.values())

        # 日志辅助函数
        def format_log(message: str) -> str:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return f"[{timestamp}] [{step_name}] {message}"

        logs = [format_log("TCP请求调试开始:"), format_log("参数替换开始:")]
        finished_variables = AutoTestToolService.resolve_placeholders(
            initial_variables, logs.append, False, finished_variables={}
        )
        if request_text is not None:
            request_text = AutoTestToolService.resolve_placeholders(
                request_text, logs.append, False, finished_variables=finished_variables
            )
        logs.append(format_log("参数替换结束"))

        # 解析 host/port（支持 host:port；若仅选应用则走环境配置）
        host: str = ""
        port: Optional[int] = None
        if request_url and ":" in request_url:
            request_parts = request_url.split(":")
            if len(request_parts) == 2 and request_parts[1].isdigit():
                host = request_parts[0].strip()
                port = int(request_parts[1])
                logs.append(format_log(f"解析请求信息(host={host}, port={port})成功"))
        if not host:
            host = request_url
        if port is None and request_port not in (None, ""):
            try:
                port = int(str(request_port).strip())
            except Exception:
                logs.append(format_log(f"解析请求信息(host={host}, port={port})失败"))
        if (not host) and env_name and request_project_id:
            try:
                from backend.applications.aotutest.services.autotest_env_crud import AUTOTEST_API_ENV_CRUD
                env_instance: AutoTestApiEnvInfo = await AUTOTEST_API_ENV_CRUD.get_by_conditions(
                    only_one=True,
                    on_error=False,
                    conditions={"project_id": request_project_id, "env_name": env_name},
                )
                if not env_instance:
                    return FailureResponse(
                        message=f"TCP请求调试失败, 环境(project_id={request_project_id}, env_name={env_name})配置不存在"
                    )
                host = (env_instance.env_host or "").strip().rstrip("/").rstrip(":")
                port = int(env_instance.env_port) if env_instance.env_port is not None else None
                logs.append(format_log(f"解析请求信息(host={host}, port={port})成功"))
            except Exception as e:
                error_message: str = f"解析请求信息(host={host}, port={port})失败, 终止调试: {e}"
                logs.append(format_log(error_message))
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                return FailureResponse(message=error_message)

        if not host or not port:
            return FailureResponse(message="TCP请求调试失败, 目标服务器地址或端口未配置(可选择应用+环境或手动输入host:port)")

        # 发送TCP请求
        payload = request_text
        start_time = time.time()
        async with AioTcpClient(timeout=timedelta(seconds=30), connect_timeout=timedelta(seconds=10)) as client:
            try:
                utils: AsyncTcpUtils = await client.tcp(
                    host=host,
                    port=int(port),
                    data=payload, frame_mode=TcpFrameMode.LENGTH_PREFIX_JSON,
                    encoding="utf-8"
                )
                raw_bytes = await utils.bytes_resp()
            except ReqInvalidException as e:
                LOGGER.error(f"{e.message}\n{traceback.format_exc()}")
                return FailureResponse(message="TCP请求调试异常", data=str(e.message))
            except Exception as e:
                error_message: str = (
                    f"【TCP请求调试】请求目标服务器发生未知错误,"
                    f"错误类型: {type(e).__name__},"
                    f"错误描述: {e}"
                )
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                return FailureResponse(message="TCP请求调试异常", data=error_message)

        # 解析响应：优先 JSON，否则当作 text
        response_json: Optional[Dict[str, Any]] = None
        duration = int((time.time() - start_time) * 1000)
        logs.append(format_log(f"TCP请求调试完成: 耗时: {duration}ms"))
        response_text: str = raw_bytes.decode("utf-8", errors="ignore")
        response_data: Optional[Union[str, Dict[str, Any]]] = response_text
        try:
            response_json = json.loads(response_text)
            response_data = response_json
        except Exception:
            LOGGER.warning(f"响应体转换JSON格式失败, 保留原样")
            response_json = None

        # 变量提取 / 断言（同 HTTP 调试）
        _, extract_results = AutoTestToolService.run_extract_variables(
            extract_variables=extract_variables or [],
            response_text=response_text,
            response_json=response_json,
            response_headers=None,
            response_cookies=None,
            session_variables_lookup=merge_all_variables,
            log_callback=lambda msg: logs.append(format_log(msg)),
        )
        validator_results = AutoTestToolService.run_assert_validators(
            assert_validators=assert_validators or [],
            response_text=response_text,
            response_json=response_json,
            response_headers=None,
            response_cookies=None,
            session_variables_lookup=merge_all_variables,
            log_callback=lambda msg: logs.append(format_log(msg)),
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
            "logs": logs,
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
        return SuccessResponse(message="TCP调试请求成功", data=result_data)
    except Exception as e:
        LOGGER.error(f"TCP请求调试失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"TCP请求调试失败，异常描述: {e}")


@autotest_step.post("/python_code_debugging", summary="API自动化测试-Python代码调试")
async def debug_python_code(
        step_data: AutoTestPythonCodeDebugRequest = Body(..., description="Python代码步骤数据")
):
    """
    调试Python代码执行接口

    功能说明：
    1. 接收前端发送的Python代码和变量配置数据
    2. 使用StepExecutionContext执行Python代码（不保存到数据库）
    3. 返回执行结果，包括提取变量、执行日志等信息

    请求参数格式：
    - step_name: 步骤名称
    - code: Python代码
    - defined_variables: 定义的变量（列表格式，每个元素包含key、value、desc，用于变量替换和代码执行上下文）
    - session_variables: 会话变量（列表格式，每个元素包含key、value、desc，用于变量替换和代码执行上下文）
    """
    try:
        # 提取请求参数
        code = step_data.code
        step_name = step_data.step_name or "执行代码请求(Python)调试"
        # defined_variables、session_variables 必须是列表格式
        defined_variables = step_data.defined_variables or []
        session_variables = step_data.session_variables or []
        if not isinstance(defined_variables, list):
            defined_variables = []
        if not isinstance(session_variables, list):
            session_variables = []

        # 合并变量到执行上下文（列表格式）
        # 如果存在相同的key，使用 defined_variables 中的值（优先级更高）
        merged_variables = {}
        for item in session_variables:
            if isinstance(item, dict) and "key" in item:
                merged_variables[item.get("key")] = item
        for item in defined_variables:
            if isinstance(item, dict) and "key" in item:
                merged_variables[item.get("key")] = item
        initial_variables = list(merged_variables.values())

        # 创建执行上下文（使用虚拟的case_id和case_code）
        from backend.applications.aotutest.services.autotest_step_engine import (
            StepExecutionContext,
            StepExecutionError
        )

        # 创建执行上下文
        async with StepExecutionContext(
                case_id=0,  # 调试模式使用虚拟ID
                case_code="DEBUG",
                initial_variables=initial_variables,
        ) as context:
            try:
                # 执行Python代码
                new_vars = context.run_python_code(code, namespace=context.clone_state())
                LOGGER.info(f"Python代码调试成功: {step_name}")
                return SuccessResponse(message="Python代码调试成功", data=new_vars, total=1)
            except StepExecutionError as e:
                # 构建失败响应
                response_data = {"error": str(e)}
                LOGGER.error(f"【Python代码调试】失败, 错误回溯: {traceback.format_exc()}")
                return SuccessResponse(message="Python代码调试失败", data=response_data, total=1)

    except Exception as e:
        response_data = {
            "错误描述": f"【Python代码调试】异常, {e}",
            "错误类型": f"{type(e).__name__}",
            "错误时间": f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "错误回溯": f"{traceback.format_exc()}",
        }
        LOGGER.error(f"【Python代码调试】异常: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"Python代码调试异常", data=response_data)


@autotest_step.post("/execute_or_debugging", summary="API自动化测试-执行或调试步骤树")
async def execute_step_tree(
        request: AutoTestStepTreeExecute = Body(..., description="步骤树数据")
):
    """
    执行步骤树（运行/调试）：
    - 运行模式：只接收case_id参数，后端基于传入的case_id，查询数据库中该用例关联的完整测试步骤树数据；
      按步骤树层级依次执行所有测试步骤，将每一步骤的执行结果（含成功/失败状态、执行日志、变量提取结果等）
      写入指定数据库表（如 AutoTestApiDetailsInfo）；注意开启数据库事务要么全部成功，要么全部失败。
      返回：执行结果汇总（如整体成功/失败、步骤执行数量）+ 数据库落库成功标识。

    - 调试模式：只接收steps参数，不接收case_id参数，无需查询数据库用例信息，直接基于传入的steps参数
      解析测试步骤树，按步骤树层级依次执行所有测试步骤；执行过程中记录每一步骤的执行结果（格式与运行模式一致），
      但不写入数据库。
      返回：完整的步骤级执行结果（含每一步的状态、日志、变量提取结果、会话变量的累积）+ 整体执行汇总。
    """
    try:
        env_name = request.env_name
        case_id = request.case_id
        steps = request.steps
        initial_variables = request.initial_variables

        # 判断运行模式还是调试模式
        # 运行模式：只传递 case_id，不传递 steps
        # 调试模式：传递 case_id 和 steps
        is_run_mode = case_id is not None and (steps is None or len(steps) == 0)
        is_debug_mode = case_id is not None and steps is not None and len(steps) > 0
        if not is_run_mode and not is_debug_mode:
            return BadReqResponse(message="必须提供case_id参数，运行模式不传递steps，调试模式需要传递steps")

        # 序列化执行结果
        def serialize_result(r: Any) -> Dict[str, Any]:
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

        # ========== 运行模式 ==========
        if is_run_mode:
            try:
                selected_dataset_names = getattr(request, "selected_dataset_names", None) or []
                # 参数化执行：根据 selected_dataset_names 长度循环，每次将 dataset_name 传入执行逻辑；数据在 HTTP 步骤执行器内按 case_id/step_no/step_code/dataset_name 查表获取
                selected_dataset_names = ["场景1名称", "场景2名称", "场景3名称"]
                if not selected_dataset_names:
                    # 普通单次执行（无选中数据集）
                    result_data = await AUTOTEST_API_STEP_CRUD.execute_single_case(
                        case_id=case_id,
                        env_name=env_name,
                        initial_variables=initial_variables,
                        report_type=AutoTestReportType.SYNC_EXEC
                    )
                    total_steps: int = result_data.get("total_steps")
                    success_steps: int = result_data.get("success_steps")
                    failed_steps: int = result_data.get("failed_steps")
                    passed_ratio: float = round((success_steps / total_steps * 100), 2) if total_steps > 0 else 0.0
                    return SuccessResponse(
                        message=f"执行完成, 共{total_steps}步骤, 成功{success_steps}步, 失败{failed_steps}步, 成功率: {passed_ratio}%",
                        data=result_data,
                        total=1
                    )

                # 参数化驱动执行（选中数据）
                parameterized_execute_results: List[Dict[str, Any]] = []
                batch_code: str = f"{int(datetime.now().timestamp())}-{uuid.uuid4().hex.upper()}"
                for dataset_name in selected_dataset_names:
                    single_data = await AUTOTEST_API_STEP_CRUD.execute_single_case(
                        case_id=case_id,
                        env_name=env_name,
                        initial_variables=initial_variables or [],
                        report_type=AutoTestReportType.SYNC_EXEC,
                        batch_code=batch_code,
                        dataset_name=dataset_name,
                    )
                    parameterized_execute_results.append(single_data)
                execute_count: int = len(parameterized_execute_results)
                success_count: int = sum(1 for r in parameterized_execute_results if r.get("success"))
                failed_count: int = execute_count - success_count
                passed_ratio: float = round((success_count / execute_count * 100), 2) if execute_count > 0 else 0.0
                return SuccessResponse(
                    message=f"参数化执行完成, 共{execute_count}次, 成功{success_count}次, 失败{failed_count}次, 成功率: {passed_ratio}%",
                    data={
                        "parameterized": True,
                        "execute_count": execute_count,
                        "success_count": success_count,
                        "failed_count": failed_count,
                        "passed_ratio": passed_ratio,
                        "details": parameterized_execute_results,
                    },
                    total=execute_count,
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
                    f"错误详情: {e}"
                )
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                return FailureResponse(message=f"执行步骤过程中发生异常，事务已回滚: {str(e)}")

        # ========== 调试模式 ==========
        else:
            # 1. 将Pydantic模型转换为字典
            steps_dict = []
            for step in steps:
                if hasattr(step, 'model_dump'):
                    steps_dict.append(step.model_dump())
                elif isinstance(step, dict):
                    steps_dict.append(step)
                else:
                    steps_dict.append(dict(step))

            tree_data = steps_dict

            # 2. 从步骤中提取case_info（如果存在）
            case_info = None
            if tree_data and isinstance(tree_data[0], dict):
                case_obj = tree_data[0].get("case")
                if case_obj:
                    case_info = {
                        "case_id": case_obj.get("case_id"),
                        "case_code": case_obj.get("case_code"),
                        "case_name": case_obj.get("case_name"),
                    }
            if not case_info:
                case_instance = await AUTOTEST_API_CASE_CRUD.get_by_id(case_id=case_id, on_error=True)
                case_info = {
                    "case_id": case_id,
                    "case_code": case_instance.case_code,
                    "case_name": case_instance.case_name,
                }

            # 3. 规范化步骤数据
            tree_data = [AutoTestToolService.normalize_step(step) for step in tree_data]

            # 4. 收集defined_variables
            # initial_variables 和 all_session_variables 都是列表格式，每个元素包含 key、value、desc
            all_session_variables = AutoTestToolService.collect_session_variables(tree_data)
            # 合并两个列表，如果存在相同的key，使用 all_session_variables 中的值（后收集的优先）
            merged_variables = {}
            # 先添加 initial_variables
            if isinstance(initial_variables, list):
                for item in initial_variables:
                    if isinstance(item, dict) and "key" in item:
                        merged_variables[item.get("key")] = item
            # 再添加 all_session_variables（会覆盖相同的key）
            if isinstance(all_session_variables, list):
                for item in all_session_variables:
                    if isinstance(item, dict) and "key" in item:
                        merged_variables[item.get("key")] = item
            try:
                # 转换回列表格式
                initial_variables = list(merged_variables.values())
            except Exception as e:
                return ParameterResponse(message=str(e))

            # 5. 获取根步骤
            root_steps = [s for s in tree_data if s.get("parent_step_id") is None]
            if not root_steps:
                return BadReqResponse(message="没有可执行的根步骤")

            # 6. 执行（若选择了单条数据集则传入 dataset_name，步骤执行器内按 case_id/step_no/step_code/dataset_name 查表取数）
            # 调试模式：选中的数据集名称必须且只能有一条，数据在 HTTP 步骤执行器内按 case_id/step_no/step_code/dataset_name 查表获取
            selected_dataset_names = getattr(request, "selected_dataset_names", None) or []
            selected_dataset_names = ["场景1名称"]
            if selected_dataset_names:
                if len(selected_dataset_names) != 1:
                    return BadReqResponse(message="调试模式下 selected_dataset_names 必须且只能选择一条数据集")
                debug_dataset_name = selected_dataset_names[0]
            else:
                debug_dataset_name = None
            engine = AutoTestStepExecutionEngine(save_report=True, defer_save=True)
            results, logs, report_code, statistics, session_variables, defer_create_report, pending_create_details = await engine.execute_case(
                case=case_info,
                steps=root_steps,
                env_name=env_name,
                initial_variables=initial_variables,
                report_type=AutoTestReportType.DEBUG_EXEC,
                dataset_name=debug_dataset_name,
            )
            if defer_create_report is not None:
                try:
                    async with in_transaction():
                        report_instance = await AUTOTEST_API_REPORT_CRUD.create_report(report_in=defer_create_report)
                        for detail_create in (pending_create_details or []):
                            detail_schema = detail_create.model_copy(update={"report_code": report_instance.report_code})
                            await AUTOTEST_API_DETAIL_CRUD.create_detail(detail_in=detail_schema)
                        case_state = statistics.get("failed_steps", 0) == 0
                        case_last_time = defer_create_report.case_ed_time
                        await AUTOTEST_API_CASE_CRUD.update_case(AutoTestApiCaseUpdate(
                            case_id=case_id,
                            case_state=case_state,
                            case_last_time=case_last_time,
                        ))
                except Exception as e:
                    LOGGER.error(f"执行或调试步骤树(调试模式)时发生未知异常，错误描述: {e}\n{traceback.format_exc()}")

            # 7. 获取最终会话变量（从执行引擎返回）
            # session_variables 和 initial_variables 都是列表格式，每个元素包含 key、value、desc
            # 合并两个列表，如果存在相同的key，使用 session_variables 中的值（后执行的优先）
            final_session_variables = {}
            # 先添加 initial_variables
            if isinstance(initial_variables, list):
                for item in initial_variables:
                    if isinstance(item, dict) and "key" in item:
                        final_session_variables[item.get("key")] = item
            # 再添加 session_variables（会覆盖相同的key）
            if isinstance(session_variables, list):
                for item in session_variables:
                    if isinstance(item, dict) and "key" in item:
                        final_session_variables[item.get("key")] = item
            # 转换回列表格式
            final_session_variables = list(final_session_variables.values())

            # 8. 返回调试模式的详细结果
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
                "saved_to_database": True
            }
            return SuccessResponse(
                message=f"调试完成, 共{total_steps}步骤, 成功{success_steps}步, 失败{failed_steps}步, 成功率: {passed_ratio}%",
                data=result_data,
                total=1
            )
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"执行或调试步骤树失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"执行或调试步骤树失败, 异常描述: {e}")


@autotest_step.post("/batch_execute", summary="API自动化测试-批量执行用例")
async def batch_execute_cases_endpoint(
        request: AutoTestBatchExecuteCases = Body(..., description="批量执行请求参数")
):
    try:
        case_ids = request.case_ids
        env_name = request.env_name
        initial_variables = request.initial_variables if request.initial_variables is not None else []
        if not isinstance(initial_variables, list):
            initial_variables = []
        if not case_ids or len(case_ids) == 0:
            return BadReqResponse(message="case_ids列表不能为空")

        # 后台执行
        # from celery_scheduler.tasks.task_exec_case import task_batch_execute_cases
        # apply_async_resound: AsyncResult = task_batch_execute_cases.apply_async(
        #     kwargs={
        #         "case_ids": case_ids,
        #         "initial_variables": initial_variables,
        #         "env_name": env_name,
        #         "report_type": AutoTestApiReportType.ASYNC_EXEC
        #     },
        #     expires=3600,
        # )
        # exec_result = {
        #     "task_id": apply_async_resound.task_id,
        #     "task_state": apply_async_resound.state
        # }

        # 异步执行
        exec_result = await AUTOTEST_API_STEP_CRUD.batch_execute_cases(
            case_ids=case_ids,
            initial_variables=initial_variables,
            env_name=env_name,
            report_type=AutoTestReportType.ASYNC_EXEC,
        )
        return SuccessResponse(message="任务挂载成功, 请稍候至报告中心查看结果", data=exec_result)
    except Exception as e:
        return FailureResponse(message=f"批量执行失败，异常描述: {str(e)}")
