# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : context.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

from backend.applications.autotest.schemas.autotest_step_schema import StepVariablesBase


@dataclass
class ExchangeContext:
    """一次请求/响应快照，供提取与断言管线按字段定位取值。"""

    # 响应侧原始素材：text 供正则/JSONPath 定位，json 为已解析对象，headers/cookies 供头部与 Cookie 断言
    response_text: Optional[str] = None
    response_json: Optional[Any] = None
    response_headers: Optional[Dict[str, Any]] = None
    response_cookies: Optional[Dict[str, Any]] = None
    # 请求侧原始素材：各协议执行器在发送后按实际发出内容回填，供断言核对请求报文
    request_text: Optional[str] = None
    request_json: Optional[Any] = None
    request_headers: Optional[Dict[str, Any]] = None
    request_cookies: Optional[Dict[str, Any]] = None
    request_form_data: Optional[Dict[str, Any]] = None
    # 变量查找表（defined + session 合并、session 覆盖同名 defined），供提取器/断言按已定义变量取值
    session_lookup: Optional[Dict[str, Any]] = None


class ListVariableResolver:
    """把变量列表适配成 get_variable(name) 取值接口，供非引擎上下文（调试/校验等）复用占位符解析。"""

    def __init__(self, variables: Optional[Sequence[StepVariablesBase]]) -> None:
        """
        构造变量列表适配器。

        :param variables: 变量列表；None 视为空列表（取值时按未定义抛 KeyError）
        """
        # 保存原列表引用不做拷贝：取值时始终按调用方当前列表内容查找
        self._variables = variables

    def get_variable(self, name: str) -> Any:
        """
        从列表中根据key取值。

        :param name: 变量名
        :return: 对应value；null是合法变量值，仅在key不存在时抛KeyError
        """
        from backend.applications.autotest.services.autotest_runtime.util_kv import KvUtils

        item = KvUtils.get_item_from_list(self._variables, name)
        if item is None:
            raise KeyError(f"必须是已定义的变量: {name!r}")
        return item.value


def coerce_variable_resolver(
        *,
        finished_variables: Any,
        is_core_engine: bool,
) -> Any:
    """
    把变量源统一成实现 get_variable(name) 的解析对象，供占位符解析复用。

    引擎上下文（is_core_engine=True）原样透传；变量列表包装为 ListVariableResolver；
    无变量源返回 None，调用方需自行判空并按"变量未定义"处理。

    :param finished_variables: 引擎上下文或变量列表；None 表示无变量源
    :param is_core_engine: True 时表示调用方已确认传入的是引擎上下文
    :return: 实现 get_variable 的兼容对象；无变量源时返回 None
    """
    if finished_variables is None:
        return None
    if is_core_engine:
        return finished_variables
    return ListVariableResolver(finished_variables)
