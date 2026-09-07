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
DATASET_EMPTY_TEXT = "#空字符串"
DATASET_NULL_VALUE = "#NULL"
DATASET_SPACE_VALUE = "#单个空格"

# 注入后代表单个空格的固定常量
DATASET_SPACE_EXPANDED = " "

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
    :return: #空字符串=空串、#NULL=None(大小写不敏感)、#单个空格=单个空格
    """
    if isinstance(value, str):
        crt_value = (value or "").strip()
        if crt_value == DATASET_EMPTY_TEXT:
            return ""
        if crt_value.upper() == DATASET_NULL_VALUE:
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

    @staticmethod
    def _accept_raw(raw_value: str, target_value: Any) -> Any:
        """
        原样接受线路。

        适用：str字段；null字段与查询哨兵(类型参考不可用，由用户负责，为后续按dataset文本做类型恢复预留扩展口)；
        未注册类型兜底(容器值等无贴合语义场景，由用户负责)。
        """
        return raw_value

    @staticmethod
    def _route_bool(raw_value: str, target_value: Any) -> Any:
        """布尔字段线路：true/false文本(大小写不敏感)转布尔，其余原样接受(由用户负责)。"""
        converted = {"true": True, "false": False}.get(raw_value.strip().lower())
        return converted if converted is not None else raw_value

    @staticmethod
    def _convert_float(raw_value: str) -> Any:
        """浮点文本转换：可转float则返回数值；无法转换或inf/nan原样接受(转出inf会破坏orjson序列化)。"""
        try:
            number = float(raw_value.strip())
        except (ValueError, OverflowError):
            return raw_value
        return number if math.isfinite(number) else raw_value

    @staticmethod
    def _route_int(raw_value: str, target_value: Any) -> Any:
        """整数字段线路：整数文本转int、浮点文本转float(保留数值语义)，其余原样接受(由用户负责)。"""
        try:
            return int(raw_value.strip())
        except ValueError:
            return DatasetValueAdapter._convert_float(raw_value)

    @staticmethod
    def _route_float(raw_value: str, target_value: Any) -> Any:
        """浮点字段线路：整数/浮点文本转float，其余原样接受(由用户负责)。"""
        return DatasetValueAdapter._convert_float(raw_value)

    _routes: Dict[type, Callable[[str, Any], Any]] = {
        type(None): _accept_raw,
        str: _accept_raw,
        bool: _route_bool,
        int: _route_int,
        float: _route_float,
        list: _accept_raw,
        dict: _accept_raw,
        object: _accept_raw,
    }

    @classmethod
    def adapt(cls, raw_value: Any, target_value: Any) -> Any:
        """
        数据源(AutoTestDataSourceModel.dataset)命中字段对应的注入数据按报文原字段类型适配入口。

        :param raw_value: 注入数据
        :param target_value: 目标数据(报文原字段值，作为类型转换参考)
        :return: 类型转换后的值；无法转换时原样返回注入数据(由用户负责)
        """
        if not isinstance(raw_value, str):
            # 非字符串(遗留/异常数据)无贴合语义，原样接受(由用户负责)
            return raw_value

        # 特殊值常量命中时直接短路返回；未命中返回原对象，继续贴合线路
        expanded = expand_dataset_special_value(raw_value)
        if expanded is not raw_value:
            return expanded
        return cls._routes.get(type(target_value), cls._accept_raw)(raw_value, target_value)
