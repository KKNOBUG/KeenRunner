# -*- coding: utf-8 -*-
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
import orjson

from backend.applications.aotutest.dependencies import AutoTestApiServices
from backend.applications.aotutest.schemas.autotest_step_schema import (
    AutoTestHttpDebugRequest,
    AutoTestPythonCodeDebugRequest,
    AutoTestRedisDebugRequest,
    AutoTestTcpDebugRequest,
    RedisOperates,
    StepAssertValidatorItem,
    StepExtractVariableItem,
    StepVariablesBase,
)
from backend.applications.aotutest.services.autotest_runtime.protocol_http import (
    assemble_http_body_payloads,
    build_absolute_http_url,
    build_httpx_request_kwargs,
    format_byte_size,
    infer_http_actual_body,
)
from backend.applications.aotutest.services.autotest_runtime.protocol_tcp import (
    parse_tcp_response,
    parse_tcp_timeouts,
    resolve_tcp_debug_request_extract_sources,
    select_tcp_debug_payload,
)
from backend.applications.aotutest.services.autotest_tool_service import AutoTestToolService
from backend.common import AioTcpClient, TcpFrameMode
from backend.common.cache.redis_connection_pool import get_app_redis_pool
from backend.configure import LOGGER
from backend.core.exceptions import NotFoundException, ParameterException, ReqInvalidException
from backend.enums import AutoTestConfigNodeType, AutoTestReqArgsType, AutoTestStepType


class StepDebugException(Exception):
    """调试业务失败（映射为FailureResponse），可携带logs等附加数据。"""

    def __init__(self, message: str, data: Any = None) -> None:
        self.message = message
        self.data = data
        super().__init__(message)


@dataclass
class EnvEndpoint:
    """环境配置解析结果。"""

    env_id: int
    env_name: str
    project_id: int
    config_name: str
    config_type: AutoTestConfigNodeType
    config_host: Optional[str]
    config_port: Optional[str]
    database_name: Optional[str] = None


@dataclass
class DebugLogger:
    """带时间戳与步骤名的调试日志收集器。"""

    step_name: str
    logs: List[str]

    def append(self, message: str) -> None:
        """
        追加一条调试日志。

        :param message: 日志正文
        :return: None
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        self.logs.append(f"[{timestamp}] [{self.step_name}] {message}")


class StepDebugService:

    @staticmethod
    def make_debug_logger(step_name: str) -> DebugLogger:
        """
        创建调试日志收集器。

        :param step_name: 步骤名称
        :return: DebugLogger实例
        """
        return DebugLogger(step_name=step_name or "DEBUG", logs=[])

    @staticmethod
    def merge_debug_variables(
            defined_variables: Optional[List[StepVariablesBase]],
            session_variables: Optional[List[StepVariablesBase]],
    ) -> Tuple[Dict[str, Any], List[StepVariablesBase]]:
        """
        合并defined与session变量；同名时session覆盖defined。

        :param defined_variables: 步骤定义变量
        :param session_variables: 会话变量
        :return: (查找字典, 占位符解析用StepVariablesBase列表)
        """
        merged: Dict[str, Any] = {}
        for item in defined_variables or []:
            if isinstance(item, StepVariablesBase) and item.key:
                merged[item.key] = item.value
        for item in session_variables or []:
            if isinstance(item, StepVariablesBase) and item.key:
                merged[item.key] = item.value
        initial_models = [StepVariablesBase(key=k, value=v, desc="") for k, v in merged.items()]
        return merged, initial_models

    @staticmethod
    def resolve_placeholders_into_pool(
            initial_var_models: List[StepVariablesBase],
            merged_lookup: Dict[str, Any],
            log: Callable[[str], None],
    ) -> List[StepVariablesBase]:
        """
        解析初始变量池占位符并回写查找字典。

        :param initial_var_models: 初始变量列表
        :param merged_lookup: 可变查找字典（就地更新）
        :param log: 日志回调
        :return: 解析后的finished_variables
        """
        finished_variables: List[StepVariablesBase] = AutoTestToolService.resolve_placeholders(
            value=initial_var_models,
            logger_object=log,
            finished_variables={},
        )
        for item in finished_variables:
            if isinstance(item, StepVariablesBase) and item.key:
                merged_lookup[item.key] = item.value
        return finished_variables

    @classmethod
    async def resolve_env_config(
            cls,
            services: AutoTestApiServices,
            *,
            project_id: int,
            env_name: str,
            config_name: str,
            config_type: AutoTestConfigNodeType,
            label: str,
            env_not_found_template: Optional[str] = None,
            config_not_found_template: Optional[str] = None,
            empty_env_message: Optional[str] = None,
    ) -> EnvEndpoint:
        """
        按应用+环境名+配置名+节点类型解析环境配置（绑定与配置的 env_type 对齐）。

        :param services: CRUD依赖聚合
        :param project_id: 应用ID
        :param env_name: 环境名称
        :param config_name: 配置名称
        :param config_type: 节点类型(与绑定表 env_type / 配置表 env_type 一致)
        :param label: 错误信息前缀（如HTTP请求调试失败）
        :param env_not_found_template: 环境不存在文案模板，可用{label}/{project_id}/{env_name}
        :param config_not_found_template: 配置不存在文案模板，可用{label}/{config_name}
        :param empty_env_message: env_name为空时的完整错误文案
        :return: EnvEndpoint
        """
        env_name = (env_name or "").strip()
        if not env_name:
            raise ParameterException(message=empty_env_message or f"{label}, 参数[env_name]不允许为空")

        env_row = await services.env_curd.get_bind_by_env_name(
            project_id=project_id,
            env_name=env_name,
            env_type=config_type,
        )
        if not env_row:
            tmpl = env_not_found_template or "{label}, 应用[{project_id}]下环境[{env_name}]不存在"
            raise NotFoundException(
                message=tmpl.format(label=label, project_id=project_id, env_name=env_name)
            )

        env_config_instance = await services.env_config_curd.get_by_conditions(
            only_one=True,
            on_error=False,
            state__not=1,
            env_bind_id=env_row.id,
            config_name=config_name,
        )
        if not env_config_instance:
            tmpl = config_not_found_template or "{label}, 目标环境下[{config_name}]配置不存在"
            raise NotFoundException(
                message=tmpl.format(label=label, config_name=config_name)
            )

        return EnvEndpoint(
            env_id=env_row.id,
            env_name=env_name,
            project_id=project_id,
            config_name=config_name,
            config_type=config_type,
            config_host=env_config_instance.config_host,
            config_port=(
                str(env_config_instance.config_port)
                if env_config_instance.config_port is not None
                else None
            ),
            database_name=(
                str(env_config_instance.database_name).strip()
                if getattr(env_config_instance, "database_name", None)
                else None
            ),
        )

    @staticmethod
    def run_extract_and_assert_for_debug(
            *,
            extract_variables: Optional[List[StepExtractVariableItem]],
            assert_validators: Optional[List[StepAssertValidatorItem]],
            session_variables_lookup: Dict[str, Any],
            finished_variables: List[StepVariablesBase],
            log: Callable[[str], None],
            response_text: Optional[str] = None,
            response_json: Optional[Any] = None,
            response_headers: Optional[Dict[str, Any]] = None,
            response_cookies: Optional[Dict[str, Any]] = None,
            request_text: Optional[str] = None,
            request_json: Optional[Any] = None,
            request_headers: Optional[Dict[str, Any]] = None,
            request_cookies: Optional[Dict[str, Any]] = None,
            prepend_extract_results: Optional[List[Dict[str, Any]]] = None,
            sync_extract_into_lookup: bool = True,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        调试路径提取+断言（is_core_engine=False），并将提取值写回变量池。

        :param extract_variables: 提取规则
        :param assert_validators: 断言规则
        :param session_variables_lookup: 变量查找表（就地更新）
        :param finished_variables: 已完成变量列表（就地追加）
        :param log: 日志回调
        :param response_text: 响应文本
        :param response_json: 响应JSON
        :param response_headers: 响应头
        :param response_cookies: 响应Cookie
        :param request_text: 请求文本
        :param request_json: 请求JSON
        :param request_headers: 请求头
        :param request_cookies: 请求Cookie
        :param prepend_extract_results: 需前置合并的提取结果（如Redis自动写入）
        :param sync_extract_into_lookup: 是否将提取结果同步写入session_variables_lookup；
            Redis历史调试接口仅写入finished_variables，需传False以保持契约
        :return: (extract_results, validator_results)
        """
        extract_data, extract_results = AutoTestToolService.run_extract_variables(
            extract_variables=extract_variables or [],
            response_text=response_text,
            response_json=response_json,
            response_headers=response_headers,
            response_cookies=response_cookies,
            request_text=request_text,
            request_json=request_json,
            request_headers=request_headers,
            request_cookies=request_cookies,
            session_variables_lookup=session_variables_lookup,
            log_callback=log,
        )
        for extract_key, extract_value in extract_data.items():
            finished_variables.append(StepVariablesBase(key=extract_key, value=extract_value, desc=""))
            if sync_extract_into_lookup:
                session_variables_lookup[extract_key] = extract_value

        if prepend_extract_results:
            extract_results = list(prepend_extract_results) + (extract_results or [])

        validator_results = AutoTestToolService.run_assert_validators(
            assert_validators=assert_validators or [],
            response_text=response_text,
            response_json=response_json,
            response_headers=response_headers,
            response_cookies=response_cookies,
            request_text=request_text,
            request_json=request_json,
            request_headers=request_headers,
            request_cookies=request_cookies,
            session_variables_lookup=session_variables_lookup,
            log_callback=log,
            finished_variables=finished_variables,
            is_core_engine=False,
        )
        return extract_results or [], validator_results or []

    @staticmethod
    def pack_debug_result(
            *,
            duration: int,
            size: str,
            data: Any,
            extract_results: List[Dict[str, Any]],
            validator_results: List[Dict[str, Any]],
            logs: List[str],
            request_info: Dict[str, Any],
            status: Any = None,
            headers: Optional[Dict[str, Any]] = None,
            cookies: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        组装调试统一出参壳。

        :param duration: 耗时毫秒
        :param size: 可读大小
        :param data: 协议响应体
        :param extract_results: 提取结果
        :param validator_results: 断言结果
        :param logs: 调试日志
        :param request_info: 请求侧信息
        :param status: HTTP状态码等
        :param headers: 响应头
        :param cookies: 响应Cookie
        :return: 调试结果字典
        """
        return {
            "status": status,
            "headers": headers if headers is not None else {},
            "cookies": cookies if cookies is not None else {},
            "data": data,
            "duration": duration,
            "size": size,
            "extract_results": extract_results,
            "validator_results": validator_results,
            "logs": logs,
            "request_info": request_info,
        }

    @classmethod
    async def debug_http(
            cls,
            debug_in: AutoTestHttpDebugRequest,
            services: AutoTestApiServices,
    ) -> Dict[str, Any]:
        """
        调试HTTP请求步骤。

        :param debug_in: HTTP调试入参
        :param services: CRUD依赖聚合
        :return: 调试结果字典
        """
        env_name = (debug_in.env_name or "").strip()
        step_name = debug_in.step_name
        request_project_id = debug_in.request_project_id
        request_config_name = debug_in.request_config_name
        request_args_type: Optional[AutoTestReqArgsType] = debug_in.request_args_type
        request_url = (debug_in.request_url or "").lstrip("/")
        request_method = (debug_in.request_method or "GET")
        if hasattr(request_method, "value"):
            request_method = str(request_method.value).upper()
        else:
            request_method = str(request_method).upper()

        request_header = debug_in.request_header
        request_params = debug_in.request_params
        request_form_data = debug_in.request_form_data
        request_form_file = debug_in.request_form_file
        request_form_urlencoded = debug_in.request_form_urlencoded
        request_body = debug_in.request_body
        request_text = debug_in.request_text
        extract_variables = debug_in.extract_variables or []
        assert_validators = debug_in.assert_validators or []

        merged_lookup, initial_models = cls.merge_debug_variables(
            debug_in.defined_variables, debug_in.session_variables
        )
        logger = cls.make_debug_logger(step_name)
        log = logger.append

        if request_url and not request_url.lower().startswith("http"):
            endpoint = await cls.resolve_env_config(
                services,
                project_id=request_project_id,
                env_name=env_name,
                config_name=request_config_name,
                config_type=AutoTestConfigNodeType.API,
                label="HTTP请求调试失败",
            )
            host = (endpoint.config_host or "").strip()
            if not host:
                raise NotFoundException(
                    message=f"HTTP请求调试失败, 目标环境下[{request_config_name}]配置不完整"
                )
            request_url = build_absolute_http_url(host, endpoint.config_port, request_url)

        log(
            f"【HTTP请求】调试开始: \n\t"
            f"环境名称: {env_name}\n\t"
            f"应用ID: {request_project_id}\n\t"
            f"配置名称: {request_config_name}\n\t"
            f"请求方法: {request_method}\n\t"
            f"请求地址: {request_url}"
        )

        finished_variables = cls.resolve_placeholders_into_pool(initial_models, merged_lookup, log)
        headers_list = AutoTestToolService.resolve_placeholders(
            value=request_header, logger_object=log, finished_variables=finished_variables
        )
        params_list = AutoTestToolService.resolve_placeholders(
            value=request_params, logger_object=log, finished_variables=finished_variables
        )
        form_data_list = AutoTestToolService.resolve_placeholders(
            value=request_form_data, logger_object=log, finished_variables=finished_variables
        )
        urlencoded_list = AutoTestToolService.resolve_placeholders(
            value=request_form_urlencoded, logger_object=log, finished_variables=finished_variables
        )
        form_files_list = AutoTestToolService.resolve_placeholders(
            value=request_form_file, logger_object=log, finished_variables=finished_variables
        )
        if request_body is not None:
            request_body = AutoTestToolService.resolve_placeholders(
                value=request_body, logger_object=log, finished_variables=finished_variables
            )
        if request_text is not None:
            if request_args_type == AutoTestReqArgsType.XML:
                request_text = AutoTestToolService.resolve_xml_placeholders(
                    xml_text=request_text, logger_object=log, finished_variables=finished_variables
                )
            else:
                request_text = AutoTestToolService.resolve_placeholders(
                    value=request_text, logger_object=log, finished_variables=finished_variables
                )

        headers = AutoTestToolService.convert_list_to_dict_for_http(headers_list)
        params = AutoTestToolService.convert_list_to_dict_for_http(params_list)
        form_data = AutoTestToolService.convert_list_to_dict_for_http(form_data_list)
        urlencoded = AutoTestToolService.convert_list_to_dict_for_http(urlencoded_list)
        form_files = AutoTestToolService.convert_list_to_dict_for_http(form_files_list)

        payloads = assemble_http_body_payloads(
            request_args_type,
            request_text=request_text,
            request_body=request_body,
            form_data=form_data,
            form_files=form_files,
            urlencoded=urlencoded,
            headers=headers,
        )
        headers = payloads.headers

        request_kwargs = build_httpx_request_kwargs(
            headers=headers if headers else None,
            params=params if params else None,
            data=payloads.data_payload,
            json_data=payloads.json_payload,
            content=payloads.content_payload,
            files=payloads.file_payload,
        )

        start_time = time.time()
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            try:
                response = await client.request(method=request_method, url=request_url, **request_kwargs)
            except httpx.TimeoutException as e:
                raise StepDebugException(message="请求超时，请检查URL是否可访问或网络连接是否正常") from e
            except httpx.ConnectError as e:
                raise StepDebugException(message=f"连接失败: {str(e)}") from e
            except httpx.RequestError as e:
                raise StepDebugException(message=f"请求失败: {str(e)}") from e
            except Exception as e:
                error_message = (
                    f"【HTTP请求】调试异常, "
                    f"错误类型: {type(e).__name__}, "
                    f"错误描述: {e}"
                )
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise StepDebugException(message="HTTP请求调试异常", data=error_message) from e

        duration = int((time.time() - start_time) * 1000)
        log(
            f"【HTTP请求】调试完成: \n\t"
            f"状态描述: {response.reason_phrase}\n\t"
            f"状态代码: {response.status_code}\n\t"
            f"响应字符: {response.encoding}\n\t"
            f"响应版本: {response.http_version}\n\t"
            f"响应耗时: {duration}ms"
        )

        response_json = None
        response_text = response.text
        response_headers = dict(response.headers)
        try:
            response_json = response.json()
            response_data: Any = response_json
        except (ValueError, orjson.JSONDecodeError):
            response_data = response_text

        response_cookies: Dict[str, Any] = {}
        if response.cookies:
            for cookie in response.cookies.jar:
                response_cookies[cookie.name] = cookie.value

        request_json_for_extract = (
            payloads.json_payload if isinstance(payloads.json_payload, (dict, list)) else None
        )
        if request_json_for_extract is None and isinstance(request_body, (dict, list)):
            request_json_for_extract = request_body
        request_text_for_extract = request_text if request_text not in (None, "") else (
            payloads.data_payload if isinstance(payloads.data_payload, str) else None
        )

        extract_results, validator_results = cls.run_extract_and_assert_for_debug(
            extract_variables=extract_variables,
            assert_validators=assert_validators,
            session_variables_lookup=merged_lookup,
            finished_variables=finished_variables,
            log=log,
            response_text=response_text,
            response_json=response_json,
            response_headers=response_headers,
            response_cookies=response_cookies,
            request_text=request_text_for_extract,
            request_json=request_json_for_extract,
            request_headers=headers,
            request_cookies=AutoTestToolService.parse_cookie_header(headers),
        )

        actual_body_type, actual_body = infer_http_actual_body(
            request_args_type=request_args_type,
            json_payload=payloads.json_payload,
            content_payload=payloads.content_payload,
            data_payload=payloads.data_payload,
            file_payload=payloads.file_payload,
            form_data=form_data,
            form_files=form_files,
        )
        result = cls.pack_debug_result(
            status=response.status_code,
            headers=dict(response.headers),
            cookies=response_cookies,
            data=response_data,
            duration=duration,
            size=format_byte_size(len(response.content)),
            extract_results=extract_results,
            validator_results=validator_results,
            logs=logger.logs,
            request_info={
                "url": request_url,
                "method": request_method,
                "headers": headers or {},
                "params": params,
                "body_type": actual_body_type,
                "body": actual_body,
                "request_text": request_text,
            },
        )
        LOGGER.info(
            f"HTTP请求调试完成: {request_method} {request_url}, "
            f"状态码: {response.status_code}, 耗时: {duration}ms"
        )
        return result

    @classmethod
    async def debug_tcp(
            cls,
            debug_in: AutoTestTcpDebugRequest,
            services: AutoTestApiServices,
    ) -> Dict[str, Any]:
        """
        调试TCP请求步骤。

        :param debug_in: TCP调试入参
        :param services: CRUD依赖聚合
        :return: 调试结果字典
        """
        from backend.common import AsyncTcpUtils

        env_name = (debug_in.env_name or "").strip()
        step_name = debug_in.step_name
        request_project_id = debug_in.request_project_id
        request_config_name = debug_in.request_config_name
        request_args_type: Optional[AutoTestReqArgsType] = debug_in.request_args_type
        request_text = debug_in.request_text
        request_body: Any = debug_in.request_body
        extract_variables = debug_in.extract_variables or []
        assert_validators = debug_in.assert_validators or []

        merged_lookup, initial_models = cls.merge_debug_variables(
            debug_in.defined_variables, debug_in.session_variables
        )
        logger = cls.make_debug_logger(step_name)
        log = logger.append

        log(
            f"TCP请求调试开始: \n\t"
            f"环境名称: {env_name}\n\t"
            f"应用ID: {request_project_id}\n\t"
            f"配置名称: {request_config_name}\n\t"
            f"请求体类型: {request_args_type}\n\t"
            f"目标地址: 由环境配置解析(config_host/config_port)"
        )
        log("【参数替换】开始: ")

        finished_variables = cls.resolve_placeholders_into_pool(initial_models, merged_lookup, log)
        if request_args_type == AutoTestReqArgsType.JSON:
            request_body = AutoTestToolService.resolve_placeholders(
                value=request_body, logger_object=log, finished_variables=finished_variables
            )
        elif request_text is not None:
            if request_args_type == AutoTestReqArgsType.XML:
                request_text = AutoTestToolService.resolve_xml_placeholders(
                    xml_text=request_text, logger_object=log, finished_variables=finished_variables
                )
            else:
                request_text = AutoTestToolService.resolve_placeholders(
                    value=request_text, logger_object=log, finished_variables=finished_variables
                )
        log("【参数替换】结束")

        try:
            endpoint = await cls.resolve_env_config(
                services,
                project_id=request_project_id,
                env_name=env_name,
                config_name=request_config_name,
                config_type=AutoTestConfigNodeType.API,
                label="TCP请求调试失败",
                config_not_found_template="{label}, 环境配置[{config_name}]不存在",
            )
        except (ParameterException, NotFoundException) as e:
            log(str(e.message))
            raise
        except Exception as e:
            error_message = f"解析请求信息失败, 终止调试: {e}"
            log(error_message)
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise StepDebugException(message=error_message) from e

        host = (endpoint.config_host or "").strip().replace("http://", "").replace("https://", "")
        port = (endpoint.config_port or "").strip()
        log(f"解析请求信息(host={host}, port={port})成功")
        if not host or not port:
            raise StepDebugException(
                message=(
                    "TCP请求调试失败, 目标服务器地址或端口未配置"
                    "(请检查该环境下的API环境配置中的config_host/config_port)"
                )
            )

        payload = select_tcp_debug_payload(
            request_args_type, request_text=request_text, request_body=request_body
        )
        tcp_frame_mode = (debug_in.tcp_frame_mode or "length_prefix_json").strip().lower()
        frame_mode = TcpFrameMode.RAW if tcp_frame_mode == "raw" else TcpFrameMode.LENGTH_PREFIX_JSON
        length_field_size = debug_in.tcp_length_field_size or 8
        encoding = debug_in.tcp_encoding or "utf-8"
        max_response_bytes = debug_in.tcp_max_response_bytes or (10 * 1024 * 1024)
        response_type = (debug_in.tcp_response_type or "text").strip().lower()
        connect_td, read_td = parse_tcp_timeouts(
            debug_in.tcp_connect_timeout, debug_in.tcp_read_timeout
        )

        start_time = time.time()
        async with AioTcpClient(
                timeout=read_td or timedelta(seconds=30),
                connect_timeout=connect_td,
                length_field_size=int(length_field_size),
                max_response_bytes=int(max_response_bytes),
        ) as client:
            try:
                utils: AsyncTcpUtils = await client.tcp(
                    host=host,
                    port=int(port),
                    data=payload,
                    frame_mode=frame_mode,
                    encoding=encoding,
                    connect_timeout=connect_td,
                    read_timeout=read_td,
                )
                raw_bytes = await utils.bytes_resp()
            except ReqInvalidException as e:
                LOGGER.error(f"{e.message}\n{traceback.format_exc()}")
                raise StepDebugException(message="TCP请求调试异常", data=str(e.message)) from e
            except Exception as e:
                error_message = (
                    f"【TCP请求调试】请求目标服务器发生未知错误,"
                    f"错误类型: {type(e).__name__},"
                    f"异常描述: {e}"
                )
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise StepDebugException(message="TCP请求调试异常", data=error_message) from e

        duration = int((time.time() - start_time) * 1000)
        log(f"TCP请求调试完成: 耗时: {duration}ms")
        parsed = parse_tcp_response(raw_bytes, encoding=encoding, response_type=response_type)
        request_json_for_extract, request_text_for_extract = resolve_tcp_debug_request_extract_sources(
            request_body=request_body, request_text=request_text
        )

        extract_results, validator_results = cls.run_extract_and_assert_for_debug(
            extract_variables=extract_variables,
            assert_validators=assert_validators,
            session_variables_lookup=merged_lookup,
            finished_variables=finished_variables,
            log=log,
            response_text=parsed.response_text,
            response_json=parsed.response_json,
            request_text=request_text_for_extract,
            request_json=request_json_for_extract,
        )

        result = cls.pack_debug_result(
            data=parsed.response_data,
            duration=duration,
            size=format_byte_size(len(raw_bytes)),
            extract_results=extract_results,
            validator_results=validator_results,
            logs=logger.logs,
            request_info={
                "url": f"{host}:{port}",
                "method": "TCP",
                "headers": {},
                "params": {},
                "body_type": request_args_type,
                "body": payload,
            },
        )
        LOGGER.info(f"TCP请求调试完成: 耗时: {duration}ms")
        return result

    @classmethod
    async def debug_python(cls, debug_in: AutoTestPythonCodeDebugRequest) -> Dict[str, Any]:
        """
        调试Python代码步骤；断言规则与PythonStepExecutor对齐（仅变量池）。

        :param debug_in: Python调试入参
        :return: 调试结果字典（含result/assert_validators）
        """
        from backend.applications.aotutest.services.autotest_step_engine import (
            StepExecutionContext,
            StepExecutionError,
            StepExecutionResult,
        )

        code = debug_in.code
        step_name = debug_in.step_name or "代码请求(Python)调试"
        defined_variables = debug_in.defined_variables or []
        session_variables = debug_in.session_variables or []
        assert_validators = debug_in.assert_validators or []

        _, initial_variables = cls.merge_debug_variables(defined_variables, session_variables)
        debugging_return: Dict[str, Any] = {}

        async with StepExecutionContext(
                case_id=0, case_code="DEBUG", initial_variables=initial_variables
        ) as context:
            try:
                debugging_result = StepExecutionResult(
                    case_id=0,
                    step_code="DEBUG",
                    step_id=None,
                    step_no=None,
                    step_name=step_name,
                    step_type=AutoTestStepType.PYTHON,
                    success=True,
                )
                executive_namespace = context.clone_state()
                executive_result = context.run_python_code(
                    code, namespace=executive_namespace, step_result=debugging_result
                )
                validator_result: List[Dict[str, Any]] = []

                if assert_validators:
                    for vc in assert_validators:
                        source = (vc.source or "").strip().lower()
                        if source and source not in ("session_variables", "变量池"):
                            raise StepExecutionError(
                                f"【代码请求(Python)】数据源类型 {source} 不被允许"
                            )

                    session_lookup_map: Dict[str, Any] = {}
                    session_lookup_map.update(AutoTestToolService.list_to_dict(defined_variables))
                    session_lookup_map.update(AutoTestToolService.list_to_dict(session_variables))
                    if isinstance(executive_result, list):
                        session_lookup_map["result"] = executive_result
                    elif isinstance(executive_result, dict):
                        session_lookup_map.update(executive_result)
                    # 与改造前调试接口保持一致：仅跑断言管线（不做提取）
                    validator_result = AutoTestToolService.run_assert_validators(
                        assert_validators=assert_validators,
                        response_text=None,
                        response_json=None,
                        response_headers=None,
                        response_cookies=None,
                        session_variables_lookup=session_lookup_map,
                        log_callback=lambda msg: context.log(msg),
                        finished_variables=context,
                        is_core_engine=True,
                    )
                    assert_failed_number = sum(
                        1 for valid in validator_result if not valid.get("success", True)
                    )
                    if assert_failed_number > 0:
                        debugging_return = {
                            "result": executive_result,
                            "assert_validators": validator_result,
                            "error": (
                                f"【断言验证】- 共计: {assert_failed_number}个断言验证未通过, "
                                f"详情见报告明细"
                            ),
                        }
                        LOGGER.info(f"Python代码调试失败(断言未通过): {step_name}")
                        raise StepDebugException(message="Python代码调试失败", data=debugging_return)

                debugging_return["result"] = executive_result
                debugging_return["assert_validators"] = validator_result
                LOGGER.info(f"Python代码调试成功: {step_name}")
                return debugging_return
            except StepDebugException:
                raise
            except StepExecutionError as e:
                debugging_return["error"] = str(e)
                LOGGER.error(f"【Python代码调试】失败, 错误回溯: {traceback.format_exc()}")
                raise StepDebugException(message="Python代码调试失败", data=debugging_return) from e

    @classmethod
    async def debug_redis(
            cls,
            debug_in: AutoTestRedisDebugRequest,
            services: AutoTestApiServices,
    ) -> Dict[str, Any]:
        """
        调试Redis请求步骤；查到即止语义与RedisStepExecutor对齐。

        :param debug_in: Redis调试入参
        :param services: CRUD依赖聚合
        :return: 调试结果字典
        """
        from backend.applications.aotutest.services.autotest_step_engine import RedisStepExecutor

        env_name = (debug_in.env_name or "").strip()
        step_name = debug_in.step_name
        redis_operates: List[RedisOperates] = debug_in.redis_operates or []
        redis_searched = bool(debug_in.redis_searched)
        extract_variables = debug_in.extract_variables or []
        assert_validators = debug_in.assert_validators or []

        merged_lookup, initial_models = cls.merge_debug_variables(
            debug_in.defined_variables, debug_in.session_variables
        )
        logger = cls.make_debug_logger(step_name)
        log = logger.append

        if not env_name:
            raise ParameterException(message="Redis请求调试失败, 参数[env_name]不允许为空")

        log(
            f"Redis请求调试开始: \n\t"
            f"环境名称: {env_name}\n\t"
            f"操作条数: {len(redis_operates)}\n\t"
            f"查到即止: {redis_searched}"
        )
        log("【参数替换】开始: ")
        finished_variables = cls.resolve_placeholders_into_pool(initial_models, merged_lookup, log)

        pool_manager = get_app_redis_pool()
        redis_operates_request: List[Dict[str, Any]] = []
        redis_operates_response: List[Dict[str, Any]] = []
        mark_extract_variables: List[Dict[str, Any]] = []
        start_time = time.time()

        for redis_idx, redis_operate in enumerate(redis_operates):
            operate_no = f"第{redis_idx + 1}条Redis配置"
            config_host: Optional[str] = None
            config_port: Optional[str] = None
            operate_name = redis_operate.name
            operate_expr = redis_operate.expr
            operate_project_id: Optional[int] = redis_operate.project_id
            operate_project_name = redis_operate.project_name
            operate_variable_name = redis_operate.variable_name
            operate_config_name = redis_operate.config_name
            operate_database_name = redis_operate.database_name
            operate_desc = redis_operate.desc
            operate_result_count = f"{operate_variable_name}_count"

            try:
                operate_expr = AutoTestToolService.resolve_placeholders(
                    value=operate_expr, logger_object=log, finished_variables=finished_variables
                )
                operate_config_name = AutoTestToolService.resolve_placeholders(
                    value=operate_config_name, logger_object=log, finished_variables=finished_variables
                )
                operate_project_name = AutoTestToolService.resolve_placeholders(
                    value=operate_project_name, logger_object=log, finished_variables=finished_variables
                )
                operate_database_name = AutoTestToolService.resolve_placeholders(
                    value=operate_database_name, logger_object=log, finished_variables=finished_variables
                )
                operate_variable_name = AutoTestToolService.resolve_placeholders(
                    value=operate_variable_name, logger_object=log, finished_variables=finished_variables
                )
                operate_result_count = f"{operate_variable_name}_count"

                if not operate_project_id and (operate_project_name or "").strip():
                    project_instance = await services.project_curd.get_by_name(
                        operate_project_name.strip(), on_error=False
                    )
                    if not project_instance:
                        msg = f"{operate_no}：应用(project_name={operate_project_name!r})不存在"
                        log(msg)
                        raise NotFoundException(message=msg)
                    operate_project_id = project_instance.id
                if not operate_project_id:
                    raise StepDebugException(message=f"{operate_no}：参数[project_id]不允许为空")
                if not operate_config_name:
                    raise StepDebugException(message=f"{operate_no}：参数[config_name]不允许为空")
                if not operate_database_name:
                    raise StepDebugException(message=f"{operate_no}：参数[database_name]不允许为空")
                if not operate_expr:
                    raise StepDebugException(message=f"{operate_no}：参数[expr]不允许为空")
                if not operate_variable_name:
                    raise StepDebugException(message=f"{operate_no}：参数[variable_name]不允许为空")

                endpoint = await cls.resolve_env_config(
                    services,
                    project_id=operate_project_id,
                    env_name=env_name,
                    config_name=operate_config_name,
                    config_type=AutoTestConfigNodeType.REDIS,
                    label=operate_no,
                    env_not_found_template="{label}：应用[{project_id}]下环境[{env_name}]不存在",
                    config_not_found_template="{label}：环境配置[{config_name}]不存在",
                )
                config_host = endpoint.config_host
                config_port = endpoint.config_port
                if endpoint.database_name:
                    operate_database_name = endpoint.database_name

                log(
                    f"{operate_no}：解析配置成功"
                    f"(host={config_host}, port={config_port}, db={operate_database_name})"
                )

                redis_client = await pool_manager.get_or_create_client(
                    app_id=str(operate_project_id),
                    env=env_name,
                    config_name=operate_config_name,
                    db_name=operate_database_name,
                )
                expr_executive_result = await pool_manager.execute_commands(
                    client=redis_client, expr=operate_expr
                )
                redis_data = expr_executive_result.get("redis_data")
                redis_count = expr_executive_result.get("redis_count")

                mark_extract_variables.append({
                    "index": redis_idx,
                    "name": operate_variable_name,
                    "source": "Redis请求",
                    "scope": "ALL",
                    "expr": "Redis命令",
                    "extract_value": redis_data,
                    "success": True,
                    "error": "",
                })
                mark_extract_variables.append({
                    "index": redis_idx,
                    "name": operate_result_count,
                    "source": "Redis请求",
                    "scope": "ALL",
                    "expr": "Redis命令",
                    "extract_value": redis_count,
                    "success": True,
                    "error": "",
                })
                log(
                    f"{operate_no}：已自动写入变量池 variable_name={operate_variable_name}, "
                    f"{operate_result_count}={redis_count}"
                )

                redis_operates_request.append({
                    "index": redis_idx,
                    "name": operate_name,
                    "env_name": env_name,
                    "expr": operate_expr,
                    "project_id": operate_project_id,
                    "project_name": operate_project_name,
                    "variable_name": [operate_variable_name, operate_result_count],
                    "config_name": operate_config_name,
                    "database_name": operate_database_name,
                    "desc": operate_desc,
                })
                redis_operates_response.append({
                    "index": redis_idx,
                    "name": operate_name,
                    "variable_name": [operate_variable_name, operate_result_count],
                    "redis_meta": {
                        "env_name": env_name,
                        "project_id": operate_project_id,
                        "project_name": operate_project_name,
                        "config_name": operate_config_name,
                        "database_name": operate_database_name,
                        "config_host": config_host,
                        "config_port": config_port,
                    },
                    "redis_data": redis_data,
                    "redis_count": redis_count,
                })
                log(f"{operate_no}：执行完成, 命令数={redis_count}")

                if redis_searched and RedisStepExecutor.has_effective_redis_result(redis_data):
                    log(f"【Redis请求】查到即止：{operate_no}已返回有效结果，已终止后续命令")
                    break
            except (ParameterException, NotFoundException) as e:
                log(str(e.message))
                raise
            except StepDebugException:
                raise
            except Exception as e:
                error_message = f"{operate_no}：执行失败, {e}"
                log(error_message)
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                redis_operates_request.append({
                    "index": redis_idx,
                    "name": operate_name,
                    "env_name": env_name,
                    "expr": operate_expr,
                    "project_id": operate_project_id,
                    "project_name": operate_project_name,
                    "variable_name": [operate_variable_name, operate_result_count],
                    "config_name": operate_config_name,
                    "database_name": operate_database_name,
                    "desc": operate_desc,
                })
                redis_operates_response.append({
                    "index": redis_idx,
                    "name": operate_name,
                    "variable_name": [operate_variable_name, operate_result_count],
                    "redis_meta": {
                        "env_name": env_name,
                        "project_id": operate_project_id,
                        "project_name": operate_project_name,
                        "config_name": operate_config_name,
                        "database_name": operate_database_name,
                        "config_host": config_host,
                        "config_port": config_port,
                    },
                    "redis_data": None,
                    "redis_count": None,
                    "error": error_message,
                })
                raise StepDebugException(
                    message=error_message, data={"logs": logger.logs}
                ) from e

        duration = int((time.time() - start_time) * 1000)
        response_text_str = orjson.dumps(redis_operates_response, default=str).decode("UTF-8")
        log(f"Redis请求调试完成: 耗时: {duration}ms")

        for extract_item in mark_extract_variables:
            if isinstance(extract_item, dict) and extract_item.get("success") and extract_item.get("name") is not None:
                merged_lookup[extract_item["name"]] = extract_item.get("extract_value")
                finished_variables.append(
                    StepVariablesBase(
                        key=str(extract_item["name"]),
                        value=extract_item.get("extract_value"),
                        desc="",
                    )
                )

        extract_results, validator_results = cls.run_extract_and_assert_for_debug(
            extract_variables=extract_variables,
            assert_validators=assert_validators,
            session_variables_lookup=merged_lookup,
            finished_variables=finished_variables,
            log=log,
            response_text=response_text_str,
            response_json=redis_operates_response,
            prepend_extract_results=mark_extract_variables,
            sync_extract_into_lookup=False,
        )

        result = cls.pack_debug_result(
            data=redis_operates_response,
            duration=duration,
            size=format_byte_size(len(response_text_str.encode("utf-8"))),
            extract_results=extract_results,
            validator_results=validator_results,
            logs=logger.logs,
            request_info={
                "request_env_name": env_name,
                "redis_operates": redis_operates_request,
                "redis_searched": redis_searched,
            },
        )
        LOGGER.info(f"Redis请求调试完成: 耗时: {duration}ms")
        return result
