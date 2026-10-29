# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_task_view
@DateTime: 2026/1/31 12:42
"""
import os
import traceback
from typing import Optional

from fastapi import APIRouter, Body, Query, Depends, Path
from starlette.responses import FileResponse
from tortoise.expressions import Q

from backend.applications.autotest.dependencies import AutoTestServices, get_autotest_api_services
from backend.applications.autotest.models.autotest_env_config_model import AutoTestEnvBindModel
from backend.applications.autotest.models.autotest_env_model import AutoTestEnvModel
from backend.applications.autotest.schemas.autotest_record_schema import AutoTestRecordSelect, AutoTestRecordBatchDelete
from backend.applications.autotest.schemas.autotest_task_schema import (
    AutoTestTaskCreate,
    AutoTestTaskId,
    AutoTestTaskSchedulePreview,
    AutoTestTaskSelect,
    AutoTestTaskUpdate,
)
from backend.applications.autotest.services.autotest_scope_guard import assert_cases_readable
from backend.applications.autotest.services.autotest_task_crud import extract_steps_execute_envs
from backend.applications.autotest.services.autotest_task_schedule import (
    TaskSchedule,
    normalize_schedule,
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
    NoPermissionException,
)
from backend.core.responses import (
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    DataBaseStorageResponse,
    NotFoundResponse,
    DataAlreadyExistsResponse,
)
from backend.services import DataScope, DependTagScope, get_current_username

autotest_task = APIRouter()


@autotest_task.post("/create", summary="新增任务", description="新增任务信息")
async def create_task(
        task_in: AutoTestTaskCreate = Body(..., description="任务信息"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    新增任务。

    :param task_in: 任务入参
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，恢复软删任务时要求创建人允许当前用户写入
    :return: 统一HTTP响应
    """
    try:
        instance = await services.task_curd.create_task(task_in=task_in, scope=scope)
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
    except NoPermissionException:  # 归属校验失败需向上抛出，交由全局处理器返回403
        raise
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
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    根据id或code删除任务。

    :param task_id: 任务主键ID
    :param task_code: 任务业务标识
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，仅允许删除创建人为自己的任务
    :return: 统一HTTP响应
    """
    try:
        instance = await services.task_curd.delete_task(scope=scope, task_id=task_id, task_code=task_code)
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
    except NoPermissionException:  # 归属校验失败需向上抛出，交由全局处理器返回403
        raise
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code删除任务信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@autotest_task.post("/update", summary="更新任务", description="根据id或code更新任务信息")
async def update_task(
        task_in: AutoTestTaskUpdate = Body(..., description="任务信息"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    根据id或code更新任务。

    :param task_in: 任务入参
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，仅允许修改创建人为自己的任务
    :return: 统一HTTP响应
    """
    try:
        instance = await services.task_curd.update_task(task_in=task_in, scope=scope)
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
    except NoPermissionException:  # 归属校验失败需向上抛出，交由全局处理器返回403
        raise
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
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    根据id或code查询任务。

    :param task_id: 任务主键ID
    :param task_code: 任务业务标识
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，校验任务创建人可见性
    :return: 统一HTTP响应
    """
    try:
        if task_id:
            instance = await services.task_curd.get_by_id(task_id=task_id, on_error=True, state__not=1)
        else:
            instance = await services.task_curd.get_by_code(task_code=task_code, on_error=True, state__not=1)
        if not scope.can_read(instance.created_user):  # 详情需收口到可见范围
            raise NoPermissionException(
                message=f"查询任务失败, 任务[{instance.task_code}]创建人[{instance.created_user}]不在当前用户可见范围"
            )
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
    except NoPermissionException:  # 归属校验失败需向上抛出，交由全局处理器返回403
        raise
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询任务信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_task.post("/search", summary="查询任务列表", description="根据条件分页查询任务列表信息(Body)")
async def search_tasks(
        task_in: AutoTestTaskSelect = Body(..., description="查询条件"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    根据条件查询任务。

    :param task_in: 任务入参
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，按创建人过滤可见范围
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
        if task_in.last_execute_user:
            q &= Q(last_execute_user=task_in.last_execute_user)
        if task_in.created_user:
            q &= Q(created_user=task_in.created_user)
        if task_in.updated_user:
            q &= Q(updated_user=task_in.updated_user)
        if task_in.env_name:
            # task_involve_envs存储环境名称：前端执行环境下拉已按名称去重，直接按名称匹配
            q &= Q(task_involve_envs__contains=[task_in.env_name])
        elif task_in.env_id:
            # task_involve_envs存储环境名称：将入参env_id(环境绑定ID)转换为环境名称再匹配
            env_bind = await AutoTestEnvBindModel.get_or_none(id=task_in.env_id)
            env_name = None
            if env_bind:
                env_enum = await AutoTestEnvModel.get_or_none(id=env_bind.env_enum_id)
                env_name = env_enum.env_name if env_enum else None
            # 环境不存在时返回空结果集
            q &= Q(task_involve_envs__contains=[env_name]) if env_name else Q(pk=0)
        if task_in.execute_time_start:
            execute_time_start = task_in.execute_time_start.strip()
            if len(execute_time_start) == 10:
                execute_time_start = f"{execute_time_start} 00:00:00"
            q &= Q(last_execute_time__gte=execute_time_start)
        if task_in.execute_time_end:
            execute_time_end = task_in.execute_time_end.strip()
            if len(execute_time_end) == 10:
                execute_time_end = f"{execute_time_end} 23:59:59"
            q &= Q(last_execute_time__lte=execute_time_end)
        q &= Q(state=task_in.state)
        owner_q = scope.read_q("created_user")
        if owner_q is not None:
            q &= owner_q
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
        # 步骤执行环境映射 + 行级可删标记（按当前资源族的删除范围判定，含部门范围）
        for task_dict, obj in zip(data, instances):
            task_dict["steps_execute_env"] = extract_steps_execute_envs(task_dict.get("cases_execute_config"))
            task_dict["can_delete"] = scope.can_delete(obj.created_user)
        LOGGER.info(f"根据条件分页查询任务列表信息成功, 结果数量: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件分页查询任务列表信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_task.post("/run", summary="执行任务", description="立即执行任务")
async def run_task(
        task_in: AutoTestTaskId = Body(..., description="任务ID"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    立即执行任务。

    :param task_in: 任务入参
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，执行会写报告/执行记录，需先校验任务可见性
    :return: 统一HTTP响应
    """
    try:
        task_id: int = task_in.task_id
        instance = await services.task_curd.get_by_id(task_id=task_id, on_error=True, state__not=1)
        if not scope.can_read(instance.created_user):
            error_message: str = f"任务[{instance.task_name}]创建人[{instance.created_user}]不在当前用户可见范围"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)
        # 存量任务可能挂载了越权用例，执行前按用例资源族重新收敛
        await assert_cases_readable(scope, instance.task_case_ids or [])
        from backend.celery_scheduler.tasks.task_autotest_case import run_autotest_task
        from backend.enums import AutoTestReportType
        # __task_id会随消息传到Worker，task_prerun从request.properties取出；
        # 只有传了__task_id，Worker端_create_task_record才会查任务表并写入record的task_id/task_name。
        # created_user 写入执行记录（Worker 无 HTTP 鉴权上下文）。
        run_autotest_task.apply_async(
            kwargs={
                "task_id": task_id,
                "report_type": AutoTestReportType.ASYNC_EXEC,
                "created_user": get_current_username(),
            },
            __task_id=task_id
        )
        LOGGER.info(f"下发执行任务成功，task_id={task_id}")
        return SuccessResponse(message="已下发执行，请稍后在报告中查看结果", data={"task_id": task_id}, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NoPermissionException:  # 读范围校验失败需向上抛出，交由全局处理器返回403
        raise
    except Exception as e:
        LOGGER.error(f"执行任务失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"执行失败，异常描述: {e}")


@autotest_task.post("/start", summary="启动任务", description="启用任务定时调度")
async def start_task(
        task_in: AutoTestTaskId = Body(..., description="任务ID"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    启动任务（启用调度）。

    :param task_in: 任务入参
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，仅允许启停创建人为自己的任务
    :return: 统一HTTP响应
    """
    try:
        task_id: int = task_in.task_id
        # 启停调度视为任务修改刷新维护人：调度触发的执行，执行人归因到最后操作者
        instance = await services.task_curd.set_task_enabled(
            task_id=task_id, scope=scope, enabled=True, updated_user=get_current_username()
        )
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
    except NoPermissionException:  # 归属校验失败需向上抛出，交由全局处理器返回403
        raise
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"启用任务调度失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"启动失败，异常描述: {e}")


@autotest_task.post("/stop", summary="停止任务", description="停用任务定时调度")
async def stop_task(
        task_in: AutoTestTaskId = Body(..., description="任务ID"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    停止任务（关闭调度）。

    :param task_in: 任务入参
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，仅允许启停创建人为自己的任务
    :return: 统一HTTP响应
    """
    try:
        task_id: int = task_in.task_id
        # 停用调度同样视为任务修改，刷新维护人保持“最后修改人”语义一致
        instance = await services.task_curd.set_task_enabled(
            task_id=task_id, scope=scope, enabled=False, updated_user=get_current_username()
        )
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
    except NoPermissionException:  # 归属校验失败需向上抛出，交由全局处理器返回403
        raise
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"关闭任务调度失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"停止失败，异常描述: {e}")


@autotest_task.post("/copy", summary="新增任务副本", description="根据任务id复刻生成新任务")
async def copy_task(
        task_in: AutoTestTaskId = Body(..., description="任务ID"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    完全复刻任务记录生成新任务。

    复制规则：业务配置(用例/执行配置/定时表达式等)原样复制；
    task_code重新生成、task_enabled停用、执行痕迹(最后执行时间/人/结果)重置。

    :param task_in: 任务入参
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，源任务须在可见范围内，新任务挂载的用例须可见
    :return: 统一HTTP响应
    """
    try:
        task_id: int = task_in.task_id
        instance = await services.task_curd.copy_task(
            task_id=task_id,
            operate_user=get_current_username(),
            scope=scope,
        )
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3",
            },
            replace_fields={"id": "task_id"},
        )
        LOGGER.info(f"复制任务成功，源task_id={task_id}，新task_id={instance.id}")
        return SuccessResponse(message="复制成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except NoPermissionException:  # 源任务/挂载用例越权需向上抛出，交由全局处理器返回403
        raise
    except Exception as e:
        LOGGER.error(f"复制任务失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"复制失败，异常描述: {e}")


@autotest_task.post("/schedule_preview", summary="查询定时执行预览", description="按时效与定时表达式正推即将到来的触发日期时间(近10次)")
async def preview_task_schedule(
        preview_in: AutoTestTaskSchedulePreview = Body(..., description="预览条件"),
):
    """
    定时执行预览：按时效与定时表达式正推即将到来的触发日期时间，供新增/编辑页展示。

    :param preview_in: 预览入参
    :return: 统一HTTP响应，data为升序触发日期时间列表
    """
    try:
        schedule = normalize_schedule(
            periodic=preview_in.task_periodic_expr,
            schedule=preview_in.task_schedule_expr.model_dump() if preview_in.task_schedule_expr else None,
        )
        if not schedule:
            return ParameterResponse(message="参数[task_schedule_expr]不允许为空")
        schedule_obj = TaskSchedule.from_expr(preview_in.task_periodic_expr, schedule)
        data = schedule_obj.preview_fire_times() if schedule_obj else []
        return SuccessResponse(message="预览成功", data=data, total=len(data))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"定时执行预览失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"预览失败，异常描述: {str(e)}")


@autotest_task.post("/record/search", summary="查询执行记录", description="根据条件分页查询任务执行记录(Body)")
async def search_task_records(
        record_in: AutoTestRecordSelect = Body(..., description="查询条件"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    任务执行记录查询。

    :param record_in: 任务执行记录查询入参
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，按创建人过滤可见范围
    :return: 统一HTTP响应
    """
    try:
        total, instances = await services.record_curd.select_records(record_in=record_in, scope=scope)
        data = [
            await obj.to_dict(
                exclude_fields={"created_time", "updated_time"},
                replace_fields={"id": "record_id"}
            )
            for obj in instances
        ]
        # 行级可删标记：记录创建人是归属口径，按当前资源族的删除范围判定
        for item, obj in zip(data, instances):
            item["can_delete"] = scope.can_delete(obj.created_user)
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
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    根据执行记录attachments项下载文件。

    :param record_id: 执行记录主键
    :param key: 附件标识（信封attachments[].key）
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，校验记录创建人可见性
    :return: 文件流响应
    """
    try:
        record = await services.record_curd.get_or_none(id=record_id, state__not=1)
        if not record:
            return ParameterResponse(message=f"执行记录不存在: record_id={record_id}")
        if not scope.can_read(record.created_user):  # 产物文件归属于记录创建人，需收口到可见范围
            raise NoPermissionException(
                message=f"下载附件失败, 记录[id={record_id}]创建人[{record.created_user}]不在当前用户可见范围"
            )
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
    except NoPermissionException:  # 归属校验失败需向上抛出，交由全局处理器返回403
        raise
    except ValueError as e:
        return ParameterResponse(message=str(e))
    except Exception as e:
        LOGGER.error(f"根据记录id与附件key下载附件失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"下载失败，异常描述: {str(e)}")


@autotest_task.delete("/record/delete", summary="删除执行记录", description="删除终态执行记录并物理清理产物文件")
async def delete_task_record(
        record_id: int = Query(..., description="执行记录主键"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    删除终态执行记录(硬删)并物理清理产物文件。

    仅终态(成功/失败/部分成功)任务允许删除；等待执行/正在执行任务拒绝删除。

    :param record_id: 执行记录主键
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，仅允许删除创建人为自己的执行记录
    :return: 统一HTTP响应
    """
    try:
        deleted = await services.record_curd.delete_record_with_artifacts(record_id=record_id, scope=scope)
        LOGGER.info(f"删除执行记录成功, record_id={record_id}, deleted={deleted}")
        return SuccessResponse(message="删除成功")
    except NoPermissionException:  # 归属校验失败需向上抛出，交由全局处理器返回403
        raise
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"删除执行记录失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@autotest_task.post("/record/deletes", summary="批量删除执行记录", description="批量删除终态执行记录并物理清理产物文件")
async def delete_task_records(
        record_in: AutoTestRecordBatchDelete = Body(..., description="批量删除执行记录入参"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    批量删除终态执行记录(硬删)并物理清理产物文件。

    仅终态(成功/失败/部分成功)任务允许删除；任一条等待执行/正在执行则整批拒绝。

    :param record_in: 执行记录ID列表
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，仅允许删除创建人为自己的执行记录
    :return: 统一HTTP响应，data为实际删除的记录数量
    """
    try:
        deleted = await services.record_curd.delete_records_with_artifacts(record_in=record_in, scope=scope)
        LOGGER.info(f"批量删除执行记录成功, record_ids={record_in.record_ids}, deleted={deleted}")
        return SuccessResponse(message="批量删除成功", data={"deleted": deleted}, total=deleted)
    except NoPermissionException:  # 归属校验失败需向上抛出，交由全局处理器返回403
        raise
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"批量删除执行记录失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"批量删除失败，异常描述: {str(e)}")
