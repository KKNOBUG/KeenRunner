# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_analysis_view.py
@DateTime: 2026/9/17 14:30
"""
import traceback

from fastapi import APIRouter

from backend.applications.performance.services.perf_analysis_service import PerfAnalysisService
from backend.configure import LOGGER
from backend.core.responses import FailureResponse, SuccessResponse

perf_analysis = APIRouter()


@perf_analysis.get("/status", summary="查询性能域运行态诊断", description="只读汇聚指标服务可用性/产物目录体量/报告状态分布(运维排障用)")
async def get_perf_analysis_status():
    """
    性能域只读诊断: 指标服务探活、产物根目录统计、报告状态分布与最近执行记录。

    各分项异常(指标不可达/产物目录缺失)不作为接口错误, 由对应分段的字段如实回显。

    :return: 统一HTTP响应, data含metrics/artifacts/reports三段
    """
    try:
        data = await PerfAnalysisService.status()
        return SuccessResponse(message="诊断信息查询成功", data=data, total=1)
    except Exception as e:
        LOGGER.error(f"性能域诊断信息查询失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"诊断查询失败，异常描述: {str(e)}")
