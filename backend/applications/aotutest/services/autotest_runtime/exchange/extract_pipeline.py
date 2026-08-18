# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : extract_pipeline.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from backend.applications.aotutest.schemas.autotest_step_schema import StepExtractVariableItem
from backend.applications.aotutest.services.autotest_runtime.exchange.extractors import Extractors


class ExtractPipeline:
    """批量执行变量提取并汇总name->value与逐项结果。"""

    @classmethod
    def run_extract_variables(
            cls,
            *,
            extract_variables: Sequence[StepExtractVariableItem],
            response_text: Optional[str] = None,
            response_json: Optional[Union[list, dict]] = None,
            response_headers: Optional[Dict[str, Any]] = None,
            response_cookies: Optional[Dict[str, Any]] = None,
            request_text: Optional[str] = None,
            request_json: Optional[Union[list, dict]] = None,
            request_headers: Optional[Dict[str, Any]] = None,
            request_cookies: Optional[Dict[str, Any]] = None,
            request_form_data: Optional[Dict[str, Any]] = None,
            session_variables_lookup: Optional[Dict[str, Any]] = None,
            log_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        根据StepExtractVariableItem列表从请求/响应/变量池中提取变量。

        不完整规则（缺name/source，或SOME模式缺expr）会跳过该项并可选记日志，
        不中断其余项；单条提取异常记入该项error/success=False，不向外抛出。

        :param extract_variables: 提取规则列表（元素须为StepExtractVariableItem）
        :param response_text: 响应正文
        :param response_json: 响应JSON，或DB/Redis步骤的操作结果列表
        :param response_headers: 响应头
        :param response_cookies: 响应Cookie
        :param request_text: 请求正文
        :param request_json: 请求JSON
        :param request_headers: 请求头
        :param request_cookies: 请求Cookie
        :param request_form_data: 请求 Form-Data / X-WWW-Form-Urlencoded 合并映射
        :param session_variables_lookup: 变量池字典
        :param log_callback: 可选日志回调(str) -> None
        :return: (name->value字典, 逐项结果列表)；成功项才写入字典
        """
        extract_results_dict: Dict[str, Any] = {}
        extract_results_list: List[Dict[str, Any]] = []
        if not extract_variables:
            return extract_results_dict, extract_results_list
        if not isinstance(extract_variables, (list, tuple)):
            raise TypeError(
                f"extract_variables 必须为序列类型 StepExtractVariableItem，当前: {type(extract_variables).__name__}"
            )
        for extract_config in extract_variables:
            if not isinstance(extract_config, StepExtractVariableItem):
                raise TypeError(
                    f"extract_variables 子项必须为 StepExtractVariableItem，当前: {type(extract_config).__name__}"
                )
            name = extract_config.name
            expr = extract_config.expr
            source = extract_config.source
            range_type = extract_config.scope
            index = extract_config.index
            scope_is_all = str(range_type or "").strip().upper() == "ALL"
            if not name or not source or (not scope_is_all and not expr):
                if log_callback:
                    log_callback(
                        f"【变量提取】表达式子项解析无效(跳过提取): \n\t"
                        f"参数[name, source]是必须的, SOME 模式还需[expr], 如需继续提取可添加[scope, index]参数"
                    )
                continue
            error_message: str = ""
            extract_value = None
            try:
                extract_value = Extractors.extract_from_source(
                    source=source,
                    expr=expr,
                    range_type=range_type,
                    index=index,
                    response_text=response_text,
                    response_json=response_json,
                    response_headers=response_headers,
                    response_cookies=response_cookies,
                    request_text=request_text,
                    request_json=request_json,
                    request_headers=request_headers,
                    request_cookies=request_cookies,
                    request_form_data=request_form_data,
                    session_variables_lookup=session_variables_lookup,
                    operation_type="变量提取",
                )
                if log_callback:
                    log_callback(
                        f"【变量提取】成功: \n\t"
                        f"提取名称: {name}\n\t"
                        f"提取对象: {source}\n\t"
                        f"提取范围: {range_type}\n\t"
                        f"提取路径: {expr}\n\t"
                        f"提取索引: {index}\n\t"
                        f"提取数据: {extract_value}"
                    )
            except Exception as e:
                error_message = str(e)
                if log_callback:
                    log_callback(
                        f"【变量提取】失败: \n\t"
                        f"提取名称: {name}\n\t"
                        f"提取对象: {source}\n\t"
                        f"提取范围: {range_type}\n\t"
                        f"提取路径: {expr}\n\t"
                        f"提取索引: {index}\n\t"
                        f"提取数据: {extract_value}\n\t"
                        f"错误描述: {error_message}"
                    )
            item = {
                "name": name,
                "source": source,
                "scope": range_type,
                "expr": expr,
                "index": index,
                "extract_value": extract_value,
                "error": error_message,
                "success": error_message == "",
            }
            extract_results_list.append(item)
            if error_message == "":
                extract_results_dict[name] = extract_value
        return extract_results_dict, extract_results_list
