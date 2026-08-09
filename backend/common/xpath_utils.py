# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : xpath_utils
"""
from typing import Any, List, Optional, Union
from xml.etree import ElementTree


class XPathUtils:
    """
    利用XPath对XML数据进行增删改查的工具类。

    表达式遵循ElementTree有限XPath语法；多匹配时默认操作最后一个元素；
    默认命名空间下无前缀路径会自动按{*}回退匹配。
    """

    @staticmethod
    def _parse(xml_data: Union[str, ElementTree.Element]) -> ElementTree.Element:
        """
        将XML字符串或元素解析为ElementTree元素。

        :param xml_data: XML字符串或ElementTree元素
        :return: ElementTree元素
        """
        if isinstance(xml_data, str):
            return ElementTree.fromstring(xml_data.encode("utf-8"))
        return xml_data

    @staticmethod
    def _local_name(tag: str) -> str:
        """
        取元素标签本地名，去掉Clark命名空间前缀。

        :param tag: 元素标签
        :return: 本地标签名
        """
        if tag and "}" in tag:
            return tag.rsplit("}", 1)[-1]
        return tag or ""

    @staticmethod
    def _tag_in_parent_ns(parent: ElementTree.Element, local_name: str) -> str:
        """
        根据父节点命名空间生成子标签；父无命名空间则返回本地名。

        :param parent: 父元素
        :param local_name: 子元素本地名
        :return: 带或不带命名空间的标签名
        """
        parent_tag = parent.tag or ""
        if "}" in parent_tag:
            ns = parent_tag.split("}", 1)[0][1:]
            return f"{{{ns}}}{local_name}"
        return local_name

    @classmethod
    def _rewrite_segment_ns_agnostic(cls, segment: str) -> str:
        """
        将单个路径段中的无前缀元素名改写为{*}Name形式。

        :param segment: XPath路径段
        :return: 改写后的路径段
        """
        if not segment or segment in (".", "..", "*"):
            return segment
        if segment.startswith("@") or segment.startswith("{"):
            return segment
        if "[" in segment:
            name, rest = segment.split("[", 1)
            predicate = "[" + rest
        else:
            name, predicate = segment, ""
        if not name or name in (".", "..", "*"):
            return segment
        if name.startswith("{"):
            return segment
        if ":" in name:
            name = name.split(":", 1)[-1]
        return "{*}" + name + predicate

    @classmethod
    def namespace_agnostic_xpath(cls, xpath: str) -> str:
        """
        将无命名空间前缀的XPath改写为可匹配任意命名空间的形式。

        :param xpath: 原始XPath表达式，如./Head/SvcCd
        :return: 改写后表达式，如./{*}Head/{*}SvcCd；已含Clark名时原样返回
        """
        if not xpath or "{" in xpath:
            return xpath
        parts: List[str] = []
        i = 0
        n = len(xpath)
        while i < n:
            if xpath.startswith("//", i):
                parts.append("//")
                i += 2
                continue
            if xpath[i] == "/":
                parts.append("/")
                i += 1
                continue
            j = i
            while j < n and xpath[j] != "/":
                j += 1
            parts.append(cls._rewrite_segment_ns_agnostic(xpath[i:j]))
            i = j
        return "".join(parts)

    @classmethod
    def findall(cls, root: ElementTree.Element, xpath: str) -> List[ElementTree.Element]:
        """
        命名空间兼容的findall，先原路径再{*}回退匹配。

        :param root: 搜索根元素
        :param xpath: XPath表达式
        :return: 匹配到的元素列表
        """
        if not xpath:
            return []
        try:
            elements = root.findall(xpath)
        except (SyntaxError, TypeError):
            elements = []
        if elements:
            return list(elements)
        alt = cls.namespace_agnostic_xpath(xpath)
        if not alt or alt == xpath:
            return list(elements) if elements else []
        try:
            return list(root.findall(alt))
        except (SyntaxError, TypeError):
            return []

    @classmethod
    def find_child(cls, parent: ElementTree.Element, name: str) -> Optional[ElementTree.Element]:
        """
        在直接子节点中根据本地名查找，兼容有无命名空间。

        :param parent: 父元素
        :param name: 子元素名或本地名
        :return: 匹配子元素；未找到时为None
        """
        if not name:
            return None
        child = parent.find(name)
        if child is not None:
            return child
        if name.startswith("{") or name.startswith("@"):
            return None
        local = name.split(":", 1)[-1] if ":" in name else name
        child = parent.find("{*}" + local)
        if child is not None:
            return child
        for elem in parent:
            if cls._local_name(elem.tag) == local:
                return elem
        return None

    @classmethod
    def _find_parent(
            cls,
            root: ElementTree.Element,
            target: ElementTree.Element,
    ) -> Optional[ElementTree.Element]:
        """
        在root子树中查找target的直接父元素。

        :param root: 搜索起点元素
        :param target: 目标子元素
        :return: 父元素；根节点本身或未找到时为None
        """
        for elem in root.iter():
            for child in elem:
                if child is target:
                    return elem
        return None

    @classmethod
    def add(
            cls,
            xml_data: Union[str, ElementTree.Element],
            xpath: str,
            value: Any,
            tag: Optional[str] = None,
    ) -> str:
        """
        按XPath新增节点并返回XML字符串。

        路径存在时按末匹配元素追加子节点或同名兄弟；路径不存在时沿路径逐级创建。

        :param xml_data: 待修改的XML字符串或ElementTree元素
        :param xpath: XPath表达式，定位目标父元素或路径
        :param value: 新数据，写入新元素text
        :param tag: 新子元素标签名；不提供时按规则推导
        :return: 新增后的XML字符串
        """
        if not xpath:
            if isinstance(xml_data, str):
                return xml_data
            return ElementTree.tostring(xml_data, encoding="unicode")

        root = cls._parse(xml_data)
        elements = cls.findall(root, xpath)

        if not elements:
            # 情况4：XPath 不存在，沿路径创建元素
            cls._create_path(root, xpath, value, tag)
            return ElementTree.tostring(root, encoding="unicode")

        target = elements[-1]
        children = list(target)

        # 推导新元素标签名（本地名）
        if tag:
            new_local = cls._local_name(tag)
        elif children:
            new_local = cls._local_name(children[-1].tag)
        else:
            new_local = cls._local_name(target.tag)
        new_tag = cls._tag_in_parent_ns(target, new_local)

        if not children and not tag:
            # 情况3：叶子节点且无显式 tag → 追加同名兄弟元素
            parent = cls._find_parent(root, target)
            append_to = parent if parent is not None else target
            sibling_tag = cls._tag_in_parent_ns(append_to, new_local)
            new_element = ElementTree.Element(sibling_tag)
            new_element.text = str(value) if value is not None else ""
            append_to.append(new_element)
        else:
            # 情况1/2：作为子元素追加
            new_element = ElementTree.SubElement(target, new_tag)
            new_element.text = str(value) if value is not None else ""

        return ElementTree.tostring(root, encoding="unicode")

    @classmethod
    def _create_path(
            cls,
            root: ElementTree.Element,
            xpath: str,
            value: Any,
            tag: Optional[str] = None,
    ) -> None:
        """
        沿xpath逐级创建元素，末级写入value。

        仅支持以/分隔的简单路径；含//或谓词的复杂路径不创建。

        :param root: 根元素，原地修改
        :param xpath: XPath表达式
        :param value: 末级写入值
        :param tag: 末级新增子元素标签名；不提供时设置末级元素text
        """
        path = xpath.strip()
        if path.startswith("./"):
            path = path[2:]
        if path.startswith("/"):
            path = path[1:]
        # 仅处理简单分段路径；含 // 或谓词则不创建
        if "//" in path or "[" in path:
            return
        parts = [p for p in path.split("/") if p]
        if not parts:
            return

        current = root
        for part in parts:
            if part.startswith("{"):
                local = cls._local_name(part)
            elif ":" in part:
                local = part.split(":", 1)[-1]
            else:
                local = cls._local_name(part)
            child = cls.find_child(current, local)
            if child is None:
                child = ElementTree.SubElement(current, cls._tag_in_parent_ns(current, local))
            current = child

        if tag:
            new_local = cls._local_name(tag)
            new_element = ElementTree.SubElement(current, cls._tag_in_parent_ns(current, new_local))
            new_element.text = str(value) if value is not None else ""
        else:
            current.text = str(value) if value is not None else ""

    @classmethod
    def delete(
            cls,
            xml_data: Union[str, ElementTree.Element],
            xpath: str,
    ) -> str:
        """
        按XPath删除匹配节点并返回XML字符串。

        :param xml_data: 待修改的XML字符串或ElementTree元素
        :param xpath: XPath表达式
        :return: 删除后的XML字符串；未匹配时返回原内容
        """
        if not xpath:
            if isinstance(xml_data, str):
                return xml_data
            return ElementTree.tostring(xml_data, encoding="unicode")

        root = cls._parse(xml_data)
        elements = cls.findall(root, xpath)
        if not elements:
            if isinstance(xml_data, str):
                return xml_data
            return ElementTree.tostring(root, encoding="unicode")

        for elem in elements:
            parent = cls._find_parent(root, elem)
            if parent is not None:
                parent.remove(elem)

        return ElementTree.tostring(root, encoding="unicode")

    @classmethod
    def update(
            cls,
            xml_data: Union[str, ElementTree.Element],
            xpath: str,
            value: Any,
    ) -> str:
        """
        按XPath更新匹配节点文本并返回XML字符串。

        :param xml_data: 待修改的XML字符串或ElementTree元素
        :param xpath: XPath表达式；多匹配时仅更新最后一个
        :param value: 新值，写入匹配元素的text
        :return: 更新后的XML字符串；未匹配时返回原内容
        """
        if not xpath:
            if isinstance(xml_data, str):
                return xml_data
            return ElementTree.tostring(xml_data, encoding="unicode")

        root = cls._parse(xml_data)
        elements = cls.findall(root, xpath)
        if not elements:
            if isinstance(xml_data, str):
                return xml_data
            return ElementTree.tostring(root, encoding="unicode")

        target_element = elements[-1]
        target_element.text = str(value) if value is not None else ""
        return ElementTree.tostring(root, encoding="unicode")

    @classmethod
    def query(
            cls,
            xml_data: Union[str, ElementTree.Element],
            xpath: str,
    ) -> Optional[Any]:
        """
        按XPath查询并返回匹配结果。

        :param xml_data: 待查询的XML字符串或ElementTree元素
        :param xpath: XPath表达式；多匹配时仅取最后一个
        :return: 匹配元素的text或XML字符串；未匹配时为None
        """
        if not xpath:
            return None

        root = cls._parse(xml_data)
        elements = cls.findall(root, xpath)
        if not elements:
            return None

        element = elements[-1]
        return element.text if element.text else ElementTree.tostring(element, encoding="unicode")


if __name__ == '__main__':
    mock_xml = """
    <root>
        <user>zhangsan</user>
        <information>
            <name>张三</name>
            <age>18</age>
            <phone>18100001234</phone>
            <email>zhangsan@test.com</email>
            <address>上海市浦东新区</address>
        </information>
        <hobby>
            <item>唱</item>
            <item>跳</item>
            <item>Rap</item>
            <item>篮球</item>
            <item>嘻嘻哈哈</item>
        </hobby>
        <cars>
            <car>
                <brand>奔驰</brand>
                <price>255555.0</price>
            </car>
            <car>
                <brand>宝马</brand>
                <price>288888.0</price>
            </car>
            <car>
                <brand>奥迪</brand>
                <price>300000.0</price>
            </car>
        </cars>
        <mobile>
            <中国电信>10000</中国电信>
            <中国移动>10086</中国移动>
            <中国联通>10010</中国联通>
        </mobile>
    </root>
    """

    # print("=" * 100)
    # print("【XPathUtils.update 场景】")
    # print("=" * 100)
    #
    # print("[1] 普通节点更新: ./user")
    # print(XPathUtils.update(mock_xml, "./user", "lisi"))
    # print("-" * 100)
    #
    # print("[2] 嵌套节点更新: ./information/name")
    # print(XPathUtils.update(mock_xml, "./information/name", "里斯"))
    # print("-" * 100)
    #
    # print("[3] 嵌套节点更新: ./information/email")
    # print(XPathUtils.update(mock_xml, "./information/email", "lisi@test.com"))
    # print("-" * 100)
    #
    # print("[4] 索引精确更新第5个hobby: ./hobby/item[5]")
    # print(XPathUtils.update(mock_xml, "./hobby/item[5]", "x"))
    # print("-" * 100)
    #
    # print("[5] 索引精确更新第1个car的brand: ./cars/car[1]/brand")
    # print(XPathUtils.update(mock_xml, "./cars/car[1]/brand", "保时捷"))
    # print("-" * 100)
    #
    # print("[6] 索引精确更新第3个car的price: ./cars/car[3]/price")
    # print(XPathUtils.update(mock_xml, "./cars/car[3]/price", "500000.0"))
    # print("-" * 100)
    #
    # print("[7] 多匹配默认更新最后一个: .//item")
    # print(XPathUtils.update(mock_xml, ".//item", "x"))
    # print("-" * 100)
    #
    # print("[8] 多匹配默认更新最后一个car的brand: .//brand")
    # print(XPathUtils.update(mock_xml, ".//brand", "大众"))
    # print("-" * 100)
    #
    # print("[9] 中文节点更新: ./mobile/中国移动")
    # print(XPathUtils.update(mock_xml, "./mobile/中国移动", "10087"))
    # print("-" * 100)
    #
    # print("[10] 未匹配节点不修改原数据: ./nonexistent")
    # print(XPathUtils.update(mock_xml, "./nonexistent", "x"))
    # print("-" * 100)
    #
    # print("[11] 空XPath返回原数据: 空字符串")
    # print(XPathUtils.update(mock_xml, "", "x"))
    # print("-" * 100)
    #
    # print("[12] 数值类型写入: ./information/age")
    # print(XPathUtils.update(mock_xml, "./information/age", 20))
    # print("-" * 100)
    #
    # print("[13] None值写入空字符串: ./information/age")
    # print(XPathUtils.update(mock_xml, "./information/age", None))
    # print("-" * 100)
    #
    # print("=" * 100)
    # print("【XPathUtils.query 场景】")
    # print("=" * 100)
    #
    # print("[14] 普通节点查询: ./user")
    # print(XPathUtils.query(mock_xml, "./user"))
    # print("-" * 100)
    #
    # print("[15] 嵌套节点查询: ./information/address")
    # print(XPathUtils.query(mock_xml, "./information/address"))
    # print("-" * 100)
    #
    # print("[16] 索引精确查询第2个car的brand: ./cars/car[2]/brand")
    # print(XPathUtils.query(mock_xml, "./cars/car[2]/brand"))
    # print("-" * 100)
    #
    # print("[17] 多匹配默认查询最后一个: .//item")
    # print(XPathUtils.query(mock_xml, ".//item"))
    # print("-" * 100)
    #
    # print("[18] 多匹配默认查询最后一个car的price: .//price")
    # print(XPathUtils.query(mock_xml, ".//price"))
    # print("-" * 100)
    #
    # print("[19] 中文节点查询: ./mobile/中国联通")
    # print(XPathUtils.query(mock_xml, "./mobile/中国联通"))
    # print("-" * 100)
    #
    # print("[20] 未匹配节点查询返回None: ./nonexistent")
    # print(XPathUtils.query(mock_xml, "./nonexistent"))
    # print("-" * 100)
    #
    # print("[21] 空XPath查询返回None: 空字符串")
    # print(XPathUtils.query(mock_xml, ""))
    # print("-" * 100)

    # print("=" * 100)
    # print("【XPathUtils.add 场景】")
    # print("=" * 100)
    #
    # print("[22] 在hobby下追加同名子元素(无tag): ./hobby")
    # print(XPathUtils.add(mock_xml, "./hobby", "游戏"))
    # print("-" * 100)
    #
    # print("[23] 在mobile下追加指定tag子元素: ./mobile, tag=中国铁通")
    # print(XPathUtils.add(mock_xml, "./mobile", "10050", tag="中国铁通"))
    # print("-" * 100)
    #
    # print("[24] 在cars下追加同名car子元素(无tag): ./cars")
    # print(XPathUtils.add(mock_xml, "./cars", "newcar"))
    # print("-" * 100)
    #
    # print("[25] 在information下追加指定tag子元素: ./information, tag=gender")
    # print(XPathUtils.add(mock_xml, "./information", "男", tag="gender"))
    # print("-" * 100)
    #
    # print("[26] 叶子节点无tag追加同名兄弟: ./user")
    # print(XPathUtils.add(mock_xml, "./user", "lisi"))
    # print("-" * 100)
    #
    # print("[27] XPath不存在沿路径创建: ./new/element, tag=value")
    # print(XPathUtils.add(mock_xml, "./new/element", "x", tag="value"))
    # print("-" * 100)
    #
    # print("[28] XPath不存在沿路径创建(无tag): ./new/leaf")
    # print(XPathUtils.add(mock_xml, "./new/leaf", "x"))
    # print("-" * 100)
    #
    # print("[29] 空XPath返回原数据: 空字符串")
    # print(XPathUtils.add(mock_xml, "", "x"))
    # print("-" * 100)
    #
    # print("=" * 100)
    # print("【XPathUtils.delete 场景】")
    # print("=" * 100)
    #
    # print("[30] 删除普通节点: ./user")
    # print(XPathUtils.delete(mock_xml, "./user"))
    # print("-" * 100)
    #
    # print("[31] 删除嵌套节点: ./information/email")
    # print(XPathUtils.delete(mock_xml, "./information/email"))
    # print("-" * 100)
    #
    # print("[32] 索引精确删除第1个car: ./cars/car[1]")
    # print(XPathUtils.delete(mock_xml, "./cars/car[1]"))
    # print("-" * 100)
    #
    # print("[33] 删除所有同名节点: .//item")
    # print(XPathUtils.delete(mock_xml, ".//item"))
    # print("-" * 100)
    #
    # print("[34] 删除所有car的brand: .//brand")
    # print(XPathUtils.delete(mock_xml, ".//brand"))
    # print("-" * 100)
    #
    # print("[35] 删除中文节点: ./mobile/中国联通")
    # print(XPathUtils.delete(mock_xml, "./mobile/中国联通"))
    # print("-" * 100)
    #
    # print("[36] 未匹配节点不修改原数据: ./nonexistent")
    # print(XPathUtils.delete(mock_xml, "./nonexistent"))
    # print("-" * 100)
    #
    # print("[37] 空XPath返回原数据: 空字符串")
    # print(XPathUtils.delete(mock_xml, ""))
    # print("-" * 100)

    mock_xml2 = """<BOSFXIII xmlns="http://www.bankofshanghai.com/BOSFX/2017/07">
    <Head>
        <SvcCd>1630029</SvcCd>
        <ScnCd>08</ScnCd>
        <CnlTxnCd>CUPS354</CnlTxnCd>
        <CnsmrSrlNo>${消费方}</CnsmrSrlNo>
        <CnsmrSvcNo>10.240.119.111</CnsmrSvcNo>
        <CnsmrSysId>CUTP</CnsmrSysId>
        <CnsmrTxnCd>CUPS354</CnsmrTxnCd>
        <GlblSrlNo>${流水号}</GlblSrlNo>
        <InstId/>
        <InttCnlCd>C13</InttCnlCd>
        <MAC/>
        <MsgVerNo>3.0</MsgVerNo>
        <OrgnlCnsmrSvcNo>10.240.119.111</OrgnlCnsmrSvcNo>
        <OrgnlCnsmrSysId>CUTP</OrgnlCnsmrSysId>
        <SvcVerNo>1.0</SvcVerNo>
        <SysRsrvFlgStr/>
        <SysRsrvStr/>
        <TxnDt>${date}</TxnDt>
        <TxnTm>${time}</TxnTm>
        <UsrNo/>
    </Head>
    <Body>
        <MsgTp>0106</MsgTp>
        <srteElmtVal>C+3137496900</srteElmtVal>
        <AcctNo>6250990266685052</AcctNo>
        <TxnDealCd>502200</TxnDealCd>
        <SysTrcNo>223066</SysTrcNo>
        <LclTxnTm>083006</LclTxnTm>
        <LclTxnDt>0629</LclTxnDt>
        <CrdVldDt>3305</CrdVldDt>
        <ClearDate>0225</ClearDate>
        <MrchTp>5411</MrchTp>
        <SvcPntInptMdCd>012</SvcPntInptMdCd>
        <POSCdtnCd>00</POSCdtnCd>
        <CrdAcptIndCd>315310018000111</CrdAcptIndCd>
        <CrdAcptNmAdr>测试银联云闪付分期结果查询</CrdAcptNmAdr>
        <IdntNo>2026060121800201077469817796</IdntNo>
        <AgngQualfSrlNo>03199315960001</AgngQualfSrlNo>
        <SysCnlInd>CNL</SysCnlInd>
        <BnkInnrCnlNo>020</BnkInnrCnlNo>
        <ExtrnlMrchNo>000</ExtrnlMrchNo>
        <DealMdNo>000</DealMdNo>
        <channelNumber>C13</channelNumber>
        <operatorNumber>1234</operatorNumber>
        <branchInstNumber>3001144</branchInstNumber>
    </Body>
</BOSFXIII>"""

    print(XPathUtils.query(mock_xml2, "./Head/SvcCd"))
    print("-" * 100)
