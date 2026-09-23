# -*- coding: utf-8 -*-
"""
多记录对比/汇总视图：/perf/comparison/* 路由编排(参数接收 -> 服务调用 -> 统一响应)。

对比记录为结论快照实体(创建时一次性计算, 无update语义), detail 下发全字段
快照并复核引用报告现存性; 列表不加载 report_refs/result_snapshot 大字段。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_comparison_view.py
@DateTime: 2026/9/17 20:30
"""
import traceback
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Query
from tortoise.expressions import Q

from backend.applications.performance.dependencies import PerfServices, get_perf_api_services
from backend.applications.performance.schemas.perf_comparison_schema import (
    PerfComparisonCreate,
    PerfComparisonSelect,
)
from backend.applications.performance.services.perf_comparison_service import PerfComparisonService
from backend.configure import LOGGER
from backend.core.exceptions import (
    DataBaseStorageException,
    NotFoundException,
    ParameterException,
)
from backend.core.responses import (
    DataBaseStorageResponse,
    FailureResponse,
    NotFoundResponse,
    ParameterResponse,
    SuccessResponse,
)

perf_comparison = APIRouter()

# 序列化排除脚手架字段(对齐 job/dataset 视图模式; 详情保留创建人与时间供结论溯源)
COMPARISON_EXCLUDE_FIELDS = {
    "state",
    "reserve_1", "reserve_2", "reserve_3",
}
COMPARISON_REPLACE_FIELDS = {"id": "comparison_id"}


@perf_comparison.post("/create", summary="新增多记录对比/汇总", description="对2~20份已完成报告创建横向对比或同场景汇总(创建时一次性计算结果快照)")
async def create_perf_comparison(
        comparison_in: PerfComparisonCreate = Body(..., description="对比记录信息"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    新建多记录对比/汇总记录。

    :param comparison_in: 对比记录创建入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await PerfComparisonService.create_comparison(comparison_in=comparison_in)
        data = await instance.to_dict(
            exclude_fields=COMPARISON_EXCLUDE_FIELDS, replace_fields=COMPARISON_REPLACE_FIELDS)
        return SuccessResponse(message="创建成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新建多记录对比失败, 异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"创建失败, 异常描述: {str(e)}")


@perf_comparison.get("/detail", summary="查询对比/汇总详情", description="根据id或code查询对比记录(含结果快照与引用报告现存性复核)")
async def get_perf_comparison_detail(
        comparison_id: Optional[int] = Query(None, description="对比记录ID"),
        comparison_code: Optional[str] = Query(None, description="对比记录标识代码"),
):
    """
    查询对比/汇总记录详情。

    :param comparison_id: 对比记录主键ID
    :param comparison_code: 对比记录业务标识
    :return: 统一HTTP响应, data含detail与missing_report_codes
    """
    try:
        if not comparison_id and not comparison_code:
            raise ParameterException(message="请提供参数[comparison_id | comparison_code]查询对比记录")
        result = await PerfComparisonService.get_comparison_detail(
            comparison_id=comparison_id, comparison_code=comparison_code)
        return SuccessResponse(message="查询成功", data=result, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询对比记录详情失败, 异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 异常描述: {str(e)}")


@perf_comparison.post("/search", summary="查询对比/汇总列表", description="根据条件分页查询对比记录列表(Body, 不含结果快照大字段)")
async def search_perf_comparisons(
        comparison_in: PerfComparisonSelect = Body(..., description="查询条件"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据条件分页查询对比/汇总记录列表。

    :param comparison_in: 查询条件入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if comparison_in.comparison_id:
            q &= Q(id=comparison_in.comparison_id)
        if comparison_in.comparison_code:
            q &= Q(comparison_code=comparison_in.comparison_code)
        if comparison_in.comparison_name:
            q &= Q(comparison_name__contains=comparison_in.comparison_name)
        if comparison_in.comparison_mode:
            q &= Q(comparison_mode=comparison_in.comparison_mode)
        if comparison_in.created_user:
            q &= Q(created_user=comparison_in.created_user)
        q &= Q(state=comparison_in.state)
        total, rows = await services.comparison_curd.select_perf_comparisons(
            search=q,
            page=comparison_in.page,
            page_size=comparison_in.page_size,
            order=comparison_in.order,
        )
        # 列表走显式取列(字典行), 统一主键别名后直接下发
        data: List[Dict[str, Any]] = [{**row, "comparison_id": row.pop("id", None)} for row in rows]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"分页查询对比记录列表失败, 异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 异常描述: {str(e)}")


@perf_comparison.delete("/delete", summary="删除对比/汇总记录", description="根据id或code软删除对比记录(结论快照不可修改, 删除后可重新创建)")
async def delete_perf_comparison(
        comparison_id: Optional[int] = Query(None, description="对比记录ID"),
        comparison_code: Optional[str] = Query(None, description="对比记录标识代码"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    软删除对比/汇总记录。

    :param comparison_id: 对比记录主键ID
    :param comparison_code: 对比记录业务标识
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if not comparison_id and not comparison_code:
            raise ParameterException(message="请提供参数[comparison_id | comparison_code]删除对比记录")
        instance = await services.comparison_curd.delete_perf_comparison(
            comparison_id=comparison_id, comparison_code=comparison_code)
        data = await instance.to_dict(
            exclude_fields=COMPARISON_EXCLUDE_FIELDS, replace_fields=COMPARISON_REPLACE_FIELDS)
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"删除对比记录失败, 异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败, 异常描述: {str(e)}")
