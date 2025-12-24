"""自动化测试-步骤执行引擎

面向对象实现，负责根据步骤树结构执行测试步骤。
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import datetime
import requests
import random

from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Tuple, Union

import httpx

from backend.applications.aotutest.models.autotest_model import StepType
from backend.applications.aotutest.services.autotest_report_crud import AUTOTEST_API_REPORT_CRUD
from backend.applications.aotutest.services.autotest_detail_crud import AUTOTEST_API_DETAIL_CRUD
from backend.applications.aotutest.schemas.autotest_report_schema import AutoTestApiReportCreate, AutoTestApiReportUpdate
from backend.applications.aotutest.schemas.autotest_detail_schema import AutoTestApiDetailCreate, AutoTestApiDetailUpdate
from backend.services.ctx import CTX_USER_ID


class StepExecutionError(Exception):
    """执行过程中出现的业务异常。"""


@dataclass
class StepExecutionResult:
    """记录单个步骤的执行结果。"""

    step_id: Optional[int]
    step_no: Optional[int]
    step_code: Optional[str]
    step_name: str
    step_type: StepType
    success: bool
    message: str = ""
    error: Optional[str] = None
    elapsed: Optional[float] = None
    response: Optional[Any] = None
    extract_variables: Dict[str, Any] = field(default_factory=dict)
    assert_validators: List[Dict[str, Any]] = field(default_factory=list)
    children: List["StepExecutionResult"] = field(default_factory=list)

    def append_child(self, child: "StepExecutionResult") -> None:
        self.children.append(child)


class HttpClientProtocol(Protocol):
    """HTTP 客户端协议，便于依赖注入和单元测试。"""

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        ...


class StepExecutionContext:
    """执行上下文，负责维护变量、日志以及外部依赖。"""

    def __init__(
            self,
            case_id: int,
            case_code: str,
            *,
            initial_variables: Optional[Dict[str, Any]] = None,
            http_client: Optional[HttpClientProtocol] = None,
            report_code: Optional[str] = None,
    ) -> None:
        self.case_id = case_id
        self.case_code = case_code
        self.report_code = report_code
        self.defined_variables: Dict[str, Any] = dict(initial_variables or {})
        self.session_variables: Dict[str, Any] = {}
        self.extract_variables: Dict[str, Any] = {}
        self.logs: Dict[int, List[str]] = {}
        # 记录循环次数：key 为 step_code，值为当前执行次数（从1开始）
        self.step_cycle_index: Dict[str, int] = {}
        self._current_step_no: Optional[int] = None
        self._http_client = http_client
        self._exit_stack = AsyncExitStack()

    async def __aenter__(self) -> "StepExecutionContext":
        """异步上下文管理器入口方法，初始化HTTP客户端（如未提供）

        若未指定外部HTTP客户端，将创建一个默认的httpx.AsyncClient实例，
        并通过AsyncExitStack管理其生命周期，确保在上下文退出时自动关闭客户端连接。
        默认超时配置：请求超时10秒，连接超时5秒。

        Returns:
            StepExecutionContext: 上下文管理器实例本身，用于异步with语句
        """
        if self._http_client is None:
            # 创建默认HTTP客户端，设置超时参数（请求超时10秒，连接超时5秒）
            client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0))
            # 将客户端纳入异步退出栈管理，确保上下文退出时自动关闭
            self._http_client = await self._exit_stack.enter_async_context(client)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._exit_stack.aclose()

    @property
    def http_client(self) -> HttpClientProtocol:
        if self._http_client is None:
            raise RuntimeError("HTTP client 未初始化，请在异步上下文中使用")
        return self._http_client

    def log(self, message: str, step_no: Optional[int] = None) -> None:
        step_no = self._current_step_no or 1

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.logs.setdefault(step_no, []).append(f"[{timestamp}] {message}")

    def set_current_step_no(self, step_no: Optional[int] = None) -> None:
        self._current_step_no = step_no

    def clone_state(self) -> Dict[str, Any]:
        return {
            "defined_variables": dict(self.defined_variables),
            "session_variables": dict(self.session_variables),
            "extract_variables": dict(self.extract_variables),
        }

    def update_variables(self, data: Dict[str, Any], *, scope: str = "defined_variables") -> None:
        target_map = {
            "defined_variables": self.defined_variables,
            "session_variables": self.session_variables,
            "extract_variables": self.extract_variables,
        }
        scope_map = target_map.get(scope)
        if scope_map is None:
            raise ValueError(f"未知变量作用域: {scope}")
        scope_map.update(data)
        self.log(f"更新变量[{scope}]: {data}")

    def get_variable(self, name: str) -> Any:
        """获取变量值，按优先级查找：extract_variables > session_variables > defined_variables"""
        for scope in (self.extract_variables, self.session_variables, self.defined_variables):
            if name in scope:
                return scope[name]
        raise KeyError(f"变量 {name} 未定义")

    def resolve_placeholders(self, value: Any) -> Any:
        """支持嵌套结构中的 ${var} 占位符替换。"""
        try:
            if isinstance(value, str):
                pattern = re.compile(r"\$\{([^}]+)}")

                def replace(match: re.Match[str]) -> str:
                    var_name = match.group(1)
                    try:
                        resolved = self.get_variable(var_name)
                    except KeyError:
                        self.log(f"变量 {var_name} 未定义，保留原值")
                        return match.group(0)
                    except Exception as exc:
                        self.log(f"获取变量 {var_name} 失败: {exc}，保留原值")
                        return match.group(0)
                    try:
                        return str(resolved)
                    except Exception as exc:
                        self.log(f"变量 {var_name} 转换为字符串失败: {exc}，保留原值")
                        return match.group(0)

                return pattern.sub(replace, value)

            if isinstance(value, dict):
                return {k: self.resolve_placeholders(v) for k, v in value.items()}

            if isinstance(value, list):
                return [self.resolve_placeholders(item) for item in value]

            return value
        except Exception as exc:
            self.log(f"占位符解析异常: {exc}，返回原值")
            return value

    async def sleep(self, seconds: Optional[float]) -> None:
        if seconds is None:
            return
        if seconds < 0:
            raise StepExecutionError("等待时间不能为负数")
        self.log(f"等待 {seconds} 秒")
        await asyncio.sleep(seconds)

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
            self.log(f"HTTP请求: {method} {url} kwargs={filtered_kwargs}")
            try:
                response = await client.request(method, url, **kwargs)
                self.log(f"HTTP响应: 状态码 {response.status_code}")
                return response
            except httpx.TimeoutException as exc:
                self.log(f"HTTP请求超时: {exc}")
                raise StepExecutionError(f"HTTP请求超时: {exc}") from exc
            except httpx.RequestError as exc:
                self.log(f"HTTP请求错误: {exc}")
                raise StepExecutionError(f"HTTP请求错误: {exc}") from exc
            except Exception as exc:
                self.log(f"HTTP请求异常: {exc}")
                raise StepExecutionError(f"HTTP请求异常: {exc}") from exc
        except StepExecutionError:
            raise
        except Exception as exc:
            raise StepExecutionError(f"HTTP请求处理异常: {exc}") from exc

    def run_python_code(self, code: str, *, namespace: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行 Python 代码块，返回新增变量。"""
        if not code:
            return {}

        prepared = self._normalize_python_code(code)
        # 提供安全的全局环境，包含必要的内置函数和导入功能
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
        except Exception as exc:
            raise StepExecutionError(f"执行代码失败: {exc}") from exc

        functions = {
            name: obj for name, obj in local_context.items() if callable(obj)
        }
        if functions:
            if len(functions) == 1:
                func = next(iter(functions.values()))
                result = func()
            else:
                raise StepExecutionError("仅支持定义一个函数作为入口")
        elif "result" in local_context:
            result = local_context["result"]
        else:
            result = None

        if result is None:
            return {}
        if not isinstance(result, dict):
            raise StepExecutionError("执行代码返回值必须是 dict 类型")
        self.log(f"[执行代码(Python)] 返回结果: {result}")
        return result

    @staticmethod
    def _normalize_python_code(code: str) -> str:
        code = code.strip()
        if not code:
            return code

        # 如果代码包含换行符，说明已经格式化好了
        if "\n" in code:
            return code

        # 处理单行函数定义的情况，例如: "def generate_var():import random return {...}"
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
                # 处理 return 等语句，确保有正确的缩进
                for keyword in ("return ", "if ", "for ", "while ", "with "):
                    if remaining_body.startswith(keyword):
                        normalized_parts.append(f"    {remaining_body}")
                        break
                else:
                    # 如果没有匹配的关键字，直接添加并缩进
                    normalized_parts.append(f"    {remaining_body}")

            return "\n".join(normalized_parts)

        return code

    @property
    def current_step_no(self):
        return self._current_step_no


class BaseStepExecutor:
    """步骤执行器基类。"""

    def __init__(self, step: Dict[str, Any], context: StepExecutionContext):
        self.step = step
        self.context = context

    @property
    def step_id(self) -> Optional[int]:
        return self.step.get("id")

    @property
    def step_no(self) -> Optional[int]:
        return self.step.get("step_no")

    @property
    def step_code(self) -> Optional[str]:
        return self.step.get("step_code") or self.step.get("id")

    @property
    def step_name(self) -> str:
        return self.step.get("step_name") or ""

    @property
    def step_type(self) -> StepType:
        return StepType(self.step.get("step_type"))

    @property
    def children(self) -> List[Dict[str, Any]]:
        return sorted(
            (self.step.get("children") or []) + (self.step.get("quote_steps") or []),
            key=lambda item: item.get("step_no", 0),
        )

    async def execute(self) -> StepExecutionResult:
        start = time.perf_counter()
        step_start_time = datetime.now()
        step_st_time_str = step_start_time.strftime("%Y-%m-%d %H:%M:%S")
        # 默认循环次数为1；若循环控制器提前写入，则取已记录值
        num_cycles = self.context.step_cycle_index.get(self.step_code or "", 1)
        # 确保记录下来，便于子层读取
        if self.step_code:
            self.context.step_cycle_index.setdefault(self.step_code, num_cycles)
        result = StepExecutionResult(
            step_id=self.step_id,
            step_no=self.step_no,
            step_code=self.step_code,
            step_name=self.step_name,
            step_type=self.step_type,
            success=True,
        )
        # 设置当前步骤编号
        previous_step_no: int = self.context.current_step_no
        self.context.set_current_step_no(self.step_no)
        try:
            await self._before_execute()
            await self._execute(result)
            await self._after_execute(result)
        except Exception as exc:
            result.success = False
            result.error = str(exc)
            self.context.log(f"步骤执行失败: {exc}", step_no=previous_step_no)
        finally:
            # 无论成功还是失败，都将当前步骤提取的变量追加到会话变量，便于后续步骤复用
            try:
                if result.extract_variables:
                    self.context.update_variables(result.extract_variables, scope="session_variables")
                    self.context.log(f"合并变量到session_variables: {result.extract_variables}", step_no=self.step_no)
            except Exception as exc:
                # 变量合并失败不应该影响步骤执行结果
                self.context.log(f"合并变量到session_variables失败: {exc}", step_no=self.step_no)

            self.context.set_current_step_no(step_no=previous_step_no)
            end = time.perf_counter()
            result.elapsed = round(end - start, 6)
            if self.context.report_code:
                try:
                    await self._save_step_detail(result, step_st_time_str, num_cycles)
                except Exception as exc:
                    # 保存步骤明细失败不应该影响执行流程
                    self.context.log(f"保存步骤明细失败: {exc}", step_no=self.step_no)
        return result

    async def _save_step_detail(self, result: StepExecutionResult, step_st_time_str: str, num_cycles: int) -> None:
        """保存步骤明细到数据库（含无响应步骤占位；循环多次执行合并）"""
        try:
            step_end_time = datetime.now()
            step_start_dt = datetime.strptime(step_st_time_str, "%Y-%m-%d %H:%M:%S")
            step_ed_time_str = step_end_time.strftime("%Y-%m-%d %H:%M:%S")
            step_elapsed = f"{result.elapsed:.3f}" if result.elapsed is not None else "0.000"

            step_logs = self.context.logs.get(self.step_no, [])
            step_exec_logger = "\n".join(step_logs) if step_logs else None

            response_header = None
            response_body = None
            response_text = None
            response_cookie = None
            response_elapsed = None

            if result.response:
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

            step_code = self.step_code or f"step-{self.step_id or self.step_no or 'tmp'}"

            # 1. defined_variables: 从步骤配置中获取用户定义的变量
            # 这是用户在步骤配置中预先定义的变量（如固定值、随机函数等）
            defined_variables = self.step.get("defined_variables") or {}

            # 2. extract_variables: 从响应中提取的变量
            # 只包含通过 extract_variables 配置从响应中提取的变量
            extract_variables = {}
            extract_variables_config = self.step.get("extract_variables")
            if extract_variables_config and isinstance(extract_variables_config, dict) and result.extract_variables:
                ext_var_name = extract_variables_config.get("name")
                if ext_var_name and ext_var_name in result.extract_variables:
                    extract_variables[ext_var_name] = result.extract_variables[ext_var_name]

            # 3. session_variables: 累积的会话变量（包含所有步骤产生的变量）
            # 使用深拷贝确保保存的是当前时刻的快照，不会被后续步骤影响
            # session_variables 包含：
            # - 从响应中提取的变量（extract_variables）
            # - 前后置代码产生的变量
            # - 其他步骤产生的变量
            session_variables = dict(self.context.session_variables) if self.context.session_variables else {}

            detail_create = AutoTestApiDetailCreate(
                case_id=self.context.case_id,
                case_code=self.context.case_code,
                report_code=self.context.report_code,
                step_id=self.step_id or 0,
                step_no=self.step_no or 0,
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
                response_cookie=response_cookie,
                response_header=response_header or {},
                response_body=response_body or {},
                response_text=response_text,
                response_elapsed=response_elapsed,
                session_variables=session_variables,
                defined_variables=defined_variables,
                extract_variables=extract_variables,
                assert_validators=result.assert_validators or []
            )
            await AUTOTEST_API_DETAIL_CRUD.create_step_detail(detail_create)
        except Exception as e:
            print(f"保存步骤明细失败: {e}")

    async def _before_execute(self) -> None:
        try:
            defined_variables = self.step.get("defined_variables") or {}
            if defined_variables:
                try:
                    prepared = self.context.resolve_placeholders(defined_variables)
                    self.context.update_variables(prepared, scope="defined_variables")
                except Exception as exc:
                    self.context.log(f"前置变量处理失败: {exc}，继续执行", step_no=self.step_no)

            pre_code = self.step.get("pre_code")
            if pre_code:
                try:
                    new_vars = self.context.run_python_code(
                        pre_code,
                        namespace=self.context.clone_state(),
                    )
                    if new_vars:
                        self.context.update_variables(new_vars, scope="extract_variables")
                except Exception as exc:
                    self.context.log(f"前置代码执行失败: {exc}，继续执行", step_no=self.step_no)

            pre_wait = self.step.get("pre_wait")
            if pre_wait is not None:
                try:
                    await self.context.sleep(float(pre_wait))
                except Exception as exc:
                    self.context.log(f"前置等待失败: {exc}，继续执行", step_no=self.step_no)
        except Exception as exc:
            self.context.log(f"前置处理异常: {exc}，继续执行", step_no=self.step_no)

    async def _after_execute(self, result: StepExecutionResult) -> None:
        try:
            post_code = self.step.get("post_code")
            if post_code:
                try:
                    new_vars = self.context.run_python_code(
                        post_code,
                        namespace=self.context.clone_state(),
                    )
                    if new_vars:
                        self.context.update_variables(new_vars, scope="extract_variables")
                        result.extract_variables.update(new_vars)
                except Exception as exc:
                    self.context.log(f"后置代码执行失败: {exc}，继续执行", step_no=self.step_no)

            post_wait = self.step.get("post_wait")
            if post_wait is not None:
                try:
                    await self.context.sleep(float(post_wait))
                except Exception as exc:
                    self.context.log(f"后置等待失败: {exc}，继续执行", step_no=self.step_no)
        except Exception as exc:
            self.context.log(f"后置处理异常: {exc}，继续执行", step_no=self.step_no)

    async def _execute(self, result: StepExecutionResult) -> None:
        raise NotImplementedError

    async def _execute_children(self) -> List[StepExecutionResult]:
        results: List[StepExecutionResult] = []
        for child in self.children:
            try:
                executor = StepExecutorFactory.create_executor(child, self.context)
                child_result = await executor.execute()
                results.append(child_result)
            except Exception as exc:
                # 子步骤执行失败，创建失败结果记录
                error_msg = f"子步骤执行失败: {exc}"
                self.context.log(error_msg, step_no=child.get("step_no"))
                failed_result = StepExecutionResult(
                    step_id=child.get("id"),
                    step_no=child.get("step_no"),
                    step_code=child.get("step_code") or child.get("id"),
                    step_name=child.get("step_name", ""),
                    step_type=StepType(child.get("step_type", "")),
                    success=False,
                    error=error_msg,
                )
                results.append(failed_result)
        return results


class LoopStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        try:
            iteration = 0
            max_cycles = self.step.get("max_cycles")
            condition = self.step.get("conditions")
            should_continue = True
            guard_limit = 1000

            async def run_children_once() -> List[StepExecutionResult]:
                try:
                    child_results = await self._execute_children()
                    for child in child_results:
                        result.append_child(child)
                        if not child.success:
                            result.success = False
                    return child_results
                except Exception as exc:
                    result.success = False
                    error_msg = f"执行子步骤失败: {exc}"
                    result.error = error_msg
                    self.context.log(error_msg, step_no=self.step_no)
                    return []

            self.context.log(f"[循环控制器] ---> 开始", step_no=self.step_no)
            while should_continue:
                iteration += 1
                # 记录循环次数（作用于当前循环和子步骤）
                if self.step_code:
                    self.context.step_cycle_index[self.step_code] = iteration

                self.context.log(f"[循环控制器] [次数循环] 第 {iteration} 次执行", step_no=self.step_no)
                # 为子步骤记录当前循环次数（每次循环前重置子树的计数起点）
                for child in self.children:
                    child_code = child.get("step_code") or child.get("id") or ""
                    if child_code:
                        self.context.step_cycle_index[child_code] = iteration

                try:
                    await run_children_once()
                except Exception as exc:
                    result.success = False
                    error_msg = f"循环第 {iteration} 次执行失败: {exc}"
                    result.error = error_msg
                    self.context.log(error_msg, step_no=self.step_no)
                    # 可以选择继续或中断循环
                    break

                if max_cycles and iteration >= max_cycles:
                    self.context.log(f"[循环控制器] ---> 结束", step_no=self.step_no)
                    break

                if condition:
                    try:
                        if not self._evaluate_condition(condition):
                            should_continue = False
                    except Exception as exc:
                        result.success = False
                        error_msg = f"循环条件评估失败: {exc}"
                        result.error = error_msg
                        self.context.log(error_msg, step_no=self.step_no)
                        break

                if iteration >= guard_limit:
                    raise StepExecutionError("循环次数超过安全阈值, 疑似无限循环, 循环终止...")

                if not max_cycles and not condition:
                    should_continue = False
                    self.context.log(f"[循环控制器] ---> 结束", step_no=self.step_no)
        except StepExecutionError:
            raise
        except Exception as exc:
            result.success = False
            result.error = f"循环控制器执行异常: {exc}"
            self.context.log(result.error, step_no=self.step_no)

    def _evaluate_condition(self, condition: str) -> bool:
        try:
            # 处理 JSON 字符串中可能包含的 Python None/True/False
            # 使用正则表达式更精确地替换，避免误替换字符串中的值
            # 替换独立的 None/True/False（前后不是字母数字或下划线）
            normalized_condition = re.sub(r'\bNone\b', 'null', condition)
            normalized_condition = re.sub(r'\bTrue\b', 'true', normalized_condition)
            normalized_condition = re.sub(r'\bFalse\b', 'false', normalized_condition)
            condition_obj = json.loads(normalized_condition)
        except json.JSONDecodeError as exc:
            raise StepExecutionError(f"循环条件解析失败: {exc}") from exc
        except Exception as exc:
            raise StepExecutionError(f"循环条件处理异常: {exc}") from exc

        value_expr = condition_obj.get("value")
        operation = condition_obj.get("operation")
        except_value = condition_obj.get("except_value")

        if value_expr is None or operation is None:
            raise StepExecutionError("循环条件配置不完整")

        try:
            resolved = self.context.resolve_placeholders(value_expr)
            if isinstance(resolved, str) and resolved.startswith("${") and resolved.endswith("}"):
                variable_name = resolved[2:-1]
                try:
                    value = self.context.get_variable(variable_name)
                except KeyError as exc:
                    raise StepExecutionError(f"循环条件中变量未定义: {variable_name}") from exc
            else:
                value = resolved
        except Exception as exc:
            if isinstance(exc, StepExecutionError):
                raise
            raise StepExecutionError(f"循环条件变量解析失败: {exc}") from exc

        try:
            return ConditionStepExecutor.compare(value, operation, except_value)
        except Exception as exc:
            raise StepExecutionError(f"循环条件比较失败: {exc}") from exc


class ConditionStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        try:
            condition = self.step.get("conditions")
            if not condition:
                raise StepExecutionError("条件分支缺少条件配置")

            # 处理 JSON 字符串中可能包含的 Python None/True/False
            # 使用正则表达式更精确地替换，避免误替换字符串中的值
            # 替换独立的 None/True/False（前后不是字母数字或下划线）
            normalized_condition = re.sub(r'\bNone\b', 'null', condition)
            normalized_condition = re.sub(r'\bTrue\b', 'true', normalized_condition)
            normalized_condition = re.sub(r'\bFalse\b', 'false', normalized_condition)
            condition_obj = json.loads(normalized_condition)

            value_expr = condition_obj.get("value")
            operation = condition_obj.get("operation")
            except_value = condition_obj.get("except_value")
            desc = condition_obj.get("desc", "")

            if value_expr is None or operation is None:
                raise StepExecutionError("条件配置不完整，缺少 value 或 operation")

            try:
                resolved_value_expr = self.context.resolve_placeholders(value_expr)
            except Exception as exc:
                raise StepExecutionError(f"条件变量解析失败: {exc}") from exc

            try:
                if isinstance(resolved_value_expr, str) and resolved_value_expr.startswith(
                        "${") and resolved_value_expr.endswith("}"):
                    variable_name = resolved_value_expr[2:-1]
                    try:
                        value = self.context.get_variable(variable_name)
                    except KeyError as exc:
                        raise StepExecutionError(f"条件中变量未定义: {variable_name}") from exc
                else:
                    value = resolved_value_expr
            except StepExecutionError:
                raise
            except Exception as exc:
                raise StepExecutionError(f"条件值获取失败: {exc}") from exc

            try:
                if not self.compare(value, operation, except_value):
                    result.success = True
                    result.message = f"条件未满足: {desc}"
                    self.context.log(result.message, step_no=self.step_no)
                    return
            except Exception as exc:
                raise StepExecutionError(f"条件比较失败: {exc}") from exc

            result.message = f"条件满足: {desc}"
            self.context.log(result.message, step_no=self.step_no)
            try:
                child_results = await self._execute_children()
                for child in child_results:
                    result.append_child(child)
                    if not child.success:
                        result.success = False
            except Exception as exc:
                result.success = False
                error_msg = f"执行条件分支子步骤失败: {exc}"
                result.error = error_msg
                self.context.log(error_msg, step_no=self.step_no)
        except Exception as exc:
            # 捕获条件判断的异常，避免阻断后续执行
            result.success = False
            result.error = str(exc)
            result.message = f"条件执行异常: {exc}"
            self.context.log(result.message, step_no=self.step_no)

    @staticmethod
    def compare(value: Any, operation: str, except_value: Any) -> bool:
        op_map: Dict[str, Callable[[Any, Any], bool]] = {
            "等于": lambda a, b: a == b,
            "不等于": lambda a, b: a != b,
            "大于": lambda a, b: a > b,
            "大于等于": lambda a, b: a >= b,
            "小于": lambda a, b: a < b,
            "小于等于": lambda a, b: a <= b,
            "非空": lambda a, _: a is not None and a != "",
            "为空": lambda a, _: a is None or a == "",
        }
        comparator = op_map.get(operation)
        if comparator is None:
            raise StepExecutionError(f"不支持的条件操作符: {operation}")
        return comparator(value, except_value)


class PythonStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        try:
            code = self.step.get("code")
            if not code:
                raise StepExecutionError("执行代码步骤缺少 code 配置")

            try:
                new_vars = self.context.run_python_code(
                    code,
                    namespace=self.context.clone_state(),
                )
            except StepExecutionError:
                raise
            except Exception as exc:
                raise StepExecutionError(f"Python代码执行失败: {exc}") from exc

            if new_vars:
                try:
                    self.context.update_variables(new_vars, scope="extract_variables")
                    result.extract_variables.update(new_vars)
                except Exception as exc:
                    raise StepExecutionError(f"更新变量失败: {exc}") from exc
        except StepExecutionError:
            raise
        except Exception as exc:
            result.success = False
            result.error = f"Python步骤执行异常: {exc}"
            self.context.log(result.error, step_no=self.step_no)
            raise StepExecutionError(result.error) from exc


class WaitStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        try:
            wait_seconds = self.step.get("wait")
            if wait_seconds is None:
                raise StepExecutionError("等待控制步骤缺少 wait 配置")

            try:
                wait_float = float(wait_seconds)
            except (ValueError, TypeError) as exc:
                raise StepExecutionError(f"等待时间格式错误: {wait_seconds}") from exc

            try:
                await self.context.sleep(wait_float)
            except StepExecutionError:
                raise
            except Exception as exc:
                raise StepExecutionError(f"等待操作失败: {exc}") from exc
        except StepExecutionError:
            raise
        except Exception as exc:
            result.success = False
            result.error = f"等待步骤执行异常: {exc}"
            self.context.log(result.error, step_no=self.step_no)
            raise StepExecutionError(result.error) from exc


class TcpStepExecutor(BaseStepExecutor):
    pass

class DataBaseStepExecutor(BaseStepExecutor):
    pass

class HttpStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        try:
            request_url = self.step.get("request_url")
            request_method = (self.step.get("request_method") or "GET").upper()
            request_port = self.step.get("request_port")

            if not request_url:
                raise StepExecutionError("网络请求步骤缺少 request_url")

            if request_port:
                raise StepExecutionError("暂未实现 TCP 请求执行逻辑")

            try:
                headers = self.context.resolve_placeholders(self.step.get("request_header") or {})
                params = self.context.resolve_placeholders(self.step.get("request_params") or {})
                form_data = self.context.resolve_placeholders(self.step.get("request_form_data") or {})
                urlencoded = self.context.resolve_placeholders(self.step.get("request_form_urlencoded") or {})
                request_body = self.context.resolve_placeholders(self.step.get("request_body"))
                request_text = self.step.get("request_text")
            except Exception as exc:
                raise StepExecutionError(f"请求参数解析失败: {exc}") from exc

            form_files = self.step.get("request_form_file")
            data_payload: Optional[Any] = None
            json_payload: Optional[Any] = None

            try:
                if request_text:
                    data_payload = self.context.resolve_placeholders(request_text)
                elif form_data:
                    data_payload = form_data
                elif urlencoded:
                    data_payload = urlencoded

                if request_body:
                    json_payload = request_body

                params_payload = params if isinstance(params, dict) else None
            except Exception as exc:
                raise StepExecutionError(f"请求体处理失败: {exc}") from exc

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
            except httpx.RequestError as exc:
                raise StepExecutionError(f"HTTP请求失败: {exc}") from exc
            except httpx.HTTPStatusError as exc:
                # HTTP状态错误不一定是失败，记录响应继续处理
                response = exc.response
                self.context.log(f"HTTP响应状态码异常: {exc.response.status_code}", step_no=self.step_no)
            except Exception as exc:
                raise StepExecutionError(f"HTTP请求异常: {exc}") from exc

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
                }
            except Exception as exc:
                raise StepExecutionError(f"响应处理失败: {exc}") from exc

            try:
                response_json = response.json()
            except (ValueError, json.JSONDecodeError):
                response_json = None
            except Exception as exc:
                self.context.log(f"响应JSON解析失败: {exc}，将使用文本响应", step_no=self.step_no)
                response_json = None

            try:
                extract_variables = self._extract_variables(response_json)
                if extract_variables:
                    # 提取变量同时放入会话变量，便于后续步骤引用
                    self.context.update_variables(extract_variables, scope="session_variables")
                    self.context.update_variables(extract_variables, scope="extract_variables")
                    result.extract_variables.update(extract_variables)
            except Exception as exc:
                error_msg = f"变量提取失败: {exc}"
                self.context.log(error_msg, step_no=self.step_no)
                # 变量提取失败不影响请求成功，只记录错误

            try:
                validator_results = self._run_validators(response_json)
                result.assert_validators.extend(validator_results)
                if any(not item.get("success", True) for item in validator_results):
                    raise StepExecutionError("断言失败")
            except StepExecutionError:
                raise
            except Exception as exc:
                error_msg = f"断言执行失败: {exc}"
                self.context.log(error_msg, step_no=self.step_no)
                raise StepExecutionError(error_msg) from exc
        except StepExecutionError:
            raise
        except Exception as exc:
            result.success = False
            result.error = f"HTTP步骤执行异常: {exc}"
            self.context.log(result.error, step_no=self.step_no)
            raise StepExecutionError(result.error) from exc

    def _extract_variables(self, response_json: Any) -> Dict[str, Any]:
        try:
            extract_variables = self.step.get("extract_variables")
            if not extract_variables or response_json is None:
                return {}

            name = extract_variables.get("name")
            expr = extract_variables.get("expr")

            if not name or not expr:
                raise StepExecutionError("变量提取配置不完整")

            try:
                extracted = self._resolve_json_path(response_json, expr)
            except StepExecutionError:
                raise
            except Exception as exc:
                raise StepExecutionError(f"JSONPath解析失败: {exc}") from exc

            return {name: extracted}
        except StepExecutionError:
            raise
        except Exception as exc:
            raise StepExecutionError(f"变量提取异常: {exc}") from exc

    def _run_validators(self, response_json: Any) -> List[Dict[str, Any]]:
        try:
            # 兼容validators和assert_validators字段名
            assert_validators = self.step.get("assert_validators") or self.step.get("assert_validators")
            if not assert_validators or response_json is None:
                return []

            expr = assert_validators.get("expr")
            operation = assert_validators.get("operation")
            expected = assert_validators.get("except_value")
            name = assert_validators.get("name")

            if not expr or not operation:
                raise StepExecutionError("断言配置不完整")

            try:
                actual = self._resolve_json_path(response_json, expr)
            except StepExecutionError:
                raise
            except Exception as exc:
                raise StepExecutionError(f"断言JSONPath解析失败: {exc}") from exc

            try:
                success = ConditionStepExecutor.compare(actual, operation, expected)
            except StepExecutionError:
                raise
            except Exception as exc:
                raise StepExecutionError(f"断言比较失败: {exc}") from exc

            message = f"断言[{name}] {expr} {operation} {expected}, 实际值={actual}"
            self.context.log(message, step_no=self.step_no)

            return [{
                "name": name,
                "expr": expr,
                "operation": operation,
                "expected": expected,
                "actual": actual,
                "success": success,
                "message": message,
            }]
        except StepExecutionError:
            raise
        except Exception as exc:
            raise StepExecutionError(f"断言执行异常: {exc}") from exc

    @staticmethod
    def _resolve_json_path(data: Any, expr: str) -> Any:
        try:
            if not expr or not isinstance(expr, str):
                raise StepExecutionError("JSONPath表达式必须是非空字符串")

            if not expr.startswith("$."):
                raise StepExecutionError("仅支持 $. 开头的 JSONPath 表达式")

            if data is None:
                raise StepExecutionError("数据为空，无法解析JSONPath")

            parts = [part for part in expr[2:].split(".") if part]
            if not parts:
                raise StepExecutionError("JSONPath表达式路径为空")

            current: Any = data
            for i, part in enumerate(parts):
                if isinstance(current, dict):
                    if part not in current:
                        raise StepExecutionError(f"JSONPath路径不存在: {'$.'.join(parts[:i+1])}")
                    current = current.get(part)
                elif isinstance(current, list):
                    try:
                        index = int(part)
                    except ValueError as exc:
                        raise StepExecutionError(f"列表索引必须为整数: {part}") from exc
                    try:
                        current = current[index]
                    except IndexError as exc:
                        raise StepExecutionError(f"列表索引越界: {part}，列表长度: {len(current)}") from exc
                else:
                    raise StepExecutionError(f"无法在 {type(current).__name__} 类型上应用 JSONPath: {part}，路径: {'$.'.join(parts[:i+1])}")

            return current
        except StepExecutionError:
            raise
        except Exception as exc:
            raise StepExecutionError(f"JSONPath解析异常: {exc}") from exc


class DefaultStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        try:
            # 默认只执行子步骤
            child_results = await self._execute_children()
            for child in child_results:
                result.append_child(child)
                if not child.success:
                    result.success = False
        except Exception as exc:
            result.success = False
            result.error = f"默认步骤执行异常: {exc}"
            self.context.log(result.error, step_no=self.step_no)
            raise StepExecutionError(result.error) from exc


class StepExecutorFactory:
    """根据 StepType 创建对应执行器。"""

    EXECUTOR_MAP: Dict[StepType, Callable[[Dict[str, Any], StepExecutionContext], BaseStepExecutor]] = {
        StepType.TCP: TcpStepExecutor,
        StepType.HTTP: HttpStepExecutor,
        StepType.PYTHON: PythonStepExecutor,
        StepType.DATABASE: DataBaseStepExecutor,
        StepType.LOOP: LoopStepExecutor,
        StepType.IF: ConditionStepExecutor,
        StepType.WAIT: WaitStepExecutor,
    }

    @classmethod
    def create_executor(cls, step: Dict[str, Any], context: StepExecutionContext) -> BaseStepExecutor:
        try:
            step_type_str = step.get("step_type")
            if not step_type_str:
                raise StepExecutionError("步骤类型未定义")

            try:
                step_type = StepType(step_type_str)
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
    """测试步骤执行引擎入口。"""

    def __init__(self, *, http_client: Optional[HttpClientProtocol] = None, save_report: bool = True) -> None:
        self._http_client = http_client
        self._save_report = save_report
        self._report_code: Optional[str] = None

    async def execute_case(
            self,
            case: Dict[str, Any],
            steps: Iterable[Dict[str, Any]],
            *,
            initial_variables: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[StepExecutionResult], Dict[int, List[str]], Optional[str], Dict[str, Any]]:
        """
        执行测试用例并返回：(结果列表, 日志, 报告码, 统计信息)
        """
        case_id = case.get("id")
        case_code = case.get("case_code")
        case_name = case.get("case_name", "")

        case_start_time = datetime.now()
        case_st_time_str = case_start_time.strftime("%Y-%m-%d %H:%M:%S")

        report_code = None
        if self._save_report:
            try:
                user_id = CTX_USER_ID.get(0)
                user_name = str(user_id) if user_id else None
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
                    created_user=user_name
                )
                report_instance = await AUTOTEST_API_REPORT_CRUD.create_report(report_create)
                report_code = report_instance.report_code
                self._report_code = report_code
            except Exception as e:
                print(f"创建报告失败: {e}")

        async with StepExecutionContext(
                case_id=case_id,
                case_code=case_code,
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

                # 对于根步骤（parent_step_id 为 None），汇总所有子步骤的日志
                if step.get("parent_step_id") is None:
                    root_step_no = step.get("step_no")
                    if root_step_no is not None:
                        self._aggregate_root_step_logs(context, result, root_step_no)

            # 统计（按 step_code 去重合并）
            all_results = self._collect_all_results(results)
            unique_states: Dict[str, bool] = {}
            for r in all_results:
                key = r.step_code or f"{r.step_id}-{r.step_no}"
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
                    await AUTOTEST_API_REPORT_CRUD.update_report(report_update)
                except Exception as e:
                    print(f"更新报告失败: {e}")

            statistics = {
                "total_steps": total_steps,
                "success_steps": success_steps,
                "failed_steps": failed_steps,
                "pass_ratio": round(pass_ratio, 2)
            }

            return results, context.logs, report_code, statistics

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
            root_step_no: int
    ) -> None:
        """
        汇总根步骤的所有子步骤日志

        Args:
            context: 执行上下文
            root_result: 根步骤的执行结果
            root_step_no: 根步骤编号
        """

        def collect_child_step_nos(result: StepExecutionResult) -> List[int]:
            """递归收集所有子步骤的编号"""
            step_nos = []
            if result.step_no is not None:
                step_nos.append(result.step_no)
            for child in result.children:
                step_nos.extend(collect_child_step_nos(child))
            return step_nos

        # 收集所有子步骤的编号（递归收集，包括子步骤的子步骤）
        child_step_nos = []
        for child in root_result.children:
            child_step_nos.extend(collect_child_step_nos(child))

        # 汇总所有子步骤的日志（按步骤编号排序）
        aggregated_logs = []
        for step_no in sorted(child_step_nos):
            if step_no in context.logs:
                aggregated_logs.extend(context.logs[step_no])

        # 将根步骤的日志替换为：根步骤自己的日志 + 所有子步骤的汇总日志
        if root_step_no in context.logs:
            root_logs = context.logs[root_step_no]
            # 根步骤日志 + 子步骤汇总日志
            context.logs[root_step_no] = root_logs + aggregated_logs
        else:
            # 如果根步骤没有自己的日志，直接使用子步骤的汇总日志
            context.logs[root_step_no] = aggregated_logs


class AutoTestStepExecution:
    def __init__(
            self, *,
            test_steps: Union[Dict[str, Any], List[Dict[str, Any]]],
            initial_variables: Dict[str, Any] = None,
    ) -> None:
        if not isinstance(test_steps, (dict, list)):
            raise TypeError("测试步骤类型错误")
        self.initial_variables = initial_variables if initial_variables else {}
        self.test_steps = test_steps if isinstance(test_steps, list) else test_steps["data"]

    async def get_case_info(self) -> Dict[str, Any]:
        # 提取用例信息（从第一个步骤中获取）
        case_info: dict = self.test_steps[0].get("case", {})
        if not case_info:
            raise ValueError("从第一个步骤中获取用例信息失败")
        return case_info

    async def get_parent_step(self) -> List[Dict[str, Any]]:
        # 提取根步骤（parent_step_id为None的步骤）
        root_steps = [step for step in self.test_steps if step.get("parent_step_id") is None]
        return root_steps

    async def execute(self):
        # 创建执行引擎
        engine = AutoTestStepExecutionEngine()
        # 执行测试
        try:
            case_info = await self.get_case_info()
            print(f"\n用例信息:\n", json.dumps(case_info, ensure_ascii=False, indent=2))

            root_steps = await self.get_parent_step()
            print(f"\n根步骤数量: {len(root_steps)}")

            results, logs, _, _ = await engine.execute_case(
                case=case_info,
                steps=root_steps,
                initial_variables=self.initial_variables  # 可以在这里设置初始变量
            )

            # 打印执行日志
            print("\n执行日志:")
            for log_code, log_message in logs.items():
                print(f"{log_code}: \n" + '\n'.join(log_message))

            # 打印执行结果
            print("\n步骤执行结果:")
            for result in results:
                self._print_result(result)

            # 统计信息
            total_steps = sum(1 for _ in self._count_all_results(results))
            success_steps = sum(1 for r in self._count_all_results(results) if r.success)
            failed_steps = total_steps - success_steps

            execute_detail: Dict[str, int] = {
                "total_steps": total_steps,
                "success_steps": success_steps,
                "failed_steps": failed_steps,
                "rate": f"{success_steps / total_steps * 100:.2f}%" if total_steps > 0 else "N/A"

            }
            print(f"\n执行统计:\n", json.dumps(execute_detail, ensure_ascii=False))

        except Exception as e:
            print(f"\n执行异常: \n{type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    @classmethod
    def _print_result(cls, result: StepExecutionResult, indent: int = 0) -> None:
        """递归打印执行结果"""
        prefix = "  " * indent
        status = "✓" if result.success else "✗"
        print(f"{prefix}{status} [{result.step_no}] {result.step_name} ({result.step_type.value})")
        if result.message:
            print(f"{prefix}   消息: {result.message}")
        if result.error:
            print(f"{prefix}   错误: {result.error}")
        if result.elapsed:
            print(f"{prefix}   耗时: {result.elapsed:.3f}秒")
        if result.extract_variables:
            print(f"{prefix}   变量: {json.dumps(result.extract_variables, ensure_ascii=False)}")
        if result.assert_validators:
            print(f"{prefix}   断言: {json.dumps(result.assert_validators, ensure_ascii=False)}")
        if result.response:
            print(f"{prefix}   响应: {json.dumps(result.response, ensure_ascii=False)[:200]}...")

        for child in result.children:
            cls._print_result(child, indent + 2)

    @classmethod
    def _count_all_results(cls, results: List[StepExecutionResult]) -> List[StepExecutionResult]:
        """递归收集所有结果"""
        all_results = []
        for result in results:
            all_results.append(result)
            all_results.extend(cls._count_all_results(result.children))
        return all_results
