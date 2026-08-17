# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_transfer_view.py
@DateTime: 2026/8/17
"""
import traceback
from typing import Optional

from fastapi import APIRouter, Body, Query, Depends
from tortoise.expressions import Q

from backend.applications.aotutest.dependencies import AutoTestApiServices, get_autotest_api_services
from backend.applications.aotutest.schemas.autotest_case_transfer_schema import (
    AutoTestApiCaseTransferCreate,
    AutoTestApiCaseTransferSelect,
)
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataAlreadyExistsException,
    DataBaseStorageException,
)
from backend.core.responses import (
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    NotFoundResponse,
    DataBaseStorageResponse,
    DataAlreadyExistsResponse,
)

autotest_case_transfer = APIRouter()


@autotest_case_transfer.post("/create", summary="转让用例", description="将用例所属人转让给指定人员并写入转让记录")
async def transfer_case(
        transfer_in: AutoTestApiCaseTransferCreate = Body(..., description="转让信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    转让用例所属人。

    :param transfer_in: 转让入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.case_transfer_curd.transfer_case(transfer_in)
        data = await instance.to_dict(replace_fields={"id": "transfer_id"})
        return SuccessResponse(message="转让成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"转让用例失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"转让失败，异常描述: {e}")


@autotest_case_transfer.get("/get", summary="查询转让记录", description="根据转让记录ID查询单条转让记录")
async def get_case_transfer(
        transfer_id: Optional[int] = Query(None, description="转让记录ID"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据转让记录ID查询单条转让记录。

    :param transfer_id: 转让记录主键ID
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.case_transfer_curd.get_by_id(transfer_id=transfer_id, on_error=True)
        data = await instance.to_dict(replace_fields={"id": "transfer_id"})
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询用例转让记录失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_case_transfer.post("/search", summary="查询转让记录列表", description="根据条件分页查询转让记录(Body)")
async def search_case_transfers(
        transfer_in: AutoTestApiCaseTransferSelect = Body(..., description="查询条件"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据条件分页查询转让记录。

    :param transfer_in: 查询入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if transfer_in.transfer_id:
            q &= Q(id=transfer_in.transfer_id)
        if transfer_in.case_id:
            q &= Q(case_id=transfer_in.case_id)
        if transfer_in.prev_owner_user:
            q &= Q(prev_owner_user=transfer_in.prev_owner_user)
        if transfer_in.next_owner_user:
            q &= Q(next_owner_user=transfer_in.next_owner_user)
        if transfer_in.created_user:
            q &= Q(created_user=transfer_in.created_user)
        if transfer_in.involve_user:
            q &= Q(prev_owner_user=transfer_in.involve_user) | Q(next_owner_user=transfer_in.involve_user)
        if transfer_in.created_time_begin:
            date_from = transfer_in.created_time_begin.strip()
            if len(date_from) == 10:
                date_from = f"{date_from} 00:00:00"
            q &= Q(created_time__gte=date_from)
        if transfer_in.created_time_end:
            date_to = transfer_in.created_time_end.strip()
            if len(date_to) == 10:
                date_to = f"{date_to} 23:59:59"
            q &= Q(created_time__lte=date_to)

        total, instances = await services.case_transfer_curd.select_transfers(
            search=q,
            page=transfer_in.page,
            page_size=transfer_in.page_size,
            order=transfer_in.order,
        )
        data = [await obj.to_dict(replace_fields={"id": "transfer_id"}) for obj in instances]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"分页查询用例转让记录失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")
