# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_source_view.py
@DateTime: 2026/3/6
"""
import hashlib

from fastapi import APIRouter, UploadFile, File, Form
from typing import Optional

from backend import LOGGER
from backend.applications.aotutest.services.autotest_data_source_crud import AUTOTEST_DATA_SOURCE_CRUD
from backend.applications.aotutest.services.autotest_data_source_parser import (
    parse_xlsx_first_sheet_async,
    parse_xlsx_to_parsed_data_async,
)
from backend.applications.aotutest.services.autotest_step_crud import AUTOTEST_API_STEP_CRUD
from backend.applications.base.services.file_transfer import FileTransfer
from backend.core.responses.http_response import SuccessResponse, FailureResponse, BadReqResponse, ParameterResponse
from backend.services.ctx import CTX_USER_ID

autotest_data_source = APIRouter()


async def _get_case_root_steps_async(case_id: int):
    """异步：获取用例根步骤列表（按 step_no 排序）。"""
    tree_data = await AUTOTEST_API_STEP_CRUD.get_by_case_id(case_id=case_id)
    if not tree_data or not isinstance(tree_data, list):
        return []
    if len(tree_data) > 1 and isinstance(tree_data[-1], dict) and "total_steps" in tree_data[-1]:
        tree_data = tree_data[:-1]
    root_steps = [s for s in tree_data if isinstance(s, dict) and s.get("step_no") is not None]
    root_steps.sort(key=lambda x: (x.get("step_no") or 0))
    return root_steps


@autotest_data_source.post("/single_step_dataset_upload", summary="参数化驱动-单步骤数据集上传")
async def single_step_dataset_upload(
    case_id: int = Form(..., description="用例ID"),
    file_desc: Optional[str] = Form(None, description="数据驱动文件场景描述"),
    file: UploadFile = File(..., description="xlsx 文件（仅读取第 1 个 sheet）"),
):
    """
    单步骤数据集上传：参数 case_id、file、file_desc。
    xlsx 仅解析第 1 个 sheet 页；step_code 由接口内部取该用例第一个根步骤。
    """
    if not case_id:
        return ParameterResponse(message="case_id 不能为空")

    root_steps = await _get_case_root_steps_async(case_id)
    if not root_steps:
        return BadReqResponse(message="该用例下没有可用的根步骤，请先维护步骤树")

    first_step = root_steps[0]
    step_code = (first_step.get("step_code") or "").strip()
    if not step_code:
        return BadReqResponse(message="该用例第一个根步骤缺少 step_code")

    destination = f"{case_id}/single"
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

    try:
        file_hash = ""
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        file_hash = (file_hash or "")[:255]
    except Exception as e:
        LOGGER.warning(f"计算文件哈希失败: {e}")

    try:
        step_data, dataset_names = await parse_xlsx_first_sheet_async(file_path)
    except FileNotFoundError as e:
        return FailureResponse(message=str(e))
    except ValueError as e:
        return BadReqResponse(message=f"解析失败: {str(e)}")

    if not step_data:
        return BadReqResponse(message="解析结果为空（第 1 个 sheet 无有效数据）")

    try:
        user_id = CTX_USER_ID.get(0)
        created_user = str(user_id) if user_id else None
        instance = await AUTOTEST_DATA_SOURCE_CRUD.create_data_sources_from_parsed(
            case_id=case_id,
            step_code=step_code,
            file_name=file_name or None,
            file_path=file_path,
            file_hash=file_hash or None,
            file_desc=(file_desc or "")[:2048].strip() or None,
            parsed_data=step_data,
            dataset_names=dataset_names,
            created_user=created_user,
        )
    except Exception as e:
        LOGGER.error(f"数据源保存失败: {e}")
        return FailureResponse(message=str(e))

    data = await instance.to_dict(
        exclude_fields={
            "state",
            "created_user", "updated_user",
            "created_time", "updated_time",
            "reserve_1", "reserve_2", "reserve_3"
        },
        replace_fields={"id": "data_source_id"}
    )
    return SuccessResponse(message="单步骤数据集上传成功，已创建数据源并同步缓存", data=data, total=1)


@autotest_data_source.post("/batch_step_dataset_upload", summary="参数化驱动-多步骤数据集上传")
async def batch_step_dataset_upload(
    case_id: int = Form(..., description="用例ID"),
    file_desc: Optional[str] = Form(None, description="数据驱动文件场景描述"),
    file: UploadFile = File(..., description="xlsx 文件（所有 sheet 均为数据集，按 sheet 顺序对应根步骤）"),
):
    """
    多步骤数据集上传：参数 case_id、file、file_desc。
    xlsx 中所有 sheet 页均为数据集；每个 sheet 按顺序对应用例的根步骤，step_code 由接口内部从步骤树获取。
    """
    if not case_id:
        return ParameterResponse(message="case_id 不能为空")

    root_steps = await _get_case_root_steps_async(case_id)
    if not root_steps:
        return BadReqResponse(message="该用例下没有可用的根步骤，请先维护步骤树")

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

    try:
        file_hash = ""
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
    created = []
    for i, sheet_name in enumerate(sheet_names):
        step_data = full_parsed[sheet_name]
        if not isinstance(step_data, dict):
            continue
        dataset_names = sorted(step_data.keys()) if step_data else []
        if i < len(root_steps):
            step_code = (root_steps[i].get("step_code") or "").strip()
        else:
            step_code = str(sheet_name).strip()[:64] if sheet_name else f"sheet_{i}"

        try:
            instance = await AUTOTEST_DATA_SOURCE_CRUD.create_data_sources_from_parsed(
                case_id=case_id,
                step_code=step_code,
                file_name=file_name or None,
                file_path=file_path,
                file_hash=file_hash or None,
                file_desc=(file_desc or "")[:2048].strip() or None,
                parsed_data=step_data,
                dataset_names=dataset_names,
                created_user=created_user,
            )
            data = await instance.to_dict(
                exclude_fields={
                    "state",
                    "created_user", "updated_user",
                    "created_time", "updated_time",
                    "reserve_1", "reserve_2", "reserve_3"
                },
                replace_fields={"id": "data_source_id"}
            )
            created.append(data)
        except Exception as e:
            LOGGER.error(f"数据源保存失败 step_code={step_code}: {e}")

    if not created:
        return BadReqResponse(message="未成功创建任何数据源记录")
    return SuccessResponse(
        message=f"多步骤数据集上传成功，共 {len(created)} 条数据源",
        data=created,
        total=len(created),
    )


@autotest_data_source.get("/list", summary="参数化驱动-按用例查询数据源列表（按 file_code 聚合，含 dataset_names，不含 dataset）")
async def list_data_sources(
    case_id: int,
    state: Optional[int] = 0,
):
    """返回该用例下所有数据源文件（按 file_code 聚合，每条文件含 steps 列表），用于前端选择数据源与数据集。"""
    if not case_id:
        return ParameterResponse(message="case_id 不能为空")
    try:
        items = await AUTOTEST_DATA_SOURCE_CRUD.list_by_case(case_id=case_id, state=state)
        by_file: dict = {}
        for x in items:
            fc = x.file_code or ""
            if fc not in by_file:
                by_file[fc] = {
                    "file_code": fc,
                    "case_id": x.case_id,
                    "file_name": x.file_name,
                    "file_path": x.file_path,
                    "file_desc": x.file_desc,
                    "dataset_names": x.dataset_names or [],
                    "steps": [],
                    "created_time": x.created_time.isoformat() if getattr(x.created_time, "isoformat", None) else str(x.created_time),
                    "updated_time": x.updated_time.isoformat() if getattr(x.updated_time, "isoformat", None) else str(x.updated_time),
                }
            by_file[fc]["steps"].append({"step_code": x.step_code})
        for v in by_file.values():
            v["steps"].sort(key=lambda s: s["step_code"])
        data = list(by_file.values())
        return SuccessResponse(data=data, total=len(data))
    except Exception as e:
        LOGGER.error(f"查询数据源列表失败: {e}")
        return FailureResponse(message=str(e))
