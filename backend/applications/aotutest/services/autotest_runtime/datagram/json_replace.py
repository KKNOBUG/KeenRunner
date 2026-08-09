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

from backend.common import JSONPathUtils


class JsonDatagram:
    """根据JSONPath映射原地（或解析后）更新JSON请求报文。"""

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

        # JSONPath 可能返回多个命中；这里根据“单命中”处理（符合你描述的两段链路）
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
            # 回写时保持 outer 类型仍为字符串 JSON
            JSONPathUtils.update(datagram, outer_path, updated_inner_json)
            return

        if isinstance(outer_value, dict):
            updated_inner_json = JSONPathUtils.update(outer_value, inner_path, json_value)
            try:
                updated_inner_obj = orjson.loads(updated_inner_json)
            except (TypeError, orjson.JSONDecodeError):
                updated_inner_obj = outer_value
            # 回写时保持 outer 类型仍为 dict
            JSONPathUtils.update(datagram, outer_path, updated_inner_obj)
            return

        # 其他类型暂不处理（例如 int/float/bool）
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
        将JSONPath->值的映射写入request_body（dict或可解析为dict的JSON字符串）、form-data、urlencoded，
        原地修改dict，找不到路径则忽略（与JSONPathUtils行为一致）。

        :param path_map: JSONPath->值的映射
        :param request_body: 原始body（dict或可解析为dict的JSON字符串）
        :param form_data: form-data字典，原地修改；可为None
        :param urlencoded: x-www-form-urlencoded字典，原地修改；可为None
        :return: 写入后的request_body，字符串body解析为dict时返回该dict，否则返回原值
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
                JsonDatagram._by_jsonpath_modify_inner_content(form_data, json_path, json_value)
        if isinstance(urlencoded, dict):
            for json_path, json_value in path_map.items():
                if not json_path:
                    continue
                JsonDatagram._by_jsonpath_modify_inner_content(urlencoded, json_path, json_value)
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
        数据驱动报文替换：先根据head_map更新请求头键值，再依次将head_map、body_map
        根据JSONPath应用到request_body/form_data/urlencoded。

        规则说明：head_map中路径会先解析为请求头字段名，仅当该键已存在于request_headers时覆盖；
        head_map与body_map均会写入body/form/urlencoded（request_body中也可能出现head侧路径）；
        支持'outer@JSON@inner'两段内嵌JSONPath，找不到路径时忽略（与JSONPathUtils一致）。

        :param head_map: 请求头/报文侧JSONPath->值
        :param body_map: 报文体JSONPath->值
        :param request_body: 原始body（dict或可解析为dict的JSON字符串）
        :param request_headers: 请求头字典；可为None（则不改头）
        :param form_data: form-data字典；可为None
        :param urlencoded: x-www-form-urlencoded字典；可为None
        :return: 含'headers'/'request_body'/'form_data'/'urlencoded'的字典
            （dict入参多为原地修改后的同一引用）
        """
        head_map = head_map or {}
        body_map = body_map or {}
        if request_headers is not None:
            for json_path, json_value in head_map.items():
                if not json_path:
                    continue
                key = JsonDatagram._by_jsonpath_modify_request_header(json_path)
                if key and key in request_headers:
                    request_headers[key] = json_value

        rb = request_body
        rb = JsonDatagram._by_jsonpath_modify_request_params(
            head_map, request_body=rb, form_data=form_data, urlencoded=urlencoded
        )
        rb = JsonDatagram._by_jsonpath_modify_request_params(
            body_map, request_body=rb, form_data=form_data, urlencoded=urlencoded
        )
        return {
            "headers": request_headers,
            "request_body": rb,
            "form_data": form_data,
            "urlencoded": urlencoded,
        }
