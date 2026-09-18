# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_task_view.py
@DateTime: 2026/9/14 11:20
"""
import traceback
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Query, Depends
from tortoise.expressions import Q

from backend.applications.performance.dependencies import PerfServices, get_perf_api_services
from backend.applications.performance.schemas.perf_task_schema import (
    PerfTaskCreate,
    PerfTaskSelect,
    PerfTaskUpdate,
    PerfTaskLocate,
)
from backend.applications.performance.services.perf_execute_service import PerfExecuteService
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    DataAlreadyExistsException,
    ParameterException,
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

perf_task = APIRouter()

# 任务详情序列化统一排除脚手架字段(列表/详情共用, 对齐 tag/task 视图模式)
TASK_EXCLUDE_FIELDS = {
    "state",
    "created_user", "created_time",
    "updated_user", "updated_time",
    "reserve_1", "reserve_2", "reserve_3",
}
TASK_REPLACE_FIELDS = {"id": "perf_id"}


@perf_task.post("/create", summary="新增压测任务", description="新增压测任务信息")
async def create_perf_task(
        task_in: PerfTaskCreate = Body(..., description="压测任务信息"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    新增压测任务。

    :param task_in: 压测任务入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.task_curd.create_perf_task(task_in=task_in)
        data = await instance.to_dict(exclude_fields=TASK_EXCLUDE_FIELDS, replace_fields=TASK_REPLACE_FIELDS)
        return SuccessResponse(message="新增成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增压测任务失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {str(e)}")


@perf_task.delete("/delete", summary="删除压测任务", description="根据id或code删除压测任务信息")
async def delete_perf_task(
        perf_id: Optional[int] = Query(None, description="任务ID"),
        perf_code: Optional[str] = Query(None, description="任务标识代码"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据id或code删除压测任务。

    :param perf_id: 任务主键ID
    :param perf_code: 任务业务标识
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.task_curd.delete_perf_task(perf_id=perf_id, perf_code=perf_code)
        data = await instance.to_dict(exclude_fields=TASK_EXCLUDE_FIELDS, replace_fields=TASK_REPLACE_FIELDS)
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code删除压测任务信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@perf_task.post("/update", summary="更新压测任务", description="根据id或code更新压测任务信息")
async def update_perf_task(
        task_in: PerfTaskUpdate = Body(..., description="压测任务信息"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据id或code更新压测任务。

    :param task_in: 压测任务入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.task_curd.update_perf_task(task_in=task_in)
        data = await instance.to_dict(exclude_fields=TASK_EXCLUDE_FIELDS, replace_fields=TASK_REPLACE_FIELDS)
        return SuccessResponse(data=data, message="更新成功", total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code更新压测任务信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {str(e)}")


@perf_task.get("/get", summary="查询压测任务", description="根据id或code查询压测任务信息")
async def get_perf_task(
        perf_id: Optional[int] = Query(None, description="任务ID"),
        perf_code: Optional[str] = Query(None, description="任务标识代码"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据id或code查询压测任务。

    :param perf_id: 任务主键ID
    :param perf_code: 任务业务标识
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if perf_id:
            instance = await services.task_curd.get_by_id(perf_id=perf_id, on_error=True, state__not=1)
        else:
            instance = await services.task_curd.get_by_code(perf_code=perf_code, on_error=True, state__not=1)
        data = await instance.to_dict(exclude_fields=TASK_EXCLUDE_FIELDS, replace_fields=TASK_REPLACE_FIELDS)
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询压测任务信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@perf_task.post("/search", summary="查询压测任务列表", description="根据条件分页查询压测任务列表信息(Body)")
async def search_perf_tasks(
        task_in: PerfTaskSelect = Body(..., description="查询条件"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据条件查询压测任务。

    :param task_in: 压测任务入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if task_in.perf_id:
            q &= Q(id=task_in.perf_id)
        if task_in.perf_code:
            q &= Q(perf_code=task_in.perf_code)
        if task_in.perf_project:
            q &= Q(perf_project=task_in.perf_project)
        if task_in.perf_name:
            q &= Q(perf_name__contains=task_in.perf_name)
        if task_in.load_mode:
            q &= Q(load_mode=task_in.load_mode)
        if task_in.last_execute_state:
            q &= Q(last_execute_state=task_in.last_execute_state)
        if task_in.created_user:
            q &= Q(created_user=task_in.created_user)
        if task_in.updated_user:
            q &= Q(updated_user=task_in.updated_user)
        q &= Q(state=task_in.state)
        total, instances = await services.task_curd.select_perf_tasks(
            search=q,
            page=task_in.page,
            page_size=task_in.page_size,
            order=task_in.order
        )
        data: List[Dict[str, Any]] = [
            await obj.to_dict(
                exclude_fields=TASK_EXCLUDE_FIELDS,
                replace_fields=TASK_REPLACE_FIELDS,
            )
            for obj in instances
        ]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件分页查询压测任务列表信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@perf_task.post("/run", summary="执行压测任务", description="立即执行压测任务(含场景装载闸门, 置排队后经{port}_perf队列异步施压)")
async def run_perf_task_view(
        task_in: PerfTaskLocate = Body(..., description="任务执行入参"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    立即执行压测任务。

    :param task_in: 任务执行入参(id或code二选一)
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await PerfExecuteService.run_task(task_in=task_in)
        from backend.celery_scheduler.tasks.task_performance import run_perf_task
        from backend.services.ctx import get_current_username
        # 队列路由统一走 celery_config.task_routes({port}_perf), 禁止硬编码queue
        run_perf_task.apply_async(
            kwargs={"perf_code": instance.perf_code, "created_user": get_current_username()}
        )
        LOGGER.info(f"下发执行压测任务成功，perf_id={instance.id}, perf_code={instance.perf_code}")
        data = await instance.to_dict(exclude_fields=TASK_EXCLUDE_FIELDS, replace_fields=TASK_REPLACE_FIELDS)
        return SuccessResponse(message="已下发执行，请稍后在报告中查看结果", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"执行压测任务失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"执行失败，异常描述: {str(e)}")


@perf_task.post("/stop", summary="停止压测任务", description="停止排队中或执行中的压测任务(引擎等待循环感知后杀进程组)")
async def stop_perf_task(
        task_in: PerfTaskLocate = Body(..., description="任务定位入参"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    停止压测任务。

    :param task_in: 任务定位入参(id或code二选一)
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await PerfExecuteService.stop_task(task_in=task_in)
        data = await instance.to_dict(exclude_fields=TASK_EXCLUDE_FIELDS, replace_fields=TASK_REPLACE_FIELDS)
        return SuccessResponse(message="停止指令已下发，任务将在数秒内终止", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"停止压测任务失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"停止失败，异常描述: {str(e)}")
