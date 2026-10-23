# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : functions.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional, Tuple

from backend.common.generate_utils import GenerateUtils


class PlaceholderFunctions:
    """解析并动态执行GenerateUtils上的辅助函数。"""

    @classmethod
    def _parse_funcname_funcargs(cls, func_string: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        解析func_name(key1=val1, key2="a,b")格式字符串，仅支持关键字字面量参数。

        使用AST解析而非逗号切分，避免字符串参数内含逗号时被错误拆分。

        :param func_string: 函数调用形式的字符串
        :return: 二元组(函数名, 参数字典)，无法解析时返回(None, None)
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
        针对content为函数调用字符串格式(如func_name(...))的场景, 通过GenerateUtils类实现反射机制动态执行对应函数并返回函数返回值。

        :param content: 如"generate_uuid()"、"generate_string(length=2)"
        :return: 函数返回值
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
