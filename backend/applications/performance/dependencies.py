# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : dependencies.py
@DateTime: 2026/9/14 11:20
"""
from dataclasses import dataclass

from backend.applications.performance.services.perf_api_crud import PerfApiCrud
from backend.applications.performance.services.perf_comparison_crud import PerfComparisonCrud
from backend.applications.performance.services.perf_dataset_crud import PerfDatasetCrud
from backend.applications.performance.services.perf_job_crud import PerfJobCrud
from backend.applications.performance.services.perf_report_crud import PerfReportCrud
from backend.applications.performance.services.perf_scene_crud import PerfSceneCrud
from backend.applications.performance.services.perf_load_preset_crud import PerfLoadPresetCrud


@dataclass
class PerfServices:
    """性能测试相关CRUD服务聚合，供视图层依赖注入。"""
    preset_curd: PerfLoadPresetCrud
    report_curd: PerfReportCrud
    api_curd: PerfApiCrud
    scene_curd: PerfSceneCrud
    dataset_curd: PerfDatasetCrud
    job_curd: PerfJobCrud
    comparison_curd: PerfComparisonCrud


async def get_perf_api_services() -> PerfServices:
    """
    构造并返回性能测试CRUD服务聚合实例。

    :return: PerfServices 实例
    """
    return PerfServices(
        preset_curd=PerfLoadPresetCrud(),
        report_curd=PerfReportCrud(),
        api_curd=PerfApiCrud(),
        scene_curd=PerfSceneCrud(),
        dataset_curd=PerfDatasetCrud(),
        job_curd=PerfJobCrud(),
        comparison_curd=PerfComparisonCrud(),
    )
