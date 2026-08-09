# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : xml_replace.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from xml.etree import ElementTree

from backend.common.xpath_utils import XPathUtils


class XmlDatagram:
    """根据XPath映射更新XML请求报文。"""

    @staticmethod
    def replace_xml_datagram(
            *,
            body_map: Optional[Dict[str, Any]] = None,
            request_text: Optional[str] = None,
    ) -> Optional[str]:
        """
        数据驱动报文替换（XML）：根据XPath将body_map写入请求XML。

        :param body_map: XPath->值的映射
        :param request_text: XML报文字符串；空值原样返回
        :return: 替换后的XML字符串
        """
        if not request_text:
            return request_text

        body_map = body_map or {}
        for xpath_expr, xpath_value in body_map.items():
            if not xpath_expr:
                continue
            try:
                request_text = XPathUtils.update(request_text, xpath_expr, xpath_value)
            except ElementTree.ParseError as e:
                raise ValueError(f"【XML报文替换】请求报文不是有效的XML格式, 错误描述: {e}") from e
            except ValueError:
                raise
            except Exception as e:
                raise ValueError(f"【XML报文替换】XPath表达式[{xpath_expr}]执行失败, 错误: {e}") from e

        return request_text
