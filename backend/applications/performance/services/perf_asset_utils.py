# -*- coding: utf-8 -*-
"""
性能域跨资产共享的纯函数工具。

放置被多个资产层(接口/数据集/场景/任务)共同使用、且不访问数据库与网络的辅助函数:
避免同一份「模型字段归一」「副本命名」「非空列空值拦截」逻辑散落在各 crud 里各写一遍。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_asset_utils.py
@DateTime: 2026/9/16 11:10
"""
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.configure import LOGGER, PROJECT_CONFIG
from backend.core.exceptions import NotFoundException, ParameterException


# 副本名称标记(与功能任务「基础名+时间戳」同思路, 带标记便于用户在列表里认出这是副本)
COPY_NAME_MARKER = "-副本"
# 上一轮副本后缀: 微秒时间戳20位; 连续复制时先剥离, 名称不会链式变长
COPY_NAME_SUFFIX_PATTERN = re.compile(r"_\d{20}$")
# 微秒级时间戳: 唯一性由时间戳保证, 无需回库查重(查重式命名会在循环里发SQL)
COPY_NAME_TIME_FORMAT = "%Y%m%d%H%M%S%f"


def model_field_literal(instance: Any, field: str) -> Any:
    """
    读取模型字段值并把枚举归一为字面量, 供与 schema dump(mode="json") 结果做等价比较。

    :param instance: 模型实例
    :param field: 字段名
    :return: 字段值(枚举转字面量), 字段不存在时返回None
    """
    value = getattr(instance, field, None)
    return getattr(value, "value", value)


def build_copy_name(source_name: str, *, max_length: int = 255) -> str:
    """
    生成副本名称: 「基础名-副本_微秒时间戳」。

    时间戳后缀保证同应用下唯一(免查库), 且重复复制同一副本时先剥离上一轮后缀,
    名称恒为「源基础名-副本_最新时间戳」, 不会越复制越长。

    :param source_name: 源名称
    :param max_length: 名称列长度上限(用于截断基础名, 保证后缀不被截掉)
    :return: 副本名称
    """
    base_name: str = COPY_NAME_SUFFIX_PATTERN.sub("", source_name or "")
    if base_name.endswith(COPY_NAME_MARKER):
        base_name = base_name[: -len(COPY_NAME_MARKER)]
    marker: str = f"{COPY_NAME_MARKER}_{datetime.now().strftime(COPY_NAME_TIME_FORMAT)}"
    return f"{base_name[: max_length - len(marker)]}{marker}"


def _strip_none_keys(value: Any) -> Any:
    """
    递归剔除字典中取值为None的键(与 schema dump(exclude_none) 同口径)。

    :param value: 任意JSON结构值
    :return: 剔除空值键后的同构值
    """
    if isinstance(value, dict):
        return {key: _strip_none_keys(item) for key, item in value.items() if item is not None}
    if isinstance(value, (list, tuple)):
        return [_strip_none_keys(item) for item in value]
    return value


def canonical_value(value: Any) -> str:
    """
    任意定义值 → 可比对的规范JSON文本。

    同一份定义从前端表单、schema dump、数据库回查三个方向进来, 键序与「缺键 vs null」形态
    会不一致; 直接比 Python 对象会把未改动的保存误判为定义变更, 白白自增版本号并作废调试结论。

    :param value: 待比较的定义值(标量/字典/列表)
    :return: 键按字典序排列、无空值键的JSON文本
    """
    return json.dumps(_strip_none_keys(value), sort_keys=True, ensure_ascii=False, default=str)


def ensure_no_null_for_required_fields(model_cls: Any, update_dict: Dict[str, Any], action: str) -> None:
    """
    拦截对非空列显式提交 null。

    更新入口允许「提交 null 即清空」, 但清空只对可空列成立: 往非空列写 NULL 会一路带到 DB 层
    炸成约束错误, 用户拿到的报错定位不到字段。这里按模型元信息(null=False)提前判定并报出字段名。

    :param model_cls: Tortoise 模型类
    :param update_dict: 待写入的更新字典
    :param action: 动作描述(用于错误文案, 如 "更新压测接口")
    :return: None
    """
    fields_map: Dict[str, Any] = model_cls._meta.fields_map
    offenders: List[str] = sorted(
        name for name, value in update_dict.items()
        if value is None and name in fields_map and not fields_map[name].null
    )
    if offenders:
        error_message: str = f"{action}信息失败, 以下字段不允许提交空值: {offenders}"
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)


# ============================ 报告对比(基线可比性/对比页共用) ============================

# 报告标量对比维度: (字段名, 展示名); 口径与配置指纹一致(负载/断言/预热/熔断任一变化即不可比)
REPORT_COMPARE_SCALAR_FIELDS = (
    ("env_name", "施压环境"),
    ("env_config_name", "缺省APP配置"),
    ("target_host", "施压目标"),
    ("concurrent_users", "峰值并发"),
    ("target_rps", "目标RPS"),
    ("run_duration", "计划时长(s)"),
    ("assert_mode", "断言口径"),
    ("sample_ratio", "断言采样比(%)"),
    ("warmup_seconds", "预热剔除(s)"),
    ("error_rate_threshold", "熔断阈值(%)"),
)

# scene_items 项内对比维度: (键, 展示名); 与配置指纹的 items 摘要键保持同口径
SCENE_ITEM_COMPARE_FIELDS = (
    ("role", "角色"),
    ("weight", "权重"),
    ("transaction", "事务"),
    ("delay_mode", "思考时间模式"),
    ("delay_ms", "思考时间(ms)"),
)


def _diff_dataset_field(current_item: Dict[str, Any], baseline_item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    对比单个接口项的数据集差异(只比策略与场景数, 不展开场景内容)。

    :param current_item: 当前报告的接口项快照
    :param baseline_item: 基线报告的接口项快照
    :return: 差异列表(空列表=无差异)
    """
    current_ds: Dict[str, Any] = current_item.get("dataset") if isinstance(current_item.get("dataset"), dict) else {}
    baseline_ds: Dict[str, Any] = baseline_item.get("dataset") if isinstance(baseline_item.get("dataset"), dict) else {}
    diffs: List[Dict[str, Any]] = []
    if current_ds.get("strategy") != baseline_ds.get("strategy"):
        diffs.append({"field": "dataset_strategy", "label": "数据集策略",
                      "baseline": baseline_ds.get("strategy"), "current": current_ds.get("strategy")})
    current_scenes: int = len(current_ds.get("scenes") or [])
    baseline_scenes: int = len(baseline_ds.get("scenes") or [])
    if current_scenes != baseline_scenes:
        diffs.append({"field": "dataset_scenes", "label": "数据集场景数",
                      "baseline": baseline_scenes, "current": current_scenes})
    return diffs


def diff_report_pair(current: Any, baseline: Any) -> Dict[str, Any]:
    """
    对比两份压测报告的配置差异(纯函数: 只读模型属性, 不访问数据库)。

    设计§5.7: 指纹不一致时显式提示差异项而非禁止对比, 本函数给出差异明细供
    基线不可比原因(incomparable_reasons)与报告对比页(snapshot_diff)共用。

    :param current: 当前报告模型实例(PerfReportModel)
    :param baseline: 基线报告模型实例(PerfReportModel)
    :return: 差异明细字典, 形如:
        {"same_scene": true, "fingerprint_same": false,
         "field_diffs": [{"field": "concurrent_users", "label": "峰值并发",
                          "baseline": 50, "current": 100}],
         "item_diffs": [{"api_code": "xx", "api_name": "下单", "kind": "changed",
                         "fields": [{"field": "weight", "label": "权重",
                                     "baseline": 1, "current": 3}]}]}
    """
    field_diffs: List[Dict[str, Any]] = []
    for field, label in REPORT_COMPARE_SCALAR_FIELDS:
        current_value = model_field_literal(current, field)
        baseline_value = model_field_literal(baseline, field)
        if current_value != baseline_value:
            field_diffs.append({"field": field, "label": label,
                                "baseline": baseline_value, "current": current_value})

    current_items: Dict[str, Dict[str, Any]] = {
        str(item.get("api_code")): item
        for item in (current.scene_items_snapshot or []) if isinstance(item, dict) and item.get("api_code")
    }
    baseline_items: Dict[str, Dict[str, Any]] = {
        str(item.get("api_code")): item
        for item in (baseline.scene_items_snapshot or []) if isinstance(item, dict) and item.get("api_code")
    }
    item_diffs: List[Dict[str, Any]] = []
    for api_code in sorted(set(current_items) - set(baseline_items)):
        item = current_items[api_code]
        item_diffs.append({"api_code": api_code, "api_name": item.get("api_name"), "kind": "added", "fields": []})
    for api_code in sorted(set(baseline_items) - set(current_items)):
        item = baseline_items[api_code]
        item_diffs.append({"api_code": api_code, "api_name": item.get("api_name"), "kind": "removed", "fields": []})
    for api_code in sorted(set(current_items) & set(baseline_items)):
        current_item = current_items[api_code]
        baseline_item = baseline_items[api_code]
        # scene_items_snapshot 是 dict 列表, 直接取键值(model_field_literal 走 getattr 只适用模型实例)
        changed: List[Dict[str, Any]] = [
            {"field": key, "label": label,
             "baseline": baseline_item.get(key), "current": current_item.get(key)}
            for key, label in SCENE_ITEM_COMPARE_FIELDS
            if current_item.get(key) != baseline_item.get(key)
        ]
        if current_item.get("api_version") != baseline_item.get("api_version"):
            changed.append({"field": "api_version", "label": "接口版本",
                            "baseline": baseline_item.get("api_version"), "current": current_item.get("api_version")})
        changed.extend(_diff_dataset_field(current_item, baseline_item))
        if changed:
            item_diffs.append({"api_code": api_code, "api_name": current_item.get("api_name"),
                               "kind": "changed", "fields": changed})

    return {
        "same_scene": bool(current.scene_code) and current.scene_code == baseline.scene_code,
        "fingerprint_same": bool(current.config_fingerprint) and current.config_fingerprint == baseline.config_fingerprint,
        "field_diffs": field_diffs,
        "item_diffs": item_diffs,
    }


def summarize_report_diff(diffs: Dict[str, Any]) -> List[str]:
    """
    把结构化差异明细转成可读文本行(基线不可比原因列表的直接来源)。

    :param diffs: diff_report_pair 的返回值
    :return: 差异描述列表(空列表=完全可比)
    """
    lines: List[str] = []
    if not diffs.get("same_scene"):
        lines.append("两份报告不属于同一压测场景")
    for diff in diffs.get("field_diffs") or []:
        lines.append(f"{diff['label']}不一致: 基线[{diff['baseline']}] → 当前[{diff['current']}]")
    for diff in diffs.get("item_diffs") or []:
        display_name: str = str(diff.get("api_name") or diff.get("api_code") or "")
        if diff.get("kind") == "added":
            lines.append(f"当前报告新增接口项[{display_name}]")
        elif diff.get("kind") == "removed":
            lines.append(f"当前报告缺少基线中的接口项[{display_name}]")
        else:
            detail = "、".join(
                f"{field['label']} {field['baseline']}→{field['current']}" for field in diff.get("fields") or []
            )
            lines.append(f"接口项[{display_name}]配置变化: {detail}")
    return lines


# ==================== 报告产物(清单/下载共用) ====================

# 报告业务标识字符白名单: unique_identify 生成的「时间戳-UUIDHEX」形态, 拒绝路径分隔符/点号等危险字符
REPORT_CODE_PATTERN = re.compile(r"^[0-9A-Za-z_\-]+$")
# 产物文件名白名单: 引擎工作目录仅写场景快照/引擎日志/结果分片三类文件, 白名单外一律拒绝下载
REPORT_ARTIFACT_PATTERN = re.compile(r"^(scene\.json|locust\.log|result_\d+\.json)$")
# 产物类型中文标签(清单展示用; result_{pid}.json 单独前缀判定)
ARTIFACT_KIND_LABELS = {
    "scene.json": "场景快照",
    "locust.log": "引擎日志",
}
# 清单排序权重: 场景快照 > 引擎日志 > 结果分片
ARTIFACT_SORT_PRIORITY = {"scene.json": 0, "locust.log": 1}


def artifact_kind_label(name: str) -> str:
    """产物文件类型中文标签: 白名单精确项查表, result_{pid}.json 按前缀归为结果分片。"""
    if ARTIFACT_KIND_LABELS.get(name):
        return ARTIFACT_KIND_LABELS[name]
    if name.startswith("result_") and name.endswith(".json"):
        return "结果分片"
    return "未知"


def format_human_size(size_bytes: int) -> str:
    """字节数转人类可读体积文本(1024进制, 一位小数; 不足1KB直接展示字节数)。"""
    size = float(size_bytes or 0)
    if size < 1024:
        return f"{int(size)} B"
    for unit in ("KB", "MB", "GB"):
        size /= 1024
        if size < 1024:
            return f"{size:.1f} {unit}"
    return f"{size:.1f} TB"


def resolve_report_artifact_dir(report_code: str) -> str:
    """
    解析并校验报告产物目录: 报告标识白名单校验 -> 拼接路径 -> 防越界 -> 目录存在性。

    :param report_code: 报告业务标识
    :return: 产物目录绝对路径
    :raises ParameterException: 报告标识含非法字符
    :raises NotFoundException: 产物目录不存在(报告未产生引擎产物或已被清理)
    """
    code = str(report_code or "").strip()
    if not code or not REPORT_CODE_PATTERN.match(code):
        error_message: str = f"报告产物路径非法, 报告标识不允许包含路径分隔符等字符: [{code}]"
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)
    artifact_dir: str = os.path.normpath(os.path.join(PROJECT_CONFIG.OUTPUT_PERF_DIR, code))
    if not artifact_dir.startswith(os.path.normpath(PROJECT_CONFIG.OUTPUT_PERF_DIR)):
        raise NotFoundException(message="报告产物路径不被允许")
    if not os.path.isdir(artifact_dir):
        raise NotFoundException(message=f"报告产物目录不存在: [{code}](报告未执行到引擎拉起或产物已被清理)")
    return artifact_dir


def list_report_artifacts(report_code: str) -> List[Dict[str, Any]]:
    """
    列出报告产物目录内白名单文件清单(场景快照/引擎日志/结果分片)。

    :param report_code: 报告业务标识
    :return: 清单列表, 元素形如 {"name", "kind", "size", "size_human", "modified_time"}, 按场景快照/日志/分片排序
    :raises ParameterException: 报告标识含非法字符
    :raises NotFoundException: 产物目录不存在
    """
    artifact_dir: str = resolve_report_artifact_dir(report_code)
    artifacts: List[Dict[str, Any]] = []
    for entry in os.scandir(artifact_dir):
        if not entry.is_file() or not REPORT_ARTIFACT_PATTERN.match(entry.name):
            continue
        stat = entry.stat()
        modified_time = datetime.fromtimestamp(stat.st_mtime)
        artifacts.append({
            "name": entry.name,
            "kind": artifact_kind_label(entry.name),
            "size": stat.st_size,
            "size_human": format_human_size(stat.st_size),
            "modified_time": modified_time.strftime("%Y-%m-%d %H:%M:%S"),
            "_priority": ARTIFACT_SORT_PRIORITY.get(entry.name, 2),
        })
    artifacts.sort(key=lambda item: (item.pop("_priority"), item["name"]))
    return artifacts


def resolve_report_artifact_path(report_code: str, artifact_name: str) -> Optional[str]:
    """
    解析待下载产物文件的绝对路径: 文件名白名单校验 + 目录越界防护 + 存在性校验。

    :param report_code: 报告业务标识
    :param artifact_name: 产物文件名(白名单: scene.json/locust.log/result_{pid}.json)
    :return: 文件绝对路径
    :raises ParameterException: 文件名不在白名单或报告标识非法
    :raises NotFoundException: 产物目录或目标文件不存在
    """
    name = str(artifact_name or "").strip()
    if not REPORT_ARTIFACT_PATTERN.match(name):
        error_message = f"报告产物文件名不在允许范围: [{name}](仅支持场景快照/引擎日志/结果分片)"
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)
    artifact_dir: str = resolve_report_artifact_dir(report_code)
    artifact_path: str = os.path.normpath(os.path.join(artifact_dir, name))
    if not artifact_path.startswith(artifact_dir):
        raise NotFoundException(message="报告产物路径不被允许")
    if not os.path.isfile(artifact_path):
        raise NotFoundException(message=f"报告产物文件不存在: [{name}]")
    return artifact_path


# ==================== 报告导出(xlsx 组装纯函数) ====================

# 判定结果与统计对象中文口径(与前端 PerfReportDrawer 同一把尺子)
_TARGET_SCOPE_LABELS = {"global": "全局", "api": "接口", "transaction": "事务"}
_TARGET_METRIC_LABELS = {
    "rps": "RPS", "success_rps": "成功RPS", "total_requests": "总请求数", "avg_rt": "平均RT(ms)",
    "p90": "P90(ms)", "p95": "P95(ms)", "p99": "P99(ms)", "error_rate": "失败率(%)",
}
_OP_SYMBOLS = {"gt": ">", "ge": ">=", "lt": "<", "le": "<=", "eq": "="}
_STOPPED_REASON_LABELS = {
    "completed": "正常完成", "manual": "手动停止", "circuit_break": "熔断触发",
    "engine_error": "引擎异常", "timeout_kill": "超时强杀",
}


def _fmt_export_value(value: Any) -> Any:
    """导出单元格值归一: None转空串避免全列被 pandas 推断为文本; 其余原样。"""
    return "" if value is None else value


def _build_report_summary_rows(report: Any) -> List[List[Any]]:
    """报告概要 sheet 数据: 键值两列, 字段顺序与前端抽屉概要区一致。"""
    status = str(getattr(report.status, "value", report.status))
    stopped = str(getattr(report.stopped_reason, "value", report.stopped_reason)) if report.stopped_reason else ""
    pairs: List[tuple] = [
        ("报告编码", report.report_code), ("报告状态", status),
        ("结束原因", _STOPPED_REASON_LABELS.get(stopped, stopped)),
        ("压测场景", report.scene_name), ("施压模式", report.run_mode),
        ("有效并发(峰值)", report.concurrent_users), ("计划时长(秒)", report.run_duration),
        ("引擎进程数", report.process_count),
        ("施压环境", report.env_name), ("环境配置", report.env_config_name),
        ("目标地址", report.target_host),
        ("开始时间", report.started_time.strftime("%Y-%m-%d %H:%M:%S") if report.started_time else None),
        ("结束时间", report.finished_time.strftime("%Y-%m-%d %H:%M:%S") if report.finished_time else None),
        ("有效时长(秒)", report.duration_seconds), ("预热剔除(秒)", report.warmup_seconds),
        ("总请求数", report.total_requests), ("失败率(%)", report.error_rate),
        ("RPS", report.rps), ("成功RPS", report.success_rps),
        ("平均RT(ms)", report.avg_rt), ("P95(ms)", report.p95),
        ("P99(ms)", report.p99), ("标准差(ms)", report.std_dev),
        ("配置指纹", report.config_fingerprint),
        ("基线报告", report.baseline_report_code), ("批次标识", report.batch_code),
        ("执行人", report.created_user),
    ]
    # rps 模式报告额外展示目标吞吐(该列其余模式恒空, 不占无意义行)
    if report.target_rps is not None:
        pairs.append(("目标吞吐(RPS)", report.target_rps))
    return [[label, _fmt_export_value(value)] for label, value in pairs]


def _build_target_rows(report: Any) -> List[List[Any]]:
    """SLA 判定 sheet 数据: 与前端 targetColumns 列口径一致。"""
    rows: List[List[Any]] = []
    for item in report.target_result or []:
        rows.append([
            _TARGET_SCOPE_LABELS.get(str(item.get("scope")), item.get("scope")),
            _TARGET_METRIC_LABELS.get(str(item.get("target")), item.get("target")),
            item.get("api_ref") or "全局",
            "跳过" if item.get("skipped") else f"{_OP_SYMBOLS.get(str(item.get('op')), item.get('op'))} {item.get('expect')}",
            "-" if item.get("skipped") else _fmt_export_value(item.get("actual")),
            "跳过" if item.get("skipped") else ("达标" if item.get("passed") else "未达标"),
            "失败" if item.get("severity") == "fail" else ("告警" if item.get("severity") == "warn" else item.get("severity") or ""),
            item.get("reason") or ("样本量或时长不足, 跳过判定" if item.get("skipped") else ""),
        ])
    return rows


def _build_api_rows(report: Any) -> List[List[Any]]:
    """接口维度聚合 sheet 数据: 与前端 apiColumns 列口径一致。"""
    return [
        [
            item.get("api_name"), item.get("method"), item.get("total_requests"), item.get("failed_requests"),
            item.get("error_rate"), item.get("avg_rt"), item.get("p90"),
            item.get("p95"), item.get("p99"), item.get("rps"),
            "低" if item.get("low_confidence") else "正常",
        ]
        for item in report.api_aggregations or []
    ]


def _build_transaction_rows(report: Any) -> List[List[Any]]:
    """事务维度聚合 sheet 数据: 与前端 transactionColumns 列口径一致。"""
    return [
        [item.get("name"), item.get("rounds"), item.get("failed"), item.get("avg_rt"), item.get("p95"), item.get("business_tps")]
        for item in report.transaction_aggregations or []
    ]


def _build_error_rows(report: Any) -> List[List[Any]]:
    """错误归因 sheet 数据: 与前端 errorColumns 列口径一致。"""
    return [
        [item.get("api_name"), item.get("method"), item.get("error"), item.get("occurrences")]
        for item in report.error_breakdown or []
    ]


def _build_baseline_rows(report: Any) -> List[List[Any]]:
    """基线对比 sheet 数据: 未钉基线返回空列表(不生成该 sheet); 可比时输出三指标变化与退化判定。"""
    baseline_diff: Dict[str, Any] = report.baseline_diff or {}
    if not report.baseline_report_code and not baseline_diff:
        return []
    rows: List[List[Any]] = [["基线报告", report.baseline_report_code or ""]]
    if baseline_diff.get("comparable") is False:
        rows.append(["可比性", "不可比"])
        rows.append(["不可比原因", "；".join(baseline_diff.get("incomparable_reasons") or [])])
        return rows
    diff = baseline_diff.get("diff") or {}
    rows.append(["可比性", "可比"])
    rows.append(["P95变化(%)", _fmt_export_value(diff.get("p95"))])
    rows.append(["RPS变化(%)", _fmt_export_value(diff.get("qps"))])
    rows.append(["错误率变化(百分点)", _fmt_export_value(diff.get("error_rate"))])
    for violation in baseline_diff.get("violations") or []:
        rows.append(["退化判定", violation])
    return rows


def build_report_export_sheets(report: Any) -> List[Dict[str, Any]]:
    """
    组装报告导出 xlsx 的 sheet 数据(纯函数, 不碰文件IO): 前端抽屉各区块的一一镜像。

    :param report: 压测报告模型实例
    :return: sheet 列表, 元素形如 {"name": sheet名, "header": 表头列表, "rows": 数据行列表};
        未钉基线时不含「基线对比」sheet
    """
    sheets: List[Dict[str, Any]] = [
        {"name": "概要", "header": ["项目", "内容"], "rows": _build_report_summary_rows(report)},
        {
            "name": "SLA判定",
            "header": ["层级", "指标", "对象", "判定", "实际", "结论", "严重级", "说明"],
            "rows": _build_target_rows(report),
        },
        {
            "name": "接口维度",
            "header": ["接口", "方法", "请求数", "失败数", "失败率(%)", "平均RT(ms)", "P90(ms)", "P95(ms)", "P99(ms)", "RPS", "置信"],
            "rows": _build_api_rows(report),
        },
        {
            "name": "事务维度",
            "header": ["事务", "圈数", "失败圈", "平均RT(ms)", "P95(ms)", "业务TPS"],
            "rows": _build_transaction_rows(report),
        },
        {"name": "错误归因", "header": ["接口", "方法", "错误", "次数"], "rows": _build_error_rows(report)},
    ]
    baseline_rows = _build_baseline_rows(report)
    if baseline_rows:
        sheets.append({"name": "基线对比", "header": ["项目", "内容"], "rows": baseline_rows})
    return sheets
