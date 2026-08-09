# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : util_kv.py
@DateTime: 2025/11/9 11:58
"""
from __future__ import annotations

import traceback
from datetime import datetime
from typing import Any, Dict, Optional, Sequence

import orjson

from backend.applications.aotutest.schemas.autotest_step_schema import (
    AutoTestStepTreeUpdateItem,
    StepVariablesBase,
)


class KvUtils:
    """变量列表与HTTP键值转换、会话查找表及错误消息格式化。"""

    @classmethod
    def _key_value_list_to_dict(cls, items: Sequence[StepVariablesBase], *, skip_if_no_value: bool = False) -> Dict[str, Any]:
        """
        将StepVariablesBase列表平铺为Dict[str, Any]。

        :param items: 变量项序列
        :param skip_if_no_value: 为True时跳过value为None的项
        :return: key -> value字典
        """
        if not items:
            return {}
        result: Dict[str, Any] = {}
        for item in items:
            if not isinstance(item, StepVariablesBase):
                raise TypeError(f"变量项必须为 StepVariablesBase，得到 {type(item).__name__}")
            if skip_if_no_value and item.value is None:
                continue
            key: str = item.key
            if key:
                result[key] = item.value
        return result

    @classmethod
    def list_to_dict(cls, variable_list: Sequence[StepVariablesBase]) -> Dict[str, Any]:
        """
        将StepVariablesBase列表转为name -> value字典, 供Python代码命名空间使用，会跳过value为None的变量。

        :param variable_list: 变量模型列表
        :return: 键为变量名、值为变量值的字典
        """
        items = list(variable_list) if variable_list is not None else []
        return cls._key_value_list_to_dict(items, skip_if_no_value=True)

    @classmethod
    def convert_list_to_dict_for_http(cls, data: Any) -> Dict[str, Any]:
        """
        将HTTP步骤中的key/value列表（列表项优先为StepVariablesBase）转为字典。
        历史JSON仍为dict时在边界model_validate后应已为模型，此处仅作有限兼容。

        :param data: key/value列表或空
        :return: 请求参数字典
        """
        if not data or not isinstance(data, list):
            return {}
        result: Dict[str, Any] = {}
        for item in data:
            if isinstance(item, StepVariablesBase):
                if item.key:
                    result[item.key] = item.value
            elif isinstance(item, dict) and item.get("key") is not None:
                result[item["key"]] = item.get("value")
        return result

    @staticmethod
    def get_value_from_list(variables: Optional[Sequence[StepVariablesBase]], name: str) -> Any:
        """
        从StepVariablesBase列表中取key为name的项的value。

        :param variables: 变量列表
        :param name: 变量名
        :return: 变量值；未找到时返回None
        """
        if variables is None:
            return None
        for variable in variables:
            if isinstance(variable, StepVariablesBase) and getattr(variable, "key", None) and variable.key == name:
                return variable.value
        return None

    @staticmethod
    def try_serialize_request_body(raw: Any) -> Any:
        """
        将步骤中的request_body规范为对象：JSON字符串尽量解析为dict，否则保持原样，空字符串返回{}。

        :param raw: 原始request_body
        :return: 解析后的对象或原值
        """
        if isinstance(raw, str):
            try:
                return orjson.loads(raw) if raw.strip() else {}
            except (TypeError, orjson.JSONDecodeError):
                return raw
        return raw

    @classmethod
    def format_step_error_message(
            cls,
            step: AutoTestStepTreeUpdateItem,
            exception: Exception,
            is_child_step: bool = False,
            offset_message: str = ""
    ) -> str:
        """
        格式化步骤执行失败信息, 供步骤引擎中各类执行器统一使用。

        :param step: 步骤模型
        :param exception: 捕获的异常
        :param is_child_step: 是否为子步骤失败
        :param offset_message: 附加偏移说明（如数据库第N条操作）
        :return: 格式化后的多行错误字符串
        """
        message: str = "【子步骤】" if is_child_step else "【根步骤】"
        offset_message: str = f", {offset_message}" if offset_message else ""
        case_id = step.case_id
        step_id = step.step_id
        step_no = step.step_no
        step_code = step.step_code
        step_name = step.step_name
        step_type = step.step_type
        return (
            f"{message}执行失败{offset_message}: \n\t"
            f"用例ID: {case_id}\n\t"
            f"步骤ID: {step_id}\n\t"
            f"步骤序号: {step_no}\n\t"
            f"步骤标识: {step_code}\n\t"
            f"步骤名称: {step_name}\n\t"
            f"步骤类型: {step_type}\n\t"
            f"错误描述: {exception}\n\t"
            f"错误类型: {type(exception).__name__}\n\t"
            f"错误时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\t"
            f"错误回溯: {traceback.format_exc()}"
        )

    @staticmethod
    def parse_cookie_header(headers: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """
        从请求头Cookie字段解析name -> value字典。

        :param headers: 请求头映射；键名大小写不敏感匹配Cookie
        :return: Cookie名到值的字典；无Cookie或非法输入时返回空字典
        """
        if not headers or not isinstance(headers, dict):
            return {}
        cookie_raw: Any = None
        for key, value in headers.items():
            if str(key).lower() == "cookie":
                cookie_raw = value
                break
        if cookie_raw is None:
            return {}
        if isinstance(cookie_raw, dict):
            return {str(k): "" if v is None else str(v) for k, v in cookie_raw.items()}
        cookie_text = str(cookie_raw).strip()
        if not cookie_text:
            return {}
        parsed: Dict[str, str] = {}
        for part in cookie_text.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            name, _, value = part.partition("=")
            name = name.strip()
            if name:
                parsed[name] = value.strip()
        return parsed

    @classmethod
    def build_session_lookup(
            cls,
            defined_variables: Optional[Sequence[StepVariablesBase]] = None,
            session_variables: Optional[Sequence[StepVariablesBase]] = None,
    ) -> Dict[str, Any]:
        """
        合并defined / session变量为提取与断言用的查找字典（session覆盖同名defined）。

        :param defined_variables: 用例/步骤定义变量
        :param session_variables: 会话变量（优先级更高）
        :return: name -> value字典
        """
        lookup: Dict[str, Any] = cls.list_to_dict(defined_variables or [])
        lookup.update(cls.list_to_dict(session_variables or []))
        return lookup
