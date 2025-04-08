# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : basic_view.py
@DateTime: 2025/4/7 09:10
"""
import os.path
from pathlib import Path
from typing import Union
from urllib.parse import quote

from fastapi import APIRouter, UploadFile, File, Form
from starlette.responses import StreamingResponse

from backend import PROJECT_CONFIG
from backend.applications.base.services.file_transfer import FileTransfer
from backend.common.file_utils import FileUtils
from backend.core.response.http_response import (
    SuccessResponse,
    FailureResponse,
    NotFoundResponse
)
from backend.enums.file_size_enum import FileSizeEum

file_transfer = APIRouter()


@file_transfer.post("/upload", summary="上传文件")
async def upload_file(
        file: UploadFile = File(..., title="文件对象"),
        path: Union[str, Path] = Form(..., title="文件上传目的地"),
        add_timestamp: bool = Form(default=True, title="是否为上传的文件添加时间戳"),
        check_filename: bool = Form(default=True, title="是否检查文件名称是否符合规范"),
        check_filetype: bool = Form(default=True, title="是否检查文件后缀是否符合规范"),
        check_filesize: bool = Form(default=True, title="是否检查文件体积是否符合规范"),
        upload_file_size: FileSizeEum = Form(default=FileSizeEum.TINY.value, title="文件的体积限制"),
):
    state, detail = await FileTransfer.save_upload_file_chunks(
        upload_file=file,
        destination=path,
        add_timestamp=add_timestamp,
        check_filename=check_filename,
        check_filetype=check_filetype,
        check_filesize=check_filesize,
        upload_file_size=upload_file_size.value
    )

    if not state:
        return FailureResponse(message=f"上传失败，错误描述: {detail}")
    return SuccessResponse(message="上传成功", data=detail)


@file_transfer.post("/download", summary="下载文件")
async def download_file(path: Union[str, Path] = Form(..., title="文件下载路径")):
    filepath: str = os.path.join(PROJECT_CONFIG.OUTPUT_DIR, path)
    filename: str = quote(os.path.basename(path).encode("utf-8"))
    return StreamingResponse(
        content=FileTransfer.iter_download_file_chunks(download_file=filepath),
        media_type="application/octet-stream",
        headers={
            "filename": filename,
            "Content-Disposition": f"attachment; filename*=utf-8''{filename}"
        }
    )


@file_transfer.post("/read", summary="读取文件")
async def read_file(path: Union[str, Path] = Form(..., title="文件读取路径")):
    filepath: str = os.path.join(PROJECT_CONFIG.OUTPUT_DIR, path)
    try:
        with open(file=filepath, mode="r", encoding="utf-8") as fp:
            content: str = fp.read()
        return SuccessResponse(data=content, message="文件读取成功")
    except FileNotFoundError:
        return NotFoundResponse(message=f"文件:{filepath}未找到")
    except Exception as e:
        return FailureResponse(message=f"发生错误: {str(e)}", data={"error": str(e)})


@file_transfer.post("/move", summary="移动文件")
async def move_file(
        src_path: Union[str, Path] = Form(..., title="文件原始路径"),
        dst_path: Union[str, Path] = Form(..., title="文件目标路径"),
):
    src_file_path: str = os.path.join(PROJECT_CONFIG.OUTPUT_DIR, src_path)
    dst_file_path: str = os.path.join(PROJECT_CONFIG.OUTPUT_DIR, dst_path)
    try:
        state: bool = FileUtils.move_directory(src_file_path, dst_file_path)
        return SuccessResponse(message="文件移动成功", data={"src_path": src_file_path, "dst_path": dst_file_path})
    except Exception as e:
        return FailureResponse(message=f"发生错误: {str(e)}", data={"error": str(e)})
