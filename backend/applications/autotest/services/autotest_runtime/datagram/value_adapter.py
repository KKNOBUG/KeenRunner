# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : value_adapter.py
@DateTime: 2026/9/4
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict

# 特殊值常量：用户在数据源单元格中编写的占位文本
DATASET_EMPTY_TEXT = "#空值"
DATASET_NULL_VALUE = "#空的"
DATASET_SPACE_VALUE = "#空格"

# 注入后代表三个空格的固定常量
DATASET_SPACE_EXPANDED = "   "

__all__ = [
    "DATASET_EMPTY_TEXT",
    "DATASET_NULL_VALUE",
    "DATASET_SPACE_VALUE",
    "DATASET_SPACE_EXPANDED",
    "DatasetValueAdapter",
    "expand_dataset_special_value",
    "expand_dataset_general_value",
]


def expand_dataset_special_value(value: Any) -> Any:
    """
    数据源(AutoTestDataSourceModel.dataset)命中字段对应的注入数据为特殊值常量占位时替换为具体值。

    :param value: 注入数据
    :return: #空值=空串、#空的=None、#空格=三空格
    """
    if isinstance(value, str):
        crt_value = (value or "").strip()
        if crt_value == DATASET_EMPTY_TEXT:
            return ""
        if crt_value == DATASET_NULL_VALUE:
            return None
        if crt_value == DATASET_SPACE_VALUE:
            return DATASET_SPACE_EXPANDED
    return value


def expand_dataset_general_value(value: Any) -> str:
    """
    数据源(AutoTestDataSourceModel.dataset)命中字段对应的注入数据转为协议文本；

    :param value: 注入数据
    :return: 协议文本
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class DatasetValueAdapter:
    """数据源(AutoTestDataSourceModel.dataset)命中字段对应的注入数据的类型适配器。"""

    ADAPT_REJECTED = object()

    @staticmethod
    def _accept_raw(raw_value: str, target_value: Any) -> Any:
        """
        原样接受线路。

        适用：str字段；null字段与查询哨兵(类型参考不可用，由用户负责，为后续按dataset文本做类型恢复预留扩展口)。
        """
        return raw_value

    @staticmethod
    def _reject(raw_value: str, target_value: Any) -> Any:
        """不采纳线路：文本无法贴合目标类型(或参考类型未知)，跳过注入保留报文原值。"""
        return DatasetValueAdapter.ADAPT_REJECTED

    @staticmethod
    def _route_bool(raw_value: str, target_value: Any) -> Any:
        """布尔字段线路：仅接受true/false文本(大小写不敏感)，其余不采纳。"""
        lowered = raw_value.strip().lower()
        return {"true": True, "false": False}.get(lowered, DatasetValueAdapter.ADAPT_REJECTED)

    @staticmethod
    def _convert_float(raw_value: str) -> Any:
        """浮点文本转换：inf/nan文本按不采纳处理(转出inf会破坏后续orjson序列化)。"""
        try:
            number = float(raw_value.strip())
        except (ValueError, OverflowError):
            return DatasetValueAdapter.ADAPT_REJECTED
        return number if math.isfinite(number) else DatasetValueAdapter.ADAPT_REJECTED

    @staticmethod
    def _route_int(raw_value: str, target_value: Any) -> Any:
        """整数字段线路：接受整数/浮点文本，浮点文本转float保留数值语义，其余不采纳。"""
        try:
            return int(raw_value.strip())
        except ValueError:
            return DatasetValueAdapter._convert_float(raw_value)

    @staticmethod
    def _route_float(raw_value: str, target_value: Any) -> Any:
        """浮点字段线路：仅接受整数/浮点文本。"""
        return DatasetValueAdapter._convert_float(raw_value)

    _routes: Dict[type, Callable[[str, Any], Any]] = {
        type(None): _accept_raw,
        str: _accept_raw,
        bool: _route_bool,
        int: _route_int,
        float: _route_float,
        list: _reject,
        dict: _reject,
        object: _accept_raw,
    }

    @classmethod
    def adapt(cls, raw_value: Any, target_value: Any) -> Any:
        """
        数据源(AutoTestDataSourceModel.dataset)命中字段对应的注入数据按报文原字段类型适配入口。

        :param raw_value: 注入数据
        :param target_value: 目标数据
        :return:
        """
        if not isinstance(raw_value, str):
            return cls.ADAPT_REJECTED

        # 特殊值常量命中时直接短路返回；未命中返回原对象，继续贴合线路
        expanded = expand_dataset_special_value(raw_value)
        if expanded is not raw_value:
            return expanded
        return cls._routes.get(type(target_value), cls._reject)(raw_value, target_value)
