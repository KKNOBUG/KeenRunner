# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : api_doc_convert.py
@DateTime: 2025/4/7 15:44
"""
from typing import List, Optional, Any, Dict, Union
from xml.etree import ElementTree as ET


class APIDocConvert:
    """
    将Excel风格的接口字段表转换为树结构，并生成JSON或XML报文骨架。

    STRUCT/ARRAY同名二次出现视为闭合标记；ARRAY下叶子字段挂到隐式STRUCT子节点。
    """

    def __init__(self, *args, **kwargs):
        """
        初始化转换器。

        :param args: 保留位置参数
        :param kwargs: 保留关键字参数
        """
        super().__init__(*args, **kwargs)

    @classmethod
    def parse_excel_data(cls, excel_rows: List[tuple]) -> dict:
        """
        将Excel行列表解析为嵌套字段树。

        :param excel_rows: 行元组列表，项为(en_name, zh_name, field_type, length)
        :return: 根节点字典，含type/name/children等键
        """
        root: dict = {}
        stack: list = []
        current = None
        array_flag = False

        for row in excel_rows:
            en_name, zh_name, field_type, length = row
            if field_type.upper() == "STRUCT":
                if not stack:
                    root = {"type": "STRUCT", "children": [], "name": en_name}
                    stack.append(root)
                    current = root
                else:
                    # 检查是否遇到结束标记（同名字段第二次出现）
                    if current["name"] == en_name and current["type"].upper() == "STRUCT":
                        stack.pop()
                        if stack:
                            current = stack[-1]
                    else:
                        new_struct = {"type": "STRUCT", "children": [], "name": en_name}
                        current["children"].append(new_struct)
                        stack.append(new_struct)
                        current = new_struct
            elif field_type.upper() == "ARRAY":
                # 检查是否遇到结束标记（同名字段第二次出现）
                if current.get("name") == en_name and current["type"].upper() == "ARRAY":
                    stack.pop()
                    current = stack[-1]
                    array_flag = False
                else:
                    new_struct = {"type": "ARRAY", "children": [], "name": en_name}
                    current["children"].append(new_struct)
                    stack.append(new_struct)
                    current = new_struct
                    array_flag = True
            else:
                if array_flag:
                    if not current["children"]:
                        current["children"].append({"type": "STRUCT", "children": []})
                    current["children"][-1]["children"].append({
                        "type": field_type, "name": en_name, "length": length
                    })
                else:
                    current["children"].append({
                        "name": en_name,
                        "type": field_type,
                        "length": length
                    })
        return root

    def build_json(self, node: dict, is_root: bool = True) -> Union[Dict[str, Any], List[Any], str]:
        """
        根据字段树生成JSON报文骨架，叶子值使用length字段。

        :param node: 字段树节点
        :param is_root: 是否为根节点，根节点外层包裹节点名
        :return: 字典、列表或空字符串
        """
        if node["type"] == "STRUCT":
            result = {}
            for child in node["children"]:
                if child["type"] == "STRUCT":
                    result[child["name"]] = self.build_json(child, False)
                elif child["type"] == "ARRAY":
                    result[child["name"]] = [self.build_json(child, False)]
                else:
                    result[child["name"]] = child["length"]
            return result if not is_root else {node["name"]: result}
        elif node["type"] == "ARRAY":
            return [self.build_json(node["children"][0], False)]
        else:
            return ""

    def build_xml(self, node: dict, parent: Optional[ET.Element] = None) -> Optional[ET.Element]:
        """
        根据字段树生成XML报文骨架，叶子文本使用length字段。

        :param node: 字段树节点
        :param parent: 父Element；为None时创建根节点并返回
        :return: 根Element；挂到parent时返回None
        """
        if parent is None:
            root = ET.Element(node["name"])
            for child in node["children"]:
                self.build_xml(child, root)
            return root
        elif node["type"].upper() == "STRUCT":
            elem = ET.SubElement(parent, node["name"])
            for child in node["children"]:
                self.build_xml(child, elem)
        elif node["type"].upper() == "ARRAY":
            array_elem = ET.SubElement(parent, node["name"])
            for item in node["children"]:
                for child in item["children"]:
                    ET.SubElement(array_elem, child["name"]).text = child["length"]
        else:
            ET.SubElement(parent, node["name"]).text = node["length"]


if __name__ == '__main__':
    excel_data = [
        ("TCoSignoffMultAaaRq", "", "Struct", ""),
        ("CommonRqHdr", "", "Struct", ""),
        ("GlblSrlNo", "全局流水号", "String", "28"),
        ("CnlTxnCd", "渠道交易码", "String", "64"),
        ("CnsmrSysId", "消费方系统标识", "String", "16"),
        ("SPName", "外围系统简称", "String", "50"),
        ("RqUID", "消费方流水号", "String", "50"),
        ("NumTranCode", "数字交易码", "String", "50"),
        ("ClearDate", "清算日期", "String", "50"),
        ("TranDate", "交易处理日期", "string", "50"),
        ("TranTime", "交易处理时间", "string", "50"),
        ("DirectSendFlag", "穿透标示", "String", "50"),
        ("ChannelId", "渠道Id", "string", "50"),
        ("Version", "", "string", "50"),
        ("CntId", "柜员号", "string", "50"),
        ("CompanyCode", "开户行", "string", "50"),
        ("CommonRqHdr", "", "Struct", ""),
        ("FBID", "业务类型", "string", "50"),
        ("FtTxnType", "本地交易类型", "string", "50"),
        ("MediumType", "介质类型", "string", "50"),
        ("MediumAccNo", "介质账号", "string", "50"),
        ("Pwd", "", "string", "128"),
        ("Name", "姓名", "string", "120"),
        ("LegalEntTyp", "证件类型", "string", "50"),
        ("LegalId", "证件号码", "string", "50"),
        ("FbNoRec", "", "array", ""),
        ("FbNo", "业务类型", "string", "50"),
        ("ComContNo", "商业合同号", "string", "50"),
        ("FbNoRec", "", "array", ""),
        ("CustId", "客户Id号", "string", "50"),
        ("TCoSignoffMultAaaRq", "", "Struct", ""),
    ]

    structure = APIDocConvert()
    data = structure.parse_excel_data(excel_data)
    print(structure.build_json(data))

    xml_root = structure.build_xml(data)
    print(ET.tostring(xml_root, encoding="unicode"))

    import random
    import string


    def generate_random_string(length):
        """
        生成指定长度的随机字母数字串。

        :param length: 字符串长度
        :return: 随机字符串
        """
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for i in range(length))


    def generate_message(data_structure):
        """
        按JSON骨架中的length生成随机报文样例。

        :param data_structure: build_json产出的嵌套字典
        :return: 填充随机值后的报文字典
        """
        message = {}
        for key, value in data_structure.items():
            if isinstance(value, dict):
                message[key] = generate_message(value)
            elif isinstance(value, list):
                message[key] = []
                for item in value:
                    if isinstance(item, dict):
                        message[key].append(generate_message(item))
                    else:
                        message[key].append(generate_random_string(int(value)))
            else:
                message[key] = generate_random_string(int(value))
        return message


    data_structure = {
        'TCoSignoffMultAaaRq': {
            'CommonRqHdr': {
                'GlblSrlNo': '28',
                'CnlTxnCd': '64',
                'CnsmrSysId': '16',
                'SPName': '50',
                'RqUID': '50',
                'NumTranCode': '50',
                'ClearDate': '50',
                'TranDate': '50',
                'TranTime': '50',
                'DirectSendFlag': '50',
                'ChannelId': '50',
                'Version': '50',
                'CntId': '50',
                'CompanyCode': '50'
            },
            'FBID': '50',
            'FtTxnType': '50',
            'MediumType': '50',
            'MediumAccNo': '50',
            'Pwd': '128',
            'Name': '120',
            'LegalEntTyp': '50',
            'LegalId': '50',
            'FbNoRec': [
                {
                    'FbNo': '50',
                    'ComContNo': '50'
                }
            ],
            'CustId': '50'
        }
    }

    generated_message = generate_message(data_structure)
    print(generated_message)
