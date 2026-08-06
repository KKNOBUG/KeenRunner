# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_detail_view
@DateTime: 2025/11/27 14:25
"""
import traceback
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Body, Query, Depends
from tortoise.expressions import Q

from backend.applications.aotutest.dependencies import AutoTestApiServices, get_autotest_api_services
from backend.applications.aotutest.schemas.autotest_detail_schema import (
    AutoTestApiDetailCreate,
    AutoTestApiDetailUpdate,
    AutoTestApiDetailSelect
)
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
)
from backend.core.responses import (
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    NotFoundResponse,
    DataBaseStorageResponse
)

autotest_detail = APIRouter()


@autotest_detail.post("/create", summary="新增明细")
async def create_step_detail(
        detail_in: AutoTestApiDetailCreate = Body(..., description="明细信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    新增明细。

    :param detail_in: 明细入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.detail_curd.create_detail(detail_in)
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
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增明细失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {e}")


@autotest_detail.delete("/delete", summary="删除明细", description="根据id或code删除明细信息")
async def delete_detail(
        detail_id: Optional[int] = Query(None, description="明细ID"),
        step_code: Optional[str] = Query(None, description="步骤标识代码"),
        report_code: Optional[str] = Query(None, description="报告标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code删除明细。

    :param detail_id: 明细主键ID
    :param step_code: 步骤业务标识
    :param report_code: 报告业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.detail_curd.delete_detail(
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
        LOGGER.info(f"根据id或code删除明细成功, 结果明细: {data}")
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code删除明细失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@autotest_detail.post("/update", summary="更新明细", description="根据id或code更新明细信息")
async def update_detail(
        detail_in: AutoTestApiDetailUpdate = Body(..., description="明细信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code更新明细。

    :param detail_in: 明细入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.detail_curd.update_detail(detail_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "detail_id"}
        )
        LOGGER.info(f"根据id或code更新明细成功, 结果明细: {data}")
        return SuccessResponse(message="更新成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code更新明细失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {e}")


@autotest_detail.get("/get", summary="查询明细", description="根据id或code查询明细信息")
async def get_step_detail(
        detail_id: Optional[int] = Query(None, description="明细ID"),
        step_code: Optional[str] = Query(None, description="步骤标识代码"),
        report_code: Optional[str] = Query(None, description="报告标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code查询明细。

    :param detail_id: 明细主键ID
    :param step_code: 步骤业务标识
    :param report_code: 报告业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if detail_id:
            instance = await services.detail_curd.get_by_id(detail_id=detail_id, on_error=True, state__not=1)
        elif step_code and report_code:
            instance = await services.detail_curd.get_by_conditions(
                only_one=True,
                on_error=True,
                step_code=step_code,
                report_code=report_code,
                state__not=1,
            )
        else:
            return ParameterResponse(message="查询明细失败, 请传detail_id或(step_code与report_code)")
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "detail_id"}
        )
        LOGGER.info(f"根据id或code查询明细成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询明细失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_detail.post("/search", summary="查询明细列表", description="根据条件分页查询明细列表信息(Body)")
async def search_step_details(
        detail_in: AutoTestApiDetailSelect = Body(..., description="查询条件"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据条件查询明细。

    :param detail_in: 明细入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if detail_in.case_id:
            q &= Q(case_id=detail_in.case_id)
        if detail_in.case_code:
            q &= Q(case_code=detail_in.case_code)
        if detail_in.report_code:
            q &= Q(report_code=detail_in.report_code)
        if detail_in.step_id:
            q &= Q(step_id=detail_in.step_id)
        if detail_in.step_no:
            q &= Q(step_no=detail_in.step_no)
        if detail_in.step_code:
            q &= Q(step_code=detail_in.step_code)
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
        total, instances = await services.detail_curd.select_details(
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
            detail_serializes.append(serialize)
        LOGGER.info(f"根据条件查询明细成功, 结果数量: {total}")
        return SuccessResponse(message="查询成功", data=detail_serializes, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件查询明细失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")
