from __future__ import annotations

import asyncio
import datetime
import json
import random
import re
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Tuple, Union
from xml.etree import ElementTree as ET

import httpx
import requests

from backend.applications.aotutest.models.autotest_model import AutoTestApiEnvInfo, AutoTestApiCaseInfo
from backend.applications.aotutest.schemas.autotest_case_schema import AutoTestApiCaseUpdate
from backend.applications.aotutest.schemas.autotest_detail_schema import AutoTestApiDetailCreate
from backend.applications.aotutest.schemas.autotest_report_schema import (
    AutoTestApiReportCreate,
    AutoTestApiReportUpdate
)
from backend.applications.aotutest.services.autotest_tool_service import AutoTestToolService
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    ParameterException,
)
from backend.enums.autotest_enum import (
    AutoTestStepType,
    AutoTestReportType,
    AutoTestLoopMode,
    AutoTestCaseType,
    AutoTestLoopErrorStrategy
)
from backend.services.ctx import CTX_USER_ID


class StepExecutionError(Exception):
    """执行过程中出现的业务异常。"""


@dataclass
class StepExecutionResult:
    case_id: Optional[int]
    step_id: Optional[int]
    step_no: Optional[int]
    step_code: Optional[str]
    step_name: Optional[str]
    step_type: AutoTestStepType
    success: bool
    message: str = ""
    error: Optional[str] = None
    response: Optional[Any] = None
    elapsed: Optional[float] = None
    quote_case_id: Optional[int] = None
    extract_variables: Dict[str, Any] = field(default_factory=dict)
    assert_validators: List[Dict[str, Any]] = field(default_factory=list)
    children: List["StepExecutionResult"] = field(default_factory=list)

    def append_child(self, child: "StepExecutionResult") -> None:
        self.children.append(child)


class HttpClientProtocol(Protocol):
    """HTTP 客户端协议, 便于依赖注入和单元测试。"""

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        ...


class StepExecutionContext:
    """执行上下文, 负责维护变量、日志以及外部依赖。"""

    def __init__(
            self,
            case_id: int,
            case_code: str,
            *,
            env: Optional[str] = None,
            initial_variables: Optional[Dict[str, Any]] = None,
            http_client: Optional[HttpClientProtocol] = None,
            report_code: Optional[str] = None,
    ) -> None:
        self.env = env
        self.case_id = case_id
        self.case_code = case_code
        self.report_code = report_code
        self.defined_variables: Dict[str, Any] = {}
        self.session_variables: Dict[str, Any] = dict(initial_variables or {})
        self.extract_variables: Dict[str, Any] = {}
        self.logs: Dict[str, List[str]] = {}
        self.step_cycle_index: Dict[str, int] = {}
        self._current_step_code: Optional[int] = None
        self._http_client = http_client
        self._exit_stack = AsyncExitStack()
        self.timeout: float = 30.0
        self.connect: float = 10.0

    async def __aenter__(self) -> "StepExecutionContext":
        """
        异步上下文管理器入口方法, 初始化HTTP客户端（如未提供）

        若未指定外部HTTP客户端, 将创建一个默认的httpx.AsyncClient实例,
        并通过AsyncExitStack管理其生命周期, 确保在上下文退出时自动关闭客户端连接。
        默认超时配置：请求超时10秒, 连接超时5秒。

        Returns:
            StepExecutionContext: 上下文管理器实例本身, 用于异步with语句
        """
        try:
            if self._http_client is None:
                # 创建默认HTTP客户端, 设置超时参数（请求超时10秒, 连接超时5秒）
                client = httpx.AsyncClient(timeout=httpx.Timeout(timeout=self.timeout, connect=self.connect))
                # 将客户端纳入异步退出栈管理, 确保上下文退出时自动关闭
                self._http_client = await self._exit_stack.enter_async_context(client)
            return self
        except Exception as e:
            error_message: str = f"初始化HTTP客户端连接失败, 无法创建测试执行上下文管理器, 错误描述: {e}"
            self.log(message=error_message)
            raise StepExecutionError(error_message) from e

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            await self._exit_stack.aclose()
        except Exception as e:
            error_message: str = f"关闭HTTP客户端连接失败, 错误描述: {e}"
            self.log(message=error_message)

    @property
    def http_client(self) -> HttpClientProtocol:
        if self._http_client is None:
            raise RuntimeError("HTTP Client 未初始化, 请在异步上下文中使用")
        return self._http_client

    def log(self, message: str, step_code: Optional[str] = None) -> None:
        step_code = step_code or self._current_step_code
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.logs.setdefault(step_code, []).append(f"[{timestamp}] {message}")

    def set_current_step_code(self, step_code: Optional[str] = None) -> None:
        self._current_step_code = step_code

    def clone_state(self) -> Dict[str, Any]:
        """
        克隆当前变量状态，用于Python代码执行的命名空间。
        :return:
        """
        return {
            "defined_variables": dict(self.defined_variables),
            "session_variables": dict(self.session_variables),
        }

    def update_variables(self, data: Dict[str, Any], *, scope: str = "defined_variables") -> None:
        target_map = {
            "extract_variables": self.extract_variables,
            "defined_variables": self.defined_variables,
            "session_variables": self.session_variables,
        }
        scope_map = target_map.get(scope)
        if scope_map is None:
            raise ValueError(
                f"【更新变量】-【{scope}】错误: '{scope}' 不是有效的变量作用域"
                f"(仅支持defined_variables、session_variables或extract_variables)"
            )
        try:
            scope_map.update(data)
            self.log(f"【更新变量】-【{scope}】成功: {data}")
        except Exception as e:
            error_message: str = f"【更新变量】-【{scope}】失败, 数据: {data}, 错误描述: {e}"
            self.log(error_message)
            raise StepExecutionError(error_message) from e

    def get_variable(self, name: str) -> Any:
        """
        获取变量值, 按优先级查找：defined_variables > session_variables

        变量作用域说明：
        - defined_variables: 当前步骤的临时变量（从步骤配置中获取）
        - session_variables: 持续累积已执行的步骤产生的变量（所有步骤共享）
        """
        if not name or not isinstance(name, str):
            raise StepExecutionError(f"【获取变量】变量名无效: 变量名必须是非空字符串, 当前值: {name}")
        for scope_name, scope in [
            ("defined_variables", self.defined_variables),
            ("session_variables", self.session_variables),
        ]:
            if name in scope:
                try:
                    return scope[name]
                except Exception as e:
                    raise StepExecutionError(f"【获取变量】'{name}'的值时发生错误(作用域: {scope_name}): {e}") from e

        raise KeyError(f"【获取变量】变量({name})未定义, 请检查变量名是否正确, 或确认变量是否已在之前的步骤中定义")

    def resolve_placeholders(self, value: Any) -> Any:
        """支持嵌套结构中的 ${var} 占位符替换。"""
        try:
            if isinstance(value, str):
                pattern = re.compile(r"\$\{([^}]+)}")

                def replace(match: re.Match[str]) -> str:
                    var_name = match.group(1)
                    if not var_name:
                        self.log("【获取变量】占位符解析失败, 不允许引用空白符, 保留原值")
                        return match.group(0)
                    try:
                        resolved = self.get_variable(var_name)
                    except KeyError:
                        self.log(f"【获取变量】占位符解析失败, 变量({var_name})未定义, 保留原值")
                        return match.group(0)
                    except Exception as e:
                        self.log(f"【获取变量】占位符解析失败, 引用变量({var_name})引发未知异常, 保留原值, 错误描述: {e}")
                        return match.group(0)
                    try:
                        self.log("【获取变量】占位符解析成功, ${" + var_name + "}  <=>  " + f"{resolved}")
                        return str(resolved)
                    except Exception as e:
                        self.log(
                            f"【获取变量】将变量[{var_name}]的值[{resolved}]转换为字符串时失败, 保留原值, 错误描述: {e}")
                        return match.group(0)

                return pattern.sub(replace, value)

            if isinstance(value, dict):
                try:
                    return {k: self.resolve_placeholders(v) for k, v in value.items()}
                except Exception as e:
                    self.log(f"【获取变量】解析字典中的占位符时发生错误, 键: {list(value.keys())}, 错误: {e}")
                    return value
            if isinstance(value, list):
                try:
                    return [self.resolve_placeholders(item) for item in value]
                except Exception as e:
                    self.log(f"【获取变量】解析列表中的占位符时发生错误, 列表长度: {len(value)}, 错误: {e}")
                    return value
            return value
        except Exception as e:
            self.log(
                f"【获取变量】占位符解析过程中发生未知异常, 保留原值, "
                f"错误类型: {type(e).__name__}, "
                f"错误描述: {e}"
            )
            return value

    async def sleep(self, seconds: Optional[float]) -> None:
        if seconds is None:
            return
        try:
            wait_time = float(seconds)
        except (ValueError, TypeError) as e:
            raise StepExecutionError(
                f"【等待控制】等待时间解析失败: "
                f"参数[seconds]必须是[float]类型, 且不允许小于0, "
                f"但得到[{type(seconds)}类型: [{seconds}], 错误描述: {e}"
            ) from e
        if wait_time < 0:
            raise StepExecutionError(
                f"【等待控制】等待时间解析失败: "
                f"参数[seconds]必须是[float]类型, 且不允许小于0, "
                f"但得到[{type(seconds)}类型: [{seconds}]"
            )
        if wait_time > 300:
            raise StepExecutionError(
                f"【等待控制】等待时间解析失败: "
                f"参数[seconds]必须是[float]类型, 且不允许大于300, "
                f"但得到[{type(seconds)}类型: [{seconds}]"
            )
        try:
            await asyncio.sleep(wait_time)
            self.log(f"【等待控制】等待 {wait_time} 秒成功")
        except Exception as e:
            raise StepExecutionError(f"【等待控制】执行等待操作时发生异常: {e}") from e

    async def send_http_request(
            self,
            method: str,
            url: str,
            *,
            headers: Optional[Dict[str, Any]] = None,
            params: Optional[Dict[str, Any]] = None,
            data: Optional[Any] = None,
            json_data: Optional[Any] = None,
            files: Optional[Any] = None,
            timeout: Optional[float] = None,
    ) -> httpx.Response:
        try:
            client = self.http_client
            kwargs = {
                "headers": headers,
                "params": params,
                "data": data,
                "json": json_data,
                "files": files,
            }
            if timeout is not None:
                kwargs["timeout"] = timeout
            filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
            self.log(f"【HTTP请求】请求方式: {method}")
            self.log(f"【HTTP请求】请求地址: {url}")
            self.log(f"【HTTP请求】请求参数: {filtered_kwargs}")
            try:
                response = await client.request(method, url, **kwargs)
                self.log(
                    f"【HTTP请求】请求成功: "
                    f"响应代码: {response.status_code}, "
                    f"响应消息: {response.reason_phrase}, "
                    f"响应耗时: {response.elapsed.total_seconds()}"
                )
                return response
            except httpx.TimeoutException as e:
                error_message: str = (
                    f"【HTTP请求】请求超时: "
                    f"在规定时间范围内未能从服务器获取到响应数据"
                    f"(可能原因: 网络延迟、服务器响应慢或超时设置过短), "
                    f"错误类型: {type(e).__name__}, "
                    f"错误描述: {e}"
                )
                self.log(error_message)
                raise StepExecutionError(error_message) from e
            except httpx.RequestError as e:
                error_message: str = (
                    f"【HTTP请求】请求失败: "
                    f"请求服务器时发生网络错误"
                    f"(可能原因: 网络连接问题、DNS解析失败或服务器不可达, "
                    f"错误类型: {type(e).__name__}, "
                    f"错误描述: {e}"
                )
                self.log(error_message)
                raise StepExecutionError(error_message) from e
            except Exception as e:
                error_message: str = (
                    f"【HTTP请求】请求失败: "
                    f"请求服务器时发生未知错误"
                    f"错误类型: {type(e).__name__}, "
                    f"错误描述: {e}"
                )
                self.log(error_message)
                raise StepExecutionError(error_message) from e
        except StepExecutionError:
            raise
        except Exception as e:
            self.log(str(e))
            raise StepExecutionError(str(e)) from e

    def run_python_code(self, code: str, *, namespace: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行 Python 代码块, 返回新增变量。"""
        if not code: return {}
        resolved_code = self._resolve_code_placeholders(code)
        prepared = self._normalize_python_code(resolved_code)
        # 提供安全的全局环境, 包含必要的内置函数和导入功能
        safe_globals = {
            "__builtins__": {
                "__import__": __import__,
                "len": len,
                "range": range,
                "min": min,
                "max": max,
                "sum": sum,
                "abs": abs,
                "round": round,
                "int": int,
                "float": float,
                "str": str,
                "bool": bool,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "set": set,
                "print": print,
                "random": random,
                "time": time,
                "datetime": datetime,
                "requests": requests,
            }
        }
        local_context: Dict[str, Any] = {}
        if namespace:
            local_context.update(namespace)

        try:
            exec(prepared, safe_globals, local_context)
        except SyntaxError as e:
            error_message: str = (
                f"【执行代码请求(Python)】代码解析失败: "
                f"请遵循 Python PEP8 编码规范, "
                f"错误位置: 第{e.lineno}行, "
                f"错误类型: {type(e).__name__}, "
                f"错误描述: {e}"
            )
            self.log(error_message)
            raise StepExecutionError(error_message) from e
        except NameError as e:
            error_message: str = (
                f"【执行代码请求(Python)】代码解析失败: "
                f"请检查代码中是否引用了未定义的变量或函数, "
                f"错误类型: {type(e).__name__}, "
                f"错误描述: {e}"
            )
            self.log(error_message)
            raise StepExecutionError(error_message) from e
        except Exception as e:
            error_message: str = (
                f"【执行代码请求(Python)】代码解析异常: "
                f"错误类型: {type(e).__name__}, "
                f"错误描述: {e}"
            )
            self.log(error_message)
            raise StepExecutionError(error_message) from e

        functions = {name: obj for name, obj in local_context.items() if callable(obj)}
        if functions:
            if len(functions) == 1:
                try:
                    func = next(iter(functions.values()))
                    result = func()
                except Exception as e:
                    error_message: str = (
                        f"【执行代码请求(Python)】代码执行异常: "
                        f"错误类型: {type(e).__name__}, "
                        f"错误描述: {e}"
                    )
                    self.log(error_message)
                    raise StepExecutionError(error_message) from e
            else:
                func_names = ", ".join(functions.keys())
                error_message: str = (
                    f"【执行代码请求(Python)】代码执行失败: "
                    f"仅支持定义一个函数作为入口, 当前存在多个函数: {func_names}"
                )
                self.log(error_message)
                raise StepExecutionError(error_message)
        elif "result" in local_context:
            result = local_context["result"]
        else:
            result = None

        if result is None:
            self.log("【执行代码请求(Python)】代码执行完成, 但无结果")
            return {}
        if not isinstance(result, dict):
            error_message: str = (
                f"【执行代码请求(Python)】代码执行失败: "
                f"返回值类型不被接受, "
                f"期望返回类型: Dict[str, Any], "
                f"实际返回类型: {type(result).__name__}, "
                f"返回值: {result}"
            )
            self.log(error_message)
            raise StepExecutionError(error_message)
        self.log(f"【执行代码请求(Python)】代码执行完成, 返回结果: {result}")
        return result

    @staticmethod
    def _normalize_python_code(code: str) -> str:
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

            # 提取 import/from 语句（必须在 return 之前）
            import_lines = []
            remaining_body = body

            # 查找所有 import/from 语句
            while True:
                import_pos = remaining_body.find("import ")
                from_pos = remaining_body.find("from ")

                if import_pos == -1 and from_pos == -1:
                    break

                # 找到第一个 import 或 from
                if from_pos != -1 and (import_pos == -1 or from_pos < import_pos):
                    pos = from_pos
                    keyword = "from "
                else:
                    pos = import_pos
                    keyword = "import "

                # 找到 import 语句的结束位置（下一个关键字或行尾）
                remaining_after_keyword = remaining_body[pos + len(keyword):]
                next_keywords = ["return ", "if ", "for ", "while ", "with ", "import ", "from "]
                end_pos = len(remaining_after_keyword)

                for kw in next_keywords:
                    kw_pos = remaining_after_keyword.find(kw)
                    if kw_pos != -1 and kw_pos < end_pos:
                        end_pos = kw_pos

                # 提取完整的 import 语句
                import_stmt = remaining_body[pos:pos + len(keyword) + end_pos].strip()
                import_lines.append(import_stmt)

                # 继续处理剩余部分
                remaining_body = remaining_body[pos + len(keyword) + end_pos:].strip()

            # 组合格式化后的代码
            normalized_parts = []

            # 1. 先添加所有 import 语句（在函数外部）
            if import_lines:
                normalized_parts.extend(import_lines)

            # 2. 添加函数定义
            normalized_parts.append(func_def)

            # 3. 添加函数体（需要缩进）
            if remaining_body:
                # 处理 return 等语句, 确保有正确的缩进
                for keyword in ("return ", "if ", "for ", "while ", "with "):
                    if remaining_body.startswith(keyword):
                        normalized_parts.append(f"    {remaining_body}")
                        break
                else:
                    # 如果没有匹配的关键字, 直接添加并缩进
                    normalized_parts.append(f"    {remaining_body}")

            return "\n".join(normalized_parts)

        return code

    def _resolve_code_placeholders(self, code: str) -> str:
        """
        解析Python代码中的占位符，将 ${var_name} 替换为实际变量值。

        处理规则：
        1. 字符串字面量中的占位符（如 '${var}'）替换为实际值，去掉占位符周围的引号
           例如：'${idx_1}' == 1 会变成 1 == 1（假设 idx_1 = 1）
        2. 字符串拼接中的占位符（如 '${item}_1001'）替换为实际值，保持字符串格式
           例如：'${item_1}_1001' 会变成 'test_1001'（假设 item_1 = "test"）
        3. 代码逻辑中的占位符（如 if ${var} == 1:）直接替换为实际值
        """
        if not code or not isinstance(code, str):
            return code

        pattern = re.compile(r"(['\"])\$\{([^}]+)}\1")

        def replace_string_placeholder(match: re.Match[str]) -> str:
            """处理字符串字面量中的占位符，如 '${var}' 或 "${var}" """
            quote_char = match.group(1)
            var_name = match.group(2)
            if not var_name:
                self.log("【执行代码请求(Python)】占位符解析失败, 不允许引用空白符, 保留原值")
                return match.group(0)

            try:
                var_value = self.get_variable(var_name)
            except KeyError:
                self.log(f"【执行代码请求(Python)】占位符解析失败, 变量({var_name})未定义, 保留原值")
                return match.group(0)
            except Exception as e:
                self.log(f"【执行代码请求(Python)】占位符解析失败, 引用变量({var_name})失败, 保留原值, 错误描述: {e}")
                return match.group(0)

            # 在字符串字面量中，替换为实际值（去掉引号）
            # 例如：'${idx_1}' == 1 变成 1 == 1
            if isinstance(var_value, str):
                return var_value
            elif isinstance(var_value, (int, float, bool)):
                return str(var_value)
            elif var_value is None:
                return "None"
            else:
                return str(var_value)

        # 先处理字符串字面量中的占位符（如 '${var}' 或 "${var}"）
        code = pattern.sub(replace_string_placeholder, code)

        # 再处理字符串拼接中的占位符（如 '${var}_suffix' 或 'prefix_${var}'）
        # 使用更通用的正则：匹配引号内的内容，包含占位符
        pattern2 = re.compile(r"(['\"])((?:(?!\1).)*?)\$\{([^}]+)}((?:(?!\1).)*?)\1")

        def replace_string_concat_placeholder(match: re.Match[str]) -> str:
            """处理字符串拼接中的占位符，如 'prefix_${var}_suffix' """
            quote_char = match.group(1)
            prefix = match.group(2)
            var_name = match.group(3)
            suffix = match.group(4)

            if not var_name:
                self.log("【执行代码请求(Python)】占位符解析失败, 不允许引用空白符, 保留原值")
                return match.group(0)

            try:
                var_value = self.get_variable(var_name)
            except KeyError:
                self.log(f"【执行代码请求(Python)】占位符解析失败, 变量({var_name})未定义, 保留原值")
                return match.group(0)
            except Exception as e:
                self.log(f"【执行代码请求(Python)】占位符解析失败, 引用变量({var_name})失败, 保留原值, 错误描述: {e}")
                return match.group(0)

            # 字符串拼接，保持字符串格式
            result = prefix + str(var_value) + suffix
            return quote_char + result + quote_char

        code = pattern2.sub(replace_string_concat_placeholder, code)

        # 最后处理代码逻辑中的占位符（不在字符串中的）
        pattern3 = re.compile(r"\$\{([^}]+)}")

        def replace_code_placeholder(match: re.Match[str]) -> str:
            """处理代码逻辑中的占位符，如 if ${var} == 1: """
            var_name = match.group(1)
            if not var_name:
                self.log("【执行代码请求(Python)】占位符解析失败, 不允许引用空白符, 保留原值")
                return match.group(0)

            try:
                var_value = self.get_variable(var_name)
            except KeyError:
                self.log(f"【执行代码请求(Python)】占位符解析失败, 变量({var_name})未定义, 保留原值")
                return match.group(0)
            except Exception as e:
                self.log(f"【执行代码请求(Python)】占位符解析失败, 引用变量({var_name})失败, 保留原值, 错误描述: {e}")
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
            resolved_code = pattern3.sub(replace_code_placeholder, code)
            return resolved_code
        except Exception as e:
            error_message: str = (
                f"【执行代码请求(Python)】占位符解析异常, 保留原值, "
                f"错误类型: {type(e).__name__}, "
                f"错误描述: {e}"
            )
            self.log(error_message)
            return code

    @property
    def current_step_code(self):
        return self._current_step_code


class BaseStepExecutor:
    """步骤执行器基类。"""

    def __init__(self, step: Dict[str, Any], context: StepExecutionContext):
        self.step = step
        self.context = context

    @property
    def case_id(self) -> Optional[int]:
        return self.step.get("case_id")

    @property
    def step_id(self) -> Optional[int]:
        return self.step.get("step_id")

    @property
    def step_no(self) -> Optional[int]:
        return self.step.get("step_no")

    @property
    def step_code(self) -> Optional[str]:
        return self.step.get("step_code")

    @property
    def step_name(self) -> Optional[str]:
        return self.step.get("step_name")

    @property
    def step_type(self) -> AutoTestStepType:
        return AutoTestStepType(self.step.get("step_type"))

    @property
    def quote_case_id(self) -> Optional[int]:
        return self.step.get("quote_case_id")

    @property
    def children(self) -> List[Dict[str, Any]]:
        return sorted(
            (self.step.get("children") or []) + (self.step.get("quote_steps") or []),
            key=lambda item: item.get("step_no", 0),
        )

    async def execute(self) -> StepExecutionResult:
        start = time.perf_counter()
        step_start_time = datetime.now()
        step_st_time_str = step_start_time.strftime("%Y-%m-%d %H:%M:%S.%f")
        num_cycles = self.context.step_cycle_index.get(self.step_code)
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
        # 设置当前步骤编号
        self.context.set_current_step_code(self.step_code)
        previous_step_code: Optional[int] = self.context.current_step_code
        try:
            await self._execute(result)
        except Exception as e:
            result.success = False
            result.error = str(e)
            self.context.log(str(e), step_code=previous_step_code)
        finally:
            try:
                if result.extract_variables:
                    self.context.update_variables(result.extract_variables, scope="session_variables")
                    self.context.log(
                        f"【合并变量】-【session_variables】成功: {result.extract_variables}",
                        step_code=self.step_code
                    )
            except Exception as e:
                self.context.log(f"【合并变量】-【session_variables】失败: {e}", step_code=self.step_code)

            self.context.set_current_step_code(step_code=previous_step_code)
            end = time.perf_counter()
            result.elapsed = round(end - start, 6)
            if self.context.report_code:
                try:
                    await self._save_step_detail(result, step_st_time_str, num_cycles)
                except Exception as e:
                    # 保存步骤明细失败不应该影响执行流程
                    self.context.log(
                        f"保存步骤明细(case_id={self.case_id}, step_id={self.step_id}, "
                        f"step_no={self.step_no}, step_code={self.step_code})失败, 错误描述: {e}",
                        step_code=self.step_code
                    )
        return result

    async def _save_step_detail(self, result: StepExecutionResult, step_st_time_str: str, num_cycles: int) -> None:
        """保存步骤明细到数据库（含无响应步骤占位；循环多次执行合并）"""
        try:
            step_end_time = datetime.now()
            step_ed_time_str = step_end_time.strftime("%Y-%m-%d %H:%M:%S.%f")
            step_elapsed = f"{result.elapsed:.3f}" if result.elapsed is not None else "0.000"

            step_logs = self.context.logs.get(self.step_code, [])
            step_exec_logger = "\n".join(step_logs) if step_logs else None

            response_header = None
            response_body = None
            response_text = None
            response_cookie = None
            response_elapsed = None

            if result.response:
                response_elapsed = result.response.get("elapsed")
                response_header = result.response.get("headers")
                response_text = result.response.get("text")
                if response_text:
                    try:
                        response_body = json.loads(response_text)
                    except (ValueError, TypeError):
                        response_body = None
                cookies = result.response.get("cookies") if isinstance(result.response, dict) else None
                if cookies:
                    response_cookie = json.dumps(cookies, ensure_ascii=False)

            step_code = self.step_code

            # 1. defined_variables: 从步骤配置中获取用户定义的变量
            defined_variables = self.step.get("defined_variables") or {}

            # 2. extract_variables: 从响应中提取的变量
            extract_variables = {}
            extract_variables_config: List[Dict[str, Any]] = self.step.get("extract_variables")
            if extract_variables_config and isinstance(extract_variables_config, list) and result.extract_variables:
                for extract in extract_variables_config:
                    ext_name = extract.get("name")
                    if ext_name and ext_name in result.extract_variables:
                        extract_variables[ext_name] = result.extract_variables[ext_name]

            # 3. session_variables: 累积的会话变量（包含所有步骤产生的变量）
            session_variables = dict(self.context.session_variables) if self.context.session_variables else {}

            detail_create = AutoTestApiDetailCreate(
                case_id=self.context.case_id,
                case_code=self.context.case_code,
                report_code=self.context.report_code,
                step_id=self.step_id,
                step_no=self.step_no,
                step_name=self.step_name,
                step_code=step_code,
                step_type=self.step_type,
                step_state=result.success,
                step_st_time=step_st_time_str,
                step_ed_time=step_ed_time_str,
                step_elapsed=step_elapsed,
                step_exec_logger=step_exec_logger,
                step_exec_except=result.error,
                num_cycles=num_cycles,
                response_cookie=response_cookie or None,
                response_header=response_header or None,
                response_body=response_body or None,
                response_text=response_text or None,
                response_elapsed=response_elapsed,
                session_variables=session_variables,
                defined_variables=defined_variables,
                extract_variables=extract_variables,
                assert_validators=result.assert_validators or []
            )
            from backend.applications.aotutest.services.autotest_detail_crud import AUTOTEST_API_DETAIL_CRUD
            await AUTOTEST_API_DETAIL_CRUD.create_detail(detail_create)
        except Exception as e:
            error_message: str = (
                f"保存步骤明细(case_id={self.case_id}, step_id={self.step_id}, "
                f"step_no={self.step_no}, step_code={self.step_code})失败, 错误描述: {e}"
            )
            raise StepExecutionError(error_message)

    async def _execute(self, result: StepExecutionResult) -> None:
        raise NotImplementedError

    async def _execute_children(self) -> List[StepExecutionResult]:
        results: List[StepExecutionResult] = []
        for child in self.children:
            try:
                executor = StepExecutorFactory.create_executor(child, self.context)
                child_result = await executor.execute()
                results.append(child_result)
            except Exception as e:
                # 子步骤执行失败, 创建失败结果记录
                case_id: int = child.get("case_id")
                step_id: int = child.get("step_id")
                step_no: int = child.get("step_no")
                step_code: str = child.get("step_code")
                step_name: str = child.get("step_name")
                step_type: str = child.get("step_type")
                error_message: str = (
                    f"子步骤执行失败: "
                    f"用例ID: {case_id}, "
                    f"步骤序号: {step_no}, "
                    f"步骤标识: {step_code}, "
                    f"步骤名称: {step_name}, "
                    f"步骤类型: {step_type}, "
                    f"错误类型: {type(e).__name__}, "
                    f"错误详情: {e}"
                )
                self.context.log(error_message, step_code=step_code)
                failed_result = StepExecutionResult(
                    case_id=case_id,
                    step_id=step_id,
                    step_no=step_no,
                    step_code=step_code,
                    step_name=step_name,
                    step_type=AutoTestStepType(step_type),
                    quote_case_id=child.get("quote_case_id"),
                    success=False,
                    error=error_message,
                )
                results.append(failed_result)
        return results


class LoopStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        try:
            # 获取循环模式，必须明确指定
            loop_mode_str = self.step.get("loop_mode")
            if not loop_mode_str:
                raise StepExecutionError(
                    "【循环结构】请明确指定循环模式类型(仅允许选择: 次数循环, 对象循环, 字典循环, 条件循环)")
            # 获取错误处理策略，必须明确指定
            on_error_str = self.step.get("loop_on_error")
            if not on_error_str:
                raise StepExecutionError(
                    "【循环结构】请明确指定错误处理策略(仅允许选择: 继续下一次循环, 中断循环, 停止整个用例执行)")
            try:
                loop_mode = AutoTestLoopMode(loop_mode_str)
            except (ValueError, TypeError) as e:
                raise StepExecutionError(
                    f"【循环结构】循环模式{loop_mode_str}无效(仅允许选择: 次数循环、对象循环、字典循环、条件循环)"
                ) from e
            try:
                on_error = AutoTestLoopErrorStrategy(on_error_str)
            except (ValueError, TypeError) as e:
                raise StepExecutionError(
                    f"【循环结构】错误处理策略{on_error_str}无效(仅允许选择: 继续下一次循环、中断循环、停止整个用例执行)"
                ) from e

            # 根据循环模式执行不同的逻辑
            if loop_mode == AutoTestLoopMode.COUNT:
                await self._execute_count_loop(result, on_error)
            elif loop_mode == AutoTestLoopMode.ITERABLE:
                await self._execute_iterable_loop(result, on_error)
            elif loop_mode == AutoTestLoopMode.DICT:
                await self._execute_dict_loop(result, on_error)
            elif loop_mode == AutoTestLoopMode.CONDITION:
                await self._execute_condition_loop(result, on_error)
            else:
                raise StepExecutionError(
                    f"【循环结构】循环模式[{loop_mode_str}]无效(仅允许选择: 次数循环, 对象循环, 字典循环, 条件循环)")

        except StepExecutionError:
            raise
        except Exception as e:
            error_message: str = (
                f"子步骤执行失败: "
                f"用例ID: {self.case_id}, "
                f"步骤序号: {self.step_no}, "
                f"步骤标识: {self.step_code}, "
                f"步骤名称: {self.step_name}, "
                f"步骤类型: {self.step_type}, "
                f"错误类型: {type(e).__name__}, "
                f"错误详情: {e}"
            )
            result.success = False
            result.error = error_message
            self.context.log(result.error, step_code=self.step_code)
            raise StepExecutionError(result.error) from e

    async def _execute_count_loop(self, result: StepExecutionResult, on_error: AutoTestLoopErrorStrategy) -> None:
        """次数循环模式"""
        loop_maximums = self.step.get("loop_maximums")
        if not loop_maximums:
            raise StepExecutionError("【循环结构】次数循环模式不允许loop_maximums参数为空")

        loop_interval = self.step.get("loop_interval")
        guard_limit = 100  # 安全限制

        self.context.log(f"【循环结构】次数循环开始: 最大循环次数: {loop_maximums}", step_code=self.step_code)
        for iteration in range(1, loop_maximums + 1):
            # 记录循环次数
            if self.step_code:
                self.context.step_cycle_index[self.step_code] = iteration
            self.context.log(f"【循环结构】次数循环: 第{iteration}/{loop_maximums}次执行", step_code=self.step_code)
            for child in self.children:
                child_code = child.get("step_code")
                if child_code:
                    self.context.step_cycle_index[child_code] = iteration
            try:
                # 执行子步骤
                child_results = await self._execute_children()
                for child in child_results:
                    result.append_child(child)
                    if not child.success:
                        result.success = False
                        if on_error == AutoTestLoopErrorStrategy.STOP:
                            raise StepExecutionError(
                                f"【循环结构】子步骤执行失败(错误处理策略: 停止整个用例执行), {child.error}")
                        elif on_error == AutoTestLoopErrorStrategy.BREAK:
                            self.context.log(
                                f"【循环结构】子步骤执行失败(错误处理策略: 中断循环), {child.error}",
                                step_code=self.step_code
                            )
                            return
                        elif on_error == AutoTestLoopErrorStrategy.CONTINUE:
                            self.context.log(
                                f"【循环结构】子步骤执行失败(错误处理策略: 继续下一次循环), {child.error}",
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
                error_message = f"【循环结构】次数循环: 第{iteration}次执行失败, 错误描述: {e}"
                self.context.log(error_message, step_code=self.step_code)
                result.success = False
                if on_error == AutoTestLoopErrorStrategy.STOP:
                    raise StepExecutionError(error_message) from e
                elif on_error == AutoTestLoopErrorStrategy.BREAK:
                    return

            # 循环间隔（最后一次不需要等待）
            if iteration < loop_maximums and loop_interval and loop_interval > 0:
                await self.context.sleep(loop_interval)

            # 安全检查
            if iteration >= guard_limit:
                raise StepExecutionError(
                    f"【循环结构】循环次数超过最大限制{guard_limit}次: 已执行 {iteration} 次, "
                    f"疑似无限循环, 为保护系统安全已自动终止循环"
                )

        self.context.log(f"【循环结构】次数循环结束: 共执行{loop_maximums}次", step_code=self.step_code)

    async def _execute_iterable_loop(self, result: StepExecutionResult, on_error: AutoTestLoopErrorStrategy) -> None:
        """对象循环模式"""
        loop_iterable = self.step.get("loop_iterable")
        if not loop_iterable:
            raise StepExecutionError("【循环结构】对象循环模式不允许loop_iterable参数为空")

        # 获取变量名（loop_iter_idx 是变量名，用于存储 enumerate 得到的索引值）
        loop_iter_idx = self.step.get("loop_iter_idx")
        if isinstance(loop_iter_idx, int):
            index_var_name = "loop_index"
        else:
            index_var_name = loop_iter_idx if loop_iter_idx else "loop_index"

        # 循环索引从1开始（enumerate的start参数固定为1）
        start_index = 1
        value_var_name = self.step.get("loop_iter_val") or "loop_value"
        loop_interval = self.step.get("loop_interval")

        # 解析可迭代对象来源
        try:
            iterable_obj = self._parse_iterable_source(loop_iterable)
            # 验证是否为可迭代对象（排除字符串和字节）
            if isinstance(iterable_obj, (str, bytes)):
                raise StepExecutionError(
                    f"【循环结构】对象循环模式: loop_iterable 必须是可迭代对象(列表, 元组等), "
                    f"当前类型: {type(iterable_obj).__name__}"
                )
            if not hasattr(iterable_obj, "__iter__"):
                raise StepExecutionError(
                    f"【循环结构】对象循环模式: loop_iterable 必须是可迭代对象(列表, 元组等), "
                    f"当前类型: {type(iterable_obj).__name__}"
                )
            # 转换为列表以便索引
            iterable_list = list(iterable_obj)
            total_items = len(iterable_list)
            if total_items == 0:
                self.context.log("【循环结构】对象循环: 可迭代对象为空, 跳过循环", step_code=self.step_code)
                return
            self.context.log(
                f"【循环结构】对象循环开始: "
                f"可迭代对象长度: {total_items}, "
                f"索引变量: {index_var_name}, "
                f"数据变量: {value_var_name}",
                step_code=self.step_code
            )
            for idx, item in enumerate(iterable_list, start=start_index):
                # 记录循环次数
                if self.step_code:
                    self.context.step_cycle_index[self.step_code] = idx
                self.context.log(
                    f"【循环结构】对象循环: 第{idx}/{total_items}次执行, 数据: {item}",
                    step_code=self.step_code
                )
                # 将循环变量注入到上下文
                self.context.update_variables(
                    {f"{index_var_name}_{idx}": idx, f"{value_var_name}_{idx}": item},
                    scope="session_variables"
                )
                # 为子步骤记录当前循环次数
                for child in self.children:
                    child_code = child.get("step_code")
                    if child_code:
                        self.context.step_cycle_index[child_code] = idx
                try:
                    # 执行子步骤
                    child_results = await self._execute_children()
                    for child in child_results:
                        result.append_child(child)
                        if not child.success:
                            result.success = False
                            if on_error == AutoTestLoopErrorStrategy.STOP:
                                raise StepExecutionError(f"【循环结构】子步骤执行失败(错误处理策略: 停止整个用例执行)")
                            elif on_error == AutoTestLoopErrorStrategy.BREAK:
                                self.context.log(
                                    f"【循环结构】子步骤执行失败(错误处理策略: 中断循环), {child.error}",
                                    step_code=self.step_code
                                )
                                return
                            elif on_error == AutoTestLoopErrorStrategy.CONTINUE:
                                # CONTINUE 模式继续下一次循环
                                self.context.log(
                                    f"【循环结构】子步骤执行失败(错误处理策略: 继续下一次循环), {child.error}",
                                    step_code=self.step_code
                                )
                                pass
                except StepExecutionError:
                    if on_error == AutoTestLoopErrorStrategy.STOP:
                        raise
                    elif on_error == AutoTestLoopErrorStrategy.BREAK:
                        return
                    elif on_error == AutoTestLoopErrorStrategy.CONTINUE:
                        # CONTINUE 模式继续下一次循环
                        pass
                except Exception as e:
                    error_message = f"【循环结构】对象循环: 第{idx}次执行失败, 错误描述: {e}"
                    self.context.log(error_message, step_code=self.step_code)
                    result.success = False
                    if on_error == AutoTestLoopErrorStrategy.STOP:
                        raise StepExecutionError(error_message) from e
                    elif on_error == AutoTestLoopErrorStrategy.BREAK:
                        return

                # 循环间隔（最后一次不需要等待）
                if idx < total_items and loop_interval and loop_interval > 0:
                    await self.context.sleep(loop_interval)

            self.context.log(f"【循环结构】对象循环结束: 共执行{total_items}次", step_code=self.step_code)

        except StepExecutionError:
            raise
        except Exception as e:
            raise StepExecutionError(f"【循环结构】对象循环执行异常: {e}") from e

    async def _execute_dict_loop(self, result: StepExecutionResult, on_error: AutoTestLoopErrorStrategy) -> None:
        """字典循环模式"""
        loop_iterable = self.step.get("loop_iterable")
        if not loop_iterable:
            raise StepExecutionError("【循环结构】字典循环模式不允许loop_iterable参数为空")

        # 获取变量名（loop_iter_idx 是索引变量名，loop_iter_key 是键变量名，loop_iter_val 是值变量名）
        loop_iter_idx = self.step.get("loop_iter_idx")
        if isinstance(loop_iter_idx, int):
            index_var_name = "loop_index"
        else:
            # 如果是字符串，直接使用；如果为空，使用默认值
            index_var_name = loop_iter_idx if loop_iter_idx else "loop_index"

        # 循环索引从1开始（enumerate的start参数固定为1）
        start_index = 1
        key_var_name = self.step.get("loop_iter_key") or "loop_key"
        value_var_name = self.step.get("loop_iter_val") or "loop_value"
        loop_interval = self.step.get("loop_interval")

        try:
            # 解析字典对象来源
            dict_obj = self._parse_iterable_source(loop_iterable)
            # 验证是否为字典
            if not isinstance(dict_obj, dict):
                raise StepExecutionError(
                    f"【循环结构】字典循环模式: loop_iterable 必须是字典类型, "
                    f"当前类型: {type(dict_obj).__name__}"
                )
            total_items = len(dict_obj)
            if total_items == 0:
                self.context.log("【循环结构】字典循环: 字典对象为空, 跳过循环", step_code=self.step_code)
                return

            self.context.log(
                f"【循环结构】字典循环开始: "
                f"字典键数量: {total_items}, "
                f"索引变量: {index_var_name}, "
                f"键变量: {key_var_name}, "
                f"值变量: {value_var_name}",
                step_code=self.step_code
            )
            for idx, (key, value) in enumerate(dict_obj.items(), start=start_index):
                # 记录循环次数
                if self.step_code:
                    self.context.step_cycle_index[self.step_code] = idx
                self.context.log(
                    f"【循环结构】字典循环: 第{idx}/{total_items}次执行, 键={key}, 值={value}",
                    step_code=self.step_code
                )
                # 将循环变量注入到上下文
                self.context.update_variables(
                    {f"{index_var_name}_{idx}": idx, f"{value_var_name}_{idx}": value},
                    scope="session_variables"
                )
                # 为子步骤记录当前循环次数
                for child in self.children:
                    child_code = child.get("step_code") or child.get("id") or ""
                    if child_code:
                        self.context.step_cycle_index[child_code] = idx

                # 执行子步骤
                try:
                    child_results = await self._execute_children()
                    for child in child_results:
                        result.append_child(child)
                        if not child.success:
                            result.success = False
                            if on_error == AutoTestLoopErrorStrategy.STOP:
                                raise StepExecutionError(f"【循环结构】子步骤执行失败(错误处理策略: 停止整个用例执行)")
                            elif on_error == AutoTestLoopErrorStrategy.BREAK:
                                self.context.log(
                                    f"【循环结构】子步骤执行失败(错误处理策略: 中断循环), {child.error}",
                                    step_code=self.step_code
                                )
                                return
                            elif on_error == AutoTestLoopErrorStrategy.CONTINUE:
                                # CONTINUE 模式继续下一次循环
                                self.context.log(
                                    f"【循环结构】子步骤执行失败(错误处理策略: 继续下一次循环), {child.error}",
                                    step_code=self.step_code
                                )
                                pass
                except StepExecutionError:
                    if on_error == AutoTestLoopErrorStrategy.STOP:
                        raise
                    elif on_error == AutoTestLoopErrorStrategy.BREAK:
                        return
                    elif on_error == AutoTestLoopErrorStrategy.CONTINUE:
                        # CONTINUE 模式继续下一次循环
                        pass
                except Exception as e:
                    error_message = f"【循环结构】字典循环: 第{idx}次执行失败, 错误描述: {e}"
                    self.context.log(error_message, step_code=self.step_code)
                    result.success = False
                    if on_error == AutoTestLoopErrorStrategy.STOP:
                        raise StepExecutionError(error_message) from e
                    elif on_error == AutoTestLoopErrorStrategy.BREAK:
                        return

                # 循环间隔（最后一次不需要等待）
                if idx < total_items and loop_interval and loop_interval > 0:
                    await self.context.sleep(loop_interval)

            self.context.log(f"【循环结构】字典循环结束: 共执行{total_items}次", step_code=self.step_code)

        except StepExecutionError:
            raise
        except Exception as e:
            raise StepExecutionError(f"【循环结构】字典循环执行异常: {e}") from e

    async def _execute_condition_loop(self, result: StepExecutionResult, on_error: AutoTestLoopErrorStrategy) -> None:
        """条件循环模式"""
        condition = self.step.get("conditions")
        if not condition:
            raise StepExecutionError("【循环结构】条件循环模式不允许conditions参数为空")

        loop_timeout = self.step.get("loop_timeout")
        loop_interval = self.step.get("loop_interval")
        guard_limit = 1000  # 安全限制

        # 记录开始时间（用于超时控制）
        start_time = time.time()
        iteration = 0
        should_continue = True

        self.context.log(
            f"【循环结构】条件循环开始: 超时时间={loop_timeout if loop_timeout else '无限制'}秒",
            step_code=self.step_code
        )
        while should_continue:
            iteration += 1
            if loop_timeout and loop_timeout > 0:
                elapsed = time.time() - start_time
                if elapsed >= loop_timeout:
                    self.context.log(
                        f"【循环结构】条件循环超时: 已执行 {iteration} 次, 耗时 {elapsed:.2f} 秒, 超过限制 {loop_timeout} 秒",
                        step_code=self.step_code
                    )
                    break
            # 记录循环次数
            if self.step_code:
                self.context.step_cycle_index[self.step_code] = iteration

            self.context.log(f"【循环结构】条件循环: 第{iteration}次执行", step_code=self.step_code)
            # 为子步骤记录当前循环次数
            for child in self.children:
                child_code = child.get("step_code") or child.get("id") or ""
                if child_code:
                    self.context.step_cycle_index[child_code] = iteration

            try:
                # 执行子步骤
                child_results = await self._execute_children()
                for child in child_results:
                    result.append_child(child)
                    if not child.success:
                        result.success = False
                        if on_error == AutoTestLoopErrorStrategy.STOP:
                            raise StepExecutionError(f"【循环结构】子步骤执行失败(错误处理策略: 停止整个用例执行)")
                        elif on_error == AutoTestLoopErrorStrategy.BREAK:
                            self.context.log(
                                f"【循环结构】子步骤执行失败(错误处理策略: 中断循环), {child.error}",
                                step_code=self.step_code
                            )
                            return
                        elif on_error == AutoTestLoopErrorStrategy.CONTINUE:
                            # CONTINUE 模式继续下一次循环
                            self.context.log(
                                f"【循环结构】子步骤执行失败(错误处理策略: 继续下一次循环), {child.error}",
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
                    # CONTINUE 模式继续下一次循环
                    pass
            except Exception as e:
                error_message = f"【循环结构】条件循环: 第{iteration}次执行失败, 错误描述: {e}"
                self.context.log(error_message, step_code=self.step_code)
                result.success = False
                if on_error == AutoTestLoopErrorStrategy.STOP:
                    raise StepExecutionError(error_message) from e
                elif on_error == AutoTestLoopErrorStrategy.BREAK:
                    should_continue = False
                    break

            if not should_continue:
                break
            try:
                if not self._evaluate_condition(condition):
                    self.context.log(f"【循环结构】条件循环: 条件不满足, 结束循环", step_code=self.step_code)
                    should_continue = False
                    break
            except Exception as e:
                result.success = False
                error_message = f"【循环结构】条件评估失败: {e}"
                result.error = error_message
                self.context.log(error_message, step_code=self.step_code)
                should_continue = False
                break

            # 安全检查
            if iteration >= guard_limit:
                raise StepExecutionError(
                    f"【循环结构】循环次数超过最大限制{guard_limit}次: 已执行 {iteration} 次, "
                    f"疑似无限循环, 为保护系统安全已自动终止循环"
                )

            # 循环间隔
            if loop_interval and loop_interval > 0:
                await self.context.sleep(loop_interval)

        self.context.log(f"【循环结构】条件循环结束: 共执行{iteration}次", step_code=self.step_code)

    def _evaluate_condition(self, condition: str) -> bool:
        try:
            # 处理 JSON 字符串中可能包含的 Python None/True/False
            # 使用正则表达式更精确地替换, 避免误替换字符串中的值
            # 替换独立的 None/True/False（前后不是字母数字或下划线）
            normalized_condition = re.sub(r'\bNone\b', 'null', condition)
            normalized_condition = re.sub(r'\bTrue\b', 'true', normalized_condition)
            normalized_condition = re.sub(r'\bFalse\b', 'false', normalized_condition)
            condition_obj = json.loads(normalized_condition)
        except json.JSONDecodeError as e:
            raise StepExecutionError(
                f"【循环结构】条件表达式不是有效的JSON格式, "
                f"错误位置: 第{e.lineno}行, 第{e.colno}列, "
                f"错误信息: {e.msg}"
            ) from e

        except Exception as e:
            raise StepExecutionError(f"【循环结构】条件表达式解析异常, 错误详情: {e}") from e

        value_expr = condition_obj.get("value")
        operation = condition_obj.get("operation")
        except_value = condition_obj.get("except_value")
        if value_expr is None or operation is None:
            raise StepExecutionError(f"【循环结构】条件表达式缺少必要字段: [value={value_expr}, operation={operation}]")

        try:
            resolved = self.context.resolve_placeholders(value_expr)
            if isinstance(resolved, str) and resolved.startswith("${") and resolved.endswith("}"):
                variable_name = resolved[2:-1]
                try:
                    value = self.context.get_variable(variable_name)
                except KeyError as e:
                    raise StepExecutionError(f"【循环结构】条件表达式中变量未定义: {variable_name}") from e
            else:
                value = resolved
        except Exception as e:
            if isinstance(e, StepExecutionError):
                raise
            raise StepExecutionError(f"【循环结构】条件表达式中占位符解析异常, 错误描述: {e}") from e
        try:
            return ConditionStepExecutor.compare(value, operation, except_value)
        except Exception as e:
            raise StepExecutionError(f"【循环结构】条件表达式执行异常, 错误描述: {e}") from e

    def _parse_iterable_source(self, source: Any) -> Any:
        """解析可迭代对象来源，支持变量引用、JSON字符串和直接对象"""
        try:
            # 先解析占位符
            resolved_source = self.context.resolve_placeholders(source)

            # 如果是字符串且以 ${ 开头，尝试获取变量
            if isinstance(resolved_source, str) and resolved_source.startswith("${") and resolved_source.endswith("}"):
                variable_name = resolved_source[2:-1]
                obj = self.context.get_variable(variable_name)
            elif isinstance(resolved_source, str):
                # 尝试解析 JSON 字符串
                try:
                    obj = json.loads(resolved_source)
                except (json.JSONDecodeError, ValueError):
                    # 如果不是 JSON，作为普通字符串处理
                    obj = resolved_source
            else:
                obj = resolved_source

            return obj
        except StepExecutionError:
            raise
        except Exception as e:
            raise StepExecutionError(f"【循环结构】解析可迭代对象来源失败: {e}") from e


class ConditionStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        try:
            condition = self.step.get("conditions")
            if not condition:
                raise StepExecutionError("【条件分支】缺少必要配置: conditions")

            # 处理 JSON 字符串中可能包含的 Python None/True/False
            # 使用正则表达式更精确地替换, 避免误替换字符串中的值
            # 替换独立的 None/True/False（前后不是字母数字或下划线）
            try:
                normalized_condition = re.sub(r'\bNone\b', 'null', condition)
                normalized_condition = re.sub(r'\bTrue\b', 'true', normalized_condition)
                normalized_condition = re.sub(r'\bFalse\b', 'false', normalized_condition)
                condition_obj = json.loads(normalized_condition)
            except json.JSONDecodeError as e:
                raise StepExecutionError(
                    f"【条件分支】条件表达式不是有效的JSON格式: "
                    f"错误位置: 第{e.lineno}行, 第{e.colno}列, "
                    f"错误类型: {type(e).__name__}"
                    f"错误信息: {e}"
                ) from e
            except Exception as e:
                raise StepExecutionError(f"【条件分支】条件表达式解析异常, 错误详情: {e}") from e

            value_expr = condition_obj.get("value")
            operation = condition_obj.get("operation")
            except_value = condition_obj.get("except_value")
            desc = condition_obj.get("desc", "")
            if value_expr is None or operation is None:
                raise StepExecutionError(
                    f"【条件分支】条件表达式缺少必要字段: [value={value_expr}, operation={operation}]")
            try:
                resolved_value_expr = self.context.resolve_placeholders(value_expr)
            except StepExecutionError:
                raise
            except Exception as e:
                raise StepExecutionError(f"【条件分支】条件表达式占位符解析异常, 错误详情: {e}") from e

            try:
                if isinstance(resolved_value_expr, str) and resolved_value_expr.startswith(
                        "${") and resolved_value_expr.endswith("}"):
                    variable_name = resolved_value_expr[2:-1]
                    try:
                        value = self.context.get_variable(variable_name)
                    except KeyError as e:
                        raise StepExecutionError(f"【条件分支】条件表达式中变量未定义: {variable_name}") from e
                else:
                    value = resolved_value_expr
            except StepExecutionError:
                raise
            except Exception as e:
                raise StepExecutionError(f"【条件分支】条件表达式中变量解析异常, 错误描述: {e}") from e

            try:
                if not self.compare(value, operation, except_value):
                    result.success = True
                    result.message = f"【条件分支】条件未满足: {desc}"
                    self.context.log(result.message, step_code=self.step_code)
                    return
            except Exception as e:
                raise StepExecutionError(f"【条件分支】条件表达式执行异常, 错误描述: {e}") from e

            result.message = f"【条件分支】条件满足: {desc}"
            self.context.log(result.message, step_code=self.step_code)
            try:
                child_results = await self._execute_children()
                for child in child_results:
                    result.append_child(child)
                    if not child.success:
                        result.success = False
            except Exception as e:
                result.success = False
                error_message: str = f"【条件分支】执行条件分支子步骤失败: {e}"
                result.error = error_message
                self.context.log(error_message, step_code=self.step_code)
        except Exception as e:
            # 捕获条件判断的异常, 避免阻断后续执行
            error_message: str = (
                f"【条件分支】步骤执行失败: "
                f"用例ID: {self.case_id}, "
                f"步骤序号: {self.step_no}, "
                f"步骤标识: {self.step_code}, "
                f"步骤名称: {self.step_name}, "
                f"步骤类型: {self.step_type}, "
                f"错误类型: {type(e).__name__}, "
                f"错误详情: {e}"
            )
            result.success = False
            result.error = error_message
            self.context.log(result.error, step_code=self.step_code)

    @staticmethod
    def compare(value: Any, operation: str, except_value: Any) -> bool:
        try:
            # 使用 AutoTestToolService 的统一比较方法，确保与断言验证逻辑一致
            return AutoTestToolService.compare_assertion(value, operation, except_value)
        except ValueError as e:
            raise StepExecutionError(f"【条件分支】条件比较失败: {e}") from e


class PythonStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        try:
            code = self.step.get("code")
            if not code:
                raise StepExecutionError("【执行代码请求(Python)】缺少必要配置: code")

            try:
                run_code_st = datetime.now()
                new_vars = self.context.run_python_code(code, namespace=self.context.clone_state())
                run_code_ed = datetime.now()
            except StepExecutionError:
                raise
            except Exception as e:
                error_message: str = (
                    f"【执行代码请求(Python)】步骤执行失败: "
                    f"用例ID: {self.case_id}, "
                    f"步骤序号: {self.step_no}, "
                    f"步骤标识: {self.step_code}, "
                    f"步骤名称: {self.step_name}, "
                    f"步骤类型: {self.step_type}, "
                    f"错误类型: {type(e).__name__}, "
                    f"错误详情: {e}"
                )
                raise StepExecutionError(error_message) from e

            if new_vars:
                try:
                    import json
                    self.context.update_variables(new_vars, scope="extract_variables")
                    result.extract_variables.update(new_vars)
                    result.response = {
                        "elapsed": f"{(run_code_ed - run_code_st).total_seconds():.3f}",
                        "headers": {},
                        "cookies": None,
                        "text": json.dumps(new_vars, ensure_ascii=False)
                    }
                except Exception as e:
                    raise StepExecutionError(f"【更新变量】-【extract_variables】失败: {e}") from e
        except StepExecutionError:
            raise
        except Exception as e:
            error_message: str = (
                f"【执行代码请求(Python)】步骤执行失败: "
                f"用例ID: {self.case_id}, "
                f"步骤序号: {self.step_no}, "
                f"步骤标识: {self.step_code}, "
                f"步骤名称: {self.step_name}, "
                f"步骤类型: {self.step_type}, "
                f"错误类型: {type(e).__name__}, "
                f"错误详情: {e}"
            )
            result.success = False
            result.error = error_message
            self.context.log(error_message, step_code=self.step_code)
            raise StepExecutionError(error_message) from e


class WaitStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        try:
            wait_seconds = self.step.get("wait")
            if wait_seconds is None:
                raise StepExecutionError("【等待控制】缺少必要配置: wait")

            try:
                wait_float = float(wait_seconds)
            except (ValueError, TypeError) as e:
                raise StepExecutionError(
                    f"【等待控制】参数[wait]必须是[float]类型, 且不允许小于0, "
                    f"但得到[{type(wait_seconds)}]类型: {wait_seconds}, 错误: {e}"
                ) from e

            try:
                await self.context.sleep(wait_float)
            except StepExecutionError:
                raise
            except Exception as e:
                raise StepExecutionError(f"【等待控制】步骤执行失败: {e}") from e
        except StepExecutionError:
            raise
        except Exception as e:
            error_message: str = (
                f"【等待控制】步骤执行异常: "
                f"用例ID: {self.case_id}, "
                f"步骤序号: {self.step_no}, "
                f"步骤标识: {self.step_code}, "
                f"步骤名称: {self.step_name}, "
                f"步骤类型: {self.step_type}, "
                f"错误类型: {type(e).__name__}, "
                f"错误详情: {e}"
            )
            result.success = False
            result.error = error_message
            self.context.log(result.error, step_code=self.step_code)
            raise StepExecutionError(result.error) from e


class QuoteCaseStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        try:
            quote_case_id = self.step.get("quote_case_id")
            if not quote_case_id:
                raise StepExecutionError("【引用公共用例】缺少必要配置: quote_case_id")

            try:
                from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
                quote_case_instance: AutoTestApiCaseInfo = await AUTOTEST_API_CASE_CRUD.get_by_conditions(
                    only_one=True,
                    on_error=True,
                    conditions={
                        "id": quote_case_id,
                        "case_type": AutoTestCaseType.PUBLIC_SCRIPT.value
                    }
                )
            except (ParameterException, NotFoundException) as e:
                raise StepExecutionError(f"【引用公共用例】用例(id={quote_case_id})不存在, 错误描述: {e.message}") from e
            except Exception as e:
                raise StepExecutionError(f"【引用公共用例】用例(id={quote_case_id})查询异常, 错误描述: {e}") from e

            quote_case_dict = await quote_case_instance.to_dict(
                include_fields={"id", "case_code", "case_name"},
                replace_fields={"id": "case_id"}
            )
            quote_case_name: str = quote_case_dict["case_name"]
            try:
                from backend.applications.aotutest.services.autotest_step_crud import AUTOTEST_API_STEP_CRUD
                quote_steps = await AUTOTEST_API_STEP_CRUD.get_by_case_id(case_id=quote_case_id)
                if not quote_steps:
                    self.context.log(
                        f"【引用公共用例】用例(id={quote_case_id})暂无任何可执行步骤数据",
                        step_code=self.step_code
                    )
                    return
                quote_steps.pop(-1)
            except Exception as e:
                raise StepExecutionError(
                    f"【引用公共用例】获取用例(id={quote_case_id})步骤树数据异常, 错误描述: {e}") from e

            self.context.log(
                f"【引用公共用例】执行用例(id={quote_case_id}, name={quote_case_name})开始",
                step_code=self.step_code
            )
            normalized_steps = [AutoTestToolService.normalize_step(step) for step in quote_steps]
            ordered_steps = sorted(normalized_steps, key=lambda item: item.get("step_no", 0))
            for quote_step in ordered_steps:
                try:
                    executor = StepExecutorFactory.create_executor(quote_step, self.context)
                    child_result = await executor.execute()
                    result.append_child(child_result)
                    if not child_result.success:
                        result.success = False
                except StepExecutionError:
                    raise
                except Exception as e:
                    case_id: int = quote_step.get("case_id")
                    step_id: int = quote_step.get("step_id")
                    step_no: int = quote_step.get("step_no")
                    step_code: str = quote_step.get("step_code")
                    step_name: str = quote_step.get("step_name")
                    step_type: str = quote_step.get("step_type")
                    error_message: str = (
                        f"【引用公共用例】步骤执行失败: "
                        f"用例ID: {case_id}, "
                        f"步骤序号: {step_no}, "
                        f"步骤标识: {step_code}, "
                        f"步骤名称: {step_name}, "
                        f"步骤类型: {step_type}, "
                        f"错误类型: {type(e).__name__}, "
                        f"错误详情: {e}"
                    )
                    self.context.log(error_message, step_code=step_code)
                    failed_result = StepExecutionResult(
                        case_id=case_id,
                        step_id=step_id,
                        step_no=step_no,
                        step_code=step_code,
                        step_name=step_name,
                        step_type=AutoTestStepType(step_type),
                        quote_case_id=quote_step.get("quote_case_id"),
                        success=False,
                        error=error_message
                    )
                    result.append_child(failed_result)
            self.context.log(
                f"【引用公共用例】执行用例(id={quote_case_id}, name={quote_case_name})结束",
                step_code=self.step_code
            )
        except StepExecutionError:
            raise
        except Exception as e:
            error_message: str = (
                f"【引用公共用例】步骤执行失败: "
                f"用例ID: {self.case_id}, "
                f"步骤序号: {self.step_no}, "
                f"步骤标识: {self.step_code}, "
                f"步骤名称: {self.step_name}, "
                f"步骤类型: {self.step_type}, "
                f"错误类型: {type(e).__name__}, "
                f"错误详情: {e}"
            )
            result.success = False
            result.error = error_message
            self.context.log(error_message, step_code=self.step_code)
            raise StepExecutionError(error_message) from e


class TcpStepExecutor(BaseStepExecutor):
    pass


class DataBaseStepExecutor(BaseStepExecutor):
    pass


class HttpStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        try:
            env: str = self.context.env
            step_type: str = self.step.get("step_type")
            request_url: str = self.step.get("request_url")
            request_project: str = self.step.get("request_project")
            request_method: str = self.step.get("request_method", "").upper()
            if env and step_type == AutoTestStepType.HTTP and not request_url.lower().startswith("http"):
                try:
                    env_instance: AutoTestApiEnvInfo = await AutoTestApiEnvInfo.filter(
                        project_id=request_project,
                        env_name=env,
                    ).first()
                    if not env_instance:
                        raise StepExecutionError(f"【HTTP请求】环境(project_id={request_project}, name={env})配置不存在")
                    execute_environment_host: str = env_instance.env_host.rstrip("/")
                    if not execute_environment_host:
                        raise StepExecutionError(
                            f"【HTTP请求】环境(project_id={request_project}, "
                            f"name={env}, host={execute_environment_host})配置异常"
                        )
                    request_url = f"{execute_environment_host}/{request_url.lstrip('/')}"
                except StepExecutionError:
                    raise
                except Exception as e:
                    raise StepExecutionError(f"【HTTP请求】环境配置查询异常, 错误描述: {e}") from e

            if request_url and not request_url.startswith("http"):
                raise StepExecutionError(
                    f"【HTTP请求】请求URL({request_url})不是有效的HTTP/HTTPS地址"
                )
            if not request_url:
                raise StepExecutionError("【HTTP请求】HTTP请求配置错误: 请求URL(request_url)未配置")

            # 处理变量占位符
            headers = self.context.resolve_placeholders(self.step.get("request_header") or {})
            params = self.context.resolve_placeholders(self.step.get("request_params") or {})
            form_data = self.context.resolve_placeholders(self.step.get("request_form_data") or {})
            urlencoded = self.context.resolve_placeholders(self.step.get("request_form_urlencoded") or {})
            request_body = self.context.resolve_placeholders(self.step.get("request_body"))
            request_text = self.context.resolve_placeholders(self.step.get("request_text"))
            form_files = self.step.get("request_form_file")
            data_payload: Optional[Any] = None
            json_payload: Optional[Any] = None
            if request_text:
                data_payload = self.context.resolve_placeholders(request_text)
            elif form_data:
                data_payload = form_data
            elif urlencoded:
                data_payload = urlencoded
            if request_body:
                json_payload = request_body

            params_payload = params if isinstance(params, dict) else None

            try:
                response = await self.context.send_http_request(
                    request_method,
                    request_url,
                    headers=headers or None,
                    params=params_payload,
                    data=data_payload,
                    json_data=json_payload,
                    files=form_files,
                )
            except httpx.RequestError as e:
                raise StepExecutionError(
                    f"【HTTP请求】请求 {request_method} {request_url} 时发生网络错误, 错误详情: {e}"
                ) from e
            except httpx.HTTPStatusError as e:
                # HTTP状态错误不一定是失败, 记录响应继续处理
                response = e.response
                self.context.log(
                    f"【HTTP请求】响应状态码异常: 服务器返回状态码 {e.response.status_code}, 将继续处理响应",
                    step_code=self.step_code
                )
            except Exception as e:
                raise StepExecutionError(
                    f"【HTTP请求】请求 {request_method} {request_url} 时发生未预期的异常, 错误详情: {e}"
                ) from e

            try:
                cookies = {}
                if response.cookies:
                    for cookie in response.cookies.jar:
                        cookies[cookie.name] = cookie.value

                result.response = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "text": response.text,
                    "cookies": cookies,
                    "elapsed": str(response.elapsed.total_seconds()),
                }
            except AttributeError as e:
                raise StepExecutionError(f"【HTTP请求】响应对象缺少必要属性, 错误详情: {e}") from e
            except Exception as e:
                raise StepExecutionError(
                    f"【HTTP请求】在提取响应状态码、内容、headers、cookies时失败, 错误详情: {e}") from e

            try:
                response_json = response.json()
            except (ValueError, json.JSONDecodeError):
                response_json = None
            except Exception as e:
                self.context.log(f"【HTTP请求】响应JSON解析失败: {e}, 将使用文本响应", step_code=self.step_code)
                response_json = None

            try:
                extract_variables = self._extract_variables(
                    response_json=response_json,
                    response_text=result.response.get("text") if result.response else None,
                    response_headers=result.response.get("response_headers") if result.response else None,
                    response_cookies=result.response.get("response_cookies") if result.response else None,
                )
                if extract_variables:
                    # 提取变量同时放入会话变量, 便于后续步骤引用
                    self.context.update_variables(extract_variables, scope="session_variables")
                    self.context.update_variables(extract_variables, scope="extract_variables")
                    result.extract_variables.update(extract_variables)
            except StepExecutionError:
                raise
            except Exception as e:
                error_message: str = f"【HTTP请求】变量提取失败: {e}"
                # 变量提取失败不影响请求成功, 只记录错误
                self.context.log(error_message, step_code=self.step_code)

            try:
                validator_results = self._run_validators(
                    response_json=response_json,
                    response_text=result.response.get("text") if result.response else None,
                    response_headers=result.response.get("response_headers") if result.response else None,
                    response_cookies=result.response.get("response_cookies") if result.response else None,
                )
                result.assert_validators.extend(validator_results)
                assert_failed_number: int = 0
                for valid in validator_results:
                    valid_status: bool = valid.get("success", True)
                    expr_message: str = (
                        f"实际值: [{valid.get('expr')}], "
                        f"操作符: [{valid.get('operation')}], "
                        f"预期值: [{valid.get('except_value')}]"
                    )
                    if valid_status:
                        self.context.log(f"【断言验证】- 成功: {expr_message}", step_code=self.step_code)
                    else:
                        self.context.log(f"【断言验证】- 失败: {expr_message}", step_code=self.step_code)
                        assert_failed_number += 1
                    if assert_failed_number > 0:
                        error_message: str = f"【断言验证】- 共计: {assert_failed_number}个断言验证未通过"
                        raise StepExecutionError(error_message)
            except StepExecutionError:
                raise
            except Exception as e:
                error_message: str = f"【断言验证】在运行断言检查时发生异常, 错误详情: {e}"
                self.context.log(error_message, step_code=self.step_code)
                raise StepExecutionError(error_message) from e
        except StepExecutionError:
            raise
        except Exception as e:
            error_message: str = (
                f"【HTTP请求】步骤执行失败: "
                f"用例ID: {self.case_id}, "
                f"步骤序号: {self.step_no}, "
                f"步骤标识: {self.step_code}, "
                f"步骤名称: {self.step_name}, "
                f"步骤类型: {self.step_type}, "
                f"错误类型: {type(e).__name__}, "
                f"错误详情: {e}"
            )
            result.success = False
            result.error = error_message
            self.context.log(error_message, step_code=self.step_code)
            raise StepExecutionError(result.error) from e

    def _extract_variables(
            self,
            *,
            response_text: Optional[str] = None,
            response_json: Optional[Union[list, dict]] = None,
            response_headers: Optional[Dict[str, Any]] = None,
            response_cookies: Optional[Dict[str, Any]] = None,

    ) -> Dict[str, Any]:
        try:
            extract_variables = self.step.get("extract_variables")
            if not extract_variables or response_json is None:
                return {}
            if not isinstance(extract_variables, list):
                raise StepExecutionError(
                    f"【变量提取】表达式列表解析失败: "
                    f"参数[extract_variables]必须是[List[Dict[str, Any]]]类型, "
                    f"但得到[{type(extract_variables)}]类型"
                )
            extract_results = {}
            for ext_config in extract_variables:
                if not isinstance(ext_config, dict):
                    self.context.log(
                        f"【变量提取】表达式子项解析无效(跳过): "
                        f"参数[extract_variables]的子项必须是[Dict[str, Any]]类型, "
                        f"但得到[{type(ext_config)}]类型: {ext_config}"
                    )
                    continue
                name: Optional[str] = ext_config.get("name")
                expr: Optional[str] = ext_config.get("expr")
                source: Optional[str] = ext_config.get("source")
                range_type: Optional[str] = ext_config.get("range")
                index: Optional[int] = ext_config.get("index")
                if not name or not expr or not source:
                    self.context.log(
                        f"【变量提取】表达式子项解析无效(跳过): "
                        f"参数[name, expr, source]是必须的, 如需继续提取可添加[range, index]参数"
                    )
                    continue
                try:
                    extracted_value = self._extract_from_source(
                        source=source,
                        expr=expr,
                        range_type=range_type,
                        index=index,
                        response_text=response_text,
                        response_json=response_json,
                        response_headers=response_headers,
                        response_cookies=response_cookies,
                        operation_type="变量提取"
                    )
                    extract_results[name] = extracted_value
                    self.context.log(
                        f"【变量提取】[{name}]: 从[{source}]中提取成功, 数据: {extracted_value}",
                        step_code=self.step_code
                    )
                except StepExecutionError:
                    raise
                except Exception as e:
                    # 继续处理其他变量, 不中断
                    self.context.log(
                        f"【变量提取】[{name}]: 从[{source}]中提取失败, 原因: {e}",
                        step_code=self.step_code
                    )
            return extract_results
        except StepExecutionError:
            raise
        except Exception as e:
            error_message: str = (
                f"【变量提取】步骤执行失败: "
                f"用例ID: {self.case_id}, "
                f"步骤序号: {self.step_no}, "
                f"步骤标识: {self.step_code}, "
                f"步骤名称: {self.step_name}, "
                f"步骤类型: {self.step_type}, "
                f"错误类型: {type(e).__name__}, "
                f"错误详情: {e}"
            )
            raise StepExecutionError(error_message) from e

    def _extract_from_source(
            self,
            *,
            source: str,
            expr: Optional[str],
            range_type: str = "SOME",
            index: Optional[int] = None,
            response_text: Optional[str] = None,
            response_json: Optional[Union[list, dict]] = None,
            response_headers: Optional[Dict[str, Any]] = None,
            response_cookies: Optional[Dict[str, Any]] = None,
            operation_type: str = "变量提取"
    ):

        if source.lower() == "response json":
            if not response_json:
                raise StepExecutionError(f"【{operation_type}】响应内容不是有效的JSON数据")
            if range_type.lower() == "all":
                return response_json
            else:
                if not expr:
                    raise StepExecutionError(
                        f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是有效的JSONPath表达式")
                try:
                    extracted = AutoTestToolService.resolve_json_path(data=response_json, expr=expr)
                except Exception as e:
                    raise StepExecutionError(str(e)) from e
                if isinstance(extracted, list) and index is not None:
                    try:
                        index_int: int = int(index)
                        if index < len(extracted):
                            return extracted[index_int]
                        else:
                            raise StepExecutionError(
                                f"【{operation_type}】数组越界, 给定索引[{index_int}]不可大于数组长度[{len(extracted)}]"
                            )
                    except (ValueError, TypeError) as e:
                        raise StepExecutionError(
                            f"【{operation_type}】参数[index]必须是数字类型, 错误描述: {e}"
                        ) from e
                return extracted

        elif source.lower() == "response xml":
            if not response_text:
                raise StepExecutionError(f"【{operation_type}】响应内容不是有效的XML数据")
            if range_type.lower() == "all":
                return response_text
            else:
                if not expr:
                    raise StepExecutionError(
                        f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是有效的XPath表达式")
                else:
                    try:
                        response_xml = ET.fromstring(response_text)
                        elements = response_xml.findall(expr)
                        if not elements:
                            raise StepExecutionError(f"【{operation_type}】XPath表达式[{expr}]未匹配到元素")
                        if index is not None:
                            try:
                                index_int: int = int(index)
                                if index_int < len(elements):
                                    element = elements[index_int]
                                    return element.text if element.text else ET.tostring(element, encoding='Unicode')
                                else:
                                    raise StepExecutionError(
                                        f"【{operation_type}】数组越界, 给定索引[{index_int}]不可大于数组长度[{len(elements)}]"
                                    )
                            except (ValueError, TypeError) as e:
                                raise StepExecutionError(
                                    f"【{operation_type}】参数[index]必须是数字类型, 错误描述: {e}"
                                ) from e
                        else:
                            element = elements[-1]
                            return element.text if element.text else ET.tostring(element, encoding='Unicode')
                    except ET.ParseError as e:
                        raise StepExecutionError(f"【{operation_type}】响应内容不是XML格式, 错误描述: {e}") from e
                    except Exception as e:
                        raise StepExecutionError(f"【{operation_type}】XPath表达式[{expr}]执行失败, 错误描述: {e}") from e

        elif source.lower() == "response text":
            if not response_text:
                raise StepExecutionError(f"【{operation_type}】响应内容不是有效的Text数据")
            if range_type.lower() == "all":
                return response_text
            else:
                if not expr:
                    raise StepExecutionError(
                        f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是有效的正则表达式")
                else:
                    try:
                        match = re.search(expr, response_text)
                        if match:
                            return match.group(0)
                        else:
                            raise StepExecutionError(f"【{operation_type}】正则表达式[{expr}]未匹配到内容")
                    except re.error as e:
                        raise StepExecutionError(f"【{operation_type}】正则表达式执行失败, 错误描述: {e}") from e

        elif source.lower() == "response header":
            if not response_headers:
                raise StepExecutionError(f"【{operation_type}】响应header为空")
            if range_type.lower() == "all":
                return response_headers
            else:
                if not expr:
                    raise StepExecutionError(f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是存在的键名")
                var = response_headers.get(expr)
                if not var:
                    raise StepExecutionError(f"【{operation_type}】响应 Headers 中不存在: {expr}")
                return var

        elif source.lower() == "response cookie":
            if not response_cookies:
                raise StepExecutionError(f"【{operation_type}】响应Cookie为空")
            if range_type.lower() == "all":
                return response_cookies
            else:
                if not expr:
                    raise StepExecutionError(f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是存在的键名")
                var = response_cookies.get(expr)
                if not var:
                    raise StepExecutionError(f"【{operation_type}】响应 Cookies 中不存在: {expr}")
                return var

        elif source.lower() == "session_variables" or source == "变量池":
            if not expr:
                raise StepExecutionError(f"【{operation_type}】模式[SOME]下参数[expr]是必须的, 并且需要是存在的键名")
            try:
                return self.context.get_variable(expr)
            except KeyError:
                raise StepExecutionError(f"【{operation_type}】在变量池[Session Variables Pool]中未找到[{expr}]变量")

        else:
            raise StepExecutionError(f"【{operation_type}】源类型 {source} 不被支持")

    def _run_validators(
            self,
            *,
            response_text: Optional[str] = None,
            response_json: Optional[Union[list, dict]] = None,
            response_headers: Optional[Dict[str, Any]] = None,
            response_cookies: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        try:
            assert_validators = self.step.get("assert_validators")
            if not assert_validators:
                return []
            if not isinstance(assert_validators, list):
                raise StepExecutionError(
                    f"【断言验证】表达式列表解析失败: "
                    f"参数[extract_variables]必须是[List[Dict[str, Any]]]类型, "
                    f"但得到[{type(assert_validators)}]类型"
                )
            valid_results: List[Dict[str, Any]] = []
            for validator_config in assert_validators:
                if not isinstance(validator_config, dict):
                    self.context.log(
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
                if not expr or not operation or not except_value:
                    self.context.log(
                        f"【断言验证】表达式子项解析无效(跳过): "
                        f"参数[name, expr, source]是必须的, 如需继续提取可添加[range, index]参数",
                        step_code=self.step_code
                    )
                    continue

                try:
                    actual_value = self._extract_from_source(
                        source=source,
                        expr=expr,
                        range_type="SOME",
                        index=None,
                        response_text=response_text,
                        response_json=response_json,
                        response_headers=response_headers,
                        response_cookies=response_cookies,
                        operation_type="断言验证"
                    )
                except StepExecutionError:
                    raise
                except Exception as e:
                    raise StepExecutionError(f"【断言验证】提取实际值失败, 错误描述: {e}") from e

                try:
                    success = ConditionStepExecutor.compare(actual_value, operation, except_value)
                except StepExecutionError:
                    raise
                except Exception as e:
                    raise StepExecutionError(f"【断言验证】比较失败: [{validator_config}], 错误描述: {e}") from e
                valid_results.append({
                    "name": name,
                    "expr": expr,
                    "source": source,
                    "operation": operation,
                    "except_value": except_value,
                    "actual_value": actual_value,
                    "success": success,
                })

            return valid_results
        except StepExecutionError:
            raise
        except Exception as e:
            error_message: str = (
                f"【断言验证】步骤执行失败: "
                f"用例ID: {self.case_id}, "
                f"步骤序号: {self.step_no}, "
                f"步骤标识: {self.step_code}, "
                f"步骤名称: {self.step_name}, "
                f"步骤类型: {self.step_type}, "
                f"错误类型: {type(e).__name__}, "
                f"错误详情: {e}"
            )
            raise StepExecutionError(error_message) from e


class DefaultStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        try:
            # 默认只执行子步骤
            child_results = await self._execute_children()
            for child in child_results:
                result.append_child(child)
                if not child.success:
                    result.success = False
        except Exception as e:
            error_message: str = (
                f"【默认步骤】步骤执行失败: "
                f"用例ID: {self.case_id}, "
                f"步骤序号: {self.step_no}, "
                f"步骤标识: {self.step_code}, "
                f"步骤名称: {self.step_name}, "
                f"步骤类型: {self.step_type}, "
                f"错误类型: {type(e).__name__}, "
                f"错误详情: {e}"
            )
            result.success = False
            result.error = error_message
            self.context.log(error_message, step_code=self.step_code)
            raise StepExecutionError(error_message) from e


class StepExecutorFactory:
    """根据 AutoTestStepType 创建对应执行器。"""

    EXECUTOR_MAP: Dict[AutoTestStepType, Callable[[Dict[str, Any], StepExecutionContext], BaseStepExecutor]] = {
        AutoTestStepType.TCP: TcpStepExecutor,
        AutoTestStepType.HTTP: HttpStepExecutor,
        AutoTestStepType.PYTHON: PythonStepExecutor,
        AutoTestStepType.DATABASE: DataBaseStepExecutor,
        AutoTestStepType.LOOP: LoopStepExecutor,
        AutoTestStepType.IF: ConditionStepExecutor,
        AutoTestStepType.WAIT: WaitStepExecutor,
        AutoTestStepType.QUOTE: QuoteCaseStepExecutor,
    }

    @classmethod
    def create_executor(cls, step: Dict[str, Any], context: StepExecutionContext) -> BaseStepExecutor:
        try:
            step_type_str = step.get("step_type")
            if not step_type_str:
                raise StepExecutionError("步骤类型未定义")

            try:
                step_type = AutoTestStepType(step_type_str)
            except (ValueError, TypeError) as exc:
                raise StepExecutionError(f"无效的步骤类型: {step_type_str}") from exc

            executor_cls = cls.EXECUTOR_MAP.get(step_type, DefaultStepExecutor)
            if executor_cls is None:
                raise StepExecutionError(f"未找到步骤类型 {step_type} 对应的执行器")

            try:
                return executor_cls(step, context)
            except Exception as exc:
                raise StepExecutionError(f"创建执行器失败: {exc}") from exc
        except StepExecutionError:
            raise
        except Exception as exc:
            raise StepExecutionError(f"创建执行器异常: {exc}") from exc


class AutoTestStepExecutionEngine:
    """ 测试步骤执行引擎入口 """

    def __init__(
            self, *,
            http_client: Optional[HttpClientProtocol] = None,
            save_report: bool = True,
            task_code: Optional[str] = None,
    ) -> None:
        self._http_client = http_client
        self._save_report = save_report
        self._task_code = task_code
        self._report_code: Optional[str] = None

    async def execute_case(
            self,
            case: Dict[str, Any],
            steps: Iterable[Dict[str, Any]],
            report_type: AutoTestReportType,
            *,
            execute_environment: Optional[str] = None,
            initial_variables: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[StepExecutionResult], Dict[str, List[str]], Optional[str], Dict[str, Any], Dict[str, Any]]:
        report_code = None
        case_start_time = datetime.now()
        case_id: int = case.get("case_id")
        case_code: str = case.get("case_code")
        case_name: str = case.get("case_name")
        case_st_time_str = case_start_time.strftime("%Y-%m-%d %H:%M:%S.%f")
        if self._save_report:
            try:
                user_id = CTX_USER_ID.get(0)
                user_name = str(user_id) if user_id else None
                # 如果没有指定report_type, 默认使用EXEC1（执行方式1）
                final_report_type = report_type if report_type is not None else AutoTestReportType.EXEC1
                report_create = AutoTestApiReportCreate(
                    case_id=case_id,
                    case_code=case_code,
                    case_name=case_name,
                    case_st_time=case_st_time_str,
                    case_state=False,
                    step_total=0,
                    step_fill_count=0,
                    step_pass_count=0,
                    step_pass_ratio=0.0,
                    report_type=final_report_type,
                    created_user=user_name,
                    task_code=self._task_code
                )
                from backend.applications.aotutest.services.autotest_report_crud import AUTOTEST_API_REPORT_CRUD
                report_instance = await AUTOTEST_API_REPORT_CRUD.create_report(report_create)
                report_code = report_instance.report_code
                self._report_code = report_code
            except Exception as e:
                error_message: str = f"创建测试报告失败: 用例ID={case_id}, 用例编码={case_code}, 错误详情: {e}"
                raise StepExecutionError(error_message) from e

        async with StepExecutionContext(
                case_id=case_id,
                case_code=case_code,
                env=execute_environment,
                initial_variables=initial_variables,
                http_client=self._http_client,
                report_code=report_code,
        ) as context:
            ordered_root_steps = sorted(steps, key=lambda item: item.get("step_no", 0))
            results: List[StepExecutionResult] = []
            for step in ordered_root_steps:
                context.step_code = step.get("step_code")
                executor = StepExecutorFactory.create_executor(step, context)
                result = await executor.execute()
                results.append(result)
                # 对于根步骤（parent_step_id 为 None）, 汇总所有子步骤的日志
                if step.get("parent_step_id") is None:
                    root_step_code = step.get("step_code")
                    if root_step_code is not None:
                        self._aggregate_root_step_logs(context, result, root_step_code)

            # 统计（按 step_code 去重合并）
            all_results = self._collect_all_results(results)
            unique_states: Dict[str, bool] = {}
            for r in all_results:
                key = r.step_code
                if key not in unique_states:
                    unique_states[key] = True
                if not r.success:
                    unique_states[key] = False

            total_steps = len(unique_states)
            success_steps = sum(1 for v in unique_states.values() if v)
            failed_steps = total_steps - success_steps
            pass_ratio = (success_steps / total_steps * 100) if total_steps > 0 else 0.0

            case_end_time = datetime.now()
            case_ed_time_str = case_end_time.strftime("%Y-%m-%d %H:%M:%S")
            case_elapsed = f"{(case_end_time - case_start_time).total_seconds():.3f}"
            case_state = failed_steps == 0

            if self._save_report and report_code:
                try:
                    user_id = CTX_USER_ID.get(0)
                    user_name = str(user_id) if user_id else None
                    report_update = AutoTestApiReportUpdate(
                        report_code=report_code,
                        case_ed_time=case_ed_time_str,
                        case_elapsed=case_elapsed,
                        case_state=case_state,
                        step_total=total_steps,
                        step_fill_count=failed_steps,
                        step_pass_count=success_steps,
                        step_pass_ratio=pass_ratio,
                        updated_user=user_name
                    )
                    from backend.applications.aotutest.services.autotest_report_crud import AUTOTEST_API_REPORT_CRUD
                    await AUTOTEST_API_REPORT_CRUD.update_report(report_update)
                except Exception as e:
                    error_message: str = f"更新测试报告失败: 报告编码={report_code}, 错误详情: {e}"
                    raise StepExecutionError(error_message) from e

                try:
                    from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
                    await AUTOTEST_API_CASE_CRUD.update_case(AutoTestApiCaseUpdate(
                        case_id=case_id,
                        case_state=case_state,
                        case_last_time=case_ed_time_str
                    ))
                except Exception as e:
                    error_message: str = f"更新测试用例失败: 用例ID={case_id}, 用例代码={case_code}, 错误详情: {e}"
                    raise StepExecutionError(error_message) from e

            statistics = {
                "total_steps": total_steps,
                "success_steps": success_steps,
                "failed_steps": failed_steps,
                "pass_ratio": round(pass_ratio, 2)
            }

            # 返回会话变量（用于调试模式）
            session_variables = dict(context.session_variables) if context.session_variables else {}
            return results, context.logs, report_code, statistics, session_variables

    @staticmethod
    def _collect_all_results(results: List[StepExecutionResult]) -> List[StepExecutionResult]:
        all_res = []
        for r in results:
            all_res.append(r)
            all_res.extend(AutoTestStepExecutionEngine._collect_all_results(r.children))
        return all_res

    @staticmethod
    def _aggregate_root_step_logs(
            context: StepExecutionContext,
            root_result: StepExecutionResult,
            root_step_code: str
    ) -> None:
        """
        汇总根步骤的所有子步骤日志`

        Args:
            context: 执行上下文
            root_result: 根步骤的执行结果
            root_step_no: 根步骤编号
        """

        def collect_child_step_nos(result: StepExecutionResult) -> List[str]:
            """递归收集所有子步骤的编号"""
            step_codes = []
            if result.step_code is not None:
                step_codes.append(result.step_code)
            for child in result.children:
                step_codes.extend(collect_child_step_nos(child))
            return step_codes

        # 收集所有子步骤的编号（递归收集, 包括子步骤的子步骤）
        child_step_codes = []
        for child in root_result.children:
            child_step_codes.extend(collect_child_step_nos(child))

        # 汇总所有子步骤的日志（按步骤编号排序）
        aggregated_logs = []
        for step_code in sorted(child_step_codes):
            if step_code in context.logs:
                aggregated_logs.extend(context.logs[step_code])

        # 将根步骤的日志替换为：根步骤自己的日志 + 所有子步骤的汇总日志
        if root_step_code in context.logs:
            root_logs = context.logs[root_step_code]
            # 根步骤日志 + 子步骤汇总日志
            context.logs[root_step_code] = root_logs + aggregated_logs
        else:
            # 如果根步骤没有自己的日志, 直接使用子步骤的汇总日志
            context.logs[root_step_code] = aggregated_logs
