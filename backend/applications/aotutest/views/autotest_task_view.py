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
from backend.applications.aotutest.schemas.autotest_record_schema import AutoTestApiRecordSelect
from backend.applications.aotutest.schemas.autotest_task_schema import (
    AutoTestApiTaskCreate,
    AutoTestApiTaskSelect,
    AutoTestApiTaskUpdate,
)
from backend.applications.aotutest.services.autotest_record_crud import AUTOTEST_API_RECORD_CRUD
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


@autotest_task.post("/run", summary="API自动化测试-立即执行任务")
async def run_task_info(task_in: dict = Body(..., description="任务ID")):
    """立即执行指定任务（下发 Celery 异步执行）。"""
    try:
        task_id = task_in.get("task_id")
        if task_id is None:
            return ParameterResponse(message="参数 task_id 不能为空")
        await AUTOTEST_API_TASK_CRUD.get_by_id(task_id=task_id, on_error=True)
        from backend.celery_scheduler.tasks.task_autotest_case import run_autotest_task
        from backend.enums.autotest_enum import AutoTestReportType
        # __task_id 会随消息传到 Worker，task_prerun 从 request.properties 取出；
        # 只有传了 __task_id，Worker 端 _create_task_record 才会查任务表并写入 record 的 task_id/task_name。
        run_autotest_task.apply_async(
            kwargs={
                "task_id": task_id,
                "report_type": AutoTestReportType.ASYNC_EXEC,
            },
            queue="autotest_queue",
            __task_id=task_id
        )
        LOGGER.info(f"已下发执行任务 task_id={task_id}")
        return SuccessResponse(message="已下发执行，请稍后在报告中查看结果", data={"task_id": task_id}, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"执行任务失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"执行失败, 异常描述: {e}")


@autotest_task.post("/start", summary="API自动化测试-启动任务（启用调度）")
async def start_task_info(task_in: dict = Body(..., description="任务ID")):
    """将任务设为启用，使其被定时扫描并按时执行。"""
    try:
        task_id = task_in.get("task_id")
        if task_id is None:
            return ParameterResponse(message="参数 task_id 不能为空")
        instance = await AUTOTEST_API_TASK_CRUD.set_task_enabled(task_id=task_id, enabled=True)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3",
            },
            replace_fields={"id": "task_id"},
        )
        LOGGER.info(f"已启动任务 task_id={task_id}")
        return SuccessResponse(message="任务已启动，将按调度执行", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"启动任务失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"启动失败, 异常描述: {e}")


@autotest_task.post("/stop", summary="API自动化测试-停止任务（关闭调度）")
async def stop_task_info(task_in: dict = Body(..., description="任务ID")):
    """将任务设为未启动（task_enabled=False），不再被定时扫描执行。"""
    try:
        task_id = task_in.get("task_id")
        if task_id is None:
            return ParameterResponse(message="参数 task_id 不能为空")
        instance = await AUTOTEST_API_TASK_CRUD.set_task_enabled(task_id=task_id, enabled=False)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3",
            },
            replace_fields={"id": "task_id"},
        )
        LOGGER.info(f"已停止任务 task_id={task_id}")
        return SuccessResponse(message="任务已停止，将不再按调度执行", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"停止任务失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"停止失败, 异常描述: {e}")


@autotest_task.post("/record/search", summary="API自动化测试-任务执行记录查询")
async def search_task_records(record_in: AutoTestApiRecordSelect = Body(..., description="查询条件")):
    """按条件分页查询任务执行记录（Celery 调度任务ID、任务信息ID、任务名称、状态、调度方式、开始/结束时间等）。"""
    try:
        total, instances = await AUTOTEST_API_RECORD_CRUD.select_records(record_in=record_in)
        data = [
            await obj.to_dict(
                exclude_fields={"created_time", "updated_time"},
                replace_fields={"id": "record_id"}
            )
            for obj in instances
        ]
        LOGGER.info(f"按条件查询任务执行记录成功, 结果数量: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询任务执行记录失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 异常描述: {str(e)}")
