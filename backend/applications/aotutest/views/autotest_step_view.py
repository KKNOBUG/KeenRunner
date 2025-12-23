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

from backend.applications.aotutest.schemas.autotest_step_schema import (
    AutoTestApiStepCreate, AutoTestApiStepUpdate,
    AutoTestStepSelect, AutoTestStepTreeUpdateList, AutoTestStepTreeUpdateItem,
    AutoTestHttpDebugRequest
)
from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
from backend.applications.aotutest.services.autotest_step_crud import AUTOTEST_API_STEP_CRUD
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    NotFoundResponse,
    BadReqResponse,
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
        if step_in.id:
            q &= Q(id=step_in.id)
        if step_in.case_id:
            q &= Q(case_id=step_in.case_id)
        if step_in.step_type:
            q &= Q(step_type=step_in.step_type)
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


@autotest_step.post("/update/tree", summary="批量更新测试用例和步骤信息")
async def batch_update_steps_tree(
        steps: AutoTestStepTreeUpdateList = Body(..., description="步骤树数据（数组嵌套字典）")
):
    """
    批量更新测试用例和步骤信息

    核心功能：
    1. 验证数据是否符合模型要求（如果数组中只有一个字典对象且该字典对象只有一个"case"键，则仅更新/新增测试用例）
    2. 接收嵌套结构的步骤树数据
    3. 提取并去重测试用例信息，批量更新或新增
    4. 递归处理所有层级的步骤，批量更新或新增
    5. 验证用例信息和步骤信息的关联正确性
    6. 使用事务保证原子性（要么全部成功，要么全部回滚）

    入参格式：
    - 外层是步骤数组
    - 每个步骤包含：步骤信息、case字段（测试用例信息）、children字段（子步骤数组）

    返回格式：
    - 成功：返回更新成功的提示 + 影响的用例数 / 步骤数 + 详细的用例和步骤信息
    - 失败：返回失败原因
    """
    try:
        steps_data: List[AutoTestStepTreeUpdateItem] = steps.steps
        logger.info(f"开始批量更新步骤树，共 {len(steps_data)} 个根步骤")

        # 1. 验证数据是否符合模型要求
        # 如果数组中只有一个字典对象且该字典对象只有一个"case"键，说明该测试用例不存在步骤信息
        if len(steps_data) == 1:
            first_step: AutoTestStepTreeUpdateItem = steps_data[0]
            # 检查是否只有case字段，没有其他步骤相关字段
            # 排除children、quote_steps、quote_case这些不影响判断的字段
            step_dict: Dict[str, Any] = first_step.model_dump(exclude={"children", "quote_steps", "quote_case"},
                                                              exclude_none=True)
            # 如果除了case字段和id字段外，没有其他有效字段，则认为只有case信息
            has_step_info = False if list(step_dict.keys()) == ["case"] else True

            if not has_step_info and first_step.case:
                # 只有case信息，没有步骤信息，仅处理用例
                logger.info("检测到只有用例信息，没有步骤信息，仅处理用例")
                case: Dict[str, Any] = first_step.case
                if isinstance(case, dict):
                    # 为后续映射增加输入key，便于新增后回传id
                    # case["_input_key"] = "only_case_0"
                    cases_data = [case]
                else:
                    return BadReqResponse(message="用例信息格式不正确")

                # 使用事务执行批量更新/新增用例
                try:
                    async with in_transaction():
                        case_result = await AUTOTEST_API_CASE_CRUD.batch_update_or_create_cases(cases_data)
                        logger.info(
                            f"用例处理完成：新增 {case_result['created_count']} 个，更新 {case_result['updated_count']} 个，失败 {len(case_result['failed_cases'])} 个")

                        result_data = {
                            "case_update": {
                                "created_count": case_result["created_count"],
                                "updated_count": case_result["updated_count"],
                                "failed_count": len(case_result["failed_cases"]),
                                "failed_cases": case_result["failed_cases"],
                                "cases": case_result.get("cases", [])
                            },
                            "step_update": {
                                "created_count": 0,
                                "updated_count": 0,
                                "failed_count": 0,
                                "failed_steps": [],
                                "steps": []
                            }
                        }

                        total_failed = len(case_result["failed_cases"])
                        if total_failed > 0:
                            message = f"用例处理完成，但存在部分失败：失败 {total_failed} 个"
                            logger.warning(message)
                            return SuccessResponse(data=result_data, message=message)
                        else:
                            message = f"用例处理成功：新增 {case_result['created_count']} 个，更新 {case_result['updated_count']} 个"
                            logger.info(message)
                            return SuccessResponse(data=result_data, message=message)
                except Exception as transaction_error:
                    logger.error(f"用例处理过程中发生异常，事务已回滚: {str(transaction_error)}", exc_info=True)
                    raise

        # 2. 提取所有 case 数据并去重（支持没有id的新增场景）
        cases_data: List[Dict[str, Any]] = []
        case_ids_seen = set()

        def extract_cases_recursive(step_list: List[AutoTestStepTreeUpdateItem]):
            """递归提取所有 case 数据"""
            for step in step_list:
                # 提取 case 字段
                case: Dict[str, Any] = step.case
                if isinstance(case, dict) and case.get("id"):
                    case_id: int = case["id"]
                    if case_id not in case_ids_seen:
                        cases_data.append(case)
                        case_ids_seen.add(case_id)

                # 递归处理子步骤
                children = step.children
                if children:
                    extract_cases_recursive(children)

        extract_cases_recursive(steps_data)
        logger.info(f"提取到 {len(cases_data)} 个唯一用例，准备处理")

        # 3. 使用事务执行批量更新/新增
        try:
            # Tortoise ORM 的事务处理：使用 in_transaction 上下文管理器
            async with in_transaction():
                # 3.1 批量更新/新增测试用例信息
                case_result: Dict[str, Any] = await AUTOTEST_API_CASE_CRUD.batch_update_or_create_cases(cases_data)
                logger.info(
                    f"用例处理完成："
                    f"新增 {case_result['created_count']} 个，"
                    f"更新 {case_result['updated_count']} 个，"
                    f"失败 {len(case_result['failed_cases'])} 个"
                )

                # 3.2 批量更新/新增步骤信息（递归处理）
                step_result: Dict[str, Any] = await AUTOTEST_API_STEP_CRUD.batch_update_or_create_steps(steps_data)
                logger.info(
                    f"步骤处理完成："
                    f"新增 {step_result['created_count']} 个，"
                    f"更新 {step_result['updated_count']} 个，"
                    f"失败 {len(step_result['failed_steps'])} 个"
                )

                # 4. 构建返回结果
                result_data: Dict[str, Any] = {
                    "case_update": {
                        "created_count": case_result["created_count"],
                        "updated_count": case_result["updated_count"],
                        "failed_count": len(case_result["failed_cases"]),
                        "failed_cases": case_result["failed_cases"],
                        "cases": case_result.get("cases", [])
                    },
                    "step_update": {
                        "created_count": step_result["created_count"],
                        "updated_count": step_result["updated_count"],
                        "failed_count": len(step_result["failed_steps"]),
                        "failed_steps": step_result["failed_steps"],
                        "steps": step_result.get("steps", [])
                    }
                }

                # 5. 判断是否有失败项
                total_failed: int = len(case_result["failed_cases"]) + len(step_result["failed_steps"])
                if total_failed > 0:
                    message = f"批量处理完成，但存在部分失败：用例失败 {len(case_result['failed_cases'])} 个，步骤失败 {len(step_result['failed_steps'])} 个"
                    logger.warning(message)
                    return SuccessResponse(data=result_data, message=message)
                else:
                    message = f"批量处理成功：用例新增 {case_result['created_count']} 个/更新 {case_result['updated_count']} 个，步骤新增 {step_result['created_count']} 个/更新 {step_result['updated_count']} 个"
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
    - validators: 断言配置（数组或对象）

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
        # 提取请求参数
        # request_url = step_data.get("request_url")
        # request_method = (step_data.get("request_method") or "GET").upper()
        # request_header = step_data.get("request_header") or {}
        # request_params = step_data.get("request_params")
        # request_body = step_data.get("request_body")
        # request_form_data = step_data.get("request_form_data")
        # request_form_urlencoded = step_data.get("request_form_urlencoded")
        # request_text = step_data.get("request_text")
        # defined_variables = step_data.get("defined_variables") or {}
        # extract_variables = step_data.get("extract_variables") or []
        # validators = step_data.get("validators") or []
        # step_name = step_data.get("step_name") or "HTTP调试"
        #
        # # 验证必填参数
        # if not request_url:
        #     return BadReqResponse(message="请求URL不能为空")
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
        validators = step_data.validators or []
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
            extract_list = extract_variables if isinstance(extract_variables, list) else [extract_variables]
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
        if validators:
            # 支持数组格式的断言
            logs.append(format_log(f"断言开始"))
            validators_list = validators if isinstance(validators, list) else [validators]
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
