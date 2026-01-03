# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_view.py
@DateTime: 2025/4/28
"""
from typing import Optional

from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend.applications.aotutest.schemas.autotest_case_schema import (
    AutoTestApiCaseCreate,
    AutoTestApiCaseSelect,
    AutoTestApiCaseUpdate
)
from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    ParameterException,
    DataAlreadyExistsException,
    DataBaseStorageException,
)
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    NotFoundResponse,
    ParameterResponse,
    DataBaseStorageResponse,
    DataAlreadyExistsResponse,
)

autotest_case = APIRouter()


@autotest_case.post("/create", summary="API自动化测试-新增用例")
async def create_case(
        case_in: AutoTestApiCaseCreate = Body(..., description="用例信息")
):
    try:
        instance = await AUTOTEST_API_CASE_CRUD.create_case(case_in)
        data = await instance.to_dict(
            exclude_fields={"state", "created_user", "updated_user", "created_time", "updated_time"},
            replace_fields={"id": "case_id"}
        )
        return SuccessResponse(message="新增成功", data=data, total=1)
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述: {e}")


@autotest_case.delete("/delete", summary="API自动化测试-按id或code删除用例")
async def delete_case(
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
):
    try:
        instance = await AUTOTEST_API_CASE_CRUD.delete_case(case_id=case_id, case_code=case_code)
        data = await instance.to_dict(
            exclude_fields={"state", "created_user", "updated_user", "created_time", "updated_time"},
            replace_fields={"id": "case_id"}
        )
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@autotest_case.post("/update", summary="API自动化测试-按id或code更新除用例")
async def update_case(
        case_in: AutoTestApiCaseUpdate = Body(..., description="用例信息")
):
    try:
        instance = await AUTOTEST_API_CASE_CRUD.update_case(case_in)
        data = await instance.to_dict(
            exclude_fields={"state", "created_user", "updated_user", "created_time", "updated_time"},
            replace_fields={"id": "case_id"}
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
        return FailureResponse(message=f"更新失败，异常描述: {e}")


@autotest_case.get("/get", summary="API自动化测试-按id或code查询用例")
async def get_case(
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
):
    try:
        if case_id:
            instance = await AUTOTEST_API_CASE_CRUD.get_by_id(case_id=case_id, on_error=True)
        else:
            instance = await AUTOTEST_API_CASE_CRUD.get_by_code(case_code=case_code, on_error=True)
        data = await instance.to_dict(
            exclude_fields={"state", "created_user", "updated_user", "created_time", "updated_time"},
            replace_fields={"id": "case_id"}
        )
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_case.post("/search", summary="API自动化测试-按条件查询用例")
async def search_cases(
        case_in: AutoTestApiCaseSelect = Body(..., description="查询条件")
):
    try:
        q = Q()
        if case_in.case_id:
            q &= Q(id=case_in.case_id)
        if case_in.case_code:
            q &= Q(case_code__contains=case_in.case_code)
        if case_in.case_name:
            q &= Q(case_name__contains=case_in.case_name)
        if case_in.case_tags:
            q &= Q(case_tags__contains=case_in.case_tags)
        if case_in.case_type:
            q &= Q(case_type=case_in.case_type.value)
        if case_in.case_steps:
            q &= Q(case_steps__gte=case_in.case_steps)
        if case_in.case_project:
            q &= Q(case_project=case_in.case_project)
        if case_in.case_version:
            q &= Q(case_version__gte=case_in.case_version)
        if case_in.created_user:
            q &= Q(created_user__iexact=case_in.created_user)
        if case_in.updated_user:
            q &= Q(updated_user__iexact=case_in.updated_user)
        q &= Q(state=case_in.state)
        total, instances = await AUTOTEST_API_CASE_CRUD.select_cases(
            search=q,
            page=case_in.page,
            page_size=case_in.page_size,
            order=case_in.order
        )
        data = [
            await obj.to_dict(
                exclude_fields={"state", "created_user", "updated_user", "created_time", "updated_time"},
                replace_fields={"id": "case_id"}
            ) for obj in instances
        ]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")
