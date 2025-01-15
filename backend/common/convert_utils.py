# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : convert_utils.py
@DateTime: 2025/1/15 14:30
"""
import json
import xml.etree.ElementTree as ET

from typing import Dict, Any
from datetime import datetime, timedelta

import xmltodict


class Convert:
    FORMATTER: Dict[int, str] = {
        10: "%Y%m%d%H%M%S",
    }

    @classmethod
    def decimal_to_datetime(cls, decimal_str: int, fmt: int = 10) -> str:
        """
        将十进制时间戳转换为日期时间字符串。
        :param decimal_str: 十进制时间戳（微秒）。
        :param fmt: 格式化类型，默认为10。
        :return: 格式化后的日期时间字符串。
        :raises TypeError: 如果输入参数类型不正确。
        """
        if not isinstance(decimal_str, int):
            try:
                decimal_str = int(decimal_str)
            except ValueError:
                raise TypeError("参数类型错误，必须为整数或可转换为整数的字符串")

        timestamp_second = decimal_str / 1_000_000
        datetime_str = datetime(year=1970, month=1, day=1) + timedelta(seconds=timestamp_second)
        formatted_datetime = datetime_str.strftime(cls.FORMATTER[fmt])

        return formatted_datetime

    @classmethod
    def datetime_to_decimal(cls, datetime_str: str, fmt: int = 10) -> int:
        """
        将日期时间字符串转换为十进制时间戳。
        :param datetime_str: 日期时间字符串。
        :param fmt: 格式化类型，默认为10。
        :return: 十进制时间戳（微秒）。
        :raises ValueError: 如果输入的日期时间字符串格式不正确。
        """
        datetime_value = datetime.strptime(datetime_str, cls.FORMATTER[fmt])
        timestamp_microseconds = int((datetime_value - datetime(year=1970, month=1, day=1)).total_seconds() * 1_000_000)

        return timestamp_microseconds

    @classmethod
    def datagram_is_xml(cls, datagram: str) -> bool:
        """
        检查给定的字符串是否为有效的XML格式。
        :param datagram: 待检查的字符串。
        :return: 如果是有效的XML格式，返回True；否则返回False。
        """
        try:
            datagram = str(datagram).strip().strip("\n")
            root = ET.fromstring(text=datagram)
            return True
        # 字符串解析转换XML失败
        except ET.ParseError as e:
            return False
            # 类型错误
        except TypeError as e:
            return False
        # 意外错误
        except Exception as e:
            return False

    @classmethod
    def datagram_is_json(cls, datagram: str) -> bool:
        """
        检查给定的字符串是否为有效的JSON格式。
        :param datagram: 待检查的字符串。
        :return: 如果是有效的JSON格式，返回True；否则返回False。
        """
        try:
            datagram = str(datagram).strip().strip("\n")
            json.loads(s=datagram)
            return True
        # 字符串解码转json失败
        except json.decoder.JSONDecodeError:
            return False
        # 类型错误
        except TypeError as e:
            return False
        # 意外错误
        except Exception as e:
            return False

    @classmethod
    def remove_empty_tags(cls, _, key, value) -> tuple or None:
        """
        移除空标签的回调函数。
        :param _: 未使用的参数。
        :param key: XML标签名。
        :param value: XML标签值。
        :return: 如果值为空或是空字典，返回None；否则返回(key, value)元组。
        """
        # 如果值是None或者是空字典，说明是一个自闭合标签，返回None值剔除
        if value is None or (isinstance(value, dict) and not value):
            return None
        return key, value

    @classmethod
    def xml_to_json(cls, datagram: str) -> str:
        """
        将XML格式的字符串转换为JSON格式。
        :param datagram: XML字符串。
        :return: 转换后的JSON对象，如果输入不是有效的XML，则返回原始字符串。
        """
        datagram = str(datagram).strip().strip("\n")

        if not cls.datagram_is_xml(datagram=datagram):
            return datagram

        parsed_dict = xmltodict.parse(datagram, postprocessor=cls.remove_empty_tags)
        json_string = json.loads(json.dumps(parsed_dict, ensure_ascii=False))
        return json_string

    @classmethod
    def json_to_xml(cls, datagram: Any) -> str:
        """
        将JSON格式的数据转换为XML格式的字符串。
        :param datagram: JSON对象。
        :return: 转换后的XML字符串。
        """
        xml_string = xmltodict.unparse({"root": datagram}, pretty=True)
        return xml_string

    @classmethod
    def dict_to_json(cls, datagram: dict) -> str:
        """
        将字典转换为JSON格式的字符串。
        :param datagram: 字典数据。
        :return: JSON字符串。
        """
        return json.dumps(datagram, ensure_ascii=False)


if __name__ == '__main__':
    # 示例用法
    print(Convert.decimal_to_datetime(1633072800000000))  # 示例时间戳
    print(Convert.datetime_to_decimal("20211001000000"))  # 示例日期时间字符串
    print(Convert.datagram_is_xml("<root><child>value</child></root>"))  # 检查XML
    print(Convert.datagram_is_json('{"key": "value"}'))  # 检查JSON
    print(Convert.xml_to_json("<root><child>value</child></root>"))  # XML转JSON
    print(Convert.json_to_xml({"child": "value"}))  # JSON转XML
    print(Convert.dict_to_json({"key": "value"}))  # 字典转JSON
