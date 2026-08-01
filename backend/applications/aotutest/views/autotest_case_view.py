# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_view.py
@DateTime: 2025/4/28
"""
import os
import tempfile
import traceback
from typing import Optional, List, Dict, Any

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
    DataBaseStorageResponse,
    DataAlreadyExistsResponse,
    FileExtensionResponse,
)
from backend.enums import AutoTestReportType
from backend.services import get_current_username

autotest_case = APIRouter()

# 导出数量阈值：超过该值走异步 Celery 导出
EXPORT_ASYNC_THRESHOLD = 10


@autotest_case.post("/create", summary="API自动化测试-新增用例")
async def create_case(
        case_in: AutoTestApiCaseCreate = Body(..., description="用例信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    新增用例。

    :param case_in: 用例入参
    :param services: 自动化测试 CRUD 依赖聚合
    :return: 统一 HTTP 响应
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
        LOGGER.info(f"新增用例成功, 结果明细: {data}")
        return SuccessResponse(message="新增成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增用例失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {e}")


@autotest_case.delete("/delete", summary="API自动化测试-按id或code删除用例")
async def delete_case(
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    按id或code删除用例。

    :param case_id: 用例主键 ID
    :param case_code: 用例业务标识
    :param services: 自动化测试 CRUD 依赖聚合
    :return: 统一 HTTP 响应
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
        LOGGER.info(f"按id或code删除用例成功, 结果明细: {data}")
        return SuccessResponse(message="删除成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code删除用例失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@autotest_case.post("/update", summary="API自动化测试-按id或code更新除用例")
async def update_case(
        case_in: AutoTestApiCaseUpdate = Body(..., description="用例信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    按id或code更新除用例。

    :param case_in: 用例入参
    :param services: 自动化测试 CRUD 依赖聚合
    :return: 统一 HTTP 响应
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
        LOGGER.info(f"按id或code更新除用例成功, 结果明细: {data}")
        return SuccessResponse(message="更新成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code更新除用例失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {e}")


@autotest_case.get("/get", summary="API自动化测试-按id或code查询用例")
async def get_case(
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    按id或code查询用例。

    :param case_id: 用例主键 ID
    :param case_code: 用例业务标识
    :param services: 自动化测试 CRUD 依赖聚合
    :return: 统一 HTTP 响应
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
        LOGGER.info(f"按id或code查询用例成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code查询用例失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_case.post("/search", summary="API自动化测试-按条件查询用例")
async def search_cases(
        case_in: AutoTestApiCaseSelect = Body(..., description="查询条件"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    按条件查询用例。

    :param case_in: 用例入参
    :param services: 自动化测试 CRUD 依赖聚合
    :return: 统一 HTTP 响应
    """
    try:
        q = Q()
        if case_in.case_id:
            q &= Q(id=case_in.case_id)
        if case_in.exclude_case_id:
            q &= ~Q(id=case_in.exclude_case_id)
        if case_in.case_code:
            q &= Q(case_code=case_in.case_code)
        if case_in.case_name:
            q &= Q(case_name__contains=case_in.case_name)
        if case_in.case_tags:
            for tag_id in case_in.case_tags:
                q |= Q(case_tags__contains=tag_id)
        if case_in.case_types:
            q &= Q(case_type__in=[t.value for t in case_in.case_types])
        elif case_in.case_type:
            q &= Q(case_type=case_in.case_type.value)
        if case_in.case_steps:
            q &= Q(case_steps__gte=case_in.case_steps)
        if case_in.case_project:
            q &= Q(case_project=case_in.case_project)
        if case_in.case_version:
            q &= Q(case_version__gte=case_in.case_version)
        if case_in.case_attr:
            q &= Q(case_attr=case_in.case_attr.value)
        if case_in.created_user:
            q &= Q(created_user__iexact=case_in.created_user)
        if case_in.updated_user:
            q &= Q(updated_user__iexact=case_in.updated_user)
        # 创建时间范围：按 created_time 筛选，仅日期时补全为当天起止
        if case_in.date_from:
            date_from = case_in.date_from.strip()
            if len(date_from) == 10:  # YYYY-MM-DD
                date_from = f"{date_from} 00:00:00"
            q &= Q(created_time__gte=date_from)
        if case_in.date_to:
            date_to = case_in.date_to.strip()
            if len(date_to) == 10:
                date_to = f"{date_to} 23:59:59"
            q &= Q(created_time__lte=date_to)
        q &= Q(state=case_in.state)
        total, instances = await services.case_curd.select_cases(
            search=q,
            page=case_in.page,
            page_size=case_in.page_size,
            order=case_in.order
        )
        case_serializes: List[Dict[str, Any]] = []
        for instance in instances:
            serialize: Dict[str, Any] = await instance.to_dict(
                exclude_fields={
                    "state",
                    "reserve_1", "reserve_2", "reserve_3"
                },
                replace_fields={"id": "case_id"}
            )
            project_id: int = serialize.pop("case_project")
            project_instance = await services.project_curd.get_by_id(on_error=True, project_id=project_id, state__not=1)
            serialize["case_project"] = await project_instance.to_dict(
                exclude_fields={
                    "state",
                    "created_user", "updated_user",
                    "created_time", "updated_time",
                    "reserve_1", "reserve_2", "reserve_3"
                },
                replace_fields={"id": "project_id"}
            )
            tag_ids: List[int] = serialize.pop("case_tags") or []
            # 无标签用例(公共接口允许)跳过标签查询, get_by_ids不接受空列表
            serialize["case_tags"] = [
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
            case_serializes.append(serialize)
        LOGGER.info(f"按条件查询用例成功, 结果数量: {total}")
        return SuccessResponse(message="查询成功", data=case_serializes, total=total)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按条件查询用例失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_case.get("/request_step_selected_project", summary="API自动化测试-按id或code获取步骤树中请求步骤选择的应用ID列表", )
async def get_request_step_project_ids(
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    从步骤树中提取以下步骤类型所选择的应用ID并去重返回：
    - HTTP请求：step.request_project_id
    - TCP请求：step.request_project_id
    - 数据库请求：step.database_operates[*].project_id（可能多个）

    同时递归遍历 children 与 quote_steps（引用公共脚本展开后的步骤）。
    """
    try:
        project_ids: List[int] = await services.step_curd.get_request_step_project_ids(
            case_id=case_id,
            case_code=case_code,
        )
        project_ids_len: int = len(project_ids)
        LOGGER.info(f"获取步骤树请求步骤应用ID列表成功, case_id={case_id}, case_code={case_code}, 数量={project_ids_len}, 数据={project_ids}")
        return SuccessResponse(message="查询成功", data=project_ids, total=project_ids_len)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"获取步骤树请求步骤应用ID列表失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_case.post("/export_datagram_sync", summary="API自动化测试-导出公共接口用例请求头与请求体为xlsx(同步)")
async def export_testcases_xlsx(
        case_ids: List[int] = Body(..., description="用例ID列表", embed=True),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    同步导出公共接口用例的请求头与请求体为 xlsx（数量不超过 EXPORT_ASYNC_THRESHOLD）。

    :param case_ids: 用例主键列表
    :param services: 自动化测试 CRUD 依赖聚合
    :return: xlsx 文件流
    """
    try:
        if not case_ids:
            return ParameterResponse(message="请至少选择一个用例")
        if len(case_ids) > EXPORT_ASYNC_THRESHOLD:
            return ParameterResponse(message=f"导出数量超过{EXPORT_ASYNC_THRESHOLD}个，请使用异步导出")
        cases_data, invalid = await prepare_export_cases(case_ids=case_ids, services=services)
        if invalid:
            return ParameterResponse(message="存在不合规用例，已取消导出", data={"invalid": invalid})
        workbook = build_export_workbook(cases_data=cases_data)
        # 先落临时文件再以 FileResponse 分块流式返回，避免整文件驻留内存OOM；发送后自动清理
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
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"导出测试用例失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"导出失败，异常描述: {e}")


@autotest_case.post("/export_datagram_async", summary="API自动化测试-异步导出公共接口用例请求头与请求体为xlsx")
async def export_testcases_async(
        case_ids: List[int] = Body(..., description="用例ID列表", embed=True),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    异步导出公共接口用例（数量超过 EXPORT_ASYNC_THRESHOLD）：校验通过后下发 Celery 任务，
    任务生成 xlsx 并将文件名落入执行记录(task_summary)，下载入口后续于异步中心提供。

    :param case_ids: 用例主键列表
    :param services: 自动化测试 CRUD 依赖聚合
    :return: 统一 HTTP 响应（含 celery_task_id）
    """
    try:
        if not case_ids:
            return ParameterResponse(message="请至少选择一个用例")
        _, invalid = await prepare_export_cases(case_ids=case_ids, services=services)
        if invalid:
            return ParameterResponse(message="存在不合规用例，已取消导出", data={"invalid": invalid})
        apply_async_result = export_testcases_task.apply_async(
            kwargs={
                "case_ids": case_ids,
                "created_user": get_current_username(),
                "report_type": AutoTestReportType.ASYNC_EXEC.value,
            },
            expires=3600,
        )
        LOGGER.info(f"异步导出测试用例任务已下发: celery_task_id={apply_async_result.task_id}, 数量={len(case_ids)}")
        return SuccessResponse(
            message="导出任务已提交后台执行，请稍后在执行记录中查看结果",
            data={"celery_task_id": apply_async_result.task_id, "count": len(case_ids)},
            total=1,
        )
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"下发异步导出任务失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"下发导出任务失败，异常描述: {e}")


@autotest_case.post("/export_script_sync", summary="API自动化测试-导出公共接口脚本为模板xlsx(同步)")
async def export_case_scripts_xlsx(
        case_ids: List[int] = Body(..., description="用例ID列表", embed=True),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    同步导出公共接口脚本（数量不超过 EXPORT_ASYNC_THRESHOLD）：复制模板副本写入数据行，
    产出文件可直接用于「导入脚本」（更新或新增公共接口）。

    :param case_ids: 用例主键列表
    :param services: 自动化测试 CRUD 依赖聚合
    :return: xlsx 文件流
    """
    try:
        if not case_ids:
            return ParameterResponse(message="请至少选择一个用例")
        if len(case_ids) > EXPORT_ASYNC_THRESHOLD:
            return ParameterResponse(message=f"导出数量超过{EXPORT_ASYNC_THRESHOLD}个，请使用异步导出")
        rows, invalid = await prepare_script_export_rows(case_ids=case_ids, services=services)
        if invalid:
            return ParameterResponse(message="存在不合规用例，已取消导出", data={"invalid": invalid})
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
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"导出公共接口脚本失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"导出失败，异常描述: {e}")


@autotest_case.post("/export_script_async", summary="API自动化测试-异步导出公共接口脚本为模板xlsx")
async def export_case_scripts_async(
        case_ids: List[int] = Body(..., description="用例ID列表", embed=True),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    异步导出公共接口脚本（数量超过 EXPORT_ASYNC_THRESHOLD）：校验通过后下发 Celery 任务，
    任务生成 xlsx 并将文件名落入执行记录(task_summary)，下载入口后续于异步中心提供。

    :param case_ids: 用例主键列表
    :param services: 自动化测试 CRUD 依赖聚合
    :return: 统一 HTTP 响应（含 celery_task_id）
    """
    try:
        if not case_ids:
            return ParameterResponse(message="请至少选择一个用例")
        _, invalid = await prepare_script_export_rows(case_ids=case_ids, services=services)
        if invalid:
            return ParameterResponse(message="存在不合规用例，已取消导出", data={"invalid": invalid})
        apply_async_result = export_case_scripts_task.apply_async(
            kwargs={
                "case_ids": case_ids,
                "created_user": get_current_username(),
                "report_type": AutoTestReportType.ASYNC_EXEC.value,
            },
            expires=3600,
        )
        LOGGER.info(f"异步导出公共接口脚本任务已下发: celery_task_id={apply_async_result.task_id}, 数量={len(case_ids)}")
        return SuccessResponse(
            message="导出任务已提交后台执行，请稍后在执行记录中查看结果",
            data={"celery_task_id": apply_async_result.task_id, "count": len(case_ids)},
            total=1,
        )
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"下发异步导出脚本任务失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"下发导出任务失败，异常描述: {e}")


@autotest_case.post("/import_script", summary="API自动化测试-导入公共接口脚本(模板xlsx)")
async def import_case_scripts(
        file: UploadFile = File(..., description="公共接口导入导出模板xlsx(仅读取第1个sheet页)"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    导入公共接口脚本：解析模板文件逐行校验，按「所属应用+接口名称」匹配，存在更新、不存在新增；
    用例类型固定公共接口、用例属性固定正用例；全部行校验通过才在单事务内落库。

    :param file: 模板 xlsx 文件
    :param services: 自动化测试 CRUD 依赖聚合
    :return: 统一 HTTP 响应（含新增/更新计数或不合规行明细）
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
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"导入公共接口脚本失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"导入失败，异常描述: {e}")
