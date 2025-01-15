# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : replace_utils.py
@DateTime: 2025/1/15 16:33
"""
import json
import re
from typing import Dict, Any, Union, Type, Set, List


class ReplaceUtils(object):
    @staticmethod
    def replace_json(datagram: Dict[str, Any], relevance_data: Dict,
                     return_type: Union[Type[Dict[str, Any]], Type[str]] = str) -> Union[Dict[str, Any], str]:
        """
        替换JSON数据中的字段值。

        :param datagram: 要替换的JSON数据字典。
        :param relevance_data: 包含替换值的字典。
        :param return_type: 返回数据的类型，可以是Dict[str, Any]或str，默认为str。
        :return: 替换后的JSON数据，类型由return_type指定。
        :raises TypeError: 如果datagram不是字典类型。
        """
        # 判断datagram是否为字典
        if not isinstance(datagram, dict):
            raise TypeError("参数[json_data]类型错误，请传递Dict[str, Any]字典类型")

        # 使用正则表达式查找datagram中所有被双引号包围的字段名（不包括冒号后的值）
        jsondata = json.dumps(datagram, indent=4, ensure_ascii=False)
        matcheds = re.findall(r'"(.*?)": "', jsondata)

        # 如果没有找到任何需要替换的字段，或者没有提供relevance_data，则直接返回原始的datagram
        if not matcheds or not relevance_data:
            return datagram

        # 从matched列表中筛选出实际存在于relevance_data中的字段
        matched_fields: Set = set(key for key in matcheds if key in relevance_data.keys())
        # 构建替换的字典
        replace_dict = {field: relevance_data.get(field) for field in matched_fields}

        # 一次性替换所有匹配项
        for field, value in replace_dict.items():
            jsondata = re.sub(
                pattern=r'"' + field + '": "(.*?)"',
                repl=f'"{field}": "{re.escape(str(value))}"',
                string=jsondata,
                flags=re.DOTALL
            )

        return jsondata if return_type is str else json.loads(jsondata)

    @staticmethod
    def replace_str(datagram: str, relevance_data: Dict) -> str:
        """
        替换字符串中的变量。

        :param datagram: 要替换的字符串。
        :param relevance_data: 包含替换值的字典。
        :return: 替换后的字符串。
        """
        pattern = r'\${(.*?)}'
        matched = re.findall(pattern=pattern, string=str(datagram))

        # 如果没有匹配到指定需要替换的字段，或者没有给定需要替换的数据，则直接返回
        if not matched or not relevance_data:
            return datagram

        matched_fields: List = [key for key in matched if key in relevance_data.keys()]
        for field in matched_fields:
            value: Any = relevance_data.get(field)
            regular: str = re.escape('${' + field + '}')
            datagram = re.sub(regular, str(value), datagram)

        return datagram

    @staticmethod
    def replace_xml(datagram: str, relevance_data: Dict) -> str:
        """
        替换XML数据中的字段值。

        :param datagram: 要替换的XML字符串。
        :param relevance_data: 包含替换值的字典。
        :return: 替换后的XML字符串。
        """
        # 使用正则表达式查找datagram中所有被双引号包围的字段名（不包括冒号后的值）
        matched = re.findall(r'<(.*?)>', str(datagram))

        # 如果没有找到任何需要替换的字段，或者没有提供relevance_data，则直接返回原始的datagram
        if not matched or not relevance_data:
            return datagram

        # 从matched列表中筛选出实际存在于relevance_data中的字段
        matched_fields: List = [key for key in matched if key in relevance_data.keys()]
        for field in matched_fields:
            value: Any = relevance_data.get(field)
            regular: str = '<' + field + '>(.*?)</' + field + '>'
            datagram = re.sub(regular, '<' + field + '>' + str(value) + '</' + field + '>', datagram)

        return datagram

    @staticmethod
    def replace_text(datagram: str, relevance_data: Dict) -> str:
        """
        替换文本中的变量。

        :param datagram: 要替换的文本字符串。
        :param relevance_data: 包含替换值的字典。
        :return: 替换后的文本字符串。
        """
        # 使用正则表达式查找datagram中所有被双引号包围的字段名（不包括冒号后的值）
        pattern = r'"\w+": "\$\{([^\"]+)}"'
        matched = re.findall(pattern=pattern, string=str(datagram).replace("'", '"'))

        # 如果没有找到任何需要替换的字段，或者没有提供relevance_data，则直接返回原始的datagram
        if not matched or not relevance_data:
            return datagram

        # 从matched列表中筛选出实际存在于relevance_data中的字段
        matched_fields: Set = set(key for key in matched if key in relevance_data.keys())
        # 构建替换的字典
        replace_dict = {"${" + field + "}": relevance_data.get(field) for field in matched_fields}

        # 一次性替换所有匹配项（直接使用value替换${xxx}）
        for field, value in replace_dict.items():
            datagram = datagram.replace(field, str(value))

        return datagram

    @staticmethod
    def replace_values(data, replacements):
        """
        递归替换数据中的值。

        :param data: 要替换的数据，可以是字典或列表。
        :param replacements: 包含替换值的字典。
        :return: 替换后的数据。
        """
        if isinstance(data, dict):
            for key, value in data.items():
                if key in replacements:
                    data[key] = replacements[key]
                elif isinstance(value, (dict, list)):
                    ReplaceUtils.replace_values(value, replacements)

        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    ReplaceUtils.replace_values(item, replacements)

        return data


if __name__ == '__main__':
    # JSON报文替换（根据正则匹配贪婪替换）
    json_1 = {
        "Body": {
            "bizId": "${bizId}",
            "pfCode": "${pfCode}",
            "validateCode": "2"
        },
        "Head": {
            "CnlTxnCd": "111",
            "CnsmrSrlNo": "111",
            "CnsmrSvcNo": "222",
            "CnsmrSysId": "PDMP.CAM",
            "CnsmrTxnCd": "222",
            "GlblSrlNo": "2",
            "InstId": "CN2235223",
            "InttCnlCd": "T22",
            "MAC": "",
            "MsgVerNo": "3.0",
            "OrgnlCnsmrSvcNo": "",
            "OrgnlCnsmrSysId": "",
            "ScnCd": "22",
            "SvcCd": "222",
            "SvcVerNo": "",
            "SysRsrvFlgStr": "",
            "SysRsrvStr": "",
            "TxnDt": "20220222",
            "TxnTm": "095930",
            "UsrNo": "CN0010001"
        }
    }
    json_data_1 = {
        "bizId": '66666666666666666666',
        "pfCode": '66666666666666666666',
        "validateCode": '66666666666666666666',
        "GlblSrlNo": '66666666666666666666'
    }
    # print(ReplaceUtils.replace_json(datagram=json_1, relevance_data=json_data_1))

    json_2 = {
        "Body": {
            "bizId": "9557001008600123007436005249啊#$@!&#*",
            "pfCode": "2",
            "validateCode": "3",
            "OpnFcnLstArry": [
                {
                    "name": "G2.BankingBusiness",
                    "age": "aacc"
                },
                {
                    "name": "G2.OperationRecordQry",
                    "age": "aabb"
                }
            ]
        },
        "Head": {
            "CnlTxnCd": "111",
            "CnsmrSrlNo": "111",
            "CnsmrSvcNo": "222",
            "CnsmrSysId": "PDMP.CAM",
            "CnsmrTxnCd": "222",
            "GlblSrlNo": "4",
            "InstId": "CN2235223",
            "InttCnlCd": "T22",
            "MAC": "",
            "MsgVerNo": "3.0",
            "OrgnlCnsmrSvcNo": "",
            "OrgnlCnsmrSysId": "PDMP.AFM",
            "ScnCd": "22",
            "SvcCd": "222",
            "SvcVerNo": "",
            "SysRsrvFlgStr": "",
            "SysRsrvStr": "",
            "TxnDt": "20211218",
            "TxnTm": "123330",
            "UsrNo": ""
        }
    }
    json_data_2 = {
        "bizId": '7m97c5TJe8KisGkes3zcjz7F7QIwa2U4udrd',
        "pfCode": '7m97c5TJe8KisGkes3zcjz7F7QIwa2U4udrd',
        "validateCode": '7m97c5TJe8KisGkes3zcjz7F7QIwa2U4udrd',
        "GlblSrlNo": '7m97c5TJe8KisGkes3zcjz7F7QIwa2U4udrd',
        'name': '7m97c5TJe8KisGkes3zcjz7F7QIwa2U4udrd',
        'age': '7m97c5TJe8KisGkes3zcjz7F7QIwa2U4udrd'
    }
    # print(ReplaceUtils.replace_json(datagram=json_2, relevance_data=json_data_2))

    # str报文替换
    str_1 = """
    床前${明月光}，
    疑是${地上霜}。
    举头${望明月}，
    低头${思故乡}。
    """
    str_data_1 = {"明月光": "1111111111", "地上霜": "2222222222", "望明月": "3333333333", "思故乡": "4444444444"}
    # print(ReplaceUtils.replace_str(datagram=str_1, relevance_data=str_data_1))

    str_2 = "username=${admin}&password=${123456}"
    str_data_2 = {"admin": 111111, "123456": "111111"}
    # print(ReplaceUtils.replace_str(datagram=str_2, relevance_data=str_data_2))

    # xml报文替换
    xml_1 = """
    <?json version=""1.0"" encoding=""UTF-8""?>
    <Result>
        <Value1>
            <id>xxx</id>
            <name>xxx</name>
            <phone>xxx</phone>
        </Value1>
        <Value2>
            <id>xxx</id>
            <name>xxx</name>
            <phone>xxx</phone>
        </Value2>
    </Result>    
    """
    xml_data_1 = {"id": "1111111111", "name": "2222222222", "phone": "3333333333"}
    # print(ReplaceUtils.replace_xml(datagram=xml_1, relevance_data=xml_data_1))

    datagram_list = [
        {"name": "John", "age": "${age}"},
        {"name": "Jane", "age": "${age}"}
    ]
    relevance_data = {
        "age": 30,
        "city": "New York"
    }
    replaced_list = ReplaceUtils.replace_values(datagram_list, relevance_data)
    print(replaced_list)
