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

from backend.common import JSONPathUtils
from backend.configure import LOGGER


class JsonDatagram:
    """根据JSONPath映射原地（或解析后）更新JSON请求报文。"""

    @staticmethod
    def _as_wire_string(value: Any) -> str:
        """将值转为协议文本：bool用true/false，None为空串，其余取str。"""
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

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
    def _by_jsonpath_modify_inner_content(datagram: Dict[str, Any], json_path: str, json_value: Any, split_symbol: str = "@JSON@") -> None:
        """
        根据两段内嵌JSONPath定位并更新字段值，无@JSON@分隔符时退化为普通单段JSONPath更新。

        约定第一段JSONPath定位到一个字符串JSON或dict字段，第二段JSONPath在该字段值所代表的JSON内部继续定位并更新，
        最后把更新结果回写到第一段JSONPath对应的字段，形如：$.escape_field@JSON@$.name。

        :param datagram: 待更新的JSON报文字典
        :param json_path: 形如'outer@JSON@inner'的两段JSONPath，无分隔符时根据单段处理
        :param json_value: 要写入的目标值
        :param split_symbol: 两段路径的分隔符，默认'@JSON@'
        """
        if not json_path or not isinstance(json_path, str):
            return
        if not split_symbol or split_symbol not in json_path:
            JSONPathUtils.update(datagram, json_path, json_value)
            return

        json_parts: List[str] = json_path.split(split_symbol)
        if len(json_parts) != 2:
            # 兜底：无法识别链路，根据原逻辑尝试普通更新
            JSONPathUtils.update(datagram, json_path, json_value)
            return

        outer_path, inner_path = json_parts[0].strip(), json_parts[1].strip()
        if not outer_path or not inner_path:
            return

        inner_path = "$." + inner_path
        outer_value: Optional[Union[str, list, dict]] = JSONPathUtils.query(datagram, outer_path)
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
            updated_inner_json = JSONPathUtils.update(inner_obj, inner_path, json_value)
            # 回写时保持outer类型为字符串JSON
            JSONPathUtils.update(datagram, outer_path, updated_inner_json)
            return

        if isinstance(outer_value, dict):
            updated_inner_json = JSONPathUtils.update(outer_value, inner_path, json_value)
            try:
                updated_inner_obj = orjson.loads(updated_inner_json)
            except (TypeError, orjson.JSONDecodeError):
                updated_inner_obj = outer_value
            # 回写时保持outer类型为dict
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
                JsonDatagram._by_jsonpath_modify_inner_content(rb, json_path, json_value)
        elif isinstance(rb, str):
            try:
                payload_dict = orjson.loads(rb) if rb.strip() else {}
                if isinstance(payload_dict, dict):
                    for json_path, json_value in path_map.items():
                        if not json_path:
                            continue
                        JsonDatagram._by_jsonpath_modify_inner_content(payload_dict, json_path, json_value)
                    rb = payload_dict
            except (TypeError, orjson.JSONDecodeError):
                pass
        if isinstance(form_data, dict):
            for json_path, json_value in path_map.items():
                if not json_path:
                    continue
                JsonDatagram._by_jsonpath_modify_inner_content(
                    form_data, json_path, JsonDatagram._as_wire_string(json_value)
                )
        if isinstance(urlencoded, dict):
            for json_path, json_value in path_map.items():
                if not json_path:
                    continue
                JsonDatagram._by_jsonpath_modify_inner_content(
                    urlencoded, json_path, JsonDatagram._as_wire_string(json_value)
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
        数据驱动报文替换：根据head_map和body_map将JSONPath应用到body/form/urlencoded。

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
                    request_headers[key] = JsonDatagram._as_wire_string(json_value)

        rb = request_body
        rb = JsonDatagram._by_jsonpath_modify_request_params(
            head_map, request_body=rb, form_data=form_data, urlencoded=urlencoded
        )
        rb = JsonDatagram._by_jsonpath_modify_request_params(
            body_map, request_body=rb, form_data=form_data, urlencoded=urlencoded
        )
        if missed_paths:
            LOGGER.info(f"【JSON报文替换】数据源路径在报文中未命中已跳过: {', '.join(missed_paths)}")
        return {
            "headers": request_headers,
            "request_body": rb,
            "form_data": form_data,
            "urlencoded": urlencoded,
        }
