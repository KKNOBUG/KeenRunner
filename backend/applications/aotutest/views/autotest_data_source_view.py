# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_source_view.py
@DateTime: 2026/3/6
参数化驱动：数据源上传、列表查询。上传使用 file_transfer 与 project_config 的类型/大小限制；路径按 case_id/file_code/文件名称 存放在 output 目录下。
"""
import hashlib

from fastapi import APIRouter, UploadFile, File, Form
from typing import Optional

from backend import LOGGER
from backend.applications.aotutest.services.autotest_data_source_crud import AUTOTEST_DATA_SOURCE_CRUD
from backend.applications.aotutest.services.autotest_data_source_parser import parse_xlsx_to_parsed_data_async
from backend.applications.base.services.file_transfer import FileTransfer
from backend.applications.aotutest.models.autotest_model import unique_identify
from backend.core.responses.http_response import SuccessResponse, FailureResponse, BadReqResponse, ParameterResponse
from backend.services.ctx import CTX_USER_ID

autotest_data_source = APIRouter()


@autotest_data_source.post("/upload", summary="参数化驱动-上传数据驱动xlsx")
async def upload_data_source(
    case_id: int = Form(..., description="用例ID"),
    step_no: int = Form(..., description="步骤序号"),
    step_code: str = Form(..., description="步骤标识代码"),
    file_desc: Optional[str] = Form(None, description="数据驱动文件场景描述"),
    file: UploadFile = File(..., description="xlsx 文件"),
):
    """
    上传 xlsx：使用 file_transfer 落盘（路径 case_id/file_code/文件名称，位于 output/upload 下），
    解析为约定 JSON → 创建数据源记录 → 同步 Redis。文件类型与大小限制见 project_config。
    """
    if not case_id:
        return ParameterResponse(message="case_id 不能为空")

    # 按 case_id/file_code 构建相对路径，FileTransfer 会存到 OUTPUT_UPLOAD_DIR 下
    destination = f"{case_id}/{step_no}/{step_code}"

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
    file_name = getattr(file, "filename", None) or ""
    if isinstance(file_name, str):
        file_name = file_name.strip()[:255]

    try:
        file_hash = ""
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        file_hash = (file_hash or "")[:255]
    except Exception as e:
        LOGGER.warning(f"计算文件哈希失败: {e}")

    try:
        full_parsed, dataset_names = await parse_xlsx_to_parsed_data_async(file_path)
    except FileNotFoundError as e:
        return FailureResponse(message=str(e))
    except ValueError as e:
        return BadReqResponse(message=f"解析失败: {str(e)}")

    # 单步上传：取与 step_code 同名的 sheet 或第一个 sheet 的数据作为该步骤的 dataset
    step_data = full_parsed.get(step_code) if full_parsed else None
    if step_data is None and full_parsed:
        step_data = next(iter(full_parsed.values()), None)
    if not step_data:
        return BadReqResponse(message="解析结果为空或未匹配到步骤数据")

    try:
        user_id = CTX_USER_ID.get(0)
        created_user = str(user_id) if user_id else None
        instance = await AUTOTEST_DATA_SOURCE_CRUD.create_data_sources_from_parsed(
            case_id=case_id,
            step_no=step_no,
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

    if not instance:
        return BadReqResponse(message="解析结果为空，未创建任何记录")

    data = await instance.to_dict(
        exclude_fields={
            "state",
            "created_user", "updated_user",
            "created_time", "updated_time",
            "reserve_1", "reserve_2", "reserve_3"
        },
        replace_fields={"id": "case_id"}
    )
    return SuccessResponse(message="上传成功，已创建数据源并同步缓存", data=data, total=1)


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
            by_file[fc]["steps"].append({"step_no": x.step_no, "step_code": x.step_code})
        for v in by_file.values():
            v["steps"].sort(key=lambda s: s["step_no"])
        data = list(by_file.values())
        return SuccessResponse(data=data, total=len(data))
    except Exception as e:
        LOGGER.error(f"查询数据源列表失败: {e}")
        return FailureResponse(message=str(e))
