# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : basic_view.py
@DateTime: 2025/4/7 09:10
"""
import os.path
import traceback
from pathlib import Path
from typing import Union
from urllib.parse import quote

from fastapi import APIRouter, UploadFile, File, Form
from starlette.responses import StreamingResponse

from backend.common import FileUtils
from backend.configure import LOGGER, PROJECT_CONFIG
from backend.core.responses import (
    SuccessResponse,
    FailureResponse,
    NotFoundResponse
)
from backend.enums import FileSizeEum
from backend.services.file_transfer import FileTransfer

file_transfer = APIRouter()


@file_transfer.post("/upload", summary="上传文件", description="上传文件到指定目的地")
async def upload_file(
        file: UploadFile = File(..., description="文件对象"),
        path: Union[str, Path] = Form(..., description="文件上传目的地"),
        add_timestamp: bool = Form(default=True, description="是否为上传的文件添加时间戳"),
        check_filename: bool = Form(default=True, description="是否检查文件名称是否符合规范"),
        check_filetype: bool = Form(default=True, description="是否检查文件后缀是否符合规范"),
        check_filesize: bool = Form(default=True, description="是否检查文件体积是否符合规范"),
        upload_file_size: FileSizeEum = Form(default=FileSizeEum.TINY.value, description="文件的体积限制"),
):
    """
    上传文件。

    :param file: 文件对象
    :param path: 文件上传目的地
    :param add_timestamp: 是否为上传的文件添加时间戳
    :param check_filename: 是否检查文件名称是否符合规范
    :param check_filetype: 是否检查文件后缀是否符合规范
    :param check_filesize: 是否检查文件体积是否符合规范
    :param upload_file_size: 文件的体积限制
    :return: 统一HTTP响应
    """
    try:
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
            # detail 由 FileTransfer 返回，可能携带原始异常，只能进日志
            error_message: str = "上传文件失败，请检查文件名称、格式与大小是否符合要求后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [filename={file.filename}, destination={path}, 失败原因={detail}]"
            )
            return FailureResponse(message=error_message)
        return SuccessResponse(message="上传成功", data=detail)
    except Exception:
        error_message: str = "上传文件失败，暂时无法完成上传，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [filename={file.filename}, destination={path}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@file_transfer.post("/download", summary="下载文件", description="根据路径下载文件")
async def download_file(path: Union[str, Path] = Form(..., description="文件下载路径")):
    """
    下载文件。

    :param path: 文件下载路径
    :return: 文件流响应
    """
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


@file_transfer.post("/read", summary="查询文件内容", description="根据路径读取文件内容")
async def read_file(path: Union[str, Path] = Form(..., description="文件读取路径")):
    """
    读取文件。

    :param path: 文件读取路径
    :return: 统一HTTP响应
    """
    filepath: str = os.path.join(PROJECT_CONFIG.OUTPUT_DIR, path)
    try:
        with open(file=filepath, mode="r", encoding="utf-8") as fp:
            content: str = fp.read()
        return SuccessResponse(data=content, message="文件读取成功")
    except FileNotFoundError:
        # 绝对路径只写日志，避免把服务器目录结构返回给用户
        error_message: str = "读取文件失败，文件不存在或已被删除，请确认文件路径后重试"
        LOGGER.warning(f"{error_message}, 关键字段: [filepath={filepath}]")
        return NotFoundResponse(message=error_message)
    except Exception:
        error_message: str = "读取文件失败，暂时无法读取文件内容，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [filepath={filepath}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@file_transfer.post("/move", summary="更新文件位置", description="根据路径移动文件位置")
async def move_file(
        src_path: Union[str, Path] = Form(..., description="文件原始路径"),
        dst_path: Union[str, Path] = Form(..., description="文件目标路径"),
):
    """
    移动文件。

    :param src_path: 文件原始路径
    :param dst_path: 文件目标路径
    :return: 统一HTTP响应
    """
    src_file_path: str = os.path.join(PROJECT_CONFIG.OUTPUT_DIR, src_path)
    dst_file_path: str = os.path.join(PROJECT_CONFIG.OUTPUT_DIR, dst_path)
    try:
        state: bool = FileUtils.move_directory(src_file_path, dst_file_path)
        return SuccessResponse(message="文件移动成功", data={"src_path": src_file_path, "dst_path": dst_file_path, "state": state})
    except Exception:
        error_message: str = "移动文件失败，请确认源文件是否存在、目标路径是否可用后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [src_path={src_file_path}, dst_path={dst_file_path}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)
