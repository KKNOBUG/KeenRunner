# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : context.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, Sequence

from backend.applications.aotutest.schemas.autotest_step_schema import StepVariablesBase


class VariableResolver(Protocol):
    """变量解析协议：根据名称返回已定义变量的值。"""

    def get_variable(self, name: str) -> Any:
        """
        根据变量名取值。

        :param name: 变量名（占位符${name}中的name）
        :return: 变量值
        """
        ...


@dataclass
class ExchangeContext:
    """一次请求/响应快照，供提取与断言管线使用。"""

    response_text: Optional[str] = None
    response_json: Optional[Any] = None
    response_headers: Optional[Dict[str, Any]] = None
    response_cookies: Optional[Dict[str, Any]] = None
    request_text: Optional[str] = None
    request_json: Optional[Any] = None
    request_headers: Optional[Dict[str, Any]] = None
    request_cookies: Optional[Dict[str, Any]] = None
    session_lookup: Optional[Dict[str, Any]] = None


class ListVariableResolver:
    """调试视图等场景：从StepVariablesBase列表根据key取值。"""

    def __init__(self, variables: Optional[Sequence[StepVariablesBase]]) -> None:
        """
        以StepVariablesBase列表构造解析器。

        :param variables: 变量列表；可为None（视为空列表）
        """
        self._variables = variables

    def get_variable(self, name: str) -> Any:
        """
        从列表中根据key取值。

        :param name: 变量名
        :return: 对应value
        """
        from backend.applications.aotutest.services.autotest_runtime.util_kv import KvUtils

        resolved = KvUtils.get_value_from_list(self._variables, name)
        if resolved is None:
            raise KeyError(f"必须是已经存在且有值的变量: {name!r}")
        return resolved


def coerce_variable_resolver(
        *,
        finished_variables: Any,
        is_core_engine: bool,
) -> Any:
    """
    将历史(is_core_engine, finished_variables)转为可get_variable的对象。

    引擎上下文原样返回；列表路径包装为ListVariableResolver。

    :param finished_variables: 引擎上下文或变量列表；None表示无变量源
    :param is_core_engine: True时视为已实现get_variable的引擎上下文
    :return: VariableResolver兼容对象；无变量源时返回None
    """
    if finished_variables is None:
        return None
    if is_core_engine:
        return finished_variables
    return ListVariableResolver(finished_variables)
