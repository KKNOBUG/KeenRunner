# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : xml_replace.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from xml.etree import ElementTree

from backend.applications.autotest.services.autotest_runtime.datagram.value_adapter import expand_dataset_special_value, expand_dataset_general_value
from backend.common.xpath_utils import XPathUtils
from backend.configure import LOGGER


class XmlDatagram:
    """根据XPath映射更新XML请求报文。"""

    @staticmethod
    def replace_xml_datagram(body_map: Optional[Dict[str, Any]] = None, request_text: Optional[str] = None) -> Optional[str]:
        """
        数据驱动报文替换：根据XPath将body_map写入XML格式的请求报文。

        :param body_map: XPath表达式->注入值的映射
        :param request_text: XML报文字符串
        :return: 替换后的XML字符串
        """
        if not request_text:
            return request_text

        body_map = body_map or {}
        missed_paths: List[str] = []
        for xpath_expr, xpath_value in body_map.items():
            if not xpath_expr:
                continue
            if XPathUtils.query(request_text, xpath_expr) is None:
                missed_paths.append(xpath_expr)
            try:
                request_text = XPathUtils.update(
                    xml_data=request_text,
                    xpath=xpath_expr,
                    value=expand_dataset_general_value(value=expand_dataset_special_value(value=xpath_value))
                )
            except ElementTree.ParseError as e:
                raise ValueError(f"【报文替换】请求报文不是有效的XML格式, 错误描述: {e}") from e
            except ValueError:
                raise
            except Exception as e:
                raise ValueError(f"【报文替换】XPath表达式[{xpath_expr}]执行失败, 错误: {e}") from e

        if missed_paths:
            LOGGER.info(f"【报文替换】数据源路径在报文中未命中, 已跳过: {', '.join(missed_paths)}")
        return request_text
