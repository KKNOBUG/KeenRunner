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
import traceback
from typing import Optional, List, Dict, Any, Set, Tuple
from urllib.parse import quote

from fastapi import APIRouter, Body, Query, Depends, UploadFile, File
from starlette.responses import StreamingResponse
from tortoise.expressions import Q

from backend.applications.autotest.dependencies import AutoTestServices, get_autotest_api_services
from backend.applications.autotest.schemas.autotest_case_schema import (
    AutoTestCaseCreate,
    AutoTestCaseScriptGenerate,
    AutoTestCaseSelect,
    AutoTestCaseUpdate
)
from backend.applications.autotest.services.autotest_case_excel_service import (
    prepare_export_cases,
    prepare_script_export_rows,
    parse_script_workbook,
)
from backend.celery_scheduler.tasks.task_export_case_datagram import export_testcases_task
from backend.celery_scheduler.tasks.task_export_case_script import export_case_scripts_task
from backend.celery_scheduler.tasks.task_import_case_script import import_case_scripts_task
from backend.celery_scheduler.tasks.task_public_api_to_script import generate_case_scripts_task
from backend.configure import LOGGER, PROJECT_CONFIG
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
from backend.services.file_transfer import FileTransfer

autotest_case = APIRouter()


@autotest_case.post("/create", summary="新增用例", description="新增用例信息")
async def create_case(
        case_in: AutoTestCaseCreate = Body(..., description="用例信息"),
        services: AutoTestServices = Depends(get_autotest_api_services),
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
        services: AutoTestServices = Depends(get_autotest_api_services),
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
        case_in: AutoTestCaseUpdate = Body(..., description="用例信息"),
        services: AutoTestServices = Depends(get_autotest_api_services),
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
        services: AutoTestServices = Depends(get_autotest_api_services),
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
        services: AutoTestServices
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
                "reserve_1", "reserve_2", "reserve_3",
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
                "reserve_1", "reserve_2", "reserve_3",
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
        case_in: AutoTestCaseSelect = Body(..., description="查询条件"),
        services: AutoTestServices = Depends(get_autotest_api_services),
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
        if case_in.case_ids:
            # 用例ID集合精确过滤：供已选脚本回显/补全等按 ids 查询场景
            q &= Q(id__in=case_in.case_ids)
        if case_in.case_code:
            q &= Q(case_code=case_in.case_code)
        if case_in.case_name:
            q &= Q(case_name__contains=case_in.case_name)
        if case_in.case_tags:
            tag_q = Q()
            for tag_id in case_in.case_tags:
                tag_q |= Q(case_tags__contains=tag_id)
            q &= tag_q
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
        if case_in.owner_user:
            q &= Q(owner_user=case_in.owner_user)
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
        if case_in.case_ids and instances:
            # 精确过滤时按case_ids入参顺序重排(绑定顺序即业务顺序, 供编辑任务抽屉回显)，通用查询路径不受影响
            id_rank: Dict[int, int] = {}
            for case_id in case_in.case_ids:
                id_rank.setdefault(case_id, len(id_rank))
            instances.sort(key=lambda instance: id_rank.get(instance.id, len(id_rank)))
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
                    "state", "reserve_1", "reserve_2", "reserve_3",
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
        services: AutoTestServices = Depends(get_autotest_api_services),
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
        project_ids: List[int] = await services.step_curd.get_step_usage_projects(
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


@autotest_case.post("/import_template_download", summary="下载公共接口导入模板", description="公共接口数据导入模板文件xlsx下载")
async def public_api_import_template_download():
    """
    公共接口导入模板下载。

    分发仓库内置于output/template的xlsx（HTTP/TCP请求步骤共用）；流式读取，不加UTF-8 BOM，避免损坏二进制格式。

    :return: 文件流响应
    """
    filepath = os.path.normpath(os.path.join(PROJECT_CONFIG.OUTPUT_DIR, "template", "公共接口模板.xlsx"))
    if not filepath.startswith(PROJECT_CONFIG.OUTPUT_DIR) or not os.path.isfile(filepath):
        LOGGER.error(f"导入模板文件不存在: {filepath}")
        return NotFoundResponse(message="导入模板文件不存在，请联系管理员部署")
    file_name = os.path.basename(filepath)
    quoted_name = quote(file_name)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quoted_name}"
    }
    return StreamingResponse(
        FileTransfer.iter_download_file_chunks(download_file=filepath, add_bom=False),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@autotest_case.post("/export_case_datagram_async", summary="导出公共接口报文(异步)", description="导出公共接口用例请求头与请求体为xlsx(统一异步)")
async def export_case_datagram_async(
        case_ids: List[int] = Body(..., description="用例ID列表", embed=True),
        services: AutoTestServices = Depends(get_autotest_api_services),
):
    """
    异步导出公共接口用例(统一异步，不再区分数量阈值)。

    校验通过后下发Celery任务，任务生成xlsx并将产物落入执行记录(task_summary)，在异步中心查询与下载。

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
            message="导出任务已提交后台执行，请稍后在异步中心查看结果",
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


@autotest_case.post("/export_case_scripts_async", summary="导出公共接口脚本(异步)", description="导出公共接口脚本为模板xlsx(统一异步)")
async def export_case_scripts_async(
        case_ids: List[int] = Body(..., description="用例ID列表", embed=True),
        services: AutoTestServices = Depends(get_autotest_api_services),
):
    """
    异步导出公共接口脚本(统一异步，不再区分数量阈值)。

    校验通过后下发Celery任务，任务生成xlsx并将产物落入执行记录(task_summary)，在异步中心查询与下载；
    产出文件可直接用于导入脚本、更新或新增公共接口。

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
            message="导出任务已提交后台执行，请稍后在异步中心查看结果",
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


@autotest_case.post("/generate_case_scripts_async", summary="新增公共接口脚本(异步)", description="公共接口批量生成独立脚本用例(统一异步)")
async def generate_case_scripts_async(
        generate_in: AutoTestCaseScriptGenerate = Body(..., description="脚本生成入参"),
        services: AutoTestServices = Depends(get_autotest_api_services),
):
    """
    将勾选的公共接口复制生成为脚本用例。

    校验全部入参用例均为公共接口后下发Celery任务；命名规则：脚本名称=接口名称，
    同应用下已有同名记录时按「{接口名称}-{时间戳}」命名；生成结果在异步中心查询。

    :param generate_in: 脚本生成入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        case_ids = generate_in.case_ids
        if not case_ids:
            return ParameterResponse(message="请至少选择一个用例(公共接口)")
        case_models = await services.case_curd.model.filter(id__in=list(dict.fromkeys(case_ids)), state__not=1)
        case_map = {instance.id: instance for instance in case_models}
        invalid: List[Dict[str, Any]] = []
        for case_id in dict.fromkeys(case_ids):
            instance = case_map.get(case_id)
            if not instance:
                invalid.append({"case_id": case_id, "case_name": str(case_id), "reason": "用例不存在"})
            elif instance.case_type != AutoTestCaseType.PUBLIC_API:
                invalid.append({"case_id": case_id, "case_name": instance.case_name, "reason": "非公共接口用例"})

        if invalid:
            return ParameterResponse(message="选择的用例(公共接口)存在不合规，已取消生成", data={"invalid": invalid})

        apply_async_result = generate_case_scripts_task.apply_async(
            kwargs={
                "case_ids": case_ids,
                "case_project": generate_in.case_project,
                "case_type": generate_in.case_type.value,
                "case_attr": generate_in.case_attr.value,
                "case_tags": generate_in.case_tags,
                "created_user": get_current_username(),
                "report_type": AutoTestReportType.ASYNC_EXEC.value,
            },
            expires=3600,
        )
        return SuccessResponse(
            message="脚本生成任务已提交后台执行，请稍后在异步中心查看结果",
            data={"celery_task_id": apply_async_result.task_id, "count": len(case_ids)},
            total=1,
        )
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"公共接口转脚本任务下发失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"下发脚本生成任务失败，异常描述: {e}")


@autotest_case.post("/import_case_scripts_async", summary="导入公共接口脚本(异步)", description="解析模板xlsx文件并生成公共接口脚本(统一异步)")
async def import_case_scripts_async(
        file: UploadFile = File(..., description="公共接口导入导出模板xlsx(仅读取第1个sheet页)"),
):
    """
    异步导入公共接口脚本(统一异步)。

    模板解析与行格式校验同步完成(不合规行明细即时返回便于修稿重试)，校验通过后下发Celery任务；
    行级匹配校验与落库在后台执行(存在更新、不存在新增)，结果与不合规明细落入执行记录(task_summary)，在异步中心查询。

    :param file: 模板xlsx文件
    :return: 统一HTTP响应
    """
    if not (file.filename or "").endswith(".xlsx"):
        return FileExtensionResponse(message="仅支持.xlsx后缀的模板文件")
    try:
        content: bytes = await file.read()
        rows, parse_invalid = parse_script_workbook(content)
        if parse_invalid:
            return ParameterResponse(message="文件存在不合规行，已取消导入", data={"invalid": parse_invalid})
        apply_async_result = import_case_scripts_task.apply_async(
            kwargs={
                "rows": rows,
                "file_name": file.filename,
                "created_user": get_current_username(),
                "report_type": AutoTestReportType.ASYNC_EXEC.value,
            },
            expires=3600,
        )
        return SuccessResponse(
            message="导入任务已提交后台执行，请稍后在异步中心查看结果",
            data={"celery_task_id": apply_async_result.task_id, "count": len(rows)},
            total=1,
        )
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"下发导入公共接口脚本任务失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"下发导入任务失败，异常描述: {e}")
