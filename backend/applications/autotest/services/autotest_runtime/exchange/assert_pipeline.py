# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : assert_pipeline.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from backend.applications.autotest.schemas.autotest_step_schema import StepAssertValidatorItem
from backend.applications.autotest.services.autotest_runtime.exchange.assert_compare import AssertionCompare
from backend.applications.autotest.services.autotest_runtime.exchange.extractors import Extractors
from backend.applications.autotest.services.autotest_runtime.placeholders.resolver import PlaceholderResolver


class AssertPipeline:
    """批量断言验证，以及数据驱动场景的断言追加。"""

    @classmethod
    def run_assert_validators(
            cls,
            *,
            assert_validators: Sequence[StepAssertValidatorItem],
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
            is_core_engine: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        根据断言规则列表取实际值并与期望值比较，不完整规则跳过，异常记入该项且不中断其余项。

        :param assert_validators: 断言规则列表
        :param response_text: 响应正文
        :param response_json: 响应JSON，或DB/Redis操作结果列表
        :param response_headers: 响应头
        :param response_cookies: 响应Cookie
        :param request_text: 请求正文
        :param request_json: 请求JSON
        :param request_headers: 请求头
        :param request_cookies: 请求Cookie
        :param request_form_data: 请求Form-Data/X-WWW-Form-Urlencoded合并映射
        :param session_variables_lookup: 变量池字典
        :param log_callback: 可选日志回调
        :param finished_variables: 非空时对except_value先做占位符解析
        :param is_core_engine: 占位符解析模式
        :return: 每项断言结果dict列表
        """
        validator_results: List[Dict[str, Any]] = []
        if not assert_validators:
            return validator_results
        if not isinstance(assert_validators, (list, tuple)):
            raise TypeError(
                f"参数[assert_validators]必须为StepAssertValidatorItem对象，当前: {type(assert_validators).__name__}"
            )
        for validator_config in assert_validators:
            if not isinstance(validator_config, StepAssertValidatorItem):
                raise TypeError(
                    f"参数[assert_validators]子项必须为StepAssertValidatorItem对象，当前: {type(validator_config).__name__}"
                )
            name = validator_config.name
            expr = validator_config.expr
            operation = validator_config.operation
            except_value = validator_config.except_value
            source = validator_config.source
            if not name or not expr or not operation or not source:
                if log_callback:
                    log_callback(
                        f"【断言验证】表达式子项解析无效(跳过断言): \n\t"
                        f"参数[name, expr, operation, source]不允许为空, 非空断言时需添加[except_value]参数"
                    )
                continue
            error_message: str = "实际值与预期值不满足指定操作符比较"
            success: bool = False
            actual_value: Any = None
            try:
                actual_value = Extractors.extract_from_source(
                    source=source,
                    expr=expr,
                    range_type="SOME",
                    index=None,
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
                    operation_type="断言验证",
                )
            except Exception as e:
                error_message = str(e)
                if log_callback:
                    expr_message: str = (
                        f"数据源: {source}\n\t"
                        f"表达式: {expr}\n\t"
                        f"实际值: {actual_value}\n\t"
                        f"操作符: {operation}\n\t"
                        f"预期值: {except_value}\n\t"
                        f"错误描述: {error_message}"
                    )
                    log_callback(f"【断言验证】获取实际值失败: \n\t{expr_message}")
                validator_results.append({
                    "name": name,
                    "source": source,
                    "expr": expr,
                    "operation": operation,
                    "except_value": except_value,
                    "actual_value": actual_value,
                    "success": success,
                    "error": error_message,
                })
                continue
            resolved_except_value = (
                except_value
                if finished_variables is None
                else PlaceholderResolver.resolve_placeholders(
                    value=except_value,
                    logger_object=log_callback,
                    is_core_engine=is_core_engine,
                    finished_variables=finished_variables,
                )
            )
            try:
                success: bool = AssertionCompare.compare_assertion(
                    actual=actual_value,
                    operation=operation,
                    expected=resolved_except_value
                )
                if log_callback:
                    expr_message: str = (
                        f"数据源: {source}\n\t"
                        f"表达式: {expr}\n\t"
                        f"实际值: {actual_value}\n\t"
                        f"操作符: {operation}\n\t"
                        f"预期值: {resolved_except_value}"
                    )
                    if success:
                        log_callback(f"【断言验证】成功: \n\t{expr_message}")
                    else:
                        log_callback(f"【断言验证】失败: \n\t{expr_message}")
            except ValueError as e:
                error_message = str(e)
                if log_callback:
                    expr_message: str = (
                        f"数据源: {source}\n\t"
                        f"表达式: {expr}\n\t"
                        f"实际值: {actual_value}\n\t"
                        f"操作符: {operation}\n\t"
                        f"预期值: {except_value}\n\t"
                        f"错误描述: {error_message}"
                    )
                    log_callback(f"【断言验证】异常: \n\t{expr_message}")
            validator_results.append({
                "name": name,
                "source": source,
                "expr": expr,
                "operation": operation,
                "except_value": resolved_except_value,
                "actual_value": actual_value,
                "success": success,
                "error": "" if success else error_message,
            })
        return validator_results

    @staticmethod
    def append_assert_validators(
            *,
            step_struct: Optional[Dict[str, Dict[str, Any]]],
            validator_results: List[Dict[str, Any]],
            response_text: Optional[str],
            response_json: Any,
            response_headers: Optional[Dict[str, Any]],
            response_cookies: Optional[Dict[str, Any]],
            session_variables_lookup: Optional[Dict[str, Any]],
            compare_fail_message: str = "实际值与预期值不满足指定操作符比较",
            finished_variables: Optional[Any] = None,
            is_core_engine: bool = False,
            log_callback: Optional[Callable[[str], None]] = None,
            body_source: str = "response json",
    ) -> None:
        """
        将数据驱动场景的assert_head/assert_body追加到validator_results，response_headers为None时跳过head断言。

        :param step_struct: 含assert_head/assert_body的数据驱动结构
        :param validator_results: 断言结果列表（原地追加）
        :param response_text: 响应正文
        :param response_json: 响应JSON
        :param response_headers: 响应头；None时跳过head断言
        :param response_cookies: 响应Cookie
        :param session_variables_lookup: 变量池字典
        :param compare_fail_message: 比较失败时的默认错误文案
        :param finished_variables: 期望值占位符解析上下文；None则不解析
        :param is_core_engine: 占位符解析模式
        :param log_callback: 可选日志回调
        :param body_source: 保留参数，当前未生效
        :return: None
        """
        if not isinstance(step_struct, dict):
            return

        def _resolve_expected(raw_expected: Any) -> Any:
            """若提供finished_variables，则对期望值做占位符解析。"""
            if finished_variables is None:
                return raw_expected
            return PlaceholderResolver.resolve_placeholders(
                value=raw_expected,
                logger_object=log_callback,
                is_core_engine=is_core_engine,
                finished_variables=finished_variables,
            )

        def _append_one(
                *,
                except_path: str,
                except_value: Any,
                source: str,
                expr: str,
                skip_error: Optional[str] = None,
        ) -> None:
            """追加一条断言结果；skip_error非空时直接记失败。"""
            resolved_except_value = _resolve_expected(except_value)
            if skip_error:
                validator_results.append({
                    "name": except_path,
                    "expr": except_path,
                    "source": source,
                    "operation": "等于",
                    "except_value": resolved_except_value,
                    "actual_value": None,
                    "success": False,
                    "error": skip_error,
                })
                return
            try:
                actual_value = Extractors.extract_from_source(
                    source=source,
                    expr=expr,
                    range_type="SOME",
                    index=None,
                    response_text=response_text,
                    response_json=response_json,
                    response_headers=response_headers,
                    response_cookies=response_cookies,
                    session_variables_lookup=session_variables_lookup,
                    operation_type="断言验证",
                )
                success = AssertionCompare.compare_assertion(
                    actual=actual_value,
                    operation="等于",
                    expected=resolved_except_value,
                )
                validator_results.append({
                    "name": except_path,
                    "expr": except_path,
                    "source": source,
                    "operation": "等于",
                    "except_value": resolved_except_value,
                    "actual_value": actual_value,
                    "success": success,
                    "error": "" if success else compare_fail_message,
                })
            except Exception as e:
                validator_results.append({
                    "name": except_path,
                    "expr": except_path,
                    "source": source,
                    "operation": "等于",
                    "except_value": resolved_except_value,
                    "actual_value": None,
                    "success": False,
                    "error": str(e),
                })

        # assert_head：response_headers 为 None 时跳过（TCP 无响应头）
        if response_headers is not None:
            for except_path, except_value in (step_struct.get("assert_head") or {}).items():
                if not except_path:
                    continue
                _append_one(
                    except_path=except_path,
                    except_value=except_value,
                    source="response headers",
                    expr=str(except_path).strip(),
                )

        for except_path, except_value in (step_struct.get("assert_body") or {}).items():
            if not except_path:
                continue
            expr = str(except_path).strip()
            # 根据表达式前缀自动判断提取来源：$. → JSONPath, ./ 或 // → XPath, 其他 → Text
            if expr.startswith("$."):
                detected_source = "response json"
            elif expr.startswith("./") or expr.startswith("//"):
                detected_source = "response xml"
            else:
                detected_source = "response text"
            skip_error: Optional[str] = None
            if detected_source == "response json" and response_json is None:
                skip_error = "响应不是JSON，无法进行JSONPath断言"
            elif detected_source == "response xml" and not response_text:
                skip_error = "响应不是有效的XML数据"
            elif detected_source == "response text" and not response_text:
                skip_error = "响应内容不是有效的Text数据"
            _append_one(
                except_path=except_path,
                except_value=except_value,
                source=detected_source,
                expr=expr,
                skip_error=skip_error,
            )
