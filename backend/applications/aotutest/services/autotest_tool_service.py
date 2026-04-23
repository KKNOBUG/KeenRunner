# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_tool_service
@DateTime: 2026/1/17 12:20
"""
from __future__ import annotations

import ast
import json
import re
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Callable, Union
from xml.etree import ElementTree as ET

from jsonpath_ng import parse as jsonpath_parse

from backend.applications.aotutest.schemas.autotest_step_schema import AutoTestStepTreeUpdateItem
from backend.common import JSONPathUtils
from backend.common.generate_utils import GenerateUtils


class AutoTestToolService:
    """服务层：对外稳定 API；内部实现见 `AutoTestToolServiceImpl`"""

    @classmethod
    def list_to_dict(cls, variable_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        将 key/value/desc 列表转为 name -> value 字典, 供 **Python 代码命名空间** 使用

        与 convert_list_to_dict_for_http 的区别：本函数仅保留含 "value" 键的项(skip_if_no_value=True),
        无 value 的项不进入结果, 避免在 exec 命名空间中注入 key->None 导致歧义或异常
        使用处：StepExecutionContext.clone_state(), 将 defined_variables / session_variables 转为字典后
        作为 run_python_code(..., namespace=...) 的命名空间

        :param variable_list: 变量列表, 每项为含 key、value 的字典
        :return: 键为变量名、值为变量值的字典
        """
        variable_list: List[Dict[str, Any]] = variable_list if isinstance(variable_list, list) else []
        return AutoTestToolServiceImpl.key_value_list_to_dict(items=variable_list, skip_if_no_value=True)

    @classmethod
    def convert_list_to_dict_for_http(cls, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        将 key/value/desc 列表转为 key -> value 字典, 供 **HTTP 请求头/参数/表单** 使用

        与 list_to_dict 的区别：本函数不要求项必有 "value"(skip_if_no_value=False), 只要有 "key" 即加入结果,
        value 可为 None, 以支持 HTTP 中合法的空值(如空 header、未填表单字段)
        使用处：HttpStepExecutor 中将 request_header、request_params、form_data、urlencoded、form_files
        等列表转为字典后传给 httpx 发请求

        :param data: 每项含 key、value 的列表
        :return: 键值对字典；非列表入参返回空字典
        """
        return AutoTestToolServiceImpl.key_value_list_to_dict(data if isinstance(data, list) else [], skip_if_no_value=False)

    @staticmethod
    def get_value_from_list(variable_list: List[Dict[str, Any]], name: str) -> Any:
        """
        从 key/value/desc 列表中取 key 为 name 的项的 value

        :param variable_list: 变量列表, 每项为含 key、value 的字典
        :param name: 要查找的 key 名
        :return: 对应的 value, 未找到返回 None
        """
        if not isinstance(variable_list, list):
            return None
        for item in variable_list:
            if isinstance(item, dict) and item.get("key") == name:
                return item.get("value")
        return None

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
        按 JSONPath 应用到 request_body / form_data / urlencoded（与仅 body_map 时的规则一致；
        request_body 中也可能出现 head 侧 JSONPath）。
        :returns: 含 request_body、headers、form_data、urlencoded 的字典（多为原地修改后的引用）。
        """
        head_map = head_map or {}
        body_map = body_map or {}
        if request_headers is not None:
            for json_path, json_value in head_map.items():
                if not json_path:
                    continue
                key = AutoTestToolServiceImpl.by_jsonpath_modify_request_header(json_path)
                if key and key in request_headers:
                    request_headers[key] = json_value

        rb = request_body
        rb = AutoTestToolServiceImpl.by_jsonpath_modify_request_params(
            head_map, request_body=rb, form_data=form_data, urlencoded=urlencoded
        )
        rb = AutoTestToolServiceImpl.by_jsonpath_modify_request_params(
            body_map, request_body=rb, form_data=form_data, urlencoded=urlencoded
        )
        return {
            "headers": request_headers,
            "request_body": rb,
            "form_data": form_data,
            "urlencoded": urlencoded,
        }

    @staticmethod
    def acquire_dataset_payload(step_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """将数据源单行解析为步骤内使用的 head/body/assert_head/assert_body"""
        head = step_data.get("head") or {}
        body = step_data.get("body") or {}
        assert_head = step_data.get("assert-head") or {}
        assert_body = step_data.get("assert-body") or {}
        return {
            "head": head,
            "body": body,
            "assert_head": assert_head,
            "assert_body": assert_body,
        }

    @staticmethod
    def try_serialize_request_body(raw: Any) -> Any:
        """步骤里的 request_body：若为 JSON 字符串则尽量解析为 dict，否则保持原样。"""
        if isinstance(raw, str):
            try:
                return json.loads(raw) if raw.strip() else {}
            except (TypeError, json.JSONDecodeError):
                return raw
        return raw

    @staticmethod
    def try_acquire_step_dataset(step_struct: Optional[Dict[str, Any]]) -> bool:
        """是否存在数据驱动所需的 head/body/断言配置。"""
        if not isinstance(step_struct, dict):
            return False
        return bool(
            step_struct.get("head")
            or step_struct.get("body")
            or step_struct.get("assert_head")
            or step_struct.get("assert_body")
        )

    @staticmethod
    async def load_dataset_for_request_step(
            *,
            case_id: int,
            step_code: Optional[str],
            dataset_name: Optional[str],
            executing_quote_case_id: Optional[int],
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        按 dataset_name + case_id/step_code 加载数据源场景；引用公共脚本执行时不加载。
        :returns: (step_struct, 原始场景 dict 供 dataset_snapshot)；无数据时 (None, None)。
        """
        if not (dataset_name and step_code and not executing_quote_case_id):
            return None
        from backend.applications.aotutest.services.autotest_data_source_crud import AUTOTEST_DATA_SOURCE_CRUD

        step_data = await AUTOTEST_DATA_SOURCE_CRUD.get_dataset_scenario(
            case_id=case_id,
            step_code=step_code,
            dataset_name=dataset_name,
        )
        if not isinstance(step_data, dict):
            return None
        return AutoTestToolService.acquire_dataset_payload(step_data)

    @staticmethod
    def append_assert_to_validators(
            *,
            step_struct: Optional[Dict[str, Dict[str, Any]]],
            validator_results: List[Dict[str, Any]],
            response_text: Optional[str],
            response_json: Any,
            response_headers: Optional[Dict[str, Any]],
            response_cookies: Optional[Dict[str, Any]],
            session_variables_lookup: Optional[Dict[str, Any]],
            compare_fail_message: str = "实际值与期待值不满足指定操作符比较",
    ) -> None:
        """
        将数据驱动场景的 assert_head / assert_body 追加到 validator_results（原地修改）。
        assert_body 在 response_json 为 None 时逐条记失败，与 TCP 步骤原行为一致。
        """
        if not isinstance(step_struct, dict):
            return

        assert_head_map = step_struct.get("assert_head") or {}
        for except_path, except_value in assert_head_map.items():
            if not except_path:
                continue
            header_key = AutoTestToolServiceImpl.by_jsonpath_modify_request_header(except_path) or str(except_path).strip()
            try:
                actual_value = AutoTestToolService.extract_from_source(
                    source="response headers",
                    expr=header_key,
                    range_type="SOME",
                    index=None,
                    response_text=response_text,
                    response_json=response_json,
                    response_headers=response_headers,
                    response_cookies=response_cookies,
                    session_variables_lookup=session_variables_lookup,
                    operation_type="断言验证",
                )
                success = AutoTestToolService.compare_assertion(actual_value, "等于", except_value)
                validator_results.append({
                    "name": except_path,
                    "expr": except_path,
                    "source": "response headers",
                    "operation": "等于",
                    "except_value": except_value,
                    "actual_value": actual_value,
                    "success": success,
                    "error": "" if success else compare_fail_message,
                })
            except Exception as e:
                validator_results.append({
                    "name": except_path,
                    "expr": except_path,
                    "source": "response headers",
                    "operation": "等于",
                    "except_value": except_value,
                    "actual_value": None,
                    "success": False,
                    "error": str(e),
                })

        assert_body_map = step_struct.get("assert_body") or {}
        for except_path, except_value in assert_body_map.items():
            if not except_path:
                continue
            if response_json is None:
                validator_results.append({
                    "name": except_path,
                    "expr": except_path,
                    "source": "response json",
                    "operation": "等于",
                    "except_value": except_value,
                    "actual_value": None,
                    "success": False,
                    "error": "响应不是JSON，无法进行JSONPath断言",
                })
                continue
            try:
                actual_value = AutoTestToolService.extract_from_source(
                    source="response json",
                    expr=except_path,
                    range_type="SOME",
                    index=None,
                    response_text=response_text,
                    response_json=response_json,
                    response_headers=response_headers,
                    response_cookies=response_cookies,
                    session_variables_lookup=session_variables_lookup,
                    operation_type="断言验证",
                )
                success = AutoTestToolService.compare_assertion(actual_value, "等于", except_value)
                validator_results.append({
                    "name": except_path,
                    "expr": except_path,
                    "source": "response json",
                    "operation": "等于",
                    "except_value": except_value,
                    "actual_value": actual_value,
                    "success": success,
                    "error": "" if success else compare_fail_message,
                })
            except Exception as e:
                validator_results.append({
                    "name": except_path,
                    "expr": except_path,
                    "source": "response json",
                    "operation": "等于",
                    "except_value": except_value,
                    "actual_value": None,
                    "success": False,
                    "error": str(e),
                })

    @classmethod
    def format_step_error_message(
            cls,
            step: Dict[str, Any],
            exception: Exception,
            is_child_step: bool = False,
            offset_message: str = ""
    ) -> str:
        """
        格式化步骤执行失败信息, 供步骤引擎中各类执行器统一使用

        :param step: 步骤数据字典, 含 case_id、step_id、step_no、step_code、step_name、step_type 等
        :param exception: 异常对象；错误回溯使用 traceback.format_exc(), 在 except 块内调用时即为该异常的堆栈
        :param is_child_step: 是否为子步骤(True=子步骤, False=根步骤)
        :param offset_message: 关于异常的补偿描述
        :return: 格式化后的错误字符串
        """
        message: str = "【子步骤】" if is_child_step else "【根步骤】"
        offset_message: str = f", {offset_message}" if offset_message else ""
        case_id = step.get("case_id", "获取失败")
        step_id = step.get("step_id", "获取失败")
        step_no = step.get("step_no", "获取失败")
        step_code = step.get("step_code", "获取失败")
        step_name = step.get("step_name", "获取失败")
        step_type = step.get("step_type", "获取失败")
        return (
            f"{message}执行失败{offset_message}: \n"
            f"用例ID: {case_id}, \n"
            f"步骤ID: {step_id}, \n"
            f"步骤序号: {step_no}, \n"
            f"步骤标识: {step_code}, \n"
            f"步骤名称: {step_name}, \n"
            f"步骤类型: {step_type}, \n"
            f"错误描述: {exception}, \n"
            f"错误类型: {type(exception).__name__}, \n"
            f"错误时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, \n"
            f"错误回溯: {traceback.format_exc()}\n"
        )

    @classmethod
    def compare_assertion(cls, actual: Any, operation: str, expected: Any) -> bool:
        return AutoTestToolServiceImpl.compare_assertion(actual, operation, expected)

    @classmethod
    def extract_from_source(
            cls,
            *,
            source: str,
            expr: Optional[str],
            range_type: Optional[str] = "SOME",
            index: Optional[Any] = None,
            response_text: Optional[str] = None,
            response_json: Optional[Union[list, dict]] = None,
            response_headers: Optional[Dict[str, Any]] = None,
            response_cookies: Optional[Dict[str, Any]] = None,
            session_variables_lookup: Optional[Dict[str, Any]] = None,
            operation_type: str = "变量提取",
    ) -> Any:
        """
        从 source 指定来源中按 expr 与 range 提取单个值供 HTTP 调试与步骤引擎共用

        :param source: 来源类型, 如: response json、response xml、response text、response headers、response cookies、session_variables、变量池；数据库步骤可为 variable_name（与响应列表项匹配）
        :param expr: 提取表达式(JSONPath/XPath/正则), SOME 模式必填
        :param range_type: "ALL" 或 "SOME", 默认 "SOME"
        :param index: 提取结果为数组时的下标
        :param response_text: 响应正文
        :param response_json: 响应 JSON
        :param response_headers: 响应头
        :param response_cookies: 响应 Cookie
        :param session_variables_lookup: 变量池字典（Dict[str, Any]），按 JSONPath 取值
        :param operation_type: 错误信息前缀, 如 "变量提取"、"断言验证"
        :return: 提取得到的值
        :raises ValueError: 提取失败时, 携带可读错误信息
        """
        range_type: str = (range_type or "SOME").strip().lower()
        source_strip_lower: str = (source or "").strip().lower()

        if source_strip_lower == "response json":
            if response_json is None:
                raise ValueError(f"【{operation_type}】响应内容不是有效的JSON数据")
            if range_type == "all":
                return response_json
            if not expr:
                raise ValueError(f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是有效的JSONPath表达式")
            try:
                extract_value = AutoTestToolServiceImpl.resolve_json_path(data=response_json, expr=expr)
            except Exception as e:
                raise ValueError(str(e)) from e
            if isinstance(extract_value, list) and index is not None:
                try:
                    index_int = int(index)
                    if index_int < len(extract_value):
                        return extract_value[index_int]
                    raise ValueError(
                        f"【{operation_type}】数组越界, "
                        f"给定索引[{index_int}]不可大于数组长度[{len(extract_value)}]"
                    )
                except (ValueError, TypeError) as e:
                    raise ValueError(f"【{operation_type}】参数[index]必须是类型, 错误描述: {e}") from e
            return extract_value

        if source_strip_lower == "response xml":
            if not response_text:
                raise ValueError(f"【{operation_type}】响应内容不是有效的XML数据")
            if range_type == "all":
                return response_text
            if not expr:
                raise ValueError(f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是有效的XPath表达式")
            try:
                response_xml = ET.fromstring(response_text)
                elements = response_xml.findall(expr)
                if not elements:
                    raise ValueError(f"【{operation_type}】XPath表达式[{expr}]未匹配到元素")
                if index is not None:
                    try:
                        index_int = int(index)
                        if index_int < len(elements):
                            element = elements[index_int]
                            return element.text if element.text else ET.tostring(element, encoding="unicode")
                        raise ValueError(
                            f"【{operation_type}】数组越界, "
                            f"给定索引[{index_int}]不可大于数组长度[{len(elements)}]"
                        )
                    except (ValueError, TypeError) as e:
                        raise ValueError(f"【{operation_type}】参数[index]必须是整数类型, 错误描述: {e}") from e
                element = elements[-1]
                return element.text if element.text else ET.tostring(element, encoding="unicode")
            except ET.ParseError as e:
                raise ValueError(f"【{operation_type}】响应内容不是有效的XML格式, 错误描述: {e}") from e
            except ValueError:
                raise
            except Exception as e:
                raise ValueError(f"【{operation_type}】XPath表达式[{expr}]执行失败, 错误: {e}") from e

        if source_strip_lower == "response text":
            if not response_text:
                raise ValueError(f"【{operation_type}】响应内容不是有效的Text数据")
            if range_type == "all":
                return response_text
            if not expr:
                raise ValueError(f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是有效的正则表达式")
            try:
                match = re.search(expr, response_text)
                if match:
                    return match.group(0)
                raise ValueError(f"【{operation_type}】正则表达式[{expr}]未匹配到内容")
            except re.error as e:
                raise ValueError(f"【{operation_type}】正则表达式执行失败, 错误描述: {e}") from e

        if source_strip_lower == "response headers":
            if not response_headers:
                raise ValueError(f"【{operation_type}】响应 Headers 为空")
            if range_type == "all":
                return response_headers
            if not expr:
                raise ValueError(f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是有效JSONPath表达式")
            try:
                return AutoTestToolServiceImpl.resolve_json_path(data=response_headers, expr=expr)
            except Exception as e:
                raise ValueError(str(e) or f"【{operation_type}】响应 Headers JSONPath匹配失败: {expr}") from e

        if source_strip_lower == "response cookies":
            if not response_cookies:
                raise ValueError(f"【{operation_type}】响应 Cookies 为空")
            if range_type == "all":
                return response_cookies
            if not expr:
                raise ValueError(f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是有效JSONPath表达式")
            try:
                return AutoTestToolServiceImpl.resolve_json_path(data=response_cookies, expr=expr)
            except Exception as e:
                raise ValueError(str(e) or f"【{operation_type}】响应 Cookies JSONPath匹配失败: {expr}") from e

        if source_strip_lower in ("session_variables", "变量池"):
            if not expr:
                raise ValueError(f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是有效JSONPath表达式")
            if session_variables_lookup is None:
                raise ValueError(f"【{operation_type}】变量池未提供")
            if not isinstance(session_variables_lookup, dict):
                raise ValueError(
                    f"【{operation_type}】变量池类型不被支持: {type(session_variables_lookup)}; "
                    f"仅支持 Dict[str, Any] 并使用 JSONPath 取值"
                )
            try:
                return AutoTestToolServiceImpl.resolve_json_path(data=session_variables_lookup, expr=expr)
            except Exception as e:
                raise ValueError(str(e) or f"【{operation_type}】变量池 JSONPath匹配失败: {expr}") from e

        # 数据库请求步骤：source 为「请求」里配置的 variable_name；response_json 为 List[Dict]，每项含 variable_name、sql_data、sql_count 等
        source_strip: str = (source or "").strip()
        if source_strip and isinstance(response_json, list) and response_json:
            all_database_operates_response_safe: bool = all(
                isinstance(db_operate_resp, dict) and ("variable_name" in db_operate_resp or "sql_data" in db_operate_resp)
                for db_operate_resp in response_json
            )
            expr_executive_data: Optional[Dict[str, Any]] = None
            for db_operate_resp in response_json:
                if isinstance(db_operate_resp, dict) and source_strip in db_operate_resp.get("variable_name", []):
                    expr_executive_data = db_operate_resp["sql_data"]
                    break
            if expr_executive_data is not None:
                if range_type == "all":
                    return expr_executive_data
                if not expr:
                    raise ValueError(f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是有效的JSONPath表达式")
                try:
                    extract_value = AutoTestToolServiceImpl.resolve_json_path(data=expr_executive_data, expr=expr)
                except Exception as e:
                    raise ValueError(str(e)) from e

                if isinstance(extract_value, list) and index is not None:
                    try:
                        index_int = int(index)
                        if index_int < len(extract_value):
                            return extract_value[index_int]
                        raise ValueError(
                            f"【{operation_type}】数组越界, "
                            f"给定索引[{index_int}]不可大于数组长度[{len(extract_value)}]"
                        )
                    except (ValueError, TypeError) as e:
                        raise ValueError(f"【{operation_type}】参数[index]必须是整数类型, 错误描述: {e}") from e
                return extract_value
            if all_database_operates_response_safe:
                raise ValueError(
                    f"【{operation_type}】未找到存储变量[{source_strip}]对应的执行结果, "
                    f"请与「数据库具体操作」中的 variable_name 一致"
                )

        raise ValueError(f"【{operation_type}】数据源源类型 {source} 不被支持")

    @classmethod
    def run_extract_variables(
            cls,
            *,
            extract_variables: List[Dict[str, Any]],
            response_text: Optional[str] = None,
            response_json: Optional[Union[list, dict]] = None,
            response_headers: Optional[Dict[str, Any]] = None,
            response_cookies: Optional[Dict[str, Any]] = None,
            session_variables_lookup: Optional[Dict[str, Any]] = None,
            log_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        按 extract_variables 配置从响应/变量池中提取变量供 HTTP 调试与步骤引擎共用

        :param extract_variables: 变量提取配置列表, 每项通常包含 name/source/expr, 且可选 range/index
        :param response_text: HTTP 响应文本(用于 response text / response xml)
        :param response_json: HTTP 响应 JSON(用于 response json)
        :param response_headers: HTTP 响应头(用于 response headers)
        :param response_cookies: HTTP 响应 cookies(用于 response cookies)
        :param session_variables_lookup: 变量池(source=session_variables/变量池 时使用), Dict[str, Any]
        :param log_callback: 可选日志回调
        :returns: (name->value 字典, 结果列表)
                  结果列表每项含 name/source/range/expr/index/extract_value/error/success
        """
        extract_results_dict: Dict[str, Any] = {}
        extract_results_list: List[Dict[str, Any]] = []
        if not extract_variables:
            return extract_results_dict, extract_results_list
        if not isinstance(extract_variables, list):
            if log_callback:
                log_callback(
                    f"【变量提取】表达式列表解析失败: "
                    f"参数[extract_variables]必须是[List[Dict[str, Any]]]类型, "
                    f"但得到[{type(extract_variables)}]类型"
                )
            return extract_results_dict, extract_results_list
        for ext_config in extract_variables:
            if not isinstance(ext_config, dict):
                if log_callback:
                    log_callback(
                        f"【变量提取】表达式子项解析无效(跳过): "
                        f"参数[extract_variables]的子项必须是[Dict[str, Any]]类型, "
                        f"但得到[{type(ext_config)}]类型: {ext_config}"
                    )
                continue
            name = ext_config.get("name")
            expr = ext_config.get("expr")
            source = ext_config.get("source")
            range_type = ext_config.get("range")
            index = ext_config.get("index")
            if not name or not expr or not source:
                if log_callback:
                    log_callback(
                        f"【变量提取】表达式子项解析无效(跳过): "
                        f"参数[name, expr, source]是必须的, 如需继续提取可添加[range, index]参数"
                    )
                continue
            error_msg = ""
            extract_value = None
            try:
                extract_value = cls.extract_from_source(
                    source=source,
                    expr=expr,
                    range_type=range_type,
                    index=index,
                    response_text=response_text,
                    response_json=response_json,
                    response_headers=response_headers,
                    response_cookies=response_cookies,
                    session_variables_lookup=session_variables_lookup,
                    operation_type="变量提取",
                )
                if log_callback:
                    log_callback(f"【变量提取】成功: {name}  <==>  {extract_value}")
            except Exception as e:
                error_msg = str(e)
                if log_callback:
                    log_callback(f"【变量提取】失败: {name}, {error_msg}")
            item = {
                "name": name,
                "source": source,
                "range": range_type,
                "expr": expr,
                "index": index,
                "extract_value": extract_value,
                "error": error_msg,
                "success": error_msg == "",
            }
            extract_results_list.append(item)
            if error_msg == "":
                extract_results_dict[name] = extract_value
        return extract_results_dict, extract_results_list

    @classmethod
    def run_assert_validators(
            cls,
            *,
            assert_validators: List[Dict[str, Any]],
            response_text: Optional[str] = None,
            response_json: Optional[Union[list, dict]] = None,
            response_headers: Optional[Dict[str, Any]] = None,
            response_cookies: Optional[Dict[str, Any]] = None,
            session_variables_lookup: Optional[Dict[str, Any]] = None,
            log_callback: Optional[Callable[[str], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        按 assert_validators 配置从响应/变量池取实际值并与期望值比较供 HTTP 调试与步骤引擎共用

        :param assert_validators: 断言配置列表, 每项通常包含 name/source/expr/operation/except_value
        :param response_text: HTTP 响应文本(用于 response text / response xml)
        :param response_json: HTTP 响应 JSON(用于 response json)
        :param response_headers: HTTP 响应头(用于 response headers)
        :param response_cookies: HTTP 响应 cookies(用于 response cookies)
        :param session_variables_lookup: 变量池(source=session_variables/变量池 时使用), Dict[str, Any]
        :param log_callback: 可选日志回调
        :returns: 每条断言结果列表, 含 name/source/expr/operation/except_value/actual_value/success/error
        """
        validator_results: List[Dict[str, Any]] = []
        if not assert_validators:
            return validator_results
        if not isinstance(assert_validators, list):
            if log_callback:
                log_callback(
                    f"【断言验证】表达式列表解析失败: 参数[assert_validators]必须是[List[Dict[str, Any]]]类型, "
                    f"但得到[{type(assert_validators)}]类型"
                )
            return validator_results
        for validator_config in assert_validators:
            if not isinstance(validator_config, dict):
                if log_callback:
                    log_callback(
                        f"【断言验证】表达式子项解析无效(跳过): "
                        f"参数[assert_validators]的子项必须是[Dict[str, Any]]类型, "
                        f"但得到[{type(validator_config)}]类型: {validator_config}"
                    )
                continue
            name = validator_config.get("name")
            expr = validator_config.get("expr")
            operation = validator_config.get("operation")
            except_value = validator_config.get("except_value")
            source = validator_config.get("source")
            if not name or not expr or not operation or not source:
                if log_callback:
                    log_callback(
                        f"【断言验证】表达式子项解析无效(跳过): "
                        f"参数[name, expr, operation, source]是必须的, 非空断言时需添加[except_value]参数"
                    )
                continue
            error_msg = ""
            success = False
            actual_value = None
            try:
                actual_value = cls.extract_from_source(
                    source=source,
                    expr=expr,
                    range_type="SOME",
                    index=None,
                    response_text=response_text,
                    response_json=response_json,
                    response_headers=response_headers,
                    response_cookies=response_cookies,
                    session_variables_lookup=session_variables_lookup,
                    operation_type="断言验证",
                )
            except Exception as e:
                error_msg = str(e)
                if log_callback:
                    log_callback(f"【断言验证】比较失败: {name}, {error_msg}")
                validator_results.append({
                    "name": name,
                    "source": source,
                    "expr": expr,
                    "operation": operation,
                    "except_value": except_value,
                    "actual_value": actual_value,
                    "success": False,
                    "error": error_msg,
                })
                continue
            try:
                success = cls.compare_assertion(actual=actual_value, operation=operation, expected=except_value)
                if log_callback:
                    expr_message: str = (
                        f"\n\t数据源: [{source}], \n"
                        f"\t表达式: [{expr}], \n"
                        f"\t实际值: [{actual_value}], \n"
                        f"\t操作符: [{operation}], \n"
                        f"\t预期值: [{except_value}]\n\n"
                    )
                    if success:
                        log_callback(f"【断言验证】比较成功: {expr_message}")
                    else:
                        log_callback(f"【断言验证】比较失败: {expr_message}")
            except Exception as e:
                error_msg = str(e)
                success = False
                if log_callback:
                    log_callback(f"【断言验证】比较异常, 错误描述: {e}: {name}, {error_msg}")
            validator_results.append({
                "name": name,
                "source": source,
                "expr": expr,
                "operation": operation,
                "except_value": except_value,
                "actual_value": actual_value,
                "success": success,
                "error": error_msg,
            })
        return validator_results

    @classmethod
    def parse_condition_json(cls, condition: str, error_prefix: str) -> Dict[str, Any]:
        """
        将条件字符串中 Python 风格 None/True/False 转为 JSON 后解析为字典, 供步骤引擎中「循环结构」「条件分支」等使用

        :param condition: JSON 格式条件字符串, 含 value、operation、except_value 等
        :param error_prefix: 错误信息前缀, 如 "循环结构"、"条件分支"
        :return: 解析后的条件字典
        :raises ValueError: 非合法 JSON 或解析异常时, 错误信息会包含 error_prefix
        """
        try:
            normalized = re.sub(r'\bNone\b', 'null', condition)
            normalized = re.sub(r'\bTrue\b', 'true', normalized)
            normalized = re.sub(r'\bFalse\b', 'false', normalized)
            return json.loads(normalized)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"【{error_prefix}】条件表达式不是有效的JSON格式, \n"
                f"错误位置: 第{e.lineno}行, 第{e.colno}列, \n"
                f"错误信息: {e.msg}"
            ) from e
        except Exception as e:
            raise ValueError(f"【{error_prefix}】条件表达式解析异常, 错误详情: {e}") from e

    @classmethod
    def validate_step_tree_structure(cls, steps_data: List[AutoTestStepTreeUpdateItem]) -> tuple:
        """
        校验步骤树结构：无自循环引用, 且仅有「循环结构」「条件分支」类型可包含子步骤

        :param steps_data: 根步骤列表(每项可为带 children 的树节点)
        :return: (True, None) 表示通过；(False, str) 表示失败及错误信息
        """
        from backend.enums import AutoTestStepType

        # 允许有子步骤的步骤类型
        allowed_children_types = {AutoTestStepType.LOOP, AutoTestStepType.IF}

        def check_step_recursive(step: AutoTestStepTreeUpdateItem, visited_ids: set, path: list) -> tuple:
            """
            递归校验单个步骤节点及其 children：
            - 检查 step_id / step_code 自循环
            - 检查非允许类型是否包含 children

            :param step: 当前步骤节点
            :param visited_ids: 已访问 step_id 集合(用于检测自循环)
            :param path: 访问路径 step_code 列表(用于检测自循环)
            :returns: (True, None) 表示通过；(False, str) 表示失败及错误信息
            """
            step_id = step.step_id
            step_code = step.step_code

            # 检查自循环引用
            if step_id and step_id in visited_ids:
                return False, f"步骤(step_id={step_id}, step_code={step_code or 'N/A'})存在自循环引用"
            if step_code and step_code in path:
                return False, f"步骤(step_code={step_code})存在自循环引用"

            # 添加到已访问集合
            if step_id:
                visited_ids.add(step_id)
            if step_code:
                path.append(step_code)

            # 检查步骤类型是否允许有子步骤
            if step.children and len(step.children) > 0:
                if step.step_type not in allowed_children_types:
                    return False, (
                        f"步骤(step_id={step_id}, step_code={step_code or 'N/A'}, "
                        f"step_type={step.step_type})不允许包含子步骤, 仅允许'循环结构'和'条件分支'类型的步骤包含子步骤"
                    )

                # 递归检查子步骤
                for child in step.children:
                    child_is_valid, child_error_msg = check_step_recursive(child, visited_ids.copy(), path.copy())
                    if not child_is_valid:
                        return False, child_error_msg

            return True, None

        # 检查所有根步骤
        for step_data in steps_data:
            root_is_valid, root_error_msg = check_step_recursive(step_data, set(), [])
            if not root_is_valid:
                return False, root_error_msg

        return True, None

    @classmethod
    def normalize_step(cls, step: Dict[str, Any]) -> Dict[str, Any]:
        """
        规范化单条步骤数据：conditions 转为 JSON 字符串、移除 case/quote_case, 并递归规范化 children 与 quote_steps

        :param step: 步骤数据字典(可含 conditions、children、quote_steps 等)
        :return: 规范化后的新字典, 不修改入参
        """
        step = step.copy()

        # 处理conditions：如果是数组, 取第一个并转为JSON字符串
        conditions = step.get("conditions")
        if isinstance(conditions, list) and len(conditions) > 0:
            condition_obj = conditions[0]
            step["conditions"] = json.dumps(condition_obj, ensure_ascii=False)
        elif conditions is None:
            step["conditions"] = None

        # extract_variables和assert_validators保持数组格式(执行引擎已支持)
        # 移除不需要的字段
        step.pop("case", None)
        step.pop("quote_case", None)

        # 递归处理children和quote_steps
        if "children" in step and isinstance(step["children"], list):
            step["children"] = [cls.normalize_step(child) for child in step["children"]]
        if "quote_steps" in step and isinstance(step["quote_steps"], list):
            step["quote_steps"] = [cls.normalize_step(quote_step) for quote_step in step["quote_steps"]]

        return step

    @classmethod
    def collect_session_variables(cls, steps_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        递归收集步骤树中所有步骤的 session_variables, 合并为扁平列表(每项含 key、value、desc)

        :param steps_list: 步骤列表, 每项可含 children、quote_steps
        :return: 合并后的变量列表
        """
        variables = []
        if not steps_list:
            return variables
        for step in steps_list:
            session_variables = step.get("session_variables")
            if isinstance(session_variables, list):
                variables.extend(session_variables)
            # 递归处理children和quote_steps
            children = step.get("children", []) or []
            quote_steps = step.get("quote_steps", []) or []
            variables.extend(cls.collect_session_variables(children))
            variables.extend(cls.collect_session_variables(quote_steps))
        return variables

    @classmethod
    def execute_func_string(cls, session_variables: List[Dict[str, Any]]):
        """
        对会话变量列表中 func_name(...) 形式调用 GenerateUtils(实现见 AutoTestToolServiceImpl)
        :param session_variables:
        :return:
        """
        return AutoTestToolServiceImpl.execute_func_string(session_variables)

    @classmethod
    def execute_func_string_single(cls, content: str) -> Any:
        """
        单条函数字符串执行(实现见 AutoTestToolServiceImpl)
        :param content:
        :return:
        """
        return AutoTestToolServiceImpl.execute_func_string_single(content)

    @classmethod
    def resolve_placeholders(
            cls,
            value: Any,
            logger_object: Callable,
            is_core_engine: bool = False,
            finished_variables: Optional[Any] = None,
    ) -> Any:
        """
        递归解析 str/dict/list 中的 ${...} 占位符(实现见 AutoTestToolServiceImpl)
        :param value:
        :param logger_object:
        :param is_core_engine:
        :param finished_variables:
        :return:
        """
        return AutoTestToolServiceImpl.resolve_placeholders(
            value,
            logger_object,
            is_core_engine=is_core_engine,
            finished_variables=finished_variables,
        )


class AutoTestToolServiceImpl:
    """实现层：占位符解析、断言比较、GenerateUtils 调用等内部逻辑, 仅供 AutoTestToolService 使用"""

    @classmethod
    def key_value_list_to_dict(cls, items: List[Dict[str, Any]], *, skip_if_no_value: bool = False) -> Dict[str, Any]:
        """
        将 List[Dict[str, Any]] 列表嵌套字典的数据平铺为 Dict[str, Any] 格式, 提供变量列表或HTTP请求步骤参数使用

        :param items: 每项元素包含 key、value 的字典的列表
        :param skip_if_no_value: 为 True 时仅当项中含 value 键才加入结果；为 False 时仅要求 "key", value 可为 None
        :return: 键值对字典；非列表入参返回空字典
        """
        if not isinstance(items, list):
            return {}
        result: Dict[str, Any] = {}
        for item in items:
            if not isinstance(item, dict) or "key" not in item:
                continue
            if skip_if_no_value and "value" not in item:
                continue
            key: Optional[str] = item.get("key")
            if key:
                result[key] = item.get("value")
        return result

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        """
        将值标准化为便于比较的类型：数字字符串转 int 或 float, true 或 false 转 bool, 其余原样返回

        :param value: 任意值
        :return: 标准化后的值, 或原值
        """
        if value is None:
            return None
        if isinstance(value, (int, float, bool)):
            return value
        if isinstance(value, str):
            if value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
                return int(value)
            try:
                if '.' in value:
                    return float(value)
            except ValueError:
                pass
            if value.lower() == 'true':
                return True
            if value.lower() == 'false':
                return False
        return value

    @classmethod
    def _type_aware_equals(cls, actual: Any, expected: Any) -> bool:
        """
        类型感知的相等比较：先直接比较, 若不等则对两值做 _normalize_value 后再比较

        :param actual: 实际值
        :param expected: 期望值
        :return: 是否相等
        """
        # 直接比较
        if actual == expected:
            return True
        # 标准化后比较
        norm_actual = cls._normalize_value(actual)
        norm_expected = cls._normalize_value(expected)
        return norm_actual == norm_expected

    @classmethod
    def _type_aware_compare(cls, actual: Any, expected: Any, comparator) -> bool:
        """
        类型感知的大小比较：先标准化再比较；若标准化后均为数值则用数值比较, 否则用字符串比较

        :param actual: 实际值
        :param expected: 期望值
        :param comparator: 二元谓词 (a, b) -> bool, 如 lambda x, y: x > y
        :return: 比较结果
        """
        norm_actual = cls._normalize_value(actual)
        norm_expected = cls._normalize_value(expected)
        # 确保都是数值类型才能进行大小比较
        if isinstance(norm_actual, (int, float)) and isinstance(norm_expected, (int, float)):
            return comparator(norm_actual, norm_expected)
        # 如果不是数值, 尝试字符串比较
        return comparator(str(actual), str(expected))

    @classmethod
    def compare_assertion(cls, actual: Any, operation: str, expected: Any) -> bool:
        """
        根据操作符对实际值与期望值做断言比较, 支持等于、不等于、大于、小于、包含、非空等

        :param actual: 实际值
        :param operation: 操作符名称(如 "等于"、"包含"、"非空")
        :param expected: 期望值(部分操作符可忽略)
        :return: 断言是否通过
        :raises ValueError: 不支持的操作符或比较过程异常
        """
        operator_symbol_mapping: Dict[str, Callable] = {
            "等于": lambda a, b: cls._type_aware_equals(a, b),
            "不等于": lambda a, b: not cls._type_aware_equals(a, b),
            "大于": lambda a, b: cls._type_aware_compare(a, b, lambda x, y: x > y),
            "大于等于": lambda a, b: cls._type_aware_compare(a, b, lambda x, y: x >= y),
            "小于": lambda a, b: cls._type_aware_compare(a, b, lambda x, y: x < y),
            "小于等于": lambda a, b: cls._type_aware_compare(a, b, lambda x, y: x <= y),
            "长度等于": lambda a, b: (lambda nb: len(str(a)) == int(nb) if nb is not None else False)(cls._normalize_value(b)),
            "包含": lambda a, b: str(b) in str(a),
            "不包含": lambda a, b: str(b) not in str(a),
            "以...开始": lambda a, b: str(a).startswith(str(b)),
            "以...结束": lambda a, b: str(a).endswith(str(b)),
            "非空": lambda a, _: a is not None and a != "",
            "为空": lambda a, _: a is None or a == "",
        }
        comparator: Optional[Callable] = operator_symbol_mapping.get(operation)
        if comparator is None:
            raise ValueError(f"【断言表达式】操作符[{operation}]不被支持")
        try:
            return comparator(actual, expected)
        except Exception as e:
            raise ValueError(f"【断言表达式】执行失败, 实际值[{actual}] 操作符[{operation}] 期待值[{expected}] {e}") from e

    @classmethod
    def resolve_json_path(cls, data: Any, expr: str) -> Any:
        """
        使用 JSONPath 表达式从 data 中取值, 支持标准 JSONPath(如 $.data[0].id、$.list[*].name)

        :param data: 待取值的对象(dict/list 或嵌套结构)
        :param expr: 非空字符串, 合法 JSONPath 表达式(如 $.a.b、$.data[0].id、$.items[*].id)
        :return: 单匹配时返回该值, 多匹配时返回值的列表无匹配时抛出 ValueError
        :raises ValueError: 表达式非法、路径无匹配或解析异常时
        """
        expr: str = str(expr).strip()
        if not expr or not isinstance(expr, str):
            raise ValueError(f"【JSONPath表达式】必须是非空字符串")
        if not expr.startswith("$"):
            raise ValueError(f"【JSONPath表达式】必须以$.字符开头")
        if data is None:
            raise ValueError(f"【JSONPath表达式】数据源不允许为空")

        try:
            json_path_expr = jsonpath_parse(expr)
        except Exception as e:
            raise ValueError(f"【JSONPath表达式】执行失败, {e}") from e

        json_path_matches = json_path_expr.find(data)
        if not json_path_matches:
            raise ValueError(f"【JSONPath表达式】匹配失败, 请检查数据源是否包含表达式")

        values = [match.value for match in json_path_matches]
        return values[0] if len(values) == 1 else values

    @classmethod
    def _parse_funcname_funcargs(cls, func_string: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        从 func_name(key1=val1, key2=val2) 格式的字符串中解析出函数名与参数字典

        注意：当前仅支持关键字参数(如: key=value), 并使用 ast.literal_eval 进行字面量解析
        不包含 = 的内容会被忽略(即位置参数不会被解析和记录)

        :param func_string: 函数调用形式的字符串
        :return: 二元祖(函数名, 参数字典), 无法解析时返回 (None, None)
        :raises ValueError: 参数值不是合法字面量或解析失败时
        """
        if not isinstance(func_string, str):
            return None, None
        if not func_string.endswith(")") or func_string.find("(") == -1:
            return None, None
        func_name, func_args = func_string.split("(", 1)
        func_args: str = func_args.rstrip(")")
        args_dict: Dict[str, Any] = {}
        if func_args.strip():
            _args = func_args.split(",")
            for item in _args:
                # key, value = item.split("=")
                # args_dict[str(key).strip()] = eval(value)
                part = item.strip()
                if "=" not in part:
                    continue
                key, _, value_part = part.partition("=")
                key = str(key).strip()
                value_part = value_part.strip()
                try:
                    args_dict[key] = ast.literal_eval(value_part)
                except (ValueError, SyntaxError) as e:
                    raise ValueError(f"【辅助函数】[{func_string!r}]解析失败, 参数仅支持字面量(数字、字符串、布尔、None等), {key}={value_part!r}") from e
        return func_name.strip(), args_dict

    @classmethod
    def execute_func_string(cls, session_variables: List[Dict[str, Any]]):
        """
        针对会话变量中 value 为函数调用字符串格式, 如: func_name(...) 的场景，通过 GenerateUtils 类实现反射机制动态执行对应函数，并将函数返回值替换原变量值
        :param session_variables: 变量列表(列表嵌套字典的数据), 每个元素是包含 key、value、desc 的字典
        :raises AttributeError: 函数不存在、参数不匹配或执行失败时
        """
        if not isinstance(session_variables, list):
            return
        for item in session_variables:
            if not isinstance(item, dict) or "key" not in item or "value" not in item:
                continue
            key = item.get("key")
            func_string = item.get("value")
            if not key or not isinstance(func_string, str):
                continue
            try:
                func_name, func_args = cls._parse_funcname_funcargs(func_string)
            except ValueError as e:
                raise AttributeError(str(e)) from e
            if not func_name and not func_args:
                continue
            if not hasattr(GenerateUtils, func_name):
                raise AttributeError(f"【辅助函数】[{func_name}]调用失败, 未定义或不被允许调用")
            try:
                item["value"] = getattr(GenerateUtils(), func_name)(**func_args or {})
            except TypeError as e:
                raise AttributeError(f"【辅助函数】[{func_name}]调用失败, 参数签名或类型不匹配: {e}") from e
            except SyntaxError as e:
                raise AttributeError(f"【辅助函数】[{func_name}]调用失败, 语法解析失败或未定义: {e}") from e
            except Exception as e:
                raise AttributeError(f"【辅助函数】[{func_name}]调用失败, 在动态注入时发生异常: {e}") from e

    @classmethod
    def execute_func_string_single(cls, content: str) -> Any:
        """
        针对 content 为函数调用字符串格式, 如: func_name(...) 的场景，通过 GenerateUtils 类实现反射机制动态执行对应函数，并将函数返回值替换原变量值

        :param content: 如 "generate_uuid()"、"generate_string(length=2)"
        :return: 函数返回值
        :raises AttributeError: 非函数形式或函数不存在/执行失败
        """
        try:
            func_name, func_args = cls._parse_funcname_funcargs(content)
        except ValueError as e:
            raise AttributeError(f"【辅助函数】[{content!r}]调用失败: {e}") from e
        if not func_name and not func_args:
            raise AttributeError(f"【辅助函数】[{content!r}]调用失败, 占位符不是有效的调用")
        if not hasattr(GenerateUtils, func_name):
            raise AttributeError(f"【辅助函数】[{func_name}]调用失败, 未定义或不被允许调用")
        try:
            execute_result = getattr(GenerateUtils(), func_name)(**(func_args or {}))
            return execute_result
        except TypeError as e:
            raise AttributeError(f"【辅助函数】[{func_name}]调用失败, 参数签名或类型不匹配: {e}") from e
        except SyntaxError as e:
            raise AttributeError(f"【辅助函数】[{func_name}]调用失败, 语法解析失败或未定义: {e}") from e
        except Exception as e:
            raise AttributeError(f"【辅助函数】[{func_name}]调用失败, 在动态注入时发生异常: {e}") from e

    # -------------------------------------------------------------------------
    # 占位符 ${...}：单变量/函数、多占位符拼接、全为数值时整式四则(AST 白名单, 无 eval)
    # 限制：花括号内不可含 `}`；整式仅数字与 + - * / ( )；bool 不参与算术；超长表达式跳过求值
    # -------------------------------------------------------------------------

    _RE_PLACEHOLDER_SIMPLE = re.compile(r"\$\{([^}]+)\}")
    _RE_ARITHMETIC_ONLY = re.compile(r"^[\d+\-*/().\s]+$")
    # 合并后的算术串超过此长度则不做 ast.parse, 避免异常输入消耗 CPU/内存(生产防护)
    _MAX_ARITH_EXPR_CHARS = 8192

    @staticmethod
    def by_jsonpath_modify_inner_content(datagram: Dict[str, Any], json_path: str, json_value: Any, split_symbol: str = "@JSON@") -> None:
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
                inner_obj = json.loads(outer_value) if outer_value.strip() else {}
            except (TypeError, json.JSONDecodeError):
                return
            updated_inner_json = JSONPathUtils.update(inner_obj, inner_path, json_value)
            # 回写时保持 outer 类型仍为字符串 JSON
            JSONPathUtils.update(datagram, outer_path, updated_inner_json)
            return

        if isinstance(outer_value, dict):
            updated_inner_json = JSONPathUtils.update(outer_value, inner_path, json_value)
            try:
                updated_inner_obj = json.loads(updated_inner_json)
            except (TypeError, json.JSONDecodeError):
                updated_inner_obj = outer_value
            # 回写时保持 outer 类型仍为 dict
            JSONPathUtils.update(datagram, outer_path, updated_inner_obj)
            return

        # 其他类型暂不处理（例如 int/float/bool）
        return

    @staticmethod
    def by_jsonpath_modify_request_header(json_path: str) -> str:
        """从 JSONPath 取请求头键名，如 $.Content-Type -> Content-Type。"""
        if not json_path or not isinstance(json_path, str):
            return ""
        s = json_path.strip()
        if s.startswith("$."):
            s = s[2:]
        return s.split(".")[0].strip() if s else ""

    @staticmethod
    def by_jsonpath_modify_request_params(
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
                AutoTestToolServiceImpl.by_jsonpath_modify_inner_content(rb, json_path, json_value)
        elif isinstance(rb, str):
            try:
                payload_dict = json.loads(rb) if rb.strip() else {}
                if isinstance(payload_dict, dict):
                    for json_path, json_value in path_map.items():
                        if not json_path:
                            continue
                        AutoTestToolServiceImpl.by_jsonpath_modify_inner_content(payload_dict, json_path, json_value)
                    rb = payload_dict
            except (TypeError, json.JSONDecodeError):
                pass
        if isinstance(form_data, dict):
            for json_path, json_value in path_map.items():
                if not json_path:
                    continue
                AutoTestToolServiceImpl.by_jsonpath_modify_inner_content(form_data, json_path, json_value)
        if isinstance(urlencoded, dict):
            for json_path, json_value in path_map.items():
                if not json_path:
                    continue
                AutoTestToolServiceImpl.by_jsonpath_modify_inner_content(urlencoded, json_path, json_value)
        return rb

    @classmethod
    def _resolve_placeholder_inner(cls, inner: str, is_core_engine: bool, finished_variables: Optional[Any]) -> Any:
        """
        解析单个 ${...} 花括号内的文本：含括号视为 GenerateUtils 函数, 否则按变量名解析

        :param inner: 占位符花括号内文本(如 \"a\" 或 \"generate_uuid()\")会进行 strip
        :param is_core_engine: True 时 finished_variables 需提供 get_variable(name)
        :param finished_variables: 核心引擎上下文或变量列表(List[Dict], 每项含 key/value)
        :returns: 解析到的变量值或函数执行结果
        :raises KeyError: 变量未定义(非核心引擎列表路径)
        :raises AttributeError: 函数不存在或执行失败
        :raises ValueError: inner 为空白时
        """
        inner = inner.strip()
        if "(" in inner and ")" in inner:
            return cls.execute_func_string_single(inner)
        if is_core_engine:
            return finished_variables.get_variable(inner)
        resolved = AutoTestToolService.get_value_from_list(finished_variables, inner)
        if resolved is None:
            raise KeyError(f"【占位填充】获取数据失败, 必须是已经存在且有值的变量: {inner!r}")
        return resolved

    @classmethod
    def _is_calculated_numeric(cls, value: Any) -> Optional[float]:
        """
        判断value能否作为数值参与算术表达式计算, 用于区分「算术计算」与「字符串拼接」逻辑
        返回 float 对象：可参与算术计算
        返回 None：应按字符串拼接处理, 不参与算术计算
        :param value: 目标值
        :return:
        """
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            try:
                return float(s)
            except ValueError:
                return None
        return None

    @classmethod
    def _is_calculate_placeholder_expr(
            cls,
            content: str,
            regularly_slots: List[Tuple[re.Match[str], Optional[Any], Optional[str]]],
    ) -> bool:
        """
        判断当前占位符模板是否应进入「纯算术表达式」计算路径
        - 模板中占位符之外的文本只能包含算术字符, 否则按普通字符串拼接
        - 单占位符场景下, 若结果是字符串, 直接按字符串返回, 避免如 "00123" 被数值化后丢失前导 0
        """
        if len(regularly_slots) == 1:
            _, value, _ = regularly_slots[0]
            if isinstance(value, str):
                return False

        skeleton_parts: List[str] = []
        pos: int = 0
        for match, value, failed_content in regularly_slots:
            skeleton_parts.append(content[pos: match.start()])
            pos = match.end()
        skeleton_parts.append(content[pos:])
        skeleton: str = "".join(skeleton_parts).strip()
        return bool(skeleton) and bool(cls._RE_ARITHMETIC_ONLY.fullmatch(skeleton))

    @classmethod
    def _normalize_float(cls, f: float) -> str:
        """
        将浮点数转换为可以安全嵌入算术表达式的数字字面量字符串
        - 若 f 等价整数(如: 5.0、-2.0), 返回不带小数点和后缀0的整数字符串(如: "5"、"-2")
        - 若 f 不等价整数(如: 3.14、2.5), 直接返回原浮点数字符串(如: "3.14"、"2.5")
        目的：避免表达式中出现 100.0 这类冗余格式，提升可读性。
        :param f: 目标浮点数
        :return:
        """
        if f.is_integer():
            return str(int(f))
        return str(f)

    @classmethod
    def _formatter_resolved_placeholders(cls, value: Any) -> str:
        """
        非「纯算术整式求值」路径下, 将解析后的 Python 值转为字符串片段

        dict/list 使用 JSON(便于日志与下游展示)；None 转为空串
        """
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    @staticmethod
    def _formatter_calculated_result(result: Union[int, float]) -> str:
        """
        将 `_safe_calculation_expr` 的返回值格式化为对外字符串

        :param result: 算术求值结果(int/float)
        :returns: 字符串形式；若为形如 7.0 的 float, 会输出 \"7\"
        """
        if isinstance(result, float) and result.is_integer():
            return str(int(result))
        return str(result)

    @classmethod
    def _split_placeholders(
            cls,
            content: str,
            regularly_slots: List[Tuple[re.Match[str], Optional[Any], Optional[str]]],
            to_string: Callable[[Any], str],
    ) -> str:
        """
        按占位符顺序拼接 content, regularly_slots 每项为 (match, value, failed_content)：
        - failed_content 非 None：解析失败, 插入该原文(一般为 match.group(0))；
        - failed_content 为 None：解析成功, 插入 value_to_str(value)(value 可为 None, 如变量值为空)

        :param content: 待解析对象
        :param regularly_slots: 占位符匹配与解析结果列表, 每一项是三元组: match(匹配对象), value(替换值), failed_content(失败的原文)
        :param to_string: 将解析值格式化为字符串的函数
        :returns: 拼接后的字符串
        """
        pos: int = 0
        parts: List[str] = []
        for match, value, failed_content in regularly_slots:
            parts.append(content[pos: match.start()])
            parts.append(failed_content if failed_content is not None else to_string(value))
            pos = match.end()
        parts.append(content[pos:])
        return "".join(parts)

    @classmethod
    def _build_numeric_merged_expr(cls, content: str, reg_matches: List[re.Match[str]], calculated_numeric: List[float]) -> str:
        """
        将全部解析成功的占位符替换为数字字面量, 保留两侧运算符与括号, 生成可被 AST 解析的表达式字符串

        :param content: 待解析对象
        :param reg_matches: 与 calculated_numeric 一一对应的占位符 match 列表
        :param calculated_numeric: 每个占位符对应的数值(float)
        :returns: 占位符替换为数字后的表达式字符串
        """
        pos: int = 0
        parts: List[str] = []
        for match, numer in zip(reg_matches, calculated_numeric):
            parts.append(content[pos: match.start()])
            parts.append(cls._normalize_float(numer))
            pos = match.end()
        parts.append(content[pos:])
        return "".join(parts)

    @classmethod
    def _safe_calculation_expr(cls, expr: str) -> Union[int, float]:
        """
        行为目的:
            提供 resolve_placeholders 函数进行安全地计算"纯算术表达式"字符串的结果(四则运算 + 括号 + 一元正负号)
            - 例如: (${a} + 10) * ${fn()} / (${b} - 2)
        安全策略:
        - 仅当所有占位符都解析为数值, 且替换后整串仅包含合法算术字符时, 才会进入此函数计算
        - 不使用 Python 内置 eval/exec 函数计算, 完全基于 AST 语法树白名单校验实现安全计算：
            - 允许：数值常量、一元正负号、加减乘除、括号（括号自动体现为 AST 结构）
            - 禁止：变量、属性、函数调用、下标、幂运算、字符串等所有非算术语法
        行为约定:
        - 空字符串: 抛出 ValueError
        - 超出最大长度限制(> _MAX_ARITH_EXPR_CHARS)抛出 ValueError
        - 除数为0: 抛出 ZeroDivisionError
        - 返回值: 整数结果返回 int 类型，小数结果返回 float 类型
        :param expr: 算术表达式字符串(如: "1 + 2*(3-4)")
        :return: 计算结果
        """
        expr = expr.strip()
        if not expr:
            raise ValueError("计算内容为空")
        if len(expr) > cls._MAX_ARITH_EXPR_CHARS:
            raise ValueError("计算内容过长")

        def eval_node(node: ast.expr) -> float:
            """
            递归遍历 AST 节点并计算子表达式值

            :param node: AST 表达式节点
            :return: 子表达式计算值（float）
            :raises ValueError: 存在非白名单语法/运算符时抛出
            :raises ZeroDivisionError: 除法分母为 0 时抛出
            """
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    return float(node.value)
                raise ValueError("计算内容仅支持数字常量, 不支持字符串、布尔值等其他类型")
            if isinstance(node, ast.Num):  # Python 3.7 及更早
                return float(node.n)
            if isinstance(node, ast.UnaryOp):
                if isinstance(node.op, ast.USub):
                    return -eval_node(node.operand)
                if isinstance(node.op, ast.UAdd):
                    return +eval_node(node.operand)
                raise ValueError("计算内容中包含不被支持的一元运算符, 仅支持: + -")
            if isinstance(node, ast.BinOp):
                left = eval_node(node.left)
                right = eval_node(node.right)
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Mult):
                    return left * right
                if isinstance(node.op, ast.Div):
                    if right == 0:
                        raise ZeroDivisionError("计算内容错误, 除数不能为0")
                    return left / right
                raise ValueError("计算内容中包含不被支持的二元运算符, 仅支持: + - * /")
            raise ValueError("计算内容中包含不被支持的算术结构, 仅支持数字与四则运算")

        tree = ast.parse(expr, mode="eval")
        if not isinstance(tree, ast.Expression):
            raise ValueError("计算内容不是有效的算术表达式")
        raw = eval_node(tree.body)
        if isinstance(raw, float) and raw.is_integer():
            return int(raw)
        return raw

    @classmethod
    def _resolve_string_placeholders(
            cls,
            content: str,
            logger_object: Callable,
            is_core_engine: bool,
            finished_variables: Optional[Any],
    ) -> str:
        """
        解析 str 内所有 ${...}：先占位符求值；失败则保留原 ${...}；全成功则视情况整式算术或拼接
        """
        if "${" not in content:
            return content
        regularly_matched: List[re.Match[str]] = list(cls._RE_PLACEHOLDER_SIMPLE.finditer(content))
        if not regularly_matched:
            return content

        # 三元组: match(匹配对象), value(替换值), failed_content(失败的原文)
        # 第三项: 非None时表示解析失败, 应保留原文；None表示解析成功(值可以是: None)
        regularly_slots: List[Tuple[re.Match[str], Optional[Any], Optional[str]]] = []
        for match in regularly_matched:
            inner: str = match.group(1).strip()
            if not inner:
                logger_object(f"【占位填充】获取数据失败, 不允许使用空字符串, 保留原值")
                regularly_slots.append((match, None, match.group(0)))
                continue
            try:
                value = cls._resolve_placeholder_inner(inner, is_core_engine, finished_variables)
                logger_object("【占位填充】获取数据成功, ${" + inner + "}  >>>  " + str(value))
                regularly_slots.append((match, value, None))
            except KeyError as e:
                logger_object(e.args[0])
                regularly_slots.append((match, None, match.group(0)))
            except Exception as e:
                logger_object(f"【占位填充】获取数据失败, 引用[{inner!r}]发生异常, 保留原值, {e}")
                regularly_slots.append((match, None, match.group(0)))

        if any(failed_content is not None for match, value, failed_content in regularly_slots):
            return cls._split_placeholders(
                content=content,
                regularly_slots=regularly_slots,
                to_string=cls._formatter_resolved_placeholders
            )

        if not cls._is_calculate_placeholder_expr(content=content, regularly_slots=regularly_slots):
            return cls._split_placeholders(
                content=content,
                regularly_slots=regularly_slots,
                to_string=cls._formatter_resolved_placeholders
            )

        resolved_values: List[Optional[Any]] = [value for match, value, failed_content in regularly_slots]
        calculated_nums: List[Optional[float]] = [cls._is_calculated_numeric(v) for v in resolved_values]
        if not all(cn is not None for cn in calculated_nums):
            return cls._split_placeholders(
                content=content,
                regularly_slots=regularly_slots,
                to_string=cls._formatter_resolved_placeholders
            )

        calculated_numeric: List[float] = [number for number in calculated_nums if number is not None]
        reg_matches: List[re.Match[str]] = [match for match, value, failed_content in regularly_slots]
        merged: str = cls._build_numeric_merged_expr(content, reg_matches, calculated_numeric).strip()
        if (
                merged
                and len(merged) <= cls._MAX_ARITH_EXPR_CHARS
                and cls._RE_ARITHMETIC_ONLY.fullmatch(merged)
        ):
            try:
                calculated_result: Union[int, float] = cls._safe_calculation_expr(merged)
                formatted_result: str = cls._formatter_calculated_result(calculated_result)
                logger_object(f"【变量运算】算式求值成功: [{content!r}] >>> [{merged}] >>> {formatted_result}")
                return formatted_result
            except Exception as e:
                logger_object(f"【变量运算】算式求值失败: [{content!r}] >>> [{merged}] >>> {e}, 改为按字符串拼接")

        return cls._split_placeholders(
            content=content,
            regularly_slots=regularly_slots,
            to_string=cls._formatter_resolved_placeholders
        )

    @classmethod
    def resolve_placeholders(cls, value: Any, logger_object: Callable, is_core_engine: bool = False, finished_variables: Optional[Any] = None) -> Any:
        """
        递归解析 str / dict / list 中的 ${...} 占位符

        【字符串】
        - 单占位符：变量或 GenerateUtils 函数(花括号内同时含括号时按函数处理)
        - 多占位符：见类注释「实现步骤」；支持如 (${a}+10)*${b}/${c} 等(全部占位符解析成功且
          值均可视为数字时, 对合并后的表达式安全求值)

        【字典】递归每个 value(key 不替换, 与历史行为一致)

        【列表】若元素为含 key/value 的变量项 dict, 只解析 value 字段；否则递归元素

        【其它类型】原样返回

        解析失败：对应占位符保留原文；外层异常时记录日志并返回原 value

        :param value: 待解析对象
        :param logger_object: 日志回调, 签名为 (str) -> None
        :param is_core_engine: True 时 finished_variables 提供 get_variable
        :param finished_variables: 核心引擎上下文或变量列表, 含义同 _resolve_placeholder_inner
        :return: 结构不变, 占位符按规则替换后的深拷贝式结果(dict/list 新建容器)
        """
        try:
            if isinstance(value, str):
                return cls._resolve_string_placeholders(
                    content=value,
                    logger_object=logger_object,
                    is_core_engine=is_core_engine,
                    finished_variables=finished_variables
                )

            if isinstance(value, dict):
                try:
                    return {
                        k: cls.resolve_placeholders(
                            value=v,
                            logger_object=logger_object,
                            is_core_engine=is_core_engine,
                            finished_variables=finished_variables
                        )
                        for k, v in value.items()
                    }
                except Exception as e:
                    logger_object(
                        f"【占位填充】解析字典中的占位符时发生异常, 键: {list(value.keys())}, "
                        f"错误描述: {e}, \n"
                        f"错误类型: {type(e).__name__}, \n"
                        f"错误时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, \n"
                        f"错误回溯: {traceback.format_exc()}\n"
                    )
                    return value

            if isinstance(value, list):
                # 处理列表格式的变量(每个元素包含key、value、desc)
                result = []
                for item in value:
                    if isinstance(item, dict) and "key" in item and "value" in item:
                        # 列表格式的变量项, 只解析value字段
                        resolved_item = dict(item)
                        resolved_item["value"] = cls.resolve_placeholders(
                            value=item.get("value"),
                            logger_object=logger_object,
                            is_core_engine=is_core_engine,
                            finished_variables=finished_variables
                        )
                        result.append(resolved_item)
                    else:
                        # 普通列表项, 递归解析
                        result.append(
                            cls.resolve_placeholders(
                                value=item,
                                logger_object=logger_object,
                                is_core_engine=is_core_engine,
                                finished_variables=finished_variables
                            )
                        )
                return result
            return value
        except Exception as e:
            logger_object(
                f"【占位填充】解析列表中的占位符时发生异常, 保留原值, "
                f"错误描述: {e}, \n"
                f"错误类型: {type(e).__name__}, \n"
                f"错误时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, \n"
                f"错误回溯: {traceback.format_exc()}\n"
            )
            return value
