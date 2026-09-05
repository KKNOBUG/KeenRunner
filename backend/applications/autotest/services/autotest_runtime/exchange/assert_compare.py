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
    def _is_leading_zero_digit_string(cls, value: str) -> bool:
        """
        判断是否为带前导零的整数字符串，如响应码：000000，此类值在相等/集合比较中应保留字符串形态。

        :param value: 待判断字符串
        :return: 是否为带前导零的整数字符串
        """
        if not value:
            return False
        if value.startswith("-") and len(value) > 1:
            body = value[1:]
            return body.isdigit() and len(body) > 1 and body.startswith("0")
        return value.isdigit() and len(value) > 1 and value.startswith("0")

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        """
        将值标准化为便于比较的类型：数字字符串转int/float，true/false/null文本转bool/None，前导零串保留原串。

        null文本归一用于数据源dataset字符串化存储后的兼容：期望值"null"与响应null字段可判定相等。

        :param value: 任意值
        :return: 标准化后的值或原值
        """
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            if cls._is_leading_zero_digit_string(value):
                return value
            if value.isdigit() or (value.startswith("-") and len(value) > 1 and value[1:].isdigit()):
                return int(value)
            try:
                if "." in value:
                    return float(value)
            except ValueError:
                pass
            lowered = value.lower()
            if lowered == "true":
                return True
            if lowered == "false":
                return False
            if lowered == "null":
                return None
        return value

    @classmethod
    def _coerce_number_for_ordering(cls, value: Any) -> Any:
        """
        大小比较专用数值化：允许带前导零的数字串按数值参与比较；无法转换则返回原值。

        :param value: 任意值
        :return: int/float 或原值
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return value
            if text.isdigit() or (text.startswith("-") and len(text) > 1 and text[1:].isdigit()):
                return int(text)
            try:
                if "." in text:
                    return float(text)
            except ValueError:
                pass
        return value

    @classmethod
    def _is_bool_vs_number(cls, left: Any, right: Any) -> bool:
        """
        判断是否一侧为bool、另一侧为非bool的数值（Python中True==1为真，断言中禁止此类宽松相等）。

        :param left: 左值
        :param right: 右值
        :return: 是否为bool与数值的交叉组合
        """
        left_is_bool = isinstance(left, bool)
        right_is_bool = isinstance(right, bool)
        left_is_number = isinstance(left, (int, float)) and not left_is_bool
        right_is_number = isinstance(right, (int, float)) and not right_is_bool
        return (left_is_bool and right_is_number) or (right_is_bool and left_is_number)

    @classmethod
    def _type_aware_equals(cls, actual: Any, expected: Any) -> bool:
        """
        类型感知的相等比较：先直接比较，不等则标准化后再比较，bool与数值一律视为不等。

        :param actual: 实际值
        :param expected: 期望值
        :return: 是否相等
        """
        if cls._is_bool_vs_number(actual, expected):
            return False
        if actual == expected:
            return True
        norm_actual = cls._normalize_value(actual)
        norm_expected = cls._normalize_value(expected)
        if cls._is_bool_vs_number(norm_actual, norm_expected):
            return False
        return norm_actual == norm_expected

    @classmethod
    def _type_aware_compare(
            cls,
            actual: Any,
            expected: Any,
            comparator: Callable[[Any, Any], bool],
    ) -> bool:
        """
        类型感知的大小比较：优先按数值比较（含前导零数字串），否则回落字符串比较。

        :param actual: 实际值
        :param expected: 期望值
        :param comparator: 二元谓词(左, 右) -> bool, 例如operator.gt
        :return: 比较结果
        """
        num_actual = cls._coerce_number_for_ordering(actual)
        num_expected = cls._coerce_number_for_ordering(expected)
        if (
                isinstance(num_actual, (int, float))
                and not isinstance(num_actual, bool)
                and isinstance(num_expected, (int, float))
                and not isinstance(num_expected, bool)
        ):
            return comparator(num_actual, num_expected)
        return comparator(str(actual), str(expected))

    @classmethod
    def _assertion_length_equal(cls, actual: Any, expected: Any) -> bool:
        """
        比较实际值长度是否等于期望长度，无__len__的类型取str长度。

        :param actual: 实际值
        :param expected: 期望长度
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
        比较数组长度是否等于期望值。仅list/tuple 视为数组；字符串、字典等返回 False。

        :param actual: 实际值
        :param expected: 期望长度（数字字符串会经_normalize_value转换）
        :return: 是否为数组且长度相等
        """
        if not isinstance(actual, (list, tuple)):
            return False
        nb = cls._normalize_value(expected)
        if nb is None:
            return False
        try:
            return len(actual) == int(nb)
        except (TypeError, ValueError):
            return False

    @classmethod
    def _assertion_is_empty(cls, actual: Any, expected: Any) -> bool:
        """
        判断实际值是否为空：None、空串、空容器均为空。

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
        解析集合字面量内部文本：统一逗号分割，去可选引号，再经标准化转类型。

        :param text: 去掉外层[]、{}或()后的内容
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
        将期望值规范为成员判断用的列表，支持原生容器及[]、{}、()包裹的字面量。

        :param expected: 用户给定的集合或可解析为集合的值
        :return: 元素列表
        """
        if expected is None:
            raise ValueError("集合期望值不允许为[None | Null]")
        if isinstance(expected, (list, tuple, set, frozenset)):
            return list(expected)
        if isinstance(expected, dict):
            raise ValueError("集合期望值不支持Dict，请使用List/Set或[]、{}、()字面量")
        if not isinstance(expected, str):
            raise ValueError(
                "集合期望值必须使用[]、{}或()包裹，例如[元素1, 元素2]、{元素1, 元素2}或(元素1, 元素2)"
            )

        text = expected.strip()
        if not text:
            raise ValueError("集合期望值不允许为空字符串")

        pairs = {"[": "]", "{": "}", "(": ")"}
        opener = text[0]
        closer = pairs.get(opener)
        if closer is None or len(text) < 2 or not text.endswith(closer):
            raise ValueError("集合期望值必须使用[]、{}或()包裹，例如[元素1, 元素2]、{元素1, 元素2}或(元素1, 元素2)")

        inner = text[1:-1]
        if opener == "[":
            try:
                parsed = json.loads(text)
            except (json.JSONDecodeError, TypeError, ValueError):
                parsed = None
            if isinstance(parsed, list):
                return parsed
            return cls._parse_set_literal(inner)

        if opener == "{":
            try:
                parsed = json.loads(text)
            except (json.JSONDecodeError, TypeError, ValueError):
                parsed = None
            if isinstance(parsed, dict):
                raise ValueError("集合期望值不支持JSON对象，请使用[元素1, 元素2]、{元素1, 元素2}或(元素1, 元素2)写法")
            return cls._parse_set_literal(inner)

        return cls._parse_set_literal(inner)

    @classmethod
    def _assertion_in_set(cls, actual: Any, expected: Any) -> bool:
        """
        判断实际值是否属于期望集合（类型感知相等）。

        :param actual: 实际值
        :param expected: 集合（list/set，或[]、{}、()字面量）
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
