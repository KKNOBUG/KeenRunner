# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : xml_utils.py
@DateTime: 2026/10/23

XML 解析/序列化通用工具：为数据驱动报文替换与占位符解析提供命名空间、声明、注释保留能力。

背景：
- 标准库 ElementTree 默认序列化会把默认命名空间改写为 ns0/ns1 前缀；
- 若后续再对该结果做 register_namespace("ns0", ...)，Python 会抛
  "Prefix format reserved for internal use"，导致占位符解析中断；
- 因此 XML 的解析与序列化必须统一收敛到本工具，禁止各业务模块自行 tostring。

约束：
- 仅使用标准库；不改变 XML 语义，只保留原始命名空间前缀/默认命名空间与 XML 声明；
- ElementTree 不支持 CDATA，CDATA 文本会被转义后输出（语义等价，字节不保真）；
- register_namespace 为进程级全局状态，序列化期间加锁并在结束后恢复，避免并发串扰。
"""
from __future__ import annotations

import io
import re
import threading
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple
from xml.etree import ElementTree

__all__ = ["ParsedXml", "XmlUtils"]


@dataclass(frozen=True)
class ParsedXml:
    """一次 XML 解析结果：根节点、命名空间映射与可选 XML 声明。"""

    root: ElementTree.Element
    namespaces: Tuple[Tuple[str, str], ...] = ()
    declaration: Optional[str] = None


class XmlUtils:
    """XML 解析/序列化工具类：保留命名空间前缀、默认命名空间与 XML 声明。"""

    # XML 声明只允许出现在文档最前，捕获后从待解析正文中剥离；
    # 剥离可避免 ElementTree 对“Unicode 字符串携带 encoding 声明”的限制，也便于解析后原样回填。
    _DECLARATION_RE = re.compile(r"^\s*(<\?xml[^>]*\?>)\s*", re.IGNORECASE)
    # ElementTree 内部保留前缀：ns0/ns1/...，不允许业务侧注册
    _RESERVED_PREFIX_RE = re.compile(r"^ns\d+$", re.IGNORECASE)
    # register_namespace 操作进程级 _namespace_map，序列化期间串行化并恢复现场
    _namespace_lock = threading.RLock()

    # ==================== 解析 ====================

    @classmethod
    def split_declaration(cls, xml_text: str) -> Tuple[Optional[str], str]:
        """
        拆分 XML 声明与正文。

        :param xml_text: 原始 XML 文本
        :return: (声明文本或None, 去掉声明后的正文)
        """
        if not isinstance(xml_text, str):
            return None, ""
        matched = cls._DECLARATION_RE.match(xml_text)
        if not matched:
            return None, xml_text
        return matched.group(1), xml_text[matched.end():]

    @classmethod
    def collect_namespaces(cls, xml_text: str) -> Tuple[Tuple[str, str], ...]:
        """
        按文档声明顺序收集 (prefix, uri) 列表，保留默认命名空间前缀""。

        :param xml_text: XML 正文（不含声明）
        :return: 命名空间映射元组；解析失败时返回空元组
        """
        if not xml_text or not xml_text.strip():
            return ()
        try:
            events = ElementTree.iterparse(
                io.BytesIO(xml_text.encode("utf-8")),
                events=("start-ns",),
            )
            return tuple(element for _, element in events)
        except (ElementTree.ParseError, ValueError, OSError):
            return ()

    @classmethod
    def parse(cls, xml_text: str) -> ParsedXml:
        """
        解析 XML 文本，保留声明、注释与处理指令。

        :param xml_text: 原始 XML 文本
        :return: ParsedXml 解析结果
        :raises ElementTree.ParseError: XML 非法或内容为空
        """
        declaration, body = cls.split_declaration(xml_text)
        if not body or not body.strip():
            raise ElementTree.ParseError("XML content is empty")
        # insert_comments/insert_pis：默认解析器会丢弃注释与处理指令，导致报文被静默改写；
        # 这两类节点在报文签名/审计场景可能需要保留，因此显式保留。
        parser = ElementTree.XMLParser(
            target=ElementTree.TreeBuilder(insert_comments=True, insert_pis=True)
        )
        root = ElementTree.fromstring(body, parser=parser)
        return ParsedXml(
            root=root,
            namespaces=cls.collect_namespaces(body),
            declaration=declaration,
        )

    # ==================== 序列化 ====================

    @classmethod
    def serialize(
            cls,
            root: ElementTree.Element,
            *,
            namespaces: Optional[Iterable[Tuple[str, str]]] = None,
            declaration: Optional[str] = None,
            include_declaration: bool = True,
    ) -> str:
        """
        序列化 XML 根节点，保留默认命名空间/原始前缀并可选回填 XML 声明。

        :param root: XML 根节点
        :param namespaces: 原始 (prefix, uri) 列表；为空时由 ElementTree 自行处理
        :param declaration: 原始 XML 声明
        :param include_declaration: 是否输出 XML 声明
        :return: XML 文本
        """
        namespace_items = tuple(namespaces or ())
        root_tag = root.tag if isinstance(root.tag, str) else ""
        root_uri = root_tag[1:].split("}", 1)[0] if root_tag.startswith("{") else None

        # 根节点命名空间优先还原原始前缀：默认命名空间/保留前缀(ns0等)统一按默认命名空间输出，
        # 其余情况沿用原始前缀（如<ns:Root xmlns:ns=...>）。
        # 注意不能使用 tostring(default_namespace=...)：标准库遇到未加前缀的属性会直接抛
        # ValueError("cannot use non-qualified names with default_namespace option")，
        # 因此这里通过 register_namespace("", uri) 实现默认命名空间输出。
        preferred_root_prefix: Optional[str] = "" if root_uri else None
        if root_uri:
            for prefix, uri in namespace_items:
                if uri != root_uri:
                    continue
                preferred_root_prefix = "" if (prefix == "" or cls._RESERVED_PREFIX_RE.match(prefix or "")) else prefix
                break

        namespace_map = getattr(ElementTree, "_namespace_map", None)
        previous_map = dict(namespace_map) if isinstance(namespace_map, dict) else None
        with cls._namespace_lock:
            try:
                registered_uris: set = set()
                used_prefixes: dict = {}
                for prefix, uri in namespace_items:
                    if not uri or prefix == "xml":
                        continue
                    if uri == root_uri and preferred_root_prefix is not None:
                        prefix = preferred_root_prefix
                    # 非根节点的默认命名空间不能注册为进程级默认前缀，否则会给根节点错误补上 xmlns，
                    # 使根节点进入子节点的命名空间；交由 ElementTree 生成局部前缀。
                    if prefix == "" and uri != root_uri:
                        continue
                    if cls._RESERVED_PREFIX_RE.match(prefix or ""):
                        continue
                    if uri in registered_uris:
                        continue
                    # 同一前缀在嵌套作用域可能绑定不同 URI；进程级映射无法同时表达，
                    # 保留首次绑定，后者交由 ElementTree 生成 nsN 前缀，确保语义正确。
                    if prefix in used_prefixes and used_prefixes[prefix] != uri:
                        continue
                    try:
                        ElementTree.register_namespace(prefix, uri)
                        used_prefixes[prefix] = uri
                        registered_uris.add(uri)
                    except ValueError:
                        continue
                # 传入的是 Element（无原始命名空间表）时，为根节点命名空间补默认声明，
                # 避免序列化退化为 ns0/ns1 前缀。
                if root_uri and root_uri not in registered_uris:
                    try:
                        ElementTree.register_namespace(preferred_root_prefix or "", root_uri)
                    except ValueError:
                        pass
                body = ElementTree.tostring(root, encoding="unicode")
            finally:
                # 恢复进程级命名空间映射，避免不同报文/线程之间前缀互相污染
                if previous_map is not None:
                    namespace_map.clear()
                    namespace_map.update(previous_map)

        if declaration and include_declaration:
            return f"{declaration}{body}"
        return body
