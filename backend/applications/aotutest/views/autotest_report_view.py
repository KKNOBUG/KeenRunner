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

from fastapi import APIRouter, Body, Query, Depends
from tortoise.expressions import Q

from backend.applications.aotutest.dependencies import AutoTestApiServices, get_autotest_api_services
from backend.applications.aotutest.schemas.autotest_report_schema import (
    AutoTestApiReportCreate,
    AutoTestApiReportSelect,
    AutoTestApiReportUpdate,
    AutoTestApiReportBatchSelect,
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

autotest_report = APIRouter()


@autotest_report.post("/create", summary="新增报告", description="新增报告信息")
async def create_report(
        report_in: AutoTestApiReportCreate = Body(..., description="报告信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    新增报告。

    :param report_in: 报告入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.report_curd.create_report(report_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "report_id"}
        )
        return SuccessResponse(message="新增成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增报告失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {str(e)}")


@autotest_report.delete("/delete", summary="删除报告", description="根据id或code删除报告信息")
async def delete_report(
        report_id: Optional[int] = Query(None, description="报告ID"),
        report_code: Optional[str] = Query(None, description="报告代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code删除报告。

    :param report_id: 报告主键ID
    :param report_code: 报告业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.report_curd.delete_report(report_id=report_id, report_code=report_code)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "report_id"}
        )
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code删除报告信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@autotest_report.post("/update", summary="更新报告", description="根据id或code更新报告信息")
async def update_report(
        report_in: AutoTestApiReportUpdate = Body(..., description="报告信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code更新报告。

    :param report_in: 报告入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.report_curd.update_report(report_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "report_id"}
        )
        return SuccessResponse(message="更新成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code更新报告信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {str(e)}")


@autotest_report.get("/get", summary="查询报告", description="根据id或code查询报告信息")
async def get_report(
        report_id: Optional[int] = Query(None, description="报告ID"),
        report_code: Optional[str] = Query(None, description="报告标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code查询报告。

    :param report_id: 报告主键ID
    :param report_code: 报告业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if report_id:
            instance = await services.report_curd.get_by_id(report_id=report_id, on_error=True, state__not=1)
        else:
            instance = await services.report_curd.get_by_code(report_code=report_code, on_error=True, state__not=1)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "report_id"}
        )
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询报告信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_report.post("/search", summary="查询报告列表", description="根据条件分页查询报告列表信息(Body)")
async def search_reports(
        report_in: AutoTestApiReportSelect = Body(..., description="查询条件"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    按条件分页查询报告列表。

    :param report_in: 报告查询入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if report_in.case_id:
            q &= Q(case_id=report_in.case_id)
        if report_in.case_code:
            q &= Q(case_code=report_in.case_code)
        if report_in.case_name:
            # 报告表无case_name，先根据用例名称查出case_id再过滤
            matched_case_ids = await services.case_curd.model.filter(
                case_name__contains=report_in.case_name.strip(),
                state__not=1,
            ).values_list("id", flat=True)
            if not matched_case_ids:
                return SuccessResponse(message="查询成功", data=[], total=0)
            q &= Q(case_id__in=list(matched_case_ids))
        if report_in.report_id:
            q &= Q(id=report_in.report_id)
        if report_in.report_code:
            q &= Q(report_code__contains=report_in.report_code)
        if report_in.report_type:
            q &= Q(report_type=report_in.report_type.value)
        # 与 zzt 一致：始终按 task_code 精确匹配；未传时等价于 IS NULL
        if report_in.exclude_task_code:
            q &= Q(task_code__isnull=True) | Q(task_code="")
        else:
            q &= Q(task_code=report_in.task_code)
        if report_in.batch_code:
            q &= Q(batch_code__contains=report_in.batch_code)
        if report_in.case_state is not None:
            q &= Q(case_state=report_in.case_state)
        if report_in.created_user:
            q &= Q(created_user=report_in.created_user)
        if report_in.updated_user:
            q &= Q(updated_user=report_in.updated_user)
        if report_in.step_pass_ratio:
            q &= Q(step_pass_ratio__gte=report_in.step_pass_ratio)
        # 执行时间范围：根据case_st_time筛选，仅日期时补全为当天起止
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
        total, instances = await services.report_curd.select_reports(
            search=q,
            page=report_in.page,
            page_size=report_in.page_size,
            order=report_in.order
        )
        case_ids = [obj.case_id for obj in instances]
        unique_case_ids = list(set(case_ids))
        case_name_map = {}
        if unique_case_ids:
            case_name_map = dict(
                await services.case_curd.model.filter(
                    id__in=unique_case_ids,
                    state__not=1
                ).values_list("id", "case_name")
            )
        report_instances = await asyncio.gather(*[
            obj.to_dict(
                exclude_fields={
                    "state",
                    "created_user",
                    "created_time",
                    "reserve_1",
                    "reserve_2",
                    "reserve_3",
                },
                replace_fields={"id": "report_id"},
            )
            for obj in instances
        ])
        data = []
        for item in report_instances:
            ratio = item.get("step_pass_ratio", 0) or 0
            try:
                item["step_pass_ratio"] = f"{round(float(ratio), 2)}%"
            except (TypeError, ValueError):
                item["step_pass_ratio"] = "0.0%"
            item["case_name"] = case_name_map.get(item["case_id"], "")
            data.append(item)
        return SuccessResponse(message="报告列表查询成功", data=data, total=total)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件分页查询报告列表信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_report.post("/search_batches", summary="查询任务执行历史", description="按task_code聚合batch_code计算成功/部分成功/失败状态")
async def search_report_batches(
        batch_in: AutoTestApiReportBatchSelect = Body(..., description="批次查询条件"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    任务执行历史专用：按批次聚合报告并返回执行结果。

    :param batch_in: 含必填task_code；page/page_size针对批次数
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        total, batches = await services.report_curd.search_batches(batch_in)
        data = [item.model_dump(mode="json") for item in batches]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按task_code聚合batch_code计算成功/部分成功/失败状态失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")
