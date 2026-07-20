# -*- coding: utf-8 -*-
"""
断言操作符比较：类型感知相等/大小比较及 AutoTestAssertionOperation 分发。
"""
from __future__ import annotations

import operator
from typing import Any, Callable, Dict

from backend.enums.autotest_enum import AutoTestAssertionOperation


class AssertionCompare:
    """对实际值与期望值按断言操作符执行比较。"""

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        """
        将值标准化为便于比较的类型：数字字符串转 int 或 float, true 或 false 转 bool, 其余原样返回

        :param value: 任意值
        :return: 标准化后的值, 或原值
        """
        if value is None:
            return None
        if isinstance(value, (int, float, bool)):
            return value
        if isinstance(value, str):
            if value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
                return int(value)
            try:
                if '.' in value:
                    return float(value)
            except ValueError:
                pass
            if value.lower() == 'true':
                return True
            if value.lower() == 'false':
                return False
        return value

    @classmethod
    def _type_aware_equals(cls, actual: Any, expected: Any) -> bool:
        """
        类型感知的相等比较：先直接比较, 若不等则对两值做 _normalize_value 后再比较

        :param actual: 实际值
        :param expected: 期望值
        :return: 是否相等
        """
        # 直接比较
        if actual == expected:
            return True
        # 标准化后比较
        norm_actual = cls._normalize_value(actual)
        norm_expected = cls._normalize_value(expected)
        return norm_actual == norm_expected

    @classmethod
    def _type_aware_compare(
            cls,
            actual: Any,
            expected: Any,
            comparator: Callable[[Any, Any], bool],
    ) -> bool:
        """
        类型感知的大小比较：先标准化再比较；若标准化后均为数值则用数值比较, 否则用字符串比较

        :param actual: 实际值
        :param expected: 期望值
        :param comparator: 二元谓词(左, 右) -> bool, 例如 operator.gt
        :return: 比较结果
        """
        norm_actual = cls._normalize_value(actual)
        norm_expected = cls._normalize_value(expected)
        # 确保都是数值类型才能进行大小比较
        if isinstance(norm_actual, (int, float)) and isinstance(norm_expected, (int, float)):
            return comparator(norm_actual, norm_expected)
        # 如果不是数值, 尝试字符串比较
        return comparator(str(actual), str(expected))

    @classmethod
    def compare_assertion(cls, actual: Any, operation: str, expected: Any) -> bool:
        """
        根据操作符对实际值与期望值做断言比较；operation须为AutoTestAssertionOperation枚举值。

        :param actual: 实际值
        :param operation: 操作符(与AutoTestAssertionOperation一致)
        :param expected: 期望值(部分操作符可忽略)
        :return: 断言是否通过
        :raises ValueError: 不支持的操作符或比较过程异常
        """
        try:
            op = AutoTestAssertionOperation(operation)
        except ValueError as exc:
            raise ValueError(f"操作符[{operation!r}]不被支持") from exc

        def _length_equal(a: Any, e: Any) -> bool:
            """比较实际值字符串长度是否等于期望长度。"""
            nb = cls._normalize_value(e)
            return nb is not None and len(str(a)) == int(nb)

        handlers: Dict[AutoTestAssertionOperation, Callable[[Any, Any], bool]] = {
            AutoTestAssertionOperation.EQUAL: cls._type_aware_equals,
            AutoTestAssertionOperation.NOT_EQUAL: lambda a, e: not cls._type_aware_equals(a, e),
            AutoTestAssertionOperation.GREATER_THAN: lambda a, e: cls._type_aware_compare(a, e, operator.gt),
            AutoTestAssertionOperation.GREATER_OR_EQUAL: lambda a, e: cls._type_aware_compare(a, e, operator.ge),
            AutoTestAssertionOperation.LESS_THAN: lambda a, e: cls._type_aware_compare(a, e, operator.lt),
            AutoTestAssertionOperation.LESS_OR_EQUAL: lambda a, e: cls._type_aware_compare(a, e, operator.le),
            AutoTestAssertionOperation.LENGTH_EQUAL: _length_equal,
            AutoTestAssertionOperation.CONTAINS: lambda a, e: str(e) in str(a),
            AutoTestAssertionOperation.NOT_CONTAINS: lambda a, e: str(e) not in str(a),
            AutoTestAssertionOperation.STARTS_WITH: lambda a, e: str(a).startswith(str(e)),
            AutoTestAssertionOperation.ENDS_WITH: lambda a, e: str(a).endswith(str(e)),
            AutoTestAssertionOperation.NOT_EMPTY: lambda a, _e: a is not None and a != "",
            AutoTestAssertionOperation.IS_EMPTY: lambda a, _e: a is None or a == "",
        }
        comparator = handlers.get(op)
        if comparator is None:
            raise ValueError(f"操作符[{operation!r}]未绑定实现")
        try:
            return comparator(actual, expected)
        except Exception as e:
            raise ValueError(f"比较失败: 实际值[{actual}] 操作符[{operation}] 预期值[{expected}] {e}") from e
