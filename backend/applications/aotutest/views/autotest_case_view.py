# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_view.py
@DateTime: 2025/4/28
"""
from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend.applications.aotutest.schemas.autotest_case_schema import (
    AutoTestApiCaseCreate,
    AutoTestApiCaseSelect,
    AutoTestApiCaseUpdate
)
from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    NotFoundResponse,
)

autotest_case = APIRouter()


@autotest_case.post("/create", summary="新增一个测试用例信息")
async def create_case(
        case_in: AutoTestApiCaseCreate = Body(..., description="测试用例信息")
):
    """新增一个测试用例信息"""
    try:
        instance = await AUTOTEST_API_CASE_CRUD.create_case(case_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data, message="创建测试用例成功")
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"创建失败，异常描述: {str(e)}")


@autotest_case.get("/get", summary="按id查询一个测试用例信息", description="根据id查询测试用例信息")
async def get_case(
        case_id: int = Query(..., description="测试用例ID")
):
    """按id查询一个测试用例信息"""
    try:
        instance = await AUTOTEST_API_CASE_CRUD.get_by_id(case_id)
        if not instance:
            return NotFoundResponse(message=f"测试用例(id={case_id})信息不存在")
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except Exception as e:
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_case.post("/search", summary="按条件查询多个测试用例信息", description="支持分页按条件查询测试用例信息")
async def search_cases(
        case_in: AutoTestApiCaseSelect = Body(..., description="查询条件")
):
    """按条件查询多个测试用例信息"""
    try:
        q = Q()
        if case_in.case_id:
            q &= Q(id=case_in.case_id)
        if case_in.case_name:
            q &= Q(case_name__contains=case_in.case_name)
        if case_in.case_tags:
            q &= Q(case_tags__contains=case_in.case_tags)
        if case_in.case_project:
            q &= Q(case_project=case_in.case_project)
        if case_in.case_version:
            q &= Q(case_version=case_in.case_version)
        if case_in.created_user:
            q &= Q(created_user__iexact=case_in.created_user)
        q &= Q(state=case_in.state)
        total, instances = await AUTOTEST_API_CASE_CRUD.select_cases(
            search=q,
            page=case_in.page,
            page_size=case_in.page_size,
            order=case_in.order
        )
        data = [await obj.to_dict() for obj in instances]
        return SuccessResponse(data=data, total=total)
    except Exception as e:
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_case.post("/update", summary="按id修改一个测试用例信息", description="根据id修改测试用例信息")
async def update_case(
        case_in: AutoTestApiCaseUpdate = Body(..., description="测试用例信息")
):
    """按id修改一个测试用例信息"""
    try:
        instance = await AUTOTEST_API_CASE_CRUD.update_case(case_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data, message="更新测试用例成功")
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"修改失败，异常描述: {str(e)}")


@autotest_case.delete("/delete", summary="按id删除一个测试用例信息", description="根据id删除测试用例信息")
async def delete_case(
        case_id: int = Query(..., description="测试用例ID")
):
    """按id删除一个测试用例信息"""
    try:
        instance = await AUTOTEST_API_CASE_CRUD.delete_case(case_id)
        data = await instance.to_dict()
        return SuccessResponse(data=data, message="删除测试用例成功")
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@autotest_case.delete("/delete", summary="按id查询一个测试用例信息的步骤数量")
async def get_case_step_total(
        case_id: int = Query(..., description="测试用例ID")
):
    """按id查询一个测试用例信息的步骤数量"""
    try:
        instance = await AUTOTEST_API_CASE_CRUD.delete_case(case_id)
        data = await instance.to_dict()
        return SuccessResponse(data=data, message="删除测试用例成功")
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")
