# -*- coding: utf-8 -*-
"""
报文路径替换引擎(由 locust 子进程加载, 禁止 import backend 主包)。

数据源特殊值展开、值类型适配与 JSONPath/XPath 报文替换语义逐字对齐
autotest_runtime/datagram 模块(value_adapter/json_replace/xml_replace)与
common 层写查原语(JSONPathUtils/XPathUtils); 引擎内独立实现(仅依赖标准库与
orjson/jsonpath/jsonpath_ng), 调整任一侧时必须同步评估另一侧。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : datagram_replace.py
@DateTime: 2026/9/18 10:00
"""
from __future__ import annotations

import logging
import math
from typing import Any, Callable, Dict, List, Optional, Union
from xml.etree import ElementTree

import jsonpath
import jsonpath_ng
import orjson
from jsonpath_ng import parse as jsonpath_ng_parse

# 引擎内日志(禁import backend.configure, 与 perf_locustfile 同走标准logging)
LOGGER = logging.getLogger(__name__)

# JSONPath查询未解析哨兵(与 json_replace._QUERY_UNRESOLVED 同语义: 查询异常与未命中/字段null分离)
_QUERY_UNRESOLVED = object()


# ============================ 数据源特殊值与类型适配(对齐 value_adapter.py) ============================

# 特殊值常量：用户在数据源单元格中编写的占位文本
DATASET_EMPTY_TEXT = "#空字符串"
DATASET_NULL_VALUE = "#NULL"
DATASET_SPACE_VALUE = "#单个空格"

# 注入后代表单个空格的固定常量
DATASET_SPACE_EXPANDED = " "


def expand_dataset_special_value(value: Any) -> Any:
    """
    数据源场景命中字段对应的注入数据为特殊值常量占位时替换为具体值。

    :param value: 注入数据
    :return: #空字符串=空串、#NULL=None(大小写不敏感)、#单个空格=单个空格
    """
    if isinstance(value, str):
        crt_value = (value or "").strip()
        if crt_value == DATASET_EMPTY_TEXT:
            return ""
        if crt_value.upper() == DATASET_NULL_VALUE:
            return None
        if crt_value == DATASET_SPACE_VALUE:
            return DATASET_SPACE_EXPANDED
    return value


def expand_dataset_general_value(value: Any) -> str:
    """
    数据源场景命中字段对应的注入数据转为协议文本。

    :param value: 注入数据
    :return: 协议文本
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class DatasetValueAdapter:
    """数据源场景命中字段对应的注入数据的类型适配器(语义对齐 value_adapter.DatasetValueAdapter)。"""

    @staticmethod
    def _accept_raw(raw_value: str, target_value: Any) -> Any:
        """
        原样接受线路。

        适用：str字段；null字段与查询哨兵(类型参考不可用，由用户负责)；未注册类型兜底。
        """
        return raw_value

    @staticmethod
    def _route_bool(raw_value: str, target_value: Any) -> Any:
        """布尔字段线路：true/false文本(大小写不敏感)转布尔，其余原样接受(由用户负责)。"""
        converted = {"true": True, "false": False}.get(raw_value.strip().lower())
        return converted if converted is not None else raw_value

    @staticmethod
    def _convert_float(raw_value: str) -> Any:
        """浮点文本转换：可转float则返回数值；无法转换或inf/nan原样接受(转出inf会破坏orjson序列化)。"""
        try:
            number = float(raw_value.strip())
        except (ValueError, OverflowError):
            return raw_value
        return number if math.isfinite(number) else raw_value

    @staticmethod
    def _route_int(raw_value: str, target_value: Any) -> Any:
        """整数字段线路：整数文本转int、浮点文本转float(保留数值语义)，其余原样接受(由用户负责)。"""
        try:
            return int(raw_value.strip())
        except ValueError:
            return DatasetValueAdapter._convert_float(raw_value)

    @staticmethod
    def _route_float(raw_value: str, target_value: Any) -> Any:
        """浮点字段线路：整数/浮点文本转float，其余原样接受(由用户负责)。"""
        return DatasetValueAdapter._convert_float(raw_value)

    _routes: Dict[type, Callable[[str, Any], Any]] = {
        type(None): _accept_raw,
        str: _accept_raw,
        bool: _route_bool,
        int: _route_int,
        float: _route_float,
        list: _accept_raw,
        dict: _accept_raw,
        object: _accept_raw,
    }

    @classmethod
    def adapt(cls, raw_value: Any, target_value: Any) -> Any:
        """
        数据源场景命中字段对应的注入数据按报文原字段类型适配入口。

        :param raw_value: 注入数据
        :param target_value: 目标数据(报文原字段值，作为类型转换参考)
        :return: 类型转换后的值；无法转换时原样返回注入数据(由用户负责)
        """
        if not isinstance(raw_value, str):
            # 非字符串(遗留/异常数据)无贴合语义，原样接受(由用户负责)
            return raw_value

        # 特殊值常量命中时直接短路返回；未命中返回原对象，继续贴合线路
        expanded = expand_dataset_special_value(raw_value)
        if expanded is not raw_value:
            return expanded
        return cls._routes.get(type(target_value), cls._accept_raw)(raw_value, target_value)


# ============================ JSONPath 查询/更新原语(对齐 JSONPathUtils.query/update) ============================

def jsonpath_query(json_data: Union[str, List[Any], Dict[str, Any]], json_path: str) -> Union[str, list]:
    """
    执行JSONPath查询并返回结果(语义对齐 JSONPathUtils.query)。

    :param json_data: 待查询的JSON数据（可以是JSON字符串或字典）
    :param json_path: JSONPath表达式
    :return: 查询结果(单命中返回值, 多命中返回列表, 未命中返回空列表)
    """
    if isinstance(json_data, str):
        json_data = orjson.loads(json_data)

    results = jsonpath.jsonpath(json_data, json_path)
    if not results:
        return []

    return results[0] if len(results) == 1 else results


def jsonpath_update(json_data: Union[str, dict], json_path: str, value: Any) -> Union[str, dict]:
    """
    执行JSONPath更新并返回结果(语义对齐 JSONPathUtils.update)。

    dict输入时在原对象上原地修改(调用方可忽略返回值); str输入时解析后更新并返回
    序列化文本; 未命中匹配项时返回原数据。

    :param json_data: 待更新的JSON数据（可以是JSON字符串或字典）
    :param json_path: JSONPath表达式
    :param value: 新数据
    :return: 更新结果
    """
    if isinstance(json_data, str):
        json_data = orjson.loads(json_data)

    jsonpath_expr = jsonpath_ng_parse(json_path)
    matches = jsonpath_expr.find(json_data)
    if not matches:
        return json_data  # 未找到匹配项，无法进行更新，直接返回原数据

    for match in matches:
        # 如果JSONPath表达式是要修改某个下标，则match.path是实际Index对象
        if isinstance(match.path, jsonpath_ng.jsonpath.Index):
            match.context.value[match.path.index] = value
        # 如果JSONPath表达式是要修改某个字段，则match.path是实际Fields对象
        elif isinstance(match.path, jsonpath_ng.jsonpath.Fields):
            match.context.value[match.path.fields[0]] = value

    return orjson.dumps(json_data).decode("UTF-8")


# ============================ XPath 查询/更新原语(对齐 XPathUtils 查改语义) ============================

class PerfXPath:
    """
    利用XPath对XML数据进行查改的工具类。

    表达式遵循ElementTree有限XPath语法；多匹配时默认操作最后一个元素；
    默认命名空间下无前缀路径会自动按{*}回退匹配。语义对齐 common/xpath_utils.XPathUtils,
    仅复刻报文替换所需的 query/update 链路。
    """

    @staticmethod
    def _parse(xml_data: Union[str, ElementTree.Element]) -> ElementTree.Element:
        """将XML字符串或元素解析为ElementTree元素。"""
        if isinstance(xml_data, str):
            return ElementTree.fromstring(xml_data.encode("utf-8"))
        return xml_data

    @staticmethod
    def _local_name(tag: str) -> str:
        """取元素标签本地名，去掉Clark命名空间前缀。"""
        if tag and "}" in tag:
            return tag.rsplit("}", 1)[-1]
        return tag or ""

    @staticmethod
    def _tag_in_parent_ns(parent: ElementTree.Element, local_name: str) -> str:
        """根据父节点命名空间生成子标签；父无命名空间则返回本地名。"""
        parent_tag = parent.tag or ""
        if "}" in parent_tag:
            ns = parent_tag.split("}", 1)[0][1:]
            return f"{{{ns}}}{local_name}"
        return local_name

    @classmethod
    def _rewrite_segment_ns_agnostic(cls, segment: str) -> str:
        """将单个路径段中的无前缀元素名改写为{*}Name形式。"""
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
        """将无命名空间前缀的XPath改写为可匹配任意命名空间的形式。"""
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
        """命名空间兼容的findall，先原路径再{*}回退匹配。"""
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
    def update(
            cls,
            xml_data: Union[str, ElementTree.Element],
            xpath: str,
            value: Any,
    ) -> str:
        """
        按XPath更新匹配节点文本并返回XML字符串(语义对齐 XPathUtils.update)。

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
        按XPath查询并返回匹配结果(语义对齐 XPathUtils.query)。

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

        return cls.element_extract_value(elements[-1])

    @classmethod
    def element_extract_value(cls, element: ElementTree.Element) -> str:
        """
        提取单个元素的值：有子节点时返回整段序列化，否则返回叶子文本。

        父节点的element.text往往是子标签前的换行/缩进，不能当作有效取值。
        """
        if len(element) > 0:
            return ElementTree.tostring(element, encoding="unicode")
        return element.text if element.text else ElementTree.tostring(element, encoding="unicode")


# ============================ JSON 报文替换(对齐 json_replace.JsonDatagram) ============================

class PerfJsonDatagram:
    """根据JSONPath映射更新JSON请求报文(语义对齐 JsonDatagram)。"""

    @staticmethod
    def _jsonpath_hits(json_path: str, *candidates: Any) -> bool:
        """
        判定JSONPath是否在任一候选数据中命中；两段内嵌路径仅按第一段判定。

        :param json_path: JSONPath表达式，可含'outer@JSON@inner'两段形式
        :param candidates: 候选数据（dict/list或可解析为dict的JSON字符串）
        :return: 任一候选命中即为True
        """
        if not json_path or not isinstance(json_path, str):
            return False

        outer_path = json_path.split("@JSON@", 1)[0].strip()
        if not outer_path:
            return False

        try:
            expr = jsonpath_ng_parse(outer_path)
        except Exception:
            return False
        for data in candidates:
            if data is None:
                continue
            if isinstance(data, str):
                try:
                    data = orjson.loads(data) if data.strip() else None
                except (TypeError, orjson.JSONDecodeError):
                    continue
            if not isinstance(data, (dict, list)):
                continue
            if expr.find(data):
                return True

        return False

    @staticmethod
    def _query_target_value(datagram: Dict[str, Any], json_path: str) -> Any:
        """
        查询JSONPath在报文中的当前字段值，作为dataset值类型适配参考。

        未命中返回空列表、多命中或容器值返回列表本身，二者经适配器原样接受(不做类型转换，由用户负责)；
        查询异常返回_QUERY_UNRESOLVED哨兵，适配器同样走原样接受线路（与字段值为null的语义分离，
        为null字段类型恢复扩展保留区分）。

        :param datagram: 报文字典
        :param json_path: JSONPath表达式
        :return: 当前字段值；未命中返回空列表；异常返回哨兵对象
        """
        try:
            return jsonpath_query(datagram, json_path)
        except Exception:
            return _QUERY_UNRESOLVED

    @staticmethod
    def _adapt_json_value(json_value: Any, datagram: Dict[str, Any], query_path: str, type_adapted: bool) -> Any:
        """
        解析注入值：body通道按报文原字段类型适配(可转换则转换，无法转换原样接受由用户负责)；
        字符串通道(type_adapted=False)wire文本直写，不做贴合判断也不做类型参考查询。

        :param json_value: dataset字段值(字符串通道调用前已转wire文本)
        :param datagram: 类型参考查询的数据容器(body通道为报文字典或两段式inner子文档)
        :param query_path: 类型参考查询用的JSONPath(两段式时为inner路径)
        :param type_adapted: JSON body通道True；header/form/urlencoded等字符串通道False
        :return: 适配后的注入值
        """
        if not type_adapted:
            return json_value
        return DatasetValueAdapter.adapt(
            raw_value=json_value,
            target_value=PerfJsonDatagram._query_target_value(
                datagram=datagram,
                json_path=query_path
            )
        )

    @staticmethod
    def _by_jsonpath_modify_inner_content(
            datagram: Dict[str, Any],
            json_path: str,
            json_value: Any,
            split_symbol: str = "@JSON@",
            type_adapted: bool = True,
    ) -> None:
        """
        根据两段内嵌JSONPath定位并更新字段值，无@JSON@分隔符时退化为普通单段JSONPath更新。

        约定第一段JSONPath定位到一个字符串JSON或dict字段，第二段JSONPath在该字段值所代表的JSON内部继续定位并更新，
        最后把更新结果回写到第一段JSONPath对应的字段，形如：$.escape_field@JSON@$.name。

        :param datagram: 待更新的JSON报文字典
        :param json_path: 形如'outer@JSON@inner'的两段JSONPath，无分隔符时根据单段处理
        :param json_value: 要写入的目标值(dataset值，按报文原字段类型适配后写入)
        :param split_symbol: 两段路径的分隔符，默认'@JSON@'
        :param type_adapted: 是否按报文原字段类型适配dataset值；JSON body通道为True，
                             header/form/urlencoded等字符串通道传False(wire文本直接写入不做贴合判断)
        """
        if not json_path or not isinstance(json_path, str):
            return
        if not split_symbol or split_symbol not in json_path:
            adapted = PerfJsonDatagram._adapt_json_value(
                json_value=json_value,
                datagram=datagram,
                query_path=json_path,
                type_adapted=type_adapted
            )
            jsonpath_update(datagram, json_path, adapted)
            return

        json_parts: List[str] = json_path.split(split_symbol)
        if len(json_parts) != 2:
            jsonpath_update(json_data=datagram, json_path=json_path, value=json_value)
            return

        outer_path, inner_path = json_parts[0].strip(), json_parts[1].strip()
        if not outer_path or not inner_path:
            return

        # 统一为单前缀形态：第二段带$.时不再重复加前缀，
        # 避免'$.$.x'写入侧(jsonpath_ng容错命中)与查询侧(jsonpath库未命中)行为不一致
        inner_path = inner_path if inner_path.startswith("$.") else "$." + inner_path
        outer_value: Optional[Union[str, List[Any], Dict[str, Any]]] = jsonpath_query(datagram, outer_path)
        if outer_value == [] or outer_value is None:
            return

        # JSONPath可能返回多个命中，此处按单命中处理
        if isinstance(outer_value, list):
            if len(outer_value) != 1:
                return
            outer_value = outer_value[0]

        if isinstance(outer_value, str):
            try:
                inner_obj = orjson.loads(outer_value) if outer_value.strip() else {}
            except (TypeError, orjson.JSONDecodeError):
                return
            adapted = PerfJsonDatagram._adapt_json_value(
                json_value=json_value,
                datagram=inner_obj,
                query_path=inner_path,
                type_adapted=type_adapted
            )
            updated_inner_json = jsonpath_update(inner_obj, inner_path, adapted)
            if not isinstance(updated_inner_json, str):
                return
            jsonpath_update(datagram, outer_path, updated_inner_json)
            return

        if isinstance(outer_value, dict):
            adapted = PerfJsonDatagram._adapt_json_value(
                json_value=json_value,
                datagram=outer_value,
                query_path=inner_path,
                type_adapted=type_adapted
            )
            updated_inner_json = jsonpath_update(outer_value, inner_path, adapted)
            if not isinstance(updated_inner_json, str):
                return
            try:
                updated_inner_obj = orjson.loads(updated_inner_json)
            except (TypeError, orjson.JSONDecodeError):
                updated_inner_obj = outer_value
            jsonpath_update(datagram, outer_path, updated_inner_obj)
            return

        # 其他类型暂不处理
        return

    @staticmethod
    def _by_jsonpath_modify_request_header(json_path: str) -> str:
        """
        从JSONPath提取HTTP请求头字段名。

        例如$.Content-Type -> Content-Type

        :param json_path: JSONPath字符串
        :return: 头字段名；无效时返回空串
        """
        if not json_path or not isinstance(json_path, str):
            return ""
        parts = json_path.strip().split("$.", 1)
        return parts[-1].strip() if parts and parts[-1] else ""

    @staticmethod
    def _by_jsonpath_modify_request_params(
            path_map: Dict[str, Any],
            *,
            request_body: Any,
            form_data: Optional[Dict[str, Any]],
            urlencoded: Optional[Dict[str, Any]],
    ) -> Any:
        """
        将JSONPath映射写入body/form/urlencoded，原地修改dict，找不到路径则忽略。

        :param path_map: JSONPath->值的映射
        :param request_body: 原始body（dict或可解析为dict的JSON字符串）
        :param form_data: form-data字典，原地修改；可为None
        :param urlencoded: x-www-form-urlencoded字典，原地修改；可为None
        :return: 写入后的request_body
        """
        if not path_map:
            return request_body

        rb = request_body
        if isinstance(rb, dict):
            for json_path, json_value in path_map.items():
                if not json_path:
                    continue
                PerfJsonDatagram._by_jsonpath_modify_inner_content(
                    datagram=rb,
                    json_path=json_path,
                    json_value=json_value
                )
        elif isinstance(rb, str):
            try:
                payload_dict = orjson.loads(rb) if rb.strip() else {}
                if isinstance(payload_dict, dict):
                    for json_path, json_value in path_map.items():
                        if not json_path:
                            continue
                        PerfJsonDatagram._by_jsonpath_modify_inner_content(
                            datagram=payload_dict,
                            json_path=json_path,
                            json_value=json_value
                        )
                    rb = payload_dict
            except (TypeError, orjson.JSONDecodeError):
                pass
        if isinstance(form_data, dict):
            for json_path, json_value in path_map.items():
                if not json_path:
                    continue
                PerfJsonDatagram._by_jsonpath_modify_inner_content(
                    datagram=form_data,
                    json_path=json_path,
                    json_value=expand_dataset_general_value(value=expand_dataset_special_value(value=json_value)),
                    type_adapted=False
                )
        if isinstance(urlencoded, dict):
            for json_path, json_value in path_map.items():
                if not json_path:
                    continue
                PerfJsonDatagram._by_jsonpath_modify_inner_content(
                    datagram=urlencoded,
                    json_path=json_path,
                    json_value=expand_dataset_general_value(value=expand_dataset_special_value(value=json_value)),
                    type_adapted=False
                )
        return rb

    @staticmethod
    def replace_json_datagram(
            *,
            head_map: Optional[Dict[str, Any]] = None,
            body_map: Optional[Dict[str, Any]] = None,
            request_body: Any = None,
            request_headers: Optional[Dict[str, Any]] = None,
            form_data: Optional[Dict[str, Any]] = None,
            urlencoded: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        数据驱动报文替换：根据head_map/body_map将JSONPath应用到请求头与body/form/urlencoded；
        路径在所有通道均未命中时汇总记日志跳过。

        :param head_map: 请求头/报文侧JSONPath->值
        :param body_map: 报文体JSONPath->值
        :param request_body: 原始body（dict或可解析为dict的JSON字符串）
        :param request_headers: 请求头字典；可为None
        :param form_data: form-data字典；可为None
        :param urlencoded: x-www-form-urlencoded字典；可为None
        :return: 含headers/request_body/form_data/urlencoded的字典
        """
        head_map = head_map or {}
        body_map = body_map or {}
        channels = (request_body, form_data, urlencoded)
        missed_paths: List[str] = []
        for json_path in head_map:
            if not json_path:
                continue
            header_key = PerfJsonDatagram._by_jsonpath_modify_request_header(json_path)
            if (request_headers is not None and header_key in request_headers) or PerfJsonDatagram._jsonpath_hits(json_path, *channels):
                continue
            missed_paths.append(json_path)
        for json_path in body_map:
            if not json_path or PerfJsonDatagram._jsonpath_hits(json_path, *channels):
                continue
            missed_paths.append(json_path)
        if request_headers is not None:
            for json_path, json_value in head_map.items():
                if not json_path:
                    continue
                key = PerfJsonDatagram._by_jsonpath_modify_request_header(json_path)
                if key and key in request_headers:
                    request_headers[key] = expand_dataset_general_value(value=expand_dataset_special_value(value=json_value))

        rb = request_body
        rb = PerfJsonDatagram._by_jsonpath_modify_request_params(
            path_map=head_map,
            request_body=rb,
            form_data=form_data,
            urlencoded=urlencoded
        )
        rb = PerfJsonDatagram._by_jsonpath_modify_request_params(
            path_map=body_map,
            request_body=rb,
            form_data=form_data,
            urlencoded=urlencoded
        )
        if missed_paths:
            LOGGER.info(f"【报文替换】数据源路径在报文中未命中已跳过: {', '.join(missed_paths)}")
        return {
            "headers": request_headers,
            "request_body": rb,
            "form_data": form_data,
            "urlencoded": urlencoded,
        }


# ============================ XML 报文替换(对齐 xml_replace.XmlDatagram) ============================

class PerfXmlDatagram:
    """根据XPath映射更新XML请求报文(语义对齐 XmlDatagram)。"""

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
            if PerfXPath.query(request_text, xpath_expr) is None:
                missed_paths.append(xpath_expr)
            try:
                request_text = PerfXPath.update(
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
