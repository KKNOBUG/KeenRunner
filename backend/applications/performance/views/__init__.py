# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : __init__.py
@DateTime: 2026/9/14 11:20
"""
from fastapi import APIRouter

from backend.enums import ResourceTag

from .perf_analysis_view import perf_analysis
from .perf_api_view import perf_api
from .perf_comparison_view import perf_comparison
from .perf_dataset_view import perf_dataset
from .perf_job_view import perf_job
from .perf_report_view import perf_report
from .perf_scene_view import perf_scene
from .perf_load_preset_view import perf_load_preset

performance = APIRouter()

# tags 取 ResourceTag.desc（唯一事实源），启动契约据此绑定资源族，禁止手写中文字面量
performance.include_router(perf_api, prefix="/api", tags=[ResourceTag.PERF_API.desc])
performance.include_router(perf_dataset, prefix="/dataset", tags=[ResourceTag.PERF_DATASET.desc])
performance.include_router(perf_scene, prefix="/scene", tags=[ResourceTag.PERF_SCENE.desc])
performance.include_router(perf_load_preset, prefix="/load_preset", tags=[ResourceTag.PERF_PRESET.desc])
performance.include_router(perf_job, prefix="/job", tags=[ResourceTag.PERF_JOB.desc])
performance.include_router(perf_report, prefix="/report", tags=[ResourceTag.PERF_REPORT.desc])
performance.include_router(perf_comparison, prefix="/comparison", tags=[ResourceTag.PERF_COMPARE.desc])
performance.include_router(perf_analysis, prefix="/analysis", tags=[ResourceTag.PERF_DIAGNOSIS.desc])
