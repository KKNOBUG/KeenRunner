# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_tool_service.py
@DateTime: 2026/1/17 12:20
"""
from __future__ import annotations

from typing import Any, Optional, Union

from backend.applications.autotest.services.autotest_dataset_loader import DatasetLoader
from backend.applications.autotest.services.autotest_runtime.datagram.json_replace import JsonDatagram
from backend.applications.autotest.services.autotest_runtime.datagram.xml_replace import XmlDatagram
from backend.applications.autotest.services.autotest_runtime.exchange.assert_compare import AssertionCompare
from backend.applications.autotest.services.autotest_runtime.exchange.assert_pipeline import AssertPipeline
from backend.applications.autotest.services.autotest_runtime.exchange.extract_pipeline import ExtractPipeline
from backend.applications.autotest.services.autotest_runtime.exchange.extractors import Extractors
from backend.applications.autotest.services.autotest_runtime.exchange.pipeline import ExtractAssertPipeline
from backend.applications.autotest.services.autotest_runtime.placeholders.functions import PlaceholderFunctions
from backend.applications.autotest.services.autotest_runtime.placeholders.resolver import PlaceholderResolver
from backend.applications.autotest.services.autotest_runtime.util_kv import KvUtils
from backend.applications.autotest.services.autotest_runtime.validation.executor_fields import ExecutorFieldsValidation
from backend.applications.autotest.services.autotest_runtime.validation.step_tree import StepTreeValidation
from backend.applications.autotest.services.autotest_runtime.validation.variable_flow import VariableFlowValidation
from backend.enums import AutoTestReqArgsType

__all__ = ["AutoTestToolService"]


class AutoTestToolService:
    """
    自动化测试工具服务门面（供步骤引擎与调试视图复用）。

    实现根据领域拆分至 autotest_runtime；本类只保留执行链实际消费的稳定入口，并提供跨模块共用的报文类型判定。
    """

    # --- 数据的平铺和分组转换 / 日志收集 ---
    list_to_dict = KvUtils.list_to_dict
    convert_list_to_dict_for_http = KvUtils.convert_list_to_dict_for_http
    merge_mapping_dicts = KvUtils.merge_mapping_dicts
    get_item_from_list = KvUtils.get_item_from_list
    try_serialize_request_body = KvUtils.try_serialize_request_body
    format_step_error_message = KvUtils.format_step_error_message
    parse_cookie_header = KvUtils.parse_cookie_header
    build_session_lookup = KvUtils.build_session_lookup

    # --- 数据驱动 ---
    has_dataset_payload = DatasetLoader.has_dataset_payload
    load_dataset_for_request_step = DatasetLoader.load_dataset_for_request_step

    # --- 报文类型判定 ---
    @staticmethod
    def looks_like_xml_payload(value: Any) -> bool:
        """
        判断报文文本是否以XML起始标记开头（兼容BOM与前后空白）。

        :param value: 候选报文
        :return: 疑似XML返回True
        """
        if not isinstance(value, str):
            return False
        return value.lstrip("\ufeff \t\r\n").startswith("<")

    @classmethod
    def extract_xml_payload_text(cls, request_text: Any, request_body: Any) -> str:
        """
        提取步骤的XML报文本：优先request_text，缺失时兼容字符串型request_body。

        :param request_text: 文本报文
        :param request_body: 对象/字符串报文
        :return: XML文本；非XML或为空时返回空串
        """
        for value in (request_text, request_body):
            if cls.looks_like_xml_payload(value):
                return value.lstrip("\ufeff \t\r\n")
        return ""

    @classmethod
    def resolve_datagram_is_xml(
            cls,
            args_type: Optional[Union[AutoTestReqArgsType, str]],
            request_text: Optional[str],
            request_body: Any,
    ) -> bool:
        """
        判定请求报文是否按XML处理（HTTP/TCP数据驱动共用同一口径）。

        显式XML/JSON类型优先；未明确类型时，按request_text或字符串型request_body的内容嗅探。

        :param args_type: 请求体类型
        :param request_text: 文本报文
        :param request_body: 对象/字符串报文
        :return: 按XML处理返回True
        """
        args_value = str(getattr(args_type, "value", args_type) or "").strip().lower()
        if args_value == AutoTestReqArgsType.XML.value:
            return True
        if args_value == AutoTestReqArgsType.JSON.value:
            return False
        return bool(cls.extract_xml_payload_text(request_text, request_body))

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
