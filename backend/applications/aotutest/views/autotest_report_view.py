# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_report_view
@DateTime: 2025/11/27 09:33
"""
import asyncio
import traceback
from typing import Optional

from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend import LOGGER
from backend.applications.aotutest.schemas.autotest_report_schema import (
    AutoTestApiReportCreate, AutoTestApiReportSelect, AutoTestApiReportUpdate
)
from backend.applications.aotutest.services.autotest_report_crud import AUTOTEST_API_REPORT_CRUD
from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
from backend.core.exceptions.base_exceptions import (
    DataAlreadyExistsException,
    NotFoundException,
    ParameterException, DataBaseStorageException
)
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    DataBaseStorageResponse,
)

autotest_report = APIRouter()


@autotest_report.post("/create", summary="API自动化测试-新增报告")
async def create_report(
        report_in: AutoTestApiReportCreate = Body(..., description="报告信息")
):
    try:
        instance = await AUTOTEST_API_REPORT_CRUD.create_report(report_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "report_id"}
        )
        LOGGER.info(f"新增报告成功, 结果明细: {data}")
        return SuccessResponse(message="新增成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增报告失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {str(e)}")


@autotest_report.delete("/delete", summary="API自动化测试-按id或code删除报告")
async def delete_report(
        report_id: Optional[int] = Query(None, description="报告ID"),
        report_code: Optional[str] = Query(None, description="报告代码")
):
    try:
        instance = await AUTOTEST_API_REPORT_CRUD.delete_report(report_id=report_id, report_code=report_code)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "report_id"}
        )
        LOGGER.info(f"按id或code删除报告成功, 结果明细: {data}")
        return SuccessResponse(message="删除成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code删除报告失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@autotest_report.post("/update", summary="API自动化测试-按id或code更新报告")
async def update_report(
        report_in: AutoTestApiReportUpdate = Body(..., description="报告信息")
):
    try:
        instance = await AUTOTEST_API_REPORT_CRUD.update_report(report_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "report_id"}
        )
        LOGGER.info(f"按id或code更新报告成功, 结果明细: {data}")
        return SuccessResponse(message="更新成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code更新报告失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {str(e)}")


@autotest_report.get("/get", summary="API自动化测试-按id或code查询报告")
async def get_report(
        report_id: Optional[int] = Query(None, description="报告ID"),
        report_code: Optional[str] = Query(None, description="报告标识代码"),
):
    try:
        if report_id:
            instance = await AUTOTEST_API_REPORT_CRUD.get_by_id(report_id=report_id, on_error=True)
        else:
            instance = await AUTOTEST_API_REPORT_CRUD.get_by_code(report_code=report_code, on_error=True)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "report_id"}
        )
        LOGGER.info(f"按id或code查询报告成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code查询报告失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询测试报告失败，异常描述: {e}")


@autotest_report.post("/search", summary="API自动化测试-按条件查询报告")
async def search_reports(
        report_in: AutoTestApiReportSelect = Body(..., description="查询条件")
):
    try:
        q = Q()
        if report_in.case_id:
            q &= Q(case_id=report_in.case_id)
        if report_in.case_code:
            q &= Q(case_code=report_in.case_code)
        if report_in.report_id:
            q &= Q(id=report_in.report_id)
        if report_in.report_code:
            q &= Q(report_code=report_in.report_code)
        if report_in.report_type:
            q &= Q(report_type=report_in.report_type.value)
        if report_in.task_code:
            q &= Q(task_code__contains=report_in.task_code)
        if report_in.batch_code:
            q &= Q(batch_code__contains=report_in.batch_code)
        if report_in.case_state is not None:
            q &= Q(case_state=report_in.case_state)
        if report_in.created_user:
            q &= Q(created_user__iexact=report_in.created_user)
        if report_in.updated_user:
            q &= Q(updated_user__iexact=report_in.updated_user)
        if report_in.step_pass_ratio:
            q &= Q(step_pass_ratio__gte=report_in.step_pass_ratio)
        # 执行时间范围：按 case_st_time 筛选，仅日期时补全为当天起止
        if report_in.date_from:
            date_from = report_in.date_from.strip()
            if len(date_from) == 10:  # YYYY-MM-DD
                date_from = f"{date_from} 00:00:00"
            q &= Q(case_st_time__gte=date_from)
        if report_in.date_to:
            date_to = report_in.date_to.strip()
            if len(date_to) == 10:
                date_to = f"{date_to} 23:59:59"
            q &= Q(case_st_time__lte=date_to)
        q &= Q(state=report_in.state)
        total, instances = await AUTOTEST_API_REPORT_CRUD.select_reports(
            search=q,
            page=report_in.page,
            page_size=report_in.page_size,
            order=report_in.order
        )
        # 批量获取 case_id 并查询 case_name
        data = []
        case_ids = [obj.case_id for obj in instances]
        unique_case_ids = list(set(case_ids))
        case_name_map = {}
        if unique_case_ids:
            case_name_map = dict(
                await AUTOTEST_API_CASE_CRUD.model.filter(
                    id__in=unique_case_ids,
                    state__not=1
                ).values_list("id", "case_name")
            )
        # 并发执行所有 to_dict 操作（核心：用gather批量处理异步任务）
        report_instances = await asyncio.gather(*[
            obj.to_dict(
                exclude_fields={"state", "created_time", "updated_time", "reserve_1", "reserve_2", "reserve_3"},
                replace_fields={"id": "report_id"}
            )
            for obj in instances
        ])
        # 用列表推导式填充 case_name 并生成最终数据
        data = [
            {**item, "case_name": case_name_map.get(item["case_id"], "")}
            for item in report_instances
        ]
        LOGGER.info(f"按条件查询报告成功, 结果数量: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception as e:
        LOGGER.error(f"按条件查询报告失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 异常描述: {str(e)}")
