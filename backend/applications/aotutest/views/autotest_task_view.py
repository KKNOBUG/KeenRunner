# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_task_view
@DateTime: 2026/1/31 12:42
"""
import traceback
from typing import Optional

from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend import LOGGER
from backend.applications.aotutest.schemas.autotest_task_schema import (
    AutoTestApiTaskCreate,
    AutoTestApiTaskSelect,
    AutoTestApiTaskUpdate
)
from backend.applications.aotutest.services.autotest_task_crud import AUTOTEST_API_TASK_CRUD
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    DataAlreadyExistsException,
    ParameterException,
    DataBaseStorageException,
)
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    DataBaseStorageResponse,
)

autotest_task = APIRouter()


@autotest_task.post("/create", summary="API自动化测试-新增任务")
async def create_task_info(task_in: AutoTestApiTaskCreate = Body(..., description="任务信息")):
    try:
        instance = await AUTOTEST_API_TASK_CRUD.create_task(task_in=task_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "task_id"}
        )
        LOGGER.info(f"新增任务成功, 结果明细: {data}")
        return SuccessResponse(message="新增成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增任务失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {str(e)}")


@autotest_task.delete("/delete", summary="API自动化测试-按id或code删除任务")
async def delete_task_info(
        task_id: Optional[int] = Query(None, description="任务ID"),
        task_code: Optional[str] = Query(None, description="任务标识代码"),
):
    try:
        instance = await AUTOTEST_API_TASK_CRUD.delete_task(task_id=task_id, task_code=task_code)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "task_id"}
        )
        LOGGER.info(f"按id或code删除任务成功, 结果明细: {data}")
        return SuccessResponse(message="删除成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code删除任务失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@autotest_task.post("/update", summary="API自动化测试-按id或code更新任务")
async def update_task_info(task_in: AutoTestApiTaskUpdate = Body(..., description="任务信息")):
    try:
        instance = await AUTOTEST_API_TASK_CRUD.update_task(task_in=task_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "task_id"}
        )
        LOGGER.info(f"按id或code更新任务成功, 结果明细: {data}")
        return SuccessResponse(data=data, message="更新成功", total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code更新任务失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {str(e)}")


@autotest_task.get("/get", summary="API自动化测试-按id或code查询任务")
async def get_task_info(
        task_id: Optional[int] = Query(None, description="任务ID"),
        task_code: Optional[str] = Query(None, description="任务标识代码"),
):
    try:
        if task_id:
            instance = await AUTOTEST_API_TASK_CRUD.get_by_id(task_id=task_id, on_error=True)
        else:
            instance = await AUTOTEST_API_TASK_CRUD.get_by_code(task_code=task_code, on_error=True)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "task_id"}
        )
        LOGGER.info(f"按id或code查询任务成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code查询任务失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_task.post("/search", summary="API自动化测试-按条件查询任务")
async def search_tasks_info(
        task_in: AutoTestApiTaskSelect = Body(..., description="查询条件")
):
    try:
        q = Q()
        if task_in.task_id:
            q &= Q(id=task_in.task_id)
        if task_in.task_code:
            q &= Q(task_code=task_in.task_code)
        if task_in.task_env:
            q &= Q(task_env__contains=task_in.task_env)
        if task_in.task_name:
            q &= Q(task_name__contains=task_in.task_name)
        if task_in.task_project:
            q &= Q(task_project=task_in.task_project)
        if task_in.created_user:
            q &= Q(created_user__iexact=task_in.created_user)
        if task_in.updated_user:
            q &= Q(updated_user__iexact=task_in.updated_user)
        q &= Q(state=task_in.state)
        total, instances = await AUTOTEST_API_TASK_CRUD.select_tasks(
            search=q,
            page=task_in.page,
            page_size=task_in.page_size,
            order=task_in.order
        )
        data = [
            await obj.to_dict(
                exclude_fields={
                    "state",
                    "created_user", "created_time",
                    "updated_user", "updated_time",
                    "reserve_1", "reserve_2", "reserve_3"
                },
                replace_fields={"id": "task_id"}
            ) for obj in instances
        ]
        LOGGER.info(f"按条件查询任务成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"按条件查询任务失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")
