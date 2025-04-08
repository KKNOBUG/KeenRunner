# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : api_doc_convert.py
@DateTime: 2025/4/7 15:44
"""
import json
from typing import List
from xml.etree import ElementTree as ET


class APIDocConvert:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def parse_excel_data(cls, excel_rows: List[tuple]):
        """
        解析excel数据，识别Struct/Array的开始和结束标记，返回结构化数据
        :param excel_rows:
        :return:
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

    def build_json(self, node, is_root=True):
        """
        递归构建json
        :param node:
        :param is_root:
        :return:
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

    def build_xml(self, node, parent=None):
        """
        递归构建xml
        :param node:
        :param parent:
        :return:
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
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for i in range(length))


    def generate_message(data_structure):
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
