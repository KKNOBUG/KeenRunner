# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_detail_view
@DateTime: 2025/11/27 14:25
"""
from typing import Optional

from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend.applications.aotutest.schemas.autotest_detail_schema import (
    AutoTestApiDetailCreate,
    AutoTestApiDetailUpdate,
    AutoTestApiDetailSelect
)
from backend.applications.aotutest.services.autotest_detail_crud import AUTOTEST_API_DETAIL_CRUD
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException, ParameterException
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    NotFoundResponse, ParameterResponse,
)

autotest_detail = APIRouter()


@autotest_detail.post("/create", summary="新增一个测试步骤明细信息")
async def create_step_detail(
        detail_in: AutoTestApiDetailCreate = Body(..., description="测试用例信息")
):
    try:
        instance = await AUTOTEST_API_DETAIL_CRUD.create_step_detail(detail_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data, message="创建测试步骤明细成功")
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"创建测试步骤明细失败，异常描述: {str(e)}")


@autotest_detail.get("/get", summary="按id查询一个测试步骤明细信息")
async def get_step_detail(
        detail_id: int = Query(..., description="测试用例ID")
):
    try:
        instance = await AUTOTEST_API_DETAIL_CRUD.get_by_id(detail_id)
        if not instance:
            return NotFoundResponse(message=f"测试步骤明细(id={detail_id})信息不存在")
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except Exception as e:
        return FailureResponse(message=f"查询步骤明细失败，异常描述: {str(e)}")


@autotest_detail.post("/search", summary="按条件查询多个测试步骤明细信息")
async def search_step_details(
        detail_in: AutoTestApiDetailSelect = Body(..., description="查询条件")
):
    """按条件查询多个测试用例信息"""
    try:
        q = Q()
        if detail_in.id:
            q &= Q(id=detail_in.id)
        if detail_in.case_id:
            q &= Q(case_id=detail_in.case_id)
        if detail_in.step_state is not None:
            q &= Q(step_state=detail_in.step_state)
        if detail_in.created_user:
            q &= Q(created_user=detail_in.created_user)
        if detail_in.updated_user:
            q &= Q(updated_user=detail_in.updated_user)
        if detail_in.step_type:
            q &= Q(step_type=detail_in.step_type)
        q &= Q(state=detail_in.state)
        total, instances = await AUTOTEST_API_DETAIL_CRUD.select_step_details(
            search=q,
            page=detail_in.page,
            page_size=detail_in.page_size,
            order=detail_in.order
        )
        data = [await obj.to_dict() for obj in instances]
        return SuccessResponse(data=data, total=total)
    except Exception as e:
        return FailureResponse(message=f"查询步骤明细失败，异常描述: {str(e)}")


@autotest_detail.post("/update", summary="按id或code修改一个测试步骤明细信息")
async def update_report(
        detail_in: AutoTestApiDetailUpdate = Body(..., description="测试步骤明细信息")
):
    try:
        instance = await AUTOTEST_API_DETAIL_CRUD.update_step_detail(detail_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data, message="更新测试步骤明细成功")
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"更新测试步骤明细失败，异常描述: {str(e)}")


@autotest_detail.delete("/delete", summary="按id或code删除一个测试步骤明细信息")
async def delete_report(
        detail_id: Optional[int] = Query(None, description="测试步骤明细ID"),
        step_code: Optional[str] = Query(None, description="步骤标识"),
        report_code: Optional[str] = Query(None, description="报告标识")
):
    try:
        instance = await AUTOTEST_API_DETAIL_CRUD.delete_step_detail(
            detail_id=detail_id,
            step_code=step_code,
            report_code=report_code
        )
        data = await instance.to_dict()
        return SuccessResponse(data=data, message="删除测试步骤明细成功")
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"删除测试步骤明细失败，异常描述: {str(e)}")
