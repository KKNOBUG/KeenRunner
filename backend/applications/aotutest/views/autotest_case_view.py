# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_view.py
@DateTime: 2025/4/28
"""
import asyncio
import os
import tempfile
import traceback
from typing import Optional, List, Dict, Any, Set, Tuple

from fastapi import APIRouter, Body, Query, Depends, UploadFile, File
from starlette.background import BackgroundTask
from starlette.responses import FileResponse
from tortoise.expressions import Q

from backend.applications.aotutest.dependencies import AutoTestApiServices, get_autotest_api_services
from backend.applications.aotutest.schemas.autotest_case_schema import (
    AutoTestApiCaseCreate,
    AutoTestApiCaseSelect,
    AutoTestApiCaseUpdate
)
from backend.applications.aotutest.services.autotest_case_excel_service import (
    prepare_export_cases,
    build_export_workbook,
    build_export_file_name,
    prepare_script_export_rows,
    build_script_workbook,
    build_script_file_name,
    parse_script_workbook,
    import_script_rows,
)
from backend.celery_scheduler.tasks.task_export_case_datagram import export_testcases_task
from backend.celery_scheduler.tasks.task_export_case_script import export_case_scripts_task
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
    FileExtensionResponse
)
from backend.enums import AutoTestReportType, AutoTestStepType, AutoTestCaseType
from backend.services import get_current_username

autotest_case = APIRouter()

# 导出数量阈值：超过该值走异步Celery导出
EXPORT_ASYNC_THRESHOLD = 10


@autotest_case.post("/create", summary="新增用例", description="新增用例信息")
async def create_case(
        case_in: AutoTestApiCaseCreate = Body(..., description="用例信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    新增用例。

    :param case_in: 用例入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.case_curd.create_case(case_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "case_id"}
        )
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
        LOGGER.error(f"新增用例失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {e}")


@autotest_case.delete("/delete", summary="删除用例", description="根据id或code软删除用例及其步骤")
async def delete_case(
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code软删除用例及其步骤。

    :param case_id: 用例主键ID
    :param case_code: 用例业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.case_curd.delete_case(case_id=case_id, case_code=case_code)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "case_id"}
        )
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code软删除用例及其步骤失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@autotest_case.post("/update", summary="更新用例", description="根据id或code更新用例信息")
async def update_case(
        case_in: AutoTestApiCaseUpdate = Body(..., description="用例信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code更新用例信息。

    :param case_in: 用例入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.case_curd.update_case(case_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "case_id"}
        )
        return SuccessResponse(message="更新成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code更新用例信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {e}")


@autotest_case.get("/get", summary="查询用例", description="根据id或code查询用例信息")
async def get_case(
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code查询用例信息。

    :param case_id: 用例主键ID
    :param case_code: 用例业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if case_id:
            instance = await services.case_curd.get_by_id(case_id=case_id, on_error=True, state__not=1)
        else:
            instance = await services.case_curd.get_by_code(case_code=case_code, on_error=True, state__not=1)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "case_id"}
        )
        project_id: int = data.pop("case_project")
        project_instance = await services.project_curd.get_by_id(on_error=True, project_id=project_id, state__not=1)
        data["case_project"] = await project_instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "project_id"}
        )
        tag_ids: List[int] = data.pop("case_tags") or []
        # 无标签用例(公共接口允许)跳过标签查询, get_by_ids不接受空列表
        data["case_tags"] = [
            await obj.to_dict(
                exclude_fields={
                    "state",
                    "created_user", "updated_user",
                    "created_time", "updated_time",
                    "reserve_1", "reserve_2", "reserve_3"
                },
                replace_fields={"id": "tag_id"}
            ) for obj in await services.tag_curd.get_by_ids(tag_ids=tag_ids, on_error=True, state__not=1)
        ] if tag_ids else []
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询用例信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


async def batch_fetch_related_data(
        project_ids: Set[int],
        tag_ids: Set[int],
        case_ids: List[int],
        services: AutoTestApiServices
) -> Tuple[Dict[int, dict], Dict[int, dict], Dict[int, List[str]]]:
    acquire_project_instance_task = services.project_curd.get_by_ids(
        project_ids=list(project_ids),
        on_error=True,
        state__not=1
    ) if project_ids else asyncio.sleep(0, result=[])

    acquire_tag_instance_task = services.tag_curd.get_by_ids(
        tag_ids=list(tag_ids),
        on_error=True,
        state__not=1
    ) if tag_ids else asyncio.sleep(0, result=[])

    acquire_step_type_instance_task = services.step_curd.model.filter(
        ~Q(case_id__isnull=True),
        case_id__in=case_ids,
        state__not=1
    ).values_list("case_id", "step_type") if case_ids else asyncio.sleep(0, result=[])

    project_objs, tag_objs, step_type_raw = await asyncio.gather(
        acquire_project_instance_task,
        acquire_tag_instance_task,
        acquire_step_type_instance_task
    )

    project_map = {}
    for p in project_objs:
        p_dict = await p.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3", "reserve_4", "reserve_5"
            },
            replace_fields={"id": "project_id"}
        )
        project_map[p_dict["project_id"]] = p_dict

    tag_map = {}
    for tag in tag_objs:
        tag_dict = await tag.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3", "reserve_4", "reserve_5"
            },
            replace_fields={"id": "tag_id"}
        )
        tag_map[tag_dict["tag_id"]] = tag_dict

    case_step_type_map = {}
    for cid, stype in step_type_raw:
        if cid not in case_step_type_map:
            case_step_type_map[cid] = stype

    return project_map, tag_map, case_step_type_map


def _protocol_from_step_type(step_type: Any) -> Optional[str]:
    """步骤类型枚举值映射为协议标识（HTTP请求→HTTP，TCP请求→TCP）。"""
    if step_type is None:
        return None
    value = step_type.value if hasattr(step_type, "value") else str(step_type)
    if value == AutoTestStepType.HTTP.value:
        return "HTTP"
    if value == AutoTestStepType.TCP.value:
        return "TCP"
    return None


@autotest_case.post("/search", summary="查询用例列表", description="根据条件分页查询用例列表信息(Body)")
async def search_cases(
        case_in: AutoTestApiCaseSelect = Body(..., description="查询条件"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据条件分页查询用例列表信息。

    :param case_in: 用例入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if case_in.case_id:
            q &= Q(id=case_in.case_id)
        if case_in.case_code:
            q &= Q(case_code=case_in.case_code)
        if case_in.case_name:
            q &= Q(case_name__contains=case_in.case_name)
        if case_in.case_tags:
            for tag_id in case_in.case_tags:
                q |= Q(case_tags__contains=tag_id)
        if case_in.case_types:
            q &= Q(case_type__in=case_in.case_types)
        if case_in.case_steps:
            q &= Q(case_steps__gte=case_in.case_steps)
        if case_in.case_project:
            q &= Q(case_project=case_in.case_project)
        if case_in.case_version:
            q &= Q(case_version__gte=case_in.case_version)
        if case_in.case_attr:
            q &= Q(case_attr=case_in.case_attr.value)
        if case_in.created_user:
            q &= Q(created_user=case_in.created_user)
        if case_in.updated_user:
            q &= Q(updated_user=case_in.updated_user)
        q &= Q(state=case_in.state)
        if case_in.step_type is not None or case_in.request_args_type is not None:
            matched_case_ids: Optional[List[int]] = await services.case_curd.get_case_ids_by_request_step(
                step_type=case_in.step_type,
                request_args_type=case_in.request_args_type,
            )
            if not matched_case_ids:
                return SuccessResponse(message="查询成功", data=[], total=0)
            q &= Q(id__in=matched_case_ids)

        total, instances = await services.case_curd.select_cases(
            search=q,
            page=case_in.page,
            page_size=case_in.page_size,
            order=case_in.order
        )
        if not instances:
            return SuccessResponse(message="查询成功", data=[], total=total)

        # 预收集所有关联ID，一次性并发批量查询
        all_project_ids: Set[int] = set()
        all_tag_ids: Set[int] = set()
        all_case_ids: List[int] = []
        requested_types = set(case_in.case_type or [])
        script_case_types = {AutoTestCaseType.PUBLIC_SCRIPT.value, AutoTestCaseType.PRIVATE_SCRIPT.value}
        is_script_query = requested_types == script_case_types
        is_public_api_query = AutoTestCaseType.PUBLIC_API.value in requested_types

        for instance in instances:
            all_case_ids.append(instance.id)
            all_project_ids.add(instance.case_project)
            if instance.case_tags:
                all_tag_ids.update(instance.case_tags)

        # 并发拉取项目、标签、步骤类型映射
        project_map, tag_map, case_step_type_map = await batch_fetch_related_data(
            project_ids=all_project_ids,
            tag_ids=all_tag_ids,
            case_ids=all_case_ids,
            services=services
        )

        # 循环序列化每条用例
        case_serializes: List[Dict[str, Any]] = []
        for instance in instances:
            serialize: Dict[str, Any] = await instance.to_dict(
                exclude_fields={
                    "state", "created_user", "updated_user",
                    "reserve_1", "reserve_2", "reserve_3", "reserve_4", "reserve_5"
                },
                replace_fields={"id": "case_id"}
            )
            case_id = serialize["case_id"]
            project_id = serialize.pop("case_project", None)
            serialize["case_project"] = project_map.get(project_id, {})
            tag_ids = serialize.pop("case_tags", None) or []
            serialize["case_tags"] = [tag_map.get(tid, {}) for tid in tag_ids]
            if is_script_query:
                serialize["step_type"] = case_step_type_map.get(case_id, None)
            # 公共接口仅一个 HTTP/TCP 步骤，补充协议字段供列表展示
            instance_type = (
                instance.case_type.value
                if hasattr(instance.case_type, "value")
                else str(instance.case_type or "")
            )
            if is_public_api_query or instance_type == AutoTestCaseType.PUBLIC_API.value:
                serialize["step_type"] = _protocol_from_step_type(case_step_type_map.get(case_id))
            case_serializes.append(serialize)
        return SuccessResponse(message="查询成功", data=case_serializes, total=total)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件分页查询用例列表信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_case.get("/request_step_selected_project", summary="查询请求步骤应用", description="根据id或code获取步骤树中请求步骤选择的应用ID列表")
async def get_request_step_selected_project_ids(
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    从步骤树中提取以下步骤类型所选择的应用ID并去重返回。

    - HTTP请求：step.request_project_id
    - TCP请求：step.request_project_id
    - 数据库请求：step.database_operates[*].project_id（可能多个）

    同时递归遍历children与quote_steps（引用公共脚本展开后的步骤）。

    :param case_id: 用例主键ID
    :param case_code: 用例业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        project_ids: List[int] = await services.step_curd.get_request_step_project_ids(
            case_id=case_id,
            case_code=case_code,
        )
        project_ids_len: int = len(project_ids)
        return SuccessResponse(message="查询成功", data=project_ids, total=project_ids_len)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code获取步骤树中请求步骤选择的应用ID列表失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_case.post("/export_case_datagram_sync", summary="导出公共接口报文", description="导出公共接口用例请求头与请求体为xlsx(同步)")
async def export_case_datagram_sync(
        case_ids: List[int] = Body(..., description="用例ID列表", embed=True),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    同步导出公共接口用例的请求头与请求体为xlsx，数量不超过EXPORT_ASYNC_THRESHOLD。

    :param case_ids: 用例主键列表
    :param services: 自动化测试CRUD依赖聚合
    :return: 文件流响应
    """
    try:
        if not case_ids:
            return ParameterResponse(message="请至少选择一个用例(公共接口)")
        if len(case_ids) > EXPORT_ASYNC_THRESHOLD:
            return ParameterResponse(message=f"选择的用例(公共接口)数量超过{EXPORT_ASYNC_THRESHOLD}个，请使用异步导出")
        cases_data, invalid = await prepare_export_cases(case_ids=case_ids, services=services)
        if invalid:
            return ParameterResponse(message="选择的用例(公共接口)存在不合规，已取消导出", data={"invalid": invalid})
        workbook = build_export_workbook(cases_data=cases_data)
        # 先落临时文件再以FileResponse分块流式返回，避免整文件驻留内存OOM；发送后自动清理
        temp = tempfile.NamedTemporaryFile(prefix="krun_export_", suffix=".xlsx", delete=False)
        temp_path = temp.name
        temp.close()
        workbook.save(temp_path)
        return FileResponse(
            path=temp_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=build_export_file_name(get_current_username()),
            background=BackgroundTask(os.remove, temp_path),
        )
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"导出公共接口用例请求头与请求体为xlsx(同步)失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"导出失败，异常描述: {e}")


@autotest_case.post("/export_case_datagram_async", summary="导出公共接口报文(异步)", description="异步导出公共接口用例请求头与请求体为xlsx")
async def export_case_datagram_async(
        case_ids: List[int] = Body(..., description="用例ID列表", embed=True),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    异步导出公共接口用例，数量超过EXPORT_ASYNC_THRESHOLD。

    校验通过后下发Celery任务，任务生成xlsx并将文件名落入执行记录(task_summary)，下载入口后续于异步中心提供。

    :param case_ids: 用例主键列表
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if not case_ids:
            return ParameterResponse(message="请至少选择一个用例(公共接口)")
        _, invalid = await prepare_export_cases(case_ids=case_ids, services=services)
        if invalid:
            return ParameterResponse(message="选择的用例(公共接口)存在不合规，已取消导出", data={"invalid": invalid})
        apply_async_result = export_testcases_task.apply_async(
            kwargs={
                "case_ids": case_ids,
                "created_user": get_current_username(),
                "report_type": AutoTestReportType.ASYNC_EXEC.value,
            },
            expires=3600,
        )
        return SuccessResponse(
            message="导出任务已提交后台执行，请稍后在执行记录中查看结果",
            data={"celery_task_id": apply_async_result.task_id, "count": len(case_ids)},
            total=1,
        )
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"异步导出公共接口用例请求头与请求体为xlsx失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"下发导出任务失败，异常描述: {e}")


@autotest_case.post("/export_case_scripts_sync", summary="导出公共接口脚本", description="导出公共接口脚本为模板xlsx(同步)")
async def export_case_scripts_sync(
        case_ids: List[int] = Body(..., description="用例ID列表", embed=True),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    同步导出公共接口脚本，数量不超过EXPORT_ASYNC_THRESHOLD。

    复制模板副本写入数据行，产出文件可直接用于导入脚本、更新或新增公共接口。

    :param case_ids: 用例主键列表
    :param services: 自动化测试CRUD依赖聚合
    :return: 文件流响应
    """
    try:
        if not case_ids:
            return ParameterResponse(message="请至少选择一个用例(公共接口)")
        if len(case_ids) > EXPORT_ASYNC_THRESHOLD:
            return ParameterResponse(message=f"选择的用例(公共接口)数量超过{EXPORT_ASYNC_THRESHOLD}个，请使用异步导出")
        rows, invalid = await prepare_script_export_rows(case_ids=case_ids, services=services)
        if invalid:
            return ParameterResponse(message="选择的用例(公共接口)存在不合规，已取消导出", data={"invalid": invalid})
        workbook = build_script_workbook(rows)
        # 先落临时文件再以 FileResponse 分块流式返回，避免整文件驻留内存OOM；发送后自动清理
        temp = tempfile.NamedTemporaryFile(prefix="krun_export_", suffix=".xlsx", delete=False)
        temp_path = temp.name
        temp.close()
        workbook.save(temp_path)
        return FileResponse(
            path=temp_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=build_script_file_name(get_current_username()),
            background=BackgroundTask(os.remove, temp_path),
        )
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"导出公共接口脚本为模板xlsx(同步)失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"导出失败，异常描述: {e}")


@autotest_case.post("/export_case_scripts_async", summary="导出公共接口脚本(异步)", description="异步导出公共接口脚本为模板xlsx")
async def export_case_scripts_async(
        case_ids: List[int] = Body(..., description="用例ID列表", embed=True),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    异步导出公共接口脚本，数量超过EXPORT_ASYNC_THRESHOLD。

    校验通过后下发Celery任务，任务生成xlsx并将文件名落入执行记录(task_summary)，下载入口后续于异步中心提供。

    :param case_ids: 用例主键列表
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if not case_ids:
            return ParameterResponse(message="请至少选择一个用例(公共接口)")
        _, invalid = await prepare_script_export_rows(case_ids=case_ids, services=services)
        if invalid:
            return ParameterResponse(message="选择的用例(公共接口)存在不合规，已取消导出", data={"invalid": invalid})
        apply_async_result = export_case_scripts_task.apply_async(
            kwargs={
                "case_ids": case_ids,
                "created_user": get_current_username(),
                "report_type": AutoTestReportType.ASYNC_EXEC.value,
            },
            expires=3600,
        )
        return SuccessResponse(
            message="导出任务已提交后台执行，请稍后在执行记录中查看结果",
            data={"celery_task_id": apply_async_result.task_id, "count": len(case_ids)},
            total=1,
        )
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"异步导出公共接口脚本为模板xlsx失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"下发导出任务失败，异常描述: {e}")


@autotest_case.post("/import_case_scripts", summary="导入公共接口脚本", description="从模板xlsx导入公共接口脚本")
async def import_case_scripts(
        file: UploadFile = File(..., description="公共接口导入导出模板xlsx(仅读取第1个sheet页)"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    导入公共接口脚本。

    解析模板文件逐行校验，根据所属应用+接口名称匹配，存在更新、不存在新增；用例类型固定公共接口、用例属性固定正用例；全部行校验通过才在单事务内落库。

    :param file: 模板xlsx文件
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    if not (file.filename or "").endswith(".xlsx"):
        return FileExtensionResponse(message="仅支持.xlsx后缀的模板文件")
    try:
        content: bytes = await file.read()
        rows, parse_invalid = parse_script_workbook(content)
        if parse_invalid:
            return ParameterResponse(message="文件存在不合规行，已取消导入", data={"invalid": parse_invalid})
        result, resolve_invalid = await import_script_rows(rows=rows, services=services)
        if resolve_invalid:
            return ParameterResponse(message="存在无法落库的行，已取消导入", data={"invalid": resolve_invalid})
        return SuccessResponse(
            message=f"导入成功: 新增{result['created_count']}个, 更新{result['updated_count']}个公共接口",
            data=result,
            total=1,
        )
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"从模板xlsx导入公共接口脚本失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"导入失败，异常描述: {e}")
