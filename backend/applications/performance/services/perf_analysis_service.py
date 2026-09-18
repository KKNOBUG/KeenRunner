# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_analysis_service.py
@DateTime: 2026/9/17 14:30
"""
import os
from typing import Any, Dict, List

from tortoise.functions import Count

from backend.applications.performance.models.perf_report_model import PerfReportModel
from backend.applications.performance.services.perf_asset_utils import format_human_size
from backend.applications.performance.services.perf_metrics_service import PerfMetricsService
from backend.configure import LOGGER, PROJECT_CONFIG


class PerfAnalysisService:
    """性能域只读诊断: 指标服务可用性 / 产物目录体量 / 报告状态分布, 供运维排障页与运维巡检脚本消费。"""

    @staticmethod
    async def status() -> Dict[str, Any]:
        """
        汇聚性能域运行态诊断信息(全部只读, 不触发任何清理与写操作)。

        指标探活失败与产物目录缺失均不作为接口错误(诊断的本义就是暴露异常), 仅如实回显。

        :return: 诊断结果字典, 结构:
            {"metrics": PerfMetricsService.probe_availability() 结果,
             "artifacts": {"root": 产物根目录, "exists": 是否存在, "report_dirs": 报告目录数,
                           "total_size": 总字节, "total_size_human": 可读体积},
             "reports": {"total": 有效报告总数, "by_status": {状态: 数量},
                         "recent": [{report_code, scene_name, status, started_time}]}}
        """
        metrics_probe: Dict[str, Any] = await PerfMetricsService.probe_availability()
        return {
            "metrics": metrics_probe,
            "artifacts": PerfAnalysisService._summarize_artifact_root(),
            "reports": await PerfAnalysisService._summarize_reports(),
        }

    @staticmethod
    def _summarize_artifact_root() -> Dict[str, Any]:
        """
        统计压测产物根目录: 报告子目录数与递归总占用(报告目录内为场景快照/日志/分片小文件, 递归开销可忽略)。

        :return: 产物根目录摘要字典(目录不存在时 exists=False, 其余计数为0)
        """
        root: str = PROJECT_CONFIG.OUTPUT_PERF_DIR
        summary: Dict[str, Any] = {
            "root": root, "exists": os.path.isdir(root),
            "report_dirs": 0, "total_size": 0, "total_size_human": "0 B",
        }
        if not summary["exists"]:
            LOGGER.warning(f"压测产物根目录不存在: {root}")
            return summary
        for entry in os.scandir(root):
            if not entry.is_dir():
                continue
            summary["report_dirs"] += 1
            for dirpath, _dir_names, file_names in os.walk(entry.path):
                for file_name in file_names:
                    try:
                        summary["total_size"] += os.path.getsize(os.path.join(dirpath, file_name))
                    except OSError:
                        # 单个文件读取失败(竞态删除)不中断统计
                        continue
        summary["total_size_human"] = format_human_size(summary["total_size"])
        return summary

    @staticmethod
    async def _summarize_reports() -> Dict[str, Any]:
        """
        统计有效报告的状态分布与最近执行记录(两条查询, 循环外一次完成)。

        :return: 报告统计字典
        """
        status_rows: List[Dict[str, Any]] = await (
            PerfReportModel.filter(state=0)
            .annotate(count=Count("id"))
            .group_by("status")
            .values("status", "count")
        )
        recent_rows: List[PerfReportModel] = await (
            PerfReportModel.filter(state=0)
            .order_by("-id")
            .limit(10)
            .all()
        )
        return {
            "total": sum(int(row.get("count") or 0) for row in status_rows),
            # group_by 回查的status是枚举对象, 归一为字面量与 recent 行口径一致
            "by_status": {
                str(getattr(row.get("status"), "value", row.get("status"))): int(row.get("count") or 0)
                for row in status_rows
            },
            "recent": [
                {
                    "report_code": row.report_code,
                    "scene_name": row.scene_name,
                    "status": str(getattr(row.status, "value", row.status)),
                    "started_time": row.started_time.strftime("%Y-%m-%d %H:%M:%S") if row.started_time else None,
                }
                for row in recent_rows
            ],
        }
