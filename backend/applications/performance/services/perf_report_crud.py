# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_report_crud.py
@DateTime: 2026/9/14 11:20
"""
from typing import Any, Dict, List, Optional, Tuple

from tortoise.exceptions import DoesNotExist, FieldError
from tortoise.expressions import Q

from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.performance.models.perf_report_model import PerfReportModel
from backend.applications.performance.services.perf_asset_utils import diff_report_pair, summarize_report_diff
from backend.configure import LOGGER
from backend.core.exceptions import NotFoundException, ParameterException

# 列表查询返回列(白名单): 报告表有十余个快照大字段(config_snapshot/api_aggregations/locust_stats 等),
# 整行捞取会让列表报文随报告条数线性膨胀, 故只取列表页实际展示与排序需要的列。
# target_result 随列表返回是刻意保留: 列表页需一眼看出哪条未达标, 其元素个数受场景 SLA 目标条数上限约束
REPORT_LIST_FIELDS = (
    "id", "report_code", "batch_code", "status",
    "perf_id", "perf_code", "scene_id", "scene_code", "scene_name", "run_mode",
    "concurrent_users", "target_rps", "run_duration", "process_count", "env_name", "env_config_name",
    "started_time", "finished_time", "duration_seconds", "warmup_seconds",
    "total_requests", "success_requests", "fail_requests", "error_rate",
    "rps", "success_rps", "avg_rt", "p95", "p99",
    "target_result", "stopped_reason",
    "created_user", "created_time",
)

# 对比页双侧报告摘要取列(白名单): 只取指标对照表需要的列, 快照大字段不进对比报文
REPORT_COMPARE_METRICS_FIELDS = (
    "id", "report_code", "status", "scene_code", "scene_name", "run_mode",
    "concurrent_users", "target_rps", "run_duration", "env_name", "env_config_name",
    "total_requests", "success_requests", "fail_requests", "error_rate",
    "rps", "success_rps", "avg_rt", "p50", "p90", "p95", "p99",
    "duration_seconds", "config_fingerprint", "created_user", "created_time",
)


class PerfReportCrud(ScaffoldCrud[PerfReportModel, Any, Any]):
    """
    压测报告查询CRUD。

    报告记录由执行管线(PerfExecuteService.execute_pipeline)独占写入,
    本类仅提供查询入口, 不承载视图层 create/update 语义。
    """

    def __init__(self):
        super().__init__(model=PerfReportModel)

    async def get_by_id(self, report_id: int, on_error: bool = False, **kwargs) -> Optional[PerfReportModel]:
        """
        根据主键ID查询压测报告。

        :param report_id: 报告主键ID
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 报告实例或None
        """
        if not report_id:
            error_message: str = "查询压测报告信息失败, 参数[report_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.get_or_none(id=report_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询压测报告信息失败, 记录[id={report_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, report_code: str, on_error: bool = False, **kwargs) -> Optional[PerfReportModel]:
        """
        根据报告标识代码查询压测报告。

        :param report_code: 报告业务标识
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 报告实例或None
        """
        if not report_code:
            error_message: str = "查询压测报告信息失败, 参数[report_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 基类 get_or_none 的 id 为必传位参, 按业务标识查询必须走 model.filter(对齐 PerfTaskCrud.get_by_code)
        instance = await self.model.filter(report_code=report_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询压测报告信息失败, 记录[report_code={report_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def select_perf_reports(
            self,
            search: Q,
            page: int = 1,
            page_size: int = 10,
            order: Optional[List[str]] = None,
    ) -> Tuple[int, List[dict]]:
        """
        按条件分页查询压测报告列表(显式取列, 不加载快照大字段)。

        :param search: 查询条件(view层组装, 含state过滤)
        :param page: 页码
        :param page_size: 每页数量
        :param order: 排序字段列表(缺省按起始时间倒序)
        :return: (报告总数, 当前页报告行列表)
        """
        total: int = await self.model.filter(search).count()
        order_fields = order or ["-started_time"]
        queryset = self.model.filter(search).offset((page - 1) * page_size).limit(page_size)
        try:
            rows = await queryset.order_by(*order_fields).values(*REPORT_LIST_FIELDS)
        except (FieldError, DoesNotExist) as e:
            error_message: str = f"压测报告列表排序字段非法, 异常描述: {e}"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        return total, rows

    async def compare_reports(self, report_code: str, baseline_code: str) -> Dict[str, Any]:
        """
        对比两份压测报告: 配置差异明细 + 双侧核心指标对照(报告对比页数据源)。

        与基线退化判定(_build_baseline_diff)共用 diff_report_pair, 但本入口不限
        同场景同指纹: 对比页要的正是「不同并发/不同编排差在哪」, 差异由明细自说明。

        :param report_code: 当前报告标识代码
        :param baseline_code: 基线报告标识代码
        :return: 对比结果字典, 形如:
            {"current": {报告摘要}, "baseline": {报告摘要},
             "diff": {"same_scene": true, "fingerprint_same": false,
                      "field_diffs": [...], "item_diffs": [...]},
             "summary": ["峰值并发不一致: 基线[50] → 当前[100]"]}
        """
        current = await self.get_by_code(report_code=report_code, on_error=True, state__not=1)
        baseline = await self.get_by_code(report_code=baseline_code, on_error=True, state__not=1)
        if current.id == baseline.id:
            error_message: str = "报告对比失败, 两份报告不能是同一条记录"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        diffs: Dict[str, Any] = diff_report_pair(current, baseline)
        return {
            "current": await current.to_dict(
                include_fields=list(REPORT_COMPARE_METRICS_FIELDS), replace_fields={"id": "report_id"}),
            "baseline": await baseline.to_dict(
                include_fields=list(REPORT_COMPARE_METRICS_FIELDS), replace_fields={"id": "report_id"}),
            "diff": diffs,
            "summary": summarize_report_diff(diffs),
        }
