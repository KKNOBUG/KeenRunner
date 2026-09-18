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
import traceback
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, Query, UploadFile

from backend.applications.performance.dependencies import PerfServices, get_perf_api_services
from backend.applications.performance.services.perf_dataset_service import PerfDatasetService
from backend.applications.performance.schemas.perf_dataset_schema import (
    PerfDatasetCreate,
    PerfDatasetUpdate,
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

# 数据集序列化统一排除脚手架字段(对齐 task 视图模式)
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


@perf_dataset.get("/list_for_api", summary="查询接口可用数据集", description="查询某压测接口可用的数据集(归属该接口+同应用自由数据, 轻量字段不分页, 调试取数与场景编排下拉共用)")
async def list_perf_datasets_for_api(
        api_id: int = Query(..., ge=1, description="压测接口ID"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    查询某压测接口可用的数据集列表。

    :param api_id: 压测接口ID
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应(数据集轻量字段列表, 场景数由dataset_names派生)
    """
    try:
        rows = await services.dataset_curd.list_enabled_for_api(api_id=api_id)
        return SuccessResponse(message="查询成功", data=rows)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询接口可用数据集失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


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
