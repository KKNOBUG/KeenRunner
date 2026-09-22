# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_report_view.py
@DateTime: 2026/9/14 11:20
"""
import io
import traceback
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import quote

import pandas as pd
from fastapi import APIRouter, Body, Query, Depends
from starlette.responses import StreamingResponse
from tortoise.expressions import Q

from backend.applications.performance.dependencies import PerfServices, get_perf_api_services
from backend.applications.performance.schemas.perf_report_schema import PerfReportSelect, PerfReportMetrics
from backend.applications.performance.services.perf_asset_utils import (
    build_report_export_sheets,
    list_report_artifacts,
    resolve_report_artifact_path,
)
from backend.applications.performance.services.perf_metrics_service import PerfMetricsService
from backend.configure import LOGGER
from backend.core.exceptions import NotFoundException, ParameterException
from backend.core.responses import (
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    NotFoundResponse,
)
from backend.services.file_transfer import FileTransfer

perf_report = APIRouter()

# 报告序列化统一排除脚手架字段(列表/详情共用, 对齐 load_preset 视图模式)；
# created_user/created_time 保留: 执行人与创建时间是报告页与执行记录列表的业务列
REPORT_EXCLUDE_FIELDS = {
    "state",
    "updated_user", "updated_time",
    "reserve_1", "reserve_2", "reserve_3",
}


def normalize_report_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    清洗报告行数据：剔除脚手架字段并统一主键字段名, 与详情序列化口径保持一致。

    :param row: 报告原始行数据
    :return: 清洗后的报告行数据
    """
    for field in REPORT_EXCLUDE_FIELDS:
        row.pop(field, None)
    if "id" in row:
        row["report_id"] = row.pop("id")
    return row


@perf_report.get("/get", summary="查询压测报告", description="根据id或code查询压测报告详情(含locust统计快照)")
async def get_perf_report(
        report_id: Optional[int] = Query(None, description="报告ID"),
        report_code: Optional[str] = Query(None, description="报告标识代码"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据id或code查询压测报告详情。

    :param report_id: 报告主键ID
    :param report_code: 报告业务标识
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应(含locust_stats统计快照)
    """
    try:
        if report_id:
            instance = await services.report_curd.get_by_id(report_id=report_id, on_error=True, state__not=1)
        else:
            instance = await services.report_curd.get_by_code(report_code=report_code, on_error=True, state__not=1)
        data = await instance.to_dict(exclude_fields=REPORT_EXCLUDE_FIELDS, replace_fields={"id": "report_id"})
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询压测报告详情失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@perf_report.post("/search", summary="查询压测报告列表", description="根据条件分页查询压测报告列表信息")
async def search_perf_reports(
        report_in: PerfReportSelect = Body(..., description="查询条件"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    按条件分页查询压测报告列表(不含locust_stats快照大字段, 快照经详情接口获取)。

    :param report_in: 报告查询入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        q = build_report_search_query(report_in)
        total, rows = await services.report_curd.select_perf_reports(
            search=q,
            page=report_in.page,
            page_size=report_in.page_size,
            order=report_in.order,
        )
        data = [normalize_report_row(row) for row in rows]
        return SuccessResponse(message="报告列表查询成功", data=data, total=total)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件分页查询压测报告列表失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@perf_report.post("/metrics", summary="查询压测指标曲线", description="代理VictoriaMetrics查询压测指标时序曲线")
async def get_perf_report_metrics(
        metrics_in: PerfReportMetrics = Body(..., description="指标曲线查询条件"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    查询压测报告指标曲线：代理VictoriaMetrics query_range, 返回归一化时序序列。

    指标服务未配置或不可达时返回available=False与空序列, 不作为接口错误。

    :param metrics_in: 指标曲线查询入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        data = await PerfMetricsService.query_report_metrics(
            report_code=metrics_in.report_code,
            metrics=metrics_in.metrics,
            start=metrics_in.start,
            end=metrics_in.end,
            step=metrics_in.step,
        )
        return SuccessResponse(message="指标曲线查询成功", data=data, total=len(data.get("series", {})))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询压测指标曲线失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@perf_report.get("/snapshot_diff", summary="对比两份压测报告", description="配置差异明细(接口项增删改/标量维度/指纹)与双侧核心指标对照(不限同场景, 差异由明细自说明)")
async def snapshot_diff_perf_reports(
        report_code: str = Query(..., description="当前报告标识代码"),
        baseline_code: str = Query(..., description="基线报告标识代码"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    对比两份压测报告: 双侧指标对照 + 配置差异明细与可读摘要。

    :param report_code: 当前报告标识代码
    :param baseline_code: 基线报告标识代码
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应, data含current/baseline/diff/summary四段
    """
    try:
        data = await services.report_curd.compare_reports(report_code=report_code, baseline_code=baseline_code)
        return SuccessResponse(message="对比完成", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"对比压测报告失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"对比失败，异常描述: {str(e)}")


@perf_report.get("/artifacts", summary="查询报告产物清单", description="列出报告工作目录内的引擎产物文件(场景快照/引擎日志/结果分片)")
async def list_perf_report_artifacts(
        report_code: str = Query(..., description="报告标识代码"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    列出报告产物清单: 白名单内的场景快照/引擎日志/结果分片及其体积与修改时间。

    :param report_code: 报告业务标识
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应, data为清单列表
    """
    try:
        data = list_report_artifacts(report_code=report_code)
        return SuccessResponse(message="产物清单查询成功", data=data, total=len(data))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询报告产物清单失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@perf_report.get("/artifact_download", summary="下载报告产物文件", description="按文件名下载报告产物(白名单: scene.json/locust.log/result_{pid}.json)")
async def download_perf_report_artifact(
        report_code: str = Query(..., description="报告标识代码"),
        name: str = Query(..., description="产物文件名"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    下载报告产物文件: 文件名白名单校验 + 目录越界防护后流式回传。

    :param report_code: 报告业务标识
    :param name: 产物文件名
    :param services: 性能测试CRUD依赖聚合
    :return: 文件流响应
    """
    try:
        artifact_path = resolve_report_artifact_path(report_code=report_code, artifact_name=name)
        quoted_name: str = quote(name.encode("utf-8"))
        media_type = "text/plain" if name.endswith(".log") else "application/json"
        return StreamingResponse(
            content=FileTransfer.iter_download_file_chunks(download_file=artifact_path, add_bom=False),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quoted_name}"},
        )
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"下载报告产物文件失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"下载失败，异常描述: {str(e)}")


@perf_report.get("/export", summary="导出压测报告xlsx", description="导出报告概要/SLA判定/接口维度/事务维度/错误归因/基线对比多sheet报表")
async def export_perf_report(
        report_code: str = Query(..., description="报告标识代码"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    导出压测报告为 xlsx 报表: sheet 结构与报告抽屉区块一一镜像(轻量聚合数据, 同步导出)。

    :param report_code: 报告业务标识
    :param services: 性能测试CRUD依赖聚合
    :return: 文件流响应(xlsx)
    """
    try:
        report = await services.report_curd.get_by_code(report_code=report_code, on_error=True, state__not=1)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for sheet in build_report_export_sheets(report):
                frame = pd.DataFrame(sheet["rows"], columns=sheet["header"])
                frame.to_excel(writer, index=False, sheet_name=sheet["name"])
        output.seek(0)

        file_name = f"压测报告_{report.scene_name or report.report_code}_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        quoted_name: str = quote(file_name)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quoted_name}"},
        )
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"导出压测报告xlsx失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"导出失败，异常描述: {str(e)}")


def build_report_search_query(report_in: PerfReportSelect) -> Q:
    """
    组装压测报告查询条件。

    :param report_in: 报告查询入参
    :return: Tortoise Q查询条件(含state过滤)
    """
    q = Q()
    if report_in.report_id:
        q &= Q(id=report_in.report_id)
    if report_in.report_code:
        q &= Q(report_code__contains=report_in.report_code.strip())
    if report_in.preset_id:
        q &= Q(preset_id=report_in.preset_id)
    if report_in.preset_code:
        q &= Q(preset_code=report_in.preset_code)
    if report_in.batch_code:
        q &= Q(batch_code=report_in.batch_code)
    if report_in.status:
        q &= Q(status=report_in.status)
    if report_in.created_user:
        q &= Q(created_user=report_in.created_user)
    q &= Q(state=report_in.state)
    return q
