# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_source_view.py
@DateTime: 2026/3/6
"""
import hashlib
import io
import os.path
import re
import traceback
from datetime import datetime
from typing import Optional, List, Dict, Any, Set, Union
from urllib.parse import quote

import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form, Body, Query, Depends
from pydantic import ValidationError
from starlette.responses import StreamingResponse
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from backend.applications.aotutest.dependencies import AutoTestApiServices, get_autotest_api_services
from backend.applications.aotutest.models.autotest_data_source_model import AutoTestDataSourceModel
from backend.applications.aotutest.schemas.autotest_data_source_schema import (
    AutoTestDataSourceCreate,
    AutoTestDataSourceUpdate,
    AutoTestDataSourceSaveOrUpdate,
    AutoTestDataSourceSelect,
    AutoTestDataSourceUnbindCase,
)
from backend.applications.aotutest.services.autotest_case_excel_service import style_data_source_sheet
from backend.applications.aotutest.services.autotest_data_source_parser import (
    AXIS_VERTICAL,
    json_safe_value,
    parse_xlsx_first_sheet_async,
    parse_xlsx_to_parsed_data_async,
)
from backend.applications.aotutest.services.autotest_data_source_service import (
    apply_dataframe_payload,
    build_vertical_matrix_from_step,
    clear_step_data_source_meta,
    DEFAULT_SCENE_NAMES,
    ensure_case_allows_data_source,
    ensure_request_step,
    fill_create_identity,
    resolve_case,
    resolve_case_and_step,
    resolve_enabled_data_source,
    sync_step_data_source_meta,
)
from backend.configure import LOGGER, PROJECT_CONFIG
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
    BadReqResponse,
    FileExtensionResponse
)
from backend.enums import AutoTestStepType, PUBLIC_CASE_TYPES
from backend.services import get_current_username
from backend.services.file_transfer import FileTransfer

autotest_data_source = APIRouter()


async def _serialize_data_source(instance: AutoTestDataSourceModel) -> Dict[str, Any]:
    """序列化单条数据源。"""
    data = await instance.to_dict(
        exclude_fields={
            "state",
            "created_user", "updated_user", "created_time", "updated_time",
            "reserve_1", "reserve_2", "reserve_3",
        },
        replace_fields={"id": "data_source_id"},
    )
    # Excel/pandas可能留下NaN，标准JSON无法序列化
    return json_safe_value(data)


async def _sync_step_data_source_meta(
        services: AutoTestApiServices,
        case_id: int,
        step_code: str,
        data_source_id: Optional[int],
        file_name: Optional[str],
        file_desc: Optional[str],
) -> None:
    """上传数据源后，同步回写步骤上的数据源元信息，供前端步骤编辑页直接回显。"""
    await services.step_curd.model.filter(
        case_id=case_id,
        step_code=step_code,
        state=0,
    ).update(
        data_source_id=data_source_id,
        data_source_name=(file_name or "")[:2048] or None,
        data_source_desc=(file_desc or "")[:2048] or None,
    )


def _safe_sheet_name(name: Any, used: Set[str]) -> str:
    """清洗为合法Excel sheet名（去非法字符、截断31字符、重名追加序号）。"""
    clean = re.sub(r"[:\\/?*\[\]]", "_", str(name or "").strip()) or "sheet"
    clean = clean[:31]
    base = clean
    index = 1
    while clean in used:
        suffix = f"_{index}"
        clean = base[:31 - len(suffix)] + suffix
        index += 1
    used.add(clean)
    return clean


@autotest_data_source.post("/create", summary="新增数据源", description="为指定用例步骤绑定一条数据源")
async def create_data_source(
        data_source_in: AutoTestDataSourceCreate = Body(..., description="数据源信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    为指定用例步骤创建数据源。

    定位：(case_id或case_code)且(step_id或step_code)。该步骤已有启用数据源时拒绝；
    若仅有软删记录则启用并覆盖。带dataframe时按axis清洗并生成dataset。

    :param data_source_in: 数据源入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        case, step = await resolve_case_and_step(
            services,
            case_id=data_source_in.case_id,
            case_code=data_source_in.case_code,
            step_id=data_source_in.step_id,
            step_code=data_source_in.step_code,
        )
        ensure_request_step(step)
        ensure_case_allows_data_source(case)
        parsed = await apply_dataframe_payload(data_source_in.dataframe, data_source_in.axis)
        effective = data_source_in
        if parsed:
            effective = data_source_in.model_copy(update=parsed)
        effective = fill_create_identity(effective, case, step)
        async with in_transaction():
            instance = await services.data_source_curd.create_data_source(data_source_in=effective)
            await sync_step_data_source_meta(
                services,
                case_id=case.id,
                step_code=step.step_code,
                data_source_id=instance.id,
                file_name=instance.file_name,
                file_desc=instance.file_desc,
            )
        data = await _serialize_data_source(instance)
        return SuccessResponse(message="新增成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except ValidationError as e:
        return ParameterResponse(message=str(e))
    except ValueError as e:
        return BadReqResponse(message=f"解析表格数据失败: {e}")
    except Exception as e:
        LOGGER.error(f"新增数据源失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {e}")


@autotest_data_source.delete("/delete", summary="删除数据源", description="软删除数据源并解绑步骤指针")
async def delete_data_source(
        data_source_id: Optional[int] = Query(None, description="数据源主键ID"),
        data_source_code: Optional[str] = Query(None, description="数据驱动标识代码"),
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
        step_id: Optional[int] = Query(None, description="步骤ID"),
        step_code: Optional[str] = Query(None, description="步骤标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    软删除数据源并清空对应步骤的data_source_id/name/desc。

    定位：data_source_id或data_source_code优先；否则(case_id或case_code)且(step_id或step_code)。

    :param data_source_id: 数据源主键ID
    :param data_source_code: 数据源业务标识
    :param case_id: 用例主键ID
    :param case_code: 用例业务标识
    :param step_id: 步骤主键ID
    :param step_code: 步骤业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await resolve_enabled_data_source(
            services,
            data_source_id=data_source_id,
            data_source_code=data_source_code,
            case_id=case_id,
            case_code=case_code,
            step_id=step_id,
            step_code=step_code,
            on_error=True,
        )
        async with in_transaction():
            deleted = await services.data_source_curd.soft_delete(id=instance.id)
            await clear_step_data_source_meta(
                services,
                case_id=instance.case_id,
                step_code=instance.step_code,
            )
        data = await _serialize_data_source(deleted)
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"软删除数据源信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@autotest_data_source.post("/unbind_case", summary="更新数据源(解绑)", description="解绑用例下全部HTTP/TCP步骤数据源")
async def unbind_case_data_source(
        data_in: AutoTestDataSourceUnbindCase = Body(..., description="用例定位"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    解绑指定用例下全部HTTP/TCP请求步骤的数据源：软删记录并清空步骤指针。

    :param data_in: case_id或case_code
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        case = await resolve_case(services, case_id=data_in.case_id, case_code=data_in.case_code)
        async with in_transaction():
            result = await services.data_source_curd.unbind_case_data_sources(case_id=case.id)
        return SuccessResponse(message="解绑成功", data=result)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"解绑用例下全部数据源失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"解绑失败，异常描述: {e}")


@autotest_data_source.post("/update", summary="更新数据源", description="更新数据源信息")
async def update_data_source(
        data_source_in: AutoTestDataSourceUpdate = Body(..., description="数据源信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    更新已存在的数据源。定位规则与删除相同；记录不存在则失败，不新建。

    :param data_source_in: 数据源入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        existing = await resolve_enabled_data_source(
            services,
            data_source_id=data_source_in.data_source_id,
            data_source_code=data_source_in.data_source_code,
            case_id=data_source_in.case_id,
            case_code=data_source_in.case_code,
            step_id=data_source_in.step_id,
            step_code=data_source_in.step_code,
            on_error=True,
        )
        parsed = await apply_dataframe_payload(data_source_in.dataframe, data_source_in.axis)
        updates: Dict[str, Any] = {
            "data_source_id": existing.id,
            "updated_user": get_current_username(),
        }
        if parsed:
            updates.update(parsed)
        effective = data_source_in.model_copy(update=updates)
        async with in_transaction():
            instance = await services.data_source_curd.update_data_source(data_source_in=effective)
            await sync_step_data_source_meta(
                services,
                case_id=instance.case_id,
                step_code=instance.step_code,
                data_source_id=instance.id,
                file_name=instance.file_name,
                file_desc=instance.file_desc,
            )
        data = await _serialize_data_source(instance)
        return SuccessResponse(message="更新成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except ValidationError as e:
        return ParameterResponse(message=str(e))
    except ValueError as e:
        return BadReqResponse(message=f"解析表格数据失败: {e}")
    except Exception as e:
        LOGGER.error(f"更新数据源失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {e}")


@autotest_data_source.post("/save_or_update", summary="更新数据源(保存)", description="保存或更新数据源信息")
async def save_or_update_data_source(
        data_source_in: AutoTestDataSourceSaveOrUpdate = Body(..., description="数据源信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    保存或更新数据源。

    有data_source_id或data_source_code时直接更新已有记录；
    否则按(case_id或case_code)且(step_id或step_code)定位，有则更新、无则新增。

    :param data_source_in: 数据源入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        has_ds_locator = bool(data_source_in.data_source_id) or bool((data_source_in.data_source_code or "").strip())
        parsed = await apply_dataframe_payload(data_source_in.dataframe, data_source_in.axis)
        if parsed:
            data_source_in = data_source_in.model_copy(update=parsed)

        async with in_transaction():
            if has_ds_locator:
                existing = await resolve_enabled_data_source(
                    services,
                    data_source_id=data_source_in.data_source_id,
                    data_source_code=data_source_in.data_source_code,
                    on_error=True,
                )
                data_source_in.updated_user = get_current_username()
                update_in = AutoTestDataSourceUpdate.model_validate({
                    **data_source_in.model_dump(),
                    "data_source_id": existing.id,
                })
                instance = await services.data_source_curd.update_data_source(data_source_in=update_in)
            else:
                case, step = await resolve_case_and_step(
                    services,
                    case_id=data_source_in.case_id,
                    case_code=data_source_in.case_code,
                    step_id=data_source_in.step_id,
                    step_code=data_source_in.step_code,
                )
                ensure_request_step(step)
                ensure_case_allows_data_source(case)
                existing = await services.data_source_curd.get_by_case_step(
                    case_id=case.id,
                    step_code=step.step_code,
                    on_error=False,
                    state__not=1,
                )
                if existing:
                    data_source_in.updated_user = get_current_username()
                    update_in = AutoTestDataSourceUpdate.model_validate({
                        **data_source_in.model_dump(),
                        "data_source_id": existing.id,
                    })
                    instance = await services.data_source_curd.update_data_source(data_source_in=update_in)
                else:
                    create_in = AutoTestDataSourceCreate.model_validate({
                        **data_source_in.model_dump(),
                        "case_id": case.id,
                        "case_code": case.case_code,
                        "step_id": step.id,
                        "step_code": step.step_code,
                    })
                    create_in = fill_create_identity(create_in, case, step)
                    instance = await services.data_source_curd.create_data_source(data_source_in=create_in)

            await sync_step_data_source_meta(
                services,
                case_id=instance.case_id,
                step_code=instance.step_code,
                data_source_id=instance.id,
                file_name=instance.file_name,
                file_desc=instance.file_desc,
            )

        data = await _serialize_data_source(instance)
        return SuccessResponse(message="保存成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except ValidationError as e:
        return ParameterResponse(message=str(e))
    except ValueError as e:
        return BadReqResponse(message=f"解析表格数据失败: {e}")
    except Exception as e:
        LOGGER.error(f"保存或更新数据源信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"保存失败，异常描述: {e}")


@autotest_data_source.get("/build", summary="构建数据源矩阵", description="查询已有数据源矩阵或根据步骤报文构建垂直矩阵")
async def build_data_source(
        data_source_id: Optional[int] = Query(None, description="数据源主键ID"),
        data_source_code: Optional[str] = Query(None, description="数据驱动标识代码"),
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
        step_id: Optional[int] = Query(None, description="步骤ID"),
        step_code: Optional[str] = Query(None, description="步骤标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    获取用例下指定步骤的数据源结构，只查询不落库。

    能定位到已有数据源时直接返回其dataframe；否则根据当前HTTP/TCP步骤报文构建垂直矩阵。

    :param data_source_id: 数据源主键ID
    :param data_source_code: 数据源业务标识
    :param case_id: 用例主键ID
    :param case_code: 用例业务标识
    :param step_id: 步骤主键ID
    :param step_code: 步骤业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        has_ds_locator = bool(data_source_id) or bool((data_source_code or "").strip())
        if has_ds_locator:
            instance = await resolve_enabled_data_source(
                services,
                data_source_id=data_source_id,
                data_source_code=data_source_code,
                on_error=True,
            )
            data = await _serialize_data_source(instance)
            return SuccessResponse(message="查询成功", data=data, total=1)

        case, step = await resolve_case_and_step(
            services,
            case_id=case_id,
            case_code=case_code,
            step_id=step_id,
            step_code=step_code,
        )
        ensure_request_step(step)
        existing = await services.data_source_curd.get_by_case_step(
            case_id=case.id,
            step_code=step.step_code,
            on_error=False,
            state__not=1,
        )
        if existing:
            data = await _serialize_data_source(existing)
            return SuccessResponse(message="查询成功", data=data, total=1)

        matrix = build_vertical_matrix_from_step(step)
        data = {
            "case_id": case.id,
            "case_code": case.case_code,
            "step_id": step.id,
            "step_code": step.step_code,
            "dataframe": matrix,
            "axis": AXIS_VERTICAL,
            "dataset": {},
            "dataset_names": list(DEFAULT_SCENE_NAMES),
            "data_source_id": None,
        }
        return SuccessResponse(message="构建成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message), data=getattr(e, "data", None))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"构建数据源矩阵失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_data_source.get("/get", summary="查询数据源", description="根据条件查询单条数据源信息")
async def get_data_source(
        data_source_id: Optional[int] = Query(None, description="数据源主键ID"),
        data_source_code: Optional[str] = Query(None, description="数据驱动标识代码"),
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
        step_id: Optional[int] = Query(None, description="步骤ID"),
        step_code: Optional[str] = Query(None, description="步骤标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据条件查询单条数据源信息。

    定位优先级：data_source_id > data_source_code > (case+step)。

    :param data_source_id: 数据源主键ID
    :param data_source_code: 数据源业务标识
    :param case_id: 用例主键ID
    :param case_code: 用例业务标识
    :param step_id: 步骤主键ID
    :param step_code: 步骤业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if data_source_id:
            instance = await services.data_source_curd.get_by_id(data_source_id=data_source_id, on_error=True, state__not=1)
        elif (data_source_code or "").strip():
            instance = await services.data_source_curd.get_by_code(data_source_code=data_source_code.strip(), on_error=True, state__not=1)
        elif (case_id or (case_code or "").strip()) and (step_id or (step_code or "").strip()):
            instance = await services.data_source_curd.get_by_case_step(
                case_id=case_id,
                case_code=case_code,
                step_id=step_id,
                step_code=step_code,
                on_error=True,
                state__not=1
            )
        else:
            return ParameterResponse(
                message="请提供参数[data_source_id, data_source_code]或[case_id, case_code, step_id, step_code]进行查询"
            )
        if isinstance(instance, list):
            return ParameterResponse(message="当前条件匹配多条记录，请使用get_by_case_step或search接口")
        data = await _serialize_data_source(instance)
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message), data=e.data)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件查询单条数据源信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_data_source.post(path="/query_dataset_names", summary="查询数据场景", description="查询案例数据场景名称")
async def get_dataset_names(
        case_id: int = Form(..., description="用例ID"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    案例数据场景查询。

    合并当前用例下所有数据源的dataset_names，去重并保持出现顺序。

    :param case_id: 用例主键ID
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    if not case_id:
        return ParameterResponse(message="参数[case_id]不允许为空")

    data_source_instances = await services.data_source_curd.model.filter(
        case_id=case_id,
        state__not=1
    ).order_by("created_time").all()
    merged_names: List[str] = []
    seen: Set[str] = set()
    for ds in data_source_instances:
        if isinstance(ds.dataset_names, list):
            for name in ds.dataset_names:
                name_str = str(name).strip()
                if name_str and name_str not in seen:
                    seen.add(name_str)
                    merged_names.append(name_str)

    return SuccessResponse(message="查询成功", data=merged_names)


@autotest_data_source.post("/search", summary="查询数据源列表", description="根据条件分页查询数据源列表信息(Body)")
async def search_data_sources(
        data_source_in: AutoTestDataSourceSelect = Body(..., description="查询条件"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据条件分页查询数据源。

    :param data_source_in: 数据源查询入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if data_source_in.data_source_id:
            q &= Q(id=data_source_in.data_source_id)
        if data_source_in.data_source_code:
            q &= Q(data_source_code__icontains=data_source_in.data_source_code.strip())
        if data_source_in.case_id:
            q &= Q(case_id=data_source_in.case_id)
        if data_source_in.case_code:
            q &= Q(case_code__icontains=data_source_in.case_code)
        if data_source_in.step_id:
            q &= Q(step_id=data_source_in.step_id)
        if data_source_in.step_code:
            q &= Q(step_code__icontains=data_source_in.step_code)
        if data_source_in.file_name:
            q &= Q(file_name__icontains=data_source_in.file_name)
        if data_source_in.file_path:
            q &= Q(file_path__icontains=data_source_in.file_path)
        q &= Q(state=data_source_in.state)

        total, instances = await services.data_source_curd.select_data_sources(
            search=q,
            page=data_source_in.page,
            page_size=data_source_in.page_size,
            order=data_source_in.order,
        )
        serializes: List[Dict[str, Any]] = []
        for inst in instances:
            serializes.append(await _serialize_data_source(inst))
        return SuccessResponse(message="查询成功", data=serializes, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件分页查询数据源列表信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_data_source.get("/get_by_case_step", summary="查询步骤数据源", description="根据用例与步骤查询数据源(单条或列表)")
async def get_data_source_by_case_step(
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
        step_id: Optional[int] = Query(None, description="步骤ID"),
        step_code: Optional[str] = Query(None, description="步骤标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),

):
    """
    根据用例与步骤查询数据源。

    未传step条件时返回该用例下数据源列表；传入step条件时返回单条。

    :param case_id: 用例主键ID
    :param case_code: 用例业务标识
    :param step_id: 步骤主键ID
    :param step_code: 步骤业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        result = await services.data_source_curd.get_by_case_step(
            case_id=case_id,
            case_code=case_code,
            step_id=step_id,
            step_code=step_code,
            on_error=True,
            state__not=1
        )
        if isinstance(result, list):
            serializes = [await _serialize_data_source(x) for x in result]
            return SuccessResponse(message="查询成功", data=serializes, total=len(serializes))
        data = await _serialize_data_source(result)
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据用例与步骤查询数据源失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_data_source.get("/scene_names_by_case", summary="查询数据源场景列名", description="根据用例查询已落库数据源场景列名")
async def get_scene_names_by_case(
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    返回当前用例下所有已落库数据源的场景列名信息，用于无数据源绑定步骤生成空白模板。

    :param case_id: 用例主键ID
    :param case_code: 用例标识代码
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if not case_id and not (case_code or "").strip():
            return ParameterResponse(message="参数[case_id, case_code]不允许为空")

        # 定位用例，优先使用 case_id
        effective_case_id: Optional[int] = case_id
        if not effective_case_id and (case_code or "").strip():
            case_instance = await services.case_curd.get_by_code(
                case_code=case_code.strip(),
                on_error=False,
                state__not=1,
            )
            effective_case_id = case_instance.id if case_instance else None

        if not effective_case_id:
            return NotFoundResponse(message="未找到对应用例信息")

        # 查询该用例下所有未软删的数据源
        data_source_instances = await services.data_source_curd.get_by_case_step(
            case_id=effective_case_id,
            on_error=False,
            state__not=1
        )
        if not isinstance(data_source_instances, list):
            data_source_instances = [data_source_instances] if data_source_instances else []

        # 预查步骤信息（step_id -> {step_no, step_name}）
        step_ids = [ds.step_id for ds in data_source_instances if ds.step_id]
        step_map: Dict[int, Dict[str, Any]] = {}
        if step_ids:
            step_models = await services.step_curd.model.filter(
                id__in=step_ids,
                state__not=1,
            ).all()
            step_map = {
                sm.id: {
                    "step_no": sm.step_no,
                    "step_name": sm.step_name,
                }
                for sm in step_models
            }

        data_source_info: List[Dict[str, Any]] = []
        seen_scenes: List[str] = []
        seen_set: Set[str] = set()

        for ds in data_source_instances:
            if not ds or ds.state == 1:
                continue
            scene_names = []
            if isinstance(ds.dataset_names, list):
                for name in ds.dataset_names:
                    name_str = str(name).strip()
                    if not name_str:
                        continue
                    scene_names.append(name_str)
                    if name_str not in seen_set:
                        seen_set.add(name_str)
                        seen_scenes.append(name_str)

            step_meta = step_map.get(ds.step_id) or {}
            data_source_info.append({
                "step_id": str(ds.step_id) if ds.step_id else None,
                "step_no": str(step_meta.get("step_no", "")) if step_meta.get("step_no") is not None else None,
                "step_name": step_meta.get("step_name") or None,
                "data_source_scene_names": scene_names,
            })
        data_source_len = len(data_source_info)
        data_source_scenes: Dict[str, Any] = {
            "case_id": effective_case_id,
            "data_source_info": data_source_info,
            "data_source_scene_name_set": seen_scenes,
        }
        if not data_source_len:
            data_source_scenes["default"] = [
                ["", "场景1名称", "场景2名称", "场景3名称"],
                ["HEAD", "", "", ""],
                ["", "", "", ""],
                ["BODY", "", "", ""],
                ["", "", "", ""],
                ["ASSERT_HEAD", "", "", ""],
                ["", "", "", ""],
                ["ASSERT_BODY", "", "", ""],
                ["", "", "", ""]
            ]
        return SuccessResponse(message="查询成功", data=data_source_scenes, total=data_source_len)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据用例查询已落库数据源场景列名失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_data_source.get("/dataset_scenario", summary="查询数据集场景", description="查询某步骤下单个数据集场景")
async def get_dataset_scenario(
        case_id: int = Query(..., description="用例ID"),
        step_code: str = Query(..., description="步骤标识代码"),
        dataset_name: str = Query(..., description="数据集/场景名称"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    查询某步骤下单个数据集场景。

    :param case_id: 用例主键ID
    :param step_code: 步骤业务标识
    :param dataset_name: 数据集场景名称
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        scenario = await services.data_source_curd.get_dataset_scenario(
            case_id=case_id,
            step_code=step_code,
            dataset_name=dataset_name,
            state__not=1
        )
        if scenario is None:
            return SuccessResponse(message="未找到场景数据", data=None, total=0)
        return SuccessResponse(message="查询成功", data=scenario, total=1)
    except Exception as e:
        LOGGER.error(f"查询某步骤下单个数据集场景失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_data_source.get("/import_template_download", summary="下载数据源导入模板", description="下载请求步骤数据集导入模板xlsx")
async def download_import_template():
    """
    下载请求步骤数据集导入模板xlsx。

    分发仓库内置于output/template的xlsx（HTTP/TCP请求步骤共用）；流式读取，不加UTF-8 BOM，避免损坏二进制格式。

    :return: 文件流响应
    """
    filepath = os.path.normpath(os.path.join(PROJECT_CONFIG.OUTPUT_DIR, "template", "测试用例HTTP请求步骤数据源模板.xlsx"))
    if not filepath.startswith(PROJECT_CONFIG.OUTPUT_DIR) or not os.path.isfile(filepath):
        return NotFoundResponse(message="导入模板文件不存在，请确认已部署 output/template 下模板文件")
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


@autotest_data_source.post("/single_step_dataset_upload", summary="上传单步骤数据源", description="参数化驱动单步骤数据集上传")
async def single_step_dataset_upload(
        case_id: int = Form(..., description="用例ID"),
        step_id: str = Form(..., description="步骤ID"),
        step_code: str = Form(..., description="步骤标识代码"),
        file_desc: Optional[str] = Form(None, description="数据驱动文件描述"),
        file: UploadFile = File(..., description="单步骤数据驱动文件(仅支持.xlsx后缀, 单步骤模式仅读取第1个sheet页)"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    参数化驱动-单步骤数据集上传。

    :param case_id: 用例主键ID
    :param step_id: 步骤主键ID
    :param step_code: 步骤业务标识
    :param file_desc: 文件描述
    :param file: 上传文件
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    if not (file.filename or "").endswith(".xlsx"):
        return FileExtensionResponse(message="仅支持.xlsx后缀的数据驱动文件")

    try:
        step_instance = await services.step_curd.get_by_conditions(
            on_error=True,
            only_one=True,
            state__not=1,
            id=step_id,
            case_id=case_id,
            step_code=step_code,
        )
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询步骤失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询步骤失败，异常描述: {e}")

    if step_instance.step_type not in (AutoTestStepType.HTTP.value, AutoTestStepType.TCP.value):
        return ParameterResponse(message="仅支持对HTTP/TCP请求步骤上传数据驱动文件")

    try:
        case_instance = await services.case_curd.get_by_id(case_id=case_id, on_error=True, state__not=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询用例失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询用例失败，异常描述: {e}")
    if case_instance.case_type in PUBLIC_CASE_TYPES:
        return BadReqResponse(message="公共脚本/公共接口不允许使用数据源")

    destination: str = os.path.join(PROJECT_CONFIG.OUTPUT_UPLOAD_DIR, "autotest", str(case_id))
    ok, path_or_error = await FileTransfer.save_upload_file_chunks(
        upload_file=file,
        destination=destination,
        add_timestamp=False,
        check_filename=True,
        check_filetype=True,
        check_filesize=True,
        add_left_identifier=step_code,
        upload_file_size="tiny",
    )
    if not ok:
        return FailureResponse(message=f"数据驱动文件上传失败: {path_or_error}")

    file_hash: str = ""
    file_path: str = path_or_error
    file_name: str = (getattr(file, "filename", None) or "").strip()[:255]
    try:
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        file_hash = (file_hash or "")[:255]
    except Exception as e:
        LOGGER.warning(f"计算文件哈希失败: {e}")

    try:
        step_data, dataset_names, dataframe, axis = await parse_xlsx_first_sheet_async(file_path)
    except FileNotFoundError as e:
        return FailureResponse(message=f"解析文件失败，异常描述: {e}")
    except ValueError as e:
        return BadReqResponse(message=f"解析失败: {str(e)}")
    if not step_data:
        return BadReqResponse(message="解析结果为空, 第1个sheet无有效数据")
    try:
        created_user = get_current_username()
        instance = await services.data_source_curd.create_data_sources_from_parsed(
            case_id=case_id,
            case_code=case_instance.case_code,
            step_id=int(step_id),
            step_code=step_code,
            file_name=file_name or None,
            file_path=file_path,
            file_hash=file_hash or None,
            file_desc=(file_desc or "")[:2048].strip() or None,
            parsed_data=step_data,
            dataset_names=dataset_names,
            dataframe=dataframe,
            axis=axis,
            created_user=created_user,
        )
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"数据源保存失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"数据源保存失败，异常描述: {e}")

    await _sync_step_data_source_meta(
        services=services,
        case_id=case_id,
        step_code=step_code,
        data_source_id=instance.id,
        file_name=file_name,
        file_desc=file_desc,
    )
    data = await _serialize_data_source(instance)
    return SuccessResponse(message="单步骤数据集上传成功，已创建数据源并同步缓存", data=data, total=1)


@autotest_data_source.get("/single_step_dataset_download", summary="导出步骤数据源", description="根据用例步骤导出数据源xlsx")
async def single_step_dataset_download(
        case_id: int = Query(..., description="用例ID"),
        step_id: int = Query(..., description="步骤ID"),
        step_code: str = Query(..., description="步骤标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据用例步骤导出数据源xlsx。

    :param case_id: 用例主键ID
    :param step_id: 步骤主键ID
    :param step_code: 步骤业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 文件流响应
    """
    try:
        instance = await services.data_source_curd.get_by_case_step(
            case_id=case_id,
            step_id=step_id,
            step_code=step_code,
            on_error=True,
            state__not=1
        )
        matrix = instance.dataframe if isinstance(instance.dataframe, list) else []
        df = pd.DataFrame(matrix if matrix else [[]])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, header=False, sheet_name="Sheet1")
            # 统一样式：分区标记黄底、居中换行、行高/列宽自适应（与报文导出风格一致）
            style_data_source_sheet(writer.sheets["Sheet1"])
        output.seek(0)

        file_name = f"数据源导出_{step_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        quoted_name: str = quote(file_name)
        headers: Dict[str, str] = {"Content-Disposition": f"attachment; filename*=UTF-8''{quoted_name}"}
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
        )
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"导出数据源xlsx失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"导出失败，异常描述: {e}")


@autotest_data_source.post("/batch_step_dataset_upload", summary="上传步骤数据源", description="参数化驱动多步骤数据集批量上传")
async def batch_step_dataset_upload(
        case_id: int = Form(..., description="用例ID"),
        file_desc: Optional[str] = Form(None, description="数据驱动文件场景描述"),
        file: UploadFile = File(..., description="xlsx 文件(每个 sheet 名须对应步骤树中一个 HTTP/TCP 请求步骤的步骤名)"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    参数化驱动-多步骤数据集批量上传。

    根据 sheet 名匹配步骤树中的HTTP/TCP请求步骤（步骤名唯一），校验通过后逐步骤创建数据源。
    校验规则（任一不满足即整体拒绝，不落库）：
    - 每个sheet名均能匹配到步骤树中的HTTP/TCP请求步骤；
    - 各sheet的场景数量一致；
    - 各sheet的场景名称及顺序一致。

    :param case_id: 用例主键ID
    :param file_desc: 文件描述
    :param file: 上传文件
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    if not case_id:
        return ParameterResponse(message="参数[case_id]不允许为空")
    if not (file.filename or "").endswith(".xlsx"):
        return FileExtensionResponse(message="仅支持.xlsx后缀的数据驱动文件")

    # 获取用例全部步骤（含子步骤），根据步骤名建立HTTP/TCP请求步骤映射
    try:
        all_steps = await services.step_curd.model.filter(case_id=case_id, state__not=1)
    except Exception as e:
        LOGGER.error(f"查询步骤树失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询步骤树失败，异常描述: {e}")

    step_map: Dict[str, Dict[str, Any]] = {}
    for step in all_steps:
        if step.step_type not in (AutoTestStepType.HTTP, AutoTestStepType.TCP):
            continue
        step_name: str = step.step_name
        if step_name:
            step_map[step_name] = {"step_id": step.id, "step_code": step.step_code}
    if not step_map:
        return BadReqResponse(message="该用例步骤树中没有HTTP/TCP请求步骤，无法批量上传数据源")

    try:
        case_instance = await services.case_curd.get_by_id(case_id=case_id, on_error=True, state__not=1)
        case_code: str = case_instance.case_code
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询用例失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询用例失败，异常描述: {e}")
    if case_instance.case_type in PUBLIC_CASE_TYPES:
        return BadReqResponse(message="公共脚本/公共接口不允许使用数据源，无法批量上传数据源")

    destination: str = os.path.join(PROJECT_CONFIG.OUTPUT_UPLOAD_DIR, "autotest", str(case_id))
    ok, path_or_error = await FileTransfer.save_upload_file_chunks(
        upload_file=file,
        destination=destination,
        add_timestamp=True,
        check_filename=True,
        check_filetype=True,
        check_filesize=True,
        upload_file_size="small",
    )
    if not ok:
        return FailureResponse(message=f"文件保存失败: {path_or_error}")

    file_hash: str = ""
    file_path: str = path_or_error
    file_name: str = (getattr(file, "filename", None) or "").strip()[:255]
    try:
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        file_hash = (file_hash or "")[:255]
    except Exception as e:
        LOGGER.warning(f"计算文件哈希失败: {e}")

    try:
        full_parsed, _, sheet_axes, sheet_dataframes = await parse_xlsx_to_parsed_data_async(file_path)
    except FileNotFoundError as e:
        return FailureResponse(message=f"解析文件失败，异常描述: {e}")
    except ValueError as e:
        return BadReqResponse(message=f"解析失败: {str(e)}")
    if not full_parsed:
        return BadReqResponse(message="解析结果为空")

    # 校验一：每个sheet名均须匹配到HTTP/TCP请求步骤
    unmatched = [str(name) for name in full_parsed if name not in step_map]
    if unmatched:
        return BadReqResponse(message=f"含sheet未匹配到HTTP/TCP请求步骤：{', '.join(unmatched)}")

    # 校验二：各sheet场景数量一致
    scene_lists = {name: list(scenes.keys()) for name, scenes in full_parsed.items()}
    if len({len(scenes) for scenes in scene_lists.values()}) > 1:
        return BadReqResponse(message="各sheet的场景数量不一致，请检查后重新上传")

    # 校验三：各sheet场景名称及顺序一致
    reference_scenes = next(iter(scene_lists.values()))
    for name, scenes in scene_lists.items():
        if scenes != reference_scenes:
            return BadReqResponse(message=f"各sheet的场景名称或顺序不一致：sheet[{name}]")

    # 事务内逐步骤创建数据源：一致性操作，任一步骤失败则整体回滚
    created_user = get_current_username()
    created: List[Dict[str, Any]] = []
    try:
        async with in_transaction():
            for sheet_name, step_data in full_parsed.items():
                step_info: Dict[str, Any] = step_map[sheet_name]
                step_id: int = step_info["step_id"]
                step_code: str = step_info["step_code"]
                instance = await services.data_source_curd.create_data_sources_from_parsed(
                    case_id=case_id,
                    case_code=case_code,
                    step_id=int(step_id),
                    step_code=step_code,
                    file_name=file_name or None,
                    file_path=file_path,
                    file_hash=file_hash or None,
                    file_desc=(file_desc or "")[:2048].strip() or None,
                    parsed_data=step_data,
                    dataset_names=sorted(step_data.keys()),
                    dataframe=sheet_dataframes[sheet_name],
                    axis=sheet_axes.get(sheet_name, AXIS_VERTICAL),
                    created_user=created_user,
                )
                created.append(await _serialize_data_source(instance))
                await _sync_step_data_source_meta(
                    services=services,
                    case_id=case_id,
                    step_code=step_code,
                    data_source_id=instance.id,
                    file_name=file_name,
                    file_desc=file_desc,
                )
    except Exception as e:
        LOGGER.error(f"批量上传数据源失败, 已全部回滚: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"批量上传数据源失败，已全部回滚: {e}")

    return SuccessResponse(
        message=f"多步骤数据集批量上传成功，共{len(created)}条数据源",
        data=created,
        total=len(created),
    )


@autotest_data_source.get("/batch_step_dataset_download", summary="导出步骤数据源汇总", description="根据用例汇总导出所有步骤数据源xlsx")
async def batch_step_dataset_download(
        case_id: int = Query(..., description="用例ID"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    汇总导出用例下所有HTTP/TCP请求步骤绑定的数据源为单个xlsx。

    每个步骤一个sheet（sheet名=步骤名，数据=该步骤数据源的dataframe）。

    :param case_id: 用例主键ID
    :param services: 自动化测试CRUD依赖聚合
    :return: 文件流响应
    """
    try:
        data_sources = await services.data_source_curd.get_by_case_step(case_id=case_id, state__not=1)
        if not data_sources:
            return BadReqResponse(message="该用例下没有可导出的数据源")

        # 获取用例全部步骤，创建step_code/step_id -> step_name映射
        all_steps = await services.step_curd.model.filter(case_id=case_id, state__not=1)
        step_name_map: Dict[Union[str, int], str] = {}
        for step in all_steps:
            step_id: int = step.id
            step_name: str = step.step_name
            if not step_name or step.step_type not in (AutoTestStepType.HTTP, AutoTestStepType.TCP):
                continue
            if step.step_code:
                step_name_map[step.step_code] = step_name
            step_name_map[step_id] = step_name

        output = io.BytesIO()
        used_names: Set[str] = set()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for data_source in data_sources:
                dataset_id: int = data_source.step_id
                dataset_code: str = data_source.step_code
                step_name = step_name_map.get(dataset_code) or step_name_map.get(dataset_id)
                dataset_dataframe = data_source.dataframe if isinstance(data_source.dataframe, list) else []
                df = pd.DataFrame(dataset_dataframe if dataset_dataframe else [[]])
                safe_name = _safe_sheet_name(step_name, used_names)
                df.to_excel(writer, index=False, header=False, sheet_name=safe_name)
                # 统一样式：分区标记黄底、居中换行、行高/列宽自适应（与报文导出风格一致）
                style_data_source_sheet(writer.sheets[safe_name])
        output.seek(0)

        file_name = f"数据源汇总_{case_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_name)}"}
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
        )
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"汇总导出数据源xlsx失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"导出失败，异常描述: {e}")
