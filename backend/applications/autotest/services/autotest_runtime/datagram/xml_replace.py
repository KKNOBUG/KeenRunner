# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : xml_replace.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from xml.etree import ElementTree

from backend.applications.autotest.services.autotest_runtime.datagram.value_adapter import (
    expand_dataset_general_value,
    expand_dataset_special_value,
)
from backend.common.xml_utils import XmlUtils
from backend.common.xpath_utils import XPathUtils
from backend.configure import LOGGER


class XmlDatagram:
    """根据XPath映射更新XML请求报文。"""

    @staticmethod
    def replace_xml_datagram(
            body_map: Optional[Dict[str, Any]] = None,
            request_text: Optional[str] = None,
            *,
            logger_object: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        """
        数据驱动报文替换：根据XPath将body_map写入XML格式的请求报文。

        实现要点：
        - 整篇报文只解析一次、只在确有命中时序列化一次，避免逐字段重解析与命名空间反复改写；
        - 序列化统一走 XmlUtils，保留默认命名空间/XML声明/注释，避免 ElementTree 生成 ns0 前缀；
        - 支持叶子文本与 @attr 属性路径；未命中路径汇总告警但不阻断步骤（与历史语义一致）。

        :param body_map: XPath表达式->注入值的映射
        :param request_text: XML报文字符串
        :param logger_object: 可选的步骤日志回调；传入时未命中明细同步写入步骤日志
        :return: 替换后的XML字符串；无命中时原样返回
        """
        if not request_text:
            return request_text

        body_map = body_map or {}
        if not body_map:
            return request_text

        try:
            parsed = XmlUtils.parse(request_text)
        except ElementTree.ParseError as e:
            raise ValueError(f"【报文替换】请求报文不是有效的XML格式, 错误描述: {e}") from e

        missed_paths: List[str] = []
        changed = False
        for xpath_expr, xpath_value in body_map.items():
            if not xpath_expr:
                continue
            adapted_value = expand_dataset_general_value(
                value=expand_dataset_special_value(value=xpath_value)
            )
            try:
                updated = XPathUtils.update_in_place(parsed.root, xpath_expr, adapted_value)
            except Exception as e:
                raise ValueError(f"【报文替换】XPath表达式[{xpath_expr}]执行失败, 错误: {e}") from e
            if updated:
                changed = True
            else:
                missed_paths.append(xpath_expr)

        if missed_paths:
            message = f"【报文替换】数据源路径在报文中未命中, 已跳过: {', '.join(missed_paths)}"
            LOGGER.warning(message)
            if logger_object is not None:
                logger_object(message)

        if not changed:
            return request_text

        try:
            return XmlUtils.serialize(
                parsed.root,
                namespaces=parsed.namespaces,
                declaration=parsed.declaration,
            )
        except Exception as e:
            raise ValueError(f"【报文替换】XML报文序列化失败, 错误: {e}") from e
