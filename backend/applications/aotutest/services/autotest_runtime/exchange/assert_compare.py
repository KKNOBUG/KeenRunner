# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : assert_compare.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

import json
import operator
from typing import Any, Callable, Dict, List

from backend.enums.autotest_enum import AutoTestAssertionOperation


class AssertionCompare:
    """对实际值与期望值根据断言操作符执行比较。"""

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        """
        将值标准化为便于比较的类型：数字字符串转int或float, true或false转bool, 其余原样返回。

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
        类型感知的相等比较：先直接比较, 若不等则对两值做_normalize_value后再比较。

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
        类型感知的大小比较：先标准化再比较；若标准化后均为数值则用数值比较, 否则用字符串比较。

        :param actual: 实际值
        :param expected: 期望值
        :param comparator: 二元谓词(左, 右) -> bool, 例如operator.gt
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
    def _assertion_length_equal(cls, actual: Any, expected: Any) -> bool:
        """
        比较实际值长度是否等于期望长度。

        有__len__的类型（list/dict/str/set/tuple）用len(actual)，无__len__的类型（int/float/bool）用len(str(actual))取字符长度，None返回False。

        :param actual: 实际值
        :param expected: 期望长度（数字字符串会经_normalize_value转换）
        :return: 长度是否相等
        """
        nb = cls._normalize_value(expected)
        if nb is None or actual is None:
            return False
        try:
            actual_len = len(actual)
        except TypeError:
            actual_len = len(str(actual))
        return actual_len == int(nb)

    @classmethod
    def _assertion_array_length_equal(cls, actual: Any, expected: Any) -> bool:
        """
        比较容器（数组/对象）元素个数是否等于期望长度；与「长度等于」区分，后者偏字符串长度。

        仅支持 list/tuple/set/frozenset/dict；字符串、标量、None 返回 False。

        :param actual: 实际值（数组或对象）
        :param expected: 期望长度（数字字符串会经_normalize_value转换）
        :return: 容器长度是否相等
        """
        nb = cls._normalize_value(expected)
        if nb is None or actual is None:
            return False
        if not isinstance(actual, (list, tuple, set, frozenset, dict)):
            return False
        try:
            return len(actual) == int(nb)
        except (TypeError, ValueError):
            return False

    @classmethod
    def _assertion_is_empty(cls, actual: Any, expected: Any) -> bool:
        """
        判断实际值是否为空。

        None、空字符串、空容器（list/dict/set/tuple长度为0）均为空，数值/布尔等为非空。

        :param actual: 实际值
        :param expected: 期望值（忽略）
        :return: 是否为空
        """
        del expected
        if actual is None:
            return True
        if isinstance(actual, str):
            return actual == ""
        if isinstance(actual, (list, dict, set, tuple)):
            return len(actual) == 0
        return False

    @classmethod
    def _assertion_not_empty(cls, actual: Any, expected: Any) -> bool:
        """
        判断实际值是否非空。

        :param actual: 实际值
        :param expected: 期望值（忽略）
        :return: 是否非空
        """
        del expected
        return not cls._assertion_is_empty(actual, None)

    @classmethod
    def _parse_set_literal(cls, text: str) -> List[Any]:
        """
        解析集合字面量内部文本：统一全角/半角逗号后分割，去掉可选首尾引号，再经_normalize_value转类型。

        :param text: 去掉外层[]或{}后的内容
        :return: 元素列表
        """
        elements: List[Any] = []
        for part in text.replace("，", ",").split(","):
            token = part.strip()
            if not token:
                continue
            if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
                token = token[1:-1]
            elements.append(cls._normalize_value(token))
        return elements

    @classmethod
    def _coerce_to_collection(cls, expected: Any) -> List[Any]:
        """
        将期望值规范为成员判断用的列表。

        支持list/tuple/set/frozenset、JSON数组字符串、{张三, 李四, 10086}字面量；
        其余标量视为单元素集合；dict与JSON对象拒绝。

        :param expected: 用户给定的集合或可解析为集合的值
        :return: 元素列表
        :raises ValueError: 期望值非法时
        """
        if expected is None:
            raise ValueError("集合期望值不允许为[None | Null]")
        if isinstance(expected, (list, tuple, set, frozenset)):
            return list(expected)
        if isinstance(expected, dict):
            raise ValueError("集合期望值不支持Dict，请使用List/Set或集合字面量")
        if not isinstance(expected, str):
            return [expected]

        text = expected.strip()
        if not text:
            raise ValueError("集合期望值不允许为空字符串")

        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
            except (json.JSONDecodeError, TypeError, ValueError):
                parsed = None
            if isinstance(parsed, list):
                return parsed
            return cls._parse_set_literal(text[1:-1])

        if text.startswith("{") and text.endswith("}"):
            try:
                parsed = json.loads(text)
            except (json.JSONDecodeError, TypeError, ValueError):
                parsed = None
            if isinstance(parsed, dict):
                raise ValueError("集合期望值不支持JSON对象，请使用[元素1, 元素2]或{元素1, 元素2}写法")
            return cls._parse_set_literal(text[1:-1])

        return [cls._normalize_value(text)]

    @classmethod
    def _assertion_in_set(cls, actual: Any, expected: Any) -> bool:
        """
        判断实际值是否属于期望集合（类型感知相等）。

        :param actual: 实际值
        :param expected: 集合（list/set/JSON数组/{张三, 李四, 10086}）
        :return: 是否属于集合
        """
        return any(cls._type_aware_equals(actual, item) for item in cls._coerce_to_collection(expected))

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
            raise ValueError(f"操作符[{operation!r}]不被允许") from exc

        handlers: Dict[AutoTestAssertionOperation, Callable[[Any, Any], bool]] = {
            AutoTestAssertionOperation.EQUAL: cls._type_aware_equals,
            AutoTestAssertionOperation.NOT_EQUAL: lambda a, e: not cls._type_aware_equals(a, e),
            AutoTestAssertionOperation.GREATER_THAN: lambda a, e: cls._type_aware_compare(a, e, operator.gt),
            AutoTestAssertionOperation.GREATER_OR_EQUAL: lambda a, e: cls._type_aware_compare(a, e, operator.ge),
            AutoTestAssertionOperation.LESS_THAN: lambda a, e: cls._type_aware_compare(a, e, operator.lt),
            AutoTestAssertionOperation.LESS_OR_EQUAL: lambda a, e: cls._type_aware_compare(a, e, operator.le),
            AutoTestAssertionOperation.LENGTH_EQUAL: cls._assertion_length_equal,
            AutoTestAssertionOperation.ARRAY_LENGTH_EQUAL: cls._assertion_array_length_equal,
            AutoTestAssertionOperation.CONTAINS: lambda a, e: str(e) in str(a),
            AutoTestAssertionOperation.NOT_CONTAINS: lambda a, e: str(e) not in str(a),
            AutoTestAssertionOperation.IN_SET: cls._assertion_in_set,
            AutoTestAssertionOperation.NOT_IN_SET: lambda a, e: not cls._assertion_in_set(a, e),
            AutoTestAssertionOperation.STARTS_WITH: lambda a, e: str(a).startswith(str(e)),
            AutoTestAssertionOperation.ENDS_WITH: lambda a, e: str(a).endswith(str(e)),
            AutoTestAssertionOperation.NOT_EMPTY: cls._assertion_not_empty,
            AutoTestAssertionOperation.IS_EMPTY: cls._assertion_is_empty,
        }
        comparator = handlers.get(op)
        if comparator is None:
            raise ValueError(f"操作符[{operation!r}]未绑定实现")
        try:
            return comparator(actual, expected)
        except Exception as e:
            raise ValueError(f"比较失败: 实际值[{actual}] 操作符[{operation}] 预期值[{expected}] {e}") from e
