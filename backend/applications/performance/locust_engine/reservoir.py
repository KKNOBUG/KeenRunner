# -*- coding: utf-8 -*-
"""
压测响应时间蓄水池与分位统计原语(引擎与后端管线共用, 不依赖locust, 禁止 import backend 主包)。

Locust 分位数取自响应时间直方图(键按2位有效数字分桶)且不提供标准差, warmup 剔除更是
必须依赖带时间戳的原始样本 —— 因此每个 locust 进程用蓄水池保留等概率原始样本
[(ts_ms, rt_ms, ok, name, txn)], test_stop 时随 result_{pid}.json 分片落盘,
由后端管线合并所有分片后计算 p50/p90/p95/p99/std_dev/min/max。

蓄水池算法(Algorithm R): 未满时直接追加, 超容量后以 n/seen 概率等概率替换已有槽位,
保证任意时刻池内样本是全量数据流的均匀随机样本(对 name 条件化后仍是该接口样本的均匀抽样,
故合并侧可同时产出全局与单接口分位数)。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : reservoir.py
@DateTime: 2026/9/16 10:30
"""
import random
from typing import Any, Dict, List, Sequence, Tuple

# 样本行列契约(与 result 分片 samples.columns 逐字一致; 管线合并按列名取数)
SAMPLE_COLUMNS: Tuple[str, ...] = ("ts", "rt", "ok", "name", "txn")
# ts/rt/ok 三列在样本行中的固定下标(热路径按位写入, 避免字典开销)
COLUMN_TS = 0
COLUMN_RT = 1
COLUMN_OK = 2
COLUMN_NAME = 3
COLUMN_TXN = 4


class Reservoir:
    """固定容量等概率采样蓄水池(gevent 协作式调度下单 greenlet 读写, 无需加锁)。"""

    def __init__(self, capacity: int) -> None:
        """
        初始化蓄水池。

        :param capacity: 容量硬上限(对齐 backend enums PERF_RESERVOIR_SIZE, 双侧同步维护)
        """
        self.capacity: int = capacity
        self.rows: List[List[Any]] = []
        self.seen: int = 0

    def record(self, ts_ms: int, rt_ms: float, ok: bool, name: str, txn: str = "") -> None:
        """
        记录一个样本; 超容量后等概率替换。

        :param ts_ms: 样本完成时刻(Unix毫秒, warmup 剔除依据)
        :param rt_ms: 响应耗时毫秒
        :param ok: 是否成功(传输层与业务断言双通过)
        :param name: 统计行名(如 "POST /api/users" 或 "transaction:下单链路")
        :param txn: 归属事务名(无归属留空串)
        :return: None
        """
        self.seen += 1
        if len(self.rows) < self.capacity:
            self.rows.append([ts_ms, rt_ms, 1 if ok else 0, name, txn])
            return
        slot = random.randint(0, self.seen - 1)
        if slot < self.capacity:
            self.rows[slot] = [ts_ms, rt_ms, 1 if ok else 0, name, txn]

    def to_payload(self) -> Dict[str, Any]:
        """
        序列化为分片载荷(samples 字段)。

        :return: 载荷字典, 结构:
            {"columns": ["ts", "rt", "ok", "name", "txn"], "rows": [[...]],
             "capacity": 20000, "seen": 123456}
            seen > len(rows) 表示经过等概率抽样, 管线据此在报告标注"分位基于采样"
        """
        return {
            "columns": list(SAMPLE_COLUMNS),
            "rows": self.rows,
            "capacity": self.capacity,
            "seen": self.seen,
        }


def compute_percentile(sorted_values: Sequence[float], ratio: float) -> float:
    """
    计算分位数(线性插值法, 与 numpy 默认口径一致)。

    :param sorted_values: 已升序排序的样本值
    :param ratio: 分位比率(0~1, 如 0.95)
    :return: 分位数值; 空样本返回 0
    """
    total = len(sorted_values)
    if total == 0:
        return 0
    if total == 1:
        return float(sorted_values[0])
    position = (total - 1) * ratio
    lower_index = int(position)
    upper_index = min(lower_index + 1, total - 1)
    weight = position - lower_index
    return float(sorted_values[lower_index]) * (1 - weight) + float(sorted_values[upper_index]) * weight


def compute_std_dev(values: Sequence[float]) -> float:
    """
    计算总体标准差(Locust 不提供该指标, 由蓄水池样本补齐)。

    :param values: 样本值(无需排序)
    :return: 标准差; 空样本返回 0
    """
    total = len(values)
    if total == 0:
        return 0
    mean = sum(values) / total
    return (sum((value - mean) ** 2 for value in values) / total) ** 0.5
