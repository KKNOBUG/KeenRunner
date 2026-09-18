# -*- coding: utf-8 -*-
"""
压测数据作业视图：/perf/job/* 路由编排(参数接收 -> 服务调用 -> 统一响应)。

作业是压测的带外作业资产(造数/校验/清理), 执行复用 autotest 功能链经
{port}_perf 队列异步跑; 执行状态经 /status 轻量轮询, 执行观测大字段
(error_message)随 /get 详情读取。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_job_view.py
@DateTime: 2026/9/17 18:00
"""
import traceback
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Query
from tortoise.expressions import Q

from backend.applications.performance.dependencies import PerfServices, get_perf_api_services
from backend.applications.performance.schemas.perf_job_schema import (
    PerfJobCreate,
    PerfJobLocate,
    PerfJobSelect,
)
from backend.applications.performance.services.perf_job_service import PerfJobService
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
    DataBaseStorageResponse,
)

perf_job = APIRouter()

# 作业序列化统一排除脚手架字段(对齐 dataset/task 视图模式)
JOB_EXCLUDE_FIELDS = {
    "state",
    "created_user", "created_time",
    "updated_user", "updated_time",
    "reserve_1", "reserve_2", "reserve_3",
}
JOB_REPLACE_FIELDS = {"id": "job_id"}

# 执行状态轻量轮询返回列(status端点供前端任务态轮询复用, 不下发大字段)
JOB_STATUS_FIELDS = (
    "id", "job_code", "status", "celery_id", "error_message",
    "result_dataset_id", "result_rows", "report_code", "updated_time",
)


@perf_job.post("/create", summary="新增压测数据作业", description="新增压测数据作业(prepare作业需声明提取列与归属接口)")
async def create_perf_job(
        job_in: PerfJobCreate = Body(..., description="压测数据作业信息"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    新增压测数据作业。

    :param job_in: 压测数据作业入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.job_curd.create_perf_job(job_in=job_in)
        data = await instance.to_dict(exclude_fields=JOB_EXCLUDE_FIELDS, replace_fields=JOB_REPLACE_FIELDS)
        return SuccessResponse(message="新增成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增压测数据作业失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {str(e)}")


@perf_job.post("/search", summary="查询压测数据作业列表", description="根据条件分页查询压测数据作业列表信息(Body, 不含失败原因大字段)")
async def search_perf_jobs(
        job_in: PerfJobSelect = Body(..., description="查询条件"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据条件查询压测数据作业。

    :param job_in: 压测数据作业入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if job_in.job_id:
            q &= Q(id=job_in.job_id)
        if job_in.job_code:
            q &= Q(job_code=job_in.job_code)
        if job_in.job_name:
            q &= Q(job_name__contains=job_in.job_name)
        if job_in.job_type:
            q &= Q(job_type=job_in.job_type)
        if job_in.status:
            q &= Q(status=job_in.status)
        if job_in.quote_case_id:
            q &= Q(quote_case_id=job_in.quote_case_id)
        if job_in.bind_scene_id:
            q &= Q(bind_scene_id=job_in.bind_scene_id)
        if job_in.created_user:
            q &= Q(created_user=job_in.created_user)
        if job_in.updated_user:
            q &= Q(updated_user=job_in.updated_user)
        q &= Q(state=job_in.state)
        total, rows = await services.job_curd.select_perf_jobs(
            search=q,
            page=job_in.page,
            page_size=job_in.page_size,
            order=job_in.order
        )
        # 列表走显式取列(字典行), 统一主键别名后直接下发
        data: List[Dict[str, Any]] = [{**row, "job_id": row.pop("id", None)} for row in rows]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件分页查询压测数据作业列表信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@perf_job.post("/run", summary="执行压测数据作业", description="立即执行数据作业(置排队后经{port}_perf队列异步跑脚本用例N轮)")
async def run_perf_job(
        job_in: PerfJobLocate = Body(..., description="作业执行入参"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    立即执行压测数据作业。

    :param job_in: 作业定位入参(job_id/job_code二选一)
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await PerfJobService.run_job(job_in=job_in)
        from backend.celery_scheduler.tasks.task_perf_data_job import run_perf_data_job
        from backend.services.ctx import get_current_username
        # 队列路由统一走 celery_config.task_routes({port}_perf), 禁止硬编码queue
        run_perf_data_job.apply_async(
            kwargs={"job_code": instance.job_code, "created_user": get_current_username()}
        )
        LOGGER.info(f"下发执行压测数据作业成功，job_id={instance.id}, job_code={instance.job_code}")
        data = await instance.to_dict(exclude_fields=JOB_EXCLUDE_FIELDS, replace_fields=JOB_REPLACE_FIELDS)
        return SuccessResponse(message="已下发执行，请稍后查看作业状态", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"执行压测数据作业失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"执行失败，异常描述: {str(e)}")


@perf_job.get("/status", summary="查询作业执行状态", description="轻量轮询数据作业执行状态与执行观测字段(供前端任务态轮询)")
async def get_perf_job_status(
        job_id: Optional[int] = Query(None, description="作业ID"),
        job_code: Optional[str] = Query(None, description="作业标识代码"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    轻量轮询数据作业执行状态。

    :param job_id: 数据作业主键ID
    :param job_code: 数据作业业务标识
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应, data含status/celery_id/error_message/result_dataset_id/result_rows/report_code
    """
    try:
        if job_id:
            instance = await services.job_curd.get_by_id(job_id=job_id, on_error=True, state__not=1)
        else:
            instance = await services.job_curd.get_by_code(job_code=job_code, on_error=True, state__not=1)
        data = await instance.to_dict(include_fields=JOB_STATUS_FIELDS, replace_fields=JOB_REPLACE_FIELDS)
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询压测数据作业执行状态失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@perf_job.delete("/delete", summary="删除压测数据作业", description="根据id或code删除压测数据作业信息(执行中禁止删除)")
async def delete_perf_job(
        job_id: Optional[int] = Query(None, description="作业ID"),
        job_code: Optional[str] = Query(None, description="作业标识代码"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据id或code删除压测数据作业。

    :param job_id: 数据作业主键ID
    :param job_code: 数据作业业务标识
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.job_curd.delete_perf_job(job_id=job_id, job_code=job_code)
        data = await instance.to_dict(exclude_fields=JOB_EXCLUDE_FIELDS, replace_fields=JOB_REPLACE_FIELDS)
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code删除压测数据作业信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")
