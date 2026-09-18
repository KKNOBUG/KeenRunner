# -*- coding: utf-8 -*-
"""
多记录对比/汇总服务: 业务校验、结果快照计算与创建/详情编排(设计§3.7)。

三模式语义:
- compare 横向对比: 指定基准报告, 逐份输出核心指标相对基准的变化(rps/p95等百分比、
  错误率百分点) + 配置差异摘要(复用 diff_report_pair/summarize_report_diff, 与报告
  对比页同一把尺子), 基准行不输出相对值;
- merge 汇总合并: 同场景多份报告视为并行实例聚合成一份视图, 计数与速率累加、
  错误率按总量重算、延迟类按请求数加权; 分位值为加权均值而非样本级真分位
  (报告不存原始样本), 以 warnings 显式标注口径;
- hybrid: 两者兼出, 结构为 {"compare": ..., "merge": ...}。

报告为不可变快照实体, 对比结论创建时一次性计算落库; 参与报告必须全部为
completed(运行中/失败/停止的报告指标不完整, 参与对比会误导结论)。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_comparison_service.py
@DateTime: 2026/9/17 20:30
"""
from typing import Any, Dict, List, Optional

from tortoise.expressions import Q

from backend.applications.performance.models.perf_comparison_model import PerfComparisonModel
from backend.applications.performance.models.perf_report_model import PerfReportModel
from backend.applications.performance.schemas.perf_comparison_schema import PerfComparisonCreate
from backend.applications.performance.services.perf_asset_utils import diff_report_pair, summarize_report_diff
from backend.applications.performance.services.perf_comparison_crud import PerfComparisonCrud
from backend.configure import LOGGER
from backend.core.exceptions import ParameterException
from backend.enums import PerfComparisonMode, PerfReportStatus

# 对比结论可用的指标字段(与报告表 B 组标量字段对齐, relative 相对变化按此口径)
COMPARISON_METRIC_FIELDS = (
    "total_requests", "error_rate", "rps", "success_rps", "avg_rt", "p95", "p99",
)

# merge 分位字段(按请求数加权均值, 需口径警告)
MERGE_WEIGHTED_FIELDS = ("avg_rt", "p50", "p90", "p95", "p99")

# merge 聚合的接口维度行字段(与报告 api_aggregations 元素结构对齐)
MERGE_API_METRIC_FIELDS = ("avg_rt", "p90", "p95", "p99")


class PerfComparisonService:

    @staticmethod
    async def create_comparison(*, comparison_in: PerfComparisonCreate) -> PerfComparisonModel:
        """
        创建对比/汇总记录: 批量校验参与报告 + 计算结果快照 + 落库。

        :param comparison_in: 对比记录创建schema(去重与基准归属已在schema层校验)
        :return: 创建后的对比记录实例
        """
        report_codes: List[str] = comparison_in.report_codes
        # 参与报告一次批量拉取(禁止循环内逐条查库)
        reports: List[PerfReportModel] = list(await PerfReportModel.filter(
            report_code__in=report_codes, state__not=1))
        PerfComparisonService._validate_reports(
            reports=reports, report_codes=report_codes, mode=comparison_in.comparison_mode)
        # 输出顺序与传入清单一致(基准优先由 _build_refs 保证)
        reports_by_code: Dict[str, PerfReportModel] = {report.report_code: report for report in reports}
        ordered_reports: List[PerfReportModel] = [reports_by_code[code] for code in report_codes]

        crud = PerfComparisonCrud()
        comparison_dict: Dict[str, Any] = {
            "comparison_name": comparison_in.comparison_name,
            "comparison_mode": comparison_in.comparison_mode,
            "report_count": len(ordered_reports),
            "report_refs": PerfComparisonService._build_refs(
                reports=ordered_reports, baseline_code=comparison_in.baseline_code),
            # 对齐参数当前唯一策略: 按接口标识精确对齐(显式落位, 后续扩展免改表)
            "align_params": {"align_by": "api_code"},
            "result_snapshot": PerfComparisonService._build_result_snapshot(
                reports=ordered_reports, mode=comparison_in.comparison_mode,
                baseline_code=comparison_in.baseline_code),
            "comparison_desc": comparison_in.comparison_desc,
            "created_user": comparison_in.created_user,
        }
        return await crud.create_perf_comparison(comparison_dict=comparison_dict)

    @staticmethod
    async def get_comparison_detail(
            *,
            comparison_id: Optional[int] = None,
            comparison_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询对比记录详情: 全字段快照 + 引用报告现存性复核。

        报告事后被软删时结论仍可展示(报告不可变), 缺失清单由前端标注提示。

        :param comparison_id: 对比记录主键ID
        :param comparison_code: 对比记录业务标识
        :return: {"detail": 对比记录全字段字典, "missing_report_codes": 已不存在的引用报告}
        """
        crud = PerfComparisonCrud()
        if comparison_id:
            instance = await crud.get_by_id(comparison_id=comparison_id, on_error=True, state__not=1)
        else:
            instance = await crud.get_by_code(comparison_code=comparison_code, on_error=True, state__not=1)
        detail = await instance.to_dict(exclude_fields={"state"}, replace_fields={"id": "comparison_id"})
        refs: List[Dict[str, Any]] = instance.report_refs or []
        ref_codes: List[str] = [str(ref.get("report_code")) for ref in refs if ref.get("report_code")]
        alive_codes: set[str] = set()
        if ref_codes:
            alive_rows = await PerfReportModel.filter(report_code__in=ref_codes, state__not=1).values("report_code")
            alive_codes = {row["report_code"] for row in alive_rows}
        missing = [code for code in ref_codes if code not in alive_codes]
        return {"detail": detail, "missing_report_codes": missing}

    # ============================ 校验与引用快照 ============================

    @staticmethod
    def _validate_reports(
            reports: List[PerfReportModel],
            report_codes: List[str],
            mode: PerfComparisonMode,
    ) -> None:
        """
        参与报告业务校验: 存在性/完成态, 汇总类模式额外校验同场景。

        compare 不限同场景: 与报告对比页同一立场, 对比的意义正是看不同配置差在哪,
        差异由 per_report_diffs 自说明。

        :param reports: 批量拉取的报告实例
        :param report_codes: 传入的报告标识清单
        :param mode: 对比模式
        :raises ParameterException: 缺失/未完成/跨场景(仅汇总类模式)
        """
        found_codes = {report.report_code for report in reports}
        missing = [code for code in report_codes if code not in found_codes]
        if missing:
            error_message: str = f"创建对比记录失败, 以下报告不存在或已删除: {missing}"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        uncompleted = [
            report.report_code for report in reports
            if report.status != PerfReportStatus.COMPLETED
        ]
        if uncompleted:
            error_message: str = (
                f"创建对比记录失败, 以下报告未完成执行(仅completed报告的指标可参与对比): {uncompleted}"
            )
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        scene_codes = {report.scene_code for report in reports if report.scene_code}
        if mode in (PerfComparisonMode.MERGE, PerfComparisonMode.HYBRID) and len(scene_codes) > 1:
            error_message: str = (
                "创建对比记录失败, 汇总合并要求全部报告属于同一压测场景, "
                f"当前涉及场景: {sorted(scene_codes)}"
            )
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

    @staticmethod
    def _build_refs(reports: List[PerfReportModel], baseline_code: Optional[str]) -> List[Dict[str, Any]]:
        """
        组装引用摘要快照(基准报告排首位, 其余按传入顺序)。

        :param reports: 按传入顺序排列的报告实例
        :param baseline_code: 基准报告标识(可为空)
        :return: [{report_id, report_code, scene_name, concurrent_users, status, started_time, is_baseline}]
        """
        def ref_of(report: PerfReportModel) -> Dict[str, Any]:
            return {
                "report_id": report.id,
                "report_code": report.report_code,
                "scene_name": report.scene_name,
                "concurrent_users": report.concurrent_users,
                "status": str(getattr(report.status, "value", report.status)),
                "started_time": report.started_time.isoformat() if report.started_time else None,
                "is_baseline": bool(baseline_code and report.report_code == baseline_code),
            }

        ordered = sorted(
            reports,
            key=lambda report: 0 if baseline_code and report.report_code == baseline_code else 1,
        )
        return [ref_of(report) for report in ordered]

    # ============================ 结果快照计算 ============================

    @staticmethod
    def _build_result_snapshot(
            reports: List[PerfReportModel],
            mode: PerfComparisonMode,
            baseline_code: Optional[str],
    ) -> Dict[str, Any]:
        """
        按模式计算结果快照: compare/merge/hybrid 各自的结构见模块 docstring。

        :param reports: 基准优先排序后的报告实例
        :param mode: 对比模式
        :param baseline_code: 基准报告标识(compare/hybrid必填)
        :return: 结果快照字典
        """
        if mode == PerfComparisonMode.MERGE:
            return PerfComparisonService._build_merge_snapshot(reports)
        if mode == PerfComparisonMode.HYBRID:
            return {
                "compare": PerfComparisonService._build_compare_snapshot(reports, baseline_code),
                "merge": PerfComparisonService._build_merge_snapshot(reports),
            }
        return PerfComparisonService._build_compare_snapshot(reports, baseline_code)

    @staticmethod
    def _build_compare_snapshot(reports: List[PerfReportModel], baseline_code: str) -> Dict[str, Any]:
        """
        横向对比快照: 基准行在前, 逐份输出指标相对变化与配置差异摘要。

        :param reports: 报告实例(基准在列首)
        :param baseline_code: 基准报告标识
        :return: {"baseline_code", "metric_rows", "per_report_diffs"}
        """
        baseline = next((report for report in reports if report.report_code == baseline_code), None)
        if baseline is None:
            error_message: str = f"计算横向对比失败, 基准报告[{baseline_code}]不在参与清单内"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        metric_rows: List[Dict[str, Any]] = []
        for report in reports:
            row: Dict[str, Any] = {
                "report_code": report.report_code,
                "scene_name": report.scene_name,
                "concurrent_users": report.concurrent_users,
                "is_baseline": report.report_code == baseline_code,
                **{field: getattr(report, field) for field in COMPARISON_METRIC_FIELDS},
                "relative": None,
            }
            if not row["is_baseline"]:
                # 比率类给百分比变化, 错误率/请求总数额外给绝对差口径(百分点pp/计数差)便于小基线判读
                row["relative"] = {
                    field: PerfComparisonService._pct_delta(
                        current=getattr(report, field), baseline=getattr(baseline, field))
                    for field in COMPARISON_METRIC_FIELDS if field != "total_requests"
                } | {
                    "error_rate_pp": round(
                        (report.error_rate or 0) - (baseline.error_rate or 0), 2),
                    "total_requests_delta": (report.total_requests or 0) - (baseline.total_requests or 0),
                }
            metric_rows.append(row)

        per_report_diffs: List[Dict[str, Any]] = []
        for report in reports:
            if report.report_code == baseline_code:
                continue
            diffs = diff_report_pair(report, baseline)
            per_report_diffs.append({
                "report_code": report.report_code,
                "fingerprint_same": diffs.get("fingerprint_same", False),
                "summary": summarize_report_diff(diffs),
            })
        return {"baseline_code": baseline_code, "metric_rows": metric_rows, "per_report_diffs": per_report_diffs}

    @staticmethod
    def _build_merge_snapshot(reports: List[PerfReportModel]) -> Dict[str, Any]:
        """
        汇总合并快照: 计数/速率累加, 错误率按总量重算, 延迟类按请求数加权均值。

        :param reports: 报告实例(须同场景, 校验在 _validate_reports)
        :return: {"scene_name", "report_codes", "merged", "api_merged", "warnings"}
        """
        report_count = len(reports)
        total_requests = sum(report.total_requests or 0 for report in reports)
        fail_requests = sum(report.fail_requests or 0 for report in reports)
        success_requests = sum(report.success_requests or 0 for report in reports)
        merged: Dict[str, Any] = {
            "report_count": report_count,
            "total_requests": total_requests,
            "success_requests": success_requests,
            "fail_requests": fail_requests,
            "error_rate": PerfComparisonService._ratio_pct(numerator=fail_requests, denominator=total_requests),
            "rps": PerfComparisonService._round(sum(report.rps or 0 for report in reports)),
            "success_rps": PerfComparisonService._round(sum(report.success_rps or 0 for report in reports)),
            "min_rt": min((report.min_rt or 0) for report in reports),
            "max_rt": max((report.max_rt or 0) for report in reports),
            "sent_kb_s": PerfComparisonService._round(sum(report.sent_kb_s or 0 for report in reports)),
            "received_kb_s": PerfComparisonService._round(sum(report.received_kb_s or 0 for report in reports)),
            "duration_seconds": max((report.duration_seconds or 0) for report in reports),
        }
        # 延迟类按请求数加权(权重为零的报告不参与权重分母, 汇总仍给出该份的绝对值信息)
        for field in MERGE_WEIGHTED_FIELDS:
            merged[field] = PerfComparisonService._weighted_avg(
                pairs=[(getattr(report, field) or 0, report.total_requests or 0) for report in reports])

        warnings: List[str] = [
            "延迟类指标为各报告按请求数加权的均值, 非样本级真分位, 结论精度低于单报告分位",
        ]
        if any((report.total_requests or 0) < 1 for report in reports):
            warnings.append("存在无有效请求的报告, 加权结果仅由其余报告贡献")

        return {
            "scene_name": next((report.scene_name for report in reports if report.scene_name), None),
            "report_codes": [report.report_code for report in reports],
            "merged": merged,
            "api_merged": PerfComparisonService._merge_api_aggregations(reports),
            "warnings": warnings,
        }

    @staticmethod
    def _merge_api_aggregations(reports: List[PerfReportModel]) -> List[Dict[str, Any]]:
        """
        按接口标识聚合各报告的接口维度数据(同 api_code 的定义在引用校验下视为一致)。

        :param reports: 报告实例
        :return: 聚合后的接口行列表(按api_code排序)
        """
        merged_index: Dict[str, Dict[str, Any]] = {}
        for report in reports:
            for item in report.api_aggregations or []:
                if not isinstance(item, dict) or not item.get("api_code"):
                    continue
                api_code = str(item["api_code"])
                row = merged_index.setdefault(api_code, {
                    "api_code": api_code,
                    "api_name": item.get("api_name"),
                    "method": item.get("method"),
                    "total_requests": 0, "failed_requests": 0,
                    "error_rate": 0.0, "rps": 0.0,
                    "low_confidence": False,
                    **{field: 0.0 for field in MERGE_API_METRIC_FIELDS},
                })
                requests = item.get("total_requests") or 0
                row["total_requests"] += requests
                row["failed_requests"] += item.get("failed_requests") or 0
                row["rps"] = PerfComparisonService._round(row["rps"] + (item.get("rps") or 0))
                row["low_confidence"] = row["low_confidence"] or bool(item.get("low_confidence"))
                for field in MERGE_API_METRIC_FIELDS:
                    row[f"_{field}_w"] = row.get(f"_{field}_w", 0.0) + (item.get(field) or 0) * requests

        for row in merged_index.values():
            row["error_rate"] = PerfComparisonService._ratio_pct(
                numerator=row["failed_requests"], denominator=row["total_requests"])
            for field in MERGE_API_METRIC_FIELDS:
                # 各报告贡献已乘过权重(_*_w), 归一化只做除法; 复用_weighted_avg会二次乘权重,
                # 分母<=0时返回None与_weighted_avg权重和为0的口径一致
                weighted_sum = row.pop(f"_{field}_w", 0.0)
                row[field] = PerfComparisonService._round(
                    weighted_sum / row["total_requests"]) if row["total_requests"] > 0 else None
        return sorted(merged_index.values(), key=lambda row: row["api_code"])

    # ============================ 数值工具 ============================

    @staticmethod
    def _pct_delta(current: Optional[float], baseline: Optional[float]) -> Optional[float]:
        """
        相对基准的百分比变化(基准为0时无参照系返回None)。

        :param current: 当前值
        :param baseline: 基准值
        :return: 变化百分比(正=升高, 负=下降), 基准为0时None
        """
        if not baseline:
            return None
        return PerfComparisonService._round(((current or 0) - baseline) / baseline * 100)

    @staticmethod
    def _weighted_avg(pairs: List[Any]) -> Optional[float]:
        """
        加权均值(权重和为0时返回None, 由调用方决定口径回退)。

        :param pairs: (值, 权重)列表
        :return: 加权均值或None
        """
        weight_sum = sum(weight or 0 for _, weight in pairs)
        if weight_sum <= 0:
            return None
        return PerfComparisonService._round(
            sum((value or 0) * (weight or 0) for value, weight in pairs) / weight_sum)

    @staticmethod
    def _ratio_pct(*, numerator: float, denominator: float) -> float:
        """比率百分数(分母为0返回0.0)。"""
        if not denominator:
            return 0.0
        return PerfComparisonService._round(numerator / denominator * 100)

    @staticmethod
    def _round(value: Optional[float]) -> float:
        """统一保留两位小数(None归零)。"""
        return round(float(value or 0), 2)

