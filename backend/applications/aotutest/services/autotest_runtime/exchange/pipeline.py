# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : pipeline.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import orjson

from backend.applications.aotutest.schemas.autotest_step_schema import (
    StepAssertValidatorItem,
    StepExtractVariableItem,
    StepVariablesBase,
)
from backend.applications.aotutest.services.autotest_runtime.exchange.assert_pipeline import AssertPipeline
from backend.applications.aotutest.services.autotest_runtime.exchange.extract_pipeline import ExtractPipeline


class ExtractAssertPipeline:
    """串联ExtractPipeline与AssertPipeline，供步骤引擎一次调用。"""

    @classmethod
    def run_extract_and_assert(
            cls,
            *,
            extract_variables: Optional[Sequence[StepExtractVariableItem]] = None,
            assert_validators: Optional[Sequence[StepAssertValidatorItem]] = None,
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
            finished_variables: Optional[Any] = None,
            is_core_engine: bool = True,
            step_struct: Optional[Dict[str, Dict[str, Any]]] = None,
            raise_on_failure: bool = True,
            body_source: str = "response json",
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        统一执行变量提取与断言验证（引擎主路径）。

        处理顺序：
        1. ExtractPipeline.run_extract_variables
        2. 若raise_on_failure且存在success=False的提取项→抛出ValueError
        3. 将成功提取写入session_variables_lookup（及finished_variables，若支持），供同一步断言引用
        4. AssertPipeline.run_assert_validators
        5. 若step_struct is not None → append_assert_validators追加数据驱动断言
        6. 若raise_on_failure且存在失败断言→抛出ValueError

        :param extract_variables: 提取规则；None视为空列表
        :param assert_validators: 断言规则；None视为空列表
        :param response_text: 响应正文（Text/XML提取与断言）
        :param response_json: 响应JSON，或DB/Redis步骤的操作结果列表
        :param response_headers: 响应头
        :param response_cookies: 响应Cookie
        :param request_text: 请求正文
        :param request_json: 请求JSON
        :param request_headers: 请求头；未传request_cookies时可用于解析Cookie
        :param request_cookies: 请求Cookie；优先于从请求头解析
        :param request_form_data: 请求 Form-Data / X-WWW-Form-Urlencoded 合并映射
        :param session_variables_lookup: 变量池字典（session_variables/变量池source）
        :param log_callback: 可选日志回调(str) -> None
        :param finished_variables: 断言期望值占位符解析上下文；引擎传StepExecutionContext
        :param is_core_engine: True时finished_variables需提供get_variable；
            False时根据StepVariablesBase列表解析（调试视图）
        :param step_struct: 数据驱动结构；非None时追加assert_head/assert_body
            （即使内部各块为空也会进入追加逻辑，仅在结构非法时直接跳过）
        :param raise_on_failure: True时提取或断言存在失败项即抛ValueError（文案与历史引擎一致）；
            False时仅返回结果列表，由调用方自行判断
        :param body_source: 保留参数，当前未生效；assert_body来源根据表达式前缀自动识别
            （$. → response json，./或// → response xml，其他 → response text）
        :return: (extract_results_list, assert_results_list)，元素为结果dict
            （含name/source/expr/success/error等字段）
        """
        extract_results_dict, extract_results_list = ExtractPipeline.run_extract_variables(
            extract_variables=extract_variables or [],
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
            log_callback=log_callback,
        )
        if raise_on_failure:
            extract_failed_items = [item for item in extract_results_list if not item.get("success", True)]
            if extract_failed_items:
                dumps = orjson.dumps(extract_failed_items, option=orjson.OPT_INDENT_2).decode("UTF-8")
                raise ValueError(f"【变量提取】共计{len(extract_failed_items)}个提取失败: \n{dumps}")

        # 同一步内断言可能引用刚提取的变量（变量池 / ${name}），须在断言前写入查找表与上下文
        if extract_results_dict:
            if session_variables_lookup is not None:
                session_variables_lookup.update(extract_results_dict)
            update_variables = getattr(finished_variables, "update_variables", None)
            if callable(update_variables):
                update_variables(
                    [
                        StepVariablesBase(key=str(name), value=value, desc="")
                        for name, value in extract_results_dict.items()
                    ],
                    scope="session_variables",
                )

        validator_results = AssertPipeline.run_assert_validators(
            assert_validators=assert_validators or [],
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
            log_callback=log_callback,
            finished_variables=finished_variables,
            is_core_engine=is_core_engine,
        )
        if step_struct is not None:
            AssertPipeline.append_assert_validators(
                step_struct=step_struct,
                validator_results=validator_results,
                response_text=response_text,
                response_json=response_json,
                response_headers=response_headers,
                response_cookies=response_cookies,
                session_variables_lookup=session_variables_lookup,
                finished_variables=finished_variables,
                is_core_engine=is_core_engine,
                log_callback=log_callback,
                body_source=body_source,
            )
        if raise_on_failure:
            assert_failed_items = [item for item in validator_results if not item.get("success", True)]
            if assert_failed_items:
                dumps = orjson.dumps(assert_failed_items, option=orjson.OPT_INDENT_2).decode("UTF-8")
                raise ValueError(f"【断言验证】共计{len(assert_failed_items)}个断言失败: \n{dumps}")
        return extract_results_list, validator_results
