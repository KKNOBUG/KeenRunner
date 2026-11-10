# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
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
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Optional, Protocol, Tuple, Union, Set
from urllib.parse import unquote

import httpx
import orjson
from aiomysql import Pool

if TYPE_CHECKING:
    # 仅类型检查期导入：dependencies 会反向依赖 autotest_step_crud，而后者导入本模块，运行期导入将形成循环依赖
    from backend.applications.autotest.dependencies import AutoTestServices

from backend.applications.autotest.services.autotest_runtime.protocol_http import (
    assemble_http_body_payloads,
    build_httpx_request_kwargs,
)
from backend.applications.autotest.services.autotest_runtime.protocol_tcp import (
    select_tcp_payload,
    parse_tcp_response,
    parse_tcp_timeouts,
    resolve_tcp_frame_config,
    resolve_tcp_request_extract_sources,
    TCP_MAX_RESPONSE_BYTES,
)
from backend.applications.autotest.services.autotest_runtime.datagram.datagram_diff import compare_messages
from backend.applications.autotest.services.autotest_runtime.builtin_variables import collect_builtin_step_variables
from backend.applications.autotest.schemas.autotest_detail_schema import AutoTestDetailCreate
from backend.applications.autotest.schemas.autotest_report_schema import AutoTestReportCreate
from backend.applications.autotest.schemas.autotest_datagram_diff_schema import DatagramFieldCompareItem
from backend.applications.autotest.schemas.autotest_step_schema import (
    AutoTestStepTreeUpdateItem,
    ConditionsBase,
    DataBaseOperates,
    RedisOperates,
    StepVariablesBase,
    StepAssertValidatorItem,
    StepsExecuteConfigBase,
    StepExtractVariableItem,
    prepare_step_tree_item_for_execution,
    step_variables_list_from_storage,
)
from backend.applications.autotest.services.autotest_runtime.sandbox import UserCodeSandbox
from backend.applications.autotest.services.autotest_tool_service import AutoTestToolService
from backend.applications.base.services.scaffold import unique_identify
from backend.common import AioTcpClient
from backend.common.cache.redis_connection_pool import get_app_redis_pool, RedisConnPoolFromConfig
from backend.common.database.database_connection_pool import get_app_database_pool, DBConnPoolFromConfig
from backend.common.url_utils import build_absolute_http_url, is_absolute_http_url
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
)
from backend.enums import (
    AutoTestStepType,
    AutoTestBranchType,
    AutoTestReportType,
    AutoTestLoopMode,
    AutoTestCaseType,
    AutoTestLoopErrorStrategy,
    AutoTestReqArgsType,
    AutoTestConfigNodeType,
    HTTPMethod,
)
from backend.services import get_current_username


class StepExecutionError(Exception):
    """
    步骤执行期业务异常：用于中断当前步骤并把可读错误信息带回统一收口点。

    各执行器在 _execute 内抛出，由 BaseStepExecutor.execute 捕获后写入 StepExecutionResult，
    因此该异常不会穿透到用例执行入口，也不会中断同级其它步骤。
    """


@dataclass
class StepExecutionResult:
    """
    单步执行结果；容器步骤可通过children挂载子步骤结果树。

    执行器只负责填充快照字段，落库由 BaseStepExecutor._save_step_detail 读取本对象后组装明细。

    :ivar case_id: 用例ID
    :ivar step_id: 步骤ID
    :ivar step_no: 步骤序号
    :ivar step_code: 步骤标识，用于日志与统计去重
    :ivar step_name: 步骤名称
    :ivar step_type: 步骤类型枚举
    :ivar success: 本步是否成功；容器步骤任一子步骤失败即置False（条件分支未命中任何分支时仍为True）
    :ivar message: 补充说明（如条件分支命中的分支描述）
    :ivar error: 失败时的错误信息
    :ivar elapsed: 耗时（秒）
    :ivar dataset_name: 参数化数据集名称
    :ivar quote_case_id: 引用公共脚本/公共接口时的被引用用例ID（引用步骤的子步骤继承该值）
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


class HttpClientProtocol(Protocol):
    """
    HTTP客户端协议：只约束 request 方法签名，便于注入 httpx.AsyncClient 或测试替身。

    引擎仅依赖此协议，不感知客户端的具体实现与连接管理方式。
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
    步骤执行上下文：单次用例执行期间共享的运行时状态与能力集合。

    职责：
        - 持有用例/报告标识、执行配置映射、数据源场景名与引用链标记，供各执行器读取；
        - 维护两级变量池（defined_variables 步骤局部 / session_variables 会话累积）并提供占位符解析；
        - 按 step_code 归集执行日志，收集待落库明细（pending_details）；
        - 管理 HTTP 客户端生命周期（AsyncExitStack）。

    上下文同时充当运行时工具层的 finished_variables：工具层通过本类的 update_variables 把提取结果
    即时写回会话池，因此 update_variables 的签名与写回语义属于对外契约，不可随意调整。
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
            pending_details: Optional[List[AutoTestDetailCreate]] = None,
    ) -> None:
        """
        初始化步骤执行上下文。

        :param case_id: 用例ID
        :param case_code: 用例编码
        :param steps_execute_config: 执行环境配置
        :param report_code: 报告编码，用于保存步骤明细
        :param dataset_name: 参数化时传入的数据集名称，HTTP/TCP执行器据此 + case_id/step_code查表取数
        :param http_client: 可选HTTP客户端，不传则在__aenter__中创建
        :param initial_variables: 初始会话变量列表List[StepVariablesBase]；先置入session_variables再整体解析占位符，池内变量互引可求值
        :param pending_details: save_report 时收集待落库明细的列表；非None时_save_step_detail仅追加不写库
        """
        self.case_id = case_id
        self.case_code = case_code
        # 前端执行前选择的执行配置映射（key=step_id 或 @@step_name，DB/Redis 多操作再拼 _@@{index}）
        self.steps_execute_config: Dict[str, Any] = steps_execute_config or {}
        # 报告标识：为空表示不收集明细（调试/内部调用场景）
        self.report_code = report_code
        # 参数化数据集名称：HTTP/TCP 执行器据此 + case_id/step_code 查表取数
        self.dataset_name = dataset_name
        # 执行日志：按 step_code 归集；未归属步骤的日志落在 None 键下
        self.logs: Dict[str, List[str]] = {}
        # 待落库明细：非None时执行器只追加不写库，由调用方在短事务内统一写入
        self.pending_details = pending_details
        # 循环轮次：key=step_code，value=当前轮次（由循环执行器写入，明细 loop_cycles 取自此处）
        self.step_cycle_index: Dict[str, int] = {}
        # 当前执行步骤标识：日志默认归属目标，嵌套执行时由 execute() 保存与恢复
        self._current_step_code: Optional[str] = None
        # 引用链标记：非空表示正在执行被引用用例（引用壳执行期间设置，finally 回退上一层）
        self.executing_quote_case_id: Optional[int] = None
        # 引用链执行中容器步骤ID：被引用用例根步骤的parent_step_id为None，落明细时回落到此值归属引用容器
        self.executing_parent_step_id: Optional[int] = None
        # 引用公共接口自身挂载的数据源快照：由引用执行器预载（宿主case_id+引用步骤step_code查表），供引用链内层HTTP/TCP步骤消费；引用公共脚本链中恒为None（屏蔽外层引用接口数据源）
        self.quote_dataset_name: Optional[str] = None
        self.quote_dataset_snapshot: Optional[Dict[str, Dict[str, Any]]] = None
        # 外部注入的HTTP客户端：非None时由调用方负责生命周期，上下文不再重复创建
        self._http_client = http_client
        # 上下文自建异步资源的统一关闭点（当前仅默认HTTP客户端）
        self._exit_stack = AsyncExitStack()
        # 本步骤局部变量池：execute() 每次重建（用户步骤定义变量 + 内置变量），步骤结束后被下一步覆盖
        self.defined_variables: List[StepVariablesBase] = []
        # 会话变量池：跨步骤累积，初始池在下一行求值
        self.session_variables: List[StepVariablesBase] = []
        self.initialize_session_variables(initial_variables)
        # 默认HTTP客户端超时配置（秒）：请求总超时与建连超时
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
                # trust_env=False：忽略系统代理/环境变量，保证压测与执行流量按步骤配置直连目标
                client = httpx.AsyncClient(timeout=httpx.Timeout(timeout=self.timeout, connect=self.connect), trust_env=False)
                self._http_client = await self._exit_stack.enter_async_context(client)
            return self
        except Exception as e:
            error_message: str = f"异步上下文管理器: 创建HTTP客户端连接失败"
            LOGGER.error(f"{error_message}, {traceback.format_exc()}")
            self.log(message=error_message)
            raise StepExecutionError(error_message) from e

    async def __aexit__(self, exc_type: Optional[type[BaseException]], exc: Optional[BaseException], tb: Optional[types.TracebackType]) -> None:
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
            error_message: str = f"异步上下文管理器: 关闭HTTP客户端连接失败"
            LOGGER.error(f"{error_message}, {traceback.format_exc()}")
            self.log(message=error_message)

    def resolve_placeholders(self, variables: Any, step_code: Optional[str] = None) -> Any:
        """
        解析变量或配置中的${...}占位符（含函数占位符）。

        上下文适配：统一绑定 logger_object、is_core_engine 与 finished_variables=self，
        执行器无需在每个调用点重复传参。

        :param variables: 待解析的值，常见为List[StepVariablesBase]或嵌套结构
        :param step_code: 日志归属的步骤标识，未传则使用当前步骤
        :return: 解析后的值；None原样返回，空容器/0/False保留原语义
        """
        if variables is None:
            return None
        return AutoTestToolService.resolve_placeholders(
            value=variables,
            logger_object=lambda msg: self.log(msg, step_code=step_code),
            is_core_engine=True,
            finished_variables=self
        )

    def initialize_session_variables(self, initial_variables: Optional[List[StepVariablesBase]]) -> List[StepVariablesBase]:
        """
        重置会话变量池并求值，先置入原始池再整体解析函数占位符。

        执行中途进入被引用用例时复用此入口，使被引用用例与宿主用例做相同的变量池初始化，
        避免中途替换/并入的池绕过首次解析而残留${generate_xxx()}字面量。
        “先置入再解析”使变量互引只在本池内求值（不回看宿主池），维持引用域半隔离语义。

        :param initial_variables: 原始初始变量池(未解析)，None按空池处理
        :return: 解析后的会话变量池，与self.session_variables指向同一列表(执行期就地追加对调用方可见)
        """
        self.session_variables = list(initial_variables or [])
        resolved: List[StepVariablesBase] = self.resolve_placeholders(self.session_variables) or []
        self.session_variables = resolved
        return resolved

    def resolve_xml_placeholders(self, xml_text: str, step_code: Optional[str] = None) -> str:
        """
        解析XML报文中各文本节点与属性内的 ${...} 占位符（含算术表达式）。

        上下文适配：统一绑定 logger_object、is_core_engine 与 finished_variables=self。

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
        按 step_code 归集一条带时间戳的执行日志。

        :param message: 日志内容
        :param step_code: 步骤标识，用于归属；未传则使用当前步骤标识（可能为None，如上下文初始化阶段的日志）
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

    def update_variables(self, variables: List[StepVariablesBase], *, scope: str = "defined_variables") -> None:
        """
        根据作用域更新变量：variables为StepVariablesBase列表，同key覆盖，新key追加；key为空的项过滤跳过。

        :param variables: 待更新的变量列表
        :param scope: 目标作用域（defined_variables 或 session_variables）
        :return: None
        :raises ValueError: 作用域非法、入参不是列表或列表项不是 StepVariablesBase
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
            if not isinstance(variable, StepVariablesBase):
                raise ValueError("【更新变量】失败: 每项必须为 StepVariablesBase 类型且含非空 key")
            key: str = variable.key
            if not key or not key.strip():
                # 健壮性过滤：key为空的变量项不入池，不中断步骤
                continue
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
        按 defined_variables → session_variables 的优先级取名为name的变量值（defined 遮蔽同名 session）。

        defined_variables 为本步骤局部变量池（用户步骤定义 + 运行时内置变量），每次 execute() 重建；
        session_variables 为跨步骤累积的会话变量池，所有步骤共享。
        注意：此处 defined 优先；提取/断言查找表（build_session_lookup）则是 session 覆盖 defined，两者口径不同。

        :param name: 变量名，非空字符串
        :return: 变量值（null 也是合法值）
        :raises StepExecutionError: 变量名为空或不是字符串
        :raises KeyError: 两级变量池均未定义该变量
        """
        if not name or not isinstance(name, str):
            raise StepExecutionError(f"【获取变量】变量名无效: \n\t变量名必须是非空字符串, 当前值: {name}")

        for scope_name, scope_list in [
            ("defined_variables", self.defined_variables),
            ("session_variables", self.session_variables),
        ]:
            # 按key存在性判断而非value非空：null是合法变量值，且defined必须遮蔽同名session变量
            item = AutoTestToolService.get_item_from_list(scope_list, name)
            if item is not None:
                return item.value

        raise KeyError(f"【获取变量】变量({name})未定义: \n\t请检查变量名是否正确, 或确认变量是否已在之前的步骤中定义")

    async def sleep(self, seconds: Optional[float]) -> None:
        """
        异步等待指定秒数。

        :param seconds: 等待秒数；None不等待，小于0或大于300抛出异常
        :return: None
        :raises StepExecutionError: 参数不是可转float的数值、超出[0, 300]或等待过程被中断
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
        :raises StepExecutionError: URL非法、超时、连接失败或其它请求异常（均在此转译并记日志）
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
                    f"响应耗时: {response.elapsed.total_seconds():.2f}s"
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
        在受限内置与namespace下执行code，支持单函数定义或顶层result变量。

        执行顺序：记录原始代码快照 → 长度校验 → 占位符解析 → 单行代码规范化 → AST安全校验 → exec。
        import/from 仅允许UserCodeSandbox.ALLOWED_IMPORT_ROOTS中的根模块；禁止下划线开头/帧自省属性访问（防对象自省逃逸沙箱）；
        可用内建见 UserCodeSandbox.SAFE_BUILTINS（含常用异常类型），另可使用namespace变量（函数体内同可见，支持递归）。
        返回值中的mapping key会递归转为str（tuple转为list），避免非字符串key导致orjson序列化或落库失败。

        :param code: Python 代码字符串，可为单行或多行
        :param namespace: 执行时的局部命名空间（如变量字典），可选；其中的__builtins__会被剥离，无法覆盖沙箱内置
        :param step_result: 可选；传入时写入其request，记录原始代码快照（未经占位符解析与规范化的原始code）
        :return: 代码中定义的 result 或单函数返回值；支持 Dict[str, Any] 或 List[Dict[Any, Any]]；无结果时返回空字典
        :raises StepExecutionError: 代码超长、安全校验不通过、执行异常或返回类型不被接受
        """
        if step_result is not None:
            step_result.request = {
                "request_code": code,
                "request_args_type": AutoTestReqArgsType.RAW
            }
        if not code:
            return {}
        if len(code) > UserCodeSandbox.MAX_CODE_LENGTH:
            error_message = (
                f"【代码请求(Python)】代码长度超限: \n\t"
                f"最大允许: {UserCodeSandbox.MAX_CODE_LENGTH}字符\n\t"
                f"当前输入: {len(code)}字符"
            )
            self.log(error_message)
            raise StepExecutionError(error_message)
        resolved_code: str = self.resolve_code_placeholders(code)
        prepared_code: str = self.normalize_python_code(resolved_code)
        try:
            self._validate_user_python_restricted(prepared_code)
        except StepExecutionError as e:
            self.log(str(e))
            raise
        # 单命名空间执行：沙箱builtins与namespace并入同一exec上下文字典（隔离与注入规则见工厂docstring）
        exec_context: Dict[str, Any] = UserCodeSandbox.new_exec_context(namespace)

        try:
            exec(prepared_code, exec_context)
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

        # exec后从命名空间识别用户定义的函数：有函数则以唯一函数为入口，否则回落到顶层result变量
        functions = {
            name: obj
            for name, obj in exec_context.items()
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
        elif "result" in exec_context:
            result = exec_context["result"]
        else:
            result = None

        if result is None:
            self.log(f"【代码请求(Python)】执行完成, 但无结果: {result!r}")
            return {}
        # dict原样通过；list要求元素均为dict（供变量池与明细按行统一消费）
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
        静态校验用户代码（只做AST分析，不执行），拦截沙箱逃逸与不支持的语法。

        import/from仅允许UserCodeSandbox.ALLOWED_IMPORT_ROOTS中的根模块（与受限导入钩子一致）；
        禁止下划线开头属性（namedtuple只读工具方法除外）及UserCodeSandbox.FORBIDDEN_ATTRS帧自省属性
        （阻断().__class__与gi_frame等对象自省逃逸沙箱路径）；
        仅允许普通def函数，禁止class/async def；语法错误不在本方法报错，留给exec统一提示。

        :param source: 待校验的Python源代码字符串
        :return: None
        :raises StepExecutionError: 命中任一安全限制
        """
        allowed_cn = "、".join(sorted(UserCodeSandbox.ALLOWED_IMPORT_ROOTS))
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef)):
                error_message = (
                    "【代码请求(Python)】安全限制: \n\t"
                    "仅支持普通def函数或result变量, 不允许定义class或async函数"
                )
                raise StepExecutionError(error_message)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root not in UserCodeSandbox.ALLOWED_IMPORT_ROOTS:
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
                if root not in UserCodeSandbox.ALLOWED_IMPORT_ROOTS:
                    error_message = (
                        "【代码请求(Python)】安全限制(仅允许从以下模块 from 导入): \n\t"
                        f"允许依赖: {allowed_cn}\n\t"
                        f"非法依赖: {node.module}"
                    )
                    raise StepExecutionError(error_message)
            elif isinstance(node, ast.Attribute) and (
                    (node.attr.startswith("_") and node.attr not in UserCodeSandbox.ALLOWED_PRIVATE_ATTRS)
                    or node.attr in UserCodeSandbox.FORBIDDEN_ATTRS
            ):
                error_message = (
                    "【代码请求(Python)】安全限制(防止通过对象自省逃逸沙箱): \n\t"
                    f"不允许访问下划线开头/帧自省属性: {node.attr}"
                )
                raise StepExecutionError(error_message)

    @staticmethod
    def normalize_python_code(code: str) -> str:
        """
        将单行函数形式的代码格式化为多行：提取import/from，分离def与函数体并正确缩进。

        仅处理不含换行的单行代码；import 语句会被提升到函数定义之前（与 exec 上下文同层）。
        属于启发式处理：按首个冒号切分函数头与函数体，函数体统一缩进4空格，仅识别 return/if/for/while/with 开头的体。

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
        引用失败（变量未定义/函数抛错）时保留原占位符并记日志，不在此抛出异常，后续 exec 可能因之报NameError。

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
        code = UserCodeSandbox.RE_QUOTED_PLACEHOLDER.sub(replace_string_placeholder, code)

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
            new_code = UserCodeSandbox.RE_QUOTED_CONCAT.sub(replace_string_concat_placeholder, code)
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
            resolved_code = UserCodeSandbox.RE_PLACEHOLDER.sub(replace_code_placeholder, code)
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
    步骤执行器基类：一个实例只对应一个步骤节点，持有 step 与 context。

    统一执行骨架（子类只需实现 _execute）：
        1. execute() 处理步骤跳过、步骤局部变量注入、日志归属保存与恢复；
        2. 调用 _execute() 执行具体协议逻辑，异常在此收敛为 result.success=False；
        3. finally 合并提取结果到会话池、计算耗时、按需收集明细。

    契约：除「内置变量/局部变量准备阶段」失败会原样上抛外，execute() 不向上抛异常，所有执行期失败都记录在 StepExecutionResult 中，调用方据返回值做统计；
    子类 _execute 失败时应抛出 StepExecutionError，由 execute() 统一收口。
    """

    # 是否在执行前解析本步骤defined_variables并注入变量池；引用壳执行器关闭（自身无目标环境，无法提供内置变量）
    resolve_own_defined_variables: bool = True

    def __init__(self, step: AutoTestStepTreeUpdateItem, context: StepExecutionContext):
        """
        初始化步骤执行器。

        :param step: 当前步骤模型，含step_type、step_code、defined_variables等
        :param context: 执行上下文，用于变量、日志、HTTP请求等
        """
        self.step = step
        # 同一用例内共享的执行上下文
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
        """当前步骤的子步骤列表（children + quote_steps，按 step_no 升序；step_no 缺失按0参与排序）。"""
        return sorted(
            list(self.step.children or []) + list(self.step.quote_steps or []),
            key=lambda item: (item.step_no or 0),
        )

    @classmethod
    async def get_services(cls) -> AutoTestServices:
        """获取自动化测试CRUD服务聚合（延迟导入：dependencies 反向依赖本模块，顶层导入会构成循环依赖）。"""
        from backend.applications.autotest.dependencies import get_autotest_api_services
        return await get_autotest_api_services()

    async def load_step_dataset(self, result: StepExecutionResult) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        加载当前请求步骤的数据源场景，并写入结果快照。

        HTTP/TCP 共用：普通步骤按 case_id + step_code + dataset_name 查库；
        引用链内层步骤直接消费引用壳预载的 quote_dataset_snapshot，不再重复查库（也避开引用链的加载短路）。

        :param result: 本步执行结果，用于回填dataset_snapshot/dataset_name
        :return: _acquire_dataset_payload结构（head/body/assert_head/assert_body）；无数据驱动或未命中时为None
        """
        dataset_name: Optional[str] = getattr(self.context, "dataset_name", None)
        executing_quote_case_id: Optional[int] = getattr(self.context, "executing_quote_case_id", None)
        if executing_quote_case_id:
            step_struct = getattr(self.context, "quote_dataset_snapshot", None)
        else:
            step_struct = await AutoTestToolService.load_dataset_for_request_step(
                case_id=self.case_id,
                step_code=self.step_code,
                dataset_name=dataset_name,
                executing_quote_case_id=executing_quote_case_id,
            )
        result.dataset_snapshot = step_struct
        result.dataset_name = dataset_name
        return step_struct

    def evaluate_condition(self, condition: ConditionsBase, *, operation_type: str = "条件") -> bool:
        """
        评估条件是否成立：解析左侧表达式与右侧比较值中的占位符，再按操作符比较。

        Loop 条件循环与 Condition 条件分支共用，避免两套实现出现“只解析左侧、不解析右侧”的漂移。

        :param condition: 条件模型（condition_expr/condition_compare/condition_value）
        :param operation_type: 错误信息前缀（循环结构/条件分支）
        :return: 条件成立返回True
        :raises StepExecutionError: 条件字段缺失、占位符解析失败或比较符非法
        """
        condition_expr = condition.condition_expr
        condition_compare = condition.condition_compare
        condition_value = condition.condition_value
        if condition_expr is None or condition_compare is None:
            raise StepExecutionError(
                f"【{operation_type}】条件缺少必要字段: \n\t"
                f"条件表达式: {condition_expr!r}\n\t"
                f"条件操作符: {condition_compare!r}"
            )

        try:
            resolved_expr = self.context.resolve_placeholders(variables=condition_expr, step_code=self.step_code)
            if isinstance(resolved_expr, str) and resolved_expr.startswith("${") and resolved_expr.endswith("}"):
                variable_name = resolved_expr[2:-1]
                try:
                    actual_value = self.context.get_variable(variable_name)
                except KeyError as e:
                    raise StepExecutionError(
                        f"【{operation_type}】条件表达式中变量未定义: {variable_name}"
                    ) from e
            else:
                actual_value = resolved_expr
        except StepExecutionError:
            raise
        except Exception as e:
            raise StepExecutionError(f"【{operation_type}】条件表达式占位符解析异常, 错误描述: {e}") from e

        try:
            resolved_value = self.context.resolve_placeholders(variables=condition_value, step_code=self.step_code)
        except Exception as e:
            raise StepExecutionError(f"【{operation_type}】条件比较值占位符解析异常, 错误描述: {e}") from e

        try:
            return AutoTestToolService.compare_assertion(actual_value, condition_compare, resolved_value)
        except ValueError as e:
            raise StepExecutionError(f"【{operation_type}】条件表达式执行异常, 错误描述: {e}") from e

    def get_execute_config(
            self,
            database_operates_index: Optional[int] = None,
            expected_config_type: Optional[Union[AutoTestConfigNodeType, Iterable[AutoTestConfigNodeType]]] = None,
    ) -> Optional[StepsExecuteConfigBase]:
        """
        获取当前步骤的执行配置（APP/DB/REDIS）。
        KEY：step_id 优先，否则@@step_name；DB/Redis多操作再拼_@@{index}。
        指定expected_config_type时，类型不匹配视为未命中（避免HTTP误用database配置）。

        :param database_operates_index: 数据库/Redis 多操作时的操作序号（从0起）
        :param expected_config_type: 期望的配置类型（单个或可迭代多种）
        :return: 执行配置；未配置、类型不匹配或解析失败时返回 None
        """
        step_exec_config_map: Dict[str, Any] = self.context.steps_execute_config
        if not step_exec_config_map or not isinstance(step_exec_config_map, dict):
            return None

        expected_types: Optional[Set[AutoTestConfigNodeType]] = None
        if expected_config_type is not None:
            if isinstance(expected_config_type, AutoTestConfigNodeType):
                expected_types = {expected_config_type}
            else:
                expected_types = set(expected_config_type)

        step_id: Optional[int] = self.step.step_id
        step_name: Optional[str] = self.step.step_name
        cfg_key: str = str(step_id) if step_id else f"@@{str(step_name).strip()}"
        if database_operates_index is not None and database_operates_index >= 0:
            cfg_key += f"_@@{database_operates_index}"
        cfg_value: Any = step_exec_config_map.get(cfg_key)
        if not cfg_value:
            return None

        cfg: Optional[StepsExecuteConfigBase] = None
        if isinstance(cfg_value, StepsExecuteConfigBase):
            cfg = cfg_value
        elif isinstance(cfg_value, dict):
            try:
                cfg = StepsExecuteConfigBase.model_validate(cfg_value)
            except Exception:
                return None
        if cfg is None:
            return None
        if expected_types is not None and cfg.config_type not in expected_types:
            return None
        return cfg

    def collect_builtin_variables(self) -> List[StepVariablesBase]:
        """
        采集当前步骤的内置环境变量；默认无，HTTP/TCP执行器覆写提供SERVER_*/TARGET_*。

        :return: 内置变量列表；无内置变量时返回空列表
        """
        return []

    def existing_variable_keys(self) -> Set[str]:
        """
        用户已定义的变量key集合（本步骤局部+会话累积），供内置变量同名跳过判定。

        :return: 变量key集合
        """
        keys: Set[str] = {
            item.key for item in (self.step.defined_variables or [])
            if isinstance(item, StepVariablesBase) and item.key
        }
        keys |= {
            item.key for item in (self.context.session_variables or [])
            if isinstance(item, StepVariablesBase) and item.key
        }
        return keys

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
            request_form_data: Optional[Dict[str, Any]] = None,
            extract_variables: Optional[Any] = None,
            assert_validators: Optional[Any] = None,
            step_struct: Optional[Dict[str, Dict[str, Any]]] = None,
            session_lookup_extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        统一变量提取 + 断言：构建变量池查找表，调用工具管线，失败转为StepExecutionError。

        查找表优先级：session 覆盖同名 defined，session_lookup_extra 最后覆盖；
        与 get_variable 的 defined 优先口径不同，不要在两边套用同一优先级认知。
        管线以 raise_on_failure=False 运行（先拿回逐项结果），再由本方法统一聚合成一个 StepExecutionError，
        因此失败项仍会写入 result.extract_variables/assert_validators，明细不丢。

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
        :param request_form_data: 请求 Form-Data / X-WWW-Form-Urlencoded 合并映射
        :param extract_variables: 变量提取规则，缺省时使用步骤自身的 extract_variables
        :param assert_validators: 断言校验规则，缺省时使用步骤自身的assert_validators
        :param step_struct: 步骤结构映射，供提取断言管线解析引用
        :param session_lookup_extra: 额外并入变量池查找表的会话变量（优先级最高，如本步Python返回结果）
        :return: None
        :raises StepExecutionError: 存在提取/断言失败项，或管线执行异常
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
                request_form_data=request_form_data,
                session_variables_lookup=session_lookup,
                log_callback=lambda msg: self.context.log(msg, step_code=self.step_code),
                finished_variables=self.context,
                is_core_engine=True,
                step_struct=step_struct,
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
        执行当前步骤：注入局部变量、调用_execute、合并extract_variables、按需收集明细。

        若 step_is_skipped 为True，仅打INFO日志并返回None（不写明细、不计入统计、不执行子步骤）。
        无论本步成功还是失败，均返回同一个 StepExecutionResult（失败写入success/error）；
        唯一例外：内置变量/局部变量准备阶段抛出的异常会原样上抛（此时尚未进入 _execute，无结果可返回）。

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
        # 本步当前循环轮次（循环执行器写入）；顶层步骤为None，明细 loop_cycles 落NULL
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
        # 先注入内置环境变量（SERVER_HOST/SERVER_PORT/TARGET_HOST/TARGET_PORT/TARGET_PATH），
        # 使用户定义变量的值中也可引用内置变量；占位符解析完成后再拼接回变量池末尾，
        # 保证同名查找时用户变量优先命中（内置变量不覆盖用户主动定义的变量）
        try:
            builtin_variables: List[StepVariablesBase] = self.collect_builtin_variables()
            # 先置入内置变量，让用户定义变量的值可以引用它们
            self.context.defined_variables = builtin_variables
            if self.resolve_own_defined_variables:
                # 注入前剔除key为空的变量项（与前端保存校验同口径），避免空键数据进入变量池参与发送
                step_defined_variables: List[StepVariablesBase] = [
                    item for item in (self.step.defined_variables or [])
                    if isinstance(item, StepVariablesBase) and item.key and item.key.strip()
                ]
                # 将当前步骤的 defined_variables 注入到 context，供占位符解析使用
                resolved_defined_variables: List[StepVariablesBase] = self.context.resolve_placeholders(
                    variables=step_defined_variables,
                    step_code=self.step_code
                ) or []
                resolved_keys: Set[str] = {
                    item.key for item in resolved_defined_variables
                    if isinstance(item, StepVariablesBase) and item.key
                }
                self.context.defined_variables = resolved_defined_variables + [
                    item for item in builtin_variables if item.key not in resolved_keys
                ]
        except Exception:
            # 内置变量/局部变量准备失败时也必须恢复日志归属，避免current_step_code泄漏到后续步骤
            self.context.set_current_step_code(step_code=previous_step_code)
            raise
        try:
            await self._execute(result)
        except Exception as e:
            result.success = False
            # 此处不再 log：各执行器在 _execute 内已记录完整错误信息，重复记录会让明细日志出现两份同样的错误
            if not result.error:
                result.error = str(e)
            # -----------------------------------------------------------------------
            # 本 except Exception 不能删除：约定每个 execute() 必须返回 StepExecutionResult，不能把异常继续上抛。
            # 各执行器在 _execute 内的行为：捕获异常后设置 result.success=False、result.error=
            # format_step_error_message(...)，并 self.context.log(result.error)，再 raise。
            # 返回到此处时：异常已被捕获，result 可能已由执行器填好 error，且错误已记入 context.logs。
            # 此处仅做：补全 result.success=False、未设置时补全 result.error，且不再 log（避免重复）；
            # 不 re-raise，让后面的 finally 正常跑完（合并变量、计算 elapsed、收集明细），然后 return result。
            # 这样，无论本步成功还是失败，调用方拿到的都是同一个 StepExecutionResult，可以统一做 append 和统计。
            # -----------------------------------------------------------------------
        finally:
            try:
                # 将本步骤的 extract_variables 合并到 session_variables，供后续步骤引用（仅合并提取成功的，避免失败项用 None 覆盖）；
                # 经提取管线的步骤（HTTP/TCP/DB/Redis/断言/提取）已在管线内即时写回，此处的重写是幂等的
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

        仅当 context.report_code 存在时被 execute() 调用；pending_details 为None时本方法不写入任何内容。

        :param result: 本步骤执行结果对象
        :param step_st_time_str: 步骤开始时间字符串
        :param num_cycles: 循环第几轮（非循环步骤为None，明细落NULL）
        :return: None
        """
        step_end_time: datetime = datetime.now()
        step_ed_time_str: str = step_end_time.strftime("%Y-%m-%d %H:%M:%S.%f")
        step_elapsed: str = f"{result.elapsed:.2f}" if result.elapsed is not None else "0.00"
        step_logs: List[str] = self.context.logs.get(self.step_code, [])
        step_exec_logger: Optional[str] = "\n".join(step_logs) if step_logs else None
        # 响应快照：各类执行器字段不统一，按需取；无body但存文本时反序列化补齐body
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
        detail_create = AutoTestDetailCreate(
            case_id=self.context.case_id,
            case_code=self.context.case_code,
            report_code=self.context.report_code,
            quote_case_id=self.quote_case_id or result.quote_case_id,
            parent_step_id=self.step.parent_step_id or self.context.executing_parent_step_id,
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
            loop_cycles=num_cycles,
            # 请求相关
            request_url=actual_request.get("request_url"),
            request_port=actual_request.get("request_port"),
            request_method=actual_request.get("request_method"),
            request_args_type=actual_request.get("request_args_type"),
            request_project_id=self.step.request_project_id,
            request_config_name=actual_request.get("request_config_name") or self.step.request_config_name,
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
            # 次数循环：只取执行态解析后的整数（步骤定义可能是占位符字符串，不可直接写入明细Int字段）；
            # 非次数循环没有该字段，保持NULL，不存在「回落步骤定义」的分支
            loop_maximums=(
                actual_request.get("loop_maximums")
                if "loop_maximums" in actual_request
                else None
            ),
            loop_interval=self.step.loop_interval,
            loop_iterable=self.step.loop_iterable,
            loop_on_error=self.step.loop_on_error,
            loop_index=self.step.loop_index,
            loop_key=self.step.loop_key,
            loop_value=self.step.loop_value,
            code=actual_request.get("request_code"),
            loop_conditions=self._snapshot_loop_conditions(actual_request),
            branch_items=self._snapshot_branch_items(actual_request),
            branch_index=getattr(self.step, "branch_index", None),
            branch_match=actual_request.get("branch_match"),
            database_operates=actual_request.get("database_operates"),
            database_searched=actual_request.get("database_searched"),
            redis_operates=actual_request.get("redis_operates"),
            redis_searched=actual_request.get("redis_searched"),
            # 报文比对配置快照
            datagram_field_compare=actual_request.get("datagram_field_compare"),
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
            # 只收集不落库：由 execute_single_case/调试视图在短事务内统一写入，避免执行期长时间占用连接
            self.context.pending_details.append(detail_create)

    def _snapshot_loop_conditions(self, actual_request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        生成条件循环判断条件快照。

        优先取执行态 result.request.loop_conditions；缺省回落步骤定义 self.step.loop_conditions。

        :param actual_request: 本步骤 result.request 字典
        :return: Dict(condition_expr/condition_compare/condition_value) 或 None
        """
        from_request = actual_request.get("loop_conditions")
        if isinstance(from_request, dict) and from_request:
            return from_request
        cond = getattr(self.step, "loop_conditions", None)
        if cond is None:
            return None
        if hasattr(cond, "model_dump"):
            return cond.model_dump()
        if isinstance(cond, dict):
            return cond
        return None

    def _snapshot_branch_items(self, actual_request: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        生成条件分支执行快照：仅记录本次命中的那一条（不含 branch_children）。

        :param actual_request: 本步骤 result.request 字典（含 branch_items / branch_match）
        :return: 仅含命中分支的列表；未命中或非条件分支时返回 None
        """
        from_request = actual_request.get("branch_items")
        if not isinstance(from_request, list) or not from_request:
            return None
        # 执行器已写入「仅命中项」；此处再收敛字段，避免误带 branch_children
        snapshot: List[Dict[str, Any]] = []
        for item in from_request:
            if not isinstance(item, dict):
                continue
            snapshot.append({
                "branch_type": item.get("branch_type"),
                "branch_conditions": item.get("branch_conditions"),
                "branch_desc": item.get("branch_desc"),
            })
        return snapshot or None

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

        子步骤执行器创建失败或执行期抛出非预期异常时，不中断同级其它子步，而是转为一条失败结果项。

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
    循环结构执行器：按 loop_mode 分派次数/列表/字典/条件循环，逐轮写入循环变量并执行子步骤树。

    循环变量名直接取步骤配置（loop_index/loop_key/loop_value），前端输入框默认预填 loop_index/loop_key/loop_value。
    schema 只做格式校验（strip 后为空归一为None，禁止空白符与 '${'/'}'），执行期不做默认名回落，
    因此这三个字段为空时，本轮写入变量池会失败并导致本步失败。

    子步骤失败按 loop_on_error 处理：继续下一轮（CONTINUE）/ 中断本层循环（BREAK）/ 结束本步（STOP）。
    STOP 的异常文案写作“停止整个用例执行”，但该异常会被 execute() 收口为本步失败，同级与父层步骤仍继续执行。
    """

    # 条件循环最大循环时间上限(秒)：schema 入库上限 + 执行期对存量超限数据的兜底裁剪
    CONDITION_LOOP_MAX_TIMEOUT: int = 300

    # 防死循环护栏：条件循环单层最大执行轮数（与明细 loop_cycles 的 le=100 对齐）
    LOOP_GUARD_LIMIT: int = 100

    async def _execute_loop_round(
            self,
            result: StepExecutionResult,
            on_error: AutoTestLoopErrorStrategy,
            loop_no: int,
            loop_mode: str,
            loop_message: str,
            include_variables: List[StepVariablesBase],
    ) -> bool:
        """
        执行单轮子步骤：标记本轮轮次、写入本轮循环变量、执行子步骤树并按错误策略处理失败。
        四种循环模式的单轮行为完全一致，仅循环变量注入与日志文案不同，故收敛至此统一处理。

        轮次会同时写入本步与直接子步的 step_cycle_index（子步明细据自己的step_code取轮次）。

        :param result: 用于挂载子步骤结果的StepExecutionResult
        :param on_error: 子步骤失败时的处理策略：CONTINUE=继续下一轮，BREAK=中断本层循环，STOP=抛出异常结束本步
        :param loop_no: 当前轮次
        :param loop_mode: 循环模式（仅用于日志文案）
        :param loop_message: 本轮执行日志文案
        :param include_variables: 本轮写入会话变量的循环变量列表
        :raises StepExecutionError: 子步骤失败且策略为 STOP 时抛出，由外层 execute() 收口为本步失败（不中断同级/父层步骤）
        :return: True=继续下一轮；False=按[中断循环]策略结束本层循环；STOP 策略不返回（直接抛出）
        """
        if self.step_code:
            self.context.step_cycle_index[self.step_code] = loop_no

        self.context.log(message=loop_message, step_code=self.step_code)
        self.context.update_variables(include_variables, scope="session_variables")
        for child in self.children:
            # 子步明细据自己的 step_code 取轮次，故需同步写入直接子步的键（无 step_code 时退化为 step_id）
            child_code = child.step_code or (str(child.step_id) if child.step_id is not None else "")
            if child_code:
                self.context.step_cycle_index[child_code] = loop_no

        try:
            child_results = await self._execute_children()
        except StepExecutionError:
            if on_error == AutoTestLoopErrorStrategy.STOP:
                raise
            return on_error == AutoTestLoopErrorStrategy.CONTINUE
        except Exception as e:
            error_message = f"【循环结构】{loop_mode}, 第{loop_no}次执行失败, \n\t错误描述: {e}"
            self.context.log(error_message, step_code=self.step_code)
            result.success = False
            if on_error == AutoTestLoopErrorStrategy.STOP:
                raise StepExecutionError(error_message) from e
            return on_error == AutoTestLoopErrorStrategy.CONTINUE

        for child in child_results:
            result.children.append(child)
            if not child.success:
                result.success = False
                if on_error == AutoTestLoopErrorStrategy.STOP:
                    raise StepExecutionError(
                        f"【循环结构】{loop_mode}, "
                        f"子步骤执行失败(错误处理策略: 停止整个用例执行)\n\t"
                        f"错误描述: {child.error!r}"
                    )
                if on_error == AutoTestLoopErrorStrategy.BREAK:
                    self.context.log(
                        message=f"【循环结构】{loop_mode}, "
                                f"子步骤执行失败(错误处理策略: 中断循环)\n\t"
                                f"错误描述: {child.error!r}",
                        step_code=self.step_code
                    )
                    return False
                self.context.log(
                    message=f"【循环结构】{loop_mode}, "
                            f"子步骤执行失败(错误处理策略: 继续下一次循环)\n\t"
                            f"错误描述: {child.error!r}",
                    step_code=self.step_code
                )
        return True

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        校验循环模式与错误策略后，分派到对应的_execute_*_loop实现。

        校验顺序固定为 loop_mode → loop_on_error，任一为空或非法都不会进入轮次执行；
        各模式抛出的 StepExecutionError 原样上抛，其余异常经 format_step_error_message 格式化、
        写入 result.error 与执行日志后再转抛 StepExecutionError，统一由 execute() 收口置失败。

        :param result: 用于挂载子步骤结果与成败状态的执行结果对象
        :raises StepExecutionError: 循环模式/错误策略缺失或非法，或循环执行期出现其它异常
        :return: None
        """
        try:
            loop_mode: str = self.step.loop_mode
            if not loop_mode:
                raise StepExecutionError("【循环结构】请明确循环模式(仅允许选择: 次数循环, 列表循环, 字典循环, 条件循环)")
            try:
                loop_mode = AutoTestLoopMode(loop_mode)
            except (ValueError, TypeError) as e:
                raise StepExecutionError(f"【循环结构】循环模式[{loop_mode}]无效(仅允许选择: 次数循环, 列表循环, 字典循环, 条件循环)") from e
            on_error_str = self.step.loop_on_error
            if not on_error_str:
                raise StepExecutionError("【循环结构】请明确异常处理策略(仅允许选择: 继续下一次循环, 中断循环, 停止整个用例执行)")
            try:
                on_error = AutoTestLoopErrorStrategy(on_error_str)
            except (ValueError, TypeError) as e:
                raise StepExecutionError(f"【循环结构】异常处理策略{on_error_str}无效(仅允许选择: 继续下一次循环, 中断循环, 停止整个用例执行)") from e

            if loop_mode == AutoTestLoopMode.COUNT:
                await self._execute_count_loop(result, on_error)
            elif loop_mode == AutoTestLoopMode.LIST:
                await self._execute_list_loop(result, on_error)
            elif loop_mode == AutoTestLoopMode.DICT:
                await self._execute_dict_loop(result, on_error)
            elif loop_mode == AutoTestLoopMode.CONDITION:
                await self._execute_condition_loop(result, on_error)
            else:
                raise StepExecutionError(f"【循环结构】循环模式[{loop_mode}]无效(仅允许选择: 次数循环, 列表循环, 字典循环, 条件循环)")
        except StepExecutionError:
            raise
        except Exception as e:
            result.success = False
            result.error = AutoTestToolService.format_step_error_message(step=self.step, exception=e, is_child_step=False)
            self.context.log(result.error, step_code=self.step_code)
            raise StepExecutionError(result.error) from e

    def _resolve_loop_maximums(self) -> int:
        """
        解析次数循环的loop_maximums：支持字面量整数与${...}变量占位符，最终必须得到1-100的正整数。

        可接受的最终取值：int、整数值 float、纯数字字符串（允许带正负号，负数随后由区间校验拒绝）；
        布尔值、非整数浮点、非数字字符串与其它类型一律报错。

        :raises StepExecutionError: 参数为空/布尔值、占位符解析异常、取值类型非法或不在1-100区间
        :return: 解析后的最大循环次数（1-100）
        """
        loop_maximums_raw: str = self.step.loop_maximums
        if loop_maximums_raw is None or (isinstance(loop_maximums_raw, str) and not str(loop_maximums_raw).strip()):
            raise StepExecutionError("【循环结构】次数循环: 参数[loop_maximums]不允许为空")

        if isinstance(loop_maximums_raw, bool):
            raise StepExecutionError(f"【循环结构】次数循环模式: 参数[loop_maximums]不允许为布尔值")

        if isinstance(loop_maximums_raw, int):
            loop_maximums_resolved: int = loop_maximums_raw
        else:
            loop_maximums_raw = str(loop_maximums_raw).strip()
            try:
                loop_maximums_resolved: Any = self.context.resolve_placeholders(variables=loop_maximums_raw, step_code=self.step_code)
            except StepExecutionError:
                raise
            except Exception as e:
                raise StepExecutionError(f"【循环结构】次数循环模式: 参数[loop_maximums]占位符解析异常: {e}") from e

            # resolve_placeholders 对未定义变量会保留 ${var} 原样，故此处再按纯占位符形式补查一次变量池
            if isinstance(loop_maximums_resolved, str) and loop_maximums_resolved.startswith("${") and loop_maximums_resolved.endswith("}"):
                variable_name: str = loop_maximums_resolved[2:-1]
                try:
                    loop_maximums_resolved: Any = self.context.get_variable(variable_name)
                except KeyError as e:
                    raise StepExecutionError(f"【循环结构】次数循环模式: 参数[loop_maximums]占位符引用未定义, {e}") from e

        try:
            if isinstance(loop_maximums_resolved, bool):
                raise ValueError(f"布尔值不被允许")
            if isinstance(loop_maximums_resolved, int):
                loop_maximums = loop_maximums_resolved
            elif isinstance(loop_maximums_resolved, float):
                if not loop_maximums_resolved.is_integer():
                    raise ValueError(f"浮点数不被允许")
                loop_maximums = int(loop_maximums_resolved)
            elif isinstance(loop_maximums_resolved, str):
                text = loop_maximums_resolved.strip()
                if not re.fullmatch(r"[+-]?\d+", text):
                    raise ValueError(f"字符串不被允许")
                loop_maximums = int(text)
            else:
                raise ValueError(f"不支持的类型: {type(loop_maximums_resolved).__name__}, 值: {loop_maximums_resolved!r}")
        except ValueError as e:
            raise StepExecutionError(
                f"【循环结构】次数循环: 参数[loop_maximums]占位符解析值不被允许\n\t"
                f"原始值: {loop_maximums_raw!r}\n\t"
                f"解析值: {loop_maximums_resolved!r}\n\t"
                f"错误描述: {e}"
            ) from e

        if loop_maximums < 1 or loop_maximums > 100:
            raise StepExecutionError(f"【循环结构】次数循环: 参数[loop_maximums]必须为1到100之间的整数")
        return loop_maximums

    async def _execute_count_loop(self, result: StepExecutionResult, on_error: AutoTestLoopErrorStrategy) -> None:
        """
        次数循环模式：按loop_maximums（字面量或变量占位符，解析后强制1-100）执行固定次数，可选loop_interval间隔。
        每轮写入循环索引变量并执行子步骤树，失败按错误策略处理。

        明细快照：result.request 只记录解析后的 loop_maximums；loop_interval 仅用于轮次之间等待，
        最后一轮不再等待；BREAK/STOP 提前结束时直接返回，不补记"循环结束"日志。

        :param result: 用于挂载子步骤结果的StepExecutionResult
        :param on_error: 子步骤失败时的处理策略：CONTINUE=继续下一轮，BREAK=中断本层循环，STOP=抛出异常结束本步
        :raises StepExecutionError: loop_maximums 缺失或解析值非法（见 _resolve_loop_maximums）
        :return: None
        """
        loop_maximums: int = self._resolve_loop_maximums()
        result.request = {"loop_maximums": loop_maximums}

        loop_index: str = self.step.loop_index
        loop_interval: float = self.step.loop_interval

        self.context.log(message=f"【循环结构】次数循环开始: 最大循环次数: {loop_maximums}", step_code=self.step_code)
        for loop_no in range(1, loop_maximums + 1):
            should_continue = await self._execute_loop_round(
                result=result,
                on_error=on_error,
                loop_no=loop_no,
                loop_mode="次数循环",
                loop_message=f"【循环结构】次数循环, 第{loop_no}/{loop_maximums}次执行",
                include_variables=[StepVariablesBase(key=loop_index, value=loop_no, desc="")],
            )
            if not should_continue:
                return
            if loop_no < loop_maximums and loop_interval and loop_interval > 0:
                await self.context.sleep(loop_interval)

        self.context.log(message=f"【循环结构】次数循环结束: 共执行 {loop_maximums} 次", step_code=self.step_code)

    async def _execute_list_loop(self, result: StepExecutionResult, on_error: AutoTestLoopErrorStrategy) -> None:
        """
        列表循环模式：对可迭代对象（变量或 JSON 数组）逐项执行子步骤。
        每轮写入循环索引变量（从 1 起的序号）与循环数据变量（当前项）并执行子步骤树。

        明细快照：本模式不写 result.request，loop_iterable 只出现在执行日志中；
        字符串/字节串与不可迭代对象直接报错，空列表按"跳过循环"处理且不算失败；
        loop_interval 仅用于轮次之间等待，最后一轮不再等待。

        :param result: 用于挂载子步骤结果的StepExecutionResult
        :param on_error: 子步骤失败时的处理策略：CONTINUE=继续下一轮，BREAK=中断本层循环，STOP=抛出异常结束本步
        :raises StepExecutionError: loop_iterable 缺失、解析失败或解析结果不是可迭代对象
        :return: None
        """
        loop_iterable = self.step.loop_iterable
        if not loop_iterable:
            raise StepExecutionError("【循环结构】列表循环, 参数[loop_iterable]不允许为空")

        loop_var_index: str = self.step.loop_index
        loop_var_value: str = self.step.loop_value
        loop_interval: float = self.step.loop_interval
        try:
            iterable_obj = self.parse_iterable_source(loop_iterable)
            if isinstance(iterable_obj, (str, bytes)) or not hasattr(iterable_obj, "__iter__"):
                raise StepExecutionError(f"【循环结构】列表循环: 参数[loop_iterable]值类型不被允许, 当前类型: {type(iterable_obj).__name__}")

            # 转换为列表以便索引
            iterable_list = list(iterable_obj)
            total_items = len(iterable_list)
            if total_items == 0:
                self.context.log(message="【循环结构】列表循环: 参数[loop_iterable]值为空, 跳过循环", step_code=self.step_code)
                return
            self.context.log(
                message=f"【循环结构】列表循环开始: \n\t"
                        f"循环列表元素数: {total_items}\n\t"
                        f"循环索引变量名: {loop_var_index}\n\t"
                        f"循环数据变量名: {loop_var_value}",
                step_code=self.step_code
            )
            for idx, item in enumerate(iterable_list, start=1):
                should_continue = await self._execute_loop_round(
                    result=result,
                    on_error=on_error,
                    loop_no=idx,
                    loop_message=f"【循环结构】列表循环: \n\t第{idx}/{total_items}次执行\n\t数据: {item!r}",
                    loop_mode="列表循环",
                    include_variables=[
                        StepVariablesBase(key=loop_var_index, value=idx, desc=""),
                        StepVariablesBase(key=loop_var_value, value=item, desc=""),
                    ],
                )
                if not should_continue:
                    return
                if idx < total_items and loop_interval and loop_interval > 0:
                    await self.context.sleep(loop_interval)

            self.context.log(message=f"【循环结构】列表循环结束: 共执行 {total_items} 次", step_code=self.step_code)
        except StepExecutionError:
            raise
        except Exception as e:
            raise StepExecutionError(f"【循环结构】列表循环: {e}") from e

    async def _execute_dict_loop(self, result: StepExecutionResult, on_error: AutoTestLoopErrorStrategy) -> None:
        """
        字典循环模式：对字典逐 (key, value) 执行子步骤。
        每轮写入循环索引变量（从 1 起的序号）、循环键名变量、循环数据变量并执行子步骤树。

        明细快照：本模式不写 result.request；解析结果不是 dict 即报错，空字典按"跳过循环"处理且不算失败；
        loop_interval 仅用于轮次之间等待，最后一轮不再等待。

        :param result: 用于挂载子步骤结果的StepExecutionResult
        :param on_error: 子步骤失败时的处理策略：CONTINUE=继续下一轮，BREAK=中断本层循环，STOP=抛出异常结束本步
        :raises StepExecutionError: loop_iterable 缺失、解析失败或解析结果不是字典
        :return: None
        """
        loop_iterable = self.step.loop_iterable
        if not loop_iterable:
            raise StepExecutionError("【循环结构】字典循环, 参数[loop_iterable]不允许为空")

        loop_index: str = self.step.loop_index
        loop_key: str = self.step.loop_key
        loop_value: str = self.step.loop_value
        loop_interval: float = self.step.loop_interval

        try:
            # 解析字典对象来源
            dict_obj = self.parse_iterable_source(loop_iterable)
            # 验证是否为字典
            if not isinstance(dict_obj, dict):
                raise StepExecutionError(f"【循环结构】字典循环: 参数[loop_iterable]值类型不被允许, 当前类型: {type(dict_obj).__name__}")

            total_items = len(dict_obj)
            if total_items == 0:
                self.context.log(message="【循环结构】字典循环: 字典对象为空, 跳过循环", step_code=self.step_code)
                return

            self.context.log(
                message=f"【循环结构】字典循环开始: \n\t"
                        f"循环字典元素数: {total_items}\n\t"
                        f"循环索引变量名: {loop_index}\n\t"
                        f"循环键名变量名: {loop_key}\n\t"
                        f"循环数据变量名: {loop_value}",
                step_code=self.step_code
            )
            for idx, (key, value) in enumerate(dict_obj.items(), start=1):
                should_continue = await self._execute_loop_round(
                    result=result,
                    on_error=on_error,
                    loop_no=idx,
                    loop_message=f"【循环结构】字典循环: \n\t第{idx}/{total_items}次执行\n\t键={key}\n\t值={value}",
                    loop_mode=f"字典循环",
                    include_variables=[
                        StepVariablesBase(key=loop_index, value=idx, desc=""),
                        StepVariablesBase(key=loop_key, value=key, desc=""),
                        StepVariablesBase(key=loop_value, value=value, desc=""),
                    ],
                )
                if not should_continue:
                    return
                if idx < total_items and loop_interval and loop_interval > 0:
                    await self.context.sleep(loop_interval)

            self.context.log(f"【循环结构】字典循环结束: 共执行 {total_items} 次", step_code=self.step_code)

        except StepExecutionError:
            raise
        except Exception as e:
            raise StepExecutionError(f"【循环结构】字典循环执行异常: {e}") from e

    async def _execute_condition_loop(self, result: StepExecutionResult, on_error: AutoTestLoopErrorStrategy) -> None:
        """
        条件循环模式：while语义每轮先根据loop_conditions判断是否继续，仅当条件满足时才执行子步骤。
        条件一开始就不满足时子步骤一轮都不执行；超时（上限300秒，执行期兜底clamp存量超限数据）、
        条件评估异常、或子步骤按错误策略中断时退出；最多100轮（每轮一次子步骤树）防死循环。

        约定：loop_conditions与ConditionsBase一致（condition_expr/condition_compare/condition_value），
        经evaluate_condition评估；返回True表示继续循环，返回False表示结束循环。

        明细快照：result.request 只记录 loop_conditions，不含轮次与超时配置。
        边界：超时在每轮开始前检查（上一轮耗时可能已越过上限，需等下一轮开头才退出）；
        条件评估异常只记日志并置失败后退出，不再抛出；命中 LOOP_GUARD_LIMIT 则抛出 StepExecutionError 结束本步。

        :param result: 用于挂载子步骤结果的StepExecutionResult
        :param on_error: 子步骤失败时的处理策略：CONTINUE=继续下一轮，BREAK=中断本层循环，STOP=抛出异常结束本步
        :raises StepExecutionError: loop_conditions 缺失，或条件满足轮数达到防死循环上限
        :return: None
        """
        condition_config = self.step.loop_conditions
        if not condition_config:
            raise StepExecutionError("【循环结构】条件循环, 参数[loop_conditions]不允许为空")

        loop_timeout: float = self.step.loop_timeout
        loop_interval: float = self.step.loop_interval
        loop_index: str = self.step.loop_index
        # 执行期上限兜底：拦截存量数据中超出300秒的配置，超限记日志并按上限执行
        if loop_timeout and loop_timeout > self.CONDITION_LOOP_MAX_TIMEOUT:
            self.context.log(
                message=f"【循环结构】条件循环, 超时配置{loop_timeout}s超出上限{self.CONDITION_LOOP_MAX_TIMEOUT}s, 已按上限执行",
                step_code=self.step_code,
            )
            loop_timeout = float(self.CONDITION_LOOP_MAX_TIMEOUT)

        if hasattr(condition_config, "model_dump"):
            result.request = {"loop_conditions": condition_config.model_dump()}
        elif isinstance(condition_config, dict):
            result.request = {"loop_conditions": condition_config}
        else:
            result.request = {"loop_conditions": None}
        self.context.log(message=f"【循环结构】条件循环开始: \n\t循环超时配置: {loop_timeout}s", step_code=self.step_code)

        # loop_no：实际执行子步骤树的轮数（与循环索引变量、防死循环计数一致）
        loop_no = 0
        start_time = time.time()
        while True:
            if loop_timeout and loop_timeout > 0:
                elapsed = time.time() - start_time
                if elapsed >= loop_timeout:
                    self.context.log(
                        message=f"【循环结构】条件循环, 执行超时: \n\t"
                                f"累计执行: {loop_no}次\n\t"
                                f"当前耗时: {elapsed:.2f}s\n\t"
                                f"最大时间: {loop_timeout}s",
                        step_code=self.step_code
                    )
                    break

            # 先评估条件：不满足则不再执行本轮子步骤（while语义）
            try:
                matched = self.evaluate_condition(condition_config, operation_type="循环结构")
                if not matched:
                    self.context.log(
                        message=f"【循环结构】条件循环, 评估失败: \n\t本轮不执行子步骤, 已累计执行: {loop_no} 次",
                        step_code=self.step_code,
                    )
                    break
            except Exception as e:
                result.success = False
                result.error = f"【循环结构】条件循环, 评估异常: {e}"
                self.context.log(result.error, step_code=self.step_code)
                break

            if loop_no >= self.LOOP_GUARD_LIMIT:
                raise StepExecutionError(
                    f"【循环结构】条件循环, "
                    f"循环次数超过最大限制{self.LOOP_GUARD_LIMIT}, 疑似无限循环, 为保护系统安全已自动终止循环"
                )
            loop_no += 1
            should_continue = await self._execute_loop_round(
                result=result,
                on_error=on_error,
                loop_no=loop_no,
                loop_message=f"【循环结构】条件循环: 第 {loop_no} 轮(条件已满足)",
                loop_mode=f"条件循环",
                include_variables=[StepVariablesBase(key=loop_index, value=loop_no, desc="")],
            )
            if not should_continue:
                break
            if loop_interval and loop_interval > 0:
                await self.context.sleep(loop_interval)

        self.context.log(message=f"【循环结构】条件循环结束: 共执行 {loop_no} 次", step_code=self.step_code)

    def parse_iterable_source(self, source: Any) -> Any:
        """
        解析循环数据源：先做占位符替换，再根据变量名、JSON字符串或原值得到可迭代对象。

        解析顺序：占位符替换 → 结果仍为纯 ${var} 形式则查变量池 → 字符串尝试 JSON 解析 → 失败则按普通字符串返回。
        类型校验由调用方负责（列表循环拒绝字符串/字节串，字典循环要求 dict）。

        :param source: 数据源，可为${var}、JSON字符串或已解析对象
        :raises StepExecutionError: 占位符解析或变量取值失败
        :return: 可迭代对象（如 list、dict）；非 JSON 字符串时原样返回
        """
        try:
            # 先整体替换占位符；未定义变量会保留 ${var} 原样，故下面仍需按纯占位符形式补查变量池
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
    条件分支执行器：按 branch_items 顺序评估 if/elif/else，命中第一个分支即执行其子步骤（子步骤按 step_no 升序）。

    else 分支不评估条件、恒为命中，因此排在 else 之后的兄弟分支永远不会被执行（顺序由前端保证）。
    所有分支均未命中时本步 success 仍为 True，message 标记为跳过执行；
    子步骤失败只体现为 children 中的失败项，不改变本步 success 也不向上抛，
    仅当分支配置非法（branch_items 为空、if/elif 缺 branch_conditions）时本步才失败。
    """

    async def _execute_branch_children(self, branch_children: List[AutoTestStepTreeUpdateItem]) -> List[StepExecutionResult]:
        """
        执行命中分支的子步骤：按 step_no 升序逐个构建执行器并执行。

        单个子步抛出的异常在此就地转为 success=False 的失败结果（错误信息经 format_step_error_message
        记录到父步日志），因此不会中断同分支内的后续子步骤，也不会把异常传给调用方。

        :param branch_children: 命中分支的子步骤定义列表
        :return: 子步骤执行结果列表；被跳过的子步骤（execute 返回 None）不进入列表
        """
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
        """
        顺序评估分支并执行第一个命中分支下的子步骤。

        执行快照：result.request 固定写入 branch_match（命中分支下标，从0起）与 branch_items
        （只含命中的那一条且不含 branch_children）；全部未命中时两者保持 None。

        :param result: 用于挂载子步骤结果、命中信息与成败状态的执行结果对象
        :return: None
        """
        try:
            branch_items = self.step.branch_items
            if not branch_items:
                raise StepExecutionError("【条件分支】参数异常: branch_items 为空，条件分支步骤必须配置 branch_items")

            result.request = {"branch_items": None, "branch_match": None}

            for i, branch in enumerate(branch_items):
                if branch.branch_type == AutoTestBranchType.ELSE:
                    # else 不评估条件，恒命中；其后的兄弟分支因此永远不会被走到
                    matched = True
                else:
                    if not branch.branch_conditions:
                        raise StepExecutionError(f"【条件分支】第{i + 1}个分支({branch.branch_type})缺少 branch_conditions")
                    matched = self.evaluate_condition(branch.branch_conditions, operation_type="条件分支")

                if matched:
                    desc = branch.branch_desc or branch.branch_type
                    result.success = True
                    result.message = f"【条件分支】命中分支[{branch.branch_type}]: {desc}"
                    # 执行快照只记命中的那一条（不含 branch_children）
                    result.request["branch_match"] = i
                    result.request["branch_items"] = [{
                        "branch_type": branch.branch_type,
                        "branch_conditions": branch.branch_conditions.model_dump() if branch.branch_conditions else None,
                        "branch_desc": branch.branch_desc,
                    }]
                    self.context.log(result.message, step_code=self.step_code)
                    try:
                        branch_children = branch.branch_children or []
                        child_results = await self._execute_branch_children(branch_children)
                        for child in child_results:
                            result.children.append(child)
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
    Python 代码步骤执行器：在受限沙箱中执行 code，将返回的 dict/list 转为提取项与响应快照，再执行本步断言。

    代码返回 None 或空 dict/空 list 时不写 extract_variables 与 response（视作无返回值）；
    断言只支持变量池数据源（session_variables/变量池），查找顺序为 defined → session → 本步返回值。
    """

    @staticmethod
    def _pack_python_executive_result(
            executive_result: Union[Dict[str, Any], List[Dict[Any, Any]]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        将 Python 步骤返回值转为提取项与变量池增量。

        Dict：每个键生成一条提取项，变量池增量即该 dict 本身；
        List：整体作为名为 result 的单条提取项，变量池增量为 {"result": [...]}。

        :param executive_result: run_python_code 的返回值（dict 或 list）
        :return: (提取项列表, 供断言查找表使用的变量池增量)
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

        计时窗口只覆盖 run_python_code 本身（response_elapsed 不含提取打包与断言耗时）；
        原始代码快照由 run_python_code 写入 result.request（request_code/request_args_type）。

        :param result: 本步执行结果
        :raises StepExecutionError: code 缺失、沙箱执行失败、返回值打包失败或存在断言失败项
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
                        "response_elapsed": f"{(executive_ed_time - executive_st_time).total_seconds():.2f}",
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
    等待步骤执行器：按 step.wait 秒数挂起当前步骤。

    wait 为 None 时直接报错（不是"不等待"）；有效区间 0-300 秒，超出由 StepExecutionContext.sleep 拒绝。
    """

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        根据 step.wait 指定的秒数挂起当前步骤。

        :param result: 本步执行结果（等待步骤不写入请求/响应快照）
        :raises StepExecutionError: wait 未配置、超出0-300区间或等待过程被中断
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

        本步不涉及提取（extract_variables 传空列表）；逐项断言结果由管线写入 result.assert_validators，
        但 result.response 只在全部通过后生成，失败时该汇总快照缺省为空。

        :param result: 本步执行结果
        :raises StepExecutionError: assert_validators 为空、子项类型非法或存在断言失败项
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
                "response_elapsed": f"{(executive_ed_time - executive_st_time).total_seconds():.2f}",
            }
        except StepExecutionError:
            raise
        except Exception as e:
            result.success = False
            result.error = AutoTestToolService.format_step_error_message(step=self.step, exception=e, is_child_step=False)
            self.context.log(result.error, step_code=self.step_code)
            raise StepExecutionError(result.error) from e


class ExtractStepExecutor(BaseStepExecutor):
    """
    提取步骤执行器：按 extract_variables 执行变量提取，规则/来源/管线与 TCP/HTTP 步骤提取对齐。

    独立提取步骤无请求/响应报文时，数据源通常为变量池（session_variables/变量池）；
    提取成功项经管线写回会话变量池，供后续步骤以 ${name} 占位符引用。
    """

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        执行步骤上的变量提取规则，失败项通过apply_extract_and_assert转为StepExecutionError。

        本步不做断言（assert_validators 传空列表）；提取结果由管线写入 result.extract_variables，
        但 result.response 只在全部成功后生成，失败时该汇总快照缺省为空。

        :param result: 本步执行结果
        :raises StepExecutionError: extract_variables 为空、子项类型非法或存在提取失败项
        :return: None
        """
        try:
            extract_variables = self.step.extract_variables
            if not extract_variables:
                raise StepExecutionError("【提取】缺少必要配置: extract_variables")
            for extract_item in extract_variables:
                if not isinstance(extract_item, StepExtractVariableItem):
                    raise StepExecutionError(
                        f"【提取】子项参数异常: \n\t"
                        f"预期类型: StepExtractVariableItem\n\t"
                        f"实际类型: {type(extract_item).__name__}"
                    )

            executive_st_time: datetime = datetime.now()
            # 与 TCP/HTTP 共用提取/断言管线；提取成功项经 finished_variables 自动写回会话变量池
            self.apply_extract_and_assert(
                result,
                step_label="提取",
                extract_variables=extract_variables,
                assert_validators=[],
            )
            executive_ed_time: datetime = datetime.now()
            result.response = {
                "extract_count": len(extract_variables),
                "extract_passed": sum(1 for item in result.extract_variables if item.get("success")),
                "extract_failed": sum(1 for item in result.extract_variables if not item.get("success")),
                "response_elapsed": f"{(executive_ed_time - executive_st_time).total_seconds():.2f}",
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
    用户变量步骤执行器：解析 step.session_variables 中的占位符后合并进会话变量池。

    未配置变量时本步直接成功且不写任何快照；同名变量按 key 覆盖会话池中的已有值。
    """

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        解析 step.session_variables 中的占位符并合并到会话变量池。

        :param result: 本步执行结果
        :raises StepExecutionError: 占位符解析或写入会话池失败
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


class BaseQuoteCaseStepExecutor(BaseStepExecutor):
    """
    引用类步骤执行器基类：以「壳步骤」形式加载被引用用例的根步骤树，按 step_no 顺序执行并挂到 result.children。

    子类通过覆盖类属性声明策略：

        - quote_step_label：日志与错误信息前缀；
        - allowed_quote_case_types：查询被引用用例时按 case_type__in 过滤的用例类型元组；
        - allowed_append_fields_container / allowed_merge_and_override_fields：引用步骤自身可追加的容器字段名，以及是否把它们合并进内层 HTTP/TCP 步骤；
        - use_isolated_session_pool：引用域是否使用独立会话变量池（执行后整体回灌宿主，引用值覆盖宿主同名）；
        - allowed_own_dataset：是否按(宿主 case_id, 引用步骤 step_code)预载数据源快照，供引用链内层 HTTP/TCP 步骤消费；
        - resolve_own_defined_variables：基类统一关闭（容器层缺少 SERVER_*/TARGET_* 内置变量，解析自身变量会误报未定义）。

    被引用用例 state=1（软删）不会被加载；加载失败本步失败，用例无根步骤则只记日志并视为成功。
    内层根步骤失败仅把本步 success 置 False 并保留 children 明细，不向上抛异常。
    """

    # 日志/错误信息前缀
    quote_step_label: str = "引用公共步骤"
    # 允许引用的用例类型集合，加载被引用用例时按此变量过滤
    allowed_quote_case_types: Tuple[AutoTestCaseType, ...] = ()
    # 引用步骤自身可追加的容器字段名列表（是否真正合并由 allowed_merge_and_override_fields 决定）
    allowed_append_fields_container: Tuple[str, ...] = ("defined_variables", "extract_variables", "assert_validators")
    # 引用步骤自身追加的三类容器字段（defined_variables/extract_variables/assert_validators）是否合并进内层HTTP/TCP请求步骤执行
    # （引用公共接口开启：追加数据保存在引用步骤上，随本次引用执行生效；引用公共脚本关闭：被引用内容保持原样只读复用）
    allowed_merge_and_override_fields: bool = False
    # 容器层不解析自身defined_variables（追加数据由内层HTTP/TCP步骤合并后解析，容器层缺少SERVER_*/TARGET_*内置变量，会误报变量未定义）
    resolve_own_defined_variables = False
    # 会话变量池半隔离：开启后引用域执行前以被引用用例聚合结果替换上下文变量池（独享、宿主池不可见），执行结束后整个引用池按key回灌宿主（引用覆盖宿主同名）
    use_isolated_session_pool: bool = False
    # 引用步骤自身挂数据源：开启后执行内层步骤前按(宿主case_id, 引用步骤step_code)预载数据源快照注入context，供引用链内层HTTP/TCP步骤数据驱动（仅引用公共接口开启；引用公共脚本链中恒为None以屏蔽外层引用接口数据源）
    allowed_own_dataset: bool = False

    def _merge_and_override_fields(self, quote_step: AutoTestStepTreeUpdateItem) -> AutoTestStepTreeUpdateItem:
        """
        将引用步骤自身追加的 defined_variables/extract_variables/assert_validators 合并进内层 HTTP/TCP 请求步骤。

        仅 allowed_merge_and_override_fields 开启且步骤类型为 HTTP/TCP 时合并（其它类型没有响应报文上下文）；
        合并顺序为原数据在前、追加在后；defined_variables 会先剔除与追加项同名的原变量，避免重复 key 进入变量池，
        变量查找取最后一个同名项，因此追加项天然覆盖原值；同名提取/断言则按执行先后自然覆盖。
        返回的是 model_copy 副本，不修改被引用用例树上的原对象。

        :param quote_step: 被引用用例的待执行根步骤模型
        :return: 合并追加字段后的步骤模型；开关关闭/类型不匹配/无可合并字段时原样返回
        """
        if not self.allowed_merge_and_override_fields:
            return quote_step
        if quote_step.step_type not in (AutoTestStepType.HTTP, AutoTestStepType.TCP):
            return quote_step
        update: Dict[str, Any] = {}
        for field_name in self.allowed_append_fields_container:
            appended: List[Any] = list(getattr(self.step, field_name) or [])
            if not appended:
                continue
            original: List[Any] = list(getattr(quote_step, field_name) or [])
            if field_name == "defined_variables":
                appended_keys = {v.key for v in appended if isinstance(v, StepVariablesBase) and v.key}
                original = [v for v in original if not (isinstance(v, StepVariablesBase) and v.key in appended_keys)]
            update[field_name] = original + appended
        if not update:
            return quote_step
        return quote_step.model_copy(update=update)

    def _build_quote_session_pool(self, quote_case_instance: Any, quote_roots: List[AutoTestStepTreeUpdateItem]) -> List[StepVariablesBase]:
        """
        构建被引用用例的原始初始变量池（未做占位符解析），聚合口径与 AutoTestStepCrud.execute_single_case 一致：
        用例级 session_variables 在前为基底、树内用户变量步骤的收集结果在后，同名 key 由后者覆盖。

        :param quote_case_instance: 被引用用例模型实例（取其用例级 session_variables 存储值）
        :param quote_roots: 被引用用例根步骤列表（收集其中用户变量步骤的产出）
        :return: 按 key 去重后的原始初始变量池；解析求值由调用方统一执行
        """
        stored: List[StepVariablesBase] = step_variables_list_from_storage(getattr(quote_case_instance, "session_variables", None))
        collected: List[StepVariablesBase] = AutoTestToolService.collect_session_variables(quote_roots)
        merged: Dict[str, StepVariablesBase] = {}
        for item in [*stored, *collected]:
            if item.key:
                merged[item.key] = item
        return list(merged.values())

    def _merge_back_session_pool(self, host_pool: List[StepVariablesBase], quote_pool: List[StepVariablesBase]) -> List[StepVariablesBase]:
        """
        将执行后的引用池整体回灌宿主池：按 key 合并，同名变量以引用池为准。

        :param host_pool: 进入引用域前的宿主变量池快照（未被引用域污染的引用）
        :param quote_pool: 引用域执行结束后的完整变量池（含初始变量与执行产出）
        :return: 回灌后的宿主变量池
        """
        merged: Dict[str, StepVariablesBase] = {v.key: v for v in host_pool if v.key}
        for item in quote_pool:
            if item.key:
                merged[item.key] = item
        return list(merged.values())

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        加载并执行被引用用例的根步骤树；被跳过的子步（execute 返回 None）不挂入 children。

        执行顺序：校验 quote_case_id → 标记引用链（executing_quote_case_id/executing_parent_step_id）→
        查被引用用例（按 allowed_quote_case_types 与 state 过滤）→ 取根步骤树 → 构建引用初始变量池
        （隔离模式替换上下文池，共享模式按输出主导并入宿主池）→ 可选预载引用步骤自身数据源快照 →
        根步骤按 step_no 升序补齐运行时字段后逐个执行 → finally 恢复引用链标记与数据源快照、回灌变量池。

        :param result: 本步执行结果，子步骤结果写入 children
        :raises StepExecutionError: quote_case_id 缺失、被引用用例不存在/类型不符/查询异常或步骤树加载失败
        :return: None
        """
        allowed_types_desc: str = "、".join(t.value for t in self.allowed_quote_case_types)
        previous_quote_case_id: Optional[int] = getattr(self.context, "executing_quote_case_id", None)
        previous_parent_step_id: Optional[int] = getattr(self.context, "executing_parent_step_id", None)
        host_pool: List[StepVariablesBase] = []
        quote_pool: Optional[List[StepVariablesBase]] = None
        previous_quote_dataset_name: Optional[str] = getattr(self.context, "quote_dataset_name", None)
        previous_quote_dataset_snapshot: Optional[Dict[str, Dict[str, Any]]] = getattr(
            self.context, "quote_dataset_snapshot", None
        )
        try:
            quote_case_id = self.step.quote_case_id
            if not quote_case_id:
                raise StepExecutionError(f"【{self.quote_step_label}】缺少必要配置: quote_case_id")

            database_crud_services = await self.get_services()
            # 标记引用链：非空表示当前正在执行被引用用例（引用链内层数据源加载据此短路）
            self.context.executing_quote_case_id = quote_case_id
            # 将引用容器步骤ID标记为执行中父级，供被引用用例根步骤明细归属引用容器
            self.context.executing_parent_step_id = self.step_id
            try:
                quote_case_instance = await database_crud_services.case_curd.get_by_conditions(
                    only_one=True,
                    on_error=True,
                    id=quote_case_id,
                    case_type__in=[t.value for t in self.allowed_quote_case_types],
                    state__not=1,
                )
            except (ParameterException, NotFoundException) as e:
                raise StepExecutionError(
                    f"【{self.quote_step_label}】引用用例ID: {quote_case_id}不存在或用例类型不属于({allowed_types_desc})\n\t错误描述: {e.message}"
                ) from e
            except Exception as e:
                raise StepExecutionError(f"【{self.quote_step_label}】引用用例ID: {quote_case_id})查询异常\n\t错误描述: {e}") from e

            quote_case_dict = await quote_case_instance.to_dict(
                include_fields={"id", "case_code", "case_name"},
                replace_fields={"id": "case_id"}
            )
            quote_case_name: str = quote_case_dict["case_name"]
            try:
                load = await database_crud_services.step_curd.get_case_tree(case_id=quote_case_id)
                quote_roots = load.root_steps
                if not quote_roots:
                    self.context.log(
                        f"【{self.quote_step_label}】用例(id={quote_case_id})暂无任何可执行步骤数据",
                        step_code=self.step_code
                    )
                    return
            except Exception as e:
                raise StepExecutionError(
                    f"【{self.quote_step_label}】获取用例(id={quote_case_id})步骤树数据异常, 错误描述: {e}"
                ) from e

            # 进入被引用用例：先按宿主用例同款口径构建其初始变量池(用例级session_variables为基底、树内用户变量覆盖)。
            # 这是BaseQuoteCaseStepExecutor的默认初始化动作，只取决于被引用用例自身；与宿主的关系仅体现在下方池作用域策略。
            quote_initial_pool: List[StepVariablesBase] = self._build_quote_session_pool(quote_case_instance, quote_roots)
            if self.use_isolated_session_pool:
                # 半隔离(公共脚本)：宿主池暂存引用，被引用用例在自身解析后的独立池上执行，结束后整体回灌宿主。
                # initialize_session_variables返回的列表与context.session_variables同一对象，执行期就地追加对finally回灌可见。
                host_pool = self.context.session_variables
                quote_pool = self.context.initialize_session_variables(quote_initial_pool)
                self.context.log(
                    f"【{self.quote_step_label}】初始化引用域独立变量池({len(quote_pool)}项), 宿主变量池已隔离",
                    step_code=self.step_code
                )
            else:
                # 共享(公共接口)：被引用用例初始池解析后按"输出主导"并入宿主池，同名覆盖宿主，
                # 与半隔离收口的回灌方向统一（引用池覆盖宿主同名）；被引用用例步骤直接在宿主池上执行，产出即时回灌宿主。
                # 必须就地update_variables而非整段替换：嵌套引用时外层半隔离池局部变量与context.session_variables
                # 须保持同一列表对象，替换会使外层finally回灌读到执行前的旧池而丢失内层产出。
                resolved_initial: List[StepVariablesBase] = self.context.resolve_placeholders(quote_initial_pool) or []
                if resolved_initial:
                    self.context.update_variables(resolved_initial, scope="session_variables")
                self.context.log(
                    f"【{self.quote_step_label}】输出主导并入被引用用例(id={quote_case_id})初始变量池"
                    f"({len(resolved_initial)}项, 同名覆盖宿主)",
                    step_code=self.step_code
                )

            if self.allowed_own_dataset and getattr(self.step, "data_source_id", None) and self.context.dataset_name:
                # 引用步骤自身挂数据源：数据源行落在宿主用例(case_id+引用步骤step_code)，executing_quote_case_id传None绕过loader对引用链的短路
                quote_snapshot: Optional[Dict[str, Dict[str, Any]]] = await AutoTestToolService.load_dataset_for_request_step(
                    case_id=self.case_id,
                    step_code=self.step_code,
                    dataset_name=self.context.dataset_name,
                    executing_quote_case_id=None,
                )
                self.context.quote_dataset_name = self.context.dataset_name
                self.context.quote_dataset_snapshot = quote_snapshot
                if quote_snapshot is not None:
                    self.context.log(
                        f"【{self.quote_step_label}】加载数据源场景({self.context.dataset_name})成功, 供内层请求步骤数据驱动",
                        step_code=self.step_code
                    )
                else:
                    self.context.log(
                        f"【{self.quote_step_label}】数据源场景({self.context.dataset_name})在引用步骤数据源中未命中, 内层请求步骤不做数据驱动替换",
                        step_code=self.step_code
                    )
            else:
                # 开关关闭(引用公共脚本)、未挂数据源或本轮无数据场景：显式清空，屏蔽外层引用接口残留快照泄漏进本引用链
                self.context.quote_dataset_name = None
                self.context.quote_dataset_snapshot = None

            self.context.log(
                f"【{self.quote_step_label}】执行用例(id={quote_case_id}, name={quote_case_name})开始",
                step_code=self.step_code
            )
            ordered_steps = sorted(
                [prepare_step_tree_item_for_execution(s) for s in quote_roots],
                key=lambda item: (item.step_no or 0),
            )
            for quote_step in ordered_steps:
                try:
                    merged_step = self._merge_and_override_fields(quote_step)
                    executor = StepExecutorFactory.create_executor(merged_step, self.context)
                    child_result = await executor.execute()
                    if child_result is None:
                        continue
                    result.children.append(child_result)
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
                    result.children.append(failed_result)
            self.context.log(
                f"【{self.quote_step_label}】执行用例(id={quote_case_id}, name={quote_case_name})结束",
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
            # 恢复外层引用域数据源快照（嵌套引用时的正确回退）
            self.context.quote_dataset_name = previous_quote_dataset_name
            self.context.quote_dataset_snapshot = previous_quote_dataset_snapshot
            # 半隔离收口：整个执行后引用池按key回灌宿主（引用覆盖宿主同名），无论内层步骤成功或异常
            if quote_pool is not None:
                merged_host_pool: List[StepVariablesBase] = self._merge_back_session_pool(
                    host_pool=host_pool, quote_pool=quote_pool
                )
                self.context.session_variables = merged_host_pool
                self.context.log(
                    f"【{self.quote_step_label}】引用域变量池整体回灌宿主池({len(merged_host_pool)}项), 同名变量以引用域为准",
                    step_code=self.step_code
                )
            # 恢复上一级引用用例标识（支持嵌套引用时的正确回退）
            try:
                self.context.executing_quote_case_id = previous_quote_case_id
                self.context.executing_parent_step_id = previous_parent_step_id
            except Exception:
                pass


class QuotePublicApiStepExecutor(BaseQuoteCaseStepExecutor):
    """
    引用公共接口执行器：仅允许引用 case_type=PUBLIC_API 的公共用例。

    引用步骤自身追加的局部变量/提取/断言会合并进内层 HTTP/TCP 请求步骤（原数据在前、追加在后）；
    并开启引用步骤自身挂数据源：按(宿主 case_id, 引用步骤 step_code)预载快照注入引用链，供内层请求步骤数据驱动。
    未开启会话池隔离，被引用用例的初始变量与执行产出按输出主导并入宿主池。
    """

    quote_step_label = "引用公共接口"
    allowed_quote_case_types = (AutoTestCaseType.PUBLIC_API,)
    allowed_merge_and_override_fields = True
    allowed_own_dataset = True


class QuotePublicScriptStepExecutor(BaseQuoteCaseStepExecutor):
    """
    引用公共脚本执行器：仅允许引用 case_type=PUBLIC_SCRIPT 的公共用例。

    不合并引用步骤的追加字段、不加载引用步骤自身数据源（保持被引用内容原样只读复用）；
    开启会话变量池半隔离：引用域独享被引用用例聚合出的变量池，执行结束后整个引用池回灌宿主池。
    """

    quote_step_label = "引用公共脚本"
    allowed_quote_case_types = (AutoTestCaseType.PUBLIC_SCRIPT,)
    use_isolated_session_pool = True


class TcpStepExecutor(BaseStepExecutor):
    """
    TCP 步骤执行器：复用 HTTP 步骤的「数据驱动替换 → 占位符解析 → 请求发送 → 变量提取 → 断言」链路。

    约定字段（沿用步骤基础字段，避免新增 schema 破坏兼容）：

        - request_url 为 TCP host（如 127.0.0.1 或域名）、request_port 为 TCP port（字符串或数字）；
          命中执行配置（APP）时两者整体被 config_host/config_port 覆盖；最终任一为空或端口无法转 int 即失败，
          引擎不做端口区间校验。
        - request_project_id 与 request_config_name 用于提取/断言的引用解析与请求快照，两者均必填；
          命中执行配置时 request_config_name 会被 config_name 覆盖。
        - 载荷选择见 select_tcp_payload：JSON 取 request_body，RAW/XML 取 request_text，
          其它或未配置时 request_text 优先、仅当其为空才回落 request_body。
        - XML 请求（request_args_type=XML 或以 '<' 开头）走 resolve_xml_placeholders，其余走 resolve_placeholders。
        - TCP 帧配置由 resolve_tcp_frame_config 统一推导，帧字段相互独立不互斥，优先级：
          进制数≠不使用 → 长度前缀；否则配置了请求或响应结束符 → 结束符；均未配置 → RAW。
        - 读取超时取 tcp_response_timeout（未配置时缺省10秒），连接超时未单独暴露，
          由 AioTcpClient 缺省为读取超时；单次响应读取上限 TCP_MAX_RESPONSE_BYTES（10MB）。
        - tcp_connect_type=LONG 尚未实现，会按短连接降级执行；SEND_ONLY 只发不收，响应文本为空且 response_bytes=0。
    """

    def collect_builtin_variables(self) -> List[StepVariablesBase]:
        """
        采集TCP步骤内置环境变量：SERVER_*/TARGET_*（TARGET_PATH固定为空字符串）。
        目标HOST/PORT取自执行配置，未命中时TARGET_*不注入并记录内置数据获取失败日志。

        :return: 内置变量列表
        """
        current_step_config: Optional[StepsExecuteConfigBase] = self.get_execute_config(
            expected_config_type=AutoTestConfigNodeType.APP,
        )
        target_host: Optional[str] = current_step_config.config_host if current_step_config else None
        target_port: Optional[str] = (
            str(current_step_config.config_port) if current_step_config and current_step_config.config_port else None
        )
        return collect_builtin_step_variables(
            target_host=target_host,
            target_port=target_port,
            target_path="",
            existing_keys=self.existing_variable_keys(),
            log=lambda msg: self.context.log(msg, step_code=self.step_code),
        )

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        解析执行主机/端口与请求报文，发送TCP请求并完成变量提取与断言。

        流程：执行配置覆盖 host/port → 数据驱动替换（XML 与 JSON 两条替换路径）→ 占位符解析 →
        select_tcp_payload 选载荷 → 推导帧配置与超时 → 写 result.request 快照 → 单次发送并本地解析响应后
        记账 result.response → 复用提取/断言管线（请求侧取值由 resolve_tcp_request_extract_sources 归一口径）。
        请求只发送一次，解析响应失败不会重发。

        :param result: 本步执行结果
        :raises StepExecutionError: 主机/端口缺失或非法、request_project_id/request_config_name 缺失、
                                    连接与响应解析失败、或提取/断言存在失败项
        :return: None
        """
        try:
            env_name: Optional[str] = None
            request_url = (self.step.request_url or "").strip()
            request_port = self.step.request_port
            current_step_config: Optional[StepsExecuteConfigBase] = self.get_execute_config(
                expected_config_type=AutoTestConfigNodeType.APP,
            )
            if current_step_config:
                request_url: str = current_step_config.config_host
                request_port: str = current_step_config.config_port
                self.step.request_config_name = current_step_config.config_name
                env_name = current_step_config.env_name
            if not any((env_name, request_url, request_port)):
                error_message: str = f"【TCP请求】执行配置异常, 存在未明确项"
                raise StepExecutionError(error_message)
            if not request_url or not request_port:
                raise StepExecutionError(f"【TCP请求】请求主机[{request_url!r}]或请求端口[{request_port!r}]不是有效的配置")

            # 参数化驱动：与HTTP步骤同一加载口径（引用链内层直接消费引用壳预载的快照）
            step_struct = await self.load_step_dataset(result)

            request_project_id: Optional[int] = self.step.request_project_id
            request_config_name: Optional[str] = self.step.request_config_name
            if not request_project_id:
                raise StepExecutionError("【TCP请求】参数[request_project_id]不能为空")
            if not request_config_name:
                raise StepExecutionError("【TCP请求】参数[request_config_name]不能为空")

            request_body = AutoTestToolService.try_serialize_request_body(self.step.request_body)
            request_text = self.step.request_text
            if AutoTestToolService.has_dataset_payload(step_struct):
                is_xml = AutoTestToolService.resolve_datagram_is_xml(self.step.request_args_type, request_text, request_body)
                if is_xml:
                    xml_source = request_text if isinstance(request_text, str) and request_text.strip() else (
                        request_body if isinstance(request_body, str) else None
                    )
                    request_text = AutoTestToolService.replace_xml_datagram(
                        body_map=step_struct.get("body") or {},
                        request_text=xml_source,
                        logger_object=lambda msg: self.context.log(msg, step_code=self.step_code),
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
                        # TCP无请求头：HEAD分区不参与正文替换，避免误改同名body字段
                        head_map=None,
                        body_map=step_struct.get("body") or {},
                        request_headers=None,
                        request_body=body_for_replace,
                        form_data=None,
                        urlencoded=None,
                        logger_object=lambda msg: self.context.log(msg, step_code=self.step_code),
                    )
                    request_body = out["request_body"]
                    if isinstance(request_body, (dict, list)):
                        request_text = orjson.dumps(request_body).decode("UTF-8")
                    elif isinstance(request_body, str) and request_body:
                        request_text = request_body

            # 历史/导入数据可能把 XML 存在 request_body 字符串中；发送前回落到 request_text，
            # 避免 XML 步骤因 request_text 为空而发出空报文。
            if not request_text and isinstance(request_body, str) and (
                    self.step.request_args_type == AutoTestReqArgsType.XML
                    or request_body.lstrip().startswith("<")
            ):
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

            frame_config = resolve_tcp_frame_config(self.step)
            max_response_bytes = TCP_MAX_RESPONSE_BYTES
            connect_td, read_td = parse_tcp_timeouts(None, self.step.tcp_response_timeout)

            # 发送前先落请求快照（含帧配置与最终 payload），便于落库与排障
            result.request = {
                "request_url": request_url,
                "request_port": request_port,
                "request_env_name": env_name,
                "request_args_type": request_args_type_raw,
                "tcp_frame_mode": frame_config.frame_mode.value,
                "tcp_radix": self.step.tcp_radix,
                "tcp_radix_length": frame_config.radix_length,
                "tcp_datagram_length": self.step.tcp_datagram_length,
                "tcp_request_end_symbol": self.step.tcp_request_end_symbol,
                "tcp_response_end_symbol": self.step.tcp_response_end_symbol,
                "tcp_connect_type": self.step.tcp_connect_type,
                "tcp_encoding": frame_config.encoding,
                "tcp_hex_string": frame_config.hex_string,
                "tcp_response_timeout": self.step.tcp_response_timeout,
                "request_body": request_body,
                "request_text": request_text,
                "payload": payload,
            }

            if frame_config.long_connection:
                # 长连接暂未实现：按短连接降级执行，避免阻断步骤
                self.context.log("【TCP请求】连接方式为长连接, 暂未实现, 已按短连接降级执行", step_code=self.step_code)

            start = time.perf_counter()
            async with AioTcpClient(
                    timeout=read_td or timedelta(seconds=10),
                    connect_timeout=connect_td,
                    length_field_size=frame_config.radix_length,
                    max_response_bytes=max_response_bytes,
            ) as client:
                utils = await client.tcp(
                    request_url,
                    int(request_port),
                    payload,
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
                # 只请求一次：获取原始字节后本地解析，避免解析失败时重发TCP请求
                resp_bytes = await utils.bytes_resp()
                parsed = parse_tcp_response(
                    resp_bytes,
                    encoding=frame_config.encoding,
                    hex_string=frame_config.hex_string,
                )
                resp_text = parsed.response_text
                response_json = parsed.response_json

            elapsed = round(time.perf_counter() - start, 2)
            result.response = {
                "response_text": resp_text,
                "response_elapsed": f"{elapsed:.2f}",
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
    数据库请求步骤执行器：按 database_operates 顺序执行多条 SQL（先解析占位符），结果写入本步提取项与变量池。

    每条操作自动产出两个提取变量：variable_name（SQL 结果集）与 variable_name_count（行数）；
    database_searched=True 时某条 SQL 返回非空结果集即终止后续 SQL（查到即止）。
    单条操作失败只置本步失败并记录错误，不中断后续操作；StepExecutionError（配置/参数非法）则立即上抛。
    """

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        顺序执行 database_operates 中的 SQL，合并自动提取项并执行步骤自定义的提取/断言。

        执行顺序：逐条解析操作配置（执行配置覆盖 config_name/database_name）→ 占位符解析 →
        project_id 缺失时按 project_name 回查 → 取连接池执行 SQL → 记录自动提取项与请求/响应快照 →
        非空结果集触发查到即止 → 循环结束后统一写 result.request/result.response →
        以自动提取结果作为最高优先级查找项，复用提取/断言管线。

        :param result: 本步执行结果
        :raises StepExecutionError: database_operates 缺失/非法、必填参数为空、extract_variables 类型非法，
                                    或提取/断言存在失败项
        :return: None
        """
        try:
            merge_operates_env_name: Optional[str] = None
            display_config_name: Optional[str] = self.step.request_config_name
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
            # 逐条执行并同步累积请求/响应快照（每项含 variable_name、sql_data、sql_count 等），供报告与「提取/断言」根据存储变量名匹配
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
                current_op_execute_cfg: Optional[StepsExecuteConfigBase] = self.get_execute_config(
                    database_operates_index=db_idx,
                    expected_config_type=AutoTestConfigNodeType.DB,
                )
                if current_op_execute_cfg:
                    env_name: str = str(current_op_execute_cfg.env_name or "").strip()
                    config_host: str = current_op_execute_cfg.config_host
                    config_port: str = current_op_execute_cfg.config_port
                    config_name: str = current_op_execute_cfg.config_name
                    database_name: str = current_op_execute_cfg.database_name
                    db_operate.config_name = config_name
                    db_operate.database_name = database_name
                    if display_config_name:
                        display_config_name += f", ({db_idx}){db_operate.config_name}"
                    else:
                        display_config_name = f"({db_idx}){db_operate.config_name}"
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
                    # 解析SQL与配置字段中的占位符（variable_name 不参与解析，自动生成的 _count 名以其原值为前缀）
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
                        "env_name": env_name,
                        "project_id": operate_project_id,
                        "project_name": operate_project_name,
                        "config_name": operate_config_name,
                        "database_name": operate_database_name,
                        "config_host": config_host,
                        "config_port": config_port,
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
                        "env_name": env_name,
                        "project_id": operate_project_id,
                        "project_name": operate_project_name,
                        "config_name": operate_config_name,
                        "database_name": operate_database_name,
                        "config_host": config_host,
                        "config_port": config_port,
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
                "request_config_name": display_config_name,
            }
            result.response = {
                "response_body": database_operates_response,
                "response_text": response_text_str,
                "response_elapsed": f"{(executive_ed_time - executive_st_time).total_seconds():.2f}",
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
    Redis 请求步骤执行器：按 redis_operates 顺序执行多条命令（先解析占位符），结果写入本步提取项与变量池。

    每条操作自动产出两个提取变量：variable_name（命令返回值列表）与 variable_name_count（数量）；
    redis_searched=True 时某条命令返回有效结果即终止后续命令（查到即止，有效判定见 has_effective_redis_result）。
    单条操作失败只置本步失败并记录错误，不中断后续操作；StepExecutionError（配置/参数非法）则立即上抛。
    """

    @staticmethod
    def has_effective_redis_result(command_results: Optional[List[Any]]) -> bool:
        """
        判断Redis命令结果列表是否含有效数据。

        None、空 list/tuple/dict、空白字符串均视为无效；命中任意一项有效值即返回True。

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
        顺序执行 redis_operates 中的命令，合并自动提取项并执行步骤自定义的提取/断言。

        执行顺序与数据库步骤一致：逐条解析配置 → 占位符解析（variable_name 解析后重算 _count 名）→
        project_id 回查 → 取客户端执行命令 → 记录自动提取项与请求/响应快照 → 有效结果触发查到即止 →
        循环结束后统一写 result.request/result.response → 以自动提取结果作为最高优先级查找项复用提取/断言管线。

        :param result: 本步执行结果
        :raises StepExecutionError: redis_operates 缺失/非法、必填参数为空、extract_variables 类型非法，
                                    或提取/断言存在失败项
        :return: None
        """
        try:
            merge_operates_env_name: Optional[str] = None
            display_config_name: Optional[str] = self.step.request_config_name
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
                    database_operates_index=redis_idx,
                    expected_config_type=AutoTestConfigNodeType.REDIS,
                )
                if current_op_execute_cfg:
                    env_name = str(current_op_execute_cfg.env_name or "").strip()
                    config_host = current_op_execute_cfg.config_host
                    config_port = current_op_execute_cfg.config_port
                    config_name: str = current_op_execute_cfg.config_name
                    database_name: str = current_op_execute_cfg.database_name or redis_operate.database_name
                    redis_operate.config_name = config_name
                    redis_operate.database_name = database_name
                    if display_config_name:
                        display_config_name += f", ({redis_idx}){redis_operate.config_name}"
                    else:
                        display_config_name = f"({redis_idx}){redis_operate.config_name}"
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
                        project_id=operate_project_id,
                        env_name=env_name,
                        config_name=operate_config_name,
                        database_name=operate_database_name,
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
                "request_config_name": display_config_name,
                "request_env_name": merge_operates_env_name,
            }
            result.response = {
                "response_body": redis_operates_response,
                "response_text": response_text_str,
                "response_elapsed": f"{(executive_ed_time - executive_st_time).total_seconds():.2f}",
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
    HTTP 步骤执行器：组装 URL 与报文（先数据驱动替换、再变量占位符），发起请求后执行提取与断言。

    URL 补全：命中执行配置（APP）且 request_url 不是绝对地址时，按 config_host/config_port 拼成绝对 URL；
    未命中执行配置（无 env_name）或最终地址不是 http(s) 开头时直接失败。
    参数化驱动：context.dataset_name + case_id/step_code 查 AutoTestDataSourceModel 取数，替换请求头与正文字段。
    """

    def collect_builtin_variables(self) -> List[StepVariablesBase]:
        """
        采集HTTP步骤内置环境变量：SERVER_*/TARGET_*。

        TARGET_HOST/TARGET_PORT 取自执行配置（APP），TARGET_PATH 取步骤 request_url 原值（未拼装）；
        未命中执行配置时 TARGET_* 不注入，并记录内置数据获取失败日志。

        :return: 内置变量列表
        """
        current_step_config: Optional[StepsExecuteConfigBase] = self.get_execute_config(
            expected_config_type=AutoTestConfigNodeType.APP,
        )
        target_host: Optional[str] = current_step_config.config_host if current_step_config else None
        target_port: Optional[str] = (
            str(current_step_config.config_port) if current_step_config and current_step_config.config_port else None
        )
        return collect_builtin_step_variables(
            target_host=target_host,
            target_port=target_port,
            target_path=(self.step.request_url or "").strip(),
            existing_keys=self.existing_variable_keys(),
            log=lambda msg: self.context.log(msg, step_code=self.step_code),
        )

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        组装 URL 与报文，发送 HTTP 请求并完成变量提取与断言。

        分两段执行：第一段校验请求方法与执行环境、补全 URL、预载数据驱动数据；
        第二段按「列表转字典 → 数据驱动替换 → 占位符解析 → assemble_http_body_payloads 选载荷」组装报文，
        发送前先落 result.request 快照，收到响应后再落 response 快照并复用提取/断言管线。

        :param result: 本步执行结果
        :raises StepExecutionError: request_method 缺失、URL/执行环境非法、报文组装失败、请求异常，
                                    或提取/断言存在失败项
        :return: None
        """
        try:
            request_url: str = (self.step.request_url or "").strip()
            request_method: HTTPMethod = self.step.request_method
            if request_method is None:
                raise StepExecutionError("【HTTP请求】请求方式[request_method]不能为空")
            current_step_config: Optional[StepsExecuteConfigBase] = self.get_execute_config(
                expected_config_type=AutoTestConfigNodeType.APP,
            )
            env_name: Optional[str] = None
            if current_step_config:
                env_name = current_step_config.env_name
                config_name: str = current_step_config.config_name
                config_host: str = (current_step_config.config_host or "").strip()
                config_port: str = (str(current_step_config.config_port).strip() if current_step_config.config_port else "")
                self.step.request_config_name = config_name
                if not is_absolute_http_url(request_url):
                    request_url = build_absolute_http_url(config_host, config_port, request_url)

            if not request_url or not request_url.lower().startswith("http") or not env_name:
                raise StepExecutionError(f"【HTTP请求】URL[{request_url!r}]不是有效的HTTP/HTTPS地址或未明确执行环境")

            # 参数化驱动：根据 context.dataset_name + case_id/step_code 查 AutoTestDataSourceModel 取该步骤数据集
            step_struct = await self.load_step_dataset(result)
            self.context.log(
                f"【HTTP请求】请求开始: \n\t"
                f"环境名称: {env_name}\n\t"
                f"应用ID: {self.step.request_project_id}\n\t"
                f"配置名称: {self.step.request_config_name}\n\t"
                f"请求方法: {request_method}\n\t"
                f"请求地址: {request_url}\n\t"
                f"参数类型: {self.step.request_args_type}\n\t"
                f"数据源名称: {result.dataset_name}"
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
            request_body: Any = AutoTestToolService.try_serialize_request_body(self.step.request_body)
            request_text: Optional[str] = self.step.request_text

            # 2）数据驱动：先替换报文（XML走XPath、其余走JSONPath），再占位符
            if AutoTestToolService.has_dataset_payload(step_struct):
                head_map = step_struct.get("head") or {}
                body_map = step_struct.get("body") or {}
                is_xml = AutoTestToolService.resolve_datagram_is_xml(self.step.request_args_type, request_text, request_body)
                if is_xml:
                    out = AutoTestToolService.replace_json_datagram(
                        head_map=head_map,
                        body_map={},
                        request_headers=request_header,
                        request_body=None,
                        form_data=None,
                        urlencoded=None,
                        logger_object=lambda msg: self.context.log(msg, step_code=self.step_code),
                    )
                    request_header = out["headers"]
                    xml_source = request_text if isinstance(request_text, str) and request_text.strip() else (
                        request_body if isinstance(request_body, str) else None
                    )
                    request_text = AutoTestToolService.replace_xml_datagram(
                        body_map=body_map,
                        request_text=xml_source,
                        logger_object=lambda msg: self.context.log(msg, step_code=self.step_code),
                    )
                else:
                    out = AutoTestToolService.replace_json_datagram(
                        head_map=head_map,
                        body_map=body_map,
                        request_headers=request_header,
                        request_body=request_body,
                        form_data=request_form_data,
                        urlencoded=request_form_urlencoded,
                        params=request_params,
                        logger_object=lambda msg: self.context.log(msg, step_code=self.step_code),
                    )
                    request_header = out["headers"]
                    request_body = out["request_body"]
                    request_form_data = out["form_data"]
                    request_form_urlencoded = out["urlencoded"]
                    request_params = out["params"]
                    # RAW/未指定类型且正文以JSON文本提供时，payload 走 request_text；
                    # 数据驱动修改的是解析后的 request_body，必须同步回写文本，否则替换结果不会生效。
                    if (
                            isinstance(request_body, (dict, list))
                            and isinstance(request_text, str)
                            and request_text.lstrip().startswith(("{", "["))
                    ):
                        request_text = orjson.dumps(request_body).decode("UTF-8")

            # 历史/导入数据可能把 XML 存在 request_body 字符串中；发送前回落到 request_text，
            # 避免 XML 步骤因 request_text 为空而发出空报文。
            if not request_text and isinstance(request_body, str) and (
                    self.step.request_args_type == AutoTestReqArgsType.XML
                    or request_body.lstrip().startswith("<")
            ):
                request_text = request_body

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
            if AutoTestToolService.resolve_datagram_is_xml(self.step.request_args_type, request_text, request_body) and request_text:
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
                    "response_elapsed": f"{response.elapsed.total_seconds():.2f}",
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
            # 提取成功项已由管线经 finished_variables 即时写回会话池；execute() 的 finally 会再按 result.extract_variables 幂等合并一次
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
                request_form_data=AutoTestToolService.merge_mapping_dicts(
                    request_form_urlencoded, request_form_data
                ),
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
    """
    报文比对步骤执行器：解析 datagram_field_compare 的左右报文引用，调用 compare_messages 逐组比对。

    项级 datagram_field_ordered 决定是否校验顺序（0=忽略顺序，1=控制顺序，缺省为0），语义与 compare_messages 一致；
    任一组不一致即本步失败，但所有组都会执行完，逐组明细写入 result.response 供报告展示。
    """

    @staticmethod
    def _to_message_text(value: Any) -> str:
        """
        将变量值规范为比对用文本。

        None → 空串；bytes 按 UTF-8 解码（失败即报错）；dict/list 序列化为 JSON 字符串；其余走 str()。

        :param value: 报文引用解析后的原始值
        :raises StepExecutionError: bytes 无法按 UTF-8 解码
        :return: 用于比对的文本
        """
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise StepExecutionError("【报文比对】bytes报文UTF-8解码失败") from exc
        if isinstance(value, (dict, list)):
            return orjson.dumps(value, default=str).decode("UTF-8")
        return str(value)

    def _resolve_message_ref(self, raw: Any) -> Any:
        """
        解析报文引用：裸变量名自动包成${name}；占位符未替换时再尝试从变量池取值。

        :param raw: 步骤配置中的引用原文（${var}、裸变量名或其他字面量）
        :return: 解析后的报文值；变量不存在时返回保留原样的占位符字符串
        """
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
    def _get_datagram_field_ordered(raw: Any) -> int:
        """
        校验并归一顺序开关：None 归一为0（忽略顺序），仅接受 0/1。

        :param raw: 步骤配置中的 datagram_field_ordered 原值
        :raises StepExecutionError: 无法转为整数或值不是0/1
        :return: 0（忽略顺序）或 1（控制顺序）
        """
        if raw is None:
            return 0
        try:
            field_ordered = int(raw)
        except (TypeError, ValueError) as exc:
            raise StepExecutionError(f"【报文比对】datagram_field_ordered必须是0或1: {raw}") from exc
        if field_ordered not in (0, 1):
            raise StepExecutionError(f"【报文比对】datagram_field_ordered必须是0或1: {field_ordered}")
        return field_ordered

    def _load_comparisons(self) -> List[Dict[str, Any]]:
        """
        从步骤配置加载比对组：项级 datagram_field_ordered 缺省为0（忽略顺序）。

        每项需包含 left_text/right_text，支持 DatagramFieldCompareItem 模型或 dict 两种形态。

        :raises StepExecutionError: 配置缺失/非数组、项不是对象、缺少 left_text/right_text 或顺序开关非法
        :return: 归一后的比对组列表（left_text/right_text/datagram_field_ordered）
        """
        items = getattr(self.step, "datagram_field_compare", None)
        if not items:
            raise StepExecutionError("【报文比对】缺少必要配置: datagram_field_compare")
        if not isinstance(items, list):
            raise StepExecutionError("【报文比对】datagram_field_compare必须是非空数组")

        comparisons: List[Dict[str, Any]] = []
        for index, item in enumerate(items):
            if isinstance(item, DatagramFieldCompareItem):
                left_text = item.left_text
                right_text = item.right_text
                item_ordered = item.datagram_field_ordered
            elif isinstance(item, dict):
                left_text = item.get("left_text")
                right_text = item.get("right_text")
                item_ordered = item.get("datagram_field_ordered")
            else:
                raise StepExecutionError(f"【报文比对】datagram_field_compare[{index}]必须是对象")
            if left_text is None or right_text is None:
                raise StepExecutionError(
                    f"【报文比对】datagram_field_compare[{index}]缺少left_text或right_text"
                )
            comparisons.append(
                {
                    "left_text": left_text,
                    "right_text": right_text,
                    "datagram_field_ordered": self._get_datagram_field_ordered(item_ordered),
                }
            )
        return comparisons

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        逐组解析报文引用并比对，全部一致才算本步成功。

        快照约定：result.request 记录配置原值（未解析的引用文本）；result.response 固定写 status 码
        与逐组比对明细（含 is_equal、order_consistent、rows），失败时同样落库供报告定位差异。

        :param result: 本步执行结果
        :raises StepExecutionError: 配置非法、报文引用解析失败或存在不一致的比对组
        :return: None
        """
        try:
            comparisons_raw = self._load_comparisons()
            self.context.log(
                f"【报文比对】开始执行: 共{len(comparisons_raw)}组",
                step_code=self.step_code,
            )

            datagram_field_compare: List[Dict[str, Any]] = []
            failed_indices: List[int] = []
            for index, item in enumerate(comparisons_raw):
                field_ordered = item["datagram_field_ordered"]
                left_text = self._to_message_text(self._resolve_message_ref(item["left_text"]))
                right_text = self._to_message_text(self._resolve_message_ref(item["right_text"]))
                diff_data = compare_messages(
                    left_text=left_text,
                    right_text=right_text,
                    order_control=field_ordered,
                )
                datagram_field_compare.append(
                    {
                        "left_name": item["left_text"],
                        "right_name": item["right_text"],
                        "left_text": left_text,
                        "right_text": right_text,
                        "datagram_field_ordered": field_ordered,
                        "is_equal": diff_data.is_equal,
                        "format_type": diff_data.format_type,
                        "order_consistent": diff_data.order_consistent,
                        "order_message": diff_data.order_message,
                        "rows": [row.model_dump() for row in diff_data.rows],
                    }
                )
                if not diff_data.is_equal:
                    failed_indices.append(index)

            response_payload = {"datagram_field_compare": datagram_field_compare}
            result.request = {"datagram_field_compare": comparisons_raw}
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
                    f"【报文比对】共{len(failed_indices)}组不一致(索引: {failed_indices}), 详情见报告明细"
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
    默认步骤执行器：仅顺序执行子步骤，作为未映射步骤类型的回退（容器类步骤也走这里）。

    不写入请求/响应快照，只汇总 children 的成败；子步异常已在 _execute_children 内转为失败结果。
    """

    async def _execute(self, result: StepExecutionResult) -> None:
        """
        顺序执行子步骤并将结果写入本步children，任一子步失败则本步失败。

        :param result: 本步执行结果，子步骤写入children
        :raises StepExecutionError: 子步汇总阶段出现非预期异常（子步自身的异常已就地转为失败结果）
        :return: None
        """
        try:
            child_results = await self._execute_children()
            for child in child_results:
                result.children.append(child)
                if not child.success:
                    result.success = False
        except Exception as e:
            result.success = False
            result.error = AutoTestToolService.format_step_error_message(step=self.step, exception=e, is_child_step=False)
            self.context.log(result.error, step_code=self.step_code)
            raise StepExecutionError(result.error) from e


class StepExecutorFactory:
    """
    步骤执行器工厂：按 step_type 从 EXECUTOR_MAP 取实现，未映射的合法类型回落到 DefaultStepExecutor。

    仅当 step_type 缺失或无法转为 AutoTestStepType、或执行器实例化失败时抛 StepExecutionError。
    """

    # 步骤类型 → 执行器实现；不在此表中的步骤类型（容器类等）统一由 DefaultStepExecutor 处理
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
        AutoTestStepType.EXTRACT: ExtractStepExecutor,
        AutoTestStepType.QUOTE_PUBLIC_SCRIPT: QuotePublicScriptStepExecutor,
        AutoTestStepType.QUOTE_PUBLIC_API: QuotePublicApiStepExecutor,
        AutoTestStepType.USER_VARIABLES: UserVariablesStepExecutor,
        AutoTestStepType.DIFF: DatagramDiffStepExecutor,
    }

    @classmethod
    def create_executor(cls, step: AutoTestStepTreeUpdateItem, context: StepExecutionContext) -> BaseStepExecutor:
        """
        根据 step.step_type 创建对应执行器；未映射的合法类型返回 DefaultStepExecutor。

        :param step: 步骤树节点
        :param context: 执行上下文
        :raises StepExecutionError: step_type 缺失、无法转为 AutoTestStepType，或执行器实例化失败
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
    用例执行入口：生成报告标识、进入执行上下文、按 step_no 顺序执行根步骤，并汇总统计、日志与待落库数据。

    本类不直接写库：报告与明细以 AutoTestReportCreate / AutoTestDetailCreate 形式返回，由调用方在单事务内落库。
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
        # 本次执行的报告标识：_save_report=False 时保持 None，即不收集明细
        self._report_code: Optional[str] = None
        # 本次执行的待落库明细：每次 execute_case 重新置空，避免上一次执行残留
        self._pending_details: List[AutoTestDetailCreate] = []

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
        Optional[AutoTestReportCreate],
        Optional[List[AutoTestDetailCreate]]
    ]:
        """
        执行单用例：在上下文中根据 step_no 执行根步骤，可选收集报告与明细供调用方落库。

        参数化时仅传入 dataset_name，HTTP/TCP 步骤根据 case_id/step_code 与数据集名称查表取数。
        step_is_skipped 的步骤不进入 results、不写明细、不计入 statistics。

        统计口径：按 step_code 去重合并，同一 step_code 任一次失败即整体失败；
        引用壳步骤（QUOTE_PUBLIC_SCRIPT/QUOTE_PUBLIC_API）有 children 时跳过自身，避免与被引用用例的内部步骤重复计数。

        :param case: 用例信息字典，含 case_id、case_code、case_name
        :param steps: 根步骤可迭代对象（内部会按 step_no 重新排序）
        :param report_type: 报告类型枚举；为 None 时缺省写入 SYNC_EXEC
        :param steps_execute_config: 执行配置，同时用于汇总报告涉及的环境列表（involve_envs）
        :param initial_variables: 初始会话变量列表，每项含 key、value、desc
        :param dataset_name: 参数化时本次执行的数据集名称，写入每条步骤明细；步骤内据此查表取数
        :return: 七元组 (results, logs, report_code, statistics, session_variables, defer_create_report, pending_create_details)，
            results：根步骤执行结果列表（不含已跳过步骤）；logs：根据 step_code 分组；report_code：未保存时为 None；
            statistics：含 total_steps、success_steps、failed_steps、passed_ratio；session_variables：执行后变量列表；
            当 _save_report 为 True 时，最后两项为待落库的报告创建体与明细列表（report_code 已统一），
            调用方在单事务内依次 create_report、create_detail、update_case
        """
        # 运行、调试及Worker共用此入口；缺省和空配置统一为空字典，后续可安全遍历
        steps_execute_config = steps_execute_config or {}
        report_code: Optional[str] = None
        case_id: int = case.get("case_id")
        case_code: str = case.get("case_code")
        case_start_time: datetime = datetime.now()
        case_st_time_str: str = case_start_time.strftime("%Y-%m-%d %H:%M:%S.%f")
        if self._save_report:
            report_code: str = unique_identify()
            self._report_code = report_code
            self._pending_details = []
        pending_details_arg: Optional[List[AutoTestDetailCreate]] = self._pending_details if self._save_report else None
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

            # 统计（根据 step_code 去重合并，同一 step_code 任一次失败即整体失败）；引用壳步骤执行的是被引用用例的内部步骤
            # (children 已逐项计数)，因此壳步骤有 children 时跳过自身，避免壳与被引用步骤重复计数
            all_results: List[StepExecutionResult] = self.collect_all_results(results)
            quote_shell_types: Tuple[AutoTestStepType, ...] = (AutoTestStepType.QUOTE_PUBLIC_SCRIPT, AutoTestStepType.QUOTE_PUBLIC_API)
            unique_states: Dict[str, bool] = {}
            for r in all_results:
                if r.step_type in quote_shell_types and r.children:
                    continue
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
            case_ed_time_str: str = case_end_time.strftime("%Y-%m-%d %H:%M:%S.%f")
            case_elapsed: str = f"{(case_end_time - case_start_time).total_seconds():.2f}"
            case_state: bool = failed_steps == 0
            defer_create_report: Optional[AutoTestReportCreate] = None
            pending_create_details: Optional[List[AutoTestDetailCreate]] = None
            involve_envs: Set[str] = {
                var.env_name if isinstance(var, StepsExecuteConfigBase) else var.get("env_name")
                for key, var in steps_execute_config.items()
            }
            if self._save_report and report_code:
                user_name: Optional[str] = get_current_username()
                final_report_type = report_type if report_type is not None else AutoTestReportType.SYNC_EXEC
                defer_create_report = AutoTestReportCreate(
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
                    involve_envs=list(involve_envs),
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
        将根步骤下所有子步骤的日志按 step_code 收集后，追加到该根步骤在 context.logs 中的日志列表。

        汇总顺序为 step_code 字符串字典序（不是 step_no），与执行顺序可能不一致；
        根步骤自身已有日志时保持在最前，子步日志追加在后。

        :param context: 执行上下文，其logs将被修改
        :param root_result: 根步骤的执行结果，用于遍历children
        :param root_step_code: 根步骤的step_code，用于写回context.logs
        :return: None
        """

        # 递归收集 step_code（函数名沿用历史命名，实际返回的是 step_code 而非 step_no）
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

        # 收集所有子步骤的 step_code（递归收集, 包括子步骤的子步骤）
        child_step_codes: List[str] = []
        for child in root_result.children:
            child_step_codes.extend(collect_child_step_nos(child))

        # 汇总所有子步骤的日志（按 step_code 字典序排列）
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
