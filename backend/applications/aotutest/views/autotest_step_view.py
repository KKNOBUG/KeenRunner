# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_view.py
@DateTime: 2025/4/28
"""
from typing import List, Dict, Any
import logging

from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from backend.applications.aotutest.schemas.autotest_step_schema import (
    AutoTestApiStepCreate,
    AutoTestStepSelect,
    AutoTestApiStepUpdate,
    AutoTestStepTreeUpdateList, AutoTestStepTreeUpdateItem
)
from backend.applications.aotutest.services.autotest_step_crud import AUTOTEST_API_STEP_CRUD
from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    NotFoundResponse,
    BadReqResponse, ParameterResponse,
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
    1. 接收嵌套结构的步骤树数据
    2. 提取并去重测试用例信息，批量更新
    3. 递归处理所有层级的步骤，批量更新
    4. 使用事务保证原子性（要么全部成功，要么全部回滚）

    入参格式：
    - 外层是步骤数组
    - 每个步骤包含：步骤信息、case字段（测试用例信息）、children字段（子步骤数组）

    返回格式：
    - 成功：返回更新成功的提示 + 影响的用例数 / 步骤数
    - 失败：返回失败原因
    """
    try:
        steps_data: List[AutoTestStepTreeUpdateItem] = steps.steps
        logger.info(f"开始批量更新步骤树，共 {len(steps_data)} 个根步骤")

        # 2. 提取所有 case 数据并去重
        cases_data = []
        case_ids_seen = set()

        def extract_cases_recursive(step_list: List[AutoTestStepTreeUpdateItem]):
            """递归提取所有 case 数据"""
            for step in step_list:
                # 提取 case 字段
                case = step.case
                if isinstance(case, dict) and case.get("id"):
                    case_id = case["id"]
                    if case_id not in case_ids_seen:
                        cases_data.append(case)
                        case_ids_seen.add(case_id)

                # 递归处理子步骤
                children = step.children
                if children:
                    extract_cases_recursive(children)

        extract_cases_recursive(steps_data)
        logger.info(f"提取到 {len(cases_data)} 个唯一用例，准备更新")

        # 3. 使用事务执行批量更新
        try:
            # Tortoise ORM 的事务处理：使用 in_transaction 上下文管理器
            async with in_transaction():
                # 3.1 批量更新测试用例信息
                case_result = await AUTOTEST_API_CASE_CRUD.batch_update_cases(cases_data)
                logger.info(f"用例更新完成：成功 {case_result['updated_count']} 个，失败 {len(case_result['failed_cases'])} 个")

                # 3.2 批量更新步骤信息（递归处理）
                step_result = await AUTOTEST_API_STEP_CRUD.batch_update_steps(steps_data)
                logger.info(f"步骤更新完成：成功 {step_result['updated_count']} 个，失败 {len(step_result['failed_steps'])} 个")

                # 4. 构建返回结果
                result_data = {
                    "case_update": {
                        "updated_count": case_result["updated_count"],
                        "failed_count": len(case_result["failed_cases"]),
                        "failed_cases": case_result["failed_cases"]
                    },
                    "step_update": {
                        "updated_count": step_result["updated_count"],
                        "failed_count": len(step_result["failed_steps"]),
                        "failed_steps": step_result["failed_steps"]
                    }
                }

                # 5. 判断是否有失败项
                total_failed = len(case_result["failed_cases"]) + len(step_result["failed_steps"])
                if total_failed > 0:
                    message = f"批量更新完成，但存在部分失败：用例失败 {len(case_result['failed_cases'])} 个，步骤失败 {len(step_result['failed_steps'])} 个"
                    logger.warning(message)
                    return SuccessResponse(
                        data=result_data,
                        message=message
                    )
                else:
                    message = f"批量更新成功：用例 {case_result['updated_count']} 个，步骤 {step_result['updated_count']} 个"
                    logger.info(message)
                    return SuccessResponse(
                        data=result_data,
                        message=message
                    )
        except Exception as transaction_error:
            # 事务会自动回滚
            logger.error(f"批量更新过程中发生异常，事务已回滚: {str(transaction_error)}", exc_info=True)
            raise

    except NotFoundException as e:
        return NotFoundResponse(message=str(e))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e))
    except Exception as e:
        logger.error(f"批量更新失败，异常描述: {str(e)}", exc_info=True)
        return FailureResponse(message=f"批量更新失败，异常描述: {str(e)}")
