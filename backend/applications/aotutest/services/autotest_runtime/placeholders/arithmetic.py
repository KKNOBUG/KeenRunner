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
        判断value能否作为数值参与算术表达式计算, 用于区分「算术计算」与「字符串拼接」逻辑。

        返回float对象：可参与算术计算
        返回None：应根据字符串拼接处理, 不参与算术计算
        :param value: 目标值
        :return: 可参与算术的float；否则None（根据字符串拼接处理）
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
        判断当前占位符模板是否应进入「纯算术表达式」计算路径。

        模板中占位符之外的文本只能包含算术字符, 否则根据普通字符串拼接。单占位符场景下, 若结果是字符串, 直接根据字符串返回, 避免如"00123"被数值化后丢失前导0
        :param content: 待解析的占位符模板字符串
        :param regularly_slots: 占位符匹配与解析结果列表
        :return: 是否应进入纯算术表达式计算路径
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
        将浮点数转换为可以安全嵌入算术表达式的数字字面量字符串。

        若f等价整数(如: 5.0、-2.0), 返回不带小数点和后缀0的整数字符串(如: "5"、"-2")；若f不等价整数(如: 3.14、2.5), 直接返回原浮点数字符串(如: "3.14"、"2.5")。目的：避免表达式中出现100.0这类冗余格式，提升可读性
        :param f: 目标浮点数
        :return: 可嵌入算术表达式的数字字面量字符串
        """
        if f.is_integer():
            return str(int(f))
        return str(f)

    @classmethod
    def _formatter_resolved_placeholders(cls, value: Any) -> str:
        """
        非「纯算术整式求值」路径下, 将解析后的Python值转为字符串片段。

        dict/list使用JSON(便于日志与下游展示)；None转为空串
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
        将_safe_calculation_expr的返回值格式化为对外字符串。

        :param result: 算术求值结果(int/float)
        :return: 字符串形式；若为形如7.0的float, 会输出"7"
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
        根据占位符顺序拼接content, regularly_slots每项为(match, value, failed_content)。

        failed_content非None：解析失败, 插入该原文(一般为match.group(0))；failed_content为None：解析成功, 插入to_string(value)(value可为None, 如变量值为空)
        :param content: 待解析对象
        :param regularly_slots: 占位符匹配与解析结果列表, 每一项是三元组: match(匹配对象), value(替换值), failed_content(失败的原文)
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
        安全计算纯算术表达式字符串的结果(四则运算+括号+一元正负号), 供resolve_placeholders在全部占位符解析为数值且替换后整串仅包含合法算术字符时调用。

        不使用Python内置eval/exec函数计算, 完全基于AST语法树白名单校验实现安全计算, 允许数值常量、一元正负号、加减乘除、括号(括号自动体现为AST结构), 禁止变量、属性、函数调用、下标、幂运算、字符串等所有非算术语法。整数结果返回int类型, 小数结果返回float类型
        :param expr: 算术表达式字符串(如: "1 + 2*(3-4)")
        :return: 计算结果
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
