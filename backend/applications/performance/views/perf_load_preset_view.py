# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_load_preset_view.py
@DateTime: 2026/9/14 11:20
"""
import traceback
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Query, Depends
from tortoise.expressions import Q

from backend.applications.performance.dependencies import PerfServices, get_perf_api_services
from backend.applications.performance.schemas.perf_load_preset_schema import (
    PerfLoadPresetCreate,
    PerfLoadPresetSelect,
    PerfLoadPresetUpdate,
    PerfLoadPresetLocate,
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

perf_load_preset = APIRouter()

# 负载预设详情序列化统一排除脚手架字段(列表/详情共用, 对齐 tag/load_preset 视图模式)
PRESET_EXCLUDE_FIELDS = {
    "state",
    "created_user", "created_time",
    "updated_user", "updated_time",
    "reserve_1", "reserve_2", "reserve_3",
}
PRESET_REPLACE_FIELDS = {"id": "preset_id"}


@perf_load_preset.post("/create", summary="新增负载预设", description="新增负载预设信息")
async def create_perf_preset(
        preset_in: PerfLoadPresetCreate = Body(..., description="负载预设信息"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    新增负载预设。

    :param preset_in: 负载预设入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.preset_curd.create_perf_preset(preset_in=preset_in)
        data = await instance.to_dict(exclude_fields=PRESET_EXCLUDE_FIELDS, replace_fields=PRESET_REPLACE_FIELDS)
        return SuccessResponse(message="新增成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增负载预设失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {str(e)}")


@perf_load_preset.delete("/delete", summary="删除负载预设", description="根据id或code删除负载预设信息")
async def delete_perf_preset(
        preset_id: Optional[int] = Query(None, description="负载预设ID"),
        preset_code: Optional[str] = Query(None, description="负载预设标识代码"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据id或code删除负载预设。

    :param preset_id: 负载预设主键ID
    :param preset_code: 负载预设业务标识
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.preset_curd.delete_perf_preset(preset_id=preset_id, preset_code=preset_code)
        data = await instance.to_dict(exclude_fields=PRESET_EXCLUDE_FIELDS, replace_fields=PRESET_REPLACE_FIELDS)
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code删除负载预设信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@perf_load_preset.post("/update", summary="更新负载预设", description="根据id或code更新负载预设信息")
async def update_perf_preset(
        preset_in: PerfLoadPresetUpdate = Body(..., description="负载预设信息"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据id或code更新负载预设。

    :param preset_in: 负载预设入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.preset_curd.update_perf_preset(preset_in=preset_in)
        data = await instance.to_dict(exclude_fields=PRESET_EXCLUDE_FIELDS, replace_fields=PRESET_REPLACE_FIELDS)
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
        LOGGER.error(f"根据id或code更新负载预设信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {str(e)}")


@perf_load_preset.get("/get", summary="查询负载预设", description="根据id或code查询负载预设信息")
async def get_perf_load_preset(
        preset_id: Optional[int] = Query(None, description="负载预设ID"),
        preset_code: Optional[str] = Query(None, description="负载预设标识代码"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据id或code查询负载预设。

    :param preset_id: 负载预设主键ID
    :param preset_code: 负载预设业务标识
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if preset_id:
            instance = await services.preset_curd.get_by_id(preset_id=preset_id, on_error=True, state__not=1)
        else:
            instance = await services.preset_curd.get_by_code(preset_code=preset_code, on_error=True, state__not=1)
        data = await instance.to_dict(exclude_fields=PRESET_EXCLUDE_FIELDS, replace_fields=PRESET_REPLACE_FIELDS)
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询负载预设信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@perf_load_preset.post("/search", summary="查询负载预设列表", description="根据条件分页查询负载预设列表信息(Body)")
async def search_perf_load_presets(
        preset_in: PerfLoadPresetSelect = Body(..., description="查询条件"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据条件查询负载预设。

    :param preset_in: 负载预设入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if preset_in.preset_id:
            q &= Q(id=preset_in.preset_id)
        if preset_in.preset_code:
            q &= Q(preset_code=preset_in.preset_code)
        if preset_in.preset_project:
            q &= Q(preset_project=preset_in.preset_project)
        if preset_in.preset_name:
            q &= Q(preset_name__contains=preset_in.preset_name)
        if preset_in.load_mode:
            q &= Q(load_mode=preset_in.load_mode)
        if preset_in.last_execute_state:
            q &= Q(last_execute_state=preset_in.last_execute_state)
        if preset_in.created_user:
            q &= Q(created_user=preset_in.created_user)
        if preset_in.updated_user:
            q &= Q(updated_user=preset_in.updated_user)
        q &= Q(state=preset_in.state)
        total, instances = await services.preset_curd.select_perf_presets(
            search=q,
            page=preset_in.page,
            page_size=preset_in.page_size,
            order=preset_in.order
        )
        data: List[Dict[str, Any]] = [
            await obj.to_dict(
                exclude_fields=PRESET_EXCLUDE_FIELDS,
                replace_fields=PRESET_REPLACE_FIELDS,
            )
            for obj in instances
        ]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件分页查询负载预设列表信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@perf_load_preset.post("/run", summary="执行负载预设", description="立即执行负载预设(含场景装载闸门, 置排队后经{port}_perf队列异步施压)")
async def run_perf_load_preset_view(
        preset_in: PerfLoadPresetLocate = Body(..., description="负载预设执行入参"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    立即执行负载预设。

    :param preset_in: 负载预设执行入参(id或code二选一)
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await PerfExecuteService.run_preset(preset_in=preset_in)
        from backend.celery_scheduler.tasks.task_performance import run_perf_preset
        from backend.services.ctx import get_current_username
        # 队列路由统一走 celery_config.task_routes({port}_perf), 禁止硬编码queue
        run_perf_preset.apply_async(
            kwargs={"preset_code": instance.preset_code, "created_user": get_current_username()}
        )
        LOGGER.info(f"下发执行负载预设成功，preset_id={instance.id}, preset_code={instance.preset_code}")
        data = await instance.to_dict(exclude_fields=PRESET_EXCLUDE_FIELDS, replace_fields=PRESET_REPLACE_FIELDS)
        return SuccessResponse(message="已下发执行，请稍后在报告中查看结果", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"执行负载预设失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"执行失败，异常描述: {str(e)}")


@perf_load_preset.post("/stop", summary="停止负载预设", description="停止排队中或执行中的负载预设(引擎等待循环感知后杀进程组)")
async def stop_perf_load_preset(
        preset_in: PerfLoadPresetLocate = Body(..., description="负载预设定位入参"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    停止负载预设。

    :param preset_in: 负载预设定位入参(id或code二选一)
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await PerfExecuteService.stop_preset(preset_in=preset_in)
        data = await instance.to_dict(exclude_fields=PRESET_EXCLUDE_FIELDS, replace_fields=PRESET_REPLACE_FIELDS)
        return SuccessResponse(message="停止指令已下发，负载预设将在数秒内终止", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"停止负载预设失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"停止失败，异常描述: {str(e)}")
