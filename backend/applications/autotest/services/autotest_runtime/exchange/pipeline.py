# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : pipeline.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import orjson

from backend.applications.autotest.schemas.autotest_step_schema import (
    StepAssertValidatorItem,
    StepExtractVariableItem,
    StepVariablesBase,
)
from backend.applications.autotest.services.autotest_runtime.exchange.assert_pipeline import AssertPipeline
from backend.applications.autotest.services.autotest_runtime.exchange.extract_pipeline import ExtractPipeline


class ExtractAssertPipeline:
    """
    提取与断言管线的统一编排入口，供步骤引擎与步骤调试共用。

    执行顺序固定：变量提取 → 提取失败判定 → 提取结果回写变量池 → 断言验证 →
    追加数据驱动断言 → 断言失败判定，保证同一步内断言可引用本步刚提取的变量。
    """

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
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        统一执行变量提取与断言验证。

        执行顺序：按extract_variables提取 → 回写变量池 → 按assert_validators断言 →
        step_struct非空时追加数据驱动断言 → 统一判定失败。
        raise_on_failure为True时：提取存在失败项立即抛ValueError（断言不执行，成功项也不会写入变量池）；
        断言在本批（含数据驱动追加项）全部执行完后才统一抛ValueError。

        :param extract_variables: 提取规则；None视为空列表
        :param assert_validators: 断言规则；None视为空列表
        :param response_text: 响应正文
        :param response_json: 响应JSON，或DB/Redis操作结果列表
        :param response_headers: 响应头
        :param response_cookies: 响应Cookie
        :param request_text: 请求正文
        :param request_json: 请求JSON
        :param request_headers: 请求头
        :param request_cookies: 请求Cookie
        :param request_form_data: 请求Form-Data/X-WWW-Form-Urlencoded合并映射
        :param session_variables_lookup: 变量池字典；提取成功项就地写入（同名覆盖）
        :param log_callback: 可选日志回调
        :param finished_variables: 断言期望值占位符解析上下文；实现update_variables时同步写入session_variables作用域
        :param is_core_engine: 占位符解析模式；True核心引擎，False调试
        :param step_struct: 数据驱动结构；非None时追加assert_head/assert_body
        :param raise_on_failure: True时提取或断言失败抛ValueError
        :return: (提取逐项结果列表, 断言逐项结果列表)
        :raises ValueError: 提取或断言存在失败项（raise_on_failure为True时）
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
        # 提取失败先行抛出：断言依赖提取结果，且失败批次不写入变量池，避免失败值被后续引用
        if raise_on_failure:
            extract_failed_items = [item for item in extract_results_list if not item.get("success", True)]
            if extract_failed_items:
                dumps = orjson.dumps(extract_failed_items, option=orjson.OPT_INDENT_2).decode("UTF-8")
                raise ValueError(f"【变量提取】共计{len(extract_failed_items)}个提取失败: \n{dumps}")

        # 同一步内断言可能引用刚提取的变量（变量池 / ${name}），须在断言前写入查找表与上下文
        if extract_results_dict:
            if session_variables_lookup is not None:
                session_variables_lookup.update(extract_results_dict)
            # 变量池对象可选实现update_variables；未实现时仅更新查找表，不影响断言取值
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
        # 数据驱动断言：assert_head/assert_body 追加进同一结果列表，参与下面的统一失败判定
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
            )
        # 断言失败在数据驱动追加完成后统一判定，保证一次反馈完整的失败明细
        if raise_on_failure:
            assert_failed_items = [item for item in validator_results if not item.get("success", True)]
            if assert_failed_items:
                dumps = orjson.dumps(assert_failed_items, option=orjson.OPT_INDENT_2).decode("UTF-8")
                raise ValueError(f"【断言验证】共计{len(assert_failed_items)}个断言失败: \n{dumps}")
        return extract_results_list, validator_results
