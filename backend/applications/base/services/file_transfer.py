# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : file_transfer.py
@DateTime: 2025/4/7 09:13
"""
import os
import re
import traceback
from datetime import datetime
from pathlib import Path
from typing import Tuple, Union, Literal, Iterable

import aiofiles
from fastapi import UploadFile

from backend import LOGGER, PROJECT_CONFIG, GLOBAL_CONFIG
from backend.core.exceptions.base_exceptions import UploadFileException, FileExtensionException, FileTooManyException


class FileTransfer:

    @staticmethod
    async def save_upload_file_chunks(
            *,
            upload_file: UploadFile,
            destination: Union[str, Path],
            add_timestamp: bool = True,
            check_filename: bool = True,
            check_filetype: bool = True,
            check_filesize: bool = True,
            chunk_size: int = 1024 * 1024 * 10,
            upload_file_size: Literal["tiny", "micro", "small", "medium", "large", "huge"] = 'tiny',
    ) -> Tuple[bool, str]:
        """
        将上传的文件以分块的方式保存到指定的目标路径
        :param upload_file: 上传的文件对象
        :param destination: 文件保存地址
        :param add_timestamp: 是否为上传的文件添加时间戳
        :param check_filename: 是否检查文件名称是否符合规范
        :param check_filetype: 是否检查文件后缀是否符合规范
        :param check_filesize: 是否检查文件体积是否符合规范
        :param chunk_size: 异步分块的大小
        :param upload_file_size: 文件的体积限制
        :return:
        """
        # 检查文件名称
        filename: str = upload_file.filename
        if check_filename and (not filename or re.search(r'[\\/*?:\'"<>|!@#$%^&]', filename)):
            raise UploadFileException(message="文件名称不被允许")

        # 检查文件类型
        if check_filetype and (upload_file.content_type not in PROJECT_CONFIG.UPLOAD_FILE_SUFFIX):
            raise FileExtensionException(message="文件类型不被允许")

        # 检查文件大小
        if check_filesize and (upload_file.size > PROJECT_CONFIG.UPLOAD_FILE_PEAK_SIZE[upload_file_size]):
            raise FileTooManyException(message="文件体积不被允许")

        # 检查文件存放目录
        destination_dir: str = os.path.join(PROJECT_CONFIG.OUTPUT_UPLOAD_DIR, destination)
        if not os.path.exists(destination_dir):
            try:
                os.makedirs(destination_dir, exist_ok=True)
            except PermissionError:
                raise UploadFileException(message="创建文件存放目录不被允许")

        # 检查是否需要添加文件上传时间戳
        if add_timestamp:
            datetime_stamp: str = datetime.now().strftime(GLOBAL_CONFIG.DATETIME_SCHEMA)
            filename = f"{datetime_stamp}_{filename}"

        try:
            # 以异步方式打开目标文件进行二进制写入
            destination_path: str = os.path.join(destination_dir, filename)
            async with aiofiles.open(file=destination_path, mode="wb") as in_file:
                try:
                    # 循环读取上传文件的内容并写入目标文件
                    while chunk := await upload_file.read(chunk_size):
                        await in_file.write(chunk)
                finally:
                    # 确保上传文件资源被正确释放
                    await upload_file.close()
            return True, destination_path
        except Exception as e:
            error_msg = f"上传或更新数据文件发生错误: {str(e)}"
            LOGGER.error(traceback.format_exc())
            return False, error_msg

    @staticmethod
    async def iter_download_file_chunks(download_file: str, chunk_size: int = 1024 * 1024) -> Iterable[bytes]:
        """
        用于以分块的方式读取指定文件的内容，并通过生成器逐块返回，适用于流式下载文件
        :param download_file: 下载的文件对象
        :param chunk_size: 块的大小
        :return:
        """
        # 以异步方式打开文件进行二进制读取
        async with aiofiles.open(download_file, "rb") as out_file:
            # 循环读取文件内容并逐块返回
            while chunk := await out_file.read(chunk_size):
                yield chunk


