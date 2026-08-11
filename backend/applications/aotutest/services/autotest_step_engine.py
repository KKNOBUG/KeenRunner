# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_engine.py
@DateTime: 2025/11/9 11:57
"""
from __future__ import annotations

import ast
import asyncio
import re
import time
import traceback
import types
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Optional, Protocol, Tuple, Union
from urllib.parse import unquote

import httpx
import orjson
from aiomysql import Pool
from applications.aotutest.views.autotest_datagram_diff_view import compare_messages

from backend.applications.aotutest.services.autotest_runtime.protocol_http import build_httpx_request_kwargs, assemble_http_body_payloads
from backend.applications.aotutest.services.autotest_runtime.protocol_tcp import select_tcp_payload, parse_tcp_response, parse_tcp_timeouts, \
    resolve_tcp_request_extract_sources, tcp_body_source_for_assert

if TYPE_CHECKING:
    from backend.applications.aotutest.dependencies import AutoTestApiServices

from backend.applications.aotutest.schemas.autotest_detail_schema import AutoTestApiDetailCreate
from backend.applications.aotutest.schemas.autotest_report_schema import AutoTestApiReportCreate
from backend.applications.aotutest.schemas.autotest_step_schema import (
    AutoTestStepTreeUpdateItem,
    ConditionsBase,
    DataBaseOperates,
    RedisOperates,
    StepAssertValidatorItem,
    StepVariablesBase,
    StepsExecuteConfigBase,
    prepare_step_tree_item_for_execution, StepExtractVariableItem,
)
from backend.applications.aotutest.services.autotest_runtime.sandbox import (
    RE_PLACEHOLDER,
    RE_QUOTED_CONCAT,
    RE_QUOTED_PLACEHOLDER,
    USER_CODE_ALLOWED_IMPORT_ROOTS,
    USER_CODE_EXTRA_BUILTINS,
    safe_user_code_import,
)
from backend.applications.aotutest.services.autotest_tool_service import AutoTestToolService
from backend.applications.base.services.scaffold import unique_identify
from backend.common import AioTcpClient, TcpFrameMode
from backend.common.cache.redis_connection_pool import get_app_redis_pool, RedisConnPoolFromConfig
from backend.common.database.database_connection_pool import get_app_database_pool, DBConnPoolFromConfig
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
)
from backend.enums import (
    AutoTestStepType,
    AutoTestReportType,
    AutoTestLoopMode,
    PUBLIC_CASE_TYPES,
    AutoTestLoopErrorStrategy,
    AutoTestReqArgsType,
    AutoTestConfigNodeType, HTTPMethod
)
from backend.services import get_current_username


class StepExecutionError(Exception):
    """
    步骤执行过程中的业务异常，用于中断执行并携带错误信息。
    """


@dataclass
class StepExecutionResult:
    """
    单步执行结果；容器步骤可通过children挂载子步骤结果树。

    :ivar case_id: 用例ID
    :ivar step_id: 步骤ID
    :ivar step_no: 步骤序号
    :ivar step_code: 步骤标识，用于日志与统计去重
    :ivar step_name: 步骤名称
    :ivar step_type: 步骤类型枚举
    :ivar success: 本步是否成功（条件分支未执行子步骤时仍为True）
    :ivar message: 补充说明（如条件不成立时的提示）
    :ivar error: 失败时的错误信息
    :ivar elapsed: 耗时（秒）
    :ivar dataset_name: 参数化数据集名称
    :ivar quote_case_id: 引用公共脚本时的用例ID
    :ivar request: 请求快照，供明细落库
    :ivar response: 响应快照
    :ivar dataset_snapshot: 数据驱动替换用的数据集快照
    :ivar extract_variables: 变量提取结果列表
    :ivar assert_validators: 断言结果列表
    :ivar children: 子步骤执行结果列表
    """
    case_id: Optional[int]
    step_id: Optional[int]
    step_no: Optional[int]
    step_code: Optional[str]
    step_name: Optional[str]
    step_type: AutoTestStepType
    success: bool
    message: str = ""
    error: Optional[str] = None
    elapsed: Optional[float] = None
    dataset_name: Optional[str] = None
    quote_case_id: Optional[int] = None
    request: Optional[Dict[str, Any]] = None
    response: Optional[Dict[str, Any]] = None
    dataset_snapshot: Optional[Dict[str, Any]] = None
    extract_variables: List[Dict[str, Any]] = field(default_factory=list)
    assert_validators: List[Dict[str, Any]] = field(default_factory=list)
    children: List["StepExecutionResult"] = field(default_factory=list)

    def append_child(self, child: "StepExecutionResult") -> None:
        """
        将子步骤执行结果追加到当前结果的children列表。

        :param child: 子步骤的执行结果对象
        :return: None
        """
        self.children.append(child)


class HttpClientProtocol(Protocol):
    """
    HTTP客户端协议，便于依赖注入和单元测试。
    """

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """
        发起HTTP请求（由httpx.AsyncClient实现）。

        :param method: HTTP方法
        :param url: 请求URL
        :param kwargs: 传给httpx的额外参数（headers、json 等）
        :return: 响应对象
        """
        ...


class StepExecutionContext:
    """
    步骤执行上下文：维护用例/报告标识、变量池、日志、HTTP客户端及占位符解析。
    """

    def __init__(
            self,
            case_id: int,
            case_code: str,
            *,
            steps_execute_config: Optional[Dict[str, StepsExecuteConfigBase]] = None,
            report_code: Optional[str] = None,
            dataset_name: Optional[str] = None,
            http_client: Optional[HttpClientProtocol] = None,
            initial_variables: Optional[List[StepVariablesBase]] = None,
            pending_details: Optional[List[AutoTestApiDetailCreate]] = None,
    ) -> None:
        """
        初始化步骤执行上下文。

        :param case_id: 用例ID
        :param case_code: 用例编码
        :param steps_execute_config: 执行环境配置
        :param report_code: 报告编码，用于保存步骤明细
        :param dataset_name: 参数化时传入的数据集名称，仅HttpStepExecutor内据此 + case_id/step_no/step_code查表取数
        :param http_client: 可选HTTP客户端，不传则在__aenter__中创建
        :param initial_variables: 初始会话变量列表List[StepVariablesBase]；会经占位符解析后赋给session_variables
        :param pending_details: save_report 时收集待落库明细的列表；非None时_save_step_detail仅追加不写库
        """
        self.case_id = case_id
        self.case_code = case_code
        # 前端执行前配置替换映射（key=step_id 或 @@step_name）
        self.steps_execute_config: Dict[str, Any] = steps_execute_config or {}
        self.report_code = report_code
        self.dataset_name = dataset_name
        self.logs: Dict[str, List[str]] = {}
        self.pending_details = pending_details
        self.step_cycle_index: Dict[str, int] = {}
        self._current_step_code: Optional[str] = None
        self.executing_quote_case_id: Optional[int] = None
        self._http_client = http_client
        self._exit_stack = AsyncExitStack()
        self.defined_variables: List[StepVariablesBase] = []
        self.session_variables: List[StepVariablesBase] = []
        self.session_variables = self.resolve_placeholders(initial_variables) or []
        self.timeout: float = 30.0
        self.connect: float = 10.0

    async def __aenter__(self) -> "StepExecutionContext":
        """
        异步上下文管理器入口方法, 初始化HTTP客户端（如未提供）。

        若未指定外部HTTP客户端, 将创建一个默认的httpx.AsyncClient实例，并通过AsyncExitStack管理其生命周期, 确保在上下文退出时自动关闭客户端连接。
        :return: 上下文管理器实例本身, 用于异步with语句
        """
        try:
            if self._http_client is None:
                client = httpx.AsyncClient(timeout=httpx.Timeout(timeout=self.timeout, connect=self.connect))
                self._http_client = await self._exit_stack.enter_async_context(client)
            return self
        except Exception as e:
            error_message: str = f"异步上下文管理器: 创建HTTP客户端连接失败, 错误描述: {e}"
            self.log(message=error_message)
            raise StepExecutionError(error_message) from e

    async def __aexit__(
            self,
            exc_type: Optional[type[BaseException]],
            exc: Optional[BaseException],
            tb: Optional[types.TracebackType],
    ) -> None:
        """
        异步上下文退出：关闭由本上下文创建的HTTP客户端。

        :param exc_type: 异常类型
        :param exc: 异常实例
        :param tb: 回溯对象
        :return: None
        """
        try:
            await self._exit_stack.aclose()
        except Exception as e:
            error_message: str = f"异步上下文管理器: 关闭HTTP客户端连接失败, 错误描述: {e}"
            self.log(message=error_message)

    def resolve_placeholders(self, variables: Any, step_code: Optional[str] = None) -> Any:
        """
        解析变量或配置中的${...}占位符（含函数占位符）。

        :param variables: 待解析的值，常见为List[StepVariablesBase]或嵌套结构
        :param step_code: 日志归属的步骤标识，未传则使用当前步骤
        :return: 解析后的值；variables为空时返回None
        """
        if not variables:
            return None
        return AutoTestToolService.resolve_placeholders(
            value=variables or [],
            logger_object=lambda msg: self.log(msg, step_code=step_code),
            is_core_engine=True,
            finished_variables=self
        )

    def resolve_xml_placeholders(self, xml_text: str, step_code: Optional[str] = None) -> str:
        """
        解析XML报文中各文本节点与属性内的 ${...} 占位符（含算术表达式）。

        :param xml_text: XML报文字符串
        :param step_code: 日志归属的步骤标识，未传则使用当前步骤
        :return: 解析后的XML字符串；xml_text为空时原样返回
        """
        if not xml_text:
            return xml_text
        return AutoTestToolService.resolve_xml_placeholders(
            xml_text=xml_text,
            logger_object=lambda msg: self.log(msg, step_code=step_code),
            is_core_engine=True,
            finished_variables=self,
        )

    @property
    def http_client(self) -> HttpClientProtocol:
        """
        获取当前HTTP客户端，必须在async with上下文中使用。

        :return: 当前注入或创建的HTTP客户端
        """
        if self._http_client is None:
            raise RuntimeError("异步上下文管理器: HTTP客户端未创建, 请在异步上下文中使用")
        return self._http_client

    def log(self, message: str, step_code: Optional[str] = None) -> None:
        """
        根据步骤编号记录一条带时间戳的日志。

        :param message: 日志内容
        :param step_code: 步骤编号，用于归属；未传则使用当前步骤编号
        :return: None
        """
        step_code = step_code or self._current_step_code
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        self.logs.setdefault(step_code, []).append(f"[{timestamp}] {message}")

    def set_current_step_code(self, step_code: Optional[str] = None) -> None:
        """
        设置当前执行步骤的step_code，用于后续日志归属。

        :param step_code: 步骤标识代码
        :return: None
        """
        self._current_step_code = step_code

    def clone_state(self) -> Dict[str, Any]:
        """
        返回当前defined_variables与session_variables的字典形式副本，用作Python代码命名空间。

        :return: 含 "defined_variables"、"session_variables" 两个键的字典，值为name->value
        """
        return {
            "defined_variables": AutoTestToolService.list_to_dict(self.defined_variables),
            "session_variables": AutoTestToolService.list_to_dict(self.session_variables),
        }

    def update_variables(
            self,
            variables: List[StepVariablesBase],
            *,
            scope: str = "defined_variables"
    ) -> None:
        """
        根据作用域更新变量：variables为StepVariablesBase列表，同key覆盖，新key追加。

        :param variables: 待更新的变量列表
        :param scope: 目标作用域（defined_variables 或 session_variables）
        :return: None
        """
        if scope not in ("defined_variables", "session_variables"):
            raise ValueError(
                f"【更新变量】失败: \n\t"
                f"无效作用域: {scope}\n\t"
                f"有效作用域: defined_variables 或 session_variables"
            )
        if not isinstance(variables, list):
            raise ValueError(
                f"【更新变量】失败: \n\t"
                f"预期类型: List[StepVariablesBase]\n\t"
                f"实际类型: {type(variables).__name__}"
            )

        target_update_scope: List[StepVariablesBase] = self.defined_variables if scope == "defined_variables" else self.session_variables
        for variable in variables:
            if not isinstance(variable, StepVariablesBase) or not getattr(variable, "key", False):
                raise ValueError("【更新变量】失败: 每项必须为 StepVariablesBase 类型且含非空 key")
            key: str = variable.key
            already_found: bool = False
            for existing_index, existing_item in enumerate(target_update_scope):
                if isinstance(existing_item, StepVariablesBase) and existing_item.key == key:
                    target_update_scope[existing_index] = variable
                    already_found = True
                    break
            if not already_found:
                target_update_scope.append(variable)

        self.log(
            f"【更新变量】成功: \n\t"
            f"更新作用域: {scope}\n\t"
            f"更新变量名: {', '.join(str(x.key) for x in variables if getattr(x, 'key', None))}"
        )

    def get_variable(self, name: str) -> Any:
        """
        根据优先级从defined_variables、session_variables中取名为name的变量值。

        变量作用域说明：defined_variables 为当前步骤的临时变量（从步骤配置中获取），
        session_variables 为持续累积已执行的步骤产生的变量（所有步骤共享）。
        :param name: 变量名，非空字符串
        :return: 变量值
        """
        if not name or not isinstance(name, str):
            raise StepExecutionError(f"【获取变量】变量名无效: \n\t变量名必须是非空字符串, 当前值: {name}")

        for scope_name, scope_list in [
            ("defined_variables", self.defined_variables),
            ("session_variables", self.session_variables),
        ]:
            value = AutoTestToolService.get_value_from_list(scope_list, name)
            if value is not None:
                return value

        raise KeyError(f"【获取变量】变量({name})未定义: \n\t请检查变量名是否正确, 或确认变量是否已在之前的步骤中定义")

    async def sleep(self, seconds: Optional[float]) -> None:
        """
        异步等待指定秒数。

        :param seconds: 等待秒数；None不等待，小于0或大于300抛出异常
        :return: None
        """
        if seconds is None:
            return
        try:
            wait_time = float(seconds)
        except (ValueError, TypeError) as e:
            raise StepExecutionError(f"【等待控制】参数异常: \n\t预期类型: float\n\t实际类型: [{type(seconds).__name__}") from e
        if wait_time < 0:
            raise StepExecutionError(f"【等待控制】参数异常: \n\t参数[seconds]必须是[float]类型, 且不允许小于0")
        if wait_time > 300:
            raise StepExecutionError(f"【等待控制】参数异常: \n\t参数[seconds]必须是[float]类型, 且不允许大于300")
        try:
            await asyncio.sleep(wait_time)
            self.log(f"【等待控制】等待 {wait_time} 秒成功")
        except Exception as e:
            raise StepExecutionError(f"【等待控制】执行等待时发生异常: {e}") from e

    async def send_http_request(
            self,
            method: str,
            url: str,
            *,
            headers: Optional[Dict[str, Any]] = None,
            params: Optional[Dict[str, Any]] = None,
            data: Optional[Any] = None,
            json_data: Optional[Any] = None,
            content: Optional[Any] = None,
            files: Optional[Any] = None,
            timeout: Optional[float] = None,
    ) -> httpx.Response:
        """
        使用上下文 HTTP 客户端发起请求，记录日志。

        :param method: HTTP方法（如 GET、POST）
        :param url: 请求URL
        :param headers: 请求头字典
        :param params: 查询参数字典
        :param data: 请求体（非JSON）
        :param json_data: JSON请求体
        :param content: 原始内容请求体（如XML）
        :param files: 上传文件
        :param timeout: 超时秒数，None使用上下文默认
        :return: 响应对象
        """
        try:
            client = self.http_client
            kwargs = build_httpx_request_kwargs(
                headers=headers,
                params=params,
                data=data,
                json_data=json_data,
                content=content,
                files=files,
                timeout=timeout,
                encode_headers=True,
            )
            try:
                response = await client.request(method, url, **kwargs)
                self.log(
                    f"【HTTP请求】请求成功: \n\t"
                    f"状态描述: {response.reason_phrase}\n\t"
                    f"状态代码: {response.status_code}\n\t"
                    f"响应字符: {response.encoding}\n\t"
                    f"响应版本: {response.http_version}\n\t"
                    f"响应耗时: {response.elapsed.total_seconds():.3f}s"
                )
                return response
            except httpx.InvalidURL as e:
                error_message: str = (
                    f"【HTTP请求】请求无效: \n\t"
                    f"请求的URL地址不符合规范(可能原因: 地址或端口拼写错误或目标服务器处于宕机状态)\n\t"
                    f"错误类型: {type(e).__name__}\n\t"
                    f"错误描述: {e}"
                )
                self.log(error_message)
                raise StepExecutionError(error_message) from e
            except httpx.TimeoutException as e:
                error_message: str = (
                    f"【HTTP请求】请求超时: \n\t"
                    f"在规定时间范围内未能从服务器获取到响应数据(可能原因: 网络延迟、服务器响应慢或超时设置过短)\n\t"
                    f"错误类型: {type(e).__name__}\n\t"
                    f"错误描述: {e}"
                )
                self.log(error_message)
                raise StepExecutionError(error_message) from e
            except httpx.ConnectError as e:
                error_message: str = (
                    f"【HTTP请求】请求失败: \n\t"
                    f"无法建立到达目标服务器的连接(可能原因: 网络连接不可达、DNS解析失败或目标服务器处于拒绝状态)\n\t"
                    f"错误类型: {type(e).__name__}\n\t"
                    f"错误描述: {e}"
                )
                self.log(error_message)
                raise StepExecutionError(error_message) from e
            except httpx.RequestError as e:
                error_message: str = (
                    f"【HTTP请求】请求异常: \n\t"
                    f"目标服务器无法完成该请求处理(可能原因: 网络连接异常、数据包缺少或丢失\n\t"
                    f"错误类型: {type(e).__name__}\n\t"
                    f"错误描述: {e}"
                )
                self.log(error_message)
                raise StepExecutionError(error_message) from e
            except Exception as e:
                error_message: str = (
                    f"【HTTP请求】请求服务器时发生未知错误: \n\t"
                    f"错误类型: {type(e).__name__}\n\t"
                    f"错误描述: {e}"
                )
                self.log(error_message)
                raise StepExecutionError(error_message) from e
        except StepExecutionError:
            raise
        except Exception as e:
            self.log(str(e))
            raise StepExecutionError(str(e)) from e

    def run_python_code(
            self,
            code: str,
            *,
            namespace: Optional[Dict[str, Any]] = None,
            step_result: Optional[StepExecutionResult] = None
    ) -> Union[Dict[str, Any], List[Dict[Any, Any]]]:
        """
        在受限内置与namespace下执行code，支持单函数定义或result变量。

        import/from 仅允许USER_CODE_EXTRA_BUILTINS中的根名；其余模块不可导入；另可使用safe_globals中其它内置名及namespace变量。
        :param code: Python 代码字符串，可为单行或多行
        :param namespace: 执行时的局部命名空间（如变量字典），可选；不可通过__builtins__注入
        :param step_result: 可选；传入时写入其request，记录原始代码快照（未经占位符解析与规范化的原始code）
        :return: 代码中定义的 result 或单函数返回值；支持 Dict[str, Any] 或 List[Dict]；无结果时返回空字典
        """
        if step_result is not None:
            step_result.request = {
                "request_code": code,
                "request_args_type": AutoTestReqArgsType.RAW
            }
        if not code:
            return {}
        resolved_code: str = self.resolve_code_placeholders(code)
        prepared_code: str = self.normalize_python_code(resolved_code)
        try:
            self._validate_user_python_restricted(prepared_code)
        except StepExecutionError as e:
            self.log(str(e))
            raise
        safe_globals = {
            "__builtins__": {
                "__import__": safe_user_code_import,
                # 基础类型
                "bool": bool,
                "bytes": bytes,
                "bytearray": bytearray,
                "dict": dict,
                "float": float,
                "frozenset": frozenset,
                "int": int,
                "list": list,
                "set": set,
                "str": str,
                "tuple": tuple,
                # 数学运算
                "abs": abs,
                "divmod": divmod,
                "max": max,
                "min": min,
                "pow": pow,
                "round": round,
                "sum": sum,
                # 进制/编码转换
                "bin": bin,
                "chr": chr,
                "hex": hex,
                "oct": oct,
                "ord": ord,
                # 迭代/序列操作
                "all": all,
                "any": any,
                "enumerate": enumerate,
                "filter": filter,
                "len": len,
                "map": map,
                "range": range,
                "reversed": reversed,
                "sorted": sorted,
                "zip": zip,
                # 类型判断
                "callable": callable,
                "hash": hash,
                "id": id,
                "isinstance": isinstance,
                "issubclass": issubclass,
                "type": type,
                # 输出/调试
                "print": print,
                "repr": repr,
                **USER_CODE_EXTRA_BUILTINS,
            }
        }
        local_context: Dict[str, Any] = {}
        if namespace:
            namespace.pop("__builtins__", None)
            local_context.update(namespace)

        try:
            exec(prepared_code, safe_globals, local_context)
        except SyntaxError as e:
            error_message: str = (
                f"【代码请求(Python)】代码解析失败: \n\t"
                f"请遵循 Python PEP8 编码规范\n\t"
                f"错误描述: {e}\n\t"
                f"错误位置: 第{e.lineno}行\n\t"
                f"错误类型: {type(e).__name__}\n\t"
                f"错误时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            self.log(error_message)
            raise StepExecutionError(error_message) from e
        except NameError as e:
            error_message: str = (
                f"【代码请求(Python)】代码解析失败: \n\t"
                f"请检查代码中是否引用了未定义的变量或函数\n\t"
                f"错误描述: {e}\n\t"
                f"错误类型: {type(e).__name__}\n\t"
                f"错误时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            self.log(error_message)
            raise StepExecutionError(error_message) from e
        except Exception as e:
            error_message: str = (
                f"【代码请求(Python)】代码解析异常: \n\t"
                f"错误描述: {e}\n\t"
                f"错误类型: {type(e).__name__}\n\t"
                f"错误时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            self.log(error_message)
            raise StepExecutionError(error_message) from e

        functions = {
            name: obj
            for name, obj in local_context.items()
            if isinstance(obj, types.FunctionType)
        }
        if functions:
            if len(functions) == 1:
                try:
                    func = next(iter(functions.values()))
                    result = func()
                except Exception as e:
                    error_message: str = (
                        f"【代码请求(Python)】执行异常: \n\t"
                        f"错误描述: {e}\n\t"
                        f"错误类型: {type(e).__name__}\n\t"
                        f"错误时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    self.log(error_message)
                    raise StepExecutionError(error_message) from e
            else:
                func_names = ", ".join(functions.keys())
                error_message: str = (
                    f"【代码请求(Python)】执行失败: \n\t"
                    f"仅支持定义一个函数作为入口, 当前存在多个函数: {func_names}"
                )
                self.log(error_message)
                raise StepExecutionError(error_message)
        elif "result" in local_context:
            result = local_context["result"]
        else:
            result = None

        if result is None:
            self.log(f"【代码请求(Python)】执行完成, 但无结果: {result!r}")
            return {}
        if isinstance(result, dict):
            pass
        elif isinstance(result, list):
            invalid_items = [
                (idx, type(item).__name__)
                for idx, item in enumerate(result)
                if not isinstance(item, dict)
            ]
            if invalid_items:
                preview = ", ".join(f"[{idx}]={typ}" for idx, typ in invalid_items[:5])
                error_message = (
                    f"【代码请求(Python)】执行失败, 返回值类型不被接受: \n\t"
                    f"预期类型: List[Dict[Any, Any]]\n\t"
                    f"实际类型: list（存在非 dict 元素: {preview}"
                    f"{' ...' if len(invalid_items) > 5 else ''}）\n\t"
                    f"返回结果: {result!r}"
                )
                self.log(error_message)
                raise StepExecutionError(error_message)
        else:
            error_message: str = (
                f"【代码请求(Python)】执行失败, 返回值类型不被接受: \n\t"
                f"预期类型: Dict[str, Any] 或 List[Dict[Any, Any]]\n\t"
                f"实际类型: {type(result).__name__}\n\t"
                f"返回结果: {result!r}"
            )
            self.log(error_message)
            raise StepExecutionError(error_message)
        result = self._stringify_mapping_keys(result)
        try:
            result_serializer: str = orjson.dumps(result, option=orjson.OPT_INDENT_2).decode("UTF-8")
        except TypeError:
            result_serializer = repr(result)
        self.log(f"【代码请求(Python)】执行完成, 返回结果: \n{result_serializer}")
        # 对于f-string支持度不够，如下示例（暂未解决）：
        #     id_card = '${generate_ident_card_number()}'
        #     birthday = f'${{generate_ident_card_birthday(ident_card_number=${id_card})}}'
        return result

    @staticmethod
    def _stringify_mapping_keys(value: Any) -> Any:
        """
        递归将mapping的key转为str，便于orjson序列化与JSON落库。

        :param value: 任意返回值（通常为 dict 或 list[dict]）
        :return: key 已规范化后的同构结构
        """
        if isinstance(value, dict):
            return {str(k): StepExecutionContext._stringify_mapping_keys(v) for k, v in value.items()}
        if isinstance(value, list):
            return [StepExecutionContext._stringify_mapping_keys(item) for item in value]
        if isinstance(value, tuple):
            return [StepExecutionContext._stringify_mapping_keys(item) for item in value]
        return value

    @staticmethod
    def _validate_user_python_restricted(source: str) -> None:
        """
        import/from 仅允许USER_CODE_EXTRA_BUILTINS中的根名（与safe_user_code_import一致）；语法错误留给exec。

        :param source: 待校验的Python源代码字符串
        :return: None
        """
        allowed_cn = "、".join(sorted(USER_CODE_ALLOWED_IMPORT_ROOTS))
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root not in USER_CODE_ALLOWED_IMPORT_ROOTS:
                        error_message = (
                            "【代码请求(Python)】安全限制(仅允许导入预期定义的标准库模块): \n\t"
                            f"允许依赖: {allowed_cn}\n\t"
                            f"非法依赖: {alias.name}"
                        )
                        raise StepExecutionError(error_message)
            elif isinstance(node, ast.ImportFrom):
                if node.level != 0:
                    error_message = (
                        "【代码请求(Python)】安全限制: \n\t"
                        "不允许相对导入, 如: from . import xx 或 from .. import xx"
                    )
                    raise StepExecutionError(error_message)
                if not node.module:
                    error_message = (
                        "【代码请求(Python)】安全限制: \n\t"
                        "不允许此类 from 导入"
                    )
                    raise StepExecutionError(error_message)
                root = node.module.split(".", 1)[0]
                if root not in USER_CODE_ALLOWED_IMPORT_ROOTS:
                    error_message = (
                        "【代码请求(Python)】安全限制(仅允许从以下模块 from 导入): \n\t"
                        f"允许依赖: {allowed_cn}\n\t"
                        f"非法依赖: {node.module}"
                    )
                    raise StepExecutionError(error_message)

    @staticmethod
    def normalize_python_code(code: str) -> str:
        """
        将单行函数形式的代码格式化为多行：提取import/from，分离def与函数体并正确缩进。

        :param code: 原始Python代码字符串，可为单行函数定义
        :return: 格式化后的多行代码；空串或已有换行则原样返回
        """
        code = code.strip()
        if not code:
            return code

        # 如果代码包含换行符, 说明已经格式化好了
        if "\n" in code:
            return code

        # 处理单行函数定义的情况, 例如: "def generate_var():import random return {...}"
        if "def " in code and ":" in code:
            # 分离函数定义和函数体
            colon_pos = code.find(":")
            func_def = code[:colon_pos + 1].strip()  # "def generate_var():"
            body = code[colon_pos + 1:].strip()  # "import random return {...}"
            # 提取import/from语句（必须在return之前）
            import_lines = []
            remaining_body = body
            # 查找所有import/from语句
            while True:
                import_pos = remaining_body.find("import ")
                from_pos = remaining_body.find("from ")
                if import_pos == -1 and from_pos == -1:
                    break
                # 找到第一个import或from
                if from_pos != -1 and (import_pos == -1 or from_pos < import_pos):
                    pos = from_pos
                    keyword = "from "
                else:
                    pos = import_pos
                    keyword = "import "

                # 找到import语句的结束位置（下一个关键字或行尾）
                remaining_after_keyword = remaining_body[pos + len(keyword):]
                next_keywords = ["return ", "if ", "for ", "while ", "with ", "import ", "from "]
                end_pos = len(remaining_after_keyword)
                for kw in next_keywords:
                    kw_pos = remaining_after_keyword.find(kw)
                    if kw_pos != -1 and kw_pos < end_pos:
                        end_pos = kw_pos
                # 提取完整的import语句
                import_stmt = remaining_body[pos:pos + len(keyword) + end_pos].strip()
                import_lines.append(import_stmt)
                # 继续处理剩余部分
                remaining_body = remaining_body[pos + len(keyword) + end_pos:].strip()

            # 组合格式化后的代码
            normalized_parts = []
            # 1. 先添加所有import语句（在函数外部）
            if import_lines:
                normalized_parts.extend(import_lines)
            # 2. 添加函数定义
            normalized_parts.append(func_def)
            # 3. 添加函数体（需要缩进）
            if remaining_body:
                # 处理return等语句, 确保有正确的缩进
                for keyword in ("return ", "if ", "for ", "while ", "with "):
                    if remaining_body.startswith(keyword):
                        normalized_parts.append(f"    {remaining_body}")
                        break
                else:
                    # 如果没有匹配的关键字, 直接添加并缩进
                    normalized_parts.append(f"    {remaining_body}")
            return "\n".join(normalized_parts)
        return code

    def resolve_code_placeholders(self, code: str) -> str:
        """
        解析代码中的 ${var}：引号内替换为合法 Python 字面量，拼接形式保留字符串；代码逻辑中替换为 Python 字面量。

        处理规则：
        1. 字符串字面量中的占位符（如 '${var}'）替换为合法字面量：字符串用 repr 保留引号，数值/布尔/None 裸写
           例如：dic["k"] = "${name}" -> dic["k"] = '张三'；'${idx_1}' == 1 -> 1 == 1（idx_1=1）
        2. 字符串拼接中的占位符（如 '${item}_1001'）替换为实际值，保持字符串格式
           例如：'${item_1}_1001' 会变成 'test_1001'（假设 item_1 = "test"）
        3. 代码逻辑中的占位符（如 if ${var} == 1:）直接替换为实际值的 Python 表示
        注意：对 f-string 中嵌套占位符的支持度有限，例如 id_card = '${generate_ident_card_number()}' 与
        birthday = f'${{generate_ident_card_birthday(ident_card_number={id_card})}}' 这类写法可能无法正确解析。
        :param code: 含占位符的 Python 代码字符串
        :return: 占位符替换后的代码；异常时返回原 code
        """
        if not code or not isinstance(code, str):
            return code

        def replace_string_placeholder(match: re.Match[str]) -> str:
            """
            替换引号内完整占位符 '${var}' 为合法 Python 字面量。
            """
            var_name = match.group(2)
            if not var_name:
                self.log("【代码请求(Python)】占位符解析失败: \n\t不允许引用空白符, 保留原值")
                return match.group(0)
            try:
                # 支持函数占位符: "${generate_phone()}"
                if "(" in var_name and var_name.strip().endswith(")"):
                    var_value = AutoTestToolService.execute_func_string_single(var_name)
                else:
                    var_value = self.get_variable(var_name)
            except KeyError:
                self.log(f"【代码请求(Python)】占位符解析失败: \n\t变量或函数({var_name})未定义, 保留原值")
                return match.group(0)
            except Exception as e:
                self.log(f"【代码请求(Python)】占位符解析失败: \n\t引用变量或函数({var_name})失败, 保留原值\n\t错误描述: {e}")
                return match.group(0)

            # 在字符串字面量中，替换为合法的 Python 字面量，避免产生无效代码（如 dic["k"] = 邵刚 导致 NameError）
            # 字符串用 repr 保留引号：'${name}' -> '邵刚'；数值/布尔/None 裸写：'${idx}' == 1 -> 1 == 1
            if isinstance(var_value, str):
                return repr(var_value)
            elif isinstance(var_value, (int, float, bool)):
                return str(var_value)
            elif var_value is None:
                return "None"
            else:
                return repr(var_value)

        # 先处理字符串字面量中的占位符（如 '${var}' 或 "${var}"）
        code = RE_QUOTED_PLACEHOLDER.sub(replace_string_placeholder, code)

        def replace_string_concat_placeholder(match: re.Match[str]) -> str:
            """
            替换引号内拼接占位符 'prefix_${var}_suffix'，保持字符串形态。
            """
            quote_char = match.group(1)
            prefix = match.group(2)
            var_name = match.group(3)
            suffix = match.group(4)
            if not var_name:
                self.log("【代码请求(Python)】占位符解析失败: \n\t不允许引用空白符, 保留原值")
                return match.group(0)
            try:
                var_value = self.get_variable(var_name)
            except KeyError:
                self.log(f"【代码请求(Python)】占位符解析失败: \n\t变量({var_name})未定义, 保留原值")
                return match.group(0)
            except Exception as e:
                self.log(f"【代码请求(Python)】占位符解析失败: \n\t引用变量({var_name})失败, 保留原值\n\t错误描述: {e}")
                return match.group(0)

            # 字符串拼接，保持字符串格式
            result = prefix + str(var_value) + suffix
            return quote_char + result + quote_char

        # 处理字符串拼接中的占位符；循环直到无匹配，避免 "a_${x}_${y}" 中后一个占位符被误当代码逻辑用 repr 产生多余引号
        while True:
            new_code = RE_QUOTED_CONCAT.sub(replace_string_concat_placeholder, code)
            if new_code == code:
                break
            code = new_code

        def replace_code_placeholder(match: re.Match[str]) -> str:
            """
            替换代码逻辑中的裸占位符 ${var} 为 Python 字面量表示。
            """
            var_name = match.group(1)
            if not var_name:
                self.log("【代码请求(Python)】占位符解析失败: \n\t不允许引用空白符, 保留原值")
                return match.group(0)
            try:
                var_value = self.get_variable(var_name)
            except KeyError:
                self.log(f"【代码请求(Python)】占位符解析失败: \n\t变量({var_name})未定义, 保留原值")
                return match.group(0)
            except Exception as e:
                self.log(f"【代码请求(Python)】占位符解析失败: \n\t引用变量({var_name})失败, 保留原值\n\t错误描述: {e}")
                return match.group(0)

            # 在代码逻辑中，返回值的Python表示
            if isinstance(var_value, str):
                return repr(var_value)
            elif isinstance(var_value, (int, float, bool)):
                return str(var_value)
            elif var_value is None:
                return "None"
            else:
                return repr(var_value)

        try:
            # 处理代码逻辑中的占位符，如 if ${var} == 1:
            resolved_code = RE_PLACEHOLDER.sub(replace_code_placeholder, code)
            return resolved_code
        except Exception as e:
            error_message: str = (
                f"【代码请求(Python)】占位符解析异常, 保留原值: \n\t"
                f"错误类型: {type(e).__name__}\n\t"
                f"错误描述: {e}\n\t"
            )
            self.log(error_message)
            return code

    @property
    def current_step_code(self) -> Optional[str]:
        """当前执行步骤的step_code，用于日志归属。"""
        return self._current_step_code


class BaseStepExecutor:
    """
    步骤执行器基类：持有step与context，执行后合并extract_variables到session、可选保存明细。
    """

    def __init__(self, step: AutoTestStepTreeUpdateItem, context: StepExecutionContext):
        """
        初始化步骤执行器。

        :param step: 当前步骤模型，含step_type、step_code、defined_variables等
        :param context: 执行上下文，用于变量、日志、HTTP请求等
        """
        self.step = step
        self.context = context

    @property
    def case_id(self) -> Optional[int]:
        """当前步骤所属用例 ID。"""
        return self.step.case_id

    @property
    def step_id(self) -> Optional[int]:
        """当前步骤主键 ID。"""
        return self.step.step_id

    @property
    def step_no(self) -> Optional[int]:
        """当前步骤序号。"""
        return self.step.step_no

    @property
    def step_code(self) -> Optional[str]:
        """当前步骤标识代码。"""
        return self.step.step_code

    @property
    def step_name(self) -> Optional[str]:
        """当前步骤名称。"""
        return self.step.step_name

    @property
    def step_type(self) -> AutoTestStepType:
        """当前步骤类型枚举。"""
        return AutoTestStepType(self.step.step_type)

    @property
    def quote_case_id(self) -> Optional[int]:
        """引用用例 ID（引用公共脚本时）。"""
        return self.step.quote_case_id

    @property
    def children(self) -> List[AutoTestStepTreeUpdateItem]:
        """当前步骤的子步骤列表（children + quote_steps，根据 step_no 排序）。"""
        return sorted(
            list(self.step.children or []) + list(self.step.quote_steps or []),
            key=lambda item: (item.step_no or 0),
        )

    @classmethod
    async def get_services(cls) -> AutoTestApiServices:
        """获取自动化测试依赖注入的CRUD服务聚合。"""
        from backend.applications.aotutest.dependencies import get_autotest_api_services
        return await get_autotest_api_services()

    def get_execute_config(self, database_operates_index: Optional[int] = None) -> Optional[StepsExecuteConfigBase]:
        """
        获取当前步骤的执行配置（HTTP请求、TCP请求、SQL请求）。
        执行配置KEY组成规则：step_id优先、其次是@@step_name、如果是SQL请求则需要继续拼接操作序号

        :param database_operates_index: 数据库多操作时的操作序号（拼接配置 key 后缀）
        :return: 执行配置；未配置或解析失败时返回 None
        """
        step_exec_config_map: Dict[str, Any] = self.context.steps_execute_config
        if not step_exec_config_map or not isinstance(step_exec_config_map, dict):
            return None
        step_id: Optional[int] = self.step.step_id
        step_name: Optional[str] = self.step.step_name
        cfg_key: str = str(step_id) if step_id else f"@@{str(step_name).strip()}"
        if database_operates_index is not None and database_operates_index >= 0:
            cfg_key += f"_@@{database_operates_index}"
        cfg_value: Any = step_exec_config_map.get(cfg_key)
        if not cfg_value:
            return None
        elif isinstance(cfg_value, StepsExecuteConfigBase):
            return cfg_value
        elif isinstance(cfg_value, dict):
            try:
                return StepsExecuteConfigBase.model_validate(cfg_value)
            except Exception:
                return None
        return None

    def apply_extract_and_assert(
            self,
            result: StepExecutionResult,
            *,
            step_label: str,
            response_text: Optional[str] = None,
            response_json: Optional[Any] = None,
            response_headers: Optional[Dict[str, Any]] = None,
            response_cookies: Optional[Dict[str, Any]] = None,
            request_text: Optional[str] = None,
            request_json: Optional[Any] = None,
            request_headers: Optional[Dict[str, Any]] = None,
            request_cookies: Optional[Dict[str, Any]] = None,
            extract_variables: Optional[Any] = None,
            assert_validators: Optional[Any] = None,
            step_struct: Optional[Dict[str, Dict[str, Any]]] = None,
            session_lookup_extra: Optional[Dict[str, Any]] = None,
            body_source: str = "response json",
    ) -> None:
        """
        统一变量提取 + 断言：构建变量池查找表，调用工具管线，失败转为StepExecutionError。

        :param result: 用于追加提取与断言结果的步骤执行结果对象
        :param step_label: 步骤标签，用于异常信息中标识来源步骤
        :param response_text: 响应文本
        :param response_json: 响应JSON对象
        :param response_headers: 响应头字典
        :param response_cookies: 响应Cookie字典
        :param request_text: 请求文本
        :param request_json: 请求JSON对象
        :param request_headers: 请求头字典
        :param request_cookies: 请求Cookie字典
        :param extract_variables: 变量提取规则，缺省时使用步骤自身的 extract_variables
        :param assert_validators: 断言校验规则，缺省时使用步骤自身的assert_validators
        :param step_struct: 步骤结构映射，供提取断言管线解析引用
        :param session_lookup_extra: 额外并入变量池查找表的会话变量
        :param body_source: 提取断言所用的响应体来源标识
        :return: None
        """
        session_lookup = AutoTestToolService.build_session_lookup(
            self.context.defined_variables,
            self.context.session_variables,
        )
        if session_lookup_extra:
            session_lookup.update(session_lookup_extra)
        try:
            extract_results, assert_results = AutoTestToolService.run_extract_and_assert(
                extract_variables=extract_variables if extract_variables is not None else self.step.extract_variables,
                assert_validators=assert_validators if assert_validators is not None else self.step.assert_validators,
                response_text=response_text,
                response_json=response_json,
                response_headers=response_headers,
                response_cookies=response_cookies,
                request_text=request_text,
                request_json=request_json,
                request_headers=request_headers,
                request_cookies=request_cookies,
                session_variables_lookup=session_lookup,
                log_callback=lambda msg: self.context.log(msg, step_code=self.step_code),
                finished_variables=self.context,
                is_core_engine=True,
                step_struct=step_struct,
                body_source=body_source,
                raise_on_failure=False,
            )
            # 无论成功与否，先将结果追加到 result，确保落库不丢失
            result.extract_variables.extend(extract_results)
            result.assert_validators.extend(assert_results)
            # 检查是否存在失败项，有则抛出 StepExecutionError
            extract_failed = [r for r in extract_results if not r.get("success", True)]
            assert_failed = [r for r in assert_results if not r.get("success", True)]
            if extract_failed or assert_failed:
                error_parts = []
                if extract_failed:
                    error_parts.append(
                        f"【变量提取】共计{len(extract_failed)}个提取失败: \n"
                        f"{orjson.dumps(extract_failed, option=orjson.OPT_INDENT_2).decode('UTF-8')}"
                    )
                if assert_failed:
                    error_parts.append(
                        f"【断言验证】共计{len(assert_failed)}个断言失败: \n"
                        f"{orjson.dumps(assert_failed, option=orjson.OPT_INDENT_2).decode('UTF-8')}"
                    )
                raise StepExecutionError("\n".join(error_parts))
        except ValueError as e:
            raise StepExecutionError(str(e)) from e
        except StepExecutionError:
            raise
        except Exception as e:
            error_message = f"【{step_label}】在运行变量提取或断言时发生异常, 错误详情: {e}"
            self.context.log(error_message, step_code=self.step_code)
            raise StepExecutionError(error_message) from e

    async def execute(self) -> Optional[StepExecutionResult]:
        """
        执行当前步骤：注入defined_variables、调用_execute、合并extract_variables、可选保存明细。
        若 step_is_skipped 为True，仅打INFO日志并返回None（不写明细、不计入统计、不执行子步骤）。

        :return: 本步骤执行结果；跳过时返回None
        """
        # 跳过/注释：当作没有该步骤（父跳过时不会进入子步，故无需祖先标记）
        if bool(getattr(self.step, "step_is_skipped", False)):
            LOGGER.info(
                f"【步骤跳过】case_id={self.case_id}, step_no={self.step_no}, "
                f"step_name={self.step_name}, step_code={self.step_code}, step_type={self.step_type}"
            )
            return None

        start: float = time.perf_counter()
        step_start_time: datetime = datetime.now()
        step_st_time_str: str = step_start_time.strftime("%Y-%m-%d %H:%M:%S.%f")
        num_cycles: Optional[int] = self.context.step_cycle_index.get(self.step_code)
        if self.step_code:
            self.context.step_cycle_index.setdefault(self.step_code, num_cycles)
        result = StepExecutionResult(
            case_id=self.case_id,
            step_id=self.step_id,
            step_no=self.step_no,
            step_code=self.step_code,
            step_name=self.step_name,
            step_type=self.step_type,
            quote_case_id=self.quote_case_id,
            success=True,
        )
        # 设置当前步骤标识（先保存上一级 step_code 以便 finally 恢复）
        previous_step_code: Optional[str] = self.context.current_step_code
        self.context.set_current_step_code(self.step_code)
        # 将当前步骤的 defined_variables 注入到 context，供占位符解析使用
        step_defined_variables: List[StepVariablesBase] = self.step.defined_variables
        self.context.defined_variables = self.context.resolve_placeholders(
            variables=step_defined_variables,
            step_code=self.step_code
        ) or []
        try:
            await self._execute(result)
        except Exception as e:  # 会导致重复异常的信息展示在log中
            result.success = False
            # 不再在此处 log：各执行器在 _execute 内已记录完整错误信息，避免重复
            # self.context.log(str(e), step_code=previous_step_code)
            if not result.error:
                result.error = str(e)
            # -----------------------------------------------------------------------
            # 本 except Exception 不能删除，约定各个execute()必须返回一个 StepExecutionResult，所以不能把异常继续往上抛。
            # 各执行器在 _execute 内的行为：捕获异常后设置 result.success=False、result.error=
            # format_step_error_message(...)，并 self.context.log(result.error)，再 raise。
            # 返回到此处时：异常已被捕获，result 可能已由执行器填好 error，且错误已记入 context.logs。
            # 此处仅做：补全 result.success=False、未设置时补全 result.error，且不再 log（避免重复）；
            # 不 re-raise，让后面的 finally 正常跑完（合并变量、计算 elapsed、保存明细），然后 return result。
            # 这样，无论本步成功还是失败，调用方拿到的都是同一个 StepExecutionResult，可以统一做 append 和统计。
            # -----------------------------------------------------------------------
        finally:
            try:
                # 将本步骤的 extract_variables 合并到 session_variables，供后续步骤引用（仅合并提取成功的，避免失败项用 None 覆盖）
                if getattr(result, "extract_variables", None) and isinstance(result.extract_variables, list):
                    extract_list = [
                        StepVariablesBase(key=str(item.get("name")), value=item.get("extract_value"), desc="")
                        for item in result.extract_variables
                        if isinstance(item, dict) and item.get("name") is not None and item.get("success") is True
                    ]
                    if extract_list:
                        self.context.update_variables(extract_list, scope="session_variables")
            except Exception as e:
                self.context.log(f"【更新变量】-【session_variables】错误: {e}", step_code=self.step_code)

            self.context.set_current_step_code(step_code=previous_step_code)
            end: float = time.perf_counter()
            result.elapsed = round(end - start, 6)
            if self.context.report_code:
                try:
                    await self._save_step_detail(result, step_st_time_str, num_cycles)
                except Exception as e:
                    # 明细收集失败不中断后续步骤；标记本步失败并记录可排障上下文
                    detail_fail_prefix: str = "[明细收集失败]"
                    detail_fail_message: str = (
                        f"{detail_fail_prefix}\n\t"
                        f"报告标识: {self.context.report_code}\n\t"
                        f"用例ID: {self.context.case_id}\n\t"
                        f"用例标识: {self.context.case_code}\n\t"
                        f"步骤ID: {self.step_id}\n\t"
                        f"步骤序号: {self.step_no}\n\t"
                        f"步骤标识: {self.step_code}\n\t"
                        f"步骤名称: {self.step_name}\n\t"
                        f"步骤类型: {self.step_type}\n\t"
                        f"循环轮次: {num_cycles}\n\t"
                        f"步骤执行结果: {'成功' if result.success else '失败'}\n\t"
                        f"错误时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\t"
                        f"错误类型: {type(e).__name__}\n\t"
                        f"错误描述: {e}"
                    )
                    result.success = False
                    if result.error:
                        result.error = f"{result.error}\n{detail_fail_message}"
                    else:
                        result.error = detail_fail_message
                    self.context.log(detail_fail_message, step_code=self.step_code)
                    LOGGER.error(
                        f"{detail_fail_message}\n"
                        f"错误回溯:\n{traceback.format_exc()}"
                    )
        return result

    async def _save_step_detail(self, result: StepExecutionResult, step_st_time_str: str, num_cycles: int) -> None:
        """
        将本步骤执行结果序列化为明细创建体并追加到context.pending_details，由调用方在短事务内统一落库。

        :param result: 本步骤执行结果对象
        :param step_st_time_str: 步骤开始时间字符串
        :param num_cycles: 循环第几轮（非循环步骤可为None）
        :return: None
        """
        step_end_time: datetime = datetime.now()
        step_ed_time_str: str = step_end_time.strftime("%Y-%m-%d %H:%M:%S.%f")
        step_elapsed: str = f"{result.elapsed:.3f}" if result.elapsed is not None else "0.000"
        step_logs: List[str] = self.context.logs.get(self.step_code, [])
        step_exec_logger: Optional[str] = "\n".join(step_logs) if step_logs else None
        response_body = None
        response_text = None
        response_header = None
        response_cookie = None
        response_elapsed = None
        if result.response:
            response_text = result.response.get("response_text")
            response_body = result.response.get("response_body")
            response_header = result.response.get("response_header")
            response_cookie = result.response.get("response_cookie")
            response_elapsed = result.response.get("response_elapsed")
            if response_text and not response_body:
                try:
                    response_body = orjson.loads(response_text)
                except (ValueError, TypeError):
                    response_body = None

        extract_variables: List[Dict[str, Any]] = result.extract_variables
        defined_variables: List[StepVariablesBase] = self.context.defined_variables
        session_variables: List[StepVariablesBase] = self.context.session_variables
        dataset_name: Optional[str] = result.dataset_name
        dataset_snapshot: Optional[Dict[str, Any]] = result.dataset_snapshot
        have_data_driven: bool = dataset_snapshot is not None
        actual_request: Dict[str, Any] = result.request or {}
        # 当step_id、step_code为None时说明是临时步骤(没有保存入库)，所以替换为step_timestamp、temporary-step-debugging标识
        step_timestamp: int = int(str(datetime.now().timestamp()).replace(".", ""))
        detail_create = AutoTestApiDetailCreate(
            case_id=self.context.case_id,
            case_code=self.context.case_code,
            report_code=self.context.report_code,
            quote_case_id=self.quote_case_id or result.quote_case_id,
            step_id=self.step_id or step_timestamp,
            step_no=self.step_no,
            step_name=self.step_name,
            step_code=self.step_code or "temporary-step-debugging",
            step_type=self.step_type,
            step_state=result.success,
            step_st_time=step_st_time_str,
            step_ed_time=step_ed_time_str,
            step_elapsed=step_elapsed,
            step_exec_logger=step_exec_logger,
            step_exec_except=result.error,
            num_cycles=num_cycles,
            # 请求相关
            request_url=actual_request.get("request_url"),
            request_port=actual_request.get("request_port"),
            request_method=actual_request.get("request_method"),
            request_args_type=actual_request.get("request_args_type"),
            request_project_id=self.step.request_project_id,
            request_config_name=self.step.request_config_name,
            request_env_name=actual_request.get("request_env_name"),
            request_header=actual_request.get("request_header"),
            request_params=actual_request.get("request_params"),
            request_form_data=actual_request.get("request_form_data"),
            request_form_urlencoded=actual_request.get("request_form_urlencoded"),
            request_form_file=actual_request.get("request_form_file"),
            request_body=actual_request.get("request_body"),
            request_text=actual_request.get("request_text"),
            # 逻辑相关
            wait=self.step.wait,
            loop_mode=self.step.loop_mode,
            loop_timeout=self.step.loop_timeout,
            loop_maximums=self.step.loop_maximums,
            loop_interval=self.step.loop_interval,
            loop_iterable=self.step.loop_iterable,
            loop_on_error=self.step.loop_on_error,
            code=actual_request.get("request_code"),
            conditions=actual_request.get("conditions"),
            database_operates=actual_request.get("database_operates"),
            database_searched=actual_request.get("database_searched"),
            redis_operates=actual_request.get("redis_operates"),
            redis_searched=actual_request.get("redis_searched"),
            # 数据源相关
            dataset_name=dataset_name if have_data_driven else None,
            dataset_snapshot=dataset_snapshot if have_data_driven else None,
            # 响应相关
            response_cookie=response_cookie or None,
            response_header=response_header or None,
            response_body=response_body or None,
            response_text=response_text or None,
            response_elapsed=response_elapsed,
            # 变量相关(快照空池统一落NULL，与「有或没有」两态语义一致)
            session_variables=session_variables or None,
            defined_variables=defined_variables or None,
            extract_variables=extract_variables or None,
            assert_validators=result.assert_validators or None
        )
        if self.context.pending_details is not None:
            self.context.pending_details.append(detail_create)

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        子类实现：执行当前步骤逻辑，成功/失败写入result，异常由execute()捕获。

        :param result: 用于写入本步骤执行结果的StepExecutionResult实例
        :return: None
        """
        raise NotImplementedError

    async def _execute_children(self) -> List[StepExecutionResult]:
        """
        根据step_no顺序执行所有子步骤（children + quote_steps）。

        :return: 子步骤结果列表；step_is_skipped的子步返回None会被跳过；异常子步转为失败结果项
        """
        results: List[StepExecutionResult] = []
        for child in self.children:
            try:
                executor: BaseStepExecutor = StepExecutorFactory.create_executor(child, self.context)
                child_result = await executor.execute()
                if child_result is not None:
                    results.append(child_result)
            except Exception as e:
                case_id: Optional[int] = child.case_id
                step_id: Optional[int] = child.step_id
                step_no: Optional[int] = child.step_no
                step_code: Optional[str] = child.step_code
                step_name: Optional[str] = child.step_name
                step_type: AutoTestStepType = child.step_type
                error_message: str = AutoTestToolService.format_step_error_message(step=child, exception=e, is_child_step=True)
                self.context.log(error_message, step_code=step_code)
                failed_result = StepExecutionResult(
                    case_id=case_id,
                    step_id=step_id,
                    step_no=step_no,
                    step_code=step_code,
                    step_name=step_name,
                    step_type=AutoTestStepType(step_type),
                    quote_case_id=child.quote_case_id,
                    success=False,
                    error=error_message,
                )
                results.append(failed_result)
        return results


class LoopStepExecutor(BaseStepExecutor):
    """
    循环结构执行器：根据loop_mode分派次数/列表/字典/条件循环，维护loop_index等会话变量并执行子步骤。
    """

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        校验循环模式与错误策略后，分派到对应的_execute_*_loop实现。

        :param result: 用于挂载子步骤结果与成败状态的执行结果对象
        :return: None
        """
        try:
            loop_mode_str = self.step.loop_mode
            if not loop_mode_str:
                raise StepExecutionError(
                    "【循环结构】请明确指定循环模式类型: \n\t"
                    "仅允许选择: 次数循环, 列表循环, 字典循环, 条件循环"
                )
            try:
                loop_mode = AutoTestLoopMode(loop_mode_str)
            except (ValueError, TypeError) as e:
                raise StepExecutionError(
                    f"【循环结构】循环模式{loop_mode_str}无效: \n\t"
                    f"仅允许选择: 次数循环、列表循环、字典循环、条件循环"
                ) from e
            on_error_str = self.step.loop_on_error
            if not on_error_str:
                raise StepExecutionError(
                    "【循环结构】请明确指定错误处理策略: \n\t"
                    "仅允许选择: 继续下一次循环, 中断循环, 停止整个用例执行"
                )
            try:
                on_error = AutoTestLoopErrorStrategy(on_error_str)
            except (ValueError, TypeError) as e:
                raise StepExecutionError(
                    f"【循环结构】错误处理策略{on_error_str}无效: \n\t"
                    f"仅允许选择: 继续下一次循环、中断循环、停止整个用例执行"
                ) from e

            if loop_mode == AutoTestLoopMode.COUNT:
                await self._execute_count_loop(result, on_error)
            elif loop_mode == AutoTestLoopMode.LIST:
                await self._execute_list_loop(result, on_error)
            elif loop_mode == AutoTestLoopMode.DICT:
                await self._execute_dict_loop(result, on_error)
            elif loop_mode == AutoTestLoopMode.CONDITION:
                await self._execute_condition_loop(result, on_error)
            else:
                raise StepExecutionError(
                    f"【循环结构】循环模式[{loop_mode_str}]无效: \n\t"
                    f"仅允许选择: 次数循环, 列表循环, 字典循环, 条件循环"
                )
        except StepExecutionError:
            raise
        except Exception as e:
            result.success = False
            result.error = AutoTestToolService.format_step_error_message(step=self.step, exception=e, is_child_step=False)
            self.context.log(result.error, step_code=self.step_code)
            raise StepExecutionError(result.error) from e

    async def _execute_count_loop(self, result: StepExecutionResult, on_error: AutoTestLoopErrorStrategy) -> None:
        """
        次数循环模式，根据loop_maximums 执行固定次数循环，可选loop_interval间隔；超100次强制终止。

        :param result: 用于挂载子步骤结果的StepExecutionResult
        :param on_error: 子步骤失败时的策略（继续/中断/停止用例）
        :return: None
        """
        loop_maximums = self.step.loop_maximums
        if not loop_maximums:
            raise StepExecutionError("【循环结构】次数循环模式不允许loop_maximums参数为空")

        loop_interval = self.step.loop_interval
        guard_limit = 100

        self.context.log(f"【循环结构】次数循环开始: 最大循环次数: {loop_maximums}", step_code=self.step_code)
        for iteration in range(1, loop_maximums + 1):
            if self.step_code:
                self.context.step_cycle_index[self.step_code] = iteration
            self.context.log(f"【循环结构】次数循环: 第{iteration}/{loop_maximums}次执行", step_code=self.step_code)
            self.context.update_variables(
                [StepVariablesBase(key="loop_index", value=iteration, desc="")],
                scope="session_variables",
            )
            for child in self.children:
                child_code = child.step_code
                if child_code:
                    self.context.step_cycle_index[child_code] = iteration
            try:
                child_results = await self._execute_children()
                for child in child_results:
                    result.append_child(child)
                    if not child.success:
                        result.success = False
                        if on_error == AutoTestLoopErrorStrategy.STOP:
                            raise StepExecutionError(
                                f"【循环结构】子步骤执行失败(错误处理策略: 停止整个用例执行)\n\t"
                                f"错误描述: {child.error!r}"
                            )
                        elif on_error == AutoTestLoopErrorStrategy.BREAK:
                            self.context.log(
                                f"【循环结构】子步骤执行失败(错误处理策略: 中断循环)\n\t"
                                f"错误描述: {child.error!r}",
                                step_code=self.step_code
                            )
                            return
                        elif on_error == AutoTestLoopErrorStrategy.CONTINUE:
                            self.context.log(
                                f"【循环结构】子步骤执行失败(错误处理策略: 继续下一次循环)\n\t"
                                f"错误描述: {child.error!r}",
                                step_code=self.step_code
                            )
                            pass
            except StepExecutionError:
                if on_error == AutoTestLoopErrorStrategy.STOP:
                    raise
                elif on_error == AutoTestLoopErrorStrategy.BREAK:
                    return
                elif on_error == AutoTestLoopErrorStrategy.CONTINUE:
                    pass
            except Exception as e:
                error_message = f"【循环结构】次数循环: 第{iteration}次执行失败, \n\t错误描述: {e}"
                self.context.log(error_message, step_code=self.step_code)
                result.success = False
                if on_error == AutoTestLoopErrorStrategy.STOP:
                    raise StepExecutionError(error_message) from e
                elif on_error == AutoTestLoopErrorStrategy.BREAK:
                    return

            if iteration < loop_maximums and loop_interval and loop_interval > 0:
                await self.context.sleep(loop_interval)

            if iteration > guard_limit:
                raise StepExecutionError(
                    f"【循环结构】循环次数超过最大限制{guard_limit}次: \n\t"
                    f"已执行 {iteration} 次, 疑似无限循环, 为保护系统安全已自动终止循环"
                )

        self.context.log(f"【循环结构】次数循环结束: 共执行{loop_maximums}次", step_code=self.step_code)

    async def _execute_list_loop(self, result: StepExecutionResult, on_error: AutoTestLoopErrorStrategy) -> None:
        """
        列表循环模式，对可迭代对象（变量或 JSON 数组）逐项执行子步骤。
        会话变量固定为loop_index（从 1 起的序号）、loop_value（当前项）

        :param result: 用于挂载子步骤结果的StepExecutionResult
        :param on_error: 子步骤失败时的策略（继续/中断/停止用例）
        :return: None
        """
        loop_iterable = self.step.loop_iterable
        if not loop_iterable:
            raise StepExecutionError("【循环结构】列表循环模式下参数[loop_iterable]不允许为空")

        index_var_name = "loop_index"
        value_var_name = "loop_value"
        start_index = 1
        loop_interval = self.step.loop_interval

        try:
            iterable_obj = self.parse_iterable_source(loop_iterable)
            # 验证是否为可迭代对象（排除字符串和字节）
            if isinstance(iterable_obj, (str, bytes)) or not hasattr(iterable_obj, "__iter__"):
                raise StepExecutionError(
                    f"【循环结构】参数异常: \n\t"
                    f"预期类型: List[...] | Tuple[...] 等可迭代对象\n\t"
                    f"当前类型: {type(iterable_obj).__name__}"
                )
            # 转换为列表以便索引
            iterable_list = list(iterable_obj)
            total_items = len(iterable_list)
            if total_items == 0:
                self.context.log("【循环结构】列表循环: 可迭代对象为空, 跳过循环", step_code=self.step_code)
                return
            self.context.log(
                f"【循环结构】列表循环开始: \n\t"
                f"迭代长度: {total_items}\n\t"
                f"索引变量: {index_var_name}\n\t"
                f"数据变量: {value_var_name}",
                step_code=self.step_code
            )
            for idx, item in enumerate(iterable_list, start=start_index):
                # 记录循环次数
                if self.step_code:
                    self.context.step_cycle_index[self.step_code] = idx
                self.context.log(
                    f"【循环结构】列表循环: \n\t"
                    f"第{idx}/{total_items}次执行\n\t"
                    f"数据: {item!r}",
                    step_code=self.step_code
                )
                self.context.update_variables(
                    [
                        StepVariablesBase(key=index_var_name, value=idx, desc=""),
                        StepVariablesBase(key=value_var_name, value=item, desc=""),
                    ],
                    scope="session_variables",
                )
                # 为子步骤记录当前循环次数
                for child in self.children:
                    child_code = child.step_code
                    if child_code:
                        self.context.step_cycle_index[child_code] = idx
                try:
                    child_results = await self._execute_children()
                    for child in child_results:
                        result.append_child(child)
                        if not child.success:
                            result.success = False
                            if on_error == AutoTestLoopErrorStrategy.STOP:
                                raise StepExecutionError(
                                    f"【循环结构】子步骤执行失败(错误处理策略: 停止整个用例执行)\n\t"
                                    f"错误描述: {child.error!r}"
                                )
                            elif on_error == AutoTestLoopErrorStrategy.BREAK:
                                self.context.log(
                                    f"【循环结构】子步骤执行失败(错误处理策略: 中断循环)\n\t"
                                    f"错误描述: {child.error!r}",
                                    step_code=self.step_code
                                )
                                return
                            elif on_error == AutoTestLoopErrorStrategy.CONTINUE:
                                self.context.log(
                                    f"【循环结构】子步骤执行失败(错误处理策略: 继续下一次循环)\n\t"
                                    f"错误描述: {child.error!r}",
                                    step_code=self.step_code
                                )
                except StepExecutionError:
                    if on_error == AutoTestLoopErrorStrategy.STOP:
                        raise
                    elif on_error == AutoTestLoopErrorStrategy.BREAK:
                        return
                except Exception as e:
                    error_message = f"【循环结构】列表循环: \n\t第{idx}次执行失败: {e}"
                    self.context.log(error_message, step_code=self.step_code)
                    result.success = False
                    if on_error == AutoTestLoopErrorStrategy.STOP:
                        raise StepExecutionError(error_message) from e
                    elif on_error == AutoTestLoopErrorStrategy.BREAK:
                        return

                if idx < total_items and loop_interval and loop_interval > 0:
                    await self.context.sleep(loop_interval)

            self.context.log(f"【循环结构】列表循环结束: 共执行{total_items}次", step_code=self.step_code)

        except StepExecutionError:
            raise
        except Exception as e:
            raise StepExecutionError(f"【循环结构】列表循环执行异常: {e}") from e

    async def _execute_dict_loop(self, result: StepExecutionResult, on_error: AutoTestLoopErrorStrategy) -> None:
        """
        字典循环模式，对字典逐 (key, value) 执行子步骤。
        会话变量固定为loop_index（从 1 起的序号）、loop_key、loop_value

        :param result: 用于挂载子步骤结果的StepExecutionResult
        :param on_error: 子步骤失败时的策略（继续/中断/停止用例）
        :return: None
        """
        loop_iterable = self.step.loop_iterable
        if not loop_iterable:
            raise StepExecutionError("【循环结构】字典循环模式下参数[loop_iterable]不允许为空")

        index_var_name = "loop_index"
        key_var_name = "loop_key"
        value_var_name = "loop_value"
        start_index = 1
        loop_interval = self.step.loop_interval

        try:
            # 解析字典对象来源
            dict_obj = self.parse_iterable_source(loop_iterable)
            # 验证是否为字典
            if not isinstance(dict_obj, dict):
                raise StepExecutionError(
                    f"【循环结构】字典循环模式: \n\t"
                    f"预期类型: Dict[str, Any]\n\t"
                    f"实际类型: {type(dict_obj).__name__}"
                )
            total_items = len(dict_obj)
            if total_items == 0:
                self.context.log("【循环结构】字典循环: 字典对象为空, 跳过循环", step_code=self.step_code)
                return

            self.context.log(
                f"【循环结构】字典循环开始: \n\t"
                f"字典键数量: {total_items}\n\t"
                f"索引变量: {index_var_name}\n\t"
                f"键变量: {key_var_name}\n\t"
                f"值变量: {value_var_name}",
                step_code=self.step_code
            )
            for idx, (key, value) in enumerate(dict_obj.items(), start=start_index):
                # 记录循环次数
                if self.step_code:
                    self.context.step_cycle_index[self.step_code] = idx
                self.context.log(
                    f"【循环结构】字典循环: \n\t"
                    f"第{idx}/{total_items}次执行\n\t"
                    f"键={key}\n\t"
                    f"值={value}",
                    step_code=self.step_code
                )
                self.context.update_variables(
                    [
                        StepVariablesBase(key=index_var_name, value=idx, desc=""),
                        StepVariablesBase(key=key_var_name, value=key, desc=""),
                        StepVariablesBase(key=value_var_name, value=value, desc=""),
                    ],
                    scope="session_variables",
                )
                # 为子步骤记录当前循环次数
                for child in self.children:
                    child_code = child.step_code or (str(child.step_id) if child.step_id is not None else "")
                    if child_code:
                        self.context.step_cycle_index[child_code] = idx

                try:
                    child_results = await self._execute_children()
                    for child in child_results:
                        result.append_child(child)
                        if not child.success:
                            result.success = False
                            if on_error == AutoTestLoopErrorStrategy.STOP:
                                raise StepExecutionError(
                                    f"【循环结构】子步骤执行失败(错误处理策略: 停止整个用例执行)\n\t"
                                    f"错误描述: {child.error!r}"
                                )
                            elif on_error == AutoTestLoopErrorStrategy.BREAK:
                                self.context.log(
                                    f"【循环结构】子步骤执行失败(错误处理策略: 中断循环)\n\t"
                                    f"错误描述: {child.error!r}",
                                    step_code=self.step_code
                                )
                                return
                            elif on_error == AutoTestLoopErrorStrategy.CONTINUE:
                                self.context.log(
                                    f"【循环结构】子步骤执行失败(错误处理策略: 继续下一次循环)\n\t"
                                    f"错误描述: {child.error!r}",
                                    step_code=self.step_code
                                )
                except StepExecutionError:
                    if on_error == AutoTestLoopErrorStrategy.STOP:
                        raise
                    elif on_error == AutoTestLoopErrorStrategy.BREAK:
                        return
                except Exception as e:
                    error_message = f"【循环结构】字典循环: \n\t第{idx}次执行失败: {e}"
                    self.context.log(error_message, step_code=self.step_code)
                    result.success = False
                    if on_error == AutoTestLoopErrorStrategy.STOP:
                        raise StepExecutionError(error_message) from e
                    elif on_error == AutoTestLoopErrorStrategy.BREAK:
                        return

                if idx < total_items and loop_interval and loop_interval > 0:
                    await self.context.sleep(loop_interval)

            self.context.log(f"【循环结构】字典循环结束: 共执行{total_items}次", step_code=self.step_code)

        except StepExecutionError:
            raise
        except Exception as e:
            raise StepExecutionError(f"【循环结构】字典循环执行异常: {e}") from e

    async def _execute_condition_loop(self, result: StepExecutionResult, on_error: AutoTestLoopErrorStrategy) -> None:
        """
        条件循环：while语义每轮先根据conditions判断是否继续；仅当条件满足时才执行子步骤，
        再进入间隔与下一轮判断。条件一开始就不满足时，子步骤一轮都不会执行。
        超时、条件评估异常、或子步骤根据策略中断时退出；最多100轮（每轮一次子步骤树）防死循环。

        约定：conditions与ConditionsBase一致（condition_expr/condition_compare/condition_value），
        经compare_assertion评估；返回True表示继续循环，返回 False 表示结束循环。

        :param result: 用于挂载子步骤结果的StepExecutionResult
        :param on_error: 子步骤失败时的策略（继续/中断/停止用例）
        :return: None
        """
        condition = self.step.conditions
        if not condition:
            raise StepExecutionError("【循环结构】条件循环模式下参数[conditions]不允许为空")

        loop_timeout = self.step.loop_timeout
        loop_interval = self.step.loop_interval

        # iteration：实际执行子步骤树的轮数（与 loop_index、防死循环计数一致）
        iteration = 0
        guard_limit = 100
        should_continue = True
        start_time = time.time()
        self.context.log(
            f"【循环结构】条件循环开始: \n\t"
            f"循环超时时间配置: {loop_timeout}s",
            step_code=self.step_code
        )
        while should_continue:
            if loop_timeout and loop_timeout > 0:
                elapsed = time.time() - start_time
                if elapsed >= loop_timeout:
                    self.context.log(
                        f"【循环结构】条件循环超时: \n\t"
                        f"已累计执行子步骤: {iteration}轮\n\t"
                        f"当前耗时: {elapsed:.2f}s\n\t"
                        f"最大时间: {loop_timeout}s",
                        step_code=self.step_code
                    )
                    break

            # 先评估条件：不满足则不再执行本轮子步骤（while语义）
            try:
                if not self.evaluate_condition(condition):
                    self.context.log(
                        f"【循环结构】条件不满足, 结束循环: \n\t"
                        f"本轮不执行子步骤, 已累计执行子步骤: {iteration}轮",
                        step_code=self.step_code,
                    )
                    break
            except Exception as e:
                result.success = False
                error_message = f"【循环结构】条件评估失败: {e}"
                result.error = error_message
                self.context.log(error_message, step_code=self.step_code)
                should_continue = False
                break

            iteration += 1
            if self.step_code:
                self.context.step_cycle_index[self.step_code] = iteration
            self.context.log(
                f"【循环结构】条件循环: 第{iteration}轮(条件已满足, 开始执行子步骤)",
                step_code=self.step_code,
            )
            self.context.update_variables(
                [StepVariablesBase(key="loop_index", value=iteration, desc="")],
                scope="session_variables",
            )
            for child in self.children:
                child_code = child.step_code or (str(child.step_id) if child.step_id is not None else "")
                if child_code:
                    self.context.step_cycle_index[child_code] = iteration
            try:
                child_results = await self._execute_children()
                for child in child_results:
                    result.append_child(child)
                    if not child.success:
                        result.success = False
                        if on_error == AutoTestLoopErrorStrategy.STOP:
                            raise StepExecutionError(
                                f"【循环结构】子步骤执行失败(错误处理策略: 停止整个用例执行)\n\t"
                                f"错误描述: {child.error!r}"
                            )
                        elif on_error == AutoTestLoopErrorStrategy.BREAK:
                            self.context.log(
                                f"【循环结构】子步骤执行失败(错误处理策略: 中断循环)\n\t"
                                f"错误描述: {child.error!r}",
                                step_code=self.step_code
                            )
                            return
                        elif on_error == AutoTestLoopErrorStrategy.CONTINUE:
                            self.context.log(
                                f"【循环结构】子步骤执行失败(错误处理策略: 继续下一次循环)\n\t"
                                f"错误描述: {child.error!r}",
                                step_code=self.step_code
                            )
                            pass
            except StepExecutionError:
                if on_error == AutoTestLoopErrorStrategy.STOP:
                    raise
                elif on_error == AutoTestLoopErrorStrategy.BREAK:
                    should_continue = False
                    break
                elif on_error == AutoTestLoopErrorStrategy.CONTINUE:
                    pass
            except Exception as e:
                error_message = f"【循环结构】条件循环: 第{iteration}轮执行子步骤失败: {e}"
                self.context.log(error_message, step_code=self.step_code)
                result.success = False
                if on_error == AutoTestLoopErrorStrategy.STOP:
                    raise StepExecutionError(error_message) from e
                elif on_error == AutoTestLoopErrorStrategy.BREAK:
                    should_continue = False
                    break

            if not should_continue:
                break

            if iteration > guard_limit:
                raise StepExecutionError(
                    f"【循环结构】循环次数超过最大限制{guard_limit}次: \n\t"
                    f"已累计执行子步骤{iteration}轮, 疑似无限循环, 为保护系统安全已自动终止循环"
                )

            if loop_interval and loop_interval > 0:
                await self.context.sleep(loop_interval)

        self.context.log(
            f"【循环结构】条件循环结束: 共执行子步骤 {iteration} 轮",
            step_code=self.step_code,
        )

    def evaluate_condition(self, condition: ConditionsBase) -> bool:
        """
        评估条件是否成立；condition为ConditionsBase模型实例。

        :param condition: 待评估的条件模型
        :return: 条件成立返回 True，否则False
        """
        condition_expr = condition.condition_expr
        condition_compare = condition.condition_compare
        condition_value = condition.condition_value
        if condition_expr is None or condition_compare is None:
            raise StepExecutionError(
                f"【循环结构】条件缺少必要字段: \n\t"
                f"条件表达式: {condition_expr!r}\n\t"
                f"条件操作符: {condition_compare!r}"
            )
        try:
            resolved = self.context.resolve_placeholders(variables=condition_expr, step_code=self.step_code)
            if isinstance(resolved, str) and resolved.startswith("${") and resolved.endswith("}"):
                variable_name = resolved[2:-1]
                try:
                    actual_value = self.context.get_variable(variable_name)
                except KeyError as e:
                    raise StepExecutionError(f"【循环结构】条件表达式中变量未定义: {variable_name}") from e
            else:
                actual_value = resolved
        except Exception as e:
            if isinstance(e, StepExecutionError):
                raise
            raise StepExecutionError(f"【循环结构】条件表达式中占位符解析异常, 错误描述: {e}") from e
        try:
            return AutoTestToolService.compare_assertion(actual_value, condition_compare, condition_value)
        except ValueError as e:
            raise StepExecutionError(f"【循环结构】条件表达式执行异常, 错误描述: {e}") from e

    def parse_iterable_source(self, source: Any) -> Any:
        """
        解析循环数据源：先做占位符替换，再根据变量名、JSON字符串或原值得到可迭代对象。

        :param source: 数据源，可为${var}、JSON字符串或已解析对象
        :return: 可迭代对象（如 list、dict）
        """
        try:
            # 占位符解析后再解析${var} 或JSON字面量
            resolved_source = self.context.resolve_placeholders(variables=source, step_code=self.step_code)
            # 如果是字符串且以 ${ 开头，尝试获取变量
            if isinstance(resolved_source, str) and resolved_source.startswith("${") and resolved_source.endswith("}"):
                variable_name = resolved_source[2:-1]
                obj = self.context.get_variable(variable_name)
            elif isinstance(resolved_source, str):
                # 尝试解析JSON字符串
                try:
                    obj = orjson.loads(resolved_source)
                except (orjson.JSONDecodeError, ValueError):
                    # 如果不是JSON，作为普通字符串处理
                    obj = resolved_source
            else:
                obj = resolved_source
            return obj
        except StepExecutionError:
            raise
        except Exception as e:
            raise StepExecutionError(f"【循环结构】解析可迭代对象来源失败: {e}") from e


class ConditionStepExecutor(BaseStepExecutor):
    """
    条件分支执行器：根据 branch_items 顺序评估 if/elif/else，命中第一个即执行其子步骤。

    所有分支均未命中且无 else 时本步 success 仍为 True；子步骤失败不向上传递。
    """

    def _evaluate_branch_condition(self, condition: ConditionsBase) -> bool:
        condition_expr = condition.condition_expr
        condition_compare = condition.condition_compare
        condition_value = condition.condition_value
        if condition_expr is None or condition_compare is None:
            raise StepExecutionError(
                f"【条件分支】条件缺少必要字段: \n\t"
                f"条件表达式: {condition_expr!r}\n\t"
                f"条件操作符: {condition_compare!r}"
            )
        try:
            resolved = self.context.resolve_placeholders(variables=condition_expr, step_code=self.step_code)
            if isinstance(resolved, str) and resolved.startswith("${") and resolved.endswith("}"):
                variable_name = resolved[2:-1]
                try:
                    actual_value = self.context.get_variable(variable_name)
                except KeyError as e:
                    raise StepExecutionError(f"【条件分支】条件表达式中变量未定义: {variable_name}") from e
            else:
                actual_value = resolved
        except Exception as e:
            if isinstance(e, StepExecutionError):
                raise
            raise StepExecutionError(f"【条件分支】条件表达式占位符解析异常, 错误详情: {e}") from e
        try:
            return AutoTestToolService.compare_assertion(actual_value, condition_compare, condition_value)
        except ValueError as e:
            raise StepExecutionError(f"【条件分支】条件表达式执行异常, 错误描述: {e}") from e

    async def _execute_branch_children(self, branch_children: List[AutoTestStepTreeUpdateItem]) -> List[StepExecutionResult]:
        results: List[StepExecutionResult] = []
        for child in sorted(branch_children, key=lambda item: (item.step_no or 0)):
            try:
                executor: BaseStepExecutor = StepExecutorFactory.create_executor(child, self.context)
                child_result = await executor.execute()
                if child_result is not None:
                    results.append(child_result)
            except Exception as e:
                error_message: str = AutoTestToolService.format_step_error_message(step=child, exception=e, is_child_step=True)
                self.context.log(error_message, step_code=self.step_code)
                failed_result = StepExecutionResult(
                    case_id=child.case_id,
                    step_id=child.step_id,
                    step_no=child.step_no,
                    step_code=child.step_code,
                    step_name=child.step_name,
                    step_type=AutoTestStepType(child.step_type),
                    quote_case_id=child.quote_case_id,
                    success=False,
                    error=error_message,
                )
                results.append(failed_result)
        return results

    async def _execute(self, result: StepExecutionResult) -> None:
        try:
            branch_items = self.step.branch_items
            if not branch_items:
                raise StepExecutionError("【条件分支】参数异常: branch_items 为空，条件分支步骤必须配置 branch_items")

            result.request = {"branch_items": [
                {
                    "branch_type": b.branch_type,
                    "branch_conditions": b.branch_conditions.model_dump() if b.branch_conditions else None,
                    "branch_desc": b.branch_desc,
                }
                for b in branch_items
            ]}

            for i, branch in enumerate(branch_items):
                if branch.branch_type == "else":
                    matched = True
                else:
                    if not branch.branch_conditions:
                        raise StepExecutionError(f"【条件分支】第{i + 1}个分支({branch.branch_type})缺少 branch_conditions")
                    matched = self._evaluate_branch_condition(branch.branch_conditions)

                if matched:
                    desc = branch.branch_desc or branch.branch_type
                    result.success = True
                    result.message = f"【条件分支】命中分支[{branch.branch_type}]: {desc}"
                    self.context.log(result.message, step_code=self.step_code)
                    try:
                        branch_children = branch.branch_children or []
                        child_results = await self._execute_branch_children(branch_children)
                        for child in child_results:
                            result.append_child(child)
                    except Exception as e:
                        result.success = False
                        error_message: str = f"【条件分支】执行分支[{branch.branch_type}]子步骤失败: {e}"
                        result.error = error_message
                        self.context.log(error_message, step_code=self.step_code)
                    return

            result.success = True
            result.message = "【条件分支】所有分支均未命中，跳过执行"
            self.context.log(result.message, step_code=self.step_code)
        except Exception as e:
            result.success = False
            result.error = AutoTestToolService.format_step_error_message(step=self.step, exception=e, is_child_step=False)
            self.context.log(result.error, step_code=self.step_code)


class PythonStepExecutor(BaseStepExecutor):
    """
    Python 代码步骤执行器：执行code，将返回的dict/list写入extract_variables与response；断言仅支持变量池。
    """

    @staticmethod
    def _pack_python_executive_result(
            executive_result: Union[Dict[str, Any], List[Dict[Any, Any]]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        将 Python 步骤返回值转为提取项与变量池增量。

        Dict：各键写入变量池；List[Dict]：整体写入变量名 result。
        """
        if isinstance(executive_result, list):
            extract_item = {
                "name": "result",
                "source": "执行代码(Python)",
                "scope": "ALL",
                "expr": None,
                "index": None,
                "extract_value": executive_result,
                "success": True,
                "error": "",
            }
            return [extract_item], {"result": executive_result}
        extract_items = [
            {
                "name": k,
                "source": "执行代码(Python)",
                "scope": "ALL",
                "expr": None,
                "index": None,
                "extract_value": v,
                "success": True,
                "error": "",
            }
            for k, v in executive_result.items()
        ]
        return extract_items, dict(executive_result)

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        在沙箱中执行步骤代码，合并返回字典/列表并运行变量池断言。

        :param result: 本步执行结果
        :return: None
        """
        try:
            code = self.step.code
            if not code:
                raise StepExecutionError("【代码请求(Python)】缺少必要配置: code")
            try:
                executive_st_time: datetime = datetime.now()
                executive_result: Union[Dict[str, Any], List[Dict[Any, Any]]] = self.context.run_python_code(
                    code, namespace=self.context.clone_state(), step_result=result
                )
                executive_ed_time: datetime = datetime.now()
            except StepExecutionError:
                raise
            except Exception as e:
                raise StepExecutionError(AutoTestToolService.format_step_error_message(step=self.step, exception=e, is_child_step=False)) from e

            session_lookup_extra: Dict[str, Any] = {}
            if isinstance(executive_result, list) or executive_result:
                try:
                    extract_items, session_lookup_extra = self._pack_python_executive_result(executive_result)
                    result.extract_variables = extract_items
                    result.response = {
                        "response_body": executive_result,
                        "response_elapsed": f"{(executive_ed_time - executive_st_time).total_seconds():.3f}",
                    }
                except Exception as e:
                    raise StepExecutionError(f"【执行代码(Python)】提取结果失败: {e}") from e

            assert_validators = self.step.assert_validators
            if assert_validators:
                for valid in assert_validators:
                    if not isinstance(valid, StepAssertValidatorItem):
                        raise StepExecutionError(
                            f"【断言验证】子项参数异常: \n\t"
                            f"预期类型: StepAssertValidatorItem\n\t"
                            f"实际类型: {type(valid).__name__}"
                        )
                    if valid.source is None:
                        continue
                    source: str = str(valid.source).strip().lower()
                    if source not in {"session_variables", "变量池"}:
                        raise StepExecutionError(f"【代码请求(Python)】数据源源类型 {source} 不被允许")

                # 变量池快照：defined -> session -> 本步执行结果（后者优先级最高）
                self.apply_extract_and_assert(
                    result,
                    step_label="代码请求(Python)",
                    extract_variables=[],
                    assert_validators=assert_validators,
                    session_lookup_extra=session_lookup_extra,
                )
        except StepExecutionError:
            raise
        except Exception as e:
            result.success = False
            result.error = AutoTestToolService.format_step_error_message(step=self.step, exception=e, is_child_step=False)
            self.context.log(result.error, step_code=self.step_code)
            raise StepExecutionError(result.error) from e


class WaitStepExecutor(BaseStepExecutor):
    """
    等待步骤执行器：根据step.wait秒数调用context.sleep。
    """

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        根据 step.wait 指定的秒数挂起当前步骤。

        :param result: 本步执行结果（等待步骤通常不写入额外字段）
        :return: None
        """
        try:
            wait_seconds = self.step.wait
            if wait_seconds is None:
                raise StepExecutionError("【等待控制】缺少必要配置: wait")

            await self.context.sleep(wait_seconds)
        except StepExecutionError:
            raise
        except Exception as e:
            result.success = False
            result.error = AutoTestToolService.format_step_error_message(step=self.step, exception=e, is_child_step=False)
            self.context.log(result.error, step_code=self.step_code)
            raise StepExecutionError(result.error) from e


class AssertStepExecutor(BaseStepExecutor):
    """
    断言步骤执行器：按 assert_validators 执行断言，规则/比较符/管线与 HTTP 步骤断言对齐。

    独立断言步骤无请求/响应报文时，数据源通常为变量池（session_variables/变量池）；
    比较符复用 AutoTestAssertionOperation，经 StepAssertValidatorItem.operation 校验。
    """

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        执行步骤上的断言规则，失败项通过apply_extract_and_assert转为StepExecutionError。

        :param result: 本步执行结果
        :return: None
        """
        try:
            assert_validators = self.step.assert_validators
            if not assert_validators:
                raise StepExecutionError("【断言】缺少必要配置: assert_validators")
            for valid in assert_validators:
                if not isinstance(valid, StepAssertValidatorItem):
                    raise StepExecutionError(
                        f"【断言】子项参数异常: \n\t"
                        f"预期类型: StepAssertValidatorItem\n\t"
                        f"实际类型: {type(valid).__name__}"
                    )

            executive_st_time: datetime = datetime.now()
            # 与 HTTP 共用提取/断言管线；
            self.apply_extract_and_assert(
                result,
                step_label="断言",
                extract_variables=[],
                assert_validators=assert_validators,
            )
            executive_ed_time: datetime = datetime.now()
            result.response = {
                "assert_count": len(assert_validators),
                "assert_passed": sum(1 for item in result.assert_validators if item.get("success")),
                "assert_failed": sum(1 for item in result.assert_validators if not item.get("success")),
                "response_elapsed": f"{(executive_ed_time - executive_st_time).total_seconds():.3f}",
            }
        except StepExecutionError:
            raise
        except Exception as e:
            result.success = False
            result.error = AutoTestToolService.format_step_error_message(step=self.step, exception=e, is_child_step=False)
            self.context.log(result.error, step_code=self.step_code)
            raise StepExecutionError(result.error) from e


class UserVariablesStepExecutor(BaseStepExecutor):
    """
    用户变量步骤执行器：解析step.session_variables后合并到session_variables。
    """

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        解析step.session_variables中的占位符并合并到会话变量池。

        :param result: 本步执行结果
        :return: None
        """
        try:
            session_variables_raw: List[StepVariablesBase] = self.step.session_variables
            if not session_variables_raw:
                return
            session_variables_resolved: List[StepVariablesBase] = self.context.resolve_placeholders(session_variables_raw, step_code=self.step_code)
            if session_variables_resolved:
                self.context.update_variables(session_variables_resolved, scope="session_variables")
        except Exception as e:
            result.success = False
            result.error = AutoTestToolService.format_step_error_message(step=self.step, exception=e, is_child_step=False)
            self.context.log(result.error, step_code=self.step_code)
            raise StepExecutionError(result.error) from e


class QuoteCaseStepExecutor(BaseStepExecutor):
    """
    引用公共脚本执行器：加载引用用例根步骤树，根据step_no顺序执行并挂到result.children。

    本步step_is_skipped时由BaseStepExecutor.execute直接返回，不会进入本执行器。
    """

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        加载并执行引用用例的根步骤树；跳过的子步（execute 返回 None）不挂入children。

        :param result: 本步执行结果，子步骤结果写入children
        :return: None
        """
        previous_quote_case_id: Optional[int] = getattr(self.context, "executing_quote_case_id", None)
        try:
            quote_case_id = self.step.quote_case_id
            if not quote_case_id:
                raise StepExecutionError("【引用公共脚本】缺少必要配置: quote_case_id")

            database_crud_services = await self.get_services()
            # 将当前引用的公共脚本ID在步骤执行器上下文中标记，用于判断是否来自引用链
            self.context.executing_quote_case_id = quote_case_id
            try:
                quote_case_instance = await database_crud_services.case_curd.get_by_conditions(
                    only_one=True,
                    on_error=True,
                    id=quote_case_id,
                    case_type__in=[t.value for t in PUBLIC_CASE_TYPES],
                    state__not=1,
                )
            except (ParameterException, NotFoundException) as e:
                raise StepExecutionError(f"【引用公共脚本】引用用例ID: {quote_case_id}不存在\n\t错误描述: {e.message}") from e
            except Exception as e:
                raise StepExecutionError(f"【引用公共脚本】引用用例ID: {quote_case_id})查询异常\n\t错误描述: {e}") from e

            quote_case_dict = await quote_case_instance.to_dict(
                include_fields={"id", "case_code", "case_name"},
                replace_fields={"id": "case_id"}
            )
            quote_case_name: str = quote_case_dict["case_name"]
            try:
                load = await database_crud_services.step_curd.get_by_case_id(case_id=quote_case_id)
                quote_roots = load.root_steps
                if not quote_roots:
                    self.context.log(
                        f"【引用公共脚本】用例(id={quote_case_id})暂无任何可执行步骤数据",
                        step_code=self.step_code
                    )
                    return
            except Exception as e:
                raise StepExecutionError(
                    f"【引用公共脚本】获取用例(id={quote_case_id})步骤树数据异常, 错误描述: {e}"
                ) from e

            self.context.log(
                f"【引用公共脚本】执行用例(id={quote_case_id}, name={quote_case_name})开始",
                step_code=self.step_code
            )
            ordered_steps = sorted(
                [prepare_step_tree_item_for_execution(s) for s in quote_roots],
                key=lambda item: (item.step_no or 0),
            )
            for quote_step in ordered_steps:
                try:
                    executor = StepExecutorFactory.create_executor(quote_step, self.context)
                    child_result = await executor.execute()
                    if child_result is None:
                        continue
                    result.append_child(child_result)
                    if not child_result.success:
                        result.success = False
                except StepExecutionError:
                    raise
                except Exception as e:
                    case_id: Optional[int] = quote_step.case_id
                    step_id: Optional[int] = quote_step.step_id
                    step_no: Optional[int] = quote_step.step_no
                    step_code: Optional[str] = quote_step.step_code
                    step_name: Optional[str] = quote_step.step_name
                    st_enum = quote_step.step_type
                    error_message: str = AutoTestToolService.format_step_error_message(step=quote_step, exception=e, is_child_step=True)
                    self.context.log(error_message, step_code=step_code)
                    failed_result = StepExecutionResult(
                        case_id=case_id,
                        step_id=step_id,
                        step_no=step_no,
                        step_code=step_code,
                        step_name=step_name,
                        step_type=st_enum,
                        quote_case_id=quote_step.quote_case_id,
                        success=False,
                        error=error_message
                    )
                    result.append_child(failed_result)
            self.context.log(
                f"【引用公共脚本】执行用例(id={quote_case_id}, name={quote_case_name})结束",
                step_code=self.step_code
            )
        except StepExecutionError:
            raise
        except Exception as e:
            result.success = False
            result.error = AutoTestToolService.format_step_error_message(step=self.step, exception=e, is_child_step=False)
            self.context.log(result.error, step_code=self.step_code)
            raise StepExecutionError(result.error) from e
        finally:
            # 恢复上一级引用脚本标识（支持嵌套引用时的正确回退）
            try:
                self.context.executing_quote_case_id = previous_quote_case_id
            except Exception:
                pass


class TcpStepExecutor(BaseStepExecutor):
    """
    TCP 步骤执行器：复用HTTP步骤的「数据驱动替换 → 占位符解析 → 请求发送 → 变量提取 → 断言」链路。

    约定字段（沿用步骤基础字段，避免新增 schema 破坏兼容）：
        - request_url 为 TCP host（如 127.0.0.1 或域名）
        - request_port 为 TCP port（字符串或数字，范围 1~65535），二者均必填。
        - request_args_type 为 RAW 时发送 request_text（str/bytes），为 JSON 时发送 request_body（dict 或 JSON 字符串），其它或未配置时优先 request_text、否则 request_body。
        - 额外可选字段（不在 schema 中也可透传到 step dict）：
            - tcp_frame_mode 取 "length_prefix_json" 或 "raw"（对应 TcpFrameMode，默认 length_prefix_json）；
            - tcp_length_field_size 为长度前缀宽度（默认 8）；
            - tcp_encoding 为文本编码（默认 utf-8）；
            - tcp_connect_timeout 为连接超时秒数（float）；
            - tcp_read_timeout 为读写超时秒数（float）；
            - tcp_max_response_bytes 为最大响应体限制（默认 10MB）；
            - tcp_response_type 取 "json"、"xml"、"text" 或 "bytes"（默认 text，json/xml 失败会降级为 text）。
    """

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        解析执行环境与报文，发送TCP请求并完成变量提取与断言。

        :param result: 本步执行结果
        :return: None
        """
        try:
            env_name: Optional[str] = None
            request_url = (self.step.request_url or "").strip()
            request_port = self.step.request_port
            current_step_config: Optional[StepsExecuteConfigBase] = self.get_execute_config()
            if current_step_config:
                config_type: AutoTestConfigNodeType = current_step_config.config_type
                if current_step_config and config_type == AutoTestConfigNodeType.API:
                    request_url: str = current_step_config.config_host
                    request_port: str = current_step_config.config_port
                    self.step.request_config_name = current_step_config.config_name
                    env_name = current_step_config.env_name
            if not any((env_name, request_url, request_port)):
                error_message: str = f"【TCP请求】执行配置异常, 存在未明确项"
                raise StepExecutionError(error_message)
            if not request_url or not request_port:
                raise StepExecutionError(f"【TCP请求】请求主机[{request_url!r}]或请求端口[{request_port!r}]不是有效的配置")

            # 参数化驱动：与HTTP步骤一致（当存在 dataset_name 且不是引用公共脚本时）
            dataset_name: Optional[str] = getattr(self.context, "dataset_name", None)
            executing_quote_case_id: Optional[int] = getattr(self.context, "executing_quote_case_id", None)
            step_struct = await AutoTestToolService.load_dataset_for_request_step(
                case_id=self.case_id,
                step_code=self.step_code,
                dataset_name=dataset_name,
                executing_quote_case_id=executing_quote_case_id,
            )
            result.dataset_snapshot = step_struct
            result.dataset_name = dataset_name

            request_project_id: Optional[int] = self.step.request_project_id
            request_config_name: Optional[str] = self.step.request_config_name
            if not request_project_id:
                raise StepExecutionError("【TCP请求】参数[request_project_id]不能为空")
            if not request_config_name:
                raise StepExecutionError("【TCP请求】参数[request_config_name]不能为空")

            request_body = AutoTestToolService.try_serialize_request_body(self.step.request_body)
            request_text = self.step.request_text
            if AutoTestToolService.has_dataset_payload(step_struct):
                # 根据request_args_type优先判断报文类型，未明确类型时根据内容嗅探
                text_for_detect = request_text if isinstance(request_text, str) else ""
                if self.step.request_args_type == AutoTestReqArgsType.XML:
                    is_xml = True
                elif self.step.request_args_type == AutoTestReqArgsType.JSON:
                    is_xml = False
                else:
                    is_xml = text_for_detect.strip().startswith("<")
                if is_xml:
                    xml_source = request_text or (request_body if isinstance(request_body, str) else None)
                    request_text = AutoTestToolService.replace_xml_datagram(
                        body_map=step_struct.get("body") or {},
                        request_text=xml_source,
                    )
                else:
                    body_for_replace = request_body
                    if (
                            body_for_replace is None
                            or body_for_replace == {}
                            or body_for_replace == ""
                    ) and isinstance(request_text, str):
                        stripped = request_text.strip()
                        if stripped.startswith(("{", "[")):
                            try:
                                body_for_replace = orjson.loads(request_text)
                            except (orjson.JSONDecodeError, ValueError, TypeError):
                                body_for_replace = request_body
                    out = AutoTestToolService.replace_json_datagram(
                        head_map=step_struct.get("head") or {},
                        body_map=step_struct.get("body") or {},
                        request_headers=None,
                        request_body=body_for_replace,
                        form_data=None,
                        urlencoded=None,
                    )
                    request_body = out["request_body"]
                    if isinstance(request_body, (dict, list)):
                        request_text = orjson.dumps(request_body).decode("UTF-8")
                    elif isinstance(request_body, str) and request_body:
                        request_text = request_body

            request_body = self.context.resolve_placeholders(
                variables=request_body,
                step_code=self.step_code
            )
            text_after_ds = request_text if isinstance(request_text, str) else ""
            use_xml_placeholders = (
                    self.step.request_args_type == AutoTestReqArgsType.XML
                    or text_after_ds.strip().startswith("<")
            )
            if use_xml_placeholders and request_text:
                request_text = self.context.resolve_xml_placeholders(
                    xml_text=request_text,
                    step_code=self.step_code,
                )
            else:
                request_text = self.context.resolve_placeholders(
                    variables=request_text,
                    step_code=self.step_code
                )

            request_args_type_raw = self.step.request_args_type
            payload = select_tcp_payload(
                request_args_type_raw, request_text=request_text, request_body=request_body
            )

            # 写入result.request，便于落库与排障
            result.request = {
                "request_url": request_url,
                "request_port": request_port,
                "request_env_name": env_name,
                "request_args_type": request_args_type_raw,
                "tcp_frame_mode": self.step.tcp_frame_mode or "length_prefix_json",
                "tcp_length_field_size": self.step.tcp_length_field_size or 8,
                "tcp_encoding": self.step.tcp_encoding or "utf-8",
                "tcp_connect_timeout": self.step.tcp_connect_timeout,
                "tcp_read_timeout": self.step.tcp_read_timeout,
                "tcp_response_type": self.step.tcp_response_type or "text",
                "request_body": request_body,
                "request_text": request_text,
                "payload": payload,
            }

            frame_mode_raw = (self.step.tcp_frame_mode or "length_prefix_json").strip().lower()
            frame_mode = TcpFrameMode.RAW if frame_mode_raw == "raw" else TcpFrameMode.LENGTH_PREFIX_JSON

            length_field_size = self.step.tcp_length_field_size or 8
            encoding = self.step.tcp_encoding or "utf-8"
            max_response_bytes = self.step.tcp_max_response_bytes or (10 * 1024 * 1024)
            response_type = (self.step.tcp_response_type or "text").strip().lower()
            connect_td, read_td = parse_tcp_timeouts(
                self.step.tcp_connect_timeout, self.step.tcp_read_timeout
            )

            start = time.perf_counter()
            async with AioTcpClient(
                    timeout=read_td or timedelta(seconds=30),
                    connect_timeout=connect_td,
                    length_field_size=int(length_field_size),
                    max_response_bytes=int(max_response_bytes),
            ) as client:
                utils = await client.tcp(
                    request_url,
                    int(request_port),
                    payload,
                    frame_mode=frame_mode,
                    encoding=encoding,
                    connect_timeout=connect_td,
                    read_timeout=read_td,
                )
                # 只请求一次：获取原始字节后本地解析，避免解析失败时重发TCP请求
                resp_bytes = await utils.bytes_resp()
                parsed = parse_tcp_response(resp_bytes, encoding=encoding, response_type=response_type)
                resp_text = parsed.response_text
                response_json = parsed.response_json

            elapsed = round(time.perf_counter() - start, 6)
            result.response = {
                "response_text": resp_text,
                "response_elapsed": str(elapsed),
                "response_bytes": len(resp_bytes) if isinstance(resp_bytes, (bytes, bytearray)) else None,
            }

            request_json_for_extract, request_text_for_extract = resolve_tcp_request_extract_sources(
                request_body=request_body, request_text=request_text, payload=payload
            )
            self.apply_extract_and_assert(
                result,
                step_label="TCP请求",
                response_text=result.response.get("response_text") if result.response else None,
                response_json=response_json,
                request_text=request_text_for_extract,
                request_json=request_json_for_extract,
                step_struct=step_struct,
                body_source=tcp_body_source_for_assert(response_type),
            )
        except StepExecutionError:
            raise
        except Exception as e:
            result.success = False
            result.error = AutoTestToolService.format_step_error_message(step=self.step, exception=e, is_child_step=False)
            self.context.log(result.error, step_code=self.step_code)
            raise StepExecutionError(result.error) from e


class DataBaseStepExecutor(BaseStepExecutor):
    """
    数据库请求步骤：根据环境配置连接池执行多条SQL，解析占位符，结果写入变量池；支持查到即止。
    """

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        顺序执行database_operates中的SQL，合并提取结果与断言。

        :param result: 本步执行结果
        :return: None
        """
        try:
            merge_operates_env_name: Optional[str] = None
            database_operates: Optional[List[DataBaseOperates]] = self.step.database_operates
            if database_operates is None:
                raise StepExecutionError("【数据库请求】参数[database_operates]不能为空")
            if not isinstance(database_operates, list):
                raise StepExecutionError("【数据库请求】参数[database_operates]必须是列表类型")
            if not database_operates:
                raise StepExecutionError("【数据库请求】参数[database_operates]至少有一条数据库操作配置")
            mark_extract_variables: List[Dict[str, Any]] = []
            database_operates_request: List[Dict[str, Any]] = []
            database_operates_response: List[Dict[str, Any]] = []
            pool_manager: DBConnPoolFromConfig = get_app_database_pool()
            database_searched: bool = bool(self.step.database_searched)
            executive_st_time: datetime = datetime.now()
            # 步骤响应：列表，每项对应一条database_operates 执行结果（含 variable_name、sql_data、sql_count 等），供报告与「提取/断言」根据存储变量名匹配
            for db_idx, db_operate in enumerate(database_operates):
                # 清空env_name/config_host/config_port，避免循环内数据库操作相互污染
                env_name: Optional[str] = None
                config_host: Optional[str] = None
                config_port: Optional[str] = None
                operate_no: str = f"第{db_idx + 1}条数据库配置"
                if not isinstance(db_operate, DataBaseOperates):
                    raise StepExecutionError(
                        f"【数据库请求】第{operate_no}条配置类型非法: \n\t"
                        f"预期类型: DataBaseOperates\n\t"
                        f"实际类型: {type(db_operate).__name__}"
                    )
                current_op_execute_cfg: Optional[StepsExecuteConfigBase] = self.get_execute_config(database_operates_index=db_idx)
                if current_op_execute_cfg and current_op_execute_cfg.config_type == AutoTestConfigNodeType.DB:
                    env_name: str = str(current_op_execute_cfg.env_name or "").strip()
                    config_host: str = current_op_execute_cfg.config_host
                    config_port: str = current_op_execute_cfg.config_port
                    config_name: str = current_op_execute_cfg.config_name
                    database_name: str = current_op_execute_cfg.database_name
                    db_operate.config_name = config_name
                    db_operate.database_name = database_name
                    request_config_name: Optional[str] = self.step.request_config_name
                    if request_config_name:
                        self.step.request_config_name += f", ({db_idx}){db_operate.config_name}"
                    else:
                        self.step.request_config_name = f"({db_idx}){db_operate.config_name}"
                    if merge_operates_env_name:
                        merge_operates_env_name += f", ({db_idx}){env_name}"
                    else:
                        merge_operates_env_name = f"({db_idx}){env_name}"

                if not any((env_name, config_host, config_port)):
                    error_message: str = f"【数据库请求】{operate_no}：执行配置异常, 存在未明确项"
                    raise StepExecutionError(error_message)
                operate_name: str = db_operate.name
                operate_sql_expr: str = db_operate.expr
                operate_project_id: int = db_operate.project_id
                operate_project_name: str = db_operate.project_name
                operate_variable_name: str = db_operate.variable_name
                operate_config_name: str = db_operate.config_name
                operate_database_name: str = db_operate.database_name
                operate_desc: Optional[str] = db_operate.desc
                operate_result_count: str = f"{operate_variable_name}_count"
                try:
                    # 处理变量占位符
                    operate_sql_expr: str = self.context.resolve_placeholders(variables=operate_sql_expr, step_code=self.step_code)
                    operate_config_name: str = self.context.resolve_placeholders(variables=operate_config_name, step_code=self.step_code)
                    operate_project_name: str = self.context.resolve_placeholders(variables=operate_project_name, step_code=self.step_code)
                    operate_database_name: str = self.context.resolve_placeholders(variables=operate_database_name, step_code=self.step_code)
                    if not operate_project_id and operate_project_name.strip():
                        database_crud_services = await self.get_services()
                        project_instance = await database_crud_services.project_curd.get_by_name(operate_project_name.strip(), on_error=False)
                        if not project_instance:
                            raise StepExecutionError(f"【数据库请求】{operate_no}：应用(project_name={operate_project_name!r})不存在")
                        operate_project_id = project_instance.id
                    if not operate_project_id:
                        raise StepExecutionError(f"【数据库请求】{operate_no}：参数[project_id]不能为空")
                    if not operate_config_name:
                        raise StepExecutionError(f"【数据库请求】{operate_no}：参数[config_name]不能为空")
                    if not operate_database_name:
                        raise StepExecutionError(f"【数据库请求】{operate_no}：参数[database_name]不能为空")
                    if not operate_sql_expr:
                        raise StepExecutionError(f"【数据库请求】{operate_no}：参数[expr]不能为空")
                    if not operate_variable_name:
                        raise StepExecutionError(f"【数据库请求】{operate_no}：参数[variable_name]不能为空")

                    database_pool: Pool = await pool_manager.get_or_create_pool(
                        project_id=str(operate_project_id),
                        env_name=str(env_name).strip(),
                        config_name=operate_config_name,
                        database_name=operate_database_name,
                    )
                    expr_executive_result: Dict[str, Any] = await pool_manager.execute_sql(
                        pool=database_pool,
                        sql=operate_sql_expr,
                        result_as_dict=True,
                    )
                    sql_count: Optional[int] = None
                    sql_data: Optional[List[Dict[str, Any]]] = None
                    if isinstance(expr_executive_result, dict):
                        sql_data: List[Dict[str, Any]] = expr_executive_result.get("sql_data")
                        sql_count: int = expr_executive_result.get("sql_count")
                    mark_extract_variables.append({
                        "index": db_idx,
                        "name": operate_variable_name,
                        "source": "数据库请求",
                        "scope": "ALL",
                        "expr": "SQL语句",
                        "extract_value": sql_data,
                        "success": True,
                        "error": "",
                    })
                    mark_extract_variables.append({
                        "index": db_idx,
                        "name": operate_result_count,
                        "source": "数据库请求",
                        "scope": "ALL",
                        "expr": "SQL语句",
                        "extract_value": sql_count,
                        "success": True,
                        "error": "",
                    })
                    database_operates_request.append({
                        "index": db_idx,
                        "name": operate_name,
                        "env_name": env_name,
                        "expr": operate_sql_expr,
                        "project_id": operate_project_id,
                        "project_name": operate_project_name,
                        "variable_name": [operate_variable_name, operate_result_count],
                        "config_name": operate_config_name,
                        "database_name": operate_database_name,
                        "desc": operate_desc,
                    })
                    database_operates_response.append({
                        "index": db_idx,
                        "name": operate_name,
                        "variable_name": [operate_variable_name, operate_result_count],
                        "sql_meta": {
                            "env_name": env_name,
                            "project_id": operate_project_id,
                            "project_name": operate_project_name,
                            "config_name": operate_config_name,
                            "database_name": operate_database_name,
                            "config_host": config_host,
                            "config_port": config_port,
                        },
                        "sql_data": sql_data,
                        "sql_count": sql_count,
                    })
                    if database_searched and isinstance(sql_data, list) and len(sql_data) > 0:
                        self.context.log(
                            f"【数据库请求】查到即止：{operate_no}查询返回 {len(sql_data)} 行，已终止后续 SQL",
                            step_code=self.step_code,
                        )
                        break
                except StepExecutionError:
                    raise
                except Exception as e:
                    result.success = False
                    result.error = AutoTestToolService.format_step_error_message(
                        step=self.step,
                        exception=e,
                        is_child_step=False,
                        offset_message=operate_no
                    )
                    self.context.log(result.error, step_code=self.step_code)
                    database_operates_request.append({
                        "index": db_idx,
                        "name": operate_name,
                        "env_name": env_name,
                        "expr": operate_sql_expr,
                        "project_id": operate_project_id,
                        "project_name": operate_project_name,
                        "variable_name": [operate_variable_name, operate_result_count],
                        "config_name": operate_config_name,
                        "database_name": operate_database_name,
                        "desc": operate_desc,
                    })
                    database_operates_response.append({
                        "index": db_idx,
                        "name": operate_name,
                        "variable_name": [operate_variable_name, operate_result_count],
                        "sql_meta": {
                            "env_name": env_name,
                            "project_id": operate_project_id,
                            "project_name": operate_project_name,
                            "config_name": operate_config_name,
                            "database_name": operate_database_name,
                            "config_host": config_host,
                            "config_port": config_port,
                        },
                        "sql_data": None,
                        "sql_count": None,
                        "error": f"{operate_no}: {e}",
                    })

            executive_ed_time: datetime = datetime.now()
            response_text_str = orjson.dumps(database_operates_response, default=str).decode("UTF-8")
            result.extract_variables = mark_extract_variables
            result.request = {
                "database_operates": database_operates_request,
                "database_searched": database_searched,
                "request_args_type": AutoTestReqArgsType.RAW,
                "request_env_name": merge_operates_env_name,
            }
            result.response = {
                "response_body": database_operates_response,
                "response_text": response_text_str,
                "response_elapsed": f"{(executive_ed_time - executive_st_time).total_seconds():.3f}",
            }

            session_lookup_extra: Dict[str, Any] = {}
            for extract_item in mark_extract_variables:
                if isinstance(extract_item, dict) and extract_item.get("success") and extract_item.get("name") is not None:
                    session_lookup_extra[extract_item["name"]] = extract_item.get("extract_value")

            extract_variables: Optional[List[StepExtractVariableItem]] = self.step.extract_variables
            if extract_variables and not isinstance(extract_variables, list):
                raise StepExecutionError("【数据库请求】参数[extract_variables]必须是[List[Dict[str, Any]]]类型")
            self.apply_extract_and_assert(
                result,
                step_label="数据库请求",
                response_text=response_text_str,
                response_json=database_operates_response,
                extract_variables=extract_variables,
                session_lookup_extra=session_lookup_extra,
            )
        except StepExecutionError:
            raise
        except Exception as e:
            result.success = False
            result.error = AutoTestToolService.format_step_error_message(step=self.step, exception=e, is_child_step=False)
            self.context.log(result.error, step_code=self.step_code)
            raise StepExecutionError(result.error) from e


class RedisStepExecutor(BaseStepExecutor):
    """
    Redis请求步骤：根据环境配置连接Redis，顺序执行多条命令，解析占位符；支持查到即止。
    """

    @staticmethod
    def has_effective_redis_result(command_results: Optional[List[Any]]) -> bool:
        """
        判断Redis命令结果列表是否含有效数据（非空/非空白）。

        :param command_results: 命令返回值列表
        :return: 存在有效结果则为True
        """
        if not command_results:
            return False
        for result in command_results:
            if result is None:
                continue
            if isinstance(result, (list, tuple, dict)) and len(result) == 0:
                continue
            if isinstance(result, str) and not str(result).strip():
                continue
            return True
        return False

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        根据环境配置顺序执行redis_operates，解析占位符并写入结果；支持查到即止。

        :param result: 本步执行结果
        :return: None
        """
        try:
            merge_operates_env_name: Optional[str] = None
            redis_operates: Optional[List[RedisOperates]] = self.step.redis_operates
            if redis_operates is None:
                raise StepExecutionError("【Redis请求】参数[redis_operates]不能为空")
            if not isinstance(redis_operates, list):
                raise StepExecutionError("【Redis请求】参数[redis_operates]必须是列表类型")
            if not redis_operates:
                raise StepExecutionError("【Redis请求】参数[redis_operates]至少有一条Redis操作配置")

            redis_operates_request: List[Dict[str, Any]] = []
            redis_operates_response: List[Dict[str, Any]] = []
            mark_extract_variables: List[Dict[str, Any]] = []
            pool_manager: RedisConnPoolFromConfig = get_app_redis_pool()
            redis_searched: bool = bool(self.step.redis_searched)
            executive_st_time: datetime = datetime.now()

            for redis_idx, redis_operate in enumerate(redis_operates):
                env_name: Optional[str] = None
                config_host: Optional[str] = None
                config_port: Optional[str] = None
                operate_no: str = f"第{redis_idx + 1}条Redis配置"
                if not isinstance(redis_operate, RedisOperates):
                    raise StepExecutionError(
                        f"【Redis请求】{operate_no}配置类型非法: \n\t"
                        f"预期类型: RedisOperates\n\t"
                        f"实际类型: {type(redis_operate).__name__}"
                    )
                current_op_execute_cfg: Optional[StepsExecuteConfigBase] = self.get_execute_config(
                    database_operates_index=redis_idx
                )
                if current_op_execute_cfg and current_op_execute_cfg.config_type == AutoTestConfigNodeType.REDIS:
                    env_name = str(current_op_execute_cfg.env_name or "").strip()
                    config_host = current_op_execute_cfg.config_host
                    config_port = current_op_execute_cfg.config_port
                    config_name: str = current_op_execute_cfg.config_name
                    database_name: str = current_op_execute_cfg.database_name or redis_operate.database_name
                    redis_operate.config_name = config_name
                    redis_operate.database_name = database_name
                    request_config_name: Optional[str] = self.step.request_config_name
                    if request_config_name:
                        self.step.request_config_name += f", ({redis_idx}){redis_operate.config_name}"
                    else:
                        self.step.request_config_name = f"({redis_idx}){redis_operate.config_name}"
                    if merge_operates_env_name:
                        merge_operates_env_name += f", ({redis_idx}){env_name}"
                    else:
                        merge_operates_env_name = f"({redis_idx}){env_name}"

                if not any((env_name, config_host, config_port)):
                    raise StepExecutionError(f"【Redis请求】{operate_no}：执行配置异常, 存在未明确项")

                operate_name: str = redis_operate.name
                operate_expr: str = redis_operate.expr
                operate_project_id: int = redis_operate.project_id
                operate_project_name: str = redis_operate.project_name
                operate_variable_name: str = redis_operate.variable_name
                operate_config_name: str = redis_operate.config_name
                operate_database_name: str = redis_operate.database_name
                operate_desc: Optional[str] = redis_operate.desc
                operate_result_count: str = f"{operate_variable_name}_count"
                try:
                    operate_expr = self.context.resolve_placeholders(
                        variables=operate_expr,
                        step_code=self.step_code
                    )
                    operate_config_name = self.context.resolve_placeholders(
                        variables=operate_config_name,
                        step_code=self.step_code
                    )
                    operate_project_name = self.context.resolve_placeholders(
                        variables=operate_project_name,
                        step_code=self.step_code
                    )
                    operate_database_name = self.context.resolve_placeholders(
                        variables=operate_database_name,
                        step_code=self.step_code
                    )
                    operate_variable_name = self.context.resolve_placeholders(
                        variables=operate_variable_name,
                        step_code=self.step_code
                    )
                    operate_result_count = f"{operate_variable_name}_count"
                    if not operate_project_id and operate_project_name.strip():
                        database_crud_services = await self.get_services()
                        project_instance = await database_crud_services.project_curd.get_by_name(operate_project_name.strip(), on_error=False)
                        if not project_instance:
                            raise StepExecutionError(
                                f"【Redis请求】{operate_no}：应用(project_name={operate_project_name!r})不存在"
                            )
                        operate_project_id = project_instance.id
                    if not operate_project_id:
                        raise StepExecutionError(f"【Redis请求】{operate_no}：参数[project_id]不能为空")
                    if not operate_config_name:
                        raise StepExecutionError(f"【Redis请求】{operate_no}：参数[config_name]不能为空")
                    if not operate_database_name:
                        raise StepExecutionError(f"【Redis请求】{operate_no}：参数[database_name]不能为空")
                    if not operate_expr:
                        raise StepExecutionError(f"【Redis请求】{operate_no}：参数[expr]不能为空")
                    if not operate_variable_name:
                        raise StepExecutionError(f"【Redis请求】{operate_no}：参数[variable_name]不能为空")

                    redis_client = await pool_manager.get_or_create_client(
                        app_id=str(operate_project_id),
                        env=str(env_name).strip(),
                        config_name=operate_config_name,
                        db_name=operate_database_name,
                    )
                    expr_executive_result: Dict[str, Any] = await pool_manager.execute_commands(
                        client=redis_client,
                        expr=operate_expr,
                    )
                    redis_data: Optional[List[Any]] = expr_executive_result.get("redis_data")
                    redis_count: Optional[int] = expr_executive_result.get("redis_count")

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
                    self.context.log(
                        f"【Redis请求】{operate_no}：已自动写入变量池 "
                        f"variable_name={operate_variable_name}, {operate_result_count}={redis_count}",
                        step_code=self.step_code,
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
                    if redis_searched and self.has_effective_redis_result(redis_data):
                        self.context.log(
                            f"【Redis请求】查到即止：{operate_no}已返回有效结果，已终止后续命令",
                            step_code=self.step_code,
                        )
                        break
                except StepExecutionError:
                    raise
                except Exception as e:
                    result.success = False
                    result.error = AutoTestToolService.format_step_error_message(
                        step=self.step,
                        exception=e,
                        is_child_step=False,
                        offset_message=operate_no
                    )
                    self.context.log(result.error, step_code=self.step_code)
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
                        "error": f"{operate_no}: {e}",
                    })

            executive_ed_time: datetime = datetime.now()
            response_text_str = orjson.dumps(redis_operates_response, default=str).decode("UTF-8")
            result.extract_variables = mark_extract_variables
            result.request = {
                "redis_operates": redis_operates_request,
                "redis_searched": redis_searched,
                "request_args_type": AutoTestReqArgsType.RAW,
                "request_env_name": merge_operates_env_name,
            }
            result.response = {
                "response_body": redis_operates_response,
                "response_text": response_text_str,
                "response_elapsed": f"{(executive_ed_time - executive_st_time).total_seconds():.3f}",
            }

            session_lookup_extra: Dict[str, Any] = {}
            for extract_item in mark_extract_variables:
                if isinstance(extract_item, dict) and extract_item.get("success") and extract_item.get("name") is not None:
                    session_lookup_extra[extract_item["name"]] = extract_item.get("extract_value")

            extract_variables: Optional[List[StepExtractVariableItem]] = self.step.extract_variables
            if extract_variables and not isinstance(extract_variables, list):
                raise StepExecutionError("【Redis请求】参数[extract_variables]必须是[List[Dict[str, Any]]]类型")
            self.apply_extract_and_assert(
                result,
                step_label="Redis请求",
                response_text=response_text_str,
                response_json=redis_operates_response,
                extract_variables=extract_variables,
                session_lookup_extra=session_lookup_extra,
            )
        except StepExecutionError:
            raise
        except Exception as e:
            result.success = False
            result.error = AutoTestToolService.format_step_error_message(step=self.step, exception=e, is_child_step=False)
            self.context.log(result.error, step_code=self.step_code)
            raise StepExecutionError(result.error) from e


class HttpStepExecutor(BaseStepExecutor):
    """
    HTTP 步骤执行器：发请求、解析占位符、根据request_project_id取项目下环境补全 URL，并执行变量提取与断言。
    参数化驱动仅在此执行器内处理：根据dataset_name + case_id/step_code查AutoTestApiDataSourceInfo取数。
    """

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        拼装URL与报文，发送HTTP请求并完成变量提取与断言。

        :param result: 本步执行结果
        :return: None
        """
        try:
            request_url: str = (self.step.request_url or "").strip().lstrip("/")
            request_method: HTTPMethod = self.step.request_method
            current_step_config: Optional[StepsExecuteConfigBase] = self.get_execute_config()
            env_name: Optional[str] = None
            if current_step_config:
                if current_step_config.config_type == AutoTestConfigNodeType.API:
                    env_name = current_step_config.env_name
                    config_name: str = current_step_config.config_name
                    config_host: str = (current_step_config.config_host or "").strip().rstrip("/").rstrip(":")
                    config_port: str = (str(current_step_config.config_port).strip() if current_step_config.config_port else "")
                    self.step.request_config_name = config_name
                    if config_host and not config_host.lower().startswith(("http://", "https://")):
                        config_host = f"http://{config_host}"
                    request_url = (
                        f"{config_host}/{request_url}"
                        if not config_port
                        else f"{config_host}:{config_port}/{request_url}"
                    )

            if not request_url or not request_url.lower().startswith("http") or not env_name:
                raise StepExecutionError(f"【HTTP请求】URL[{request_url!r}]不是有效的HTTP/HTTPS地址或未明确执行环境")

            # 参数化驱动：根据 context.dataset_name + case_id/step_code 查 AutoTestApiDataSourceInfo 取该步骤数据集
            dataset_name: Optional[str] = getattr(self.context, "dataset_name", None)
            executing_quote_case_id: Optional[int] = getattr(self.context, "executing_quote_case_id", None)
            step_struct: Optional[Dict[str, Dict[str, Any]]] = await AutoTestToolService.load_dataset_for_request_step(
                case_id=self.case_id,
                step_code=self.step_code,
                dataset_name=dataset_name,
                executing_quote_case_id=executing_quote_case_id,
            )
            result.dataset_snapshot = step_struct
            result.dataset_name = dataset_name
            self.context.log(
                f"【HTTP请求】请求开始: \n\t"
                f"环境名称: {env_name}\n\t"
                f"应用ID: {self.step.request_project_id}\n\t"
                f"配置名称: {self.step.request_config_name}\n\t"
                f"请求方法: {request_method}\n\t"
                f"请求地址: {request_url}\n\t"
                f"参数类型: {self.step.request_args_type}\n\t"
                f"数据源名称: {dataset_name}"
            )
        except StepExecutionError:
            raise
        except Exception as e:
            raise StepExecutionError(f"【HTTP请求】请求配置或数据源处理时发生异常: {e}") from e

        try:
            # 先转成字典，再「先数据驱动替换、再变量占位符替换」，保证最终报文 = 数据驱动覆盖后再占位符替换
            # 1）转成字典（尚未解析占位符）
            request_header: Optional[Dict[str, Any]] = AutoTestToolService.convert_list_to_dict_for_http(self.step.request_header)
            request_params: Optional[Dict[str, Any]] = AutoTestToolService.convert_list_to_dict_for_http(self.step.request_params)
            request_form_data: Optional[Dict[str, Any]] = AutoTestToolService.convert_list_to_dict_for_http(self.step.request_form_data)
            request_form_urlencoded: Optional[Dict[str, Any]] = AutoTestToolService.convert_list_to_dict_for_http(self.step.request_form_urlencoded)
            request_form_file: Optional[Dict[str, Any]] = AutoTestToolService.convert_list_to_dict_for_http(self.step.request_form_file)
            request_body: Dict[str, Any] = AutoTestToolService.try_serialize_request_body(self.step.request_body)
            request_text: Optional[str] = self.step.request_text

            # 2）数据驱动：先替换报文（XML走XPath、其余走JSONPath），再占位符
            if AutoTestToolService.has_dataset_payload(step_struct):
                head_map = step_struct.get("head") or {}
                body_map = step_struct.get("body") or {}
                if self.step.request_args_type == AutoTestReqArgsType.XML:
                    out = AutoTestToolService.replace_json_datagram(
                        head_map=head_map,
                        body_map={},
                        request_headers=request_header,
                        request_body=None,
                        form_data=None,
                        urlencoded=None,
                    )
                    request_header = out["headers"]
                    request_text = AutoTestToolService.replace_xml_datagram(
                        body_map=body_map,
                        request_text=request_text,
                    )
                else:
                    out = AutoTestToolService.replace_json_datagram(
                        head_map=head_map,
                        body_map=body_map,
                        request_headers=request_header,
                        request_body=request_body,
                        form_data=request_form_data,
                        urlencoded=request_form_urlencoded,
                    )
                    request_header = out["headers"]
                    request_body = out["request_body"]
                    request_form_data = out["form_data"]
                    request_form_urlencoded = out["urlencoded"]

            # 3）再对报文做变量占位符解析
            request_header = self.context.resolve_placeholders(
                variables=request_header,
                step_code=self.step_code
            )
            request_params = self.context.resolve_placeholders(
                variables=request_params,
                step_code=self.step_code
            )
            request_form_data = self.context.resolve_placeholders(
                variables=request_form_data,
                step_code=self.step_code
            )
            request_form_urlencoded = self.context.resolve_placeholders(
                variables=request_form_urlencoded,
                step_code=self.step_code
            )
            request_body = self.context.resolve_placeholders(
                variables=request_body,
                step_code=self.step_code
            )
            if self.step.request_args_type == AutoTestReqArgsType.XML and request_text:
                request_text = self.context.resolve_xml_placeholders(
                    xml_text=request_text,
                    step_code=self.step_code,
                )
            else:
                request_text = self.context.resolve_placeholders(
                    variables=request_text,
                    step_code=self.step_code
                )

            json_payload: Optional[Any] = None
            file_payload: Optional[Any] = None
            data_payload: Optional[Any] = None
            content_payload: Optional[Any] = None
            # 根据request_args_type选取请求体类型，仅使用一种方式，避免冲突
            request_args_type: Optional[AutoTestReqArgsType] = self.step.request_args_type
            payloads = assemble_http_body_payloads(
                request_args_type,
                request_text=request_text,
                request_body=request_body,
                form_data=request_form_data,
                form_files=request_form_file,
                urlencoded=request_form_urlencoded,
                headers=request_header,
            )
            json_payload = payloads.json_payload
            data_payload = payloads.data_payload
            content_payload = payloads.content_payload
            file_payload = payloads.file_payload
            request_header = payloads.headers
            # 先写入实际发往目标服务器的数据，避免后续处理response异常时落库拿不到request
            result.request = {
                "request_url": request_url,
                "request_method": request_method.value,
                "request_env_name": env_name,
                "request_args_type": request_args_type,
                "request_header": request_header,
                "request_params": request_params,
                "request_form_data": request_form_data,
                "request_form_urlencoded": request_form_urlencoded,
                "request_form_file": request_form_file,
                "request_body": json_payload,
                "request_text": request_text,
            }
            response: httpx.Response = await self.context.send_http_request(
                request_method,
                request_url,
                headers=request_header,
                params=request_params,
                data=data_payload,
                json_data=json_payload,
                content=content_payload,
                files=file_payload,
            )
            try:
                cookies: Dict[str, Any] = {}
                if response.cookies:
                    for cookie in response.cookies.jar:
                        cookies[cookie.name] = cookie.value
                result.response = {
                    "response_code": response.status_code,
                    "response_message": response.reason_phrase,
                    "response_header": {k: unquote(v) for k, v in dict(response.headers).items()},
                    "response_text": response.text,
                    "response_cookie": cookies,
                    "response_elapsed": str(response.elapsed.total_seconds()),
                }
            except AttributeError as e:
                raise StepExecutionError(f"【HTTP请求】响应对象缺少必要属性, 错误详情: {e}") from e
            except Exception as e:
                raise StepExecutionError(f"【HTTP请求】在提取响应状态码、内容、headers、cookies时失败, 错误详情: {e}") from e
            try:
                response_json = response.json()
            except (ValueError, orjson.JSONDecodeError):
                response_json = None
            except Exception as e:
                self.context.log(f"【HTTP请求】响应JSON解析失败: {e}, 将使用文本响应", step_code=self.step_code)
                response_json = None

            request_json_for_extract = json_payload if isinstance(json_payload, (dict, list)) else None
            if request_json_for_extract is None and isinstance(request_body, (dict, list)):
                request_json_for_extract = request_body
            request_text_for_extract = request_text if request_text not in (None, "") else (
                data_payload if isinstance(data_payload, str) else None
            )
            # 合并到session_variables由execute()的finally统一从result.extract_variables处理
            self.apply_extract_and_assert(
                result,
                step_label="HTTP请求",
                response_text=result.response.get("response_text") if result.response else None,
                response_json=response_json,
                response_headers=result.response.get("response_header") if result.response else None,
                response_cookies=result.response.get("response_cookie") if result.response else None,
                request_text=request_text_for_extract,
                request_json=request_json_for_extract,
                request_headers=request_header,
                request_cookies=AutoTestToolService.parse_cookie_header(request_header),
                step_struct=step_struct,
            )
        except StepExecutionError:
            raise
        except Exception as e:
            result.success = False
            result.error = AutoTestToolService.format_step_error_message(step=self.step, exception=e, is_child_step=False)
            self.context.log(result.error, step_code=self.step_code)
            raise StepExecutionError(result.error) from e


class DatagramDiffStepExecutor(BaseStepExecutor):
    @staticmethod
    def _to_message_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise StepExecutionError("【报文比对】bytes 报文 UTF-8 解码失败") from exc
        if isinstance(value, (dict, list)):
            return orjson.dumps(value, default=str).decode("UTF-8")
        return str(value)

    def _resolve_message_ref(self, raw: Any) -> Any:
        if raw is None:
            return None
        text = str(raw).strip()
        if not text:
            return ""
        if "${" not in text:
            text = f"${{{text}}}"
        resolved = self.context.resolve_placeholders(text, step_code=self.step_code)
        if isinstance(resolved, str) and resolved.startswith("${") and resolved.endswith("}"):
            variable_name = resolved[2:-1].strip()
            if variable_name:
                try:
                    return self.context.get_variable(variable_name)
                except KeyError:
                    return resolved
        return resolved

    @staticmethod
    def _get_order_control(raw: Any) -> int:
        if raw is None:
            return 0
        try:
            order_control = int(raw)
        except (TypeError, ValueError) as exc:
            raise StepExecutionError(f"【报文比对】order_control 必须是 0 或 1: {raw}") from exc
        if order_control not in (0, 1):
            raise StepExecutionError(f"【报文比对】order_control 必须是 0 或 1: {order_control}")
        return order_control

    def _load_comparisons(self) -> List[Dict[str, Any]]:
        default_order_control = self._get_order_control(self.step.get("order_control"))
        items = self.step.get("message_comparison")
        if items:
            if not isinstance(items, list) or not items:
                raise StepExecutionError("【报文比对】message_comparison 必须是非空数组")
            comparisons: List[Dict[str, Any]] = []
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    raise StepExecutionError(f"【报文比对】message_comparison[{index}] 必须是对象")
                left_text = item.get("left_text")
                right_text = item.get("right_text")
                if left_text is None or right_text is None:
                    raise StepExecutionError(
                        f"【报文比对】message_comparison[{index}] 缺少 left_text 或 right_text"
                    )
                comparisons.append(
                    {
                        "left_text": left_text,
                        "right_text": right_text,
                        "order_control": self._get_order_control(
                            item.get("order_control", default_order_control)
                        ),
                    }
                )
            return comparisons
        left_raw = self.step.get("left_text")
        right_raw = self.step.get("right_text")
        if left_raw is None or right_raw is None:
            raise StepExecutionError("【报文比对】缺少必要参数: message_comparison")
        left_list = left_raw if isinstance(left_raw, list) else [left_raw]
        right_list = right_raw if isinstance(right_raw, list) else [right_raw]
        if len(left_list) != len(right_list):
            raise StepExecutionError(
                f"【报文比对】left_text 与 right_text 数量不一致: {len(left_list)} vs {len(right_list)}"
            )
        return [
            {
                "left_text": left_text,
                "right_text": right_text,
                "order_control": default_order_control,
            }
            for left_text, right_text in zip(left_list, right_list)
        ]

    async def _execute(self, result: StepExecutionResult) -> None:
        try:
            comparisons_raw = self._load_comparisons()

            self.context.log(
                f"【报文比对】开始执行: 共 {len(comparisons_raw)} 组",
                step_code=self.step_code,
            )

            message_comparison: List[Dict[str, Any]] = []
            failed_indices: List[int] = []
            for index, item in enumerate(comparisons_raw):
                order_control = item["order_control"]
                left_text = self._to_message_text(self._resolve_message_ref(item.get("left_text")))
                right_text = self._to_message_text(self._resolve_message_ref(item.get("right_text")))
                diff_data = compare_messages(
                    left_text=left_text,
                    right_text=right_text,
                    order_control=order_control,
                )
                message_comparison.append(
                    {
                        "left_name": item.get("left_text"),
                        "right_name": item.get("right_text"),
                        "left_text": left_text,
                        "right_text": right_text,
                        "order_control": order_control,
                        "is_equal": diff_data.is_equal,
                        "format_type": diff_data.format_type,
                        "order_consistent": diff_data.order_consistent,
                        "order_message": diff_data.order_message,
                        "rows": diff_data.model_dump().get("rows", []),
                    }
                )
                if not diff_data.is_equal:
                    failed_indices.append(index)

            response_payload = {
                "message_comparison": message_comparison,
            }
            result.request = {
                "message_comparison": comparisons_raw,
            }
            result.response = {
                "response_code": 200 if not failed_indices else 400,
                "response_message": "success" if not failed_indices else "diff found",
                "response_header": None,
                "response_cookie": None,
                "response_body": response_payload,
                "response_text": orjson.dumps(response_payload, default=str).decode("UTF-8"),
                "response_elapsed": None,
                "response_bytes": None,
            }

            if failed_indices:
                raise StepExecutionError(
                    f"【报文比对】共 {len(failed_indices)} 组不一致(索引: {failed_indices}), 详情见报告明细"
                )

            self.context.log("【报文比对】执行成功", step_code=self.step_code)

        except StepExecutionError:
            raise
        except Exception as e:
            result.success = False
            result.error = AutoTestToolService.format_step_error_message(
                step=self.step, exception=e, is_child_step=False
            )
            self.context.log(result.error, step_code=self.step_code)
            raise StepExecutionError(result.error) from e


class DefaultStepExecutor(BaseStepExecutor):
    """
    默认步骤执行器：仅顺序执行子步骤，作为未知步骤类型或容器步骤的回退。
    """

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        顺序执行子步骤并将结果写入本步children，任一子步失败则本步失败。

        :param result: 本步执行结果，子步骤写入children
        :return: None
        """
        try:
            child_results = await self._execute_children()
            for child in child_results:
                result.append_child(child)
                if not child.success:
                    result.success = False
        except Exception as e:
            result.success = False
            result.error = AutoTestToolService.format_step_error_message(step=self.step, exception=e, is_child_step=False)
            self.context.log(result.error, step_code=self.step_code)
            raise StepExecutionError(result.error) from e


class StepExecutorFactory:
    """
    根据步骤类型创建对应执行器实例，未知类型使用DefaultStepExecutor。
    """

    EXECUTOR_MAP: Dict[AutoTestStepType, Callable[[AutoTestStepTreeUpdateItem, StepExecutionContext], BaseStepExecutor]] = {
        AutoTestStepType.TCP: TcpStepExecutor,
        AutoTestStepType.HTTP: HttpStepExecutor,
        AutoTestStepType.PYTHON: PythonStepExecutor,
        AutoTestStepType.DATABASE: DataBaseStepExecutor,
        AutoTestStepType.REDIS: RedisStepExecutor,
        AutoTestStepType.LOOP: LoopStepExecutor,
        AutoTestStepType.IF: ConditionStepExecutor,
        AutoTestStepType.WAIT: WaitStepExecutor,
        AutoTestStepType.ASSERT: AssertStepExecutor,
        AutoTestStepType.QUOTE: QuoteCaseStepExecutor,
        AutoTestStepType.USER_VARIABLES: UserVariablesStepExecutor,
    }

    @classmethod
    def create_executor(cls, step: AutoTestStepTreeUpdateItem, context: StepExecutionContext) -> BaseStepExecutor:
        """
        根据step.step_type创建对应执行器；未知类型使用DefaultStepExecutor。

        :param step: 步骤树节点
        :param context: 执行上下文
        :return: 步骤执行器实例
        """
        try:
            raw_type = step.step_type
            if raw_type is None:
                raise StepExecutionError("步骤类型未定义")
            if isinstance(raw_type, AutoTestStepType):
                step_type = raw_type
            else:
                step_type = AutoTestStepType(str(raw_type).strip())
            executor_cls = cls.EXECUTOR_MAP.get(step_type, DefaultStepExecutor)
            try:
                return executor_cls(step, context)
            except Exception as exc:
                raise StepExecutionError(f"创建执行器失败: {exc}") from exc
        except StepExecutionError:
            raise
        except Exception as exc:
            raise StepExecutionError(f"创建执行器异常: {exc}") from exc


class AutoTestStepExecutionEngine:
    """
    用例执行入口：创建报告、进入上下文、根据step_no执行根步骤并汇总统计与日志。
    """

    def __init__(
            self, *,
            http_client: Optional[HttpClientProtocol] = None,
            save_report: bool = True,
            task_code: Optional[str] = None,
            batch_code: Optional[str] = None,
    ) -> None:
        """
        初始化执行引擎。

        :param http_client: 可选 HTTP 客户端，不传则上下文内自动创建
        :param save_report: 是否收集报告与步骤明细供调用方落库（执行阶段不写库，由调用方单事务写入）
        :param task_code: 任务编码，写入报告
        :param batch_code: 批次编码，写入报告
        """
        self._http_client = http_client
        self._save_report = save_report
        self._task_code = task_code
        self._batch_code = batch_code
        self._report_code: Optional[str] = None
        self._pending_details: List[AutoTestApiDetailCreate] = []

    async def execute_case(
            self,
            case: Dict[str, Any],
            steps: Iterable[AutoTestStepTreeUpdateItem],
            report_type: AutoTestReportType,
            *,
            steps_execute_config: Optional[Dict[str, StepsExecuteConfigBase]] = None,
            initial_variables: Optional[List[StepVariablesBase]] = None,
            dataset_name: Optional[str] = None,
    ) -> Tuple[
        List[StepExecutionResult],
        Dict[str, List[str]],
        Optional[str],
        Dict[str, Any],
        List[StepVariablesBase],
        Optional[AutoTestApiReportCreate],
        Optional[List[AutoTestApiDetailCreate]]
    ]:
        """
        执行单用例：在上下文中根据step_no执行根步骤，可选收集报告与明细供调用方落库。

        参数化时仅传入dataset_name，HTTP、TCP步骤根据case_id/step_code与数据集名称查表取数。
        step_is_skipped 的步骤不进入results、不写明细、不计入statistics。

        :param case: 用例信息字典，含case_id、case_code、case_name
        :param steps: 根步骤可迭代对象（已排序根据 step_no）
        :param report_type: 报告类型枚举
        :param steps_execute_config: 执行配置
        :param initial_variables: 初始会话变量列表，每项含key、value、desc
        :param dataset_name: 参数化时本次执行的数据集名称，写入每条步骤明细；步骤内据此查表取数
        :return: 七元组 (results, logs, report_code, statistics, session_variables, defer_create_report, pending_create_details)，
            results：根步骤执行结果列表（不含已跳过步骤）；logs：根据step_code分组；report_code：未保存时为None；
            statistics：含total_steps、success_steps、failed_steps、passed_ratio；session_variables：执行后变量列表；
            当_save_report为True时，最后两项为待落库的报告创建体与明细列表（report_code 已统一），
            调用方在单事务内依次create_report、create_detail、update_case
        """
        report_code: Optional[str] = None
        case_id: int = case.get("case_id")
        case_code: str = case.get("case_code")
        case_start_time: datetime = datetime.now()
        case_st_time_str: str = case_start_time.strftime("%Y-%m-%d %H:%M:%S.%f")
        if self._save_report:
            report_code: str = unique_identify()
            self._report_code = report_code
            self._pending_details = []
        pending_details_arg: Optional[List[AutoTestApiDetailCreate]] = self._pending_details if self._save_report else None
        async with StepExecutionContext(
                case_id=case_id,
                case_code=case_code,
                steps_execute_config=steps_execute_config,
                report_code=report_code,
                dataset_name=dataset_name,
                http_client=self._http_client,
                initial_variables=initial_variables,
                pending_details=pending_details_arg,
        ) as context:
            ordered_root_steps: List[AutoTestStepTreeUpdateItem] = sorted(
                [prepare_step_tree_item_for_execution(s) for s in steps],
                key=lambda item: (item.step_no or 0),
            )
            results: List[StepExecutionResult] = []
            for step in ordered_root_steps:
                executor: BaseStepExecutor = StepExecutorFactory.create_executor(step, context)
                result: Optional[StepExecutionResult] = await executor.execute()
                if result is None:
                    continue
                results.append(result)
                # 对于根步骤（parent_step_id 为 None）, 汇总所有子步骤的日志
                if step.parent_step_id is None:
                    root_step_code: str = step.step_code
                    if root_step_code is not None:
                        self.aggregate_root_step_logs(context, result, root_step_code)

            # 统计（根据 step_code 去重合并）
            all_results: List[StepExecutionResult] = self.collect_all_results(results)
            unique_states: Dict[str, bool] = {}
            for r in all_results:
                key: str = r.step_code
                if key not in unique_states:
                    unique_states[key] = True
                if not r.success:
                    unique_states[key] = False

            total_steps: int = len(unique_states)
            success_steps: int = sum(1 for v in unique_states.values() if v)
            failed_steps: int = total_steps - success_steps
            passed_ratio: float = (success_steps / total_steps * 100) if total_steps > 0 else 0.0
            case_end_time: datetime = datetime.now()
            case_ed_time_str: str = case_end_time.strftime("%Y-%m-%d %H:%M:%S")
            case_elapsed: str = f"{(case_end_time - case_start_time).total_seconds():.3f}"
            case_state: bool = failed_steps == 0
            defer_create_report: Optional[AutoTestApiReportCreate] = None
            pending_create_details: Optional[List[AutoTestApiDetailCreate]] = None
            if self._save_report and report_code:
                # 优先取上下文用户名；兼容旧逻辑仅有 user_id 时不再写入数字 ID
                user_name: Optional[str] = get_current_username()
                final_report_type = report_type if report_type is not None else AutoTestReportType.SYNC_EXEC
                defer_create_report = AutoTestApiReportCreate(
                    case_id=case_id,
                    case_code=case_code,
                    report_code=report_code,
                    case_st_time=case_st_time_str,
                    case_ed_time=case_ed_time_str,
                    case_elapsed=case_elapsed,
                    case_state=case_state,
                    step_total=total_steps,
                    step_fail_count=failed_steps,
                    step_pass_count=success_steps,
                    step_pass_ratio=passed_ratio,
                    report_type=final_report_type,
                    created_user=user_name,
                    task_code=self._task_code,
                    batch_code=self._batch_code,
                    dataset_name=(dataset_name or None),
                )
                pending_create_details = list(self._pending_details)

            statistics: Dict[str, Any] = {
                "total_steps": total_steps,
                "success_steps": success_steps,
                "failed_steps": failed_steps,
                "passed_ratio": round(passed_ratio, 2)
            }
            session_variables = context.session_variables if isinstance(context.session_variables, list) else []
            return results, context.logs, report_code, statistics, session_variables, defer_create_report, pending_create_details

    @staticmethod
    def collect_all_results(results: List[StepExecutionResult]) -> List[StepExecutionResult]:
        """
        递归收集所有步骤结果（含子步骤）为扁平列表。

        :param results: 根步骤执行结果列表
        :return: 含所有根步骤及其子步骤的扁平结果列表
        """
        all_res: List[StepExecutionResult] = []
        for r in results:
            all_res.append(r)
            all_res.extend(AutoTestStepExecutionEngine.collect_all_results(r.children))
        return all_res

    @staticmethod
    def aggregate_root_step_logs(
            context: StepExecutionContext,
            root_result: StepExecutionResult,
            root_step_code: str
    ) -> None:
        """
        将根步骤下所有子步骤的日志根据step_code收集后，追加到该根步骤在context.logs中的日志列表。

        :param context: 执行上下文，其logs将被修改
        :param root_result: 根步骤的执行结果，用于遍历children
        :param root_step_code: 根步骤的step_code，用于写回context.logs
        :return: None
        """

        def collect_child_step_nos(result: StepExecutionResult) -> List[str]:
            """
            递归收集该结果及其子结果的step_code列表。

            :param result: 当前步骤执行结果
            :return: step_code列表
            """
            step_codes: List[str] = []
            if result.step_code is not None:
                step_codes.append(result.step_code)
            for child in result.children:
                step_codes.extend(collect_child_step_nos(child))
            return step_codes

        # 收集所有子步骤的编号（递归收集, 包括子步骤的子步骤）
        child_step_codes: List[str] = []
        for child in root_result.children:
            child_step_codes.extend(collect_child_step_nos(child))

        # 汇总所有子步骤的日志（根据步骤编号排序）
        aggregated_logs: List[str] = []
        for step_code in sorted(child_step_codes):
            if step_code in context.logs:
                aggregated_logs.extend(context.logs[step_code])

        # 将根步骤的日志替换为：根步骤自己的日志 + 所有子步骤的汇总日志
        if root_step_code in context.logs:
            root_logs = context.logs[root_step_code]
            context.logs[root_step_code] = root_logs + aggregated_logs
        else:
            # 如果根步骤没有自己的日志, 直接使用子步骤的汇总日志
            context.logs[root_step_code] = aggregated_logs
