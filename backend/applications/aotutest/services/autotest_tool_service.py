# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_tool_service
@DateTime: 2026/1/17 12:20
"""
from __future__ import annotations

from backend.applications.aotutest.services.autotest_dataset_loader import DatasetLoader
from backend.applications.aotutest.services.autotest_runtime.datagram.json_replace import JsonDatagram
from backend.applications.aotutest.services.autotest_runtime.datagram.xml_replace import XmlDatagram
from backend.applications.aotutest.services.autotest_runtime.exchange.assert_compare import AssertionCompare
from backend.applications.aotutest.services.autotest_runtime.exchange.assert_pipeline import AssertPipeline
from backend.applications.aotutest.services.autotest_runtime.exchange.extract_pipeline import ExtractPipeline
from backend.applications.aotutest.services.autotest_runtime.exchange.extractors import Extractors
from backend.applications.aotutest.services.autotest_runtime.exchange.pipeline import ExtractAssertPipeline
from backend.applications.aotutest.services.autotest_runtime.placeholders.functions import PlaceholderFunctions
from backend.applications.aotutest.services.autotest_runtime.placeholders.resolver import PlaceholderResolver
from backend.applications.aotutest.services.autotest_runtime.sandbox import (
    RE_PLACEHOLDER,
    RE_QUOTED_CONCAT,
    RE_QUOTED_PLACEHOLDER,
    USER_CODE_ALLOWED_IMPORT_ROOTS,
    USER_CODE_EXTRA_BUILTINS,
    safe_user_code_import,
)
from backend.applications.aotutest.services.autotest_runtime.util_kv import KvUtils
from backend.applications.aotutest.services.autotest_runtime.validation.executor_fields import ExecutorFieldsValidation
from backend.applications.aotutest.services.autotest_runtime.validation.step_tree import StepTreeValidation
from backend.applications.aotutest.services.autotest_runtime.validation.variable_flow import VariableFlowValidation

__all__ = [
    "AutoTestToolService",
    "RE_PLACEHOLDER",
    "RE_QUOTED_PLACEHOLDER",
    "RE_QUOTED_CONCAT",
    "USER_CODE_EXTRA_BUILTINS",
    "USER_CODE_ALLOWED_IMPORT_ROOTS",
    "safe_user_code_import",
]


class AutoTestToolService:
    """
    自动化测试工具服务门面（供步骤引擎与调试视图复用）。

    实现根据领域拆分至 autotest_runtime；本类仅转发，保持公开方法名与签名不变。
    """

    # --- 数据的平铺和分组转换 / 日志收集 ---
    list_to_dict = KvUtils.list_to_dict
    convert_list_to_dict_for_http = KvUtils.convert_list_to_dict_for_http
    get_value_from_list = KvUtils.get_value_from_list
    try_serialize_request_body = KvUtils.try_serialize_request_body
    format_step_error_message = KvUtils.format_step_error_message
    parse_cookie_header = KvUtils.parse_cookie_header
    build_session_lookup = KvUtils.build_session_lookup

    # --- 数据驱动 ---
    has_dataset_payload = DatasetLoader.has_dataset_payload
    load_dataset_for_request_step = DatasetLoader.load_dataset_for_request_step
    try_acquire_step_dataset = DatasetLoader.has_dataset_payload

    # --- 数据处理 ---
    replace_json_datagram = JsonDatagram.replace_json_datagram
    replace_xml_datagram = XmlDatagram.replace_xml_datagram

    # --- 提取 / 断言 ---
    extract_from_source = Extractors.extract_from_source
    run_extract_variables = ExtractPipeline.run_extract_variables
    run_assert_validators = AssertPipeline.run_assert_validators
    append_assert_validators = AssertPipeline.append_assert_validators
    run_extract_and_assert = ExtractAssertPipeline.run_extract_and_assert
    compare_assertion = AssertionCompare.compare_assertion

    # --- 算数和占位符解析 ---
    execute_func_string_single = PlaceholderFunctions.execute_func_string_single
    resolve_placeholders = PlaceholderResolver.resolve_placeholders
    resolve_xml_placeholders = PlaceholderResolver.resolve_xml_placeholders

    # --- 执行器验证 ---
    validate_step_tree_structure = StepTreeValidation.validate_step_tree_structure
    validate_executor_fields = ExecutorFieldsValidation.validate_executor_fields
    validate_variable_flow = VariableFlowValidation.validate_variable_flow
    collect_session_variables = VariableFlowValidation.collect_session_variables
