# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : __init__.py
@DateTime: 2026/9/14 11:20
"""
from fastapi import APIRouter

from .perf_analysis_view import perf_analysis
from .perf_api_view import perf_api
from .perf_comparison_view import perf_comparison
from .perf_dataset_view import perf_dataset
from .perf_job_view import perf_job
from .perf_report_view import perf_report
from .perf_scene_view import perf_scene
from .perf_load_preset_view import perf_load_preset

performance = APIRouter()

# tags 采用「一级目录:二级模块」，与侧边栏菜单对齐，便于角色权限按模块制定规则
performance.include_router(perf_api, prefix="/api", tags=["性能测试:接口"])
performance.include_router(perf_dataset, prefix="/dataset", tags=["性能测试:数据集"])
performance.include_router(perf_scene, prefix="/scene", tags=["性能测试:场景"])
performance.include_router(perf_load_preset, prefix="/load_preset", tags=["性能测试:负载预设"])
performance.include_router(perf_job, prefix="/job", tags=["性能测试:作业"])
performance.include_router(perf_report, prefix="/report", tags=["性能测试:报告"])
performance.include_router(perf_comparison, prefix="/comparison", tags=["性能测试:对比"])
performance.include_router(perf_analysis, prefix="/analysis", tags=["性能测试:诊断"])
