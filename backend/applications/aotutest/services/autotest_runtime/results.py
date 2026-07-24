# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : results.py
@DateTime: 2025/12/28 16:15
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
