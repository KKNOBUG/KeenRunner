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


class StepExecutionError(Exception):
    """执行过程中出现的业务异常。"""


@dataclass
class StepExecutionResult:
    """记录单个步骤的执行结果。"""

    step_id: Optional[int]
    step_no: Optional[int]
    step_name: str
    step_type: StepType
    success: bool
    message: str = ""
    error: Optional[str] = None
    elapsed: Optional[float] = None
    response: Optional[Any] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    validators: List[Dict[str, Any]] = field(default_factory=list)
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
    ) -> None:
        self.case_id = case_id
        self.case_code = case_code
        self.variables: Dict[str, Any] = dict(initial_variables or {})
        self.session_variables: Dict[str, Any] = {}
        self.ext_variables: Dict[str, Any] = {}
        self.logs: Dict[int, List[str]] = {}
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
            "variables": dict(self.variables),
            "session_variables": dict(self.session_variables),
            "ext_variables": dict(self.ext_variables),
        }

    def update_variables(self, data: Dict[str, Any], *, scope: str = "variables") -> None:
        target_map = {
            "variables": self.variables,
            "session": self.session_variables,
            "ext": self.ext_variables,
        }
        scope_map = target_map.get(scope)
        if scope_map is None:
            raise ValueError(f"未知变量作用域: {scope}")
        scope_map.update(data)
        self.log(f"更新变量[{scope}]: {data}")

    def get_variable(self, name: str) -> Any:
        for scope in (self.ext_variables, self.session_variables, self.variables):
            if name in scope:
                return scope[name]
        raise KeyError(f"变量 {name} 未定义")

    def resolve_placeholders(self, value: Any) -> Any:
        """支持嵌套结构中的 ${var} 占位符替换。"""

        if isinstance(value, str):
            pattern = re.compile(r"\$\{([^}]+)}")

            def replace(match: re.Match[str]) -> str:
                var_name = match.group(1)
                try:
                    resolved = self.get_variable(var_name)
                except KeyError:
                    self.log(f"变量 {var_name} 未定义，保留原值")
                    return match.group(0)
                return str(resolved)

            return pattern.sub(replace, value)

        if isinstance(value, dict):
            return {k: self.resolve_placeholders(v) for k, v in value.items()}

        if isinstance(value, list):
            return [self.resolve_placeholders(item) for item in value]

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
        response = await client.request(method, url, **kwargs)
        self.log(f"HTTP响应: 状态码 {response.status_code}")
        return response

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
        result = StepExecutionResult(
            step_id=self.step_id,
            step_no=self.step_no,
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
            self.context.set_current_step_no(step_no=previous_step_no)
            end = time.perf_counter()
            result.elapsed = round(end - start, 6)
        return result

    async def _before_execute(self) -> None:
        use_variables = self.step.get("use_variables") or {}
        if use_variables:
            prepared = self.context.resolve_placeholders(use_variables)
            self.context.update_variables(prepared, scope="variables")

        pre_code = self.step.get("pre_code")
        if pre_code:
            new_vars = self.context.run_python_code(
                pre_code,
                namespace=self.context.clone_state(),
            )
            if new_vars:
                self.context.update_variables(new_vars, scope="variables")

        pre_wait = self.step.get("pre_wait")
        if pre_wait is not None:
            await self.context.sleep(float(pre_wait))

    async def _after_execute(self, result: StepExecutionResult) -> None:
        post_code = self.step.get("post_code")
        if post_code:
            new_vars = self.context.run_python_code(
                post_code,
                namespace=self.context.clone_state(),
            )
            if new_vars:
                self.context.update_variables(new_vars, scope="variables")
                result.variables.update(new_vars)

        post_wait = self.step.get("post_wait")
        if post_wait is not None:
            await self.context.sleep(float(post_wait))

        result.variables.update(self.context.ext_variables)

    async def _execute(self, result: StepExecutionResult) -> None:
        raise NotImplementedError

    async def _execute_children(self) -> List[StepExecutionResult]:
        results: List[StepExecutionResult] = []
        for child in self.children:
            executor = StepExecutorFactory.create_executor(child, self.context)
            child_result = await executor.execute()
            results.append(child_result)
        return results


class LoopStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        iteration = 0
        max_cycles = self.step.get("max_cycles")
        condition = self.step.get("conditions")
        should_continue = True
        guard_limit = 1000

        async def run_children_once() -> List[StepExecutionResult]:
            child_results = await self._execute_children()
            for child in child_results:
                result.append_child(child)
                if not child.success:
                    result.success = False
            return child_results

        self.context.log(f"[循环控制器] ---> 开始", step_no=self.step_no)
        while should_continue:
            iteration += 1

            self.context.log(f"[循环控制器] [次数循环] 第 {iteration} 次执行", step_no=self.step_no)
            await run_children_once()

            if max_cycles and iteration >= max_cycles:
                self.context.log(f"[循环控制器] ---> 结束", step_no=self.step_no)
                break

            if condition:
                if not self._evaluate_condition(condition):
                    should_continue = False

            if iteration >= guard_limit:
                raise StepExecutionError("循环次数超过安全阈值, 疑似无限循环, 循环终止...")

            if not max_cycles and not condition:
                should_continue = False
                self.context.log(f"[循环控制器] ---> 结束", step_no=self.step_no)

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

        value_expr = condition_obj.get("value")
        operation = condition_obj.get("operation")
        except_value = condition_obj.get("except_value")

        if value_expr is None or operation is None:
            raise StepExecutionError("循环条件配置不完整")

        resolved = self.context.resolve_placeholders(value_expr)
        value = self.context.get_variable(resolved.strip("${}")) if resolved.startswith("${") else resolved

        return ConditionStepExecutor.compare(value, operation, except_value)


class ConditionStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        condition = self.step.get("conditions")
        if not condition:
            raise StepExecutionError("条件分支缺少条件配置")

        try:
            # 处理 JSON 字符串中可能包含的 Python None/True/False
            # 使用正则表达式更精确地替换，避免误替换字符串中的值
            # 替换独立的 None/True/False（前后不是字母数字或下划线）
            normalized_condition = re.sub(r'\bNone\b', 'null', condition)
            normalized_condition = re.sub(r'\bTrue\b', 'true', normalized_condition)
            normalized_condition = re.sub(r'\bFalse\b', 'false', normalized_condition)
            condition_obj = json.loads(normalized_condition)
        except json.JSONDecodeError as exc:
            raise StepExecutionError(f"条件解析失败: {exc}") from exc

        value_expr = condition_obj.get("value")
        operation = condition_obj.get("operation")
        except_value = condition_obj.get("except_value")
        desc = condition_obj.get("desc", "")

        if value_expr is None or operation is None:
            raise StepExecutionError("条件配置不完整，缺少 value 或 operation")

        resolved_value_expr = self.context.resolve_placeholders(value_expr)

        if isinstance(resolved_value_expr, str) and resolved_value_expr.startswith(
                "${") and resolved_value_expr.endswith("}"):
            variable_name = resolved_value_expr[2:-1]
            value = self.context.get_variable(variable_name)
        else:
            value = resolved_value_expr

        if not self.compare(value, operation, except_value):
            result.success = True
            result.message = f"条件未满足: {desc}"
            self.context.log(result.message, step_no=self.step_no)
            return

        result.message = f"条件满足: {desc}"
        self.context.log(result.message, step_no=self.step_no)
        child_results = await self._execute_children()
        for child in child_results:
            result.append_child(child)
            if not child.success:
                result.success = False

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
        code = self.step.get("code")
        if not code:
            raise StepExecutionError("执行代码步骤缺少 code 配置")

        new_vars = self.context.run_python_code(
            code,
            namespace=self.context.clone_state(),
        )
        if new_vars:
            self.context.update_variables(new_vars, scope="ext")
            result.variables.update(new_vars)


class WaitStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        wait_seconds = self.step.get("wait")
        if wait_seconds is None:
            raise StepExecutionError("等待控制步骤缺少 wait 配置")
        await self.context.sleep(float(wait_seconds))


class HttpStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        request_url = self.step.get("request_url")
        request_method = (self.step.get("request_method") or "GET").upper()
        request_port = self.step.get("request_port")

        if not request_url:
            raise StepExecutionError("网络请求步骤缺少 request_url")

        if request_port:
            raise StepExecutionError("暂未实现 TCP 请求执行逻辑")

        headers = self.context.resolve_placeholders(self.step.get("request_header") or {})
        params = self.context.resolve_placeholders(self.step.get("request_params") or {})
        form_data = self.context.resolve_placeholders(self.step.get("request_form_data") or {})
        form_files = self.step.get("request_form_file")
        urlencoded = self.context.resolve_placeholders(self.step.get("request_form_urlencoded") or {})
        request_body = self.context.resolve_placeholders(self.step.get("request_body"))
        request_text = self.step.get("request_text")

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

        response = await self.context.send_http_request(
            request_method,
            request_url,
            headers=headers or None,
            params=params_payload,
            data=data_payload,
            json_data=json_payload,
            files=form_files,
        )

        result.response = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "text": response.text,
        }

        try:
            response_json = response.json()
        except ValueError:
            response_json = None

        variables = self._extract_variables(response_json)
        if variables:
            self.context.update_variables(variables, scope="ext")
            result.variables.update(variables)

        validator_results = self._run_validators(response_json)
        result.validators.extend(validator_results)
        if any(not item.get("success", True) for item in validator_results):
            raise StepExecutionError("断言失败")

    def _extract_variables(self, response_json: Any) -> Dict[str, Any]:
        ext_variables = self.step.get("ext_variables")
        if not ext_variables or response_json is None:
            return {}

        name = ext_variables.get("name")
        expr = ext_variables.get("expr")

        if not name or not expr:
            raise StepExecutionError("变量提取配置不完整")

        extracted = self._resolve_json_path(response_json, expr)
        return {name: extracted}

    def _run_validators(self, response_json: Any) -> List[Dict[str, Any]]:
        validators = self.step.get("validators")
        if not validators or response_json is None:
            return []

        expr = validators.get("expr")
        operation = validators.get("operation")
        expected = validators.get("except_value")
        name = validators.get("name")

        if not expr or not operation:
            raise StepExecutionError("断言配置不完整")

        actual = self._resolve_json_path(response_json, expr)
        success = ConditionStepExecutor.compare(actual, operation, expected)
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

    @staticmethod
    def _resolve_json_path(data: Any, expr: str) -> Any:
        if not expr.startswith("$."):
            raise StepExecutionError("仅支持 $. 开头的 JSONPath 表达式")

        parts = [part for part in expr[2:].split(".") if part]
        current: Any = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    index = int(part)
                except ValueError as exc:
                    raise StepExecutionError(f"列表索引必须为整数: {part}") from exc
                try:
                    current = current[index]
                except IndexError as exc:
                    raise StepExecutionError(f"列表索引越界: {part}") from exc
            else:
                raise StepExecutionError(f"无法在 {type(current)} 类型上应用 JSONPath: {part}")
        return current


class DefaultStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        # 默认只执行子步骤
        child_results = await self._execute_children()
        for child in child_results:
            result.append_child(child)
            if not child.success:
                result.success = False


class StepExecutorFactory:
    """根据 StepType 创建对应执行器。"""

    EXECUTOR_MAP: Dict[StepType, Callable[[Dict[str, Any], StepExecutionContext], BaseStepExecutor]] = {
        StepType.LOOP: LoopStepExecutor,
        StepType.CONDITION: ConditionStepExecutor,
        StepType.PYTHON: PythonStepExecutor,
        StepType.WAIT: WaitStepExecutor,
        StepType.HTTP: HttpStepExecutor,
        StepType.TCP: HttpStepExecutor,
    }

    @classmethod
    def create_executor(cls, step: Dict[str, Any], context: StepExecutionContext) -> BaseStepExecutor:
        step_type = StepType(step.get("step_type"))
        executor_cls = cls.EXECUTOR_MAP.get(step_type, DefaultStepExecutor)
        return executor_cls(step, context)


class AutoTestStepExecutionEngine:
    """测试步骤执行引擎入口。"""

    def __init__(self, *, http_client: Optional[HttpClientProtocol] = None) -> None:
        self._http_client = http_client

    async def execute_case(
            self,
            case: Dict[str, Any],
            steps: Iterable[Dict[str, Any]],
            *,
            initial_variables: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[StepExecutionResult], Dict[int, List[str]]]:
        async with StepExecutionContext(
                case_id=case.get("id"),
                case_code=case.get("case_code"),
                initial_variables=initial_variables,
                http_client=self._http_client,
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

            return results, context.logs

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

            results, logs = await engine.execute_case(
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
        if result.variables:
            print(f"{prefix}   变量: {json.dumps(result.variables, ensure_ascii=False)}")
        if result.validators:
            print(f"{prefix}   断言: {json.dumps(result.validators, ensure_ascii=False)}")
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
