# -*- coding: utf-8 -*-
"""
提取与断言结果的 TypedDict 形状定义。

门面仍返回 List[Dict] 以兼容报告与前端；本模块用于类型标注与后续收敛。
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class ExtractResultItem(TypedDict, total=False):
    """单条变量提取结果。"""

    name: Optional[str]
    source: Optional[str]
    scope: Optional[Any]
    expr: Optional[str]
    index: Optional[Any]
    extract_value: Any
    error: str
    success: bool


class AssertResultItem(TypedDict, total=False):
    """单条断言验证结果。"""

    name: Optional[str]
    source: Optional[str]
    expr: Optional[str]
    operation: Optional[str]
    except_value: Any
    actual_value: Any
    success: bool
    error: str
