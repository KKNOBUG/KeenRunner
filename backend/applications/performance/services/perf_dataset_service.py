# -*- coding: utf-8 -*-
"""
压测参数化数据集业务服务：上传文件解析（只回显，不落库）。

解析复用 autotest_data_source_parser 的四分区解析器(与功能数据源同一解析链路),
解析结果供前端矩阵回显与人工校对, 最终由 /perf/dataset/create 提交 dataframe+axis 落库:
写入口保持在 PerfDatasetCrud 唯一, 服务端不开「从文件直接落库」的旁路, 否则用户在页面上
对矩阵的增删改会与文件内容形成两套真相。上传文件保留在 OUTPUT_UPLOAD_DIR, 仅作来源溯源
(file_name/file_path/file_hash), 施压取数一律读库内 dataset, 不回读文件。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_dataset_service.py
@DateTime: 2026/9/16 10:20
"""
import hashlib
import os
import traceback
from typing import Optional

import aiofiles
import aiofiles.os as aos
from fastapi import UploadFile

from backend.applications.autotest.services.autotest_data_source_parser import parse_xlsx_first_sheet_async
from backend.applications.performance.schemas.perf_dataset_schema import (
    PERF_DATASET_SCENES_MAX,
    PerfDatasetParsedPreview,
)
from backend.configure import LOGGER, PROJECT_CONFIG
from backend.core.exceptions import ParameterException, UploadFileException
from backend.services.file_transfer import FileTransfer

# 支持的数据文件后缀: 与功能数据源同一把尺子(仅 xlsx)
DATASET_FILE_SUFFIX = ".xlsx"
# 上传文件存放目录(相对 OUTPUT_UPLOAD_DIR, 按应用分区便于运维排查)
DATASET_UPLOAD_DIRS = ("performance", "dataset")
# 上传体积档位: 参数化文件与功能数据源同档(tiny=16MB)
DATASET_UPLOAD_SIZE_TIER = "tiny"


async def _remove_upload_file(file_path: str) -> None:
    """
    解析失败时清理已落盘的上传文件, 避免残留孤儿文件。

    :param file_path: 上传文件路径
    :return: None
    """
    try:
        if file_path and await aos.path.exists(file_path):
            await aos.remove(file_path)
    except Exception as e:
        LOGGER.warning(f"清理上传文件[{file_path}]失败, 异常描述: {e}")


async def _calc_file_hash(file_path: str) -> Optional[str]:
    """
    计算文件 sha256(与功能数据源同一口径, 供「同一文件重复导入」识别)。

    :param file_path: 上传文件路径
    :return: 十六进制哈希, 读取失败返回None
    """
    try:
        async with aiofiles.open(file=file_path, mode="rb") as in_file:
            content: bytes = await in_file.read()
        return hashlib.sha256(content).hexdigest()
    except Exception as e:
        LOGGER.warning(f"计算文件哈希失败: {e}")
        return None


class PerfDatasetService:
    """压测数据集业务服务：文件上传解析。"""

    @staticmethod
    async def _ensure_project_exists(project_id: int) -> None:
        """
        校验应用主数据存在(先校验再落盘, 避免非法应用刷出无主目录)。

        :param project_id: 应用ID
        :return: None
        """
        from backend.applications.autotest.services.autotest_project_crud import AutoTestProjectCrud

        await AutoTestProjectCrud().get_by_id(project_id=project_id, on_error=True, state__not=1)

    @classmethod
    async def parse_upload_file(cls, *, upload_file: UploadFile, ds_project: int) -> dict:
        """
        上传 xlsx 并解析为数据集预览(场景数据 + 原始矩阵 + 文件溯源信息, 不落库)。

        矩阵全量返回: 前端编辑器本就要承载整包矩阵供编辑, 若只回部分行列,
        用户保存时反而拿不全数据。解析失败(空表/无分区标记/超场景上限)一律清理已落盘文件后抛错。

        :param upload_file: 上传文件对象(仅支持 .xlsx)
        :param ds_project: 数据集所属应用(决定存放子目录, 与将落库的 ds_project 一致)
        :return: 解析预览字典, 结构:
            {"dataset": {"场景1": {...四分区}}, "dataset_names": ["场景1"],
             "dataframe": [[...]], "axis": 0,
             "file_name": "xx.xlsx", "file_path": "/abs/path/xx.xlsx", "file_hash": "sha256..."}
        """
        await cls._ensure_project_exists(project_id=ds_project)

        file_name: str = os.path.basename(upload_file.filename or "")
        if not file_name.lower().endswith(DATASET_FILE_SUFFIX):
            error_message: str = f"上传数据集文件失败, 仅支持{DATASET_FILE_SUFFIX}后缀, 当前: {file_name or '未提供文件名'}"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        destination: str = os.path.join(
            PROJECT_CONFIG.OUTPUT_UPLOAD_DIR, *DATASET_UPLOAD_DIRS, str(ds_project),
        )
        ok, path_or_error = await FileTransfer.save_upload_file_chunks(
            upload_file=upload_file,
            destination=destination,
            add_timestamp=True,
            check_filename=True,
            check_filetype=True,
            check_filesize=True,
            upload_file_size=DATASET_UPLOAD_SIZE_TIER,
        )
        if not ok:
            error_message: str = f"上传数据集文件失败, 错误描述: {path_or_error}"
            LOGGER.error(error_message)
            raise UploadFileException(message=error_message)

        file_path: str = path_or_error
        try:
            # 四分区解析器内部把阻塞IO移入线程池, 方向自动识别, 与功能数据源同一解析链路
            dataset, dataset_names, dataframe, axis = await parse_xlsx_first_sheet_async(file_path)
        except Exception as e:
            await _remove_upload_file(file_path)
            if isinstance(e, ParameterException):
                raise
            error_message: str = f"解析数据集文件失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

        if not dataset_names:
            await _remove_upload_file(file_path)
            error_message: str = "解析数据集文件失败, 未解析到任何有效场景, 请检查分区标记(HEAD/BODY)与场景名后重新上传"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if len(dataset_names) > PERF_DATASET_SCENES_MAX:
            await _remove_upload_file(file_path)
            error_message: str = (
                f"解析数据集文件失败, 场景数超出上限[{PERF_DATASET_SCENES_MAX}], 当前: {len(dataset_names)}, "
                f"请按施压并发规模裁剪后再上传(unique 策略下超出部分永不会被用到)"
            )
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        file_hash: Optional[str] = await _calc_file_hash(file_path)
        LOGGER.info(
            f"数据集文件解析完成: file_name={file_name}, scenes={len(dataset_names)}, axis={axis}"
        )
        # 经回显契约构造一次: 字段与上限在此定档, 前端拿到的一定是完整结构, 不依赖服务内部变量名
        return PerfDatasetParsedPreview(
            dataset=dataset,
            dataset_names=dataset_names,
            dataframe=dataframe,
            axis=axis,
            # 落盘文件名可能与上传名不同(清洗非法字符+时间戳前缀), 以磁盘实际名为准保证溯源对得上
            file_name=os.path.basename(file_path),
            file_path=file_path,
            file_hash=file_hash,
        ).model_dump(mode="json")
