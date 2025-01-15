# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : jsonpath_utils.py
@DateTime: 2025/1/15 13:36
"""
import json
import typing

import jsonpath, jsonpath_ng
from jsonpath_ng import parse


class JSONPathUtils:
    """
    利用JSONPath对JSON数据的增删改查工具类
    1.执行JsonPath新增并返回结果
    2.执行JsonPath删除并返回结果
    3.执行JsonPath更新并返回结果
    4.执行JsonPath查询并返回结果
    """

    @staticmethod
    def add(json_data: typing.Union[str, dict], json_path: str, value: typing.Any,
            key: typing.Optional[str] = None) -> typing.Union[str, dict]:
        """
        执行JsonPath新增并返回结果
        1.如果JSONPath表达式存在，且对应的数据是list类型，则在末尾追加value
        2.如果JSONPath表达式存在，且对应的数据是dict类型，则在该字段中创建key-value
        3.如果JSONPath表达式存在，且对应的数据是str类型，则将该字段更新成list类，追加value
        4.如果JSONPath表达式不存在，则需要在json_data中创建json_path路径，并添加数据
        :param json_data: 待新增的JSON数据（可以是JSON字符串或字典）
        :param json_path: JsonPath表达式字符串
        :param value: 新数据
        :param key: 新数据以字典形式添加需要提供key
        :return:
        """
        if isinstance(json_data, str):
            # 如果json_data是字符串，先将其解析为Python字典
            json_data = json.loads(json_data)

        # 解析JSONPath表达式
        jsonpath_expr = parse(json_path)
        # 查找匹配项
        matches = jsonpath_expr.find(json_data)
        if matches:
            # 遍历匹配项，并添加它们
            for match in matches:
                # 如果JSONPath表达式存在，且对应的数据是list类型，则在末尾追加value
                if isinstance(match.value, list):
                    match.context.value[match.path.fields[0]].append(value)
                # 如果JSONPath表达式存在，且对应的数据是dict类型，则在该字段中创建key-value
                elif isinstance(match.value, dict):
                    match.context.value[match.path.fields[0]][key] = value
                # 如果JSONPath表达式存在，且对应的数据是str类型，则将该字段更新成list类，追加value
                elif isinstance(match.value, str) and key is None:
                    match.context.value[match.path.fields[0]] = [match.context.value[match.path.fields[0]], value]
        else:
            # 如果JSONPath表达式不存在，则需要在json_data中创建json_path路径，并添加数据
            # 将JSONPath字符串分割成路径部分
            path_parts = json_path.split('.')
            path_parts = [i for i in path_parts if i != "$"]
            current_level = json_data

            # 遍历路径部分，创建不存在的节点
            for part in path_parts[:-1]:  # 最后一个部分是要添加数据的键
                if part not in current_level:
                    current_level[part] = value if len(path_parts) == 1 else {}
                current_level = current_level[part]

            # 在最后一个部分添加数据
            if not key:
                current_level[path_parts[-1]] = value
            else:
                current_level[path_parts[-1]] = {}
                current_level[path_parts[-1]][key] = value

        return json.dumps(json_data, ensure_ascii=False)

    @staticmethod
    def delete(json_data: typing.Union[str, dict], json_path: str) -> typing.Union[str, dict]:
        """
        执行JsonPath删除并返回结果
        :param json_data: 待查询的JSON数据（可以是JSON字符串或字典）
        :param json_path: JsonPath表达式字符串
        :return: 删除结果
        """
        if isinstance(json_data, str):
            # 如果json_data是字符串，先将其解析为Python字典
            json_data = json.loads(json_data)

        jsonpath_expr = parse(json_path)
        matches = jsonpath_expr.find(json_data)

        # 遍历匹配项，并删除它们
        for match in matches:
            # 如果JSONPath表达式是要修改某个下标，则match.path是实际Index对象
            if isinstance(match.path, jsonpath_ng.jsonpath.Index):
                del match.context.value[match.path.index]
            # 如果JSONPath表达式是要修改某个字段，则match.path是实际Fields对象
            elif isinstance(match.path, jsonpath_ng.jsonpath.Fields):
                del match.context.value[match.path.fields[0]]

        return json.dumps(json_data, ensure_ascii=False)

    @staticmethod
    def update(json_data: typing.Union[str, dict], json_path: str, value: typing.Any) -> typing.Union[str, dict]:
        """
        执行JsonPath更新并返回结果
        :param json_data: 待查询的JSON数据（可以是JSON字符串或字典）
        :param json_path: JsonPath表达式字符串
        :param value: 新数据
        :return: 更新结果
        """
        if isinstance(json_data, str):
            # 如果json_data是字符串，先将其解析为Python字典
            json_data = json.loads(json_data)

        # 解析JSONPath表达式
        jsonpath_expr = parse(json_path)
        # 查找匹配项
        matches = jsonpath_expr.find(json_data)
        if not matches:
            return json_data  # 未找到匹配项，无法进行更新，直接返回原数据

        # 遍历匹配项，并更新它们
        for match in matches:
            # 如果JSONPath表达式是要修改某个下标，则match.path是实际Index对象
            if isinstance(match.path, jsonpath_ng.jsonpath.Index):
                match.context.value[match.path.index] = value
            # 如果JSONPath表达式是要修改某个字段，则match.path是实际Fields对象
            elif isinstance(match.path, jsonpath_ng.jsonpath.Fields):
                match.context.value[match.path.fields[0]] = value

        return json.dumps(json_data, ensure_ascii=False)

    @staticmethod
    def query(json_data: str or dict, json_path: str) -> str or list:
        """
        执行JsonPath查询并返回结果
        :param json_data: 待查询的JSON数据（可以是JSON字符串或字典）
        :param json_path: JsonPath表达式字符串
        :return: 查询结果
        """
        if isinstance(json_data, str):
            # 如果json_data是字符串，先将其解析为Python字典
            json_data = json.loads(json_data)

        # 执行JsonPath查询
        results = jsonpath.jsonpath(json_data, json_path)
        if not results:
            return []

        return results[0] if len(results) == 1 else results


if __name__ == '__main__':
    # 示例使用
    mock_json_data = '''
{
  "name": "zhangsan",
  "age": 30,
  "phone": 13800001234,
  "address": "上海市浦东新区",
  "hobby": [
    {"电子竞技": ["只狼", "FIFA"]},
    {"运动": ["羽毛球", "乒乓球"]}
  ],
  "cars": [
    {"model": "奔驰", "price": 255555.0},
    {"model": "宝马", "price": 288888.0},
    {"model": "奥迪", "price": 300000.0}
  ],
  "mobile": {
  "中国电信": "10000",
  "中国移动": "10086",
  "中国联通": "10010"
  }
}
    '''

    # 执行JSONPath新增
    # 如果jsonpath存在，append to dict or list
    print(JSONPathUtils.add(mock_json_data, "$.mobile", "10050", key="中国铁通"))
    print(JSONPathUtils.add(mock_json_data, "$.hobby", {"娱乐": ["唱", "跳", "Rap", "篮球"]}))

    # 如果jsonpath不存在，create key-value or create key-key-key-value
    # print(JSONPathUtils.add(mock_json_data, "$.gender", 100))
    # print(JSONPathUtils.add(mock_json_data, "$.gender", 100.99))
    # print(JSONPathUtils.add(mock_json_data, "$.gender", True))
    # print(JSONPathUtils.add(mock_json_data, "$.gender", "沃尔玛塑料袋"))
    # print(JSONPathUtils.add(mock_json_data, "$.gender", "沃尔玛塑料袋", key="666"))
    # print(JSONPathUtils.add(mock_json_data, "$.jobs", ["cv工程师", "面向百度开发工程师"]))
    # print(JSONPathUtils.add(mock_json_data, "$.jobs", ["cv工程师", "面向百度开发工程师"], "666"))
    # print(JSONPathUtils.add(mock_json_data, "$.test.item.a", "嵌套"))
    # print(JSONPathUtils.add(mock_json_data, "$.test.item.a", ["嵌套1", "嵌套2"]))
    # print(JSONPathUtils.add(mock_json_data, "$.test.item.a", ["cv工程师", "面向百度开发工程师"], key="666"))
    # print(JSONPathUtils.add(mock_json_data, "$.test.item.a", {"job": "Python"}))
    # print(JSONPathUtils.add(mock_json_data, "$.test.item.a", {"job": "Python"}, key="666"))

    # 执行JSONPath删除
    # print(JSONPathUtils.delete(mock_json_data, "$.name"))
    # print(JSONPathUtils.delete(mock_json_data, "$.hobby"))
    # print(JSONPathUtils.delete(mock_json_data, "$.cars[0]"))
    # print(JSONPathUtils.delete(mock_json_data, "$.cars[0].price"))
    # print(JSONPathUtils.delete(mock_json_data, "$.cars[*].price"))

    # 执行JSONPath更新
    # print(JSONPathUtils.update(mock_json_data, "$.name", "admin"))
    # print(JSONPathUtils.update(mock_json_data, "$.name", ["zhangsan1", "zhangsan2", "zhangsan3"]))
    # print(JSONPathUtils.update(mock_json_data, "$.name", {"姓名": "zhangsan"}))
    # print(JSONPathUtils.update(mock_json_data, "$.hobby", {"娱乐": ["唱", "跳", "Rap", "篮球"]}))
    # print(JSONPathUtils.update(mock_json_data, "$.hobby[1]", {"运1动": ["羽毛2球", "乒乓3球"]}))

    # 执行JSONPath查询
    # print(JSONPathUtils.query(mock_json_data, "$.666"))
    # print(JSONPathUtils.query(mock_json_data, "$..model"))
    # print(JSONPathUtils.query(mock_json_data, "$.hobby"))
    # print(JSONPathUtils.query(mock_json_data, "$.hobby[0]"))
    # print(JSONPathUtils.query(mock_json_data, "$.hobby.*.*[0]"))
