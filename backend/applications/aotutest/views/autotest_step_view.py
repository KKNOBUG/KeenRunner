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

from backend.applications.aotutest.models.autotest_model import ReportType
from backend.applications.aotutest.schemas.autotest_step_schema import (
    AutoTestApiStepCreate, AutoTestApiStepUpdate,
    AutoTestStepSelect, AutoTestStepTreeUpdateList, AutoTestStepTreeUpdateItem,
    AutoTestHttpDebugRequest, AutoTestStepTreeExecute
)
from backend.applications.aotutest.schemas.autotest_case_schema import AutoTestApiCaseUpdate
from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
from backend.applications.aotutest.services.autotest_step_crud import AUTOTEST_API_STEP_CRUD
from backend.applications.aotutest.services.autotest_step_engine import AutoTestStepExecutionEngine
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    NotFoundResponse,
    BadReqResponse,
    ParameterResponse,
)

logger = logging.getLogger(__name__)

autotest_step = APIRouter()


def resolve_json_path(data: Any, expr: str) -> Any:
    """解析JSONPath表达式"""
    if not expr or not expr.startswith("$."):
        raise ValueError(f"仅支持 $. 开头的 JSONPath 表达式: {expr}")

    parts = [part for part in expr[2:].split(".") if part]
    current: Any = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                index = int(part)
            except ValueError:
                raise ValueError(f"列表索引必须为整数: {part}")
            try:
                current = current[index]
            except IndexError:
                raise ValueError(f"列表索引越界: {part}")
        else:
            raise ValueError(f"无法在 {type(current)} 类型上应用 JSONPath: {part}")
    return current


def _normalize_value(value: Any) -> Any:
    """
    标准化值的类型，用于比较
    - 如果值是可以转换为数字的字符串，则转换为数字
    - 如果值是布尔型字符串，则转换为布尔值
    """
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        # 尝试转换为整数
        if value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
            return int(value)
        # 尝试转换为浮点数
        try:
            if '.' in value:
                return float(value)
        except ValueError:
            pass
        # 尝试转换为布尔值
        if value.lower() == 'true':
            return True
        if value.lower() == 'false':
            return False
    return value


def _type_aware_equals(actual: Any, expected: Any) -> bool:
    """
    类型感知的相等比较
    - 先尝试直接比较
    - 如果类型不同，尝试标准化后比较
    """
    # 直接比较
    if actual == expected:
        return True
    # 标准化后比较
    norm_actual = _normalize_value(actual)
    norm_expected = _normalize_value(expected)
    return norm_actual == norm_expected


def _type_aware_compare(actual: Any, expected: Any, comparator) -> bool:
    """
    类型感知的数值比较（用于大于、小于等）
    """
    norm_actual = _normalize_value(actual)
    norm_expected = _normalize_value(expected)
    # 确保都是数值类型才能进行大小比较
    if isinstance(norm_actual, (int, float)) and isinstance(norm_expected, (int, float)):
        return comparator(norm_actual, norm_expected)
    # 如果不是数值，尝试字符串比较
    return comparator(str(actual), str(expected))


def compare_assertion(actual: Any, operation: str, expected: Any) -> bool:
    """比较断言结果，支持类型智能转换"""
    op_map = {
        "等于": lambda a, b: _type_aware_equals(a, b),
        "不等于": lambda a, b: not _type_aware_equals(a, b),
        "大于": lambda a, b: _type_aware_compare(a, b, lambda x, y: x > y),
        "大于等于": lambda a, b: _type_aware_compare(a, b, lambda x, y: x >= y),
        "小于": lambda a, b: _type_aware_compare(a, b, lambda x, y: x < y),
        "小于等于": lambda a, b: _type_aware_compare(a, b, lambda x, y: x <= y),
        "长度等于": lambda a, b: len(str(a)) == int(_normalize_value(b)) if _normalize_value(b) is not None else False,
        "包含": lambda a, b: str(b) in str(a),
        "不包含": lambda a, b: str(b) not in str(a),
        "以...开始": lambda a, b: str(a).startswith(str(b)),
        "以...结束": lambda a, b: str(a).endswith(str(b)),
    }
    comparator = op_map.get(operation)
    if comparator is None:
        raise ValueError(f"不支持的操作符: {operation}")
    try:
        return comparator(actual, expected)
    except Exception as e:
        raise ValueError(f"断言比较失败: {str(e)}")


@autotest_step.post("/create", summary="新增一个测试步骤明细")
async def create_step(
        step_in: AutoTestApiStepCreate = Body(..., description="步骤明细信息")
):
    """新增一个测试步骤明细"""
    try:
        instance = await AUTOTEST_API_STEP_CRUD.create_step(step_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data, message="创建步骤明细成功")
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e))
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述: {str(e)}")


@autotest_step.get("/get", summary="按id查询一个测试步骤明细", description="根据id查询步骤明细信息")
async def get_step(
        step_id: int = Query(..., description="步骤明细ID")
):
    """按id查询一个测试步骤明细"""
    try:
        instance = await AUTOTEST_API_STEP_CRUD.get_by_id(step_id)
        if not instance:
            return NotFoundResponse(message=f"步骤明细(id={step_id})信息不存在")
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except Exception as e:
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_step.post("/search", summary="按条件查询多个测试步骤明细", description="支持分页按条件查询步骤明细信息")
async def search_steps(
        step_in: AutoTestStepSelect = Body(..., description="查询条件")
):
    """按条件查询多个测试步骤明细"""
    try:
        q = Q()
        if step_in.step_id:
            q &= Q(id=step_in.step_id)
        if step_in.case_id:
            q &= Q(case_id=step_in.case_id)
        if step_in.step_type:
            q &= Q(step_type=step_in.step_type.value)
        if step_in.case_type:
            q &= Q(step_type=step_in.step_type.value)
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
        data = [await obj.to_dict() for obj in instances]
        return SuccessResponse(data=data, total=total)
    except Exception as e:
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_step.post("/update", summary="按id修改一个测试步骤明细", description="根据id修改步骤明细信息")
async def update_step(
        step_in: AutoTestApiStepUpdate = Body(..., description="步骤明细信息")
):
    """按id修改一个测试步骤明细"""
    try:
        instance = await AUTOTEST_API_STEP_CRUD.update_step(step_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data, message="更新步骤明细成功")
    except NotFoundException as e:
        return NotFoundResponse(message=str(e))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e))
    except Exception as e:
        return FailureResponse(message=f"修改失败，异常描述: {str(e)}")


@autotest_step.delete("/delete", summary="按id删除一个测试步骤明细", description="根据id删除步骤明细信息")
async def delete_step(
        step_id: int = Query(..., description="步骤明细ID")
):
    """按id删除一个测试步骤明细"""
    try:
        instance = await AUTOTEST_API_STEP_CRUD.delete_step(step_id)
        data = await instance.to_dict()
        return SuccessResponse(data=data, message="删除步骤明细成功")
    except NotFoundException as e:
        return NotFoundResponse(message=str(e))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e))
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@autotest_step.get("/tree", summary="按测试用例id查询所有对应步骤",
                   description="包含所有子步骤、引用测试用例中的步骤")
async def get_step_tree(
        case_id: int = Query(..., description="测试用例ID")
):
    """
    核心功能：通过测试用例信息id查询所拥有的所有子级步骤
    包含所有子步骤、引用测试用例中的步骤
    """
    try:
        tree_data = await AUTOTEST_API_STEP_CRUD.get_by_case_id(case_id)
        step_counter = tree_data.pop(-1)
        return SuccessResponse(data=tree_data, message="获取步骤树成功", total=step_counter["total_steps"])
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"获取步骤树失败，异常描述: {str(e)}")


def validate_step_tree_structure(steps_data: List[AutoTestStepTreeUpdateItem]) -> tuple:
    """
    校验步骤树结构合法性

    Args:
        steps_data: 步骤树数据

    Returns:
        tuple[bool, Optional[str]]: (是否合法, 错误信息)
    """
    from backend.applications.aotutest.models.autotest_model import StepType

    # 允许有子步骤的步骤类型
    ALLOWED_CHILDREN_TYPES = {StepType.LOOP, StepType.IF}

    def check_step_recursive(step: AutoTestStepTreeUpdateItem, visited_ids: set, path: list) -> tuple:
        """递归检查步骤"""
        step_id = step.step_id
        step_code = step.step_code

        # 检查自循环引用
        if step_id and step_id in visited_ids:
            return False, f"步骤(step_id={step_id}, step_code={step_code or 'N/A'})存在自循环引用"
        if step_code and step_code in path:
            return False, f"步骤(step_code={step_code})存在自循环引用"

        # 添加到已访问集合
        if step_id:
            visited_ids.add(step_id)
        if step_code:
            path.append(step_code)

        # 检查步骤类型是否允许有子步骤
        if step.children and len(step.children) > 0:
            if step.step_type not in ALLOWED_CHILDREN_TYPES:
                return False, f"步骤(step_id={step_id}, step_code={step_code or 'N/A'}, step_type={step.step_type})不允许包含子步骤，仅允许'循环结构'和'条件分支'类型的步骤包含子步骤"

            # 递归检查子步骤
            for child in step.children:
                is_valid, error_msg = check_step_recursive(child, visited_ids.copy(), path.copy())
                if not is_valid:
                    return False, error_msg

        return True, None

    # 检查所有根步骤
    for step in steps_data:
        is_valid, error_msg = check_step_recursive(step, set(), [])
        if not is_valid:
            return False, error_msg

    return True, None


@autotest_step.post("/update_or_create/tree", summary="批量更新测试用例和步骤信息")
async def batch_update_steps_tree(
        data: AutoTestStepTreeUpdateList = Body(..., description="步骤树数据（包含case和steps）")
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
        is_valid, error_msg = validate_step_tree_structure(steps_data)
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
                    created_count: int = case_result['created_count']
                    updated_count: int = case_result['updated_count']
                    passed_cases: List[Dict[str, Any]] = case_result['passed_cases']
                    failed_cases: List[Dict[str, Any]] = case_result['failed_cases']
                    logger.info(
                        f"用例处理完成："
                        f"新增: {created_count}个, "
                        f"更新: {updated_count}个, "
                        f"成功明细: {passed_cases}, "
                        f"失败明细: {failed_cases}"
                    )

                    # 如果用例处理失败，直接返回
                    if len(failed_cases) > 0:
                        result_data = {
                            "cases": case_result,
                            "steps": {
                                "created_count": 0,
                                "updated_count": 0,
                                "failed_count": 0,
                                "failed_steps": [],
                                "steps": []
                            }
                        }
                        message = f"用例处理失败: {failed_cases}"
                        logger.error(message)
                        return BadReqResponse(message=message, data=result_data)

                    # 获取处理后的用例ID，用于关联步骤
                    if passed_cases and len(passed_cases) > 0:
                        processed_case = passed_cases[0]
                        final_case_id: int = processed_case.get("case_id")
                        if final_case_id:
                            # 更新步骤数据中的case_id
                            def update_case_id_recursive(step_list: List[AutoTestStepTreeUpdateItem], case_id: int):
                                """递归更新步骤的case_id"""
                                for step in step_list:
                                    step.case_id = case_id
                                    if step.children:
                                        update_case_id_recursive(step.children, case_id)

                            update_case_id_recursive(steps_data, final_case_id)

                # 5.2 批量更新/新增步骤信息（递归处理）
                step_result: Dict[str, Any] = await AUTOTEST_API_STEP_CRUD.batch_update_or_create_steps(steps_data)
                logger.info(
                    f"步骤处理完成："
                    f"新增 {step_result['created_count']} 个，"
                    f"更新 {step_result['updated_count']} 个，"
                    f"删除 {step_result.get('deleted_count', 0)} 个，"
                    f"失败 {len(step_result['failed_steps'])} 个"
                )

                # 6. 构建返回结果
                result_data: Dict[str, Any] = {
                    "case_update": case_result,
                    "step_update": step_result
                }

                # 7. 判断是否有失败项
                total_failed: int = len(failed_cases) + len(step_result["failed_steps"])
                if total_failed > 0:
                    message = f"批量处理完成, 但存在部分失败(用例失败数: {len(failed_cases)}, 步骤失败数: {len(step_result['failed_steps'])})"
                    logger.warning(message)
                    return SuccessResponse(data=result_data, message=message)
                else:
                    action_type = "更新" if is_update else "新增"
                    deleted_info = f"/删除 {step_result.get('deleted_count', 0)} 个" if step_result.get('deleted_count',
                                                                                                        0) > 0 else ""
                    message = f"{action_type}成功：用例{'更新' if is_update else '新增'} {created_count + updated_count} 个，步骤新增 {step_result['created_count']} 个/更新 {step_result['updated_count']} 个{deleted_info}"
                    logger.info(message)
                    return SuccessResponse(
                        data=result_data,
                        message=message
                    )
        except Exception as transaction_error:
            # 事务会自动回滚
            logger.error(f"批量处理过程中发生异常，事务已回滚: {str(transaction_error)}", exc_info=True)
            raise

    except NotFoundException as e:
        return NotFoundResponse(message=str(e))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e))
    except Exception as e:
        logger.error(f"批量处理失败，异常描述: {str(e)}", exc_info=True)
        return FailureResponse(message=f"批量处理失败，异常描述: {str(e)}")


@autotest_step.post("/http/debugging", summary="调试HTTP请求", description="实时调试HTTP请求，不保存到数据库")
async def debug_http_request(
        step_data: AutoTestHttpDebugRequest = Body(..., description="HTTP步骤调试数据")
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
                                extracted_value = resolve_json_path(response_json, expr)
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
                                actual_value = resolve_json_path(response_json, expr)
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
                            success = compare_assertion(actual_value, operation, expected_value)
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

        return SuccessResponse(data=result_data, message="调试请求成功")

    except Exception as e:
        logger.error(f"调试HTTP请求失败，异常描述: {str(e)}", exc_info=True)
        return FailureResponse(message=f"调试失败，异常描述: {str(e)}")


@autotest_step.post("/execute", summary="执行测试步骤树", description="运行/调试用例步骤树，生成报告与明细")
async def execute_step_tree(
        request: AutoTestStepTreeExecute = Body(..., description="执行请求参数")
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

        # 转换数据库格式的数据：处理conditions从数组转为JSON字符串
        def normalize_step(step: Dict[str, Any]) -> Dict[str, Any]:
            """规范化步骤数据格式"""
            step = step.copy()

            # 处理conditions：如果是数组，取第一个并转为JSON字符串
            conditions = step.get("conditions")
            if isinstance(conditions, list) and len(conditions) > 0:
                condition_obj = conditions[0]
                step["conditions"] = json.dumps(condition_obj, ensure_ascii=False)
            elif conditions is None:
                step["conditions"] = None

            # extract_variables和assert_validators保持数组格式（执行引擎已支持）
            # 移除不需要的字段
            step.pop("case", None)
            step.pop("quote_case", None)

            # 递归处理children和quote_steps
            if "children" in step and isinstance(step["children"], list):
                step["children"] = [normalize_step(child) for child in step["children"]]
            if "quote_steps" in step and isinstance(step["quote_steps"], list):
                step["quote_steps"] = [normalize_step(quote_step) for quote_step in step["quote_steps"]]

            return step

        # 收集所有步骤的defined_variables作为初始变量
        def collect_defined_variables(steps_list: List[Dict[str, Any]]) -> Dict[str, Any]:
            """递归收集所有步骤的defined_variables"""
            variables = {}
            for step in steps_list:
                defined_vars = step.get("defined_variables")
                if isinstance(defined_vars, dict):
                    variables.update(defined_vars)
                # 递归处理children和quote_steps
                children = step.get("children", [])
                quote_steps = step.get("quote_steps", [])
                variables.update(collect_defined_variables(children))
                variables.update(collect_defined_variables(quote_steps))
            return variables

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
            # 1. 查询用例信息
            case_instance = await AUTOTEST_API_CASE_CRUD.get_by_id(case_id)
            if not case_instance:
                return NotFoundResponse(message=f"用例(id={case_id})信息不存在")
            case_dict = await case_instance.to_dict()
            case_info = {
                "id": case_dict.get("id"),
                "case_code": case_dict.get("case_code"),
                "case_name": case_dict.get("case_name"),
            }

            # 2. 查询步骤树数据
            tree_data = await AUTOTEST_API_STEP_CRUD.get_by_case_id(case_id)
            if not tree_data:
                return BadReqResponse(message="用例没有步骤数据")
            if isinstance(tree_data, list) and tree_data and isinstance(tree_data[-1], dict) and "total_steps" in \
                    tree_data[-1]:
                tree_data.pop(-1)

            # 3. 规范化步骤数据
            tree_data = [normalize_step(step) for step in tree_data]

            # 4. 收集defined_variables
            all_defined_variables = collect_defined_variables(tree_data)
            merged_initial_variables = dict(initial_variables)
            merged_initial_variables.update(all_defined_variables)

            # 5. 获取根步骤
            root_steps = [s for s in tree_data if s.get("parent_step_id") is None]
            if not root_steps:
                return BadReqResponse(message="没有可执行的根步骤")

            # 6. 使用事务执行并保存到数据库
            try:
                async with in_transaction():
                    engine = AutoTestStepExecutionEngine(save_report=True)
                    results, logs, report_code, statistics, _ = await engine.execute_case(
                        case=case_info,
                        steps=root_steps,
                        initial_variables=merged_initial_variables
                    )

                    # 返回运行模式的简化结果
                    result_data = {
                        "success": statistics.get("failed_steps", 0) == 0,
                        "total_steps": statistics.get("total_steps", 0),
                        "success_steps": statistics.get("success_steps", 0),
                        "failed_steps": statistics.get("failed_steps", 0),
                        "pass_ratio": statistics.get("pass_ratio", 0.0),
                        "report_code": report_code,
                        "saved_to_database": True
                    }

                    return SuccessResponse(data=result_data, message="执行步骤成功并已保存到数据库")
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
            tree_data = [normalize_step(step) for step in tree_data]

            # 4. 收集defined_variables
            all_defined_variables = collect_defined_variables(tree_data)
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

            return SuccessResponse(data=result_data, message="调试执行完成")

    except NotFoundException as e:
        return NotFoundResponse(message=str(e))
    except Exception as e:
        logger.error(f"执行步骤失败，异常描述: {str(e)}", exc_info=True)
        return FailureResponse(message=f"执行失败，异常描述: {str(e)}")
