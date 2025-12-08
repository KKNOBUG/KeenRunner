# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_report_view
@DateTime: 2025/11/27 09:33
"""
from typing import Optional

from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend.applications.aotutest.schemas.autotest_report_schema import (
    AutoTestApiReportCreate, AutoTestApiReportSelect, AutoTestApiReportUpdate
)
from backend.applications.aotutest.services.autotest_report_crud import AUTOTEST_API_REPORT_CRUD
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException, ParameterException
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    DataAlreadyExistsResponse,
    NotFoundResponse,
)

autotest_report = APIRouter()


@autotest_report.post("/create", summary="新增一个测试报告信息")
async def create_report(
        report_in: AutoTestApiReportCreate = Body(..., description="测试用例信息")
):
    """新增一个测试报告信息"""
    try:
        instance = await AUTOTEST_API_REPORT_CRUD.create_report(report_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data, message="创建测试报告成功")
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"创建测试报告失败，异常描述: {str(e)}")


@autotest_report.get("/get", summary="按id查询一个测试报告信息", description="根据id查询测试报告信息")
async def get_report(
        report_id: int = Query(..., description="测试报告ID")
):
    """按id查询一个测试用例信息"""
    try:
        instance = await AUTOTEST_API_REPORT_CRUD.get_by_id(report_id)
        if not instance:
            return NotFoundResponse(message=f"测试报告(id={report_id})信息不存在")
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except Exception as e:
        return FailureResponse(message=f"查询测试报告失败，异常描述: {str(e)}")


@autotest_report.post("/search", summary="按条件查询多个测试报告信息", description="支持分页按条件查询测试报告信息")
async def search_reports(
        report_in: AutoTestApiReportSelect = Body(..., description="查询条件")
):
    """按条件查询多个测试用例信息"""
    try:
        q = Q()
        if report_in.id:
            q &= Q(id=report_in.id)
        if report_in.case_id:
            q &= Q(case_id=report_in.case_id)
        if report_in.case_name:
            q &= Q(case_name__contains=report_in.case_name)
        if report_in.case_state is not None:
            q &= Q(case_state=report_in.case_state)
        if report_in.created_user:
            q &= Q(created_user=report_in.created_user)
        if report_in.updated_user:
            q &= Q(updated_user=report_in.updated_user)
        q &= Q(state=report_in.state)
        total, instances = await AUTOTEST_API_REPORT_CRUD.select_reports(
            search=q,
            page=report_in.page,
            page_size=report_in.page_size,
            order=report_in.order
        )
        data = [await obj.to_dict() for obj in instances]
        return SuccessResponse(data=data, total=total)
    except Exception as e:
        return FailureResponse(message=f"查询测试报告失败，异常描述: {str(e)}")


@autotest_report.post("/update", summary="按id或code修改一个测试报告信息", description="根据id或code修改测试报告信息")
async def update_report(
        report_in: AutoTestApiReportUpdate = Body(..., description="测试用例信息")
):
    """按id或code修改一个测试报告信息"""
    try:
        instance = await AUTOTEST_API_REPORT_CRUD.update_report(report_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data, message="更新测试报告成功")
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"更新测试报告失败，异常描述: {str(e)}")


@autotest_report.delete("/delete", summary="按id或code删除一个测试报告信息", description="根据id或code删除测试报告信息")
async def delete_report(
        report_id: Optional[int] = Query(None, description="测试报告ID"),
        report_code: Optional[str] = Query(None, description="测试报告代码")
):
    """按id或code删除一个测试报告信息"""
    try:
        instance = await AUTOTEST_API_REPORT_CRUD.delete_report(report_id=report_id, report_code=report_code)
        data = await instance.to_dict()
        return SuccessResponse(data=data, message="删除测试报告成功")
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"删除测试报告失败，异常描述: {str(e)}")
