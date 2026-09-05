# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : json_replace.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import orjson
from jsonpath_ng import parse

from backend.applications.autotest.services.autotest_runtime.datagram.value_adapter import (
    DatasetValueAdapter,
    expand_dataset_special_value,
    expand_dataset_general_value,
)
from backend.common import JSONPathUtils
from backend.configure import LOGGER

_QUERY_UNRESOLVED = object()


class JsonDatagram:
    """根据JSONPath映射更新JSON请求报文。"""

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
            expr = parse(outer_path)
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

        未命中返回空列表、多命中或容器值返回列表本身，二者经适配器按不采纳处理(跳过注入)；
        查询异常返回_QUERY_UNRESOLVED哨兵，适配器走原样接受线路（与字段值为null的语义分离，
        为null字段类型恢复扩展保留区分）。

        :param datagram: 报文字典
        :param json_path: JSONPath表达式
        :return: 当前字段值；未命中返回空列表；异常返回哨兵对象
        """
        try:
            return JSONPathUtils.query(datagram, json_path)
        except Exception:
            return _QUERY_UNRESOLVED

    @staticmethod
    def _adapt_json_value(json_value: Any, datagram: Dict[str, Any], query_path: str, json_path: str, type_adapted: bool) -> Any:
        """
        解析注入值：body通道按报文原字段类型贴合适配，类型不贴合(不采纳哨兵)时记录跳过日志；
        字符串通道(type_adapted=False)wire文本直写，不做贴合判断也不做类型参考查询。

        :param json_value: dataset字段值(字符串通道调用前已转wire文本)
        :param datagram: 类型参考查询的数据容器(body通道为报文字典或两段式inner子文档)
        :param query_path: 类型参考查询用的JSONPath(两段式时为inner路径)
        :param json_path: 完整JSONPath表达式(日志定位用)
        :param type_adapted: JSON body通道True；header/form/urlencoded等字符串通道False
        :return: 注入值；DatasetValueAdapter.ADAPT_REJECTED表示类型不贴合应跳过
        """
        if not type_adapted:
            return json_value
        adapted = DatasetValueAdapter.adapt(
            raw_value=json_value,
            target_value=JsonDatagram._query_target_value(
                datagram=datagram,
                json_path=query_path
            )
        )
        if adapted is DatasetValueAdapter.ADAPT_REJECTED:
            LOGGER.info(f"【报文替换】dataset值与报文字段类型不贴合已跳过: {json_path}")
        return adapted

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
            adapted = JsonDatagram._adapt_json_value(
                json_value=json_value,
                datagram=datagram,
                query_path=json_path,
                json_path=json_path,
                type_adapted=type_adapted
            )
            if adapted is DatasetValueAdapter.ADAPT_REJECTED:
                return
            JSONPathUtils.update(datagram, json_path, adapted)
            return

        json_parts: List[str] = json_path.split(split_symbol)
        if len(json_parts) != 2:
            JSONPathUtils.update(json_data=datagram, json_path=json_path, value=json_value)
            return

        outer_path, inner_path = json_parts[0].strip(), json_parts[1].strip()
        if not outer_path or not inner_path:
            return

        # 统一为单前缀形态：第二段带$.时不再重复加前缀，
        # 避免'$.$.x'写入侧(jsonpath_ng容错命中)与查询侧(jsonpath库未命中)行为不一致
        inner_path = inner_path if inner_path.startswith("$.") else "$." + inner_path
        outer_value: Optional[Union[str, List[Any], Dict[str, Any]]] = JSONPathUtils.query(datagram, outer_path)
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
            adapted = JsonDatagram._adapt_json_value(
                json_value=json_value,
                datagram=inner_obj,
                query_path=inner_path,
                json_path=json_path,
                type_adapted=type_adapted
            )
            if adapted is DatasetValueAdapter.ADAPT_REJECTED:
                return
            updated_inner_json = JSONPathUtils.update(inner_obj, inner_path, adapted)
            if not isinstance(updated_inner_json, str):
                return
            JSONPathUtils.update(datagram, outer_path, updated_inner_json)
            return

        if isinstance(outer_value, dict):
            adapted = JsonDatagram._adapt_json_value(
                json_value=json_value,
                datagram=outer_value,
                query_path=inner_path,
                json_path=json_path,
                type_adapted=type_adapted
            )
            if adapted is DatasetValueAdapter.ADAPT_REJECTED:
                return
            updated_inner_json = JSONPathUtils.update(outer_value, inner_path, adapted)
            if not isinstance(updated_inner_json, str):
                return
            try:
                updated_inner_obj = orjson.loads(updated_inner_json)
            except (TypeError, orjson.JSONDecodeError):
                updated_inner_obj = outer_value
            JSONPathUtils.update(datagram, outer_path, updated_inner_obj)
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
                JsonDatagram._by_jsonpath_modify_inner_content(
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
                        JsonDatagram._by_jsonpath_modify_inner_content(
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
                JsonDatagram._by_jsonpath_modify_inner_content(
                    datagram=form_data,
                    json_path=json_path,
                    json_value=expand_dataset_general_value(value=expand_dataset_special_value(value=json_value)),
                    type_adapted=False
                )
        if isinstance(urlencoded, dict):
            for json_path, json_value in path_map.items():
                if not json_path:
                    continue
                JsonDatagram._by_jsonpath_modify_inner_content(
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
            header_key = JsonDatagram._by_jsonpath_modify_request_header(json_path)
            if (request_headers is not None and header_key in request_headers) or JsonDatagram._jsonpath_hits(json_path, *channels):
                continue
            missed_paths.append(json_path)
        for json_path in body_map:
            if not json_path or JsonDatagram._jsonpath_hits(json_path, *channels):
                continue
            missed_paths.append(json_path)
        if request_headers is not None:
            for json_path, json_value in head_map.items():
                if not json_path:
                    continue
                key = JsonDatagram._by_jsonpath_modify_request_header(json_path)
                if key and key in request_headers:
                    request_headers[key] = expand_dataset_general_value(value=expand_dataset_special_value(value=json_value))

        rb = request_body
        rb = JsonDatagram._by_jsonpath_modify_request_params(
            path_map=head_map,
            request_body=rb,
            form_data=form_data,
            urlencoded=urlencoded
        )
        rb = JsonDatagram._by_jsonpath_modify_request_params(
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
