# -*- coding: utf-8 -*-
"""
压测数据集视图：/perf/dataset/* 路由编排(参数接收 -> 服务调用 -> 统一响应)。

数据集是场景接口项的参数化数据源(结构与功能数据源同形, 「场景」即虚拟用户分配单元);
列表页显式取列规避大字段, 场景数据与矩阵经 /get 全量读取。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_dataset_view.py
@DateTime: 2026/9/16 10:30
"""
import io
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import pandas as pd
from fastapi import APIRouter, Body, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from tortoise.transactions import in_transaction

from backend.applications.autotest.services.autotest_case_excel_service import style_data_source_sheet
from backend.applications.autotest.services.autotest_data_source_service import sync_data_source_fields
from backend.applications.performance.dependencies import PerfServices, get_perf_api_services
from backend.applications.performance.services.perf_dataset_service import PerfDatasetService
from backend.applications.performance.services.perf_asset_utils import safe_sheet_name
from backend.applications.performance.schemas.perf_dataset_schema import (
    PerfDatasetCreate,
    PerfDatasetUpdate,
    PerfDatasetUpdateFields,
)
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    DataAlreadyExistsException,
    ParameterException,
    DataBaseStorageException,
)
from backend.core.responses import (
    SuccessResponse,
    FailureResponse,
    BadReqResponse,
    FileExtensionResponse,
    ParameterResponse,
    NotFoundResponse,
    DataBaseStorageResponse,
    DataAlreadyExistsResponse,
)

perf_dataset = APIRouter()

# 数据集序列化统一排除脚手架字段(对齐 load_preset 视图模式)
DATASET_EXCLUDE_FIELDS = {
    "state",
    "created_user", "created_time",
    "updated_user", "updated_time",
    "reserve_1", "reserve_2", "reserve_3",
}
DATASET_REPLACE_FIELDS = {"id": "ds_id"}


@perf_dataset.post("/create", summary="新增压测数据集", description="新增压测数据集(手动录入或上传解析后确认落库)")
async def create_perf_dataset(
        ds_in: PerfDatasetCreate = Body(..., description="压测数据集信息"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    新增压测数据集。

    :param ds_in: 压测数据集入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.dataset_curd.create_perf_dataset(ds_in=ds_in)
        data = await instance.to_dict(exclude_fields=DATASET_EXCLUDE_FIELDS, replace_fields=DATASET_REPLACE_FIELDS)
        return SuccessResponse(message="新增成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增压测数据集失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {str(e)}")


@perf_dataset.delete("/delete", summary="删除压测数据集", description="根据id或code删除压测数据集信息(被场景引用时禁止)")
async def delete_perf_dataset(
        ds_id: Optional[int] = Query(None, description="数据集ID"),
        ds_code: Optional[str] = Query(None, description="数据集标识代码"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据id或code删除压测数据集。

    :param ds_id: 数据集主键ID
    :param ds_code: 数据集业务标识
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.dataset_curd.delete_perf_dataset(ds_id=ds_id, ds_code=ds_code)
        data = await instance.to_dict(exclude_fields=DATASET_EXCLUDE_FIELDS, replace_fields=DATASET_REPLACE_FIELDS)
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code删除压测数据集信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@perf_dataset.post("/update", summary="更新压测数据集", description="根据id或code更新压测数据集信息(行数据整体覆盖)")
async def update_perf_dataset(
        ds_in: PerfDatasetUpdate = Body(..., description="压测数据集信息"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据id或code更新压测数据集。

    :param ds_in: 压测数据集入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.dataset_curd.update_perf_dataset(ds_in=ds_in)
        data = await instance.to_dict(exclude_fields=DATASET_EXCLUDE_FIELDS, replace_fields=DATASET_REPLACE_FIELDS)
        return SuccessResponse(data=data, message="更新成功", total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code更新压测数据集信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {str(e)}")


@perf_dataset.get("/get", summary="查询压测数据集", description="根据id或code查询压测数据集信息(含场景数据与矩阵全量)")
async def get_perf_dataset(
        ds_id: Optional[int] = Query(None, description="数据集ID"),
        ds_code: Optional[str] = Query(None, description="数据集标识代码"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据id或code查询压测数据集。

    :param ds_id: 数据集主键ID
    :param ds_code: 数据集业务标识
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if ds_id:
            instance = await services.dataset_curd.get_by_id(ds_id=ds_id, on_error=True, state__not=1)
        else:
            instance = await services.dataset_curd.get_by_code(ds_code=ds_code, on_error=True, state__not=1)
        data = await instance.to_dict(exclude_fields=DATASET_EXCLUDE_FIELDS, replace_fields=DATASET_REPLACE_FIELDS)
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询压测数据集信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@perf_dataset.get("/list_for_api", summary="查询接口可用数据集", description="查询某压测接口绑定的数据源(一个接口只能有一个数据源, 轻量字段不分页, 调试取数与场景编排下拉共用)")
async def list_perf_datasets_for_api(
        api_id: int = Query(..., ge=1, description="压测接口ID"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    查询某压测接口绑定的数据源列表(一个接口只能有一个数据源)。

    :param api_id: 压测接口ID
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应(数据集轻量字段列表, 场景数由dataset_names派生)
    """
    try:
        rows = await services.dataset_curd.list_enabled_for_api(api_id=api_id)
        # list_enabled_for_api 返回字典列表(.values()), 直接重命名 id → ds_id
        data = []
        for row in rows:
            d = dict(row)  # 复制字典
            if "id" in d:
                d["ds_id"] = d.pop("id")
            data.append(d)
        return SuccessResponse(message="查询成功", data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询接口可用数据集失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@perf_dataset.post("/update_fields", summary="同步接口报文字段", description="按接口当前报文同步数据源矩阵字段(新增补空/删除剔除/保留值不动)")
async def update_perf_dataset_fields(
        data_in: PerfDatasetUpdateFields = Body(..., description="接口定位(一个接口只能有一个数据源)"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    按压测接口当前报文同步数据源矩阵字段(对齐 autotest 设计: 一个接口绑定一个数据源)。

    以接口报文展平后的字段路径为准: 新增字段补空值, 删除字段剔除, 保留字段场景值不动;
    ASSERT分区原样保留, 方向以矩阵实际结构为准。

    :param data_in: 接口定位入参(api_id)
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        # 按 api_id 定位接口绑定的唯一数据源
        api = await services.api_curd.get_by_id(api_id=data_in.api_id, on_error=True, state__not=1)
        instance = await services.dataset_curd.model.filter(bind_api_id=data_in.api_id, state__not=1).first()
        if not instance:
            return BadReqResponse(message="该接口尚未绑定数据源, 无法完成字段同步")
        if not isinstance(instance.dataframe, list) or not instance.dataframe:
            return BadReqResponse(message="数据源矩阵为空, 无法完成字段同步")
        updates = await sync_data_source_fields(api, instance.dataframe, instance.axis)
        async with in_transaction():
            await services.dataset_curd.update(id=instance.id, obj_in=updates)
        LOGGER.info(f"压测数据源[id={instance.id}]字段同步完成")
        return SuccessResponse(message="字段同步成功", data={"ds_id": instance.id}, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"同步压测数据源字段失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"同步失败，异常描述: {e}")


@perf_dataset.get("/download", summary="导出压测数据集", description="按数据集矩阵导出xlsx(sheet名为数据集名称, 样式与功能数据源导出一致)")
async def download_perf_dataset(
        ds_id: Optional[int] = Query(None, description="数据集ID"),
        ds_code: Optional[str] = Query(None, description="数据集标识代码"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据id或code导出压测数据集xlsx(矩阵为空时返回业务提示)。

    :param ds_id: 数据集主键ID
    :param ds_code: 数据集业务标识
    :param services: 性能测试CRUD依赖聚合
    :return: 文件流响应
    """
    try:
        if ds_id:
            instance = await services.dataset_curd.get_by_id(ds_id=ds_id, on_error=True, state__not=1)
        else:
            instance = await services.dataset_curd.get_by_code(ds_code=ds_code, on_error=True, state__not=1)
        matrix = instance.dataframe if isinstance(instance.dataframe, list) else []
        if not matrix:
            return BadReqResponse(message="该数据集当前没有测试数据, 无法导出")
        safe_name = safe_sheet_name(instance.ds_name, set())
        df = pd.DataFrame(matrix)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, header=False, sheet_name=safe_name)
            # 统一样式: 分区标记黄底、居中换行、行高/列宽自适应(与功能数据源导出风格一致)
            style_data_source_sheet(writer.sheets[safe_name])
        output.seek(0)

        file_name = f"数据源导出_{instance.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
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
        LOGGER.error(f"导出压测数据集xlsx失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"导出失败，异常描述: {e}")


@perf_dataset.post("/upload", summary="上传解析压测数据集文件", description="上传xlsx解析为数据集预览(场景数据+矩阵+文件溯源信息, 不落库, 确认后随create/update提交dataframe+axis落库)")
async def upload_perf_dataset(
        ds_project: int = Form(..., description="数据集所属应用ID"),
        file: UploadFile = File(..., description="数据集文件(仅支持.xlsx后缀)"),
):
    """
    上传解析压测数据集文件(预览不落库, 文件已落盘待保存时随数据集关联溯源)。

    :param ds_project: 数据集所属应用ID(决定文件落盘子目录)
    :param file: 上传文件(仅支持.xlsx)
    :return: 统一HTTP响应, data结构:
        {"dataset": {"场景1": {...四分区}}, "dataset_names": ["场景1"],
         "dataframe": [[...]], "axis": 0,
         "file_name": "...", "file_path": "...", "file_hash": "sha256..."}
    """
    if not (file.filename or "").lower().endswith(".xlsx"):
        return FileExtensionResponse(message="仅支持.xlsx后缀的数据集文件")
    try:
        data = await PerfDatasetService.parse_upload_file(upload_file=file, ds_project=ds_project)
        return SuccessResponse(message="解析成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"上传解析压测数据集文件失败，异常描述: {e}\n{traceback.format_exc()}")
        return BadReqResponse(message=f"上传解析失败，异常描述: {str(e)}")
