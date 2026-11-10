# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : functions.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional, Tuple

from backend.common.generate_utils import GenerateUtils


class PlaceholderFunctions:
    """解析 func_name(k=literal, ...) 形式的占位符，并反射调用 GenerateUtils 上的辅助函数。"""

    @classmethod
    def _parse_funcname_funcargs(cls, func_string: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        解析 func_name(key1=val1, key2="a,b") 形式的调用字符串，仅支持关键字字面量参数。

        使用 AST 解析而非逗号切分，避免字符串参数内含逗号时被错误拆分。失败分两类：
        非字符串、不以 ")" 结尾、解析结果不是 Name 调用时返回 (None, None) 交由调用方拒绝；
        语法错误、位置参数、**kwargs、非字面量参数时抛 ValueError 并带上原始调用串。

        :param func_string: 函数调用形式的字符串
        :return: 二元组(函数名, 参数字典)；不构成调用形态时返回 (None, None)
        :raises ValueError: 调用串非法或参数不符合"仅关键字字面量"约束
        """
        if not isinstance(func_string, str):
            return None, None
        text = func_string.strip()
        if not text.endswith(")"):
            return None, None
        try:
            expression = ast.parse(text, mode="eval").body
        except SyntaxError as e:
            raise ValueError(f"【辅助函数】[{func_string!r}]解析失败, 不是合法的函数调用: {e}") from e
        if not isinstance(expression, ast.Call) or not isinstance(expression.func, ast.Name):
            return None, None
        if expression.args:
            raise ValueError(f"【辅助函数】[{func_string!r}]解析失败, 仅支持关键字参数")
        args_dict: Dict[str, Any] = {}
        for keyword in expression.keywords:
            if keyword.arg is None:
                raise ValueError(f"【辅助函数】[{func_string!r}]解析失败, 不支持**kwargs")
            try:
                args_dict[keyword.arg] = ast.literal_eval(keyword.value)
            except (ValueError, SyntaxError) as e:
                raise ValueError(
                    f"【辅助函数】[{func_string!r}]解析失败, 参数仅支持字面量(数字、字符串、布尔、None等), "
                    f"{keyword.arg}={ast.unparse(keyword.value)!r}"
                ) from e
        return expression.func.id, args_dict

    @classmethod
    def execute_func_string_single(cls, content: str) -> Any:
        """
        执行函数调用形式的占位符文本（如 func_name(...)）：反射 GenerateUtils 上的同名函数并返回其结果。

        仅校验 GenerateUtils 上是否存在同名属性（未维护方法白名单），参数必须是字面量关键字参数；
        解析失败、函数不存在、参数签名不匹配及调用期异常统一包装为 AttributeError，保留原始错误链。

        :param content: 如"generate_uuid()"、"generate_string(length=2)"
        :return: 函数返回值
        :raises AttributeError: 调用串非法、函数未定义或执行失败
        """
        try:
            func_name, func_args = cls._parse_funcname_funcargs(content)
        except ValueError as e:
            raise AttributeError(f"【辅助函数】[{content!r}]调用失败: {e}") from e
        if not func_name and not func_args:
            raise AttributeError(f"【辅助函数】[{content!r}]调用失败, 占位符不是有效的调用")
        if not hasattr(GenerateUtils, func_name):
            raise AttributeError(f"【辅助函数】[{func_name}]调用失败, 未定义或不被允许调用")
        try:
            return getattr(GenerateUtils(), func_name)(**(func_args or {}))
        except TypeError as e:
            raise AttributeError(f"【辅助函数】[{func_name}]调用失败, 参数签名或类型不匹配: {e}") from e
        except SyntaxError as e:
            raise AttributeError(f"【辅助函数】[{func_name}]调用失败, 语法解析失败或未定义: {e}") from e
        except Exception as e:
            raise AttributeError(f"【辅助函数】[{func_name}]调用失败, 在动态注入时发生异常: {e}") from e
