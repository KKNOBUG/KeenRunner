# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_task_view
@DateTime: 2026/1/31 12:42
"""
import os
import traceback
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query, Depends, Path
from starlette.responses import FileResponse
from tortoise.expressions import Q

from backend.applications.aotutest.dependencies import AutoTestApiServices, get_autotest_api_services
from backend.applications.aotutest.schemas.autotest_record_schema import AutoTestApiRecordSelect
from backend.applications.aotutest.schemas.autotest_task_schema import (
    AutoTestApiTaskCreate,
    AutoTestApiTaskSelect,
    AutoTestApiTaskUpdate,
)
from backend.celery_scheduler.celery_task_contract import (
    list_attachments_from_summary,
    resolve_storage_path,
)
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
    DataBaseStorageResponse,
    NotFoundResponse,
    DataAlreadyExistsResponse,
)

autotest_task = APIRouter()


@autotest_task.post("/create", summary="新增任务", description="新增任务信息")
async def create_task(
        task_in: AutoTestApiTaskCreate = Body(..., description="任务信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    新增任务。

    :param task_in: 任务入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.task_curd.create_task(task_in=task_in)
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
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增任务失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {str(e)}")


@autotest_task.delete("/delete", summary="删除任务", description="根据id或code删除任务信息")
async def delete_task(
        task_id: Optional[int] = Query(None, description="任务ID"),
        task_code: Optional[str] = Query(None, description="任务标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code删除任务。

    :param task_id: 任务主键ID
    :param task_code: 任务业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.task_curd.delete_task(task_id=task_id, task_code=task_code)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "task_id"}
        )
        LOGGER.info(f"根据id或code删除任务信息成功, 结果明细: {data}")
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code删除任务信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@autotest_task.post("/update", summary="更新任务", description="根据id或code更新任务信息")
async def update_task(
        task_in: AutoTestApiTaskUpdate = Body(..., description="任务信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code更新任务。

    :param task_in: 任务入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.task_curd.update_task(task_in=task_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "task_id"}
        )
        LOGGER.info(f"根据id或code更新任务信息成功, 结果明细: {data}")
        return SuccessResponse(data=data, message="更新成功", total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code更新任务信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {str(e)}")


@autotest_task.get("/get", summary="查询任务", description="根据id或code查询任务信息")
async def get_task(
        task_id: Optional[int] = Query(None, description="任务ID"),
        task_code: Optional[str] = Query(None, description="任务标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code查询任务。

    :param task_id: 任务主键ID
    :param task_code: 任务业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if task_id:
            instance = await services.task_curd.get_by_id(task_id=task_id, on_error=True, state__not=1)
        else:
            instance = await services.task_curd.get_by_code(task_code=task_code, on_error=True, state__not=1)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "task_id"}
        )
        LOGGER.info(f"根据id或code查询任务信息成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询任务信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_task.post("/search", summary="查询任务列表", description="根据条件分页查询任务列表信息(Body)")
async def search_tasks(
        task_in: AutoTestApiTaskSelect = Body(..., description="查询条件"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据条件查询任务。

    :param task_in: 任务入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
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
            q &= Q(created_user=task_in.created_user)
        if task_in.updated_user:
            q &= Q(updated_user=task_in.updated_user)
        if task_in.env_id:
            q &= Q(related_cases_env_id__contains=[task_in.env_id])
        if task_in.date_from:
            date_from = task_in.date_from.strip()
            if len(date_from) == 10:
                date_from = f"{date_from} 00:00:00"
            q &= Q(last_execute_time__gte=date_from)
        if task_in.date_to:
            date_to = task_in.date_to.strip()
            if len(date_to) == 10:
                date_to = f"{date_to} 23:59:59"
            q &= Q(last_execute_time__lte=date_to)
        q &= Q(state=task_in.state)
        total, instances = await services.task_curd.select_tasks(
            search=q,
            page=task_in.page,
            page_size=task_in.page_size,
            order=task_in.order
        )
        data = [
            await obj.to_dict(
                exclude_fields={
                    "state",
                    "reserve_1", "reserve_2", "reserve_3"
                },
                replace_fields={"id": "task_id"}
            ) for obj in instances
        ]
        LOGGER.info(f"根据条件分页查询任务列表信息成功, 结果数量: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件分页查询任务列表信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_task.post("/run", summary="执行任务", description="立即执行任务")
async def run_task(
        task_in: Dict[str, Any] = Body(..., description="任务ID"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    立即执行任务。

    :param task_in: 任务入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        task_id = task_in.get("task_id")
        if task_id is None:
            return ParameterResponse(message="参数[task_id]不允许为空")
        await services.task_curd.get_by_id(task_id=task_id, on_error=True, state__not=1)
        from backend.celery_scheduler.tasks.task_autotest_case import run_autotest_task
        from backend.enums import AutoTestReportType
        from backend.services.ctx import get_current_username
        # __task_id会随消息传到Worker，task_prerun从request.properties取出；
        # 只有传了__task_id，Worker端_create_task_record才会查任务表并写入record的task_id/task_name。
        # created_user 写入执行记录（Worker 无 HTTP 鉴权上下文）。
        run_autotest_task.apply_async(
            kwargs={
                "task_id": task_id,
                "report_type": AutoTestReportType.ASYNC_EXEC,
                "created_user": get_current_username(),
            },
            queue="autotest_queue",
            __task_id=task_id
        )
        LOGGER.info(f"下发执行任务成功，task_id={task_id}")
        return SuccessResponse(message="已下发执行，请稍后在报告中查看结果", data={"task_id": task_id}, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"执行任务失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"执行失败，异常描述: {e}")


@autotest_task.post("/start", summary="启动任务", description="启用任务调度")
async def start_task(
        task_in: Dict[str, Any] = Body(..., description="任务ID"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    启动任务（启用调度）。

    :param task_in: 任务入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        task_id = task_in.get("task_id")
        if task_id is None:
            return ParameterResponse(message="参数[task_id]不允许为空")
        instance = await services.task_curd.set_task_enabled(task_id=task_id, enabled=True)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3",
            },
            replace_fields={"id": "task_id"},
        )
        LOGGER.info(f"启用任务调度成功，task_id={task_id}")
        return SuccessResponse(message="任务已启动，将根据调度执行", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"启用任务调度失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"启动失败，异常描述: {e}")


@autotest_task.post("/stop", summary="停止任务", description="关闭任务调度")
async def stop_task(
        task_in: Dict[str, Any] = Body(..., description="任务ID"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    停止任务（关闭调度）。

    :param task_in: 任务入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        task_id = task_in.get("task_id")
        if task_id is None:
            return ParameterResponse(message="参数[task_id]不允许为空")
        instance = await services.task_curd.set_task_enabled(task_id=task_id, enabled=False)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3",
            },
            replace_fields={"id": "task_id"},
        )
        LOGGER.info(f"关闭任务调度成功，task_id={task_id}")
        return SuccessResponse(message="任务已停止，将不再根据调度执行", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"关闭任务调度失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"停止失败，异常描述: {e}")


@autotest_task.post("/record/search", summary="查询执行记录", description="根据条件分页查询任务执行记录(Body)")
async def search_task_records(
        record_in: AutoTestApiRecordSelect = Body(..., description="查询条件"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    任务执行记录查询。

    :param record_in: 任务执行记录查询入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        total, instances = await services.record_curd.select_records(record_in=record_in)
        data = [
            await obj.to_dict(
                exclude_fields={"created_time", "updated_time"},
                replace_fields={"id": "record_id"}
            )
            for obj in instances
        ]
        LOGGER.info(f"根据条件分页查询任务执行记录成功, 结果数量: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件分页查询任务执行记录失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_task.get("/record/{record_id}/attachments/{key}/download", summary="下载执行记录附件", description="根据记录id与附件key下载附件")
async def download_task_record_attachment(
        record_id: int = Path(..., description="执行记录主键"),
        key: str = Path(..., description="附件key，默认main"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据执行记录attachments项下载文件。

    :param record_id: 执行记录主键
    :param key: 附件标识（信封attachments[].key）
    :param services: 自动化测试CRUD依赖聚合
    :return: 文件流响应
    """
    try:
        record = await services.record_curd.get_or_none(id=record_id, state__not=1)
        if not record:
            return ParameterResponse(message=f"执行记录不存在: record_id={record_id}")
        attachments = list_attachments_from_summary(getattr(record, "task_summary", None))
        want = (key or "main").strip()
        item = next((a for a in attachments if str(a.get("key") or "") == want), None)
        # 仅一项且未带 key 的旧数据：允许用 main 取唯一附件
        if item is None and want == "main" and len(attachments) == 1:
            item = attachments[0]
        if not item or not item.get("storage_key"):
            return ParameterResponse(message=f"附件不存在: key={want}")
        file_path = resolve_storage_path(str(item["storage_key"]))
        if not os.path.isfile(file_path):
            return ParameterResponse(message="附件文件不存在或已过期清理")
        file_name = str(item.get("name") or os.path.basename(file_path))
        return FileResponse(
            path=file_path,
            media_type=str(item.get("content_type") or "application/octet-stream"),
            filename=file_name,
        )
    except ValueError as e:
        return ParameterResponse(message=str(e))
    except Exception as e:
        LOGGER.error(f"根据记录id与附件key下载附件失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"下载失败，异常描述: {str(e)}")
