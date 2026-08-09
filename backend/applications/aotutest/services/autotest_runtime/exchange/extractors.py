# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : extractors.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, Optional, Union
from xml.etree import ElementTree

from jsonpath_ng import parse as jsonpath_parse

from backend.applications.aotutest.services.autotest_runtime.context import ExchangeContext
from backend.applications.aotutest.services.autotest_runtime.util_kv import KvUtils
from backend.common.xpath_utils import XPathUtils


class Extractors:
    """JSON/XML/Text/Headers/Cookies/变量池提取实现与统一入口。"""

    @classmethod
    def _normalize_extract_source(cls, source: Optional[str]) -> str:
        """统一提取来源别名（兼容Header/Headers、Cookie/Cookies单复数）。"""
        source_strip_lower: str = (source or "").strip().lower()
        aliases = {
            "response header": "response headers",
            "response cookie": "response cookies",
            "request header": "request headers",
            "request cookie": "request cookies",
        }
        return aliases.get(source_strip_lower, source_strip_lower)

    @classmethod
    def _extract_json_payload(
            cls,
            *,
            data: Optional[Union[list, dict]],
            expr: Optional[str],
            range_type: str,
            index: Optional[Any],
            operation_type: str,
            empty_message: str,
    ) -> Any:
        """
        从JSON对象根据ALL/SOME与可选index提取。

        :param data: 响应或请求JSON（dict/list）
        :param expr: JSONPath；SOME模式必填
        :param range_type: all或some（已小写）
        :param index: 多匹配列表下标；越界抛ValueError
        :param operation_type: 错误信息前缀（变量提取/断言验证）
        :param empty_message: data为空时的错误文案
        :return: 提取值
        """
        if data is None:
            raise ValueError(empty_message)
        if range_type == "all":
            return data
        if not expr:
            raise ValueError(f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是有效的JSONPath表达式")
        try:
            extract_value = Extractors._resolve_json_path(data=data, expr=expr)
        except Exception as e:
            raise ValueError(str(e)) from e
        if isinstance(extract_value, list) and index is not None:
            try:
                index_int = int(index)
            except (ValueError, TypeError) as e:
                raise ValueError(f"【{operation_type}】参数[index]必须是整数类型, 错误描述: {e}") from e
            if index_int >= len(extract_value):
                raise ValueError(
                    f"【{operation_type}】数组越界, "
                    f"给定索引[{index_int}]不可大于数组长度[{len(extract_value)}]"
                )
            return extract_value[index_int]
        return extract_value

    @classmethod
    def _extract_xml_payload(
            cls,
            *,
            text: Optional[str],
            expr: Optional[str],
            range_type: str,
            index: Optional[Any],
            operation_type: str,
            empty_message: str,
            invalid_xml_message: str,
    ) -> Any:
        """
        从XML文本根据XPath与可选index提取元素文本或序列化片段。

        :param text: XML字符串
        :param expr: XPath；SOME模式必填
        :param range_type: all或some
        :param index: 多匹配下标；缺省取最后一个
        :param operation_type: 错误信息前缀
        :param empty_message: 正文为空时的错误文案
        :param invalid_xml_message: 解析失败时的错误文案前缀
        :return: 元素text或tostring结果；ALL时返回原文
        """
        if not text:
            raise ValueError(empty_message)
        if range_type == "all":
            return text
        if not expr:
            raise ValueError(f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是有效的XPath表达式")
        try:
            xml_root = ElementTree.fromstring(text)
            # 兼容默认命名空间：无 xmlns 走原路径，有 xmlns 时自动回退 {*} 匹配
            elements = XPathUtils.findall(xml_root, expr)
            if not elements:
                raise ValueError(f"【{operation_type}】XPath表达式[{expr}]未匹配到元素")
            if index is not None:
                try:
                    index_int = int(index)
                except (ValueError, TypeError) as e:
                    raise ValueError(f"【{operation_type}】参数[index]必须是整数类型, 错误描述: {e}") from e
                if index_int >= len(elements):
                    raise ValueError(
                        f"【{operation_type}】数组越界, "
                        f"给定索引[{index_int}]不可大于数组长度[{len(elements)}]"
                    )
                element = elements[index_int]
                return element.text if element.text else ElementTree.tostring(element, encoding="unicode")
            element = elements[-1]
            return element.text if element.text else ElementTree.tostring(element, encoding="unicode")
        except ElementTree.ParseError as e:
            raise ValueError(f"{invalid_xml_message}, 错误描述: {e}") from e
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"【{operation_type}】XPath表达式[{expr}]执行失败, 错误: {e}") from e

    @classmethod
    def _extract_text_payload(
            cls,
            *,
            text: Optional[str],
            expr: Optional[str],
            range_type: str,
            index: Optional[Any] = None,
            operation_type: str = "变量提取",
            empty_message: str = "内容为空",
    ) -> Any:
        """
        从纯文本根据正则提取匹配串，可选指定分组。

        :param text: 请求或响应正文
        :param expr: 正则表达式；SOME模式必填
        :param range_type: all或some
        :param index: 分组编号；None或0取整个匹配串(group(0))，正整数N取第N个捕获分组(group(N))，
            负数-1取最后一个分组、-2取倒数第二个分组，以此类推（与JSON/XML负索引语义一致）
        :param operation_type: 错误信息前缀
        :param empty_message: 正文为空时的错误文案
        :return: 匹配到的分组值；ALL时返回原文
        """
        if not text:
            raise ValueError(empty_message)
        if range_type == "all":
            return text
        if not expr:
            raise ValueError(f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是有效的正则表达式")
        try:
            match = re.search(expr, text, re.S)
            if not match:
                raise ValueError(f"【{operation_type}】正则表达式[{expr}]未匹配到内容")
            if index is None or int(index) == 0:
                return match.group(0)
            index_int = int(index)
            group_count = len(match.groups())
            if index_int < 0:
                # 负数索引：-1 取最后一个分组，-2 取倒数第二个，以此类推
                actual_index = group_count + index_int + 1
                if actual_index <= 0:
                    raise ValueError(
                        f"【{operation_type}】分组索引[{index_int}]超出范围, 正则表达式共有[{group_count}]个分组(可用范围: -{group_count}~-1 或 0~{group_count})"
                    )
                return match.group(actual_index)
            if index_int > group_count:
                raise ValueError(
                    f"【{operation_type}】分组索引[{index_int}]超出范围, 正则表达式共有[{group_count}]个分组(可用范围: 0~{group_count})"
                )
            return match.group(index_int)
        except re.error as e:
            raise ValueError(f"【{operation_type}】正则表达式执行失败, 错误描述: {e}") from e

    @classmethod
    def _extract_mapping_payload(
            cls,
            *,
            data: Optional[Dict[str, Any]],
            expr: Optional[str],
            range_type: str,
            operation_type: str,
            empty_message: str,
            miss_message: str,
    ) -> Any:
        """
        从Headers/Cookies等映射根据JSONPath提取。

        :param data: 映射字典
        :param expr: JSONPath；SOME模式必填
        :param range_type: all或some
        :param operation_type: 错误信息前缀
        :param empty_message: 映射为空时的错误文案
        :param miss_message: 提取异常消息为空时的兜底文案
        :return: 提取值；ALL时返回整个映射
        """
        if not data:
            raise ValueError(empty_message)
        if range_type == "all":
            return data
        if not expr:
            raise ValueError(f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是有效JSONPath表达式")
        try:
            return Extractors._resolve_json_path(data=data, expr=expr)
        except Exception as e:
            raise ValueError(str(e) or miss_message) from e

    @classmethod
    def _resolve_json_path(cls, data: Any, expr: str) -> Any:
        """
        使用JSONPath表达式从data中取值，支持标准JSONPath(如$.data[0].id、$.list[*].name)。

        :param data: 待取值的对象(dict/list或嵌套结构)
        :param expr: 非空字符串，合法JSONPath表达式(如$.a.b、$.data[0].id、$.items[*].id)
        :return: 单匹配时返回该值，多匹配时返回值的列表
        """
        expr = str(expr).strip()
        if not expr:
            raise ValueError(f"【JSONPath表达式】必须是非空字符串")
        if not expr.startswith("$"):
            raise ValueError(f"【JSONPath表达式】必须以$.字符开头")
        if data is None:
            raise ValueError(f"【JSONPath表达式】数据源不允许为空")

        try:
            json_path_expr = jsonpath_parse(expr)
        except Exception as e:
            raise ValueError(f"【JSONPath表达式】执行失败, {e}") from e

        json_path_matches = json_path_expr.find(data)
        if not json_path_matches:
            raise ValueError(f"【JSONPath表达式】匹配失败, 请检查数据源是否包含表达式")

        values = [match.value for match in json_path_matches]
        return values[0] if len(values) == 1 else values

    @classmethod
    def extract_from_source(
            cls,
            *,
            source: str,
            expr: Optional[str],
            range_type: Optional[str] = "SOME",
            index: Optional[Any] = None,
            response_text: Optional[str] = None,
            response_json: Optional[Union[list, dict]] = None,
            response_headers: Optional[Dict[str, Any]] = None,
            response_cookies: Optional[Dict[str, Any]] = None,
            request_text: Optional[str] = None,
            request_json: Optional[Union[list, dict]] = None,
            request_headers: Optional[Dict[str, Any]] = None,
            request_cookies: Optional[Dict[str, Any]] = None,
            session_variables_lookup: Optional[Dict[str, Any]] = None,
            operation_type: str = "变量提取",
    ) -> Any:
        """
        从source指定来源根据表达式提取单个值（HTTP调试与步骤引擎共用）。

        标准来源（如response/request json、xml、text、headers、cookies、
        session_variables/变量池）经规范化别名后查EXTRACTORS注册表执行。
        未命中注册表时，若response_json为DB/Redis操作结果列表，则根据
        source与项内variable_name匹配后走JSON提取回退逻辑，回退路径同样支持ALL/SOME。

        :param source: 来源类型或DB/Redis的variable_name；支持Header/Cookie单复数别名
        :param expr: 提取表达式（JSONPath/XPath/正则）；SOME模式通常必填
        :param range_type: ALL返回整段数据，SOME（默认）根据expr取值
        :param index: 多匹配结果为列表时的下标；越界抛ValueError
        :param response_text: 响应正文
        :param response_json: 响应JSON，或DB/Redis的List[Dict]操作结果
        :param response_headers: 响应头
        :param response_cookies: 响应Cookie
        :param request_text: 请求正文
        :param request_json: 请求JSON
        :param request_headers: 请求头；当request_cookies为None时用于解析Cookie
        :param request_cookies: 请求Cookie映射
        :param session_variables_lookup: 变量池Dict[str, Any]，根据JSONPath取值
        :param operation_type: 错误信息前缀，如变量提取、断言验证
        :return: 提取得到的值
        """
        range_type_n: str = (range_type or "SOME").strip().lower()
        source_key: str = cls._normalize_extract_source(source)
        resolved_request_cookies = request_cookies
        if resolved_request_cookies is None and request_headers:
            resolved_request_cookies = KvUtils.parse_cookie_header(request_headers)

        ctx = ExchangeContext(
            response_text=response_text,
            response_json=response_json,
            response_headers=response_headers,
            response_cookies=response_cookies,
            request_text=request_text,
            request_json=request_json,
            request_headers=request_headers,
            request_cookies=resolved_request_cookies,
            session_lookup=session_variables_lookup,
        )
        extractor = EXTRACTORS.get(source_key)
        if extractor is not None:
            return extractor(ctx, expr, range_type_n, index, operation_type)

        # 数据库/Redis 请求步骤：source 为「请求」里配置的 variable_name；response_json 为 List[Dict]
        source_strip: str = (source or "").strip()
        if source_strip and isinstance(response_json, list) and response_json:
            all_operates_response_safe: bool = all(
                isinstance(op_resp, dict) and (
                        "variable_name" in op_resp or "sql_data" in op_resp or "redis_data" in op_resp
                )
                for op_resp in response_json
            )
            expr_executive_data: Any = None
            is_redis_response: bool = any(
                isinstance(op_resp, dict) and "redis_data" in op_resp for op_resp in response_json
            )
            for op_resp in response_json:
                if isinstance(op_resp, dict) and source_strip in op_resp.get("variable_name", []):
                    if "redis_data" in op_resp:
                        expr_executive_data = op_resp["redis_data"]
                    else:
                        expr_executive_data = op_resp.get("sql_data")
                    break
            if expr_executive_data is not None:
                return Extractors._extract_json_payload(
                    data=expr_executive_data,
                    expr=expr,
                    range_type=range_type_n,
                    index=index,
                    operation_type=operation_type,
                    empty_message=f"【{operation_type}】未找到可提取的执行结果数据",
                )
            if all_operates_response_safe:
                step_label = "Redis具体操作" if is_redis_response else "数据库具体操作"
                raise ValueError(
                    f"【{operation_type}】未找到存储变量[{source_strip}]对应的执行结果, "
                    f"请与「{step_label}」中的 variable_name 一致"
                )

        raise ValueError(f"【{operation_type}】数据源源类型 {source} 不被允许")


def _register_extractors() -> Dict[str, Callable[..., Any]]:
    """
    构建source规范化键到提取函数的注册表。

    :return: source_key -> (ctx, expr, range_type, index, operation_type) -> Any
    """
    E = Extractors

    def json_side(side: str) -> Callable[..., Any]:
        """注册JSON侧（request/response）提取器；返回的_run根据侧从ctx取JSON并提取。"""

        def _run(ctx: ExchangeContext, expr: Optional[str], range_type: str, index: Any, operation_type: str) -> Any:
            """从请求或响应JSON根据表达式提取。"""
            data = ctx.response_json if side == "response" else ctx.request_json
            label = "响应" if side == "response" else "请求"
            return E._extract_json_payload(
                data=data, expr=expr, range_type=range_type, index=index,
                operation_type=operation_type,
                empty_message=f"【{operation_type}】{label}内容不是有效的JSON数据",
            )

        return _run

    def xml_side(side: str) -> Callable[..., Any]:
        """注册XML侧（request/response）提取器；返回的_run根据侧从ctx取文本并提取。"""

        def _run(ctx: ExchangeContext, expr: Optional[str], range_type: str, index: Any, operation_type: str) -> Any:
            """从请求或响应XML文本根据表达式提取。"""
            text = ctx.response_text if side == "response" else ctx.request_text
            label = "响应" if side == "response" else "请求"
            return E._extract_xml_payload(
                text=text, expr=expr, range_type=range_type, index=index,
                operation_type=operation_type,
                empty_message=f"【{operation_type}】{label}内容不是有效的XML数据",
                invalid_xml_message=f"【{operation_type}】{label}内容不是有效的XML格式",
            )

        return _run

    def text_side(side: str) -> Callable[..., Any]:
        """注册Text侧（request/response）提取器；返回的_run根据侧从ctx取文本并提取。"""

        def _run(ctx: ExchangeContext, expr: Optional[str], range_type: str, index: Any, operation_type: str) -> Any:
            """从请求或响应纯文本根据表达式提取，index指定正则分组编号。"""
            text = ctx.response_text if side == "response" else ctx.request_text
            label = "响应" if side == "response" else "请求"
            return E._extract_text_payload(
                text=text,
                expr=expr,
                range_type=range_type,
                index=index,
                operation_type=operation_type,
                empty_message=f"【{operation_type}】{label}内容不是有效的Text数据",
            )

        return _run

    def mapping_side(attr: str, empty: str, miss_prefix: str) -> Callable[..., Any]:
        """注册Headers/Cookies等映射字段提取器；返回的_run从ctx.attr取值。"""

        def _run(ctx: ExchangeContext, expr: Optional[str], range_type: str, index: Any, operation_type: str) -> Any:
            """从映射字段（Headers/Cookies等）根据表达式提取。"""
            data = getattr(ctx, attr)
            return E._extract_mapping_payload(
                data=data, expr=expr, range_type=range_type,
                operation_type=operation_type,
                empty_message=f"【{operation_type}】{empty}",
                miss_message=f"【{operation_type}】{miss_prefix}: {expr}",
            )

        return _run

    def session_vars(ctx: ExchangeContext, expr: Optional[str], range_type: str, index: Any, operation_type: str) -> Any:
        """从变量池session_lookup根据JSONPath取值。"""
        if not expr:
            raise ValueError(f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是有效JSONPath表达式")
        if ctx.session_lookup is None:
            raise ValueError(f"【{operation_type}】变量池未提供")
        if not isinstance(ctx.session_lookup, dict):
            raise ValueError(
                f"【{operation_type}】变量池类型不被允许: {type(ctx.session_lookup)}; "
                f"仅支持 Dict[str, Any] 并使用 JSONPath 取值"
            )
        try:
            return E._resolve_json_path(data=ctx.session_lookup, expr=expr)
        except Exception as e:
            raise ValueError(str(e) or f"【{operation_type}】变量池 JSONPath匹配失败: {expr}") from e

    return {
        "response json": json_side("response"),
        "request json": json_side("request"),
        "response xml": xml_side("response"),
        "request xml": xml_side("request"),
        "response text": text_side("response"),
        "request text": text_side("request"),
        "response headers": mapping_side(
            "response_headers", "响应 Headers 为空", "响应 Headers JSONPath匹配失败"
        ),
        "request headers": mapping_side(
            "request_headers", "请求 Headers 为空", "请求 Headers JSONPath匹配失败"
        ),
        "response cookies": mapping_side(
            "response_cookies", "响应 Cookies 为空", "响应 Cookies JSONPath匹配失败"
        ),
        "request cookies": mapping_side(
            "request_cookies", "请求 Cookies 为空", "请求 Cookies JSONPath匹配失败"
        ),
        "session_variables": session_vars,
        "变量池": session_vars,
    }


# 规范化 source 键 -> 提取可调用对象；由 extract_from_source 优先查表
EXTRACTORS: Dict[str, Callable[..., Any]] = _register_extractors()
