# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_tool_service
@DateTime: 2026/1/17 12:20
"""
from __future__ import annotations

import ast
import json
import re
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Callable, Union
from xml.etree import ElementTree as ET

from jsonpath_ng import parse as jsonpath_parse

from backend.applications.aotutest.schemas.autotest_step_schema import AutoTestStepTreeUpdateItem
from backend.common.generate_utils import GenerateUtils


class AutoTestToolServiceImpl:
    """实现层：占位符解析、断言比较、GenerateUtils 调用等内部逻辑，仅供 AutoTestToolService 使用。"""

    @classmethod
    def key_value_list_to_dict(cls, items: List[Dict[str, Any]], *, skip_if_no_value: bool = False) -> Dict[str, Any]:
        """
        将 key/value 列表转为键值对字典，供变量列表或 HTTP 参数使用。

        :param items: 每项为含 key、value 的字典的列表。
        :param skip_if_no_value: 为 True 时仅当项中含 "value" 键才加入结果；为 False 时仅要求 "key"，value 可为 None。
        :return: 键值对字典；非列表入参返回空字典。
        """
        if not isinstance(items, list):
            return {}
        result: Dict[str, Any] = {}
        for item in items:
            if not isinstance(item, dict) or "key" not in item:
                continue
            if skip_if_no_value and "value" not in item:
                continue
            key: Optional[str] = item.get("key")
            if key:
                result[key] = item.get("value")
        return result

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        """
        将值标准化为便于比较的类型：数字字符串转 int/float，'true'/'false' 转 bool，其余原样返回。

        :param value: 任意值。
        :return: 标准化后的值，或原值。
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
        类型感知的相等比较：先直接比较，若不等则对两值做 _normalize_value 后再比较。

        :param actual: 实际值。
        :param expected: 期望值。
        :return: 是否相等。
        """
        # 直接比较
        if actual == expected:
            return True
        # 标准化后比较
        norm_actual = cls._normalize_value(actual)
        norm_expected = cls._normalize_value(expected)
        return norm_actual == norm_expected

    @classmethod
    def _type_aware_compare(cls, actual: Any, expected: Any, comparator) -> bool:
        """
        类型感知的大小比较：先标准化再比较；若标准化后均为数值则用数值比较，否则用字符串比较。

        :param actual: 实际值。
        :param expected: 期望值。
        :param comparator: 二元谓词 (a, b) -> bool，如 lambda x, y: x > y。
        :return: 比较结果。
        """
        norm_actual = cls._normalize_value(actual)
        norm_expected = cls._normalize_value(expected)
        # 确保都是数值类型才能进行大小比较
        if isinstance(norm_actual, (int, float)) and isinstance(norm_expected, (int, float)):
            return comparator(norm_actual, norm_expected)
        # 如果不是数值，尝试字符串比较
        return comparator(str(actual), str(expected))

    @classmethod
    def compare_assertion(cls, actual: Any, operation: str, expected: Any) -> bool:
        """
        根据操作符对实际值与期望值做断言比较，支持等于、不等于、大于、小于、包含、非空等。

        :param actual: 实际值。
        :param operation: 操作符名称（如 "等于"、"包含"、"非空"）。
        :param expected: 期望值（部分操作符可忽略）。
        :return: 断言是否通过。
        :raises ValueError: 不支持的操作符或比较过程异常。
        """
        op_map = {
            "等于": lambda a, b: cls._type_aware_equals(a, b),
            "不等于": lambda a, b: not cls._type_aware_equals(a, b),
            "大于": lambda a, b: cls._type_aware_compare(a, b, lambda x, y: x > y),
            "大于等于": lambda a, b: cls._type_aware_compare(a, b, lambda x, y: x >= y),
            "小于": lambda a, b: cls._type_aware_compare(a, b, lambda x, y: x < y),
            "小于等于": lambda a, b: cls._type_aware_compare(a, b, lambda x, y: x <= y),
            "长度等于": lambda a, b: (lambda nb: len(str(a)) == int(nb) if nb is not None else False)(cls._normalize_value(b)),
            "包含": lambda a, b: str(b) in str(a),
            "不包含": lambda a, b: str(b) not in str(a),
            "以...开始": lambda a, b: str(a).startswith(str(b)),
            "以...结束": lambda a, b: str(a).endswith(str(b)),
            "非空": lambda a, _: a is not None and a != "",
            "为空": lambda a, _: a is None or a == "",
        }
        comparator = op_map.get(operation)
        if comparator is None:
            raise ValueError(f"操作符[{operation}]不被支持")
        try:
            return comparator(actual, expected)
        except Exception as e:
            raise ValueError(f"实际值[{actual}] 操作符[{operation}] 期待值[{expected}]表达式执行错误: {str(e)}")

    @classmethod
    def resolve_json_path(cls, data: Any, expr: str) -> Any:
        """
        使用 JSONPath 表达式从 data 中取值，支持标准 JSONPath（如 $.data[0].id、$.list[*].name）。

        :param data: 待取值的对象（dict/list 或嵌套结构）。
        :param expr: 非空字符串，合法 JSONPath 表达式（如 $.a.b、$.data[0].id、$.items[*].id）。
        :return: 单匹配时返回该值，多匹配时返回值的列表。无匹配时抛出 ValueError。
        :raises ValueError: 表达式非法、路径无匹配或解析异常时。
        """
        expr = expr.strip()
        if not expr or not isinstance(expr, str):
            raise ValueError(f"JSONPath表达式[{expr!r}]必须是非空字符串")
        if not expr.startswith("$."):
            raise ValueError(f"JSONPath表达式[{expr!r}]必须以$.字符开头(示例: $.data.user.name)")
        if data is None:
            raise ValueError(f"JSONPath表达式[{expr!r}]数据源不允许为空")

        try:
            json_path_expr = jsonpath_parse(expr)
        except Exception as e:
            raise ValueError(f"JSONPath表达式[{expr!r}]解析失败, 错误描述: {e} (示例: '$.list[0].id', '$.list[*].name')") from e

        json_path_matches = json_path_expr.find(data)
        if not json_path_matches:
            raise ValueError(f"JSONPath表达式[{expr!r}]无匹配结果, 请检查表达式或数据源")

        values = [match.value for match in json_path_matches]
        return values[0] if len(values) == 1 else values

    @classmethod
    def _parse_funcname_funcargs(cls, func_string: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        从形如 "func_name(key1=val1, key2=val2)" 的字符串中解析出函数名与参数字典。

        注意：当前实现 **仅支持关键字参数**（即 `key=value` 形式），并使用 `ast.literal_eval` 解析字面量。
        不包含 `=` 的片段会被忽略（即位置参数不会被解析/传递）。

        :param func_string: 函数调用形式的字符串。
        :return: (函数名, 参数字典)，无法解析时返回 (None, None)。
        :raises ValueError: 参数值不是合法字面量或解析失败时。
        """
        if not isinstance(func_string, str):
            return None, None
        if not func_string.endswith(")") or func_string.find("(") == -1:
            return None, None
        func_name, func_args = func_string.split("(", 1)
        func_args: str = func_args.rstrip(")")
        args_dict: Dict[str, Any] = {}
        if func_args.strip():
            _args = func_args.split(",")
            for item in _args:
                # key, value = item.split("=")
                # args_dict[str(key).strip()] = eval(value)
                part = item.strip()
                if "=" not in part:
                    continue
                key, _, value_part = part.partition("=")
                key = str(key).strip()
                value_part = value_part.strip()
                try:
                    args_dict[key] = ast.literal_eval(value_part)
                except (ValueError, SyntaxError) as e:
                    raise ValueError(f"解析参数签名失败, 仅支持字面量(数字、字符串、布尔、None等), 非法参数: {key}={value_part!r}") from e
        return func_name.strip(), args_dict

    @classmethod
    def execute_func_string(cls, session_variables: List[Dict[str, Any]]):
        """
        对会话变量列表中 value 为 "func_name(...)" 形式的项，调用 GenerateUtils 中同名函数并用返回值替换 value。

        :param session_variables: 变量列表，每项为含 key、value、desc 的字典。
        :raises AttributeError: 函数不存在、参数不匹配或执行失败时。
        """
        if not isinstance(session_variables, list):
            return
        for item in session_variables:
            if not isinstance(item, dict) or "key" not in item or "value" not in item:
                continue
            key = item.get("key")
            func_string = item.get("value")
            if not key or not isinstance(func_string, str):
                continue
            try:
                func_name, func_args = cls._parse_funcname_funcargs(func_string)
            except ValueError as e:
                raise AttributeError(f"辅助函数[{func_string!r}]调用失败: {e}") from e
            if not func_name and not func_args:
                continue
            if not hasattr(GenerateUtils, func_name):
                raise AttributeError(f"辅助函数[{func_name}]调用失败, 未定义或不被允许调用")
            try:
                item["value"] = getattr(GenerateUtils(), func_name)(**func_args or {})
            except TypeError as e:
                raise AttributeError(f"辅助函数[{func_name}]调用失败, 参数签名或类型不匹配: {e}")
            except SyntaxError as e:
                raise AttributeError(f"辅助函数[{func_name}]调用失败, 语法解析失败或未定义: {e}")
            except Exception as e:
                raise AttributeError(f"辅助函数[{func_name}]调用失败, 在动态注入时引发异常: {e}")

    @classmethod
    def execute_func_string_single(cls, content: str) -> Any:
        """
        将 content 解析为 func_name(...) 并调用 GenerateUtils 中同名方法，返回结果。
        供 resolve_placeholders 在「含括号」占位符时调用。

        :param content: 如 "generate_uuid()"、"generate_string(length=2)"。
        :return: 函数返回值。
        :raises AttributeError: 非函数形式或函数不存在/执行失败。
        """
        try:
            func_name, func_args = cls._parse_funcname_funcargs(content)
        except ValueError as e:
            raise AttributeError(f"辅助函数[{content!r}]调用失败: {e}") from e
        if not func_name and not func_args:
            raise AttributeError(f"辅助函数[{content!r}]调用失败, 占位符不是有效的调用")
        if not hasattr(GenerateUtils, func_name):
            raise AttributeError(f"辅助函数[{func_name}]调用失败, 未定义或不被允许调用")
        try:
            execute_result = getattr(GenerateUtils(), func_name)(**(func_args or {}))
            return execute_result
        except TypeError as e:
            raise AttributeError(f"辅助函数[{func_name}]调用失败, 参数签名或类型不匹配: {e}")
        except SyntaxError as e:
            raise AttributeError(f"辅助函数[{func_name}]调用失败, 语法解析失败或未定义: {e}")
        except Exception as e:
            raise AttributeError(f"辅助函数[{func_name}]调用失败, 在动态注入时引发异常: {e}")

    # -------------------------------------------------------------------------
    # 占位符 ${...}：单变量/函数、多占位符拼接、全为数值时整式四则（AST 白名单，无 eval）。
    # 限制：花括号内不可含 `}`；整式仅数字与 + - * / ( )；bool 不参与算术；超长表达式跳过求值。
    # -------------------------------------------------------------------------

    _RE_PLACEHOLDER_SIMPLE = re.compile(r"\$\{([^}]+)\}")
    _RE_ARITHMETIC_ONLY = re.compile(r"^[\d+\-*/().\s]+$")
    # 合并后的算术串超过此长度则不做 ast.parse，避免异常输入消耗 CPU/内存（生产防护）。
    _MAX_ARITH_EXPR_CHARS = 8192

    @classmethod
    def _resolve_placeholder_inner_to_value(
            cls,
            inner: str,
            is_core_engine: bool,
            finished_variables: Optional[Any],
    ) -> Any:
        """
        解析单个 ${...} 花括号内的文本：含括号视为 GenerateUtils 函数，否则按变量名解析。

        :param inner: 占位符花括号内文本（如 \"a\" 或 \"generate_uuid()\"）。会进行 strip。
        :param is_core_engine: True 时 finished_variables 需提供 get_variable(name)。
        :param finished_variables: 核心引擎上下文或变量列表（List[Dict]，每项含 key/value）。
        :returns: 解析到的变量值或函数执行结果。
        :raises KeyError: 变量未定义（非核心引擎列表路径）。
        :raises AttributeError: 函数不存在或执行失败。
        :raises ValueError: inner 为空白时。
        """
        inner = inner.strip()
        if not inner:
            raise ValueError("占位符内容必须是非空字符串(含有括号是为GenerateUtils类成员, 否则按变量名称解析)")
        if "(" in inner and ")" in inner:
            return cls.execute_func_string_single(inner)
        if is_core_engine:
            return finished_variables.get_variable(inner)
        resolved = AutoTestToolService.get_value_from_list(finished_variables, inner)
        if resolved is None:
            raise KeyError(f"占位符内容必须是有效的引用: {inner!r}")
        return resolved

    @classmethod
    def _to_float_for_expression(cls, val: Any) -> Optional[float]:
        """
        判断解析结果是否可作为「整段算术表达式」中的一个操作数。

        返回 float 表示可参与 merged 后的 _safe_eval_arithmetic；
        返回 None 表示该占位符对应值应走「字符串拼接」语义（整串不会对合并结果做算术）。

        注意：bool 返回 None，避免 True/False 被当成 1.0/0.0 参与运算（与显式需求不符）。
        """
        if val is None:
            return None
        if isinstance(val, bool):
            return None
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            s = val.strip()
            if not s:
                return None
            try:
                return float(s)
            except ValueError:
                return None
        return None

    @classmethod
    def _float_to_expr_str(cls, f: float) -> str:
        """
        将 float 写成可嵌入算术表达式的数字字面量片段。

        整数结果不带 `.0`，避免 merged 中出现多余小数点影响阅读；非整数用 str(f) 保留精度。
        """
        if f.is_integer():
            return str(int(f))
        return str(f)

    @classmethod
    def _format_resolved_for_concat(cls, val: Any) -> str:
        """
        非「纯算术整式求值」路径下，将解析后的 Python 值转为字符串片段。

        dict/list 使用 JSON（便于日志与下游展示）；None 转为空串。
        """
        if val is None:
            return ""
        if isinstance(val, (dict, list)):
            return json.dumps(val, ensure_ascii=False)
        return str(val)

    @staticmethod
    def _format_arithmetic_result_str(result: Union[int, float]) -> str:
        """
        将 `_safe_eval_arithmetic` 的返回值格式化为对外字符串。

        :param result: 算术求值结果（int/float）。
        :returns: 字符串形式；若为形如 7.0 的 float，会输出 \"7\"。
        """
        if isinstance(result, float) and result.is_integer():
            return str(int(result))
        return str(result)

    @classmethod
    def _splice_placeholders(
            cls,
            template: str,
            slots: List[Tuple[re.Match[str], Optional[Any], Optional[str]]],
            value_to_str: Callable[[Any], str],
    ) -> str:
        """
        按占位符顺序拼接 template。slots 每项为 (match, value, fail_literal)：
        - fail_literal 非 None：解析失败，插入该原文（一般为 m.group(0)）；
        - fail_literal 为 None：解析成功，插入 value_to_str(value)（value 可为 None，如变量值为空）。

        :param template: 原始模板字符串。
        :param slots: 占位符匹配与解析结果列表。
        :param value_to_str: 将解析值格式化为字符串的函数。
        :returns: 拼接后的字符串。
        """
        pos = 0
        parts: List[str] = []
        for m, val, fail_literal in slots:
            parts.append(template[pos: m.start()])
            parts.append(fail_literal if fail_literal is not None else value_to_str(val))
            pos = m.end()
        parts.append(template[pos:])
        return "".join(parts)

    @classmethod
    def _build_numeric_merged_expression(
            cls,
            template: str,
            matches: List[re.Match[str]],
            numeric_operands: List[float],
    ) -> str:
        """
        将全部解析成功的占位符替换为数字字面量，保留两侧运算符与括号，生成可被 AST 解析的表达式字符串。

        :param template: 原始模板字符串。
        :param matches: 与 numeric_operands 一一对应的占位符 match 列表。
        :param numeric_operands: 每个占位符对应的数值（float）。
        :returns: 占位符替换为数字后的表达式字符串。
        """
        pos = 0
        parts: List[str] = []
        for m, nf in zip(matches, numeric_operands):
            parts.append(template[pos: m.start()])
            parts.append(cls._float_to_expr_str(nf))
            pos = m.end()
        parts.append(template[pos:])
        return "".join(parts)

    @classmethod
    def _safe_eval_arithmetic(cls, expr: str) -> Union[int, float]:
        """
        安全地计算“纯算术表达式”字符串的结果（四则运算 + 括号 + 一元正负号）。

        ## 设计目的
        `resolve_placeholders` 支持复杂表达式，例如：

        - `(${a} + 10) * ${fn()} / (${b} - 2)`

        当且仅当所有占位符都解析为数值，并且替换后的整串只包含允许的字符时，
        才会进入本函数进行求值。

        ## 安全模型（关键）
        绝不使用 Python 内置 `eval/exec`。本函数使用 `ast.parse(expr, mode="eval")`
        生成表达式语法树，并且 **只允许白名单节点**：

        - 数值字面量：`ast.Constant`（以及 Python 3.7 的 `ast.Num`）
        - 一元运算：`+x` / `-x` -> `ast.UnaryOp` + (`ast.UAdd` / `ast.USub`)
        - 二元运算：`x+y` `x-y` `x*y` `x/y` -> `ast.BinOp` + (`ast.Add/Sub/Mult/Div`)
        - 括号：在 AST 中体现为子树结构，不需要单独节点

        所有其它语法（名称 Name、属性 Attribute、调用 Call、下标 Subscript、幂运算 Pow 等）
        都会被 `unsupported syntax` 拒绝，从根源阻断代码注入。

        ## 行为约定
        - 输入为空串：抛 `ValueError`
        - 表达式过长（> `_MAX_ARITH_EXPR_CHARS`）：抛 `ValueError`（生产防护）
        - 除数为 0：抛 `ZeroDivisionError("除数不能为 0")`
        - 返回值：默认为 `float`；若结果是整数（如 `7.0`）则返回 `int(7)`

        :param expr: 形如 `"1 + 2*(3-4)"` 的算术表达式字符串（通常已通过 `_RE_ARITHMETIC_ONLY` 校验）。
        :return: 计算结果（`int` 或 `float`）。
        """
        expr = expr.strip()
        if not expr:
            raise ValueError("算术表达式内容为空")
        if len(expr) > cls._MAX_ARITH_EXPR_CHARS:
            raise ValueError("算术表达式过长, 拒绝运算")

        def eval_node(node: ast.expr) -> float:
            """
            递归求值 AST 子树。

            之所以把入参类型标为 `ast.expr` 而不是 `ast.AST`：
            - `tree.body`、`UnaryOp.operand`、`BinOp.left/right` 在 typeshed 中均为 `ast.expr`
            - 这样 IDE/类型检查器不会提示 “期望 AST 但实际为 expr” 的告警

            :param node: AST 表达式节点。
            :returns: 子表达式求值结果（float）。
            :raises ValueError: 节点类型或运算符不在白名单时。
            :raises ZeroDivisionError: 除数为 0 时。
            """
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    return float(node.value)
                raise ValueError("算术表达式中包含非法常量, 拒绝运算")
            if isinstance(node, ast.Num):  # Python 3.7 及更早
                return float(node.n)
            if isinstance(node, ast.UnaryOp):
                if isinstance(node.op, ast.USub):
                    return -eval_node(node.operand)
                if isinstance(node.op, ast.UAdd):
                    return +eval_node(node.operand)
                raise ValueError("算术表达式中包含不被支持的一元运算符, 拒绝运算")
            if isinstance(node, ast.BinOp):
                left = eval_node(node.left)
                right = eval_node(node.right)
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Mult):
                    return left * right
                if isinstance(node.op, ast.Div):
                    if right == 0:
                        raise ZeroDivisionError("除数不能为 0")
                    return left / right
                raise ValueError("算术表达式中包含不支持的二元运算符")
            raise ValueError("算术表达式包含不支持的语法结构")

        tree = ast.parse(expr, mode="eval")
        if not isinstance(tree, ast.Expression):
            raise ValueError("文本不是有效的算术表达式")
        raw = eval_node(tree.body)
        if isinstance(raw, float) and raw.is_integer():
            return int(raw)
        return raw

    @classmethod
    def _resolve_string_placeholders(
            cls,
            s: str,
            logger_object: Callable,
            is_core_engine: bool,
            finished_variables: Optional[Any],
    ) -> str:
        """
        解析 str 内所有 ${...}：先占位符求值；失败则保留原 ${...}；全成功则视情况整式算术或拼接。
        """
        if "${" not in s:
            return s
        matches = list(cls._RE_PLACEHOLDER_SIMPLE.finditer(s))
        if not matches:
            return s

        # 第三元 fail_literal：非 None 表示该占位符解析失败，应保留原文；None 表示成功（值可为 Python None）。
        slots: List[Tuple[re.Match[str], Optional[Any], Optional[str]]] = []
        for m in matches:
            inner = m.group(1).strip()
            if not inner:
                logger_object("【获取变量】占位符解析失败, 不允许引用空白符, 保留原值")
                slots.append((m, None, m.group(0)))
                continue
            try:
                val = cls._resolve_placeholder_inner_to_value(inner, is_core_engine, finished_variables)
                logger_object("【获取变量】占位符解析成功, ${" + inner + "}  <=>  " + str(val))
                slots.append((m, val, None))
            except KeyError:
                logger_object(f"【获取变量】占位符解析失败, 变量({inner})未定义, 保留原值")
                slots.append((m, None, m.group(0)))
            except Exception as e:
                logger_object(
                    f"【获取变量】占位符解析失败, 引用({inner})发生未知异常, 保留原值, 错误描述: {e}"
                )
                slots.append((m, None, m.group(0)))

        if any(fail is not None for _, _, fail in slots):
            return cls._splice_placeholders(s, slots, cls._format_resolved_for_concat)

        resolved_values = [v for _, v, f in slots]
        nums = [cls._to_float_for_expression(v) for v in resolved_values]

        if not all(n is not None for n in nums):
            return cls._splice_placeholders(s, slots, cls._format_resolved_for_concat)

        num_floats: List[float] = [float(n) for n in nums if n is not None]
        match_list = [m for m, _, _ in slots]
        merged = cls._build_numeric_merged_expression(s, match_list, num_floats)
        ms = merged.strip()
        if (
                ms
                and len(ms) <= cls._MAX_ARITH_EXPR_CHARS
                and cls._RE_ARITHMETIC_ONLY.fullmatch(ms)
        ):
            try:
                result = cls._safe_eval_arithmetic(ms)
                out = cls._format_arithmetic_result_str(result)
                logger_object(f"【变量运算】表达式求值: {ms} => {out}")
                return out
            except Exception as e:
                logger_object(f"【变量运算】表达式求值失败: {e}, 改为按字符串拼接")

        return cls._splice_placeholders(s, slots, cls._format_resolved_for_concat)

    @classmethod
    def resolve_placeholders(cls, value: Any, logger_object: Callable, is_core_engine: bool = False, finished_variables: Optional[Any] = None) -> Any:
        """
        递归解析 str / dict / list 中的 ${...} 占位符。

        【字符串】
        - 单占位符：变量或 GenerateUtils 函数（花括号内同时含括号时按函数处理）。
        - 多占位符：见类注释「实现步骤」；支持如 (${a}+10)*${b}/${c} 等（全部占位符解析成功且
          值均可视为数字时，对合并后的表达式安全求值）。

        【字典】递归每个 value（key 不替换，与历史行为一致）。

        【列表】若元素为含 key/value 的变量项 dict，只解析 value 字段；否则递归元素。

        【其它类型】原样返回。

        解析失败：对应占位符保留原文；外层异常时记录日志并返回原 value。

        :param value: 待解析对象。
        :param logger_object: 日志回调，签名为 (str) -> None。
        :param is_core_engine: True 时 finished_variables 提供 get_variable。
        :param finished_variables: 核心引擎上下文或变量列表，含义同 _resolve_placeholder_inner_to_value。
        :return: 结构不变，占位符按规则替换后的深拷贝式结果（dict/list 新建容器）。
        """
        try:
            if isinstance(value, str):
                return cls._resolve_string_placeholders(
                    value, logger_object, is_core_engine, finished_variables
                )
            if isinstance(value, dict):
                try:
                    return {
                        k: cls.resolve_placeholders(
                            value=v,
                            logger_object=logger_object,
                            is_core_engine=is_core_engine,
                            finished_variables=finished_variables
                        )
                        for k, v in value.items()
                    }
                except Exception as e:
                    logger_object(f"【获取变量】解析字典中的占位符时发生错误, 键: {list(value.keys())}, 错误: {e}")
                    return value
            if isinstance(value, list):
                # 处理列表格式的变量（每个元素包含key、value、desc）
                result = []
                for item in value:
                    if isinstance(item, dict) and "key" in item and "value" in item:
                        # 列表格式的变量项，只解析value字段
                        resolved_item = dict(item)
                        resolved_item["value"] = cls.resolve_placeholders(
                            value=item.get("value"),
                            logger_object=logger_object,
                            is_core_engine=is_core_engine,
                            finished_variables=finished_variables
                        )
                        result.append(resolved_item)
                    else:
                        # 普通列表项，递归解析
                        result.append(
                            cls.resolve_placeholders(
                                value=item,
                                logger_object=logger_object,
                                is_core_engine=is_core_engine,
                                finished_variables=finished_variables
                            )
                        )
                return result
            return value
        except Exception as e:
            logger_object(
                f"【获取变量】占位符解析过程中发生未知异常, 保留原值, "
                f"错误类型: {type(e).__name__}, "
                f"错误描述: {e}"
            )
            return value


class AutoTestToolService:
    """服务层：对外稳定 API；内部实现见 `AutoTestToolServiceImpl`。"""

    @classmethod
    def list_to_dict(cls, variable_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        将 key/value/desc 列表转为 name -> value 字典，供 **Python 代码命名空间** 使用。

        与 convert_list_to_dict_for_http 的区别：本函数仅保留含 "value" 键的项（skip_if_no_value=True），
        无 value 的项不进入结果，避免在 exec 命名空间中注入 key->None 导致歧义或异常。
        使用处：StepExecutionContext.clone_state()，将 defined_variables / session_variables 转为字典后
        作为 run_python_code(..., namespace=...) 的命名空间。

        :param variable_list: 变量列表，每项为含 key、value 的字典。
        :return: 键为变量名、值为变量值的字典。
        """
        variable_list: List[Dict[str, Any]] = variable_list if isinstance(variable_list, list) else []
        return AutoTestToolServiceImpl.key_value_list_to_dict(items=variable_list, skip_if_no_value=True)

    @classmethod
    def convert_list_to_dict_for_http(cls, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        将 key/value/desc 列表转为 key -> value 字典，供 **HTTP 请求头/参数/表单** 使用。

        与 list_to_dict 的区别：本函数不要求项必有 "value"（skip_if_no_value=False），只要有 "key" 即加入结果，
        value 可为 None，以支持 HTTP 中合法的空值（如空 header、未填表单字段）。
        使用处：HttpStepExecutor 中将 request_header、request_params、form_data、urlencoded、form_files
        等列表转为字典后传给 httpx 发请求。

        :param data: 每项含 key、value 的列表。
        :return: 键值对字典；非列表入参返回空字典。
        """
        return AutoTestToolServiceImpl.key_value_list_to_dict(data if isinstance(data, list) else [], skip_if_no_value=False)

    @staticmethod
    def get_value_from_list(variable_list: List[Dict[str, Any]], name: str) -> Any:
        """
        从 key/value/desc 列表中取 key 为 name 的项的 value。

        :param variable_list: 变量列表，每项为含 key、value 的字典。
        :param name: 要查找的 key 名。
        :return: 对应的 value，未找到返回 None。
        """
        if not isinstance(variable_list, list):
            return None
        for item in variable_list:
            if isinstance(item, dict) and item.get("key") == name:
                return item.get("value")
        return None

    @classmethod
    def format_step_error_message(
            cls,
            step: Dict[str, Any],
            exception: Exception,
            is_child_step: bool = False,
    ) -> str:
        """
        格式化步骤执行失败信息，供步骤引擎中各类执行器统一使用。

        :param step: 步骤数据字典，含 case_id、step_id、step_no、step_code、step_name、step_type 等。
        :param exception: 异常对象；错误回溯使用 traceback.format_exc()，在 except 块内调用时即为该异常的堆栈。
        :param is_child_step: 是否为子步骤（True=子步骤，False=根步骤）。
        :return: 格式化后的错误字符串。
        """
        message: str = "【子步骤】" if is_child_step else "【根步骤】"
        case_id = step.get("case_id")
        step_id = step.get("step_id")
        step_no = step.get("step_no")
        step_code = step.get("step_code")
        step_name = step.get("step_name")
        step_type = step.get("step_type")
        return (
            f"{message}执行失败: \n"
            f"用例ID: {case_id}, \n"
            f"步骤ID: {step_id}, \n"
            f"步骤序号: {step_no}, \n"
            f"步骤标识: {step_code}, \n"
            f"步骤名称: {step_name}, \n"
            f"步骤类型: {step_type}, \n"
            f"错误描述: {exception}, \n"
            f"错误类型: {type(exception).__name__}, \n"
            f"错误时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, \n"
            f"错误回溯: {traceback.format_exc()}\n"
        )

    @classmethod
    def compare_assertion(cls, actual: Any, operation: str, expected: Any) -> bool:
        """
        根据操作符对实际值与期望值做断言比较（实现见 AutoTestToolServiceImpl）。
        :param actual:
        :param operation:
        :param expected:
        :return:
        """
        return AutoTestToolServiceImpl.compare_assertion(actual, operation, expected)

    @classmethod
    def extract_from_source(
            cls,
            *,
            source: str,
            expr: Optional[str],
            range_type: Optional[str] = "SOME",
            index: Optional[Any] = None,
            response_text: Optional[str] = None,
            response_json: Optional[Union[list, dict]] = None,
            response_headers: Optional[Dict[str, Any]] = None,
            response_cookies: Optional[Dict[str, Any]] = None,
            session_variables_lookup: Optional[Union[Dict[str, Any], Callable[[str], Any]]] = None,
            operation_type: str = "变量提取",
    ) -> Any:
        """
        从 source 指定来源中按 expr 与 range 提取单个值。供 HTTP 调试与步骤引擎共用。

        :param source: 来源类型，如 "response json"、"response xml"、"response text"、
                      "response header(s)"、"response cookie(s)"、"session_variables"、"变量池"。
        :param expr: 提取表达式（JSONPath/XPath/正则/键名等），SOME 模式必填。
        :param range_type: "ALL" 或 "SOME"，默认 "SOME"。
        :param index: 提取结果为数组时的下标。
        :param response_text: 响应正文。
        :param response_json: 响应 JSON。
        :param response_headers: 响应头。
        :param response_cookies: 响应 Cookie。
        :param session_variables_lookup: 变量池：Dict 则用 key 取值，Callable 则 get_variable(key)。
        :param operation_type: 错误信息前缀，如 "变量提取"、"断言验证"。
        :return: 提取得到的值。
        :raises ValueError: 提取失败时，携带可读错误信息。
        """
        range_type = (range_type or "SOME").strip().lower()
        src = (source or "").strip().lower()

        if src == "response json":
            if response_json is None:
                raise ValueError(f"【{operation_type}】响应内容不是有效的JSON数据")
            if range_type == "all":
                return response_json
            if not expr:
                raise ValueError(
                    f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是有效的JSONPath表达式"
                )
            try:
                extract_value = AutoTestToolServiceImpl.resolve_json_path(data=response_json, expr=expr)
            except Exception as e:
                raise ValueError(str(e)) from e
            if isinstance(extract_value, list) and index is not None:
                try:
                    index_int = int(index)
                    if index_int < len(extract_value):
                        return extract_value[index_int]
                    raise ValueError(
                        f"【{operation_type}】数组越界, "
                        f"给定索引[{index_int}]不可大于数组长度[{len(extract_value)}]"
                    )
                except (ValueError, TypeError) as e:
                    raise ValueError(f"【{operation_type}】参数[index]必须是数字类型, 错误描述: {e}") from e
            return extract_value

        if src == "response xml":
            if not response_text:
                raise ValueError(f"【{operation_type}】响应内容不是有效的XML数据")
            if range_type == "all":
                return response_text
            if not expr:
                raise ValueError(
                    f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是有效的XPath表达式"
                )
            try:
                response_xml = ET.fromstring(response_text)
                elements = response_xml.findall(expr)
                if not elements:
                    raise ValueError(f"【{operation_type}】XPath表达式[{expr}]未匹配到元素")
                if index is not None:
                    try:
                        index_int = int(index)
                        if index_int < len(elements):
                            element = elements[index_int]
                            return element.text if element.text else ET.tostring(element, encoding="unicode")
                        raise ValueError(
                            f"【{operation_type}】数组越界, "
                            f"给定索引[{index_int}]不可大于数组长度[{len(elements)}]"
                        )
                    except (ValueError, TypeError) as e:
                        raise ValueError(f"【{operation_type}】参数[index]必须是数字类型, 错误描述: {e}") from e
                element = elements[-1]
                return element.text if element.text else ET.tostring(element, encoding="unicode")
            except ET.ParseError as e:
                raise ValueError(f"【{operation_type}】响应内容不是有效的XML格式, 错误描述: {e}") from e
            except ValueError:
                raise
            except Exception as e:
                raise ValueError(f"【{operation_type}】XPath表达式[{expr}]执行失败, 错误: {e}") from e

        if src == "response text":
            if not response_text:
                raise ValueError(f"【{operation_type}】响应内容不是有效的Text数据")
            if range_type == "all":
                return response_text
            if not expr:
                raise ValueError(
                    f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是有效的正则表达式"
                )
            try:
                match = re.search(expr, response_text)
                if match:
                    return match.group(0)
                raise ValueError(f"【{operation_type}】正则表达式[{expr}]未匹配到内容")
            except re.error as e:
                raise ValueError(f"【{operation_type}】正则表达式执行失败, 错误描述: {e}") from e

        if src in ("response header", "response headers"):
            if not response_headers:
                raise ValueError(f"【{operation_type}】响应 Headers 为空")
            if range_type == "all":
                return response_headers
            if not expr:
                raise ValueError(
                    f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是存在的键名称"
                )
            var = response_headers.get(expr)
            if var is None or var == "":
                raise ValueError(f"【{operation_type}】响应 Headers 中不存在: {expr}")
            return var

        if src in ("response cookie", "response cookies"):
            if not response_cookies:
                raise ValueError(f"【{operation_type}】响应 Cookies 为空")
            if range_type == "all":
                return response_cookies
            if not expr:
                raise ValueError(
                    f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是存在的键名称"
                )
            var = response_cookies.get(expr)
            if var is None or var == "":
                raise ValueError(f"【{operation_type}】响应 Cookies 中不存在: {expr}")
            return var

        if src == "session_variables" or src == "变量池":
            if not expr:
                raise ValueError(
                    f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是存在的键名称"
                )
            if session_variables_lookup is None:
                raise ValueError(f"【{operation_type}】变量池未提供")
            if callable(session_variables_lookup):
                try:
                    return session_variables_lookup(expr)
                except KeyError:
                    raise ValueError(
                        f"【{operation_type}】在变量池[Session Variables Pool]中未找到[{expr}]变量"
                    ) from None
            val = session_variables_lookup.get(expr)
            if val is None and expr not in session_variables_lookup:
                raise ValueError(
                    f"【{operation_type}】在变量池[Session Variables Pool]中未找到[{expr}]变量"
                )
            return val

        raise ValueError(f"【{operation_type}】源类型 {source} 不被支持")

    @classmethod
    def run_extract_variables(
            cls,
            *,
            extract_variables: List[Dict[str, Any]],
            response_text: Optional[str] = None,
            response_json: Optional[Union[list, dict]] = None,
            response_headers: Optional[Dict[str, Any]] = None,
            response_cookies: Optional[Dict[str, Any]] = None,
            session_variables_lookup: Optional[Union[Dict[str, Any], Callable[[str], Any]]] = None,
            log_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        按 extract_variables 配置从响应/变量池中提取变量。供 HTTP 调试与步骤引擎共用。

        :param extract_variables: 变量提取配置列表，每项通常包含 name/source/expr，且可选 range/index。
        :param response_text: HTTP 响应文本（用于 response text / response xml）。
        :param response_json: HTTP 响应 JSON（用于 response json）。
        :param response_headers: HTTP 响应头（用于 response headers）。
        :param response_cookies: HTTP 响应 cookies（用于 response cookies）。
        :param session_variables_lookup: 变量池（source=session_variables/变量池 时使用），可为 Dict 或 Callable。
        :param log_callback: 可选日志回调。
        :returns: (name->value 字典, 结果列表)。
                  结果列表每项含 name/source/range/expr/index/extract_value/error/success。
        """
        extract_results_dict: Dict[str, Any] = {}
        extract_results_list: List[Dict[str, Any]] = []
        if not extract_variables:
            return extract_results_dict, extract_results_list
        if not isinstance(extract_variables, list):
            if log_callback:
                log_callback(
                    f"【变量提取】表达式列表解析失败: "
                    f"参数[extract_variables]必须是[List[Dict[str, Any]]]类型, "
                    f"但得到[{type(extract_variables)}]类型"
                )
            return extract_results_dict, extract_results_list
        if log_callback:
            log_callback("【变量提取】开始")
        for ext_config in extract_variables:
            if not isinstance(ext_config, dict):
                if log_callback:
                    log_callback(
                        f"【变量提取】表达式子项解析无效(跳过): "
                        f"参数[extract_variables]的子项必须是[Dict[str, Any]]类型, "
                        f"但得到[{type(ext_config)}]类型: {ext_config}"
                    )
                continue
            name = ext_config.get("name")
            expr = ext_config.get("expr")
            source = ext_config.get("source")
            range_type = ext_config.get("range")
            index = ext_config.get("index")
            if not name or not expr or not source:
                if log_callback:
                    log_callback(
                        f"【变量提取】表达式子项解析无效(跳过): "
                        f"参数[name, expr, source]是必须的, 如需继续提取可添加[range, index]参数"
                    )
                continue
            error_msg = ""
            extract_value = None
            try:
                extract_value = cls.extract_from_source(
                    source=source,
                    expr=expr,
                    range_type=range_type,
                    index=index,
                    response_text=response_text,
                    response_json=response_json,
                    response_headers=response_headers,
                    response_cookies=response_cookies,
                    session_variables_lookup=session_variables_lookup,
                    operation_type="变量提取",
                )
                if log_callback:
                    log_callback(f"【变量提取】成功: {name}  <==>  {extract_value}")
            except Exception as e:
                error_msg = str(e)
                if log_callback:
                    log_callback(f"【变量提取】失败: {name}, {error_msg}")
            item = {
                "name": name,
                "source": source,
                "range": range_type,
                "expr": expr,
                "index": index,
                "extract_value": extract_value,
                "error": error_msg,
                "success": error_msg == "",
            }
            extract_results_list.append(item)
            if error_msg == "":
                extract_results_dict[name] = extract_value
        if log_callback:
            log_callback("【变量提取】结束")
        return extract_results_dict, extract_results_list

    @classmethod
    def run_assert_validators(
            cls,
            *,
            assert_validators: List[Dict[str, Any]],
            response_text: Optional[str] = None,
            response_json: Optional[Union[list, dict]] = None,
            response_headers: Optional[Dict[str, Any]] = None,
            response_cookies: Optional[Dict[str, Any]] = None,
            session_variables_lookup: Optional[Union[Dict[str, Any], Callable[[str], Any]]] = None,
            log_callback: Optional[Callable[[str], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        按 assert_validators 配置从响应/变量池取实际值并与期望值比较。供 HTTP 调试与步骤引擎共用。

        :param assert_validators: 断言配置列表，每项通常包含 name/source/expr/operation/except_value。
        :param response_text: HTTP 响应文本（用于 response text / response xml）。
        :param response_json: HTTP 响应 JSON（用于 response json）。
        :param response_headers: HTTP 响应头（用于 response headers）。
        :param response_cookies: HTTP 响应 cookies（用于 response cookies）。
        :param session_variables_lookup: 变量池（source=session_variables/变量池 时使用），可为 Dict 或 Callable。
        :param log_callback: 可选日志回调。
        :returns: 每条断言结果列表，含 name/source/expr/operation/except_value/actual_value/success/error。
        """
        validator_results: List[Dict[str, Any]] = []
        if not assert_validators:
            return validator_results
        if not isinstance(assert_validators, list):
            if log_callback:
                log_callback(
                    f"【断言验证】表达式列表解析失败: "
                    f"参数[assert_validators]必须是[List[Dict[str, Any]]]类型, "
                    f"但得到[{type(assert_validators)}]类型"
                )
            return validator_results
        if log_callback:
            log_callback("【断言验证】开始")
        for validator_config in assert_validators:
            if not isinstance(validator_config, dict):
                if log_callback:
                    log_callback(
                        f"【断言验证】表达式子项解析无效(跳过): "
                        f"参数[assert_validators]的子项必须是[Dict[str, Any]]类型, "
                        f"但得到[{type(validator_config)}]类型: {validator_config}"
                    )
                continue
            name = validator_config.get("name")
            expr = validator_config.get("expr")
            operation = validator_config.get("operation")
            except_value = validator_config.get("except_value")
            source = validator_config.get("source")
            if not name or not expr or not operation or not source:
                if log_callback:
                    log_callback(
                        f"【断言验证】表达式子项解析无效(跳过): "
                        f"参数[name, expr, operation, source]是必须的, 非空断言时需添加[except_value]参数"
                    )
                continue
            error_msg = ""
            success = False
            actual_value = None
            try:
                actual_value = cls.extract_from_source(
                    source=source,
                    expr=expr,
                    range_type="SOME",
                    index=None,
                    response_text=response_text,
                    response_json=response_json,
                    response_headers=response_headers,
                    response_cookies=response_cookies,
                    session_variables_lookup=session_variables_lookup,
                    operation_type="断言验证",
                )
            except Exception as e:
                error_msg = str(e)
                if log_callback:
                    log_callback(f"【断言验证】比较失败: {name}, {error_msg}")
                validator_results.append({
                    "name": name,
                    "source": source,
                    "expr": expr,
                    "operation": operation,
                    "except_value": except_value,
                    "actual_value": actual_value,
                    "success": False,
                    "error": error_msg,
                })
                continue
            try:
                success = cls.compare_assertion(actual=actual_value, operation=operation, expected=except_value)
                if log_callback:
                    if success:
                        log_callback(
                            f"【断言验证】比较成功: "
                            f"{name}, {expr} {operation} {except_value}, 实际值={actual_value}"
                        )
                    else:
                        log_callback(
                            f"【断言验证】比较失败: "
                            f"{name}, {expr} {operation} {except_value}, 实际值={actual_value}"
                        )
            except Exception as e:
                error_msg = str(e)
                success = False
                if log_callback:
                    log_callback(f"【断言验证】比较异常, 错误描述: {e}: {name}, {error_msg}")
            validator_results.append({
                "name": name,
                "source": source,
                "expr": expr,
                "operation": operation,
                "except_value": except_value,
                "actual_value": actual_value,
                "success": success,
                "error": error_msg,
            })
        if log_callback:
            log_callback("【断言验证】结束")
        return validator_results

    @classmethod
    def parse_condition_json(cls, condition: str, error_prefix: str) -> Dict[str, Any]:
        """
        将条件字符串中 Python 风格 None/True/False 转为 JSON 后解析为字典，供步骤引擎中「循环结构」「条件分支」等使用。

        :param condition: JSON 格式条件字符串，含 value、operation、except_value 等。
        :param error_prefix: 错误信息前缀，如 "循环结构"、"条件分支"。
        :return: 解析后的条件字典。
        :raises ValueError: 非合法 JSON 或解析异常时，错误信息会包含 error_prefix。
        """
        try:
            normalized = re.sub(r'\bNone\b', 'null', condition)
            normalized = re.sub(r'\bTrue\b', 'true', normalized)
            normalized = re.sub(r'\bFalse\b', 'false', normalized)
            return json.loads(normalized)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"【{error_prefix}】条件表达式不是有效的JSON格式, \n"
                f"错误位置: 第{e.lineno}行, 第{e.colno}列, \n"
                f"错误信息: {e.msg}"
            ) from e
        except Exception as e:
            raise ValueError(f"【{error_prefix}】条件表达式解析异常, 错误详情: {e}") from e

    @classmethod
    def validate_step_tree_structure(cls, steps_data: List[AutoTestStepTreeUpdateItem]) -> tuple:
        """
        校验步骤树结构：无自循环引用，且仅有「循环结构」「条件分支」类型可包含子步骤。

        :param steps_data: 根步骤列表（每项可为带 children 的树节点）。
        :return: (True, None) 表示通过；(False, str) 表示失败及错误信息。
        """
        from backend.enums.autotest_enum import AutoTestStepType

        # 允许有子步骤的步骤类型
        allowed_children_types = {AutoTestStepType.LOOP, AutoTestStepType.IF}

        def check_step_recursive(step: AutoTestStepTreeUpdateItem, visited_ids: set, path: list) -> tuple:
            """
            递归校验单个步骤节点及其 children：
            - 检查 step_id / step_code 自循环
            - 检查非允许类型是否包含 children

            :param step: 当前步骤节点。
            :param visited_ids: 已访问 step_id 集合（用于检测自循环）。
            :param path: 访问路径 step_code 列表（用于检测自循环）。
            :returns: (True, None) 表示通过；(False, str) 表示失败及错误信息。
            """
            step_id = step.step_id
            step_code = step.step_code

            # 检查自循环引用
            if step_id and step_id in visited_ids:
                return False, f"步骤(step_id={step_id}, step_code={step_code or 'N/A'})存在自循环引用"
            if step_code and step_code in path:
                return False, f"步骤(step_code={step_code})存在自循环引用"

            # 添加到已访问集合
            if step_id:
                visited_ids.add(step_id)
            if step_code:
                path.append(step_code)

            # 检查步骤类型是否允许有子步骤
            if step.children and len(step.children) > 0:
                if step.step_type not in allowed_children_types:
                    return False, (
                        f"步骤(step_id={step_id}, step_code={step_code or 'N/A'}, "
                        f"step_type={step.step_type})不允许包含子步骤, 仅允许'循环结构'和'条件分支'类型的步骤包含子步骤"
                    )

                # 递归检查子步骤
                for child in step.children:
                    child_is_valid, child_error_msg = check_step_recursive(child, visited_ids.copy(), path.copy())
                    if not child_is_valid:
                        return False, child_error_msg

            return True, None

        # 检查所有根步骤
        for step_data in steps_data:
            root_is_valid, root_error_msg = check_step_recursive(step_data, set(), [])
            if not root_is_valid:
                return False, root_error_msg

        return True, None

    @classmethod
    def normalize_step(cls, step: Dict[str, Any]) -> Dict[str, Any]:
        """
        规范化单条步骤数据：conditions 转为 JSON 字符串、移除 case/quote_case，并递归规范化 children 与 quote_steps。

        :param step: 步骤数据字典（可含 conditions、children、quote_steps 等）。
        :return: 规范化后的新字典，不修改入参。
        """
        step = step.copy()

        # 处理conditions：如果是数组，取第一个并转为JSON字符串
        conditions = step.get("conditions")
        if isinstance(conditions, list) and len(conditions) > 0:
            condition_obj = conditions[0]
            step["conditions"] = json.dumps(condition_obj, ensure_ascii=False)
        elif conditions is None:
            step["conditions"] = None

        # extract_variables和assert_validators保持数组格式（执行引擎已支持）
        # 移除不需要的字段
        step.pop("case", None)
        step.pop("quote_case", None)

        # 递归处理children和quote_steps
        if "children" in step and isinstance(step["children"], list):
            step["children"] = [cls.normalize_step(child) for child in step["children"]]
        if "quote_steps" in step and isinstance(step["quote_steps"], list):
            step["quote_steps"] = [cls.normalize_step(quote_step) for quote_step in step["quote_steps"]]

        return step

    @classmethod
    def collect_session_variables(cls, steps_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        递归收集步骤树中所有步骤的 session_variables，合并为扁平列表（每项含 key、value、desc）。

        :param steps_list: 步骤列表，每项可含 children、quote_steps。
        :return: 合并后的变量列表。
        """
        variables = []
        if not steps_list:
            return variables
        for step in steps_list:
            session_variables = step.get("session_variables")
            if isinstance(session_variables, list):
                variables.extend(session_variables)
            # 递归处理children和quote_steps
            children = step.get("children", []) or []
            quote_steps = step.get("quote_steps", []) or []
            variables.extend(cls.collect_session_variables(children))
            variables.extend(cls.collect_session_variables(quote_steps))
        return variables

    @classmethod
    def execute_func_string(cls, session_variables: List[Dict[str, Any]]):
        """
        对会话变量列表中 func_name(...) 形式调用 GenerateUtils（实现见 AutoTestToolServiceImpl）。
        :param session_variables:
        :return:
        """
        return AutoTestToolServiceImpl.execute_func_string(session_variables)

    @classmethod
    def execute_func_string_single(cls, content: str) -> Any:
        """
        单条函数字符串执行（实现见 AutoTestToolServiceImpl）。
        :param content:
        :return:
        """
        return AutoTestToolServiceImpl.execute_func_string_single(content)

    @classmethod
    def resolve_placeholders(
            cls,
            value: Any,
            logger_object: Callable,
            is_core_engine: bool = False,
            finished_variables: Optional[Any] = None,
    ) -> Any:
        """
        递归解析 str/dict/list 中的 ${...} 占位符（实现见 AutoTestToolServiceImpl）。
        :param value:
        :param logger_object:
        :param is_core_engine:
        :param finished_variables:
        :return:
        """
        return AutoTestToolServiceImpl.resolve_placeholders(
            value,
            logger_object,
            is_core_engine=is_core_engine,
            finished_variables=finished_variables,
        )
