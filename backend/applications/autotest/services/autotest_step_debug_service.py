# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_step_debug_service.py
@DateTime: 2026/1/15 10:20
"""
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
import orjson

from backend.applications.autotest.dependencies import AutoTestServices
from backend.applications.autotest.schemas.autotest_step_schema import (
    AutoTestHttpDebugRequest,
    AutoTestPythonCodeDebugRequest,
    AutoTestRedisDebugRequest,
    AutoTestTcpDebugRequest,
    RedisOperates,
    StepAssertValidatorItem,
    StepExtractVariableItem,
    StepVariablesBase,
)
from backend.applications.autotest.services.autotest_runtime.builtin_variables import (
    collect_builtin_step_variables,
    strip_host_scheme,
)
from backend.applications.autotest.services.autotest_runtime.protocol_http import (
    assemble_http_body_payloads,
    build_httpx_request_kwargs,
    format_byte_size,
    infer_http_actual_body,
)
from backend.applications.autotest.services.autotest_runtime.protocol_tcp import (
    build_tcp_debug_request_info_body,
    parse_tcp_response,
    parse_tcp_timeouts,
    resolve_tcp_request_extract_sources,
    resolve_tcp_frame_config,
    select_tcp_payload,
    TCP_MAX_RESPONSE_BYTES,
)
from backend.applications.autotest.services.autotest_scope_guard import load_readable_project
from backend.applications.autotest.services.autotest_tool_service import AutoTestToolService
from backend.common import AioTcpClient
from backend.common.cache.redis_connection_pool import get_app_redis_pool
from backend.common.url_utils import build_absolute_http_url, is_absolute_http_url
from backend.configure import LOGGER
from backend.core.exceptions import NotFoundException, NoPermissionException, ParameterException, ReqInvalidException
from backend.enums import AutoTestConfigNodeType, AutoTestReqArgsType, AutoTestStepType, ResourceTag
from backend.services.data_scope import DataScope


class StepDebugException(Exception):
    """
    调试业务失败异常（视图层映射为FailureResponse）。

    message为面向用户的主提示；data可携带logs、响应片段等附加数据，便于前端展开排查。
    """

    def __init__(self, message: str, data: Any = None) -> None:
        """
        构造调试失败异常。

        :param message: 面向用户的主提示
        :param data: 附加数据（如{"logs": [...]}或错误明细）
        """
        self.message = message
        self.data = data
        super().__init__(message)


@dataclass
class EnvEndpoint:
    """环境配置解析结果（APP/REDIS等节点类型共用）。"""

    env_id: int                          # 环境绑定记录ID
    env_name: str                        # 环境名称
    project_id: int                      # 应用ID
    config_name: str                     # 配置名称
    config_type: AutoTestConfigNodeType  # 节点类型，与绑定表/配置表的env_type一致
    config_host: Optional[str]           # 主机地址；调用方需自行判空
    config_port: Optional[str]           # 端口（统一转为字符串）
    database_name: Optional[str] = None  # 数据库名，仅REDIS等节点使用


@dataclass
class DebugLogger:
    """带时间戳与步骤名的调试日志收集器。"""

    step_name: str   # 日志前缀使用的步骤名称
    logs: List[str]  # 已格式化日志行，按追加顺序返回前端

    def append(self, message: str) -> None:
        """
        追加一条调试日志。

        :param message: 日志正文
        :return: None
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        self.logs.append(f"[{timestamp}] [{self.step_name}] {message}")


class StepDebugService:
    """
    步骤调试服务：HTTP/TCP/Python/Redis四类步骤的同步调试入口。

    与执行引擎共用autotest_runtime实现（占位符、协议、提取/断言、内置变量），
    差异仅在于变量池来源、is_core_engine=False与返回日志/请求回显，保证调试结果与执行口径一致。
    """

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
        合并session与defined变量；同名时defined覆盖session，与执行引擎get_variable优先级一致。

        :param defined_variables: 步骤定义变量
        :param session_variables: 会话变量(含前端透传的用例级初始变量池)
        :return: (查找字典, 占位符解析用StepVariablesBase列表)
        """
        merged: Dict[str, Any] = {}
        for item in session_variables or []:
            if isinstance(item, StepVariablesBase) and item.key and item.key.strip():
                merged[item.key] = item.value
        for item in defined_variables or []:
            if isinstance(item, StepVariablesBase) and item.key and item.key.strip():
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
            if isinstance(item, StepVariablesBase) and item.key and item.key.strip():
                merged_lookup[item.key] = item.value
        return finished_variables

    @staticmethod
    def inject_builtin_variables_for_debug(
            initial_models: List[StepVariablesBase],
            merged_lookup: Dict[str, Any],
            *,
            target_host: Optional[str] = None,
            target_port: Optional[str] = None,
            target_path: Optional[str] = None,
            log: Callable[[str], None],
    ) -> None:
        """
        向调试变量池追加内置环境变量（SERVER_*/TARGET_*），与执行模式保持一致。
        同名时跳过：内置变量不覆盖用户主动定义的变量；获取失败项记录日志由前端反馈。

        :param initial_models: 占位符解析用初始变量列表（就地追加）
        :param merged_lookup: 提取/断言用查找字典（就地补充）
        :param target_host: 目标应用主机；None表示未解析到环境配置（如HTTP绝对URL）
        :param target_port: 目标应用端口；None表示未解析到环境配置
        :param target_path: 目标URL（等同request_url原值）；TCP调试传空字符串
        :param log: 日志回调
        :return: None
        """
        builtin_variables = collect_builtin_step_variables(
            target_host=target_host,
            target_port=target_port,
            target_path=target_path,
            existing_keys=set(merged_lookup.keys()),
            log=log,
        )
        initial_models.extend(builtin_variables)
        for item in builtin_variables:
            merged_lookup.setdefault(item.key, item.value)

    @classmethod
    async def resolve_env_config(
            cls,
            services: AutoTestServices,
            *,
            project_id: int,
            env_name: str,
            config_name: str,
            config_type: AutoTestConfigNodeType,
            label: str,
            env_not_found_template: Optional[str] = None,
            config_not_found_template: Optional[str] = None,
            empty_env_message: Optional[str] = None,
            scope: Optional[DataScope] = None,
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
        :param scope: 数据权限上下文；外部调试传入时要求应用与配置创建人均在可见范围
        :return: EnvEndpoint
        :raises ParameterException: env_name为空
        :raises NotFoundException: 环境绑定或环境配置不存在
        :raises NoPermissionException: 应用或配置创建人不在可见范围
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

        # 解析结果暴露 host/port，外部调试必须与列表口径一致：应用可读且配置创建人可读
        if scope is not None:
            await load_readable_project(scope, project_id)
            config_scope = await scope.for_tag(ResourceTag.ENV_CONFIG.value)
            await config_scope.load_owners([env_config_instance.created_user])
            if not config_scope.can_read(env_config_instance.created_user):
                error_message = (
                    f"{label}, 环境配置[{config_name}]创建人[{env_config_instance.created_user}]"
                    f"不在当前用户可见范围"
                )
                LOGGER.error(error_message)
                raise NoPermissionException(message=error_message)

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
            request_form_data: Optional[Dict[str, Any]] = None,
            prepend_extract_results: Optional[List[Dict[str, Any]]] = None,
            sync_extract_into_lookup: bool = True,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        调试路径提取+断言（is_core_engine=False），并将提取值写回变量池。

        本方法不复用ExtractAssertPipeline，因此提取失败不会因raise_on_failure中止，
        失败项仅体现在extract_results；断言失败同样只记结果，由调用方根据success汇总。

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
        :param request_form_data: 请求 Form-Data / X-WWW-Form-Urlencoded 合并映射
        :param prepend_extract_results: 需前置合并的提取结果（如Redis自动写入）
        :param sync_extract_into_lookup: 是否将提取结果同步写入session_variables_lookup；
            Redis调试接口仅写入finished_variables，需传False以保持契约
        :return: (extract_results, validator_results)
        :raises TypeError: 规则列表类型不合法
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
            request_form_data=request_form_data,
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
            request_form_data=request_form_data,
            session_variables_lookup=session_variables_lookup,
            log_callback=log,
            finished_variables=finished_variables,
            is_core_engine=False,
        )
        return extract_results or [], validator_results or []

    @staticmethod
    def pack_debug_result(
            *,
            elapsed: str,
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

        :param elapsed: 耗时秒
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
            "elapsed": elapsed,
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
            services: AutoTestServices,
            scope: Optional[DataScope] = None,
    ) -> Dict[str, Any]:
        """
        调试HTTP请求步骤。

        流程：合并变量池→相对URL解析环境配置并注入内置变量→解析占位符→组装报文→
        httpx请求（10秒超时、不读系统代理）→回显响应并按执行口径提取/断言。

        :param debug_in: HTTP调试入参
        :param services: CRUD依赖聚合
        :param scope: 数据权限上下文，相对地址解析环境配置时校验应用与配置可见性
        :return: 调试结果字典
        :raises StepDebugException: 超时、连接失败或请求异常
        :raises NotFoundException: 相对URL缺少环境配置或配置不完整
        :raises ParameterException: 环境名称缺失
        :raises NoPermissionException: 应用或配置创建人不在可见范围
        """
        env_name = (debug_in.env_name or "").strip()
        step_name = debug_in.step_name
        request_project_id = debug_in.request_project_id
        request_config_name = debug_in.request_config_name
        request_args_type: Optional[AutoTestReqArgsType] = debug_in.request_args_type
        request_url = (debug_in.request_url or "").strip()
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

        # 内置变量TARGET_PATH：等同用户填写的request_url原值（绝对/相对均原样），须在URL拼装前捕获
        target_path_raw: str = request_url
        builtin_target_host: Optional[str] = None
        builtin_target_port: Optional[str] = None
        # 绝对URL不走环境配置；相对URL必须解析出host后才能拼装目标地址
        if not is_absolute_http_url(request_url):
            endpoint = await cls.resolve_env_config(
                services,
                project_id=request_project_id,
                env_name=env_name,
                config_name=request_config_name,
                config_type=AutoTestConfigNodeType.APP,
                label="HTTP请求调试失败",
                scope=scope,
            )
            host = (endpoint.config_host or "").strip()
            if not host:
                raise NotFoundException(
                    message=f"HTTP请求调试失败, 目标环境下[{request_config_name}]配置不完整"
                )
            builtin_target_host = host
            builtin_target_port = endpoint.config_port
            request_url = build_absolute_http_url(host, endpoint.config_port, request_url)

        log(
            f"【HTTP请求】调试开始: \n\t"
            f"环境名称: {env_name}\n\t"
            f"应用ID: {request_project_id}\n\t"
            f"配置名称: {request_config_name}\n\t"
            f"请求方法: {request_method}\n\t"
            f"请求地址: {request_url}"
        )

        # 注入内置环境变量（SERVER_*/TARGET_*）：绝对URL时无环境配置，TARGET_*不注入并记录获取失败日志
        cls.inject_builtin_variables_for_debug(
            initial_models,
            merged_lookup,
            target_host=builtin_target_host,
            target_port=builtin_target_port,
            target_path=target_path_raw,
            log=log,
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
            if AutoTestToolService.resolve_datagram_is_xml(request_args_type, request_text, request_body):
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
        # trust_env=False：不读系统代理，避免调试请求被本机代理环境变量劫持
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=10.0), trust_env=False) as client:
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

        elapsed = f"{time.time() - start_time:.2f}"
        log(
            f"【HTTP请求】调试完成: \n\t"
            f"状态描述: {response.reason_phrase}\n\t"
            f"状态代码: {response.status_code}\n\t"
            f"响应字符: {response.encoding}\n\t"
            f"响应版本: {response.http_version}\n\t"
            f"响应耗时: {elapsed}s"
        )

        response_json = None
        response_text = response.text
        response_headers = dict(response.headers)
        # 非JSON响应按文本回显；response_json保持None，供提取/断言判定数据源类型
        try:
            response_json = response.json()
            response_data: Any = response_json
        except (ValueError, orjson.JSONDecodeError):
            response_data = response_text

        response_cookies: Dict[str, Any] = {}
        if response.cookies:
            for cookie in response.cookies.jar:
                response_cookies[cookie.name] = cookie.value

        # 提取/断言取实际发出的报文：优先序列化后的json_payload，回退原始request_body
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
            request_form_data=AutoTestToolService.merge_mapping_dicts(urlencoded, form_data),
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
            elapsed=elapsed,
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
            f"状态码: {response.status_code}, 耗时: {elapsed}s"
        )
        return result

    @classmethod
    async def debug_tcp(
            cls,
            debug_in: AutoTestTcpDebugRequest,
            services: AutoTestServices,
            scope: Optional[DataScope] = None,
    ) -> Dict[str, Any]:
        """
        调试TCP请求步骤。

        流程：解析环境配置→注入内置变量→解析占位符→按帧配置组包→单次收发→
        解析响应并按执行口径提取/断言。长连接暂未实现，按短连接降级。

        :param debug_in: TCP调试入参
        :param services: CRUD依赖聚合
        :param scope: 数据权限上下文，解析环境配置时校验应用与配置可见性
        :return: 调试结果字典
        :raises StepDebugException: 环境配置缺失、地址/端口不完整或收发出错
        :raises ParameterException: 环境名称缺失
        :raises NotFoundException: 环境或配置不存在
        :raises NoPermissionException: 应用或配置创建人不在可见范围
        """
        # 局部导入：仅TCP调试需要，避免模块导入期加载网络工具
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

        # 严格对齐执行模式：先解析环境配置，再进行参数占位符替换（内置变量TARGET_*依赖配置解析结果）
        try:
            endpoint = await cls.resolve_env_config(
                services,
                project_id=request_project_id,
                env_name=env_name,
                config_name=request_config_name,
                config_type=AutoTestConfigNodeType.APP,
                label="TCP请求调试失败",
                config_not_found_template="{label}, 环境配置[{config_name}]不存在",
                scope=scope,
            )
        except (ParameterException, NotFoundException, NoPermissionException) as e:
            log(str(e.message))
            raise
        except Exception as e:
            error_message = f"解析请求信息失败, 终止调试: {e}"
            log(error_message)
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise StepDebugException(message=error_message) from e

        host = strip_host_scheme(endpoint.config_host) or ""
        port = (endpoint.config_port or "").strip()
        log(f"解析请求信息(host={host}, port={port})成功")
        if not host or not port:
            raise StepDebugException(
                message=(
                    "TCP请求调试失败, 目标服务器地址或端口未配置"
                    "(请检查该环境下的API环境配置中的config_host/config_port)"
                )
            )

        # 注入内置环境变量（SERVER_*/TARGET_*），TCP的TARGET_PATH固定为空字符串；供请求体占位符替换与提取断言使用
        cls.inject_builtin_variables_for_debug(
            initial_models,
            merged_lookup,
            target_host=host,
            target_port=port,
            target_path="",
            log=log,
        )

        log("【参数替换】开始: ")

        finished_variables = cls.resolve_placeholders_into_pool(initial_models, merged_lookup, log)
        if request_args_type == AutoTestReqArgsType.JSON:
            request_body = AutoTestToolService.resolve_placeholders(
                value=request_body, logger_object=log, finished_variables=finished_variables
            )
        elif request_text is not None:
            if AutoTestToolService.resolve_datagram_is_xml(request_args_type, request_text, request_body):
                request_text = AutoTestToolService.resolve_xml_placeholders(
                    xml_text=request_text, logger_object=log, finished_variables=finished_variables
                )
            else:
                request_text = AutoTestToolService.resolve_placeholders(
                    value=request_text, logger_object=log, finished_variables=finished_variables
                )
        log("【参数替换】结束")

        payload = select_tcp_payload(
            request_args_type, request_text=request_text, request_body=request_body, serialize_json=True
        )
        frame_config = resolve_tcp_frame_config(debug_in)
        # 请求超时未配置，仅指定响应超时；read_td为空时由AioTcpClient回落30秒
        connect_td, read_td = parse_tcp_timeouts(None, debug_in.tcp_response_timeout)
        log(
            f"TCP帧配置: 帧模式={frame_config.frame_mode.value}, 进制={frame_config.radix}, "
            f"长度位宽度={frame_config.radix_length}, 总长度口径={'包含长度位' if frame_config.include_length_prefix else '不包含长度位'}, "
            f"连接方式={'只发不收' if frame_config.send_only else ('长连接' if frame_config.long_connection else '短连接')}, "
            f"Hex报文={'启用' if frame_config.hex_string else '禁用'}, 编码={frame_config.encoding}"
        )
        if frame_config.long_connection:
            # 长连接暂未实现：调试为单次收发，按短连接降级
            log("TCP调试: 连接方式为长连接, 暂未实现, 已按短连接降级执行")

        start_time = time.time()
        async with AioTcpClient(
                timeout=read_td or timedelta(seconds=30),
                connect_timeout=connect_td,
                length_field_size=frame_config.radix_length,
                max_response_bytes=TCP_MAX_RESPONSE_BYTES,
        ) as client:
            try:
                utils: AsyncTcpUtils = await client.tcp(
                    host=host,
                    port=int(port),
                    data=payload,
                    frame_mode=frame_config.frame_mode,
                    length_field_size=frame_config.radix_length,
                    radix=frame_config.radix,
                    include_length_prefix=frame_config.include_length_prefix,
                    request_end_symbol=frame_config.request_end_symbol,
                    response_end_symbol=frame_config.response_end_symbol,
                    hex_string=frame_config.hex_string,
                    send_only=frame_config.send_only,
                    encoding=frame_config.encoding,
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

        elapsed = f"{time.time() - start_time:.2f}"
        log(f"TCP请求调试完成: 耗时: {elapsed}s")
        parsed = parse_tcp_response(
            raw_bytes,
            encoding=frame_config.encoding,
            hex_string=frame_config.hex_string,
        )
        request_json_for_extract, request_text_for_extract = resolve_tcp_request_extract_sources(
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
            elapsed=elapsed,
            size=format_byte_size(len(raw_bytes)),
            extract_results=extract_results,
            validator_results=validator_results,
            logs=logger.logs,
            request_info={
                "url": f"{host}:{port}",
                "method": "TCP",
                "headers": {},
                "params": {},
                "body_type": (
                    request_args_type.value
                    if hasattr(request_args_type, "value")
                    else request_args_type
                ),
                "body": build_tcp_debug_request_info_body(
                    request_args_type, request_text=request_text, request_body=request_body
                ),
            },
        )
        LOGGER.info(f"TCP请求调试完成: 耗时: {elapsed}s")
        return result

    @classmethod
    async def debug_python(cls, debug_in: AutoTestPythonCodeDebugRequest) -> Dict[str, Any]:
        """
        调试Python代码步骤；断言规则与PythonStepExecutor对齐（仅允许变量池来源）。

        流程：在StepExecutionContext中执行代码→将返回dict合并进变量池→仅执行断言管线（不做提取）；
        断言未通过时以StepDebugException携带已产出结果返回。

        :param debug_in: Python调试入参
        :return: 调试结果字典（含result/assert_validators）
        :raises StepDebugException: 代码执行失败或断言未通过
        """
        from backend.applications.autotest.services.autotest_step_engine import (
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
            services: AutoTestServices,
            scope: Optional[DataScope] = None,
    ) -> Dict[str, Any]:
        """
        调试Redis请求步骤；查到即止语义与RedisStepExecutor对齐。

        流程：逐条解析配置（project/config/database/expr/variable_name均支持占位符）→
        执行命令→自动写入variable_name及variable_name_count→可选查到即止→统一提取/断言。
        单条失败会终止后续操作并抛出StepDebugException。

        :param debug_in: Redis调试入参
        :param services: CRUD依赖聚合
        :param scope: 数据权限上下文，解析每条操作的环境配置时校验应用与配置可见性
        :return: 调试结果字典
        :raises ParameterException: env_name缺失
        :raises NotFoundException: 应用/环境/配置不存在
        :raises NoPermissionException: 应用或配置创建人不在可见范围
        :raises StepDebugException: 单条操作参数缺失或执行失败
        """
        from backend.applications.autotest.services.autotest_step_engine import RedisStepExecutor

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
        # 自动写入变量池的记录，最终前置拼接进extract_results供前端展示
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
                    scope=scope,
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
                    project_id=operate_project_id,
                    env_name=env_name,
                    config_name=operate_config_name,
                    database_name=operate_database_name,
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

                # 查到即止：仅有效结果才终止后续命令
                if redis_searched and RedisStepExecutor.has_effective_redis_result(redis_data):
                    log(f"【Redis请求】查到即止：{operate_no}已返回有效结果，已终止后续命令")
                    break
            except (ParameterException, NotFoundException, NoPermissionException) as e:
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

        elapsed = f"{time.time() - start_time:.2f}"
        response_text_str = orjson.dumps(redis_operates_response, default=str).decode("UTF-8")
        log(f"Redis请求调试完成: 耗时: {elapsed}s")

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
            elapsed=elapsed,
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
        LOGGER.info(f"Redis请求调试完成: 耗时: {elapsed}s")
        return result
