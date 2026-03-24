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
import traceback
from datetime import datetime
from typing import Optional, List, Dict, Any
from urllib.parse import quote

import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form, Body, Query
from starlette.responses import StreamingResponse
from tortoise.expressions import Q

from backend import LOGGER, PROJECT_CONFIG
from backend.applications.aotutest.models.autotest_model import AutoTestApiDataSourceInfo
from backend.applications.aotutest.schemas.autotest_data_source_schema import (
    AutoTestDataSourceCreate,
    AutoTestDataSourceUpdate,
    AutoTestDataSourceSelect,
)
from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
from backend.applications.aotutest.services.autotest_data_source_crud import AUTOTEST_DATA_SOURCE_CRUD
from backend.applications.aotutest.services.autotest_data_source_parser import (
    parse_xlsx_first_sheet_async,
    parse_xlsx_to_parsed_data_async,
)
from backend.applications.aotutest.services.autotest_step_crud import AUTOTEST_API_STEP_CRUD
from backend.applications.base.services.file_transfer import FileTransfer
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    DataAlreadyExistsException,
    ParameterException,
    DataBaseStorageException,
)
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    BadReqResponse,
    ParameterResponse,
    FileExtensionResponse,
    DataBaseStorageResponse, NotFoundResponse,
)
from backend.enums.autotest_enum import AutoTestStepType
from backend.services.ctx import CTX_USER_ID

autotest_data_source = APIRouter()

_SERIALIZE_EXCLUDE = {
    "state",
    "created_user",
    "updated_user",
    "created_time",
    "updated_time",
    "reserve_1",
    "reserve_2",
    "reserve_3",
}


async def _serialize_data_source(instance: AutoTestApiDataSourceInfo) -> Dict[str, Any]:
    """序列化单条数据源（与 env 视图 replace id 为业务主键字段风格一致）。"""
    return await instance.to_dict(
        exclude_fields=_SERIALIZE_EXCLUDE,
        replace_fields={"id": "data_source_id"},
    )


async def _sync_step_data_source_meta(
        case_id: int,
        step_code: str,
        file_name: Optional[str],
        file_desc: Optional[str],
) -> None:
    """上传数据源后，同步回写步骤上的数据源元信息，供前端步骤编辑页直接回显。"""
    try:
        await AUTOTEST_API_STEP_CRUD.model.filter(
            case_id=case_id,
            step_code=step_code,
            state=0,
        ).update(
            data_source_name=(file_name or "")[:2048] or None,
            data_source_desc=(file_desc or "")[:2048] or None,
        )
    except Exception as e:
        LOGGER.warning(f"同步步骤数据源元信息失败(case_id={case_id}, step_code={step_code}): {e}")


async def _get_case_root_steps_async(case_id: int) -> List[Dict[str, Any]]:
    """获取用例根步骤列表（按 step_no 排序）。"""
    tree_data = await AUTOTEST_API_STEP_CRUD.get_by_case_id(case_id=case_id)
    if not tree_data or not isinstance(tree_data, list):
        return []
    if len(tree_data) > 1 and isinstance(tree_data[-1], dict) and "total_steps" in tree_data[-1]:
        tree_data = tree_data[:-1]
    root_steps = [s for s in tree_data if isinstance(s, dict) and s.get("step_no") is not None]
    root_steps.sort(key=lambda x: (x.get("step_no") or 0))
    return root_steps


# ---------------------------------------------------------------------------
# CRUD 风格接口（对齐 autotest_env_view）
# ---------------------------------------------------------------------------


@autotest_data_source.post("/create", summary="API自动化测试-新增数据源")
async def create_data_source_info(
        data_in: AutoTestDataSourceCreate = Body(..., description="数据源信息"),
):
    try:
        instance = await AUTOTEST_DATA_SOURCE_CRUD.create_data_source(data_source_in=data_in)
        data = await _serialize_data_source(instance)
        LOGGER.info(f"新增数据源成功, 结果明细: {data}")
        return SuccessResponse(message="新增成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增数据源失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败, 异常描述: {e}")


@autotest_data_source.delete("/delete", summary="API自动化测试-删除数据源(软删)")
async def delete_data_source_info(
        data_source_id: Optional[int] = Query(None, description="数据源主键ID"),
        data_source_code: Optional[str] = Query(None, description="数据驱动标识代码"),
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
        step_id: Optional[int] = Query(None, description="步骤ID"),
        step_code: Optional[str] = Query(None, description="步骤标识代码"),
):
    try:
        instance = await AUTOTEST_DATA_SOURCE_CRUD.delete_data_source(
            data_source_id=data_source_id,
            data_source_code=data_source_code,
            case_id=case_id,
            case_code=case_code,
            step_id=step_id,
            step_code=step_code,
        )
        data = await _serialize_data_source(instance)
        LOGGER.info(f"删除数据源成功, 结果明细: {data}")
        return SuccessResponse(message="删除成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"删除数据源失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败, 异常描述: {e}")


@autotest_data_source.post("/update", summary="API自动化测试-更新数据源")
async def update_data_source_info(
        data_in: AutoTestDataSourceUpdate = Body(..., description="数据源信息"),
):
    try:
        instance = await AUTOTEST_DATA_SOURCE_CRUD.update_data_source(data_source_in=data_in)
        data = await _serialize_data_source(instance)
        LOGGER.info(f"更新数据源成功, 结果明细: {data}")
        return SuccessResponse(message="更新成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"更新数据源失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败, 异常描述: {e}")


@autotest_data_source.get("/get", summary="API自动化测试-查询单条数据源")
async def get_data_source_info(
        data_source_id: Optional[int] = Query(None, description="数据源主键ID"),
        data_source_code: Optional[str] = Query(None, description="数据驱动标识代码"),
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
        step_id: Optional[int] = Query(None, description="步骤ID"),
        step_code: Optional[str] = Query(None, description="步骤标识代码"),
):
    """定位优先级：data_source_id > data_source_code > (case+step)。"""
    try:
        if data_source_id:
            instance = await AUTOTEST_DATA_SOURCE_CRUD.get_by_id(
                data_source_id=data_source_id,
                on_error=True,
            )
        elif (data_source_code or "").strip():
            instance = await AUTOTEST_DATA_SOURCE_CRUD.get_by_code(
                data_source_code=data_source_code.strip(),
                on_error=True,
            )
        elif (case_id or (case_code or "").strip()) and (step_id or (step_code or "").strip()):
            instance = await AUTOTEST_DATA_SOURCE_CRUD.get_by_case_step(
                case_id=case_id,
                case_code=case_code,
                step_id=step_id,
                step_code=step_code,
                on_error=True,
            )
        else:
            return ParameterResponse(
                message="查询参数缺失, 需提供data_source_id或data_source_code或(case_id|case_code)+(step_id|step_code)进行查询"
            )
        if isinstance(instance, list):
            return ParameterResponse(message="当前条件匹配多条记录，请使用 get_by_case_step 或 search 接口")
        data = await _serialize_data_source(instance)
        LOGGER.info(f"查询数据源成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message), data=e.data)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询数据源失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 异常描述: {e}")


@autotest_data_source.post("/search", summary="API自动化测试-按条件分页查询数据源")
async def search_data_source_info(
        sel_in: AutoTestDataSourceSelect = Body(..., description="查询条件"),
):
    try:
        q = Q()
        if sel_in.data_source_id:
            q &= Q(id=sel_in.data_source_id)
        if sel_in.data_source_code:
            q &= Q(data_source_code__icontains=sel_in.data_source_code.strip())
        if sel_in.case_id:
            q &= Q(case_id=sel_in.case_id)
        if sel_in.case_code:
            q &= Q(case_code__icontains=sel_in.case_code)
        if sel_in.step_id:
            q &= Q(step_id=sel_in.step_id)
        if sel_in.step_code:
            q &= Q(step_code__icontains=sel_in.step_code)
        if sel_in.file_name:
            q &= Q(file_name__icontains=sel_in.file_name)
        if sel_in.file_path:
            q &= Q(file_path__icontains=sel_in.file_path)
        q &= Q(state=sel_in.state)

        total, instances = await AUTOTEST_DATA_SOURCE_CRUD.select_data_sources(
            search=q,
            page=sel_in.page,
            page_size=sel_in.page_size,
            order=sel_in.order,
        )
        serializes: List[Dict[str, Any]] = []
        for inst in instances:
            serializes.append(await _serialize_data_source(inst))
        LOGGER.info(f"按条件查询数据源成功, 结果数量: {total}")
        return SuccessResponse(message="查询成功", data=serializes, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按条件查询数据源失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 异常描述: {e}")


@autotest_data_source.get("/get_by_case_step", summary="API自动化测试-按用例与步骤查询数据源(单条或列表)")
async def get_data_source_by_case_step(
        case_id: Optional[int] = Query(None, description="用例ID"),
        case_code: Optional[str] = Query(None, description="用例标识代码"),
        step_id: Optional[int] = Query(None, description="步骤ID"),
        step_code: Optional[str] = Query(None, description="步骤标识代码"),
):
    """未传 step 条件时返回该用例下数据源列表；传入 step 条件时返回单条。"""
    try:
        result = await AUTOTEST_DATA_SOURCE_CRUD.get_by_case_step(
            case_id=case_id,
            case_code=case_code,
            step_id=step_id,
            step_code=step_code,
            on_error=True,
        )
        if isinstance(result, list):
            serializes = [await _serialize_data_source(x) for x in result]
            return SuccessResponse(message="查询成功", data=serializes, total=len(serializes))
        data = await _serialize_data_source(result)
        return SuccessResponse(message="查询成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按 case_step 查询数据源失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 异常描述: {e}")


@autotest_data_source.get("/export_xlsx", summary="API自动化测试-按用例步骤导出数据源xlsx")
async def export_data_source_xlsx(
        case_id: int = Query(..., description="用例ID"),
        step_id: int = Query(..., description="步骤ID"),
        step_code: str = Query(..., description="步骤标识代码"),
):
    """从数据库 dataframe 字段导出 xlsx（不依赖前端当前表格状态）。"""
    try:
        instance = await AUTOTEST_DATA_SOURCE_CRUD.get_by_case_step(
            case_id=case_id,
            step_id=step_id,
            step_code=step_code,
            on_error=True,
        )
        if isinstance(instance, list) or not instance:
            return ParameterResponse(message="导出失败，未定位到唯一数据源记录")

        matrix = instance.dataframe if isinstance(instance.dataframe, list) else []
        df = pd.DataFrame(matrix if matrix else [[]])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, header=False, sheet_name="Sheet1")
        output.seek(0)

        safe_base = (instance.file_name or f"dataset_{case_id}_{step_code}").strip()
        safe_base = safe_base[:-5] if safe_base.lower().endswith(".xlsx") else safe_base
        file_name = f"{safe_base}_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        quoted_name = quote(file_name)
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted_name}"
        }
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
        )
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"导出数据源xlsx失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"导出失败, 异常描述: {e}")


@autotest_data_source.get("/dataset_scenario", summary="API自动化测试-查询某步骤下单个数据集场景")
async def get_dataset_scenario_info(
        case_id: int = Query(..., description="用例ID"),
        step_code: str = Query(..., description="步骤标识代码"),
        dataset_name: str = Query(..., description="数据集/场景名称"),
):
    try:
        scenario = await AUTOTEST_DATA_SOURCE_CRUD.get_dataset_scenario(
            case_id=case_id,
            step_code=step_code,
            dataset_name=dataset_name,
        )
        if scenario is None:
            return SuccessResponse(message="未找到场景数据", data=None, total=0)
        return SuccessResponse(message="查询成功", data=scenario, total=1)
    except Exception as e:
        LOGGER.error(f"查询数据集场景失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 异常描述: {e}")


@autotest_data_source.post("/single_step_dataset_upload", summary="参数化驱动-单步骤数据集上传")
async def single_step_dataset_upload(
        case_id: int = Form(..., description="用例ID"),
        step_id: str = Form(..., description="步骤ID"),
        step_code: str = Form(..., description="步骤标识代码"),
        file_desc: Optional[str] = Form(None, description="数据驱动文件描述"),
        file: UploadFile = File(..., description="单步骤数据驱动文件(仅支持.xlsx后缀, 单步骤模式仅读取第1个sheet页)"),
):
    if not file.filename.endswith(".xlsx"):
        return FileExtensionResponse(message="仅支持.xlsx后缀的数据驱动文件")

    try:
        step_instance = await AUTOTEST_API_STEP_CRUD.get_by_conditions(
            conditions={"id": step_id, "case_id": case_id, "step_code": step_code},
            on_error=True,
        )
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询步骤失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=str(e))

    if step_instance.step_type != AutoTestStepType.HTTP.value:
        return ParameterResponse(message="仅支持对HTTP请求步骤上传数据驱动文件")

    destination = os.path.join(PROJECT_CONFIG.OUTPUT_UPLOAD_DIR, "autotest", str(case_id))
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

    file_path = path_or_error
    file_name = (getattr(file, "filename", None) or "").strip()[:255]

    file_hash = ""
    try:
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        file_hash = (file_hash or "")[:255]
    except Exception as e:
        LOGGER.warning(f"计算文件哈希失败: {e}")

    try:
        step_data, dataset_names, dataframe = await parse_xlsx_first_sheet_async(file_path)
    except FileNotFoundError as e:
        return FailureResponse(message=str(e))
    except ValueError as e:
        return BadReqResponse(message=f"解析失败: {str(e)}")

    if not step_data:
        return BadReqResponse(message="解析结果为空（第 1 个 sheet 无有效数据）")

    try:
        case_instance = await AUTOTEST_API_CASE_CRUD.get_by_id(case_id=case_id, on_error=True)
        user_id = CTX_USER_ID.get(0)
        created_user = str(user_id) if user_id else None
        instance = await AUTOTEST_DATA_SOURCE_CRUD.create_data_sources_from_parsed(
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
            created_user=created_user,
        )
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"数据源保存失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=str(e))

    await _sync_step_data_source_meta(
        case_id=case_id,
        step_code=step_code,
        file_name=file_name,
        file_desc=file_desc,
    )

    data = await _serialize_data_source(instance)
    return SuccessResponse(message="单步骤数据集上传成功，已创建数据源并同步缓存", data=data, total=1)


@autotest_data_source.post("/batch_step_dataset_upload", summary="参数化驱动-多步骤数据集上传")
async def batch_step_dataset_upload(
        case_id: int = Form(..., description="用例ID"),
        file_desc: Optional[str] = Form(None, description="数据驱动文件场景描述"),
        file: UploadFile = File(..., description="xlsx 文件（所有 sheet 均为数据集，按 sheet 顺序对应根步骤）"),
):
    if not case_id:
        return ParameterResponse(message="case_id 不能为空")

    if not file.filename.endswith(".xlsx"):
        return FileExtensionResponse(message="仅支持.xlsx后缀的数据驱动文件")

    root_steps = await _get_case_root_steps_async(case_id)
    if not root_steps:
        return BadReqResponse(message="该用例下没有可用的根步骤，请先维护步骤树")
    case_code = ""
    for s in root_steps:
        c = (s or {}).get("case") if isinstance(s, dict) else None
        if isinstance(c, dict) and c.get("case_code"):
            case_code = c.get("case_code")
            break
    if not case_code:
        try:
            case_instance = await AUTOTEST_API_CASE_CRUD.get_by_id(case_id=case_id, on_error=True)
            case_code = case_instance.case_code
        except (NotFoundException, ParameterException) as e:
            return ParameterResponse(message=str(e.message))
        except Exception as e:
            LOGGER.error(f"查询用例失败: {e}\n{traceback.format_exc()}")
            return FailureResponse(message=str(e))

    destination = f"{case_id}/batch"
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

    file_path = path_or_error
    file_name = (getattr(file, "filename", None) or "").strip()[:255]

    file_hash = ""
    try:
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        file_hash = (file_hash or "")[:255]
    except Exception as e:
        LOGGER.warning(f"计算文件哈希失败: {e}")

    try:
        full_parsed, _ = await parse_xlsx_to_parsed_data_async(file_path)
    except FileNotFoundError as e:
        return FailureResponse(message=str(e))
    except ValueError as e:
        return BadReqResponse(message=f"解析失败: {str(e)}")

    if not full_parsed:
        return BadReqResponse(message="解析结果为空")

    sheet_names = list(full_parsed.keys())
    user_id = CTX_USER_ID.get(0)
    created_user = str(user_id) if user_id else None
    created: List[Dict[str, Any]] = []
    for i, sheet_name in enumerate(sheet_names):
        step_data = full_parsed[sheet_name]
        if not isinstance(step_data, dict):
            continue
        dataset_names = sorted(step_data.keys()) if step_data else []
        dataframe = []
        if i < len(root_steps):
            step_id = root_steps[i].get("step_id")
            step_code = (root_steps[i].get("step_code") or "").strip()
        else:
            step_id = None
            step_code = str(sheet_name).strip()[:64] if sheet_name else f"sheet_{i}"

            try:
                # 取该 sheet 的原始二维矩阵（header=None，与解析一致）
                import pandas as pd
                df = pd.read_excel(file_path, sheet_name=i, header=None, engine="openpyxl")
                if not df.empty:
                    dataframe = df.where(pd.notna(df), None).values.tolist()
            except Exception as e:
                LOGGER.warning(f"读取 sheet 原始二维矩阵失败(sheet_index={i}, step_code={step_code}): {e}")

        try:
            if not step_id:
                LOGGER.warning(f"多步骤数据集上传跳过：未获取到 step_id，step_code={step_code}")
                continue
            instance = await AUTOTEST_DATA_SOURCE_CRUD.create_data_sources_from_parsed(
                case_id=case_id,
                case_code=case_code or "",
                step_id=int(step_id),
                step_code=step_code,
                file_name=file_name or None,
                file_path=file_path,
                file_hash=file_hash or None,
                file_desc=(file_desc or "")[:2048].strip() or None,
                parsed_data=step_data,
                dataset_names=dataset_names,
                dataframe=dataframe,
                created_user=created_user,
            )
            created.append(await _serialize_data_source(instance))
            await _sync_step_data_source_meta(
                case_id=case_id,
                step_code=step_code,
                file_name=file_name,
                file_desc=file_desc,
            )
        except (NotFoundException, ParameterException) as e:
            LOGGER.error(f"数据源保存失败 step_code={step_code}: {e.message}")
        except (DataAlreadyExistsException, DataBaseStorageException) as e:
            LOGGER.error(f"数据源保存失败 step_code={step_code}: {e.message}")
        except Exception as e:
            LOGGER.error(f"数据源保存失败 step_code={step_code}: {e}\n{traceback.format_exc()}")

    if not created:
        return BadReqResponse(message="未成功创建任何数据源记录")
    return SuccessResponse(
        message=f"多步骤数据集上传成功，共 {len(created)} 条数据源",
        data=created,
        total=len(created),
    )
