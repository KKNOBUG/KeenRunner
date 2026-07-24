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
    """按XPath映射更新XML请求报文。"""

    @staticmethod
    def replace_xml_datagram(
            *,
            body_map: Optional[Dict[str, Any]] = None,
            request_text: Optional[str] = None,
    ) -> Optional[str]:
        """
        数据驱动报文替换（XML）：按XPath将body_map写入请求XML。

        通过'XPathUtils.update'逐项替换；匹配规则与提取侧XPath语义对齐。
        空路径跳过；匹配不到时由XPathUtils决定（通常忽略），非法XML/执行失败抛ValueError。

        :param body_map: XPath->值的映射
        :param request_text: XML报文字符串；空值原样返回
        :return: 替换后的XML字符串
        :raises ValueError: 报文不是有效XML，或XPath执行失败时
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
