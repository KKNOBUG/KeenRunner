# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : resolver.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

import re
import traceback
from datetime import datetime
from typing import Any, Callable, List, Optional, Tuple, Union
from xml.etree import ElementTree

import orjson

from backend.applications.aotutest.schemas.autotest_step_schema import StepVariablesBase
from backend.applications.aotutest.services.autotest_runtime.context import coerce_variable_resolver
from backend.applications.aotutest.services.autotest_runtime.placeholders.arithmetic import PlaceholderArithmetic
from backend.applications.aotutest.services.autotest_runtime.placeholders.functions import PlaceholderFunctions
from backend.applications.aotutest.services.autotest_runtime.sandbox import RE_PLACEHOLDER


class PlaceholderResolver:
    """递归解析str/dict/list/XML中的占位符。"""

    @classmethod
    def _resolve_placeholder_inner(cls, inner: str, is_core_engine: bool, finished_variables: Optional[Any]) -> Any:
        """
        解析单个${...}花括号内的文本：含括号视为GenerateUtils函数, 否则根据变量名解析。

        :param inner: 占位符花括号内文本(如\"a\"或\"generate_uuid()\")会进行strip
        :param is_core_engine: True时finished_variables需提供get_variable(name)
        :param finished_variables: 核心引擎上下文或变量列表(List[Dict], 每项含key/value)
        :return: 解析到的变量值或函数执行结果
        """
        inner = inner.strip()
        if "(" in inner and ")" in inner:
            return PlaceholderFunctions.execute_func_string_single(inner)
        resolver = coerce_variable_resolver(
            finished_variables=finished_variables,
            is_core_engine=is_core_engine,
        )
        if resolver is None:
            raise KeyError(f"必须是已经存在且有值的变量: {inner!r}")
        return resolver.get_variable(inner)

    @classmethod
    def _resolve_string_placeholders(
            cls,
            content: str,
            logger_object: Callable,
            is_core_engine: bool,
            finished_variables: Optional[Any],
    ) -> str:
        """
        解析str内所有${...}：先占位符求值；失败则保留原${...}；全成功则视情况整式算术或拼接。

        :param content: 待解析的str内容
        :param logger_object: 日志回调, 签名为(str) -> None
        :param is_core_engine: True时finished_variables需提供get_variable
        :param finished_variables: 核心引擎上下文或变量列表
        :return: 占位符替换后的字符串
        """
        if "${" not in content:
            return content
        regularly_matched: List[re.Match[str]] = list(RE_PLACEHOLDER.finditer(content))
        if not regularly_matched:
            return content

        # 三元组: match(匹配对象), value(替换值), failed_content(失败的原文)
        # 第三项: 非None时表示解析失败, 应保留原文；None表示解析成功(值可以是: None)
        regularly_slots: List[Tuple[re.Match[str], Optional[Any], Optional[str]]] = []
        for match in regularly_matched:
            inner: str = match.group(1).strip()
            if not inner:
                logger_object(f"【参数替换】获取数据失败: \n\t不允许使用空字符串, 保留原值")
                regularly_slots.append((match, None, match.group(0)))
                continue
            try:
                value = cls._resolve_placeholder_inner(inner, is_core_engine, finished_variables)
                logger_object("【参数替换】获取数据成功: \n\t${" + inner + "}  >>>>>  " + str(value))
                regularly_slots.append((match, value, None))
            except (KeyError, AttributeError) as e:
                logger_object(f"【参数替换】获取数据异常: \n\t错误描述: {e}")
                regularly_slots.append((match, None, match.group(0)))

        if any(failed_content is not None for match, value, failed_content in regularly_slots):
            return PlaceholderArithmetic._split_placeholders(
                content=content,
                regularly_slots=regularly_slots,
                to_string=PlaceholderArithmetic._formatter_resolved_placeholders
            )

        if not PlaceholderArithmetic._is_calculate_placeholder_expr(content=content, regularly_slots=regularly_slots):
            return PlaceholderArithmetic._split_placeholders(
                content=content,
                regularly_slots=regularly_slots,
                to_string=PlaceholderArithmetic._formatter_resolved_placeholders
            )

        resolved_values: List[Any] = [value for match, value, failed_content in regularly_slots]
        calculated_nums: List[Optional[float]] = [PlaceholderArithmetic._is_calculated_numeric(v) for v in resolved_values]
        if not all(cn is not None for cn in calculated_nums):
            return PlaceholderArithmetic._split_placeholders(
                content=content,
                regularly_slots=regularly_slots,
                to_string=PlaceholderArithmetic._formatter_resolved_placeholders
            )

        calculated_numeric: List[float] = [number for number in calculated_nums if number is not None]
        reg_matches: List[re.Match[str]] = [match for match, value, failed_content in regularly_slots]
        merged: str = PlaceholderArithmetic._build_numeric_merged_expr(content, reg_matches, calculated_numeric).strip()
        if (
                merged
                and len(merged) <= PlaceholderArithmetic._MAX_ARITH_EXPR_CHARS
                and PlaceholderArithmetic._RE_ARITHMETIC_ONLY.fullmatch(merged)
        ):
            try:
                calculated_result: Union[int, float] = PlaceholderArithmetic._safe_calculation_expr(merged)
                formatted_result: str = PlaceholderArithmetic._formatter_calculated_result(calculated_result)
                logger_object(f"【变量运算】算式求值成功\n\t: {content} >>>>> {merged} >>>>> {formatted_result}")
                return formatted_result
            except Exception as e:
                logger_object(f"【变量运算】算式求值失败\n\t: {content} >>>>> {merged} >>>>> {e}, 改为根据字符串拼接")

        return PlaceholderArithmetic._split_placeholders(
            content=content,
            regularly_slots=regularly_slots,
            to_string=PlaceholderArithmetic._formatter_resolved_placeholders
        )

    @classmethod
    def _resolve_xml_string_segment(
            cls,
            segment: Optional[str],
            logger_object: Callable,
            is_core_engine: bool,
            finished_variables: Optional[Any],
    ) -> Optional[str]:
        """
        对XML文本片段（元素text/tail或属性值）解析占位符。

        :param segment: 待处理文本；None时原样返回
        :param logger_object: 日志回调, 签名为(str) -> None
        :param is_core_engine: True时finished_variables需提供get_variable
        :param finished_variables: 核心引擎上下文或变量列表
        :return: 解析后的文本
        """
        if segment is None or "${" not in segment:
            return segment
        return cls._resolve_string_placeholders(
            content=segment,
            logger_object=logger_object,
            is_core_engine=is_core_engine,
            finished_variables=finished_variables,
        )

    @classmethod
    def _resolve_xml_element_placeholders(
            cls,
            element: ElementTree.Element,
            logger_object: Callable,
            is_core_engine: bool,
            finished_variables: Optional[Any],
    ) -> None:
        """
        原地解析单个元素及其子树中的占位符（text、attrib、子元素tail）。

        :param element: 当前XML元素节点
        :param logger_object: 日志回调, 签名为(str) -> None
        :param is_core_engine: True时finished_variables需提供get_variable
        :param finished_variables: 核心引擎上下文或变量列表
        :return: None
        """
        element.text = cls._resolve_xml_string_segment(
            segment=element.text,
            logger_object=logger_object,
            is_core_engine=is_core_engine,
            finished_variables=finished_variables,
        )
        for attr_key, attr_value in list(element.attrib.items()):
            if attr_value and "${" in attr_value:
                element.attrib[attr_key] = cls._resolve_xml_string_segment(
                    segment=attr_value,
                    logger_object=logger_object,
                    is_core_engine=is_core_engine,
                    finished_variables=finished_variables,
                )
        for child in element:
            cls._resolve_xml_element_placeholders(
                element=child,
                logger_object=logger_object,
                is_core_engine=is_core_engine,
                finished_variables=finished_variables,
            )
            child.tail = cls._resolve_xml_string_segment(
                segment=child.tail,
                logger_object=logger_object,
                is_core_engine=is_core_engine,
                finished_variables=finished_variables,
            )

    @classmethod
    def resolve_xml_placeholders(
            cls,
            xml_text: str,
            logger_object: Callable,
            is_core_engine: bool = False,
            finished_variables: Optional[Any] = None,
    ) -> str:
        """
        解析XML报文中各文本节点与属性内的${...}占位符（含算术表达式）。

        根据元素text/tail/attrib粒度调用_resolve_string_placeholders，与JSON字段级行为对齐。
        无效XML时回退为整串_resolve_string_placeholders。

        :param xml_text: XML报文字符串
        :param logger_object: 日志回调, 签名为(str) -> None
        :param is_core_engine: True时finished_variables提供get_variable
        :param finished_variables: 核心引擎上下文或变量列表
        :return: 占位符替换后的XML字符串
        """
        if not xml_text or not isinstance(xml_text, str):
            return xml_text
        if "${" not in xml_text:
            return xml_text
        try:
            root = ElementTree.fromstring(xml_text.encode("utf-8"))
            cls._resolve_xml_element_placeholders(
                element=root,
                logger_object=logger_object,
                is_core_engine=is_core_engine,
                finished_variables=finished_variables,
            )
            return ElementTree.tostring(root, encoding="unicode")
        except ElementTree.ParseError:
            logger_object(
                "【参数替换】XML 报文解析失败, 回退为整串占位符替换"
            )
            return cls._resolve_string_placeholders(
                content=xml_text,
                logger_object=logger_object,
                is_core_engine=is_core_engine,
                finished_variables=finished_variables,
            )
        except Exception as e:
            logger_object(
                f"【参数替换】解析 XML 占位符时发生异常: \n\t"
                f"错误描述: {e}\n\t"
                f"错误类型: {type(e).__name__}\n\t"
                f"错误时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\t"
                f"错误回溯: {traceback.format_exc()}"
            )
            return xml_text

    @classmethod
    def resolve_placeholders(cls, value: Any, logger_object: Callable, is_core_engine: bool = False, finished_variables: Optional[Any] = None) -> Any:
        """
        递归解析str/dict/list中的${...}占位符。

        【字符串】单/多占位符解析变量或GenerateUtils函数（花括号内同时含括号时根据函数处理）。全部占位符解析成功且值均可视为数字、模板骨架为算术字符时，对合并表达式安全求值（如(${a}+10)*${b}/${c}）；否则根据字符串拼接。若整串以{/[开头且可JSON反序列化，则对内部str节点递归替换后再dumps。

        【字典】递归每个value（key不替换，与历史行为一致）

        【列表】元素为StepVariablesBase时只解析其value并model_copy；其余元素（含普通dict/list/str）整项递归resolve_placeholders

        【其它类型】原样返回

        解析失败：对应占位符保留原文；外层异常时记录日志并返回原value。

        :param value: 待解析对象
        :param logger_object: 日志回调，签名(str) -> None（解析路径中会调用，勿传None）
        :param is_core_engine: True时finished_variables需提供get_variable
        :param finished_variables: 引擎上下文或StepVariablesBase列表
        :return: 结构形状不变；dict/list为新建容器后的结果
        """
        try:
            if isinstance(value, str):
                if "${" in value and value.startswith(("{", "[")):
                    try:
                        value_json = orjson.loads(value)
                    except orjson.JSONDecodeError:
                        return value

                    def _treatment(node: Any) -> Any:
                        """递归处理JSON反序列化后的dict/list/str中的占位符。"""
                        if isinstance(node, dict):
                            for ck, cv in node.items():
                                node[ck] = _treatment(cv)
                            return node
                        if isinstance(node, list):
                            return [_treatment(item) for item in node]
                        if isinstance(node, str) and "${" in node:
                            return cls._resolve_string_placeholders(
                                content=node,
                                logger_object=logger_object,
                                is_core_engine=is_core_engine,
                                finished_variables=finished_variables,
                            )
                        return node

                    if not isinstance(value_json, (dict, list)):
                        return value
                    return orjson.dumps(_treatment(value_json)).decode("UTF-8")

                return cls._resolve_string_placeholders(
                    content=value,
                    logger_object=logger_object,
                    is_core_engine=is_core_engine,
                    finished_variables=finished_variables
                )

            if isinstance(value, dict):
                try:
                    return {
                        k: cls.resolve_placeholders(
                            value=v,
                            logger_object=logger_object,
                            is_core_engine=is_core_engine,
                            finished_variables=finished_variables
                        )
                        for k, v in value.items()
                    }
                except Exception as e:
                    logger_object(
                        f"【参数替换】解析字典中的占位符时发生异常: \n\t"
                        f"键: {list(value.keys())}\n\t"
                        f"错误描述: {e}\n\t"
                        f"错误类型: {type(e).__name__}\n\t"
                        f"错误时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\t"
                        f"错误回溯: {traceback.format_exc()}"
                    )
                    return value

            if isinstance(value, list):
                result: List[Any] = []
                for item in value:
                    if isinstance(item, StepVariablesBase):
                        result.append(item.model_copy(update={
                            "value": cls.resolve_placeholders(
                                value=item.value,
                                logger_object=logger_object,
                                is_core_engine=is_core_engine,
                                finished_variables=finished_variables,
                            )
                        }))
                    else:
                        result.append(cls.resolve_placeholders(
                            value=item,
                            logger_object=logger_object,
                            is_core_engine=is_core_engine,
                            finished_variables=finished_variables,
                        ))
                return result
            return value
        except Exception as e:
            logger_object(
                f"【参数替换】解析占位符时发生异常: \n\t"
                f"错误描述: {e}, \n"
                f"错误类型: {type(e).__name__}, \n"
                f"错误时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, \n"
                f"错误回溯: {traceback.format_exc()}\n"
            )
            return value
