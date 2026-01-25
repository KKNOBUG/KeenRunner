# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_detail_view
@DateTime: 2025/11/27 14:25
"""
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend import LOGGER
from backend.applications.aotutest.schemas.autotest_detail_schema import (
    AutoTestApiDetailCreate,
    AutoTestApiDetailUpdate,
    AutoTestApiDetailSelect
)
from backend.applications.aotutest.services.autotest_detail_crud import AUTOTEST_API_DETAIL_CRUD
from backend.applications.aotutest.services.autotest_step_crud import AUTOTEST_API_STEP_CRUD
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    ParameterException,
    DataAlreadyExistsException, DataBaseStorageException,
)
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    ParameterResponse, DataBaseStorageResponse,
)

autotest_detail = APIRouter()


@autotest_detail.post("/create", summary="API自动化测试-新增明细")
async def create_step_detail(
        detail_in: AutoTestApiDetailCreate = Body(..., description="明细信息")
):
    try:
        instance = await AUTOTEST_API_DETAIL_CRUD.create_detail(detail_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "detail_id"}
        )
        LOGGER.info(f"新增明细成功, 结果明细: {data}")
        return SuccessResponse(message="新增成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述: {e}")


@autotest_detail.delete("/delete", summary="API自动化测试-按id或code删除明细")
async def delete_report(
        detail_id: Optional[int] = Query(None, description="明细ID"),
        step_code: Optional[str] = Query(None, description="步骤标识代码"),
        report_code: Optional[str] = Query(None, description="报告标识代码")
):
    try:
        instance = await AUTOTEST_API_DETAIL_CRUD.delete_detail(
            detail_id=detail_id,
            step_code=step_code,
            report_code=report_code
        )
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "detail_id"}
        )
        LOGGER.info(f"按id或code删除明细成功, 结果明细: {data}")
        return SuccessResponse(message="删除成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@autotest_detail.post("/update", summary="API自动化测试-按id或code更新明细")
async def update_report(
        detail_in: AutoTestApiDetailUpdate = Body(..., description="明细信息")
):
    try:
        instance = await AUTOTEST_API_DETAIL_CRUD.update_detail(detail_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "detail_id"}
        )
        LOGGER.info(f"按id或code更新明细成功, 结果明细: {data}")
        return SuccessResponse(message="更新成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"更新失败，异常描述: {e}")


@autotest_detail.get("/get", summary="API自动化测试-按id或code查询明细")
async def get_step_detail(
        detail_id: Optional[int] = Query(None, description="明细ID"),
        step_code: Optional[str] = Query(None, description="步骤标识代码"),
        report_code: Optional[str] = Query(None, description="报告标识代码"),
):
    try:
        if detail_id:
            instance = await AUTOTEST_API_DETAIL_CRUD.get_by_id(detail_id=detail_id, on_error=True)
        else:
            instance = await AUTOTEST_API_DETAIL_CRUD.get_by_conditions(
                only_one=True,
                on_error=True,
                conditions={"step_code": step_code, "report_code": report_code}
            )
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "detail_id"}
        )
        LOGGER.info(f"按id或code查询明细成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_detail.post("/search", summary="API自动化测试-按条件查询明细")
async def search_step_details(
        detail_in: AutoTestApiDetailSelect = Body(..., description="查询条件")
):
    try:
        q = Q()
        if detail_in.case_id:
            q &= Q(case_id=detail_in.case_id)
        if detail_in.case_code:
            q &= Q(case_code__contains=detail_in.case_code)
        if detail_in.report_code:
            q &= Q(report_code__contains=detail_in.report_code)
        if detail_in.step_id:
            q &= Q(step_id=detail_in.step_id)
        if detail_in.step_no:
            q &= Q(step_no=detail_in.step_no)
        if detail_in.step_code:
            q &= Q(step_code__contains=detail_in.step_code)
        if detail_in.step_type:
            q &= Q(step_type=detail_in.step_type.value)
        if detail_in.step_state is not None:
            q &= Q(step_state=detail_in.step_state)
        if detail_in.detail_id:
            q &= Q(id=detail_in.detail_id)
        if detail_in.created_user:
            q &= Q(created_user__iexact=detail_in.created_user)
        if detail_in.updated_user:
            q &= Q(updated_user__iexact=detail_in.updated_user)
        q &= Q(state=detail_in.state)
        total, instances = await AUTOTEST_API_DETAIL_CRUD.select_details(
            search=q,
            page=detail_in.page,
            page_size=detail_in.page_size,
            order=detail_in.order
        )
        detail_serializes: List[Dict[str, Any]] = []
        for instance in instances:
            serialize: Dict[str, Any] = await instance.to_dict(
                exclude_fields={
                    "state",
                    "created_user", "updated_user",
                    "created_time", "updated_time",
                    "reserve_1", "reserve_2", "reserve_3"
                },
                replace_fields={"id": "detail_id"}
            )
            step_id: int = serialize["step_id"]
            step_instance = await AUTOTEST_API_STEP_CRUD.get_by_id(
                on_error=True,
                step_id=step_id
            )
            serialize["step"] = await step_instance.to_dict(
                exclude_fields={
                    "state",
                    "created_user", "updated_user",
                    "created_time", "updated_time",
                    "reserve_1", "reserve_2", "reserve_3"
                },
                replace_fields={"id": "step_id"}
            )
            detail_serializes.append(serialize)
        LOGGER.info(f"按条件查询明细成功, 结果数量: {total}")
        return SuccessResponse(message="查询成功", data=detail_serializes, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")
