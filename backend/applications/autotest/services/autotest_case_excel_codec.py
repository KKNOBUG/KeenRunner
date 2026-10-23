# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_case_excel_codec.py
@DateTime: 2026/10/22
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterator, List, Optional, Tuple

from backend.enums import AutoTestAssertionOperation, AutoTestReqArgsType

__all__ = ["CaseScriptCodec"]


class CaseScriptCodec:
    """
    公共接口脚本模板文本协议编解码器：请求头/变量/请求体/提取/断言五类多行文本列的对称实现。

    协议约定（导出编码与导入解码必须成对维护，任一侧变更即破坏往返契约）：
    - 键值列(请求头/变量/表单类请求体)：每行 key:value:描述;，描述段恒输出；
    - 提取列：变量名:提取来源:提取范围[:提取表达式[:索引]];
    - 断言列：断言名称:断言对象:断言表达式:匹配规则[:预期值];，为空/不为空规则不输出预期值；
    - 行尾分号为英文分号，空行忽略，非法行按列名收集可读错误。
    """

    # ==================== 常量：文本协议字段与取值集合 ====================
    # 提取范围：与模板填写指引、历史数据保持中文原文
    SCOPE_ALL = "整个返回数据"
    SCOPE_SOME = "提取部分"
    EXTRACT_SCOPES = frozenset({"ALL", "SOME"})
    FORM_FIELD_BY_ARGS_TYPE: Dict[str, str] = {
        AutoTestReqArgsType.PARAMS.value: "request_params",
        AutoTestReqArgsType.FORM_DATA.value: "request_form_data",
        AutoTestReqArgsType.X_WWW_FORM_URLENCODED.value: "request_form_urlencoded",
    }
    # 请求体解析产出的步骤字段全集：未命中的字段一律置 None，保证导入更新时可清空旧值
    BODY_STEP_FIELDS: Tuple[str, ...] = (
        "request_body",
        "request_text",
        "request_params",
        "request_form_data",
        "request_form_urlencoded",
    )
    EXTRACT_SOURCES = frozenset({
        "Request Form-Data",
        "Request Text",
        "Request Json",
        "Request XML",
        "Request Headers",
        "Request Cookie",
        "Response Text",
        "Response Json",
        "Response XML",
        "Response Headers",
        "Response Cookie",
    })
    ASSERT_SOURCES = frozenset({
        "Request Form-Data",
        "Request Text",
        "Request Json",
        "Request XML",
        "Request Headers",
        "Request Cookie",
        "Response Text",
        "Response Json",
        "Response XML",
        "Response Headers",
        "Response Cookie",
        "变量池",
    })
    ASSERT_OPERATIONS = frozenset(e.value for e in AutoTestAssertionOperation)
    ASSERT_NO_EXPECTED_OPERATIONS = frozenset({
        AutoTestAssertionOperation.IS_EMPTY.value,
        AutoTestAssertionOperation.NOT_EMPTY.value,
    })

    # ==================== 通用工具 ====================

    @staticmethod
    def _get(item: Any, name: str, default: Any = None) -> Any:
        """兼容dict/schema对象字段读取。"""
        return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)

    @staticmethod
    def _enum_text(raw: Any) -> str:
        """CharEnum/字符串 → 枚举值文本。"""
        if raw is None:
            return ""
        return getattr(raw, "value", raw) or ""

    @staticmethod
    def _iter_lines(text: str) -> Iterator[Tuple[str, str]]:
        """逐行产出(去空白原文, 去尾分号片段)；空行剔除，原文用于错误定位保持导入侧提示一致。"""
        for raw in str(text or "").splitlines():
            trimmed = raw.strip()
            if not trimmed:
                continue
            yield trimmed, trimmed[:-1] if trimmed.endswith(";") else trimmed

    # ==================== 编码：结构化字段 → 多行文本 ====================

    @classmethod
    def encode_kv_lines(cls, kv_list: Optional[List[Any]], *, column: str, problems: List[str]) -> str:
        """
        将[{key,value,desc}]转为多行key:value:desc;文本，并向problems追加往返不安全项。

        描述段恒输出保证"最后一个冒号后是描述"恒成立，值内冒号即可安全往返；
        key含冒号/换行、值或描述含换行、描述含冒号仍无法安全往返，予以拦截。

        :param kv_list: 键值列表
        :param column: 列名，仅用于错误定位
        :param problems: 往返安全检测问题收集列表
        :return: 多行文本
        """
        lines: List[str] = []
        for item in kv_list or []:
            key = str(cls._get(item, "key") or "").strip()
            if not key:
                continue
            raw_value = cls._get(item, "value")
            value = "" if raw_value is None else str(raw_value)
            desc = str(cls._get(item, "desc") or "").strip()
            if ":" in key:
                problems.append(f"[{column}] {key} 的键包含冒号")
            if "\n" in key:
                problems.append(f"[{column}] {key} 的键包含换行")
            if "\n" in value:
                problems.append(f"[{column}] {key} 的值包含换行")
            if ":" in desc:
                problems.append(f"[{column}] {key} 的描述包含冒号")
            if "\n" in desc:
                problems.append(f"[{column}] {key} 的描述包含换行")
            lines.append(f"{key}:{value}:{desc};")
        return "\n".join(lines)

    @classmethod
    def encode_extract_lines(cls, extract_list: Optional[List[Any]]) -> str:
        """
        将提取配置转为多行文本；名称为空或来源缺失的项跳过（与导入校验口径一致）。

        :param extract_list: 提取配置列表
        :return: 多行文本
        """
        lines: List[str] = []
        for item in extract_list or []:
            name = str(cls._get(item, "name") or "").strip()
            source = str(cls._get(item, "source") or "").strip()
            if not name or not source:
                continue
            if cls._get(item, "scope") == "ALL":
                lines.append(f"{name}:{source}:{cls.SCOPE_ALL};")
                continue
            expr = str(cls._get(item, "expr") or "").strip()
            segment = f"{name}:{source}:{cls.SCOPE_SOME}:{expr}"
            index = cls._get(item, "index")
            if index is not None:
                segment += f":{int(index)}"
            lines.append(segment + ";")
        return "\n".join(lines)

    @classmethod
    def encode_assert_lines(cls, assert_list: Optional[List[Any]]) -> str:
        """
        将断言配置转为多行文本；名称为空或来源/表达式/匹配规则缺失的项跳过。

        :param assert_list: 断言配置列表
        :return: 多行文本
        """
        lines: List[str] = []
        for item in assert_list or []:
            name = str(cls._get(item, "name") or "").strip()
            source = str(cls._get(item, "source") or "").strip()
            expr = str(cls._get(item, "expr") or "").strip()
            operation = str(cls._get(item, "operation") or "").strip()
            if not name or not source or not expr or not operation:
                continue
            segment = f"{name}:{source}:{expr}:{operation}"
            if operation not in cls.ASSERT_NO_EXPECTED_OPERATIONS:
                raw_except = cls._get(item, "except_value")
                segment += f":{'' if raw_except is None else raw_except}"
            lines.append(segment + ";")
        return "\n".join(lines)

    @classmethod
    def encode_step_body(cls, step: Any) -> str:
        """非表单类请求体序列化；调用方已拦截表单类，此处仅处理JSON/XML/RAW。"""
        args = cls._enum_text(getattr(step, "request_args_type", None))
        if args == AutoTestReqArgsType.JSON.value:
            body = getattr(step, "request_body", None)
            return json.dumps(body, ensure_ascii=False) if isinstance(body, dict) else ""
        if args in (AutoTestReqArgsType.XML.value, AutoTestReqArgsType.RAW.value):
            return getattr(step, "request_text", None) or ""
        return ""

    # ==================== 解码：多行文本 → 结构化字段 ====================

    @classmethod
    def decode_kv_lines(cls, text: str, column: str) -> Tuple[List[Dict[str, str]], List[str]]:
        """
        解析多行key:value:desc;文本；描述非必填，值内允许冒号。

        描述取最后一个冒号后的片段：导出侧恒输出描述段，因此值内冒号可安全还原；
        描述本身含冒号无法区分，导出侧已拦截。

        :param text: 多行文本
        :param column: 列名，仅用于错误定位
        :return: (键值列表或空列表, 错误列表)
        """
        items: List[Dict[str, str]] = []
        errors: List[str] = []
        for raw, segment in cls._iter_lines(text):
            parts = segment.split(":")
            key = parts[0].strip()
            if not key:
                errors.append(f"[{column}] {raw} 缺少key")
                continue
            if len(parts) == 1:
                value, desc = "", ""
            elif len(parts) == 2:
                value, desc = parts[1], ""
            else:
                value, desc = ":".join(parts[1:-1]), parts[-1].strip()
            items.append({"key": key, "value": value, "desc": desc})
        return items, errors

    @classmethod
    def decode_extract_lines(cls, text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        解析多行提取配置文本。

        "提取部分"允许表达式内含冒号，末尾纯整数段视为索引（与导出侧追加索引的写法对称）。

        :param text: 多行文本
        :return: (提取配置列表或空列表, 错误列表)
        """
        items: List[Dict[str, Any]] = []
        errors: List[str] = []
        for raw, segment in cls._iter_lines(text):
            parts = segment.split(":")
            if len(parts) < 3:
                errors.append(f"[提取] {raw} 格式错误")
                continue
            name, source, scope = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if not name:
                errors.append(f"[提取] {raw} 缺少变量名")
                continue
            if source not in cls.EXTRACT_SOURCES:
                errors.append(f"[提取] 提取来源 {source} 不被允许")
                continue
            if scope == cls.SCOPE_ALL:
                if len(parts) > 3:
                    errors.append(f"[提取] {raw} 范围为[整个返回数据]时, 不允许填写提取表达式")
                    continue
                items.append({"name": name, "source": source, "expr": "", "scope": "ALL", "index": None})
                continue
            if scope != cls.SCOPE_SOME:
                errors.append(f"[提取] 提取范围 {scope} 不被允许")
                continue
            tail = parts[3:]
            index_val: Optional[int] = None
            if len(tail) >= 2 and re.fullmatch(r"-?\d+", tail[-1].strip()):
                index_val = int(tail[-1].strip())
                tail = tail[:-1]
            expr = ":".join(tail).strip()
            if not expr:
                errors.append(f"[提取] {raw} 缺少提取表达式")
                continue
            items.append({"name": name, "source": source, "expr": expr, "scope": "SOME", "index": index_val})
        return items, errors

    @classmethod
    def decode_assert_lines(cls, text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        解析多行断言配置文本。

        预期值允许含冒号（取第5段起拼接）；为空/不为空忽略预期值并归一为空字符串。

        :param text: 多行文本
        :return: (断言配置列表或空列表, 错误列表)
        """
        items: List[Dict[str, Any]] = []
        errors: List[str] = []
        for raw, segment in cls._iter_lines(text):
            parts = segment.split(":")
            if len(parts) < 4:
                errors.append(f"[断言] {raw} 格式错误")
                continue
            name, source, expr, operation = (
                parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip(),
            )
            if not name:
                errors.append(f"[断言] {raw} 缺少断言名称")
                continue
            if source not in cls.ASSERT_SOURCES:
                errors.append(f"[断言] 断言对象 {source} 不被允许")
                continue
            if not expr:
                errors.append(f"[断言] {raw} 缺少断言表达式")
                continue
            if operation not in cls.ASSERT_OPERATIONS:
                errors.append(f"[断言] 匹配规则 {operation} 不被允许")
                continue
            # 为空/不为空忽略预期值(兼容旧格式尾冒号，统一归一为空)；其余规则预期值必填且可含冒号
            if operation in cls.ASSERT_NO_EXPECTED_OPERATIONS:
                except_value = ""
            else:
                except_value = ":".join(parts[4:])
                if not except_value.strip():
                    errors.append(f"[断言] 匹配规则为[{operation}]时, 必须填写预期值")
                    continue
            items.append({
                "name": name, "source": source, "expr": expr,
                "operation": operation, "except_value": except_value,
            })
        return items, errors

    @classmethod
    def decode_body(cls, args_type: str, body_text: str) -> Tuple[Dict[str, Any], List[str]]:
        """
        按请求体类型解析请求体列，产出步骤落库字段；未命中字段一律为None。

        JSON必须是对象结构（列表/标量拒绝），XML/RAW原样写入request_text，
        表单类按键值文本解析；none类型要求请求体列为空。

        :param args_type: 请求体类型
        :param body_text: 请求体单元格文本
        :return: (请求体字段字典, 错误列表)
        """
        result: Dict[str, Any] = {field: None for field in cls.BODY_STEP_FIELDS}
        errors: List[str] = []
        if args_type == AutoTestReqArgsType.NONE.value:
            if body_text:
                errors.append("请求体类型为[none]时, 请求体不允许填写")
            return result, errors
        if not body_text:
            errors.append(f"请求体类型为[{args_type}]时, 请求体不允许为空")
            return result, errors
        if args_type == AutoTestReqArgsType.JSON.value:
            try:
                parsed = json.loads(body_text)
            except ValueError as e:
                errors.append(f"解析[请求体]时发生错误: {e}")
                return result, errors
            if not isinstance(parsed, dict):
                errors.append("解析[请求体]时发生错误: 请求体参数必须为对象结构, 不允许列表嵌套结构")
                return result, errors
            result["request_body"] = parsed
        elif args_type in (AutoTestReqArgsType.XML.value, AutoTestReqArgsType.RAW.value):
            result["request_text"] = body_text
        elif args_type in cls.FORM_FIELD_BY_ARGS_TYPE:
            items, kv_errors = cls.decode_kv_lines(body_text, "请求体")
            result[cls.FORM_FIELD_BY_ARGS_TYPE[args_type]] = items or None
            errors.extend(kv_errors)
        return result, errors

    # ==================== 往返安全校验 ====================

    @classmethod
    def check_extract_roundtrip(cls, extract_list: Optional[List[Any]]) -> List[str]:
        """提取列往返安全检测：冒号/换行会破坏多行文本编解码，导出前拦截。"""
        problems: List[str] = []
        for item in extract_list or []:
            name = str(cls._get(item, "name") or "")
            source = str(cls._get(item, "source") or "").strip()
            scope = str(cls._get(item, "scope") or "").strip()
            expr = str(cls._get(item, "expr") or "")
            if ":" in name:
                problems.append(f"[提取] {name} 的变量名包含冒号")
            if "\n" in name:
                problems.append(f"[提取] {name} 的变量名包含换行")
            if ":" in expr:
                problems.append(f"[提取] {name} 的表达式包含冒号")
            if "\n" in expr:
                problems.append(f"[提取] {name} 的表达式包含换行")
            if scope not in cls.EXTRACT_SCOPES:
                problems.append(f"[提取] {name} 提取范围 {scope} 不被允许")
            elif scope == "SOME" and not expr.strip():
                problems.append(f"[提取] {name} 提取范围为[提取部分]时, 必须填写提取表达式")
            if source not in cls.EXTRACT_SOURCES:
                problems.append(f"[提取] {name} 提取来源 {source} 不被允许")
        return problems

    @classmethod
    def check_assert_roundtrip(cls, assert_list: Optional[List[Any]]) -> List[str]:
        """断言列往返安全检测：冒号/换行会破坏多行文本编解码，导出前拦截。"""
        problems: List[str] = []
        for item in assert_list or []:
            name = str(cls._get(item, "name") or "")
            expr = str(cls._get(item, "expr") or "")
            operation = str(cls._get(item, "operation") or "").strip()
            except_value = str(cls._get(item, "except_value") or "")
            if ":" in name:
                problems.append(f"[断言] {name} 的名称包含冒号")
            if "\n" in name:
                problems.append(f"[断言] {name} 的名称包含换行")
            if ":" in expr:
                problems.append(f"[断言] {name} 的表达式包含冒号")
            if "\n" in expr:
                problems.append(f"[断言] {name} 的表达式包含换行")
            if "\n" in except_value:
                problems.append(f"[断言] {name} 的预期值包含换行")
            if operation not in cls.ASSERT_OPERATIONS:
                problems.append(f"[断言] {name} 匹配规则 {operation} 不被允许")
            elif operation not in cls.ASSERT_NO_EXPECTED_OPERATIONS and not except_value.strip():
                problems.append(f"[断言] {name} 匹配规则 {operation} 需要填写预期值")
        return problems
