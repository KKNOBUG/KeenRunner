# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_view.py
@DateTime: 2025/4/28
"""
import logging
from typing import List, Dict, Any

from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from backend.applications.aotutest.schemas.autotest_step_schema import (
    AutoTestApiStepCreate, AutoTestApiStepUpdate,
    AutoTestStepSelect, AutoTestStepTreeUpdateList, AutoTestStepTreeUpdateItem
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
