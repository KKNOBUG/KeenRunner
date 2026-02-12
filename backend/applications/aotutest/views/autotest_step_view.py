# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_view.py
@DateTime: 2025/4/28
"""
import json
import re
import time
import traceback
from typing import List, Dict, Any, Optional, Set
from xml.etree import ElementTree as ET

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
    AutoTestStepTreeExecute,
    AutoTestPythonCodeDebugRequest,
)
from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
from backend.applications.aotutest.services.autotest_detail_crud import AUTOTEST_API_DETAIL_CRUD
from backend.applications.aotutest.services.autotest_report_crud import AUTOTEST_API_REPORT_CRUD
from backend.applications.aotutest.services.autotest_step_crud import AUTOTEST_API_STEP_CRUD
from backend.applications.aotutest.services.autotest_step_engine import AutoTestStepExecutionEngine
from backend.applications.aotutest.services.autotest_tool_service import AutoTestToolService
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    ParameterException,
    TypeRejectException,
    DataBaseStorageException,
    DataAlreadyExistsException,
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
        if step_in.case_type:
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
        request_url = step_data.request_url
        request_method = (step_data.request_method or "GET").upper()
        request_header = step_data.request_header or []
        request_params = step_data.request_params or []
        request_form_data = step_data.request_form_data or []
        request_form_urlencoded = step_data.request_form_urlencoded or []
        request_form_file = step_data.request_form_file or []
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
        defined_variables_dict: Dict[str, Any] = {
            item["key"]: item.get("value")
            for item in defined_variables if isinstance(item, dict) and "key" in item
        }
        session_variables_dict: Dict[str, Any] = {
            item["key"]: item.get("value")
            for item in session_variables if isinstance(item, dict) and "key" in item
        }
        merge_all_variables.update(defined_variables_dict)
        merge_all_variables.update(session_variables_dict)

        # 日志辅助函数：添加时间戳和步骤名称
        from datetime import datetime
        def format_log(message: str) -> str:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return f"[{timestamp}] [{step_name}] {message}"

        if not request_url.lower().startswith("http"):
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
                execute_envi_host: str = env_instance.env_host.strip().rstrip("/").rstrip(":")
                execute_envi_port: int = env_instance.env_port
                if not execute_envi_host or not execute_envi_port:
                    return FailureResponse(
                        message=f"HTTP请求调试失败, 环境(project_id={request_project_id}, env_name={env_name})配置不正确"
                    )
                request_url = f"{execute_envi_host}:{execute_envi_port}/{request_url.lstrip('/')}"
            except Exception as e:
                LOGGER.error(f"HTTP请求调试失败, 异常描述: {e}\n{traceback.format_exc()}")
                return FailureResponse(f"HTTP请求调试异常, 错误描述: {e}")

        # 执行日志
        logs = [
            format_log(f"请求开始"),
            format_log(f"开始调试HTTP请求: {request_method} {request_url}"),
            format_log(f"参数替换开始"),
        ]

        def resolve_placeholders(value: Any) -> Any:
            """支持嵌套结构中的 ${var} 占位符替换。"""
            try:
                if isinstance(value, str):
                    pattern = re.compile(r"\$\{([^}]+)}")

                    def replace(match: re.Match) -> str:
                        var_name = match.group(1)
                        if not var_name:
                            logs.append("【获取变量】占位符解析失败, 不允许引用空白符, 保留原值")
                            return match.group(0)
                        try:
                            resolved = merge_all_variables[var_name]
                        except KeyError:
                            logs.append(f"【获取变量】占位符解析失败, 变量({var_name})未定义, 保留原值")
                            return match.group(0)
                        except Exception as e:
                            logs.append(
                                f"【获取变量】占位符解析失败, 引用变量({var_name})引发未知异常, 保留原值, 错误描述: {e}")
                            return match.group(0)
                        try:
                            logs.append("【获取变量】占位符解析成功, ${" + var_name + "} <=> " + f"{resolved}")
                            return str(resolved)
                        except Exception as e:
                            logs.append(
                                f"【获取变量】将变量[{var_name}]的值[{resolved}]转换为字符串时失败, 保留原值, 错误描述: {e}")
                            return match.group(0)

                    return pattern.sub(replace, value)

                if isinstance(value, dict):
                    try:
                        return {k: resolve_placeholders(v) for k, v in value.items()}
                    except Exception as e:
                        logs.append(f"【获取变量】解析字典中的占位符时发生错误, 键: {list(value.keys())}, 错误: {e}")
                        return value

                if isinstance(value, list):
                    try:
                        # 处理列表格式的变量（每个元素包含key、value、desc）
                        result = []
                        for item in value:
                            if isinstance(item, dict) and "key" in item and "value" in item:
                                # 列表格式的变量项，只解析value字段
                                resolved_item = dict(item)
                                resolved_item["value"] = resolve_placeholders(item.get("value"))
                                result.append(resolved_item)
                            else:
                                # 普通列表项，递归解析
                                result.append(resolve_placeholders(item))
                        return result
                    except Exception as e:
                        logs.append(f"【获取变量】解析列表中的占位符时发生错误, 列表长度: {len(value)}, 错误: {e}")
                        return value
                return value
            except Exception as e:
                logs.append(
                    f"【获取变量】占位符解析过程中发生未知异常, 保留原值, "
                    f"错误类型: {type(e).__name__}, "
                    f"错误描述: {e}"
                )
                return value

        # 解析请求参数（列表格式）
        headers_list = resolve_placeholders(request_header)
        params_list = resolve_placeholders(request_params)
        form_data_list = resolve_placeholders(request_form_data)
        urlencoded_list = resolve_placeholders(request_form_urlencoded)
        form_files_list = resolve_placeholders(request_form_file)

        # 将列表格式转换为字典格式（用于HTTP请求）
        def convert_list_to_dict(data_list):
            """将列表格式（每个元素包含key、value、desc）转换为字典格式"""
            if not isinstance(data_list, list):
                return {}
            result = {}
            for item in data_list:
                if isinstance(item, dict) and "key" in item:
                    key = item.get("key")
                    value = item.get("value")
                    if key:
                        result[key] = str(value)
            return result

        headers = convert_list_to_dict(headers_list)
        params = convert_list_to_dict(params_list)
        form_data = convert_list_to_dict(form_data_list)
        urlencoded = convert_list_to_dict(urlencoded_list)
        form_files = convert_list_to_dict(form_files_list)

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

        if data_payload is not None:
            request_kwargs["json"] = data_payload
        elif json_payload is not None:
            request_kwargs["data"] = json_payload
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
        logs.append(format_log(f"HTTP请求完成: 状态码 {response.status_code}, 耗时 {duration}ms"))
        logs.append(format_log(f"请求结束"))

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

        # 处理数据提取
        extract_results = []
        if extract_variables:
            if not isinstance(extract_variables, list):
                logs.append(format_log(
                    f"【变量提取】表达式列表解析失败: "
                    f"参数[extract_variables]必须是[List[Dict[str, Any]]]类型, "
                    f"但得到[{type(extract_variables)}]类型"
                ))
            else:
                logs.append(format_log(f"【变量提取】开始"))
                for ext_config in extract_variables:
                    try:
                        if not isinstance(ext_config, dict):
                            logs.append(format_log(
                                f"【变量提取】表达式子项解析无效(跳过): "
                                f"参数[extract_variables]的子项必须是[Dict[str, Any]]类型, "
                                f"但得到[{type(ext_config)}]类型: {ext_config}"
                            ))
                            continue

                        name = ext_config.get("name")
                        expr = ext_config.get("expr")
                        source = ext_config.get("source")
                        range_type = ext_config.get("range")
                        index = ext_config.get("index")
                        if not name or not expr or not source:
                            logs.append(format_log(
                                f"【变量提取】表达式子项解析无效(跳过): "
                                f"参数[name, expr, source]是必须的, 如需继续提取可添加[range, index]参数"
                            ))
                            continue

                        error_msg = ""
                        extracted_value = None
                        try:
                            if source.lower() == "response json":
                                if not response_json:
                                    error_msg = "【变量提取】响应内容不是有效的JSON数据"
                                elif range_type.lower() == "all":
                                    extracted_value = response_json
                                elif expr:
                                    try:
                                        extracted_value = AutoTestToolService.resolve_json_path(
                                            data=response_json,
                                            expr=expr
                                        )
                                    except Exception as e:
                                        error_msg = f"【变量提取】: {e}"
                                    if isinstance(extracted_value, list) and index is not None:
                                        try:
                                            index_int = int(index)
                                            if index_int < len(extracted_value):
                                                extracted_value = extracted_value[index_int]
                                            else:
                                                error_msg = (
                                                    f"【变量提取】数组越界, "
                                                    f"给定索引[{index_int}]不可大于数组长度[{len(extracted_value)}]"
                                                )
                                        except (ValueError, TypeError) as e:
                                            error_msg = f"【变量提取】参数[index]必须是数字类型, 错误描述: {e}"
                                else:
                                    error_msg = "【变量提取】模式[SOME]下参数[expr]是必须的, 并且需要是有效的JSONPath表达式"

                            elif source.lower() == "response xml":
                                if not response_text:
                                    error_msg = "【变量提取】响应内容不是有效的XML数据"
                                elif range_type.lower() == "all":
                                    extracted_value = response_text
                                elif expr:
                                    try:
                                        response_xml = ET.fromstring(response_text)
                                        elements = response_xml.findall(expr)
                                        if not elements:
                                            error_msg = f"【变量提取】XPath表达式[{expr}]未匹配到元素"
                                        elif index is not None:
                                            try:
                                                index_int = int(index)
                                                if index_int < len(elements):
                                                    element = elements[index_int]
                                                    extracted_value = element.text if element.text else ET.tostring(
                                                        element,
                                                        encoding="unicode"
                                                    )
                                                else:
                                                    error_msg = (
                                                        f"【变量提取】数组越界, "
                                                        f"给定索引[{index_int}]不可大于数组长度[{len(elements)}]"
                                                    )
                                            except (ValueError, TypeError) as e:
                                                error_msg = f"【变量提取】参数[index]必须是数字类型, 错误描述: {e}"
                                        else:
                                            element = elements[-1]
                                            extracted_value = element.text if element.text else ET.tostring(
                                                element,
                                                encoding="unicode"
                                            )
                                    except ET.ParseError as e:
                                        error_msg = f"【变量提取】响应内容不是有效的XML格式, 错误描述: {e}"
                                    except Exception as e:
                                        error_msg = f"【变量提取】XPath表达式[{expr}]执行失败, 错误: {e}"
                                else:
                                    error_msg = "【变量提取】模式[SOME]下参数[expr]是必须的, 并且需要是有效的XPath表达式"

                            elif source.lower() == "response text":
                                if not response_text:
                                    error_msg = "【变量提取】响应内容不是有效的Text数据"
                                if range_type.lower() == "all":
                                    extracted_value = response_text
                                elif expr:
                                    try:
                                        match = re.search(expr, response_text)
                                        extracted_value = match.group(0) if match else None
                                        if not extracted_value:
                                            error_msg = f"【变量提取】正则表达式[{expr}]未匹配到内容"
                                    except re.error as e:
                                        error_msg = f"【变量提取】正则表达式[{expr}]执行失败, 错误描述: {e}"
                                else:
                                    error_msg = "【变量提取】模式[SOME]下参数[expr]是必须的, 并且需要是有效的正则表达式"

                            elif source.lower() == "response headers":
                                if not response_headers:
                                    error_msg = "【变量提取】响应 Headers 为空"
                                if range_type.lower() == "all":
                                    extracted_value = response_headers
                                elif expr:
                                    extracted_value = response_headers.get(expr)
                                    if not extracted_value:
                                        error_msg = f"【变量提取】响应 Headers 中不存在: {expr}"
                                else:
                                    error_msg = "【变量提取】模式[SOME]下参数[expr]是必须的, 并且需要是存在的键名称"

                            elif source.lower() == "response cookies":
                                if not response_cookies:
                                    error_msg = "【变量提取】响应 Cookies 为空"
                                if range_type.lower() == "all":
                                    extracted_value = response_cookies
                                elif expr:
                                    extracted_value = response_cookies.get(expr)
                                    if not extracted_value:
                                        error_msg = f"【变量提取】响应 Cookies 中不存在: {expr}"
                                else:
                                    error_msg = "【变量提取】模式[SOME]下参数[expr]是必须的, 并且需要是存在的键名称"

                            elif source.lower() == "session_variables" or source == "变量池":
                                if expr:
                                    extracted_value = merge_all_variables.get(expr)
                                    if extracted_value is None:
                                        error_msg = f"【变量提取】在变量池[Session Variables Pool]中未找到[{expr}]变量"
                                else:
                                    error_msg = "【变量提取】模式[SOME]下参数[expr]是必须的, 并且需要是存在的键名称"
                            else:
                                error_msg = f"【变量提取】源类型 {source} 不被支持"

                            if error_msg:
                                logs.append(format_log(f"【变量提取】失败: {name}, {error_msg}"))
                            else:
                                logs.append(format_log(f"【变量提取】成功: {name}  <==>  {extracted_value}"))

                        except Exception as e:
                            error_msg = str(e)
                            logs.append(format_log(f"【变量提取】异常: {name}, 错误: {error_msg}"))

                        extract_results.append({
                            "name": name,
                            "source": source,
                            "range": range_type,
                            "expr": expr,
                            "index": index,
                            "extracted_value": extracted_value,
                            "error": error_msg,
                            "success": error_msg == ""
                        })
                    except Exception as e:
                        logs.append(format_log(f"【变量提取】发生未知异常: {str(e)}"))
                        extract_results.append({
                            "name": ext_config.get("name"),
                            "source": ext_config.get("source"),
                            "range": ext_config.get("range"),
                            "expr": ext_config.get("expr"),
                            "index": ext_config.get("index"),
                            "extracted_value": None,
                            "error": str(e),
                            "success": False
                        })
                logs.append(format_log(f"【变量提取】结束"))

        # 处理断言验证
        validator_results = []
        if assert_validators:
            # 必须是数组格式
            if not isinstance(assert_validators, list):
                logs.append(format_log(
                    f"【断言验证】表达式列表解析失败: "
                    f"参数[extract_variables]必须是[List[Dict[str, Any]]]类型, "
                    f"但得到[{type(extract_variables)}]类型"
                ))
            else:
                logs.append(format_log(f"【断言验证】开始"))
                for validator_config in assert_validators:
                    try:
                        if not isinstance(validator_config, dict):
                            logs.append(format_log(
                                f"【断言验证】表达式子项解析无效(跳过): "
                                f"参数[extract_variables]的子项必须是[Dict[str, Any]]类型, "
                                f"但得到[{type(validator_config)}]类型: {validator_config}"
                            ))
                            continue
                        name: str = validator_config.get("name")
                        expr: str = validator_config.get("expr")
                        operation: str = validator_config.get("operation")
                        except_value: str = validator_config.get("except_value")
                        source: str = validator_config.get("source")
                        if not name or not expr or not operation or not source:
                            logs.append(format_log(
                                f"【断言验证】表达式子项解析无效(跳过): "
                                f"参数[name, expr, operation, source]是必须的, 非空断言时需添加[except_value]参数"
                            ))
                            continue

                        error_msg = ""
                        success = False
                        actual_value = None
                        try:
                            if source.lower() == "response json":
                                if not response_json:
                                    error_msg = "【断言验证】响应内容不是有效的JSON数据"
                                elif expr:
                                    try:
                                        actual_value = AutoTestToolService.resolve_json_path(
                                            data=response_json,
                                            expr=expr
                                        )
                                    except Exception as e:
                                        error_msg = f"【断言验证】: {e}"
                                else:
                                    error_msg = "【断言验证】参数[expr]是必须的, 并且需要是有效的JSONPath表达式"

                            elif source.lower() == "response xml":
                                if not response_text:
                                    error_msg = "【断言验证】响应内容不是有效的XML数据"
                                elif expr:
                                    try:
                                        response_xml = ET.fromstring(response_text)
                                        elements = response_xml.findall(expr)
                                        if not elements:
                                            error_msg = f"【断言验证】XPath表达式[{expr}]未匹配到元素"
                                        else:
                                            element = elements[-1]
                                            actual_value = element.text if element.text else ET.tostring(
                                                element,
                                                encoding="unicode"
                                            )
                                    except ET.ParseError as e:
                                        error_msg = f"【断言验证】响应内容不是有效的XML格式, 错误描述: {e}"
                                    except Exception as e:
                                        error_msg = f"【断言验证】XPath表达式[{expr}]执行失败, 错误: {e}"
                                else:
                                    error_msg = "【断言验证】参数[expr]是必须的, 并且需要是有效的XPath表达式"

                            elif source.lower() == "response text":
                                if not response_text:
                                    error_msg = "【断言验证】响应内容不是有效的Text数据"
                                elif expr:
                                    try:
                                        match = re.search(expr, response_text)
                                        actual_value = match.group(0) if match else None
                                        if not actual_value:
                                            error_msg = f"【断言验证】正则表达式[{expr}]未匹配到内容"
                                    except re.error as e:
                                        error_msg = f"【断言验证】正则表达式[{expr}]执行失败, 错误描述: {e}"
                                else:
                                    error_msg = "【断言验证】参数[expr]是必须的, 并且需要是有效的正则表达式"

                            elif source.lower() == "response headers":
                                if not response_cookies:
                                    error_msg = "【断言验证】响应 Headers 为空"
                                elif expr:
                                    actual_value = response_headers.get(expr)
                                    if not actual_value:
                                        error_msg = f"【断言验证】响应 Headers 中不存在: {expr}"
                                else:
                                    error_msg = "【断言验证】参数[expr]是必须的, 并且需要是存在的键名称"

                            elif source.lower() == "response cookies":
                                if not response_cookies:
                                    error_msg = "【断言验证】响应 Cookies 为空"
                                elif expr:
                                    actual_value = response_cookies.get(expr)
                                    if not actual_value:
                                        error_msg = f"【断言验证】响应 Cookies 中不存在: {expr}"
                                else:
                                    error_msg = "【断言验证】参数[expr]是必须的, 并且需要是存在的键名称"

                            elif source.lower() == "session_variables" or source == "变量池":
                                if not defined_variables:
                                    error_msg = "【断言验证】变量池 session_variables 为空"
                                elif expr:
                                    actual_value = merge_all_variables.get(expr)
                                    if actual_value is None:
                                        error_msg = f"变量池 session_variables 中不存在: {expr}"
                                else:
                                    error_msg = "【断言验证】参数[expr]是必须的, 并且需要是存在的键名称"

                            else:
                                error_msg = f"【断言验证】源类型 {source} 不被支持"

                            if error_msg:
                                logs.append(format_log(f"【断言验证】比较失败: {name}, {error_msg}"))
                            elif actual_value is not None:
                                try:
                                    success = AutoTestToolService.compare_assertion(
                                        actual=actual_value,
                                        operation=operation,
                                        expected=except_value
                                    )
                                    if success:
                                        logs.append(format_log(
                                            f"【断言验证】比较成功: "
                                            f"{name}, {expr} {operation} {except_value}, 实际值={actual_value}"
                                        ))
                                    else:
                                        logs.append(format_log(
                                            f"【断言验证】比较失败: "
                                            f"{name}, {expr} {operation} {except_value}, 实际值={actual_value}"
                                        ))
                                except Exception as e:
                                    error_msg = str(e)
                                    logs.append(format_log(
                                        f"【断言验证】比较异常, 错误描述: {e}: {name}, {error_msg}"
                                    ))
                            else:
                                logs.append(format_log(
                                    f"【断言验证】获取实际值失败: "
                                    f"{name}, {expr} {operation} {except_value}, 实际值={actual_value}"
                                ))

                        except Exception as e:
                            logs.append(format_log(
                                f"【断言验证】获取实际值异常, 错误描述: {e}: "
                                f"{name}, {expr} {operation} {except_value}, 实际值={actual_value}"
                            ))
                        validator_results.append({
                            "name": name,
                            "source": source,
                            "expr": expr,
                            "operation": operation,
                            "except_value": except_value,
                            "actual_value": actual_value,
                            "success": success,
                            "error": error_msg
                        })
                    except Exception as e:
                        logs.append(format_log(f"【断言验证】未知异常, 错误描述: {e}"))
                        validator_results.append({
                            "name": validator_config.get("name"),
                            "source": validator_config.get("source"),
                            "expr": validator_config.get("expr"),
                            "operation": validator_config.get("operation"),
                            "expected_value": validator_config.get("except_value"),
                            "actual_value": None,
                            "success": False,
                            "error": str(e)
                        })
                logs.append(format_log(f"【断言验证】结束"))

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
            actual_body = actual_body = {}
            actual_body = {**actual_body, "__files": json_payload}
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
                response_data = {
                    "error": str(e)
                }
                LOGGER.warning(f"Python代码调试失败: {step_name}, 错误: {str(e)}")
                return FailureResponse(message="Python代码调试失败", data=response_data, total=1)

    except Exception as e:
        error_message: str = (
            f"【Python代码调试】调试过程发生未知错误, \n"
            f"错误类型: {type(e).__name__}, \n"
            f"错误详情: {e}, \n"
            f"错误回溯: {traceback.format_exc()}"
        )
        response_data = {
            "error": error_message
        }
        LOGGER.error(error_message)
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
                # 使用公共函数执行单个用例
                result_data = await AUTOTEST_API_STEP_CRUD.execute_single_case(
                    case_id=case_id,
                    env_name=env_name,
                    initial_variables=initial_variables,
                    report_type=AutoTestReportType.SYNC_EXEC
                )
                return SuccessResponse(message="执行步骤成功并已保存到数据库", data=result_data)
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
                    "id": case_instance.id,
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

            # 6. 执行
            engine = AutoTestStepExecutionEngine(save_report=True)
            results, logs, report_code, statistics, session_variables, report_create_for_defer, pending_details_for_defer = await engine.execute_case(
                case=case_info,
                steps=root_steps,
                env_name=env_name,
                initial_variables=initial_variables,
                report_type=AutoTestReportType.DEBUG_EXEC
            )
            if report_create_for_defer is not None and pending_details_for_defer is not None:
                try:
                    async with in_transaction():
                        report_instance = await AUTOTEST_API_REPORT_CRUD.create_report(report_create_for_defer)
                        created_report_code = report_instance.report_code
                        for detail_create in (pending_details_for_defer or []):
                            detail_with_report = detail_create.model_copy(update={"report_code": created_report_code})
                            await AUTOTEST_API_DETAIL_CRUD.create_detail(detail_with_report)
                        case_state = statistics.get("failed_steps", 0) == 0
                        case_last_time = report_create_for_defer.case_ed_time
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
            result_data = {
                "success": statistics.get("failed_steps", 0) == 0,
                "total_steps": statistics.get("total_steps", 0),
                "success_steps": statistics.get("success_steps", 0),
                "failed_steps": statistics.get("failed_steps", 0),
                "pass_ratio": statistics.get("pass_ratio", 0.0),
                "results": [serialize_result(r) for r in results],
                "logs": {str(k): v for k, v in logs.items()},
                "session_variables": final_session_variables,
                "saved_to_database": True
            }
            return SuccessResponse(message="调试执行完成", data=result_data)
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
