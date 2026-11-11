# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : file_transfer.py
@DateTime: 2025/4/7 09:13
"""
import base64
import mimetypes
import os
import re
import traceback
from datetime import datetime
from pathlib import Path
from typing import Tuple, Union, Literal, Iterable

import aiofiles
from fastapi import UploadFile

from backend.configure import LOGGER, PROJECT_CONFIG, GLOBAL_CONFIG
from backend.core.exceptions import UploadFileException, FileExtensionException, FileTooManyException, NoPermissionException


class FileTransfer:
    """
    文件传输工具集。

    提供 base64 解码、分块落盘与分块读取三项能力，全部以静态方法提供，不持有实例状态。
    """

    @staticmethod
    async def process_base64_file(
            base64_data: str,
            original_filename: str,
    ) -> Tuple[bytes, str, str]:
        """
        解析 base64 编码的文件数据。

        同时兼容 data URI 与纯 base64 两种输入，data URI 携带的媒体类型优先于文件名推断结果；
        解码失败统一转为上传文件异常，由调用方决定后续提示。

        :param base64_data: base64 编码的文件数据，可携带 data URI 前缀
        :param original_filename: 原始文件名，用于推断媒体类型
        :return: 解码后的文件内容、文件名与媒体类型
        """
        try:
            # 解析 data URI
            if ',' in base64_data:
                # 处理 data URI 格式 (e.g., "data:image/png;base64,...")
                content_type = base64_data.split(';')[0].split(':')[1]
                base64_content = base64_data.split(',')[1]
            else:
                # 处理纯 base64 内容
                content_type = mimetypes.guess_type(original_filename)[0] or 'application/octet-stream'
                base64_content = base64_data

            # 解码 base64 数据
            file_content = base64.b64decode(base64_content)

            return file_content, original_filename, content_type
        except Exception as e:
            raise UploadFileException(message="文件内容解析失败，请确认文件完整后重新上传") from e

    @staticmethod
    async def save_upload_file_chunks(
            *,
            upload_file: UploadFile,
            destination: Union[str, Path],
            add_timestamp: bool = True,
            check_filename: bool = True,
            check_filetype: bool = True,
            check_filesize: bool = True,
            add_left_identifier: str = None,
            add_right_identifier: str = None,
            chunk_size: int = 1024 * 1024 * 10,
            upload_file_size: Literal["tiny", "micro", "small", "medium", "large", "huge"] = 'tiny',
    ) -> Tuple[bool, str]:
        """
        将上传文件分块写入上传目录。

        依次执行文件名清洗、类型校验、体积校验与目录创建，任一项不通过即抛出对应异常；
        写入阶段（含写入路径二次校验）失败不再抛出，统一返回失败标记与可读提示，由调用方决定响应。

        :param upload_file: 上传文件对象，或包含 file 与 filename 的数据字典
        :param destination: 上传目录下的子目录
        :param add_timestamp: 是否在文件名前追加时间戳
        :param check_filename: 是否清洗文件名中的特殊字符
        :param check_filetype: 是否校验文件后缀
        :param check_filesize: 是否校验文件体积
        :param add_left_identifier: 追加在文件名左侧的标识
        :param add_right_identifier: 追加在文件名右侧的标识
        :param chunk_size: 单次异步读取的分块大小
        :param upload_file_size: 体积限制档位，对应体积限制配置的键
        :return: 写入结果与落盘后的绝对路径，失败时第二项为可读提示
        """
        # 处理不同类型的文件上传
        if isinstance(upload_file, dict):
            # 处理base64编码的文件数据
            if 'file' not in upload_file or 'filename' not in upload_file:
                raise UploadFileException(message="文件信息不完整，请重新选择文件后上传")

            file_content, filename, content_type = await FileTransfer.process_base64_file(
                upload_file['file'],
                upload_file['filename']
            )
            file_size = len(file_content)
        else:
            # 处理常规文件上传
            filename = upload_file.filename
            content_type = upload_file.content_type
            file_size = upload_file.size

        # 检查文件名称（移除特殊字符但保留扩展名）
        if check_filename:
            name, ext = os.path.splitext(filename)
            # 只对文件名部分进行清理，保留扩展名
            cleaned_name = re.sub(r'["·`‘—_!！@#$￥%^&*()（）<>《》【】[]？?|\\/:：,，.。、；;', '', name)
            if not cleaned_name:
                raise UploadFileException(message="文件名称不被允许")
            filename = cleaned_name + ext

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
            datetime_stamp: str = datetime.now().strftime(GLOBAL_CONFIG.DATETIME_FORMAT1)
            filename = f"{datetime_stamp}_{filename}"

        # 如果需要，为文件名添加标识符
        if add_left_identifier:
            filename = f"{add_left_identifier}_{filename}"
        if add_right_identifier:
            file_name, file_suffix = os.path.splitext(filename)
            filename = f"{file_name}_{add_right_identifier}.{file_suffix}"

        try:
            # 以异步方式打开目标文件进行二进制写入
            destination_path: str = os.path.normpath(os.path.join(destination_dir, filename))
            if not destination_path.startswith(PROJECT_CONFIG.OUTPUT_UPLOAD_DIR):
                raise UploadFileException(message="上传路径不被允许")
            async with aiofiles.open(file=destination_path, mode="wb") as in_file:
                try:
                    # 循环读取上传文件的内容并写入目标文件
                    while chunk := await upload_file.read(chunk_size):
                        await in_file.write(chunk)
                finally:
                    # 确保上传文件资源被正确释放
                    await upload_file.close()
            return True, destination_path
        except Exception:
            # 返回值会进入上传接口日志，原始异常只写服务端日志
            error_message: str = "上传文件失败，请检查文件名称、格式与大小是否符合要求后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [destination={destination}, filename={filename}, file_size={file_size}]\n"
                f"{traceback.format_exc()}"
            )
            return False, error_message

    @staticmethod
    async def iter_download_file_chunks(download_file: str, chunk_size: int = 1024 * 1024, add_bom: bool = False) -> Iterable[bytes]:
        """
        以分块方式读取文件，用于流式下载。

        读取前校验路径必须落在输出目录内，越界直接抛出无权限异常；响应头一经发出便无法
        再转为统一响应，因此迭代阶段的非权限异常只记录日志后原样抛出。

        :param download_file: 待下载文件的绝对路径
        :param chunk_size: 单次读取的分块大小
        :param add_bom: 是否为 UTF-8 文本补充 BOM，二进制文件不可开启
        :return: 文件内容分块的可迭代对象
        """
        download_file: str = os.path.normpath(download_file)
        if not download_file.startswith(PROJECT_CONFIG.OUTPUT_DIR):
            raise NoPermissionException(message="请求路径不被允许")

        # 预读文件头判断 BOM，与正式读取同处 try 内，文件缺失等异常才能落到日志
        UTF8_BOM = b"\xef\xbb\xbf"
        first_chunk = True
        # 使用 aiofiles 异步打开文件，以二进制读取模式
        try:
            async with aiofiles.open(file=download_file, mode="rb") as pre_read:
                start = await pre_read.read(3)
            not_exist_bom: bool = start != UTF8_BOM
            async with aiofiles.open(file=download_file, mode="rb") as out_file:
                if not download_file.startswith(PROJECT_CONFIG.OUTPUT_DIR):
                    raise NoPermissionException(message="请求路径不被允许")
                # 循环读取文件块，直到文件结束
                while chunk := await out_file.read(chunk_size):
                    if add_bom and first_chunk and not_exist_bom:
                        chunk = UTF8_BOM + chunk
                        first_chunk = False
                    # 生成当前块的数据
                    yield chunk
        except NoPermissionException:
            raise
        except Exception:
            # 迭代阶段响应头已发出，异常无法转为统一响应，记录后中断下载
            error_message: str = "下载文件失败，暂时无法读取文件内容，请稍后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [filepath={download_file}]\n"
                f"{traceback.format_exc()}"
            )
            raise
