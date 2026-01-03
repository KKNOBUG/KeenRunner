# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_view.py
@DateTime: 2025/4/28
"""
import json
import logging
import re
import time
from typing import List, Dict, Any, Optional

import httpx
from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from backend.applications.aotutest.schemas.autotest_case_schema import AutoTestApiCaseUpdate
from backend.applications.aotutest.schemas.autotest_step_schema import (
    AutoTestApiStepCreate,
    AutoTestApiStepUpdate,
    AutoTestStepSelect,
    AutoTestStepTreeUpdateList,
    AutoTestStepTreeUpdateItem,
    AutoTestHttpDebugRequest,
    AutoTestStepTreeExecute,
    AutoTestBatchExecuteCases
)
from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
from backend.applications.aotutest.services.autotest_step_crud import AUTOTEST_API_STEP_CRUD
from backend.applications.aotutest.services.autotest_step_engine import (
    AutoTestStepExecutionEngine,
    AutoTestToolService
)
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
from backend.enums.autotest_enum import ReportType

logger = logging.getLogger(__name__)

autotest_step = APIRouter()


@autotest_step.post("/create", summary="API自动化测试-新增步骤")
async def create_step(
        step_in: AutoTestApiStepCreate = Body(..., description="步骤信息")
):
    try:
        instance = await AUTOTEST_API_STEP_CRUD.create_step(step_in)
        data = await instance.to_dict(
            exclude_fields={"state", "created_user", "updated_user", "created_time", "updated_time"},
            replace_fields={"id": "step_id"}
        )
        return SuccessResponse(message="新增成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"新增失败, 异常描述: {e}")


@autotest_step.delete("/delete", summary="API自动化测试-按id或code删除步骤")
async def delete_step(
        step_id: Optional[int] = Query(None, description="步骤ID"),
        step_code: Optional[str] = Query(None, description="步骤标识代码"),
):
    try:
        instance = await AUTOTEST_API_STEP_CRUD.delete_step(step_id=step_id, step_code=step_code)
        data = await instance.to_dict(
            exclude_fields={"state", "created_user", "updated_user", "created_time", "updated_time"},
            replace_fields={"id": "step_id"}
        )
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@autotest_step.post("/update", summary="API自动化测试-按id或code更新步骤")
async def update_step(
        step_in: AutoTestApiStepUpdate = Body(..., description="步骤信息")
):
    try:
        instance = await AUTOTEST_API_STEP_CRUD.update_step(step_in)
        data = await instance.to_dict(
            exclude_fields={"state", "created_user", "updated_user", "created_time", "updated_time"},
            replace_fields={"id": "step_id"}
        )
        return SuccessResponse(message="更新成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
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
            exclude_fields={"state", "created_user", "updated_user", "created_time", "updated_time"},
            replace_fields={"id": "step_id"}
        )
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_step.post("/search", summary="API自动化测试-按条件查询步骤")
async def search_steps(
        step_in: AutoTestStepSelect = Body(..., description="查询条件")
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
                exclude_fields={"state", "created_user", "updated_user", "created_time", "updated_time"},
                replace_fields={"id": "step_id"}
            ) for obj in instances
        ]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_step.get("/tree", summary="API自动化测试-按id或code查询步骤树")
async def get_step_tree(
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
):
    try:
        tree_data = await AUTOTEST_API_STEP_CRUD.get_by_case_id(case_id=case_id, case_code=case_code)
        step_counter = tree_data.pop(-1)
        return SuccessResponse(message="查询成功", data=tree_data, total=step_counter["total_steps"])
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
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
        logger.info(f"开始批量更新步骤树，共 {len(steps_data)} 个根步骤")

        # 1. 校验步骤树结构合法性
        is_valid, error_msg = AutoTestToolService.validate_step_tree_structure(steps_data)
        if not is_valid:
            logger.error(f"步骤树结构校验失败: {error_msg}")
            return BadReqResponse(message=f"步骤树结构校验失败: {error_msg}")

        # 2. 判断是新增还是更新
        case_id = case_data.case_id
        case_code = case_data.case_code
        # 如果同时存在case_id和case_code字段，说明用例信息存在，判定为更新
        if case_id and case_code:
            is_update = True
            logger.info(f"检测到更新操作，case_id={case_id}, case_code={case_code}")
        elif not case_id and not case_code:
            is_update = False
            logger.info(f"检测到新增操作，case_id={case_id}, case_code={case_code}")
        else:
            return ParameterResponse(message="用例参数校验失败")

        # 3. 准备用例数据
        cases_data: List[AutoTestApiCaseUpdate] = [case_data]

        # 5. 使用事务执行批量更新/新增
        try:
            async with in_transaction():
                # 5.1 处理用例信息
                case_result: Dict[str, Any] = {
                    "created_count": 0,
                    "updated_count": 0,
                    "failed_cases": [],
                    "passed_cases": []
                }
                if cases_data:
                    case_result: Dict[str, Any] = await AUTOTEST_API_CASE_CRUD.batch_update_or_create_cases(cases_data)
                    created_case_count: int = case_result['created_count']
                    updated_case_count: int = case_result['updated_count']
                    success_case_detail: List[Dict[str, Any]] = case_result['success_detail']
                    logger.info(
                        f"用例处理完成："
                        f"新增: {created_case_count}个, "
                        f"更新: {updated_case_count}个, "
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
                                        recursive_update_case_id(step.children, case_id)

                            recursive_update_case_id(steps_data, successful_case_id)

                # 5.2 批量更新/新增步骤信息（递归处理）
                step_result: Dict[str, Any] = await AUTOTEST_API_STEP_CRUD.batch_update_or_create_steps(steps_data)
                created_step_count: int = step_result['created_count']
                updated_step_count: int = step_result['updated_count']
                deleted_step_count: int = step_result['deleted_count']
                success_step_detail: List[Dict[str, Any]] = step_result['success_detail']
                logger.info(
                    f"步骤处理完成："
                    f"新增: {created_step_count}个, "
                    f"更新: {updated_step_count}个, "
                    f"成功明细: {success_step_detail}"
                )

                # 6. 构建返回结果
                result_data: Dict[str, Any] = {
                    "cases": case_result,
                    "steps": step_result
                }

                # 7. 返回
                message = (
                    f"批量处理完成: "
                    f"用例新增数: {created_case_count}, "
                    f"用例更新数: {updated_case_count}, "
                    f"步骤新增数: {created_step_count}, "
                    f"步骤更新数: {updated_step_count}, "
                    f"步骤删除数: {deleted_step_count}"
                )
                logger.warning(message)
                return SuccessResponse(message=message, data=result_data)
        except (TypeRejectException,
                ParameterException,
                DataBaseStorageException,
                DataAlreadyExistsException,
                NotFoundException) as e:
            return FailureResponse(message=e.message)
        except Exception as transaction_error:
            # 事务会自动回滚
            logger.error(f"批量处理过程中发生异常，事务已回滚: {str(transaction_error)}", exc_info=True)
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
        logger.error(f"批量处理失败，异常描述: {str(e)}", exc_info=True)
        return FailureResponse(message=f"批量处理失败，异常描述: {str(e)}")


@autotest_step.post("/http_debugging", summary="API自动化测试-HTTP请求调试")
async def debug_http_request(
        step_data: AutoTestHttpDebugRequest = Body(..., description="HTTP请求步骤数据")
):
    """
    调试HTTP请求接口

    功能说明：
    1. 接收前端发送的HTTP请求配置数据
    2. 使用httpx发送HTTP请求（不保存到数据库）
    3. 执行数据提取和断言验证
    4. 返回格式化的响应数据，包括状态码、响应头、响应体、耗时、提取结果、断言结果、执行日志等信息

    请求参数格式（与步骤数据结构一致）：
    - request_url: 请求URL
    - request_method: 请求方法（GET/POST/PUT/DELETE等）
    - request_header: 请求头（字典）
    - request_params: 请求参数（字典或字符串）
    - request_body: JSON请求体（字典）
    - request_form_data: form-data格式数据（字典）
    - request_form_urlencoded: x-www-form-urlencoded格式数据（字典）
    - request_text: 文本格式请求体（字符串）
    - defined_variables: 定义的变量（字典，用于变量替换）
    - extract_variables: 提取变量配置（数组或对象）
    - assert_validators: 断言配置（数组或对象）

    返回数据格式：
    - status: HTTP状态码
    - headers: 响应头（字典）
    - cookies: Cookies（字典）
    - data: 响应数据（JSON对象或文本）
    - duration: 请求耗时（毫秒）
    - size: 响应大小（KB或B）
    - extract_results: 数据提取结果（数组）
    - validator_results: 断言结果（数组）
    - logs: 执行日志（数组）
    """
    try:
        # 提取请求参数（使用 Pydantic 模型，自动验证）
        request_url = step_data.request_url
        request_method = (step_data.request_method or "GET").upper()
        request_header = step_data.request_header or {}
        request_params = step_data.request_params
        request_body = step_data.request_body
        request_form_data = step_data.request_form_data
        request_form_urlencoded = step_data.request_form_urlencoded
        request_text = step_data.request_text
        defined_variables = step_data.defined_variables or {}
        extract_variables = step_data.extract_variables or []
        assert_validators = step_data.assert_validators or []
        step_name = step_data.step_name or "HTTP调试"

        # 日志辅助函数：添加时间戳和步骤名称
        from datetime import datetime
        def format_log(message: str) -> str:
            """格式化日志：[时间戳] [步骤名称] 消息内容"""
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return f"[{timestamp}] [{step_name}] {message}"

        # 执行日志
        logs = [
            format_log(f"请求开始"),
            format_log(f"开始调试HTTP请求: {request_method} {request_url}"),
            format_log(f"参数替换开始"),
        ]

        # 处理变量替换（简单实现，支持 ${variable} 格式）
        def resolve_placeholders(value: Any) -> Any:
            """解析占位符变量"""
            if isinstance(value, str):
                for var_name, var_value in defined_variables.items():
                    if value.startswith("$"):
                        value = value.replace(f"${{{var_name}}}", str(var_value))
                        logs.append("${" + var_name + "} => " + f"{var_value}")
                return value
            elif isinstance(value, dict):
                return {k: resolve_placeholders(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_placeholders(item) for item in value]
            return value

        # 解析请求参数
        headers = resolve_placeholders(request_header)
        params = resolve_placeholders(request_params) if request_params else None

        # 处理请求体
        json_data = None
        data = None
        files = None

        if request_text:
            # 文本格式请求体
            data = resolve_placeholders(request_text)
        elif request_form_data:
            # form-data格式
            data = resolve_placeholders(request_form_data)
        elif request_form_urlencoded:
            # x-www-form-urlencoded格式
            data = resolve_placeholders(request_form_urlencoded)
        elif request_body:
            # JSON格式
            json_data = resolve_placeholders(request_body)

        # 构建请求参数
        logs.append(format_log("参数替换结束"))
        request_kwargs = {
            "headers": headers if headers else None,
            "params": params if params else None,
        }

        if json_data is not None:
            request_kwargs["json"] = json_data
        elif data is not None:
            request_kwargs["data"] = data
        if files is not None:
            request_kwargs["files"] = files

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
                logger.error(f"HTTP请求异常: {str(e)}", exc_info=True)
                return FailureResponse(message=f"请求异常: {str(e)}")

        # 计算耗时
        duration = int((time.time() - start_time) * 1000)  # 转换为毫秒
        logs.append(format_log(f"HTTP请求完成: 状态码 {response.status_code}, 耗时 {duration}ms"))
        logs.append(format_log(f"请求结束"))

        # 解析响应数据
        response_json = None
        response_data = None
        response_body_text = response.text
        try:
            # 尝试解析为JSON
            response_json = response.json()
            response_data = response_json
        except (ValueError, json.JSONDecodeError):
            # 如果不是JSON，使用文本
            response_data = response_body_text

        # 解析Cookies
        cookies = {}
        if response.cookies:
            for cookie in response.cookies.jar:
                cookies[cookie.name] = cookie.value

        # 计算响应大小
        response_size = len(response.content)
        size_str = f"{response_size / 1024:.2f}KB" if response_size > 1024 else f"{response_size}B"

        # 处理数据提取
        extract_results = []
        if extract_variables:
            # 支持数组格式的提取变量
            logs.append(format_log(f"提取开始"))
            extract_list: List[dict] = extract_variables if isinstance(extract_variables, list) else [extract_variables]
            for extract_item in extract_list:
                try:
                    name = extract_item.get("name", "")
                    source = extract_item.get("source", "Response Json")
                    expr = extract_item.get("expr", "")
                    range_type = extract_item.get("range", "SOME")

                    extracted_value = None
                    error_msg = ""

                    if source == "Response Json":
                        if not response_json:
                            error_msg = "响应不是JSON格式，无法提取"
                            logs.append(format_log(f"提取变量失败: {name}, {error_msg}"))
                        elif range_type == "ALL":
                            # 全部提取
                            extracted_value = response_json
                            logs.append(format_log(f"提取变量成功: {name} = {extracted_value}"))
                        elif expr:
                            try:
                                # 部分提取
                                extracted_value = AutoTestToolService.resolve_json_path(response_json, expr)
                                logs.append(format_log(f"提取变量成功: {name} = {extracted_value}"))
                            except Exception as e:
                                error_msg = str(e)
                                logs.append(format_log(f"提取变量失败: {name}, 错误: {error_msg}"))
                        else:
                            error_msg = "部分提取需要提供表达式"
                            logs.append(format_log(f"提取变量失败: {name}, {error_msg}"))
                    elif source == "Response Header" and expr:
                        # 从响应头提取
                        extracted_value = response.headers.get(expr, "")
                        if extracted_value:
                            logs.append(format_log(f"提取变量成功: {name} = {extracted_value}"))
                        else:
                            error_msg = f"响应头中未找到: {expr}"
                            logs.append(format_log(f"提取变量失败: {name}, {error_msg}"))
                    elif source == "Response Cookie" and expr:
                        # 从Cookie提取
                        extracted_value = cookies.get(expr, "")
                        if extracted_value:
                            logs.append(format_log(f"提取变量成功: {name} = {extracted_value}"))
                        else:
                            error_msg = f"Cookie中未找到: {expr}"
                            logs.append(format_log(f"提取变量失败: {name}, {error_msg}"))
                    elif source == "Response Text" and expr:
                        # 从响应文本提取（正则表达式）
                        try:
                            match = re.search(expr, response_body_text)
                            extracted_value = match.group(0) if match else None
                            if extracted_value:
                                logs.append(format_log(f"提取变量成功: {name} = {extracted_value}"))
                            else:
                                error_msg = f"正则表达式未匹配到内容: {expr}"
                                logs.append(format_log(f"提取变量失败: {name}, {error_msg}"))
                        except Exception as e:
                            error_msg = f"正则表达式错误: {str(e)}"
                            logs.append(format_log(f"提取变量失败: {name}, {error_msg}"))
                    else:
                        error_msg = "提取配置不完整"
                        logs.append(format_log(f"提取变量失败: {name}, {error_msg}"))

                    extract_results.append({
                        "name": name,
                        "source": source,
                        "range": range_type,
                        "expr": expr,
                        "extracted_value": extracted_value,
                        "error": error_msg,
                        "success": error_msg == ""
                    })
                except Exception as e:
                    logs.append(format_log(f"处理提取变量时出错: {str(e)}"))
                    extract_results.append({
                        "name": extract_item.get("name", ""),
                        "source": extract_item.get("source", ""),
                        "range": extract_item.get("range", ""),
                        "expr": extract_item.get("expr", ""),
                        "extracted_value": None,
                        "error": str(e),
                        "success": False
                    })
            logs.append(format_log(f"提取结束"))

        # 处理断言验证
        validator_results = []
        if assert_validators:
            # 支持数组格式的断言
            logs.append(format_log(f"断言开始"))
            validators_list: List[Dict] = assert_validators if isinstance(assert_validators,
                                                                          list) else [assert_validators]
            for validator_item in validators_list:
                try:
                    name = validator_item.get("name", "")
                    source = validator_item.get("source", "Response Json")
                    expr = validator_item.get("expr", "")
                    operation = validator_item.get("operation", "等于")
                    expected_value = validator_item.get("except_value")

                    actual_value = None
                    error_msg = ""
                    success = False

                    if source == "Response Json" and expr:
                        if not response_json:
                            error_msg = "响应不是JSON格式，无法断言"
                            logs.append(format_log(f"断言失败: {name}, {error_msg}"))
                        else:
                            try:
                                actual_value = AutoTestToolService.resolve_json_path(response_json, expr)
                            except Exception as e:
                                error_msg = f"无法解析表达式 {expr}: {str(e)}"
                                logs.append(format_log(f"断言失败: {name}, {error_msg}"))
                    elif source == "Response Header" and expr:
                        actual_value = response.headers.get(expr, "")
                    elif source == "Response Cookie" and expr:
                        actual_value = cookies.get(expr, "")
                    elif source == "Response Text" and expr:
                        # 从响应文本提取（正则表达式）
                        try:
                            match = re.search(expr, response_body_text)
                            actual_value = match.group(0) if match else None
                        except Exception as e:
                            error_msg = f"正则表达式错误: {str(e)}"
                            logs.append(format_log(f"断言失败: {name}, {error_msg}"))
                    elif source == "变量池" and expr:
                        # 从变量池提取（这里简化处理，实际应该从定义的变量中获取）
                        actual_value = defined_variables.get(expr, None)
                        if actual_value is None:
                            error_msg = f"变量池中未找到: {expr}"
                            logs.append(format_log(f"断言失败: {name}, {error_msg}"))

                    if error_msg == "" and actual_value is not None:
                        try:
                            success = AutoTestToolService.compare_assertion(actual_value, operation, expected_value)
                            if success:
                                logs.append(format_log(
                                    f"断言通过: {name}, {expr} {operation} {expected_value}, 实际值={actual_value}"))
                            else:
                                logs.append(format_log(
                                    f"断言失败: {name}, {expr} {operation} {expected_value}, 实际值={actual_value}"))
                        except Exception as e:
                            error_msg = str(e)
                            logs.append(format_log(f"断言比较失败: {name}, {error_msg}"))
                    elif error_msg == "":
                        error_msg = "无法获取实际值"
                        logs.append(format_log(f"断言失败: {name}, {error_msg}"))

                    validator_results.append({
                        "name": name,
                        "source": source,
                        "expr": expr,
                        "operation": operation,
                        "expected_value": expected_value,
                        "actual_value": actual_value,
                        "success": success,
                        "error": error_msg
                    })
                except Exception as e:
                    logs.append(format_log(f"处理断言时出错: {str(e)}"))
                    validator_results.append({
                        "name": validator_item.get("name", ""),
                        "source": validator_item.get("source", ""),
                        "expr": validator_item.get("expr", ""),
                        "operation": validator_item.get("operation", ""),
                        "expected_value": validator_item.get("except_value"),
                        "actual_value": None,
                        "success": False,
                        "error": str(e)
                    })
            logs.append(format_log(f"断言结束"))

        # 构建返回数据（包含处理后的请求信息，用于前端展示实际发送的报文）
        # 确定实际发送的请求体类型和内容
        actual_body_type = "none"
        actual_body = None
        if json_data is not None:
            actual_body_type = "json"
            actual_body = json_data
        elif data is not None:
            if request_form_data:
                actual_body_type = "form-data"
            elif request_form_urlencoded:
                actual_body_type = "x-www-form-urlencoded"
            else:
                actual_body_type = "text"
            actual_body = data

        result_data = {
            "status": response.status_code,
            "headers": dict(response.headers),
            "cookies": cookies,
            "data": response_data,
            "duration": duration,
            "size": size_str,
            "extract_results": extract_results,
            "validator_results": validator_results,
            "logs": logs,
            # 添加处理后的请求信息，供前端展示实际发送的报文
            "request_info": {
                "url": request_url,
                "method": request_method,
                "headers": headers or {},
                "params": params,
                "body_type": actual_body_type,
                "body": actual_body
            }
        }

        logger.info(
            f"HTTP调试请求成功: {request_method} {request_url}, 状态码: {response.status_code}, 耗时: {duration}ms")

        return SuccessResponse(message="调试请求成功", data=result_data)
    except Exception as e:
        logger.error(f"调试HTTP请求失败，异常描述: {str(e)}", exc_info=True)
        return FailureResponse(message=f"调试失败，异常描述: {str(e)}")


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
        case_id = request.case_id
        steps = request.steps
        initial_variables = request.initial_variables or {}

        # 判断运行模式还是调试模式
        is_run_mode = case_id is not None
        is_debug_mode = steps is not None and len(steps) > 0

        if not is_run_mode and not is_debug_mode:
            return BadReqResponse(message="必须提供case_id（运行模式）或steps（调试模式）之一")

        if is_run_mode and is_debug_mode:
            return BadReqResponse(message="运行模式和调试模式不能同时使用，请只提供case_id或steps之一")

        # 序列化执行结果
        def serialize_result(r: Any) -> Dict[str, Any]:
            return {
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
                    initial_variables=initial_variables,
                    report_type=ReportType.EXEC1
                )
                return SuccessResponse(message="执行步骤成功并已保存到数据库", data=result_data)
            except NotFoundException as e:
                return NotFoundResponse(message=str(e.message))
            except ParameterException as e:
                return BadReqResponse(message=str(e.message))
            except Exception as transaction_error:
                logger.error(f"执行步骤过程中发生异常，事务已回滚: {str(transaction_error)}", exc_info=True)
                return FailureResponse(message=f"执行失败，事务已回滚: {str(transaction_error)}")

        # ========== 调试模式 ==========
        else:  # is_debug_mode
            # 1. 将Pydantic模型转换为字典（如果步骤是Pydantic模型）
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
                        "id": case_obj.get("id"),
                        "case_code": case_obj.get("case_code") or f"tmp-{int(time.time())}",
                        "case_name": case_obj.get("case_name") or "未命名用例",
                    }
            if not case_info:
                case_info = {
                    "id": None,
                    "case_code": f"tmp-{int(time.time())}",
                    "case_name": "调试用例",
                }

            # 3. 规范化步骤数据
            tree_data = [AutoTestToolService.normalize_step(step) for step in tree_data]

            # 4. 收集defined_variables
            all_defined_variables = AutoTestToolService.collect_defined_variables(tree_data)
            merged_initial_variables = dict(initial_variables)
            merged_initial_variables.update(all_defined_variables)

            # 5. 获取根步骤
            root_steps = [s for s in tree_data if s.get("parent_step_id") is None]
            if not root_steps:
                return BadReqResponse(message="没有可执行的根步骤")

            # 6. 执行但不保存到数据库
            engine = AutoTestStepExecutionEngine(save_report=False)
            results, logs, report_code, statistics, session_variables = await engine.execute_case(
                case=case_info,
                steps=root_steps,
                initial_variables=merged_initial_variables,
                report_type=ReportType.EXEC1
            )

            # 7. 获取最终会话变量（从执行引擎返回）
            # 会话变量已经包含了所有步骤产生的extract_variables
            # 合并初始变量（defined_variables）
            final_session_variables = dict(session_variables)
            final_session_variables.update(merged_initial_variables)

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
                "saved_to_database": False
            }

            return SuccessResponse(message="调试执行完成", data=result_data, )
    except Exception as e:
        logger.error(f"执行步骤失败，异常描述: {str(e)}", exc_info=True)
        return FailureResponse(message=f"执行失败，异常描述: {str(e)}")


@autotest_step.post("/batch_execute", summary="API自动化测试-批量执行用例")
async def batch_execute_cases_endpoint(
        request: AutoTestBatchExecuteCases = Body(..., description="批量执行请求参数")
):
    """
    批量执行测试用例：
    - 根据cases_ids列表(多个case_id)执行，逐一执行列表内的所有case_id
    - 针对每一个case_id开启独立的事务，确保每个用例的执行结果独立保存
    - 如果某个用例执行失败，不会影响其他用例的执行
    - 返回每个用例的执行结果汇总

    返回数据格式：
    - total_cases: 总用例数
    - success_cases: 成功用例数
    - failed_cases: 失败用例数
    - results: 每个用例的执行结果列表
    - summary: 汇总信息（包含成功率、是否全部成功等）
    """
    try:
        case_ids = request.case_ids
        execute_environment = request.env
        initial_variables = request.initial_variables or {}
        if not case_ids or len(case_ids) == 0:
            return BadReqResponse(message="case_ids列表不能为空")

        # 调用批量执行函数
        result_data = await AUTOTEST_API_STEP_CRUD.batch_execute_cases(
            case_ids=case_ids,
            initial_variables=initial_variables,
            execute_environment=execute_environment,
            report_type=ReportType.EXEC2
        )
        message = (
            f"批量执行完成: "
            f"总用例数: {result_data['total_cases']}, "
            f"成功: {result_data['success_cases']}, "
            f"失败: {result_data['failed_cases']}"
        )
        return SuccessResponse(message=message, data=result_data, )
    except Exception as e:
        logger.error(f"批量执行用例失败，异常描述: {str(e)}", exc_info=True)
        return FailureResponse(message=f"批量执行失败，异常描述: {str(e)}")
