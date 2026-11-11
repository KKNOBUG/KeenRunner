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
    分块上传文件。

    按需校验文件名、后缀与体积后再落盘；FileTransfer 返回的失败原因可能包含
    原始异常，只写入日志。

    :param file: 上传的文件对象
    :param path: 文件保存的相对路径（以上传目录为根）
    :param add_timestamp: 是否为文件名添加时间戳
    :param check_filename: 是否校验文件名是否合规
    :param check_filetype: 是否校验文件后缀是否合规
    :param check_filesize: 是否校验文件体积是否合规
    :param upload_file_size: 文件体积限制档位，传入枚举 value
    :return: 统一响应，成功时 data 为文件保存后的服务器绝对路径，失败时仅返回可读提示
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
    按相对路径下载文件。

    以输出目录为根拼接路径，返回带附件头的流式响应；响应头一经发出便无法再转为
    统一响应，因此路径越界与文件缺失在构造响应前先行校验。

    :param path: 文件下载路径（相对输出目录）
    :return: 文件流响应，文件名按 UTF-8 编码写入 Content-Disposition
    """
    # 以输出目录为根拼接相对路径，并规范化为绝对路径
    filepath: str = os.path.normpath(os.path.join(PROJECT_CONFIG.OUTPUT_DIR, path))
    try:
        # 流式响应头发出后异常无法转为统一响应，可预见的失败必须前置拦截
        if not filepath.startswith(PROJECT_CONFIG.OUTPUT_DIR):
            error_message: str = "下载文件失败，请求路径不被允许"
            LOGGER.warning(f"{error_message}, 关键字段: [filepath={filepath}]")
            return FailureResponse(message=error_message)
        if not os.path.isfile(filepath):
            error_message: str = "下载文件失败，文件不存在或已被删除，请确认文件路径后重试"
            LOGGER.warning(f"{error_message}, 关键字段: [filepath={filepath}]")
            return NotFoundResponse(message=error_message)
        filename: str = quote(os.path.basename(path).encode("utf-8"))
        return StreamingResponse(
            content=FileTransfer.iter_download_file_chunks(download_file=filepath),
            media_type="application/octet-stream",
            headers={
                "filename": filename,
                "Content-Disposition": f"attachment; filename*=utf-8''{filename}"
            }
        )
    except Exception:
        error_message: str = "下载文件失败，暂时无法完成下载，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [filepath={filepath}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@file_transfer.post("/read", summary="查询文件内容", description="根据路径读取文件内容")
async def read_file(path: Union[str, Path] = Form(..., description="文件读取路径")):
    """
    读取文件文本内容。

    以输出目录为根拼接路径；文件不存在返回 404，绝对路径只写入日志，不回显给用户。

    :param path: 文件读取路径（相对输出目录）
    :return: 统一响应，成功时 data 为 UTF-8 文本内容
    """
    # 以输出目录为根拼接相对路径
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
    移动或重命名文件。

    :param src_path: 文件原始路径（相对输出目录）
    :param dst_path: 文件目标路径（相对输出目录）
    :return: 统一响应，成功时 data 含 src_path、dst_path 与 state，路径字段为服务器绝对路径
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
