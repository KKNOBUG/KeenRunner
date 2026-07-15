# -*- coding: utf-8 -*-
"""
数据驱动 JSON 报文替换（请求头 / body / form / urlencoded）。

支持普通 JSONPath 与 ``outer@JSON@inner`` 两段内嵌路径更新。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import orjson

from backend.common import JSONPathUtils


class JsonDatagram:
    """按 JSONPath 映射原地（或解析后）更新 JSON 请求报文。"""

    @staticmethod
    def _by_jsonpath_modify_inner_content(datagram: Dict[str, Any], json_path: str, json_value: Any, split_symbol: str = "@JSON@") -> None:
        """
        支持两段 JSONPath，用于类似：
          $.escape_field@JSON@$.name

        约定：
        - 第一段 JSONPath 定位到一个“字符串 JSON”或“dict”字段
        - 第二段 JSONPath 在该字段值所代表的 JSON 内部继续定位并更新
        - 最后把更新结果回写到第一段 JSONPath 对应的字段
        """
        if not json_path or not isinstance(json_path, str):
            return
        if not split_symbol or split_symbol not in json_path:
            JSONPathUtils.update(datagram, json_path, json_value)
            return

        json_parts: List[str] = json_path.split(split_symbol)
        if len(json_parts) != 2:
            # 兜底：无法识别链路，按原逻辑尝试普通更新
            JSONPathUtils.update(datagram, json_path, json_value)
            return

        outer_path, inner_path = json_parts[0].strip(), json_parts[1].strip()
        if not outer_path or not inner_path:
            return

        inner_path = "$." + inner_path
        outer_value: Union[str, list] = JSONPathUtils.query(datagram, outer_path)
        if outer_value == [] or outer_value is None:
            return

        # JSONPath 可能返回多个命中；这里按“单命中”处理（符合你描述的两段链路）
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
        从 JSONPath 提取 HTTP 请求头字段名。

        例如 $.Content-Type -> Content-Type

        :param json_path: JSONPath 字符串
        :return: 头字段名；无效时返回空串
        """
        if not json_path or not isinstance(json_path, str):
            return ""
        s = json_path.strip()
        if s.startswith("$."):
            s = s[2:]
        return s.split(".")[0].strip() if s else ""

    @staticmethod
    def _by_jsonpath_modify_request_params(
            path_map: Dict[str, Any],
            *,
            request_body: Any,
            form_data: Optional[Dict[str, Any]],
            urlencoded: Optional[Dict[str, Any]],
    ) -> Any:
        """
        将 JSONPath -> 值的映射写入 request_body（dict 或可解析为 dict 的 JSON 字符串）、
        form-data、urlencoded；原地修改 dict，找不到路径则忽略（与 JSONPathUtils 行为一致）。
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
        数据驱动报文替换：先按 head_map 更新请求头键值，再依次将 head_map、body_map
        按 JSONPath 应用到 request_body / form_data / urlencoded。

        规则说明：
        - head_map 中路径会先解析为请求头字段名，仅当该键已存在于 request_headers 时覆盖；
        - head_map 与 body_map 均会写入 body/form/urlencoded（request_body 中也可能出现 head 侧路径）；
        - 支持 ``outer@JSON@inner`` 两段内嵌 JSONPath；找不到路径时忽略（与 JSONPathUtils 一致）。

        :param head_map: 请求头 / 报文侧 JSONPath -> 值
        :param body_map: 报文体 JSONPath -> 值
        :param request_body: 原始 body（dict 或可解析为 dict 的 JSON 字符串）
        :param request_headers: 请求头字典；可为 None（则不改头）
        :param form_data: form-data 字典；可为 None
        :param urlencoded: x-www-form-urlencoded 字典；可为 None
        :return: 含 ``headers`` / ``request_body`` / ``form_data`` / ``urlencoded`` 的字典
            （dict 入参多为原地修改后的同一引用）
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
