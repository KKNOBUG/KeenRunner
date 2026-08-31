# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : arithmetic.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

import ast
import re
from typing import Any, Callable, List, Optional, Tuple, Union

import orjson


class PlaceholderArithmetic:
    """占位符场景下的数值判定、表达式拼接与安全算术计算。"""

    _RE_ARITHMETIC_ONLY = re.compile(r"^[\d+\-*/().\s]+$")
    _MAX_ARITH_EXPR_CHARS = 8192

    @classmethod
    def _is_calculated_numeric(cls, value: Any) -> Optional[float]:
        """
        判断value能否作为数值参与算术计算，返回float可参与计算，None则走字符串拼接。

        :param value: 目标值
        :return: 可参与算术的float；否则None
        """
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            try:
                return float(s)
            except ValueError:
                return None
        return None

    @classmethod
    def _is_calculate_placeholder_expr(
            cls,
            content: str,
            regularly_slots: List[Tuple[re.Match[str], Optional[Any], Optional[str]]],
    ) -> bool:
        """
        判断占位符模板是否应进入纯算术计算路径，模板中占位符之外只能含算术字符。

        :param content: 待解析的占位符模板字符串
        :param regularly_slots: 占位符匹配与解析结果列表
        :return: 是否应进入纯算术计算路径
        """
        if len(regularly_slots) == 1:
            if re.search(r"[+\-*/]", content) is None:
                return False
            match, value, failed_content = regularly_slots[0]
            if value is None:
                return False
            try:
                float(value)
                return True
            except ValueError:
                return False

        skeleton_parts: List[str] = []
        pos: int = 0
        for match, value, failed_content in regularly_slots:
            skeleton_parts.append(content[pos: match.start()])
            pos = match.end()
        skeleton_parts.append(content[pos:])
        skeleton: str = "".join(skeleton_parts).strip()
        return bool(skeleton) and bool(cls._RE_ARITHMETIC_ONLY.fullmatch(skeleton))

    @classmethod
    def _normalize_float(cls, f: float) -> str:
        """
        将浮点数转为可嵌入算术表达式的字面量字符串，整数等价物去小数点。

        :param f: 目标浮点数
        :return: 数字字面量字符串
        """
        if f.is_integer():
            return str(int(f))
        return str(f)

    @classmethod
    def _formatter_resolved_placeholders(cls, value: Any) -> str:
        """
        非纯算术路径下将解析后的Python值转为字符串片段，dict/list用JSON，None为空串。

        :param value: 解析后的Python值
        :return: 格式化后的字符串片段
        """
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return orjson.dumps(value).decode("UTF-8")
        return str(value)

    @staticmethod
    def _formatter_calculated_result(result: Union[int, float]) -> str:
        """
        将算术求值结果格式化为对外字符串，整数等价float输出整数形式。

        :param result: 算术求值结果
        :return: 字符串形式
        """
        if isinstance(result, float) and result.is_integer():
            return str(int(result))
        return str(result)

    @classmethod
    def _split_placeholders(
            cls,
            content: str,
            regularly_slots: List[Tuple[re.Match[str], Optional[Any], Optional[str]]],
            to_string: Callable[[Any], str],
    ) -> str:
        """
        根据占位符顺序拼接content，解析失败插入原文，成功插入to_string(value)。

        :param content: 待解析对象
        :param regularly_slots: 占位符匹配与解析结果列表
        :param to_string: 将解析值格式化为字符串的函数
        :return: 拼接后的字符串
        """
        pos: int = 0
        parts: List[str] = []
        for match, value, failed_content in regularly_slots:
            parts.append(content[pos: match.start()])
            parts.append(failed_content if failed_content is not None else to_string(value))
            pos = match.end()
        parts.append(content[pos:])
        return "".join(parts)

    @classmethod
    def _build_numeric_merged_expr(cls, content: str, reg_matches: List[re.Match[str]], calculated_numeric: List[float]) -> str:
        """
        将全部解析成功的占位符替换为数字字面量, 保留两侧运算符与括号, 生成可被AST解析的表达式字符串。

        :param content: 待解析对象
        :param reg_matches: 与calculated_numeric一一对应的占位符match列表
        :param calculated_numeric: 每个占位符对应的数值(float)
        :return: 占位符替换为数字后的表达式字符串
        """
        pos: int = 0
        parts: List[str] = []
        for match, numer in zip(reg_matches, calculated_numeric):
            parts.append(content[pos: match.start()])
            parts.append(cls._normalize_float(numer))
            pos = match.end()
        parts.append(content[pos:])
        return "".join(parts)

    @classmethod
    def _safe_calculation_expr(cls, expr: str) -> Union[int, float]:
        """
        安全计算纯算术表达式字符串结果，基于AST白名单校验，禁止变量/函数调用等非算术语法。

        :param expr: 算术表达式字符串
        :return: 计算结果（int或float）
        """
        expr = expr.strip()
        if not expr:
            raise ValueError("计算内容为空")
        if len(expr) > cls._MAX_ARITH_EXPR_CHARS:
            raise ValueError("计算内容过长")

        def eval_node(node: ast.expr) -> float:
            """
            递归遍历AST节点并计算子表达式值。

            :param node: AST表达式节点
            :return: 子表达式计算值（float）
            """
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    return float(node.value)
                raise ValueError("计算内容仅支持数字常量, 不支持字符串、布尔值等其他类型")
            if isinstance(node, ast.Num):  # Python 3.7 及更早
                return float(node.n)
            if isinstance(node, ast.UnaryOp):
                if isinstance(node.op, ast.USub):
                    return -eval_node(node.operand)
                if isinstance(node.op, ast.UAdd):
                    return +eval_node(node.operand)
                raise ValueError("计算内容中包含不被允许的一元运算符, 仅支持: + -")
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
                        raise ZeroDivisionError("计算内容错误, 除数不能为0")
                    return left / right
                raise ValueError("计算内容中包含不被允许的二元运算符, 仅支持: + - * /")
            raise ValueError("计算内容中包含不被允许的算术结构, 仅支持数字与四则运算")

        tree = ast.parse(expr, mode="eval")
        if not isinstance(tree, ast.Expression):
            raise ValueError("计算内容不是有效的算术表达式")
        raw = eval_node(tree.body)
        if isinstance(raw, float) and raw.is_integer():
            return int(raw)
        return raw
