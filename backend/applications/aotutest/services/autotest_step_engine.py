"""自动化测试-步骤执行引擎

面向对象实现, 负责根据步骤树结构执行测试步骤。
"""
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
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Tuple

import httpx
import requests

from backend.applications.aotutest.models.autotest_model import AutoTestApiEnvInfo
from backend.applications.aotutest.schemas.autotest_detail_schema import AutoTestApiDetailCreate
from backend.applications.aotutest.schemas.autotest_report_schema import (
    AutoTestApiReportCreate,
    AutoTestApiReportUpdate,
)
from backend.applications.aotutest.schemas.autotest_step_schema import AutoTestStepTreeUpdateItem
from backend.applications.aotutest.services.autotest_detail_crud import AUTOTEST_API_DETAIL_CRUD
from backend.applications.aotutest.services.autotest_report_crud import AUTOTEST_API_REPORT_CRUD
from backend.enums.autotest_enum import StepType, ReportType, LoopMode, LoopErrorStrategy
from backend.services.ctx import CTX_USER_ID


class AutoTestToolService:

    def __init__(self):
        ...

    @classmethod
    def resolve_json_path(cls, data: Any, expr: str) -> Any:
        """解析JSONPath表达式"""
        if not expr or not expr.startswith("$."):
            raise ValueError(f"仅支持 $. 开头的 JSONPath 表达式: {expr}")

        parts = [part for part in expr[2:].split(".") if part]
        current: Any = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    index = int(part)
                except ValueError:
                    raise ValueError(f"列表索引必须为整数: {part}")
                try:
                    current = current[index]
                except IndexError:
                    raise ValueError(f"列表索引越界: {part}")
            else:
                raise ValueError(f"无法在 {type(current)} 类型上应用 JSONPath: {part}")
        return current

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        """
        标准化值的类型，用于比较
        - 如果值是可以转换为数字的字符串，则转换为数字
        - 如果值是布尔型字符串，则转换为布尔值
        """
        if value is None:
            return None
        if isinstance(value, (int, float, bool)):
            return value
        if isinstance(value, str):
            # 尝试转换为整数
            if value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
                return int(value)
            # 尝试转换为浮点数
            try:
                if '.' in value:
                    return float(value)
            except ValueError:
                pass
            # 尝试转换为布尔值
            if value.lower() == 'true':
                return True
            if value.lower() == 'false':
                return False
        return value

    @classmethod
    def _type_aware_equals(cls, actual: Any, expected: Any) -> bool:
        """
        类型感知的相等比较
        - 先尝试直接比较
        - 如果类型不同，尝试标准化后比较
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
        类型感知的数值比较（用于大于、小于等）
        """
        norm_actual = cls._normalize_value(actual)
        norm_expected = cls._normalize_value(expected)
        # 确保都是数值类型才能进行大小比较
        if isinstance(norm_actual, (int, float)) and isinstance(norm_expected, (int, float)):
            return comparator(norm_actual, norm_expected)
        # 如果不是数值，尝试字符串比较
        return comparator(str(actual), str(expected))

    @classmethod
    def compare_assertion(cls, actual: Any, operation: str, expected: Any) -> bool:
        """比较断言结果，支持类型智能转换"""
        op_map = {
            "等于": lambda a, b: cls._type_aware_equals(a, b),
            "不等于": lambda a, b: not cls._type_aware_equals(a, b),
            "大于": lambda a, b: cls._type_aware_compare(a, b, lambda x, y: x > y),
            "大于等于": lambda a, b: cls._type_aware_compare(a, b, lambda x, y: x >= y),
            "小于": lambda a, b: cls._type_aware_compare(a, b, lambda x, y: x < y),
            "小于等于": lambda a, b: cls._type_aware_compare(a, b, lambda x, y: x <= y),
            "长度等于": lambda a, b: len(str(a)) == int(cls._normalize_value(b)) if cls._normalize_value(
                b) is not None else False,
            "包含": lambda a, b: str(b) in str(a),
            "不包含": lambda a, b: str(b) not in str(a),
            "以...开始": lambda a, b: str(a).startswith(str(b)),
            "以...结束": lambda a, b: str(a).endswith(str(b)),
        }
        comparator = op_map.get(operation)
        if comparator is None:
            raise ValueError(f"不支持的操作符: {operation}")
        try:
            return comparator(actual, expected)
        except Exception as e:
            raise ValueError(f"断言比较失败: {str(e)}")

    @classmethod
    def validate_step_tree_structure(cls, steps_data: List[AutoTestStepTreeUpdateItem]) -> tuple:
        """
        校验步骤树结构合法性

        Args:
            steps_data: 步骤树数据

        Returns:
            tuple[bool, Optional[str]]: (是否合法, 错误信息)
        """
        from backend.applications.aotutest.models.autotest_model import StepType

        # 允许有子步骤的步骤类型
        allowed_children_types = {StepType.LOOP, StepType.IF}

        def check_step_recursive(step: AutoTestStepTreeUpdateItem, visited_ids: set, path: list) -> tuple:
            """递归检查步骤"""
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
                    return False, f"步骤(step_id={step_id}, step_code={step_code or 'N/A'}, step_type={step.step_type})不允许包含子步骤，仅允许'循环结构'和'条件分支'类型的步骤包含子步骤"

                # 递归检查子步骤
                for child in step.children:
                    is_valid, error_msg = check_step_recursive(child, visited_ids.copy(), path.copy())
                    if not is_valid:
                        return False, error_msg

            return True, None

        # 检查所有根步骤
        for step in steps_data:
            is_valid, error_msg = check_step_recursive(step, set(), [])
            if not is_valid:
                return False, error_msg

        return True, None

    @classmethod
    def normalize_step(cls, step: Dict[str, Any]) -> Dict[str, Any]:
        """
        规范化步骤数据格式

        Args:
            step: 步骤数据字典

        Returns:
            规范化后的步骤数据字典
        """
        step = step.copy()

        # 处理conditions：如果是数组，取第一个并转为JSON字符串
        conditions = step.get("conditions")
        if isinstance(conditions, list) and len(conditions) > 0:
            condition_obj = conditions[0]
            step["conditions"] = json.dumps(condition_obj, ensure_ascii=False)
        elif conditions is None:
            step["conditions"] = None

        # extract_variables和assert_validators保持数组格式（执行引擎已支持）
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
    def collect_defined_variables(cls, steps_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        递归收集所有步骤的defined_variables作为初始变量
        Args:
            steps_list: 步骤列表

        Returns:
            合并后的变量字典
        """
        variables = {}
        for step in steps_list:
            defined_vars = step.get("defined_variables")

            if isinstance(defined_vars, dict):
                variables.update(defined_vars)
            # 递归处理children和quote_steps
            children = step.get("children", [])
            quote_steps = step.get("quote_steps", [])
            variables.update(cls.collect_defined_variables(children))
            variables.update(cls.collect_defined_variables(quote_steps))
        return variables


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
        self.defined_variables: Dict[str, Any] = dict(initial_variables or {})
        self.session_variables: Dict[str, Any] = {}
        self.extract_variables: Dict[str, Any] = {}
        self.logs: Dict[int, List[str]] = {}
        self.step_cycle_index: Dict[str, int] = {}
        self._current_step_no: Optional[int] = None
        self._http_client = http_client
        self._exit_stack = AsyncExitStack()
        self.timeout: float = 30.0
        self.connect: float = 10.0

    async def __aenter__(self) -> "StepExecutionContext":
        """异步上下文管理器入口方法, 初始化HTTP客户端（如未提供）

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

    def log(self, message: str, step_no: Optional[int] = None) -> None:
        step_no = step_no or self._current_step_no
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
        """获取变量值, 按优先级查找：extract_variables > session_variables > defined_variables"""
        if not name or not isinstance(name, str):
            raise StepExecutionError(f"【获取变量】变量名无效: 变量名必须是非空字符串, 当前值: {name}")
        for scope_name, scope in [
            ("extract_variables", self.extract_variables),
            ("session_variables", self.session_variables),
            ("defined_variables", self.defined_variables)
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
                        self.log("【获取变量】占位符格式错误: ${} 中变量名为空, 保留原值")
                        return match.group(0)
                    try:
                        resolved = self.get_variable(var_name)
                    except KeyError:
                        self.log(f"【获取变量】占位符变量({var_name})未定义, 将保留原占位符: ${'{'}{var_name}{'}'}")
                        return match.group(0)
                    except Exception as e:
                        self.log(f"【获取变量】获取占位符变量({var_name})的值时发生错误(保留原占位符): {e}")
                        return match.group(0)
                    try:
                        return str(resolved)
                    except Exception as e:
                        self.log(f"【获取变量】将变量({var_name})的值转换为字符串时失败(保留原占位符): {e}")
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
            self.log(f"【获取变量】占位符解析过程中发生未预期的错误: {e}, 将返回原值")
            return value

    async def sleep(self, seconds: Optional[float]) -> None:
        if seconds is None:
            return
        try:
            wait_time = float(seconds)
        except (ValueError, TypeError) as e:
            raise StepExecutionError(f"【等待控制】等待时间格式错误: 期望数字类型, 实际值: {seconds}, 错误: {e}") from e
        if wait_time < 0:
            raise StepExecutionError(f"【等待控制】等待时间不能为负数: 当前值 {wait_time} 秒")
        if wait_time > 300:
            raise StepExecutionError(f"【等待控制】等待时间不能大于300秒: 当前值 {wait_time} 秒")
        self.log(f"【等待控制】等待 {wait_time} 秒")
        try:
            await asyncio.sleep(wait_time)
        except Exception as e:
            raise StepExecutionError(f"【等待控制】执行等待操作时发生错误: {e}") from e

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
            self.log(f"【HTTP请求】请求: {method} {url} kwargs={filtered_kwargs}")
            try:
                response = await client.request(method, url, **kwargs)
                self.log(
                    f"【HTTP请求】响应代码: {response.status_code}, "
                    f"响应消息: {response.reason_phrase}, 响应耗时: {response.elapsed.total_seconds()}"
                )
                return response
            except httpx.TimeoutException as e:
                error_message: str = (
                    f"【HTTP请求】请求超时: 请求({method})({url})在指定时间内({self.timeout})未收到响应"
                    f"(可能原因: 网络延迟、服务器响应慢或超时设置过短)"
                )
                self.log(error_message)
                raise StepExecutionError(error_message) from e
            except httpx.RequestError as e:
                error_message: str = (
                    f"【HTTP请求】请求失败: 请求({method})({url})时发生网络错误"
                    f"(可能原因: 网络连接问题、DNS解析失败或服务器不可达, 详情: {e})"
                )
                self.log(error_message)
                raise StepExecutionError(error_message) from e
            except Exception as e:
                error_message: str = f"【HTTP请求】请求异常: 请求({method})({url})时发生异常, 错误描述: {e}"
                self.log(error_message)
                raise StepExecutionError(error_message) from e
        except StepExecutionError:
            raise
        except Exception as e:
            error_message: str = f"【HTTP请求】请求异常: 在处理请求参数或发送请求的过程出现意外情况, 错误描述: {e}"
            self.log(error_message)
            raise StepExecutionError(error_message) from e

    def run_python_code(self, code: str, *, namespace: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行 Python 代码块, 返回新增变量。"""
        if not code:
            return {}
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
                f"【执行代码请求(Python)】代码解析错误: "
                f"请遵循Python PEP8规范, 错误位置: 第{e.lineno}行, 错误描述: {e.msg}"
            )
            self.log(error_message)
            raise StepExecutionError(error_message) from e
        except NameError as e:
            error_message: str = f"【执行代码请求(Python)】代码执行错误: 使用了未定义的变量或函数 '{e.name}', 请检查代码中引用的变量和函数是否已定义"
            self.log(error_message)
            raise StepExecutionError(error_message) from e
        except Exception as e:
            error_message: str = f"【执行代码请求(Python)】代码执行异常: {type(e).__name__}: {e}, 请检查代码逻辑是否正确"
            self.log(error_message)
            raise StepExecutionError(error_message) from e

        functions = {
            name: obj for name, obj in local_context.items() if callable(obj)
        }
        if functions:
            if len(functions) == 1:
                try:
                    func = next(iter(functions.values()))
                    result = func()
                except Exception as e:
                    error_message: str = f"【执行代码请求(Python)】调用Python函数时发生错误: 函数执行失败, 错误描述: {e}"
                    self.log(error_message)
                    raise StepExecutionError(error_message) from e
            else:
                func_names = ", ".join(functions.keys())
                raise StepExecutionError(
                    f"【执行代码请求(Python)】代码中定义了多个函数: {func_names}, 仅支持定义一个函数作为入口, 请修改代码只保留一个函数"
                )
        elif "result" in local_context:
            result = local_context["result"]
        else:
            result = None

        if result is None:
            self.log("【执行代码请求(Python)】代码未返回结果, 返回空字典")
            return {}
        if not isinstance(result, dict):
            error_message: str = (
                f"【执行代码请求(Python)】代码返回值类型错误: 期望返回字典(dict)类型, "
                f"实际返回类型: {type(result).__name__}, 返回值: {result}"
            )
            self.log(error_message)
            raise StepExecutionError(error_message)
        self.log(f"【执行代码请求(Python)】返回结果: {result}")
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
                self.log("【执行代码请求(Python)】占位符格式错误: ${} 中变量名为空, 保留原值")
                return match.group(0)

            try:
                var_value = self.get_variable(var_name)
            except KeyError:
                self.log(f"【执行代码请求(Python)】占位符变量({var_name})未定义, 将保留原占位符")
                return match.group(0)
            except Exception as e:
                self.log(f"【执行代码请求(Python)】获取占位符变量({var_name})失败: {e}, 将保留原占位符")
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
                return match.group(0)

            try:
                var_value = self.get_variable(var_name)
            except KeyError:
                self.log(f"【执行代码请求(Python)】占位符变量({var_name})未定义, 将保留原占位符")
                return match.group(0)
            except Exception as e:
                self.log(f"【执行代码请求(Python)】获取占位符变量({var_name})失败: {e}, 将保留原占位符")
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
                return match.group(0)

            try:
                var_value = self.get_variable(var_name)
            except KeyError:
                self.log(f"【执行代码请求(Python)】占位符变量({var_name})未定义, 将保留原占位符")
                return match.group(0)
            except Exception as e:
                self.log(f"【执行代码请求(Python)】获取占位符变量({var_name})失败: {e}, 将保留原占位符")
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
            self.log(f"【执行代码请求(Python)】解析代码占位符时发生错误: {e}, 将使用原代码")
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
        return self.step.get("step_id")

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
        # 默认循环次数为1；若循环控制器提前写入, 则取已记录值
        num_cycles = self.context.step_cycle_index.get(self.step_code or "", 1)
        # 确保记录下来, 便于子层读取
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
        self.context.set_current_step_no(self.step_no)
        previous_step_no: Optional[int] = self.context.current_step_no
        try:
            await self._execute(result)
        except Exception as e:
            result.success = False
            result.error = str(e)
            self.context.log(f"步骤执行失败: {e}", step_no=previous_step_no)
        finally:
            # 无论成功还是失败, 都将当前步骤提取的变量追加到会话变量, 便于后续步骤复用
            try:
                if result.extract_variables:
                    self.context.update_variables(result.extract_variables, scope="session_variables")
                    self.context.log(
                        f"【合并变量】-【session_variables】成功: {result.extract_variables}",
                        step_no=self.step_no
                    )
            except Exception as e:
                # 变量合并失败不应该影响步骤执行结果
                self.context.log(f"【合并变量】-【session_variables】失败: {e}", step_no=self.step_no)

            self.context.set_current_step_no(step_no=previous_step_no)
            end = time.perf_counter()
            result.elapsed = round(end - start, 6)
            if self.context.report_code:
                try:
                    await self._save_step_detail(result, step_st_time_str, num_cycles)
                except Exception as e:
                    # 保存步骤明细失败不应该影响执行流程
                    self.context.log(f"保存步骤明细失败: {e}", step_no=self.step_no)
        return result

    async def _save_step_detail(self, result: StepExecutionResult, step_st_time_str: str, num_cycles: int) -> None:
        """保存步骤明细到数据库（含无响应步骤占位；循环多次执行合并）"""
        try:
            step_end_time = datetime.now()
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

            step_code = self.step_code

            # 1. defined_variables: 从步骤配置中获取用户定义的变量
            # 这是用户在步骤配置中预先定义的变量（如固定值、随机函数等）
            defined_variables = self.step.get("defined_variables") or {}

            # 2. extract_variables: 从响应中提取的变量
            # 只包含通过 extract_variables 配置从响应中提取的变量
            extract_variables = {}
            extract_variables_config: List[Dict[str, Any]] = self.step.get("extract_variables")
            if extract_variables_config and isinstance(extract_variables_config, list) and result.extract_variables:
                for extract in extract_variables_config:
                    ext_name = extract.get("name")
                    if ext_name and ext_name in result.extract_variables:
                        extract_variables[ext_name] = result.extract_variables[ext_name]

            # 3. session_variables: 累积的会话变量（包含所有步骤产生的变量）
            # 使用深拷贝确保保存的是当前时刻的快照, 不会被后续步骤影响
            # session_variables 包含：
            # - 从响应中提取的变量（extract_variables）
            # - 其他步骤产生的变量
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
            await AUTOTEST_API_DETAIL_CRUD.create_detail(detail_create)
        except Exception as e:
            error_message: str = f"保存步骤明细到数据库失败: 步骤ID={self.step_id}, 步骤编号={self.step_no}, 错误详情: {e}"
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
                error_message: str = (
                    f"子步骤执行失败: "
                    f"步骤序号='{child.get('step_no')}', "
                    f"步骤名称='{child.get('step_name')}', "
                    f"步骤类型={child.get('step_type')}, "
                    f"错误类型={type(e).__name__}, "
                    f"错误详情: {e}"
                )
                self.context.log(error_message, step_no=child.get("step_no"))
                failed_result = StepExecutionResult(
                    step_id=child.get("id"),
                    step_no=child.get("step_no"),
                    step_code=child.get("step_code") or child.get("id"),
                    step_name=child.get("step_name", ""),
                    step_type=StepType(child.get("step_type", "")),
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
                raise StepExecutionError("【循环结构】循环模式未指定, 请明确指定循环模式类型")

            try:
                loop_mode = LoopMode(loop_mode_str)
            except (ValueError, TypeError) as e:
                raise StepExecutionError(
                    f"【循环结构】循环模式{loop_mode_str}无效(仅允许选择: 次数循环、对象循环、字典循环、条件循环)"
                ) from e

            # 获取错误处理策略，必须明确指定
            on_error_str = self.step.get("loop_on_error")
            if not on_error_str:
                raise StepExecutionError("【循环结构】错误处理策略未指定, 请明确指定错误处理策略")

            try:
                on_error = LoopErrorStrategy(on_error_str)
            except (ValueError, TypeError) as e:
                raise StepExecutionError(
                    f"【循环结构】错误处理策略{on_error_str}无效(仅允许选择: 继续下一次循环、中断循环、停止整个用例执行)"
                ) from e

            # 根据循环模式执行不同的逻辑
            if loop_mode == LoopMode.COUNT:
                await self._execute_count_loop(result, on_error)
            elif loop_mode == LoopMode.ITERABLE:
                await self._execute_iterable_loop(result, on_error)
            elif loop_mode == LoopMode.DICT:
                await self._execute_dict_loop(result, on_error)
            elif loop_mode == LoopMode.CONDITION:
                await self._execute_condition_loop(result, on_error)
            else:
                raise StepExecutionError(f"【循环结构】不支持的循环模式: {loop_mode}")

        except StepExecutionError:
            raise
        except Exception as e:
            result.success = False
            result.error = f"【循环结构】执行异常: {e}"
            self.context.log(result.error, step_no=self.step_no)
            raise StepExecutionError(result.error) from e

    async def _execute_count_loop(self, result: StepExecutionResult, on_error: LoopErrorStrategy) -> None:
        """次数循环模式"""
        loop_maximums = self.step.get("loop_maximums")
        if not loop_maximums:
            raise StepExecutionError("【循环结构】次数循环模式缺少必要字段: loop_maximums")

        loop_interval = self.step.get("loop_interval")
        guard_limit = 100  # 安全限制

        self.context.log(f"【循环结构】次数循环开始: 最大循环次数={loop_maximums}", step_no=self.step_no)

        for iteration in range(1, loop_maximums + 1):
            # 记录循环次数
            if self.step_code:
                self.context.step_cycle_index[self.step_code] = iteration

            self.context.log(f"【循环结构】次数循环: 第{iteration}/{loop_maximums}次执行", step_no=self.step_no)

            # 为子步骤记录当前循环次数
            for child in self.children:
                child_code = child.get("step_code") or child.get("id") or ""
                if child_code:
                    self.context.step_cycle_index[child_code] = iteration

            # 执行子步骤
            try:
                child_results = await self._execute_children()
                for child in child_results:
                    result.append_child(child)
                    if not child.success:
                        result.success = False
                        if on_error == LoopErrorStrategy.STOP:
                            raise StepExecutionError(f"【循环结构】子步骤执行失败, 停止整个用例执行")
                        elif on_error == LoopErrorStrategy.BREAK:
                            self.context.log(f"【循环结构】子步骤执行失败, 中断循环", step_no=self.step_no)
                            return
                        # CONTINUE 模式继续下一次循环
            except StepExecutionError:
                if on_error == LoopErrorStrategy.STOP:
                    raise
                elif on_error == LoopErrorStrategy.BREAK:
                    self.context.log(f"【循环结构】子步骤执行异常, 中断循环", step_no=self.step_no)
                    return
                # CONTINUE 模式继续下一次循环
            except Exception as e:
                error_message = f"【循环结构】次数循环: 第{iteration}次执行失败, 错误描述: {e}"
                self.context.log(error_message, step_no=self.step_no)
                result.success = False
                if on_error == LoopErrorStrategy.STOP:
                    raise StepExecutionError(error_message) from e
                elif on_error == LoopErrorStrategy.BREAK:
                    return
                # CONTINUE 模式继续下一次循环

            # 循环间隔（最后一次不需要等待）
            if iteration < loop_maximums and loop_interval and loop_interval > 0:
                await self.context.sleep(loop_interval)

            # 安全检查
            if iteration >= guard_limit:
                raise StepExecutionError(
                    f"【循环结构】循环次数超过最大限制{guard_limit}次: 已执行 {iteration} 次, "
                    f"疑似无限循环, 为保护系统安全已自动终止循环"
                )

        self.context.log(f"【循环结构】次数循环结束: 共执行{loop_maximums}次", step_no=self.step_no)

    async def _execute_iterable_loop(self, result: StepExecutionResult, on_error: LoopErrorStrategy) -> None:
        """对象循环模式"""
        loop_iterable = self.step.get("loop_iterable")
        if not loop_iterable:
            raise StepExecutionError("【循环结构】对象循环模式缺少必要字段: loop_iterable")

        # 获取变量名（loop_iter_idx 是变量名，用于存储 enumerate 得到的索引值）
        loop_iter_idx = self.step.get("loop_iter_idx")
        # 处理可能是 IntField 的情况（模型定义问题，实际应该是变量名字符串）
        if isinstance(loop_iter_idx, int):
            # 如果是整数，可能是模型默认值1，使用默认变量名
            index_var_name = "loop_index"
        else:
            # 如果是字符串，直接使用；如果为空，使用默认值
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
                    f"【循环结构】对象循环模式: loop_iterable 不能是字符串或字节类型, "
                    f"请使用列表、元组等可迭代对象"
                )

            if not hasattr(iterable_obj, "__iter__"):
                raise StepExecutionError(
                    f"【循环结构】对象循环模式: loop_iterable 必须是可迭代对象(列表、元组等), "
                    f"当前类型: {type(iterable_obj).__name__}"
                )

            # 转换为列表以便索引
            iterable_list = list(iterable_obj)
            total_items = len(iterable_list)

            if total_items == 0:
                self.context.log("【循环结构】对象循环: 可迭代对象为空, 跳过循环", step_no=self.step_no)
                return

            self.context.log(
                f"【循环结构】对象循环开始: 可迭代对象长度={total_items}, "
                f"索引变量={index_var_name}, 值变量={value_var_name}",
                step_no=self.step_no
            )

            for idx, item in enumerate(iterable_list, start=start_index):
                # 记录循环次数
                if self.step_code:
                    self.context.step_cycle_index[self.step_code] = idx

                self.context.log(
                    f"【循环结构】对象循环: 第{idx}/{total_items}次执行, 值={item}",
                    step_no=self.step_no
                )

                # 将循环变量注入到上下文
                self.context.update_variables(
                    {f"{index_var_name}_{idx}": idx, f"{value_var_name}_{idx}": item},
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
                            if on_error == LoopErrorStrategy.STOP:
                                raise StepExecutionError(f"【循环结构】子步骤执行失败, 停止整个用例执行")
                            elif on_error == LoopErrorStrategy.BREAK:
                                self.context.log(f"【循环结构】子步骤执行失败, 中断循环", step_no=self.step_no)
                                return
                except StepExecutionError:
                    if on_error == LoopErrorStrategy.STOP:
                        raise
                    elif on_error == LoopErrorStrategy.BREAK:
                        self.context.log(f"【循环结构】子步骤执行异常, 中断循环", step_no=self.step_no)
                        return
                except Exception as e:
                    error_message = f"【循环结构】对象循环: 第{idx}次执行失败, 错误描述: {e}"
                    self.context.log(error_message, step_no=self.step_no)
                    result.success = False
                    if on_error == LoopErrorStrategy.STOP:
                        raise StepExecutionError(error_message) from e
                    elif on_error == LoopErrorStrategy.BREAK:
                        return

                # 循环间隔（最后一次不需要等待）
                if idx < total_items and loop_interval and loop_interval > 0:
                    await self.context.sleep(loop_interval)

            self.context.log(f"【循环结构】对象循环结束: 共执行{total_items}次", step_no=self.step_no)

        except StepExecutionError:
            raise
        except Exception as e:
            raise StepExecutionError(f"【循环结构】对象循环执行异常: {e}") from e

    async def _execute_dict_loop(self, result: StepExecutionResult, on_error: LoopErrorStrategy) -> None:
        """字典循环模式"""
        loop_iterable = self.step.get("loop_iterable")
        if not loop_iterable:
            raise StepExecutionError("【循环结构】字典循环模式缺少必要字段: loop_iterable")

        # 获取变量名（loop_iter_idx 是索引变量名，loop_iter_key 是键变量名，loop_iter_val 是值变量名）
        loop_iter_idx = self.step.get("loop_iter_idx")
        # 处理可能是 IntField 的情况（模型定义问题，实际应该是变量名字符串）
        if isinstance(loop_iter_idx, int):
            # 如果是整数，可能是模型默认值1，使用默认变量名
            index_var_name = "loop_index"
        else:
            # 如果是字符串，直接使用；如果为空，使用默认值
            index_var_name = loop_iter_idx if loop_iter_idx else "loop_index"

        # 循环索引从1开始（enumerate的start参数固定为1）
        start_index = 1

        key_var_name = self.step.get("loop_iter_key") or "loop_key"
        value_var_name = self.step.get("loop_iter_val") or "loop_value"
        loop_interval = self.step.get("loop_interval")

        # 解析字典对象来源
        try:
            dict_obj = self._parse_iterable_source(loop_iterable)

            # 验证是否为字典
            if not isinstance(dict_obj, dict):
                raise StepExecutionError(
                    f"【循环结构】字典循环模式: loop_iterable 必须是字典类型, "
                    f"当前类型: {type(dict_obj).__name__}"
                )

            total_items = len(dict_obj)
            if total_items == 0:
                self.context.log("【循环结构】字典循环: 字典对象为空, 跳过循环", step_no=self.step_no)
                return

            self.context.log(
                f"【循环结构】字典循环开始: 字典键数量={total_items}, "
                f"索引变量={index_var_name}, 键变量={key_var_name}, 值变量={value_var_name}",
                step_no=self.step_no
            )

            for idx, (key, value) in enumerate(dict_obj.items(), start=start_index):
                # 记录循环次数
                if self.step_code:
                    self.context.step_cycle_index[self.step_code] = idx

                self.context.log(
                    f"【循环结构】字典循环: 第{idx}/{total_items}次执行, 键={key}, 值={value}",
                    step_no=self.step_no
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
                            if on_error == LoopErrorStrategy.STOP:
                                raise StepExecutionError(f"【循环结构】子步骤执行失败, 停止整个用例执行")
                            elif on_error == LoopErrorStrategy.BREAK:
                                self.context.log(f"【循环结构】子步骤执行失败, 中断循环", step_no=self.step_no)
                                return
                except StepExecutionError:
                    if on_error == LoopErrorStrategy.STOP:
                        raise
                    elif on_error == LoopErrorStrategy.BREAK:
                        self.context.log(f"【循环结构】子步骤执行异常, 中断循环", step_no=self.step_no)
                        return
                except Exception as e:
                    error_message = f"【循环结构】字典循环: 第{idx}次执行失败, 错误描述: {e}"
                    self.context.log(error_message, step_no=self.step_no)
                    result.success = False
                    if on_error == LoopErrorStrategy.STOP:
                        raise StepExecutionError(error_message) from e
                    elif on_error == LoopErrorStrategy.BREAK:
                        return

                # 循环间隔（最后一次不需要等待）
                if idx < total_items and loop_interval and loop_interval > 0:
                    await self.context.sleep(loop_interval)

            self.context.log(f"【循环结构】字典循环结束: 共执行{total_items}次", step_no=self.step_no)

        except StepExecutionError:
            raise
        except Exception as e:
            raise StepExecutionError(f"【循环结构】字典循环执行异常: {e}") from e

    async def _execute_condition_loop(self, result: StepExecutionResult, on_error: LoopErrorStrategy) -> None:
        """条件循环模式"""
        condition = self.step.get("conditions")
        if not condition:
            raise StepExecutionError("【循环结构】条件循环模式缺少必要字段: conditions")

        loop_timeout = self.step.get("loop_timeout")
        loop_interval = self.step.get("loop_interval")
        guard_limit = 1000  # 安全限制

        # 记录开始时间（用于超时控制）
        start_time = time.time()
        iteration = 0
        should_continue = True

        self.context.log(
            f"【循环结构】条件循环开始: 超时时间={loop_timeout if loop_timeout else '无限制'}秒",
            step_no=self.step_no
        )

        while should_continue:
            iteration += 1

            # 检查超时
            if loop_timeout and loop_timeout > 0:
                elapsed = time.time() - start_time
                if elapsed >= loop_timeout:
                    self.context.log(
                        f"【循环结构】条件循环超时: 已执行 {iteration} 次, 耗时 {elapsed:.2f} 秒, 超过限制 {loop_timeout} 秒",
                        step_no=self.step_no
                    )
                    break

            # 记录循环次数
            if self.step_code:
                self.context.step_cycle_index[self.step_code] = iteration

            self.context.log(f"【循环结构】条件循环: 第{iteration}次执行", step_no=self.step_no)

            # 为子步骤记录当前循环次数
            for child in self.children:
                child_code = child.get("step_code") or child.get("id") or ""
                if child_code:
                    self.context.step_cycle_index[child_code] = iteration

            # 执行子步骤
            try:
                child_results = await self._execute_children()
                for child in child_results:
                    result.append_child(child)
                    if not child.success:
                        result.success = False
                        if on_error == LoopErrorStrategy.STOP:
                            raise StepExecutionError(f"【循环结构】子步骤执行失败, 停止整个用例执行")
                        elif on_error == LoopErrorStrategy.BREAK:
                            self.context.log(f"【循环结构】子步骤执行失败, 中断循环", step_no=self.step_no)
                            should_continue = False
                            break
            except StepExecutionError:
                if on_error == LoopErrorStrategy.STOP:
                    raise
                elif on_error == LoopErrorStrategy.BREAK:
                    self.context.log(f"【循环结构】子步骤执行异常, 中断循环", step_no=self.step_no)
                    should_continue = False
                    break
            except Exception as e:
                error_message = f"【循环结构】条件循环: 第{iteration}次执行失败, 错误描述: {e}"
                self.context.log(error_message, step_no=self.step_no)
                result.success = False
                if on_error == LoopErrorStrategy.STOP:
                    raise StepExecutionError(error_message) from e
                elif on_error == LoopErrorStrategy.BREAK:
                    should_continue = False
                    break

            if not should_continue:
                break

            # 评估循环条件
            try:
                if not self._evaluate_condition(condition):
                    self.context.log(f"【循环结构】条件循环: 条件不满足, 结束循环", step_no=self.step_no)
                    should_continue = False
                    break
            except Exception as e:
                result.success = False
                error_message = f"【循环结构】条件评估失败: {e}"
                result.error = error_message
                self.context.log(error_message, step_no=self.step_no)
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

        self.context.log(f"【循环结构】条件循环结束: 共执行{iteration}次", step_no=self.step_no)

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
                f"【循环结构】循环条件JSON格式错误: 条件配置不是有效的JSON格式, "
                f"错误位置: 第{e.lineno}行第{e.colno}列, 错误信息: {e.msg}, 请检查条件配置格式"
            ) from e

        except Exception as e:
            raise StepExecutionError(
                f"【循环结构】处理循环条件时发生错误: 在解析或处理条件配置时失败, 错误详情: {e}") from e

        value_expr = condition_obj.get("value")
        operation = condition_obj.get("operation")
        except_value = condition_obj.get("except_value")

        if value_expr is None or operation is None:
            raise StepExecutionError(
                f"【循环结构】循环条件配置不完整: 缺少必要字段, value={value_expr}, operation={operation}, 请检查条件配置")

        try:
            resolved = self.context.resolve_placeholders(value_expr)
            if isinstance(resolved, str) and resolved.startswith("${") and resolved.endswith("}"):
                variable_name = resolved[2:-1]
                try:
                    value = self.context.get_variable(variable_name)
                except KeyError as e:
                    raise StepExecutionError(f"【循环结构】循环条件中变量未定义: {variable_name}") from e
            else:
                value = resolved
        except Exception as e:
            if isinstance(e, StepExecutionError):
                raise
            raise StepExecutionError(f"【循环结构】循环条件变量解析失败: {e}") from e

        try:
            return ConditionStepExecutor.compare(value, operation, except_value)
        except Exception as e:
            raise StepExecutionError(f"【循环结构】循环条件比较失败: {e}") from e

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
                raise StepExecutionError("【条件分支】缺少条件配置")

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
                    f"【条件分支】条件配置格式错误: 条件配置不是有效的JSON格式, "
                    f"错误位置: 第{e.lineno}行第{e.colno}列, 错误信息: {e.msg}, 请检查条件配置格式"
                ) from e
            except Exception as e:
                raise StepExecutionError(
                    f"【条件分支】解析条件配置时发生错误: 在处理条件JSON字符串时失败, 错误详情: {e}") from e

            value_expr = condition_obj.get("value")
            operation = condition_obj.get("operation")
            except_value = condition_obj.get("except_value")
            desc = condition_obj.get("desc", "")
            if value_expr is None or operation is None:
                raise StepExecutionError(
                    f"【条件分支】条件配置不完整: 缺少必要字段, value={value_expr}, operation={operation}, 请检查条件配置是否完整"
                )
            try:
                resolved_value_expr = self.context.resolve_placeholders(value_expr)
            except StepExecutionError as e:
                raise
            except Exception as e:
                raise StepExecutionError(
                    f"【条件分支】解析条件变量占位符时发生错误: 在处理条件值'{value_expr}'中的变量占位符时失败, 错误详情: {e}"
                ) from e

            try:
                if isinstance(resolved_value_expr, str) and resolved_value_expr.startswith(
                        "${") and resolved_value_expr.endswith("}"):
                    variable_name = resolved_value_expr[2:-1]
                    try:
                        value = self.context.get_variable(variable_name)
                    except KeyError as e:
                        raise StepExecutionError(f"【条件分支】条件中变量未定义: {variable_name}") from e
                else:
                    value = resolved_value_expr
            except StepExecutionError:
                raise
            except Exception as e:
                raise StepExecutionError(f"【条件分支】条件值获取失败: {e}") from e

            try:
                if not self.compare(value, operation, except_value):
                    result.success = True
                    result.message = f"【条件分支】条件未满足: {desc}"
                    self.context.log(result.message, step_no=self.step_no)
                    return
            except Exception as e:
                raise StepExecutionError(f"【条件分支】条件比较失败: {e}") from e

            result.message = f"【条件分支】条件满足: {desc}"
            self.context.log(result.message, step_no=self.step_no)
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
                self.context.log(error_message, step_no=self.step_no)
        except Exception as e:
            # 捕获条件判断的异常, 避免阻断后续执行
            result.success = False
            result.error = str(e)
            result.message = f"【条件分支】条件执行异常: {e}"
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
            raise StepExecutionError(f"【条件分支】不支持的条件操作符: {operation}")
        return comparator(value, except_value)


class PythonStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        try:
            code = self.step.get("code")
            if not code:
                raise StepExecutionError("【执行代码请求(Python)】执行代码步骤缺少code配置")

            try:
                new_vars = self.context.run_python_code(
                    code,
                    namespace=self.context.clone_state(),
                )
            except StepExecutionError:
                raise
            except Exception as e:
                raise StepExecutionError(f"【执行代码请求(Python)】执行失败: {e}") from e

            if new_vars:
                try:
                    self.context.update_variables(new_vars, scope="extract_variables")
                    result.extract_variables.update(new_vars)
                except Exception as e:
                    raise StepExecutionError(f"【更新变量】-【extract_variables】失败: {e}") from e
        except StepExecutionError:
            raise
        except Exception as e:
            result.success = False
            result.error = f"【执行代码请求(Python)】执行异常: {e}"
            self.context.log(result.error, step_no=self.step_no)
            raise StepExecutionError(result.error) from e


class WaitStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        try:
            wait_seconds = self.step.get("wait")
            if wait_seconds is None:
                raise StepExecutionError("【等待控制】等待步骤缺少wait配置")

            try:
                wait_float = float(wait_seconds)
            except (ValueError, TypeError) as e:
                raise StepExecutionError(
                    f"【等待控制】等待时间格式错误: 期望数字类型, 实际值: {wait_seconds}, 错误: {e}"
                ) from e

            try:
                await self.context.sleep(wait_float)
            except StepExecutionError:
                raise
            except Exception as e:
                raise StepExecutionError(f"【等待控制】等待步骤执行失败: {e}") from e
        except StepExecutionError:
            raise
        except Exception as e:
            result.success = False
            result.error = f"【等待控制】等待步骤执行异常: {e}"
            self.context.log(result.error, step_no=self.step_no)
            raise StepExecutionError(result.error) from e


class TcpStepExecutor(BaseStepExecutor):
    pass


class DataBaseStepExecutor(BaseStepExecutor):
    pass


class HttpStepExecutor(BaseStepExecutor):
    async def _execute(self, result: StepExecutionResult) -> None:
        try:
            env = self.context.env
            step_type = self.step.get("step_type")
            request_url = self.step.get("request_url")
            request_project: str = self.step.get("request_project")
            if env and step_type == StepType.HTTP and not request_url.lower().startswith("http"):
                try:
                    env_instance = await AutoTestApiEnvInfo.filter(
                        project_id=request_project,
                        env_name=env,
                    ).first()
                    if not env_instance:
                        raise StepExecutionError(
                            f"【HTTP请求】环境配置不存在: "
                            f"项目({request_project})下未找到环境名称({env})的配置, 请检查环境配置是否正确"
                        )
                    execute_environment_host: str = env_instance.env_host.rstrip("/")
                    if not execute_environment_host:
                        raise StepExecutionError(
                            f"【HTTP请求】环境主机地址为空: 环境名称({env})的主机地址(env_host)未配置, 请检查环境配置"
                        )
                    request_url = f"{execute_environment_host}/{request_url.lstrip('/')}"
                except StepExecutionError:
                    raise
                except Exception as e:
                    raise StepExecutionError(
                        f"【HTTP请求】获取环境配置失败: 查询项目({request_project})环境名称({env})时发生错误: {e}"
                    ) from e

            request_method = (self.step.get("request_method") or "GET").upper()
            request_port = self.step.get("request_port")
            if request_url and not request_url.startswith("http") and not request_port:
                raise StepExecutionError(
                    f"【HTTP请求】请求URL格式错误: URL({request_url})不是有效的HTTP/HTTPS地址, 请检查URL配置或添加端口号"
                )
            if not request_url:
                raise StepExecutionError("【HTTP请求】HTTP请求配置错误: 请求URL(request_url)未配置, 请填写完整的请求地址")
            if request_port:
                raise StepExecutionError(
                    f"【HTTP请求】TCP请求暂不支持: 检测到请求端口配置(request_port={request_port}), "
                    f"当前版本仅支持HTTP/HTTPS请求, TCP请求功能尚未实现"
                )
            try:
                headers = self.context.resolve_placeholders(self.step.get("request_header") or {})
                params = self.context.resolve_placeholders(self.step.get("request_params") or {})
                form_data = self.context.resolve_placeholders(self.step.get("request_form_data") or {})
                urlencoded = self.context.resolve_placeholders(self.step.get("request_form_urlencoded") or {})
                request_body = self.context.resolve_placeholders(self.step.get("request_body"))
                request_text = self.step.get("request_text")
            except Exception as e:
                raise StepExecutionError(
                    f"【HTTP请求】解析请求参数时发生错误: 在处理请求头、参数或请求体中的变量占位符时失败, 错误详情: {e}"
                ) from e

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
            except StepExecutionError:
                raise
            except Exception as e:
                raise StepExecutionError(f"【HTTP请求】处理请求体时发生错误: 在构建请求数据时失败, 错误详情: {e}") from e

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
                    f"【HTTP请求】请求失败: 请求 {request_method} {request_url} 时发生网络错误, 错误详情: {e}"
                ) from e
            except httpx.HTTPStatusError as e:
                # HTTP状态错误不一定是失败, 记录响应继续处理
                response = e.response
                self.context.log(
                    f"【HTTP请求】响应状态码异常: 服务器返回状态码 {e.response.status_code}, 将继续处理响应",
                    step_no=self.step_no
                )
            except Exception as e:
                raise StepExecutionError(
                    f"【HTTP请求】请求发生未预期的错误: 请求 {request_method} {request_url} 时发生异常, 错误详情: {e}"
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
                }
            except AttributeError as e:
                raise StepExecutionError(f"【HTTP请求】响应对象格式错误: 响应对象缺少必要属性, 错误详情: {e}") from e
            except Exception as e:
                raise StepExecutionError(
                    f"【HTTP请求】处理响应时发生错误: 在提取响应状态码、头部、内容或Cookie时失败, 错误详情: {e}") from e

            try:
                response_json = response.json()
            except (ValueError, json.JSONDecodeError):
                response_json = None
            except Exception as e:
                self.context.log(f"【HTTP请求】响应JSON解析失败: {e}, 将使用文本响应", step_no=self.step_no)
                response_json = None

            try:
                extract_variables = self._extract_variables(response_json)
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
                self.context.log(error_message, step_no=self.step_no)

            try:
                validator_results = self._run_validators(response_json)
                result.assert_validators.extend(validator_results)
                failed_validators = [v for v in validator_results if not v.get("success", True)]
                if failed_validators:
                    failed_msgs = [
                        f"断言 '{v.get('name', '未命名')}': {v.get('message', '断言失败')}"
                        for v in failed_validators
                    ]
                    error_message: str = f"【断言验证】-【{len(failed_validators)}个断言未通过, 详情: {'; '.join(failed_msgs)}】"
                    self.context.log(error_message, step_no=self.step_no)
                    raise StepExecutionError(error_message)
            except StepExecutionError:
                raise
            except Exception as e:
                error_message: str = f"【断言验证】在运行断言检查时发生异常, 错误详情: {e}"
                self.context.log(error_message, step_no=self.step_no)
                raise StepExecutionError(error_message) from e
        except StepExecutionError:
            raise
        except Exception as e:
            result.success = False
            result.error = f"【断言验证】步骤执行异常: {e}"
            self.context.log(result.error, step_no=self.step_no)
            raise StepExecutionError(result.error) from e

    def _extract_variables(self, response_json: Any) -> Dict[str, Any]:
        try:
            extract_variables = self.step.get("extract_variables")
            if not extract_variables or response_json is None:
                return {}

            result = {}

            # 支持数组格式和单个对象格式
            if isinstance(extract_variables, list):
                # 数组格式：处理多个提取配置
                for ext_config in extract_variables:
                    if not isinstance(ext_config, dict):
                        continue
                    name = ext_config.get("name")
                    expr = ext_config.get("expr")
                    if not name or not expr:
                        continue
                    try:
                        extracted = self._resolve_json_path(response_json, expr)
                        result[name] = extracted
                    except StepExecutionError:
                        raise
                    except Exception as e:
                        self.context.log(f"【变量提取】失败 [{name}]: {e}", step_no=self.step_no)
                        # 继续处理其他变量, 不中断
            elif isinstance(extract_variables, dict):
                # 单个对象格式：兼容旧格式
                name = extract_variables.get("name")
                expr = extract_variables.get("expr")
                if not name or not expr:
                    raise StepExecutionError(
                        f"【变量提取】配置不完整: "
                        f"缺少变量名(name)或JSONPath表达式(expr), 当前配置: name={name}, expr={expr}"
                    )
                try:
                    extracted = self._resolve_json_path(response_json, expr)
                    result[name] = extracted
                except StepExecutionError:
                    raise
                except Exception as e:
                    raise StepExecutionError(f"【变量提取】JSONPath解析失败: {e}") from e
            else:
                raise StepExecutionError(
                    f"【变量提取】不支持的extract_variables格式: {type(extract_variables)}")

            return result
        except StepExecutionError:
            raise
        except Exception as e:
            raise StepExecutionError(f"【变量提取】提取异常: {e}") from e

    def _run_validators(self, response_json: Any) -> List[Dict[str, Any]]:
        try:
            assert_validators = self.step.get("assert_validators")
            if not assert_validators or response_json is None:
                return []

            results: List[Dict[str, Any]] = []

            # 支持数组格式和单个对象格式
            if isinstance(assert_validators, list):
                # 数组格式：处理多个断言配置
                for validator_config in assert_validators:
                    if not isinstance(validator_config, dict):
                        continue
                    expr = validator_config.get("expr")
                    operation = validator_config.get("operation")
                    except_value = validator_config.get("except_value")
                    name = validator_config.get("name", "")

                    if not expr or not operation:
                        self.context.log(f"【断言验证】配置不完整, 跳过: {validator_config}", step_no=self.step_no)
                        continue

                    try:
                        actual_value = self._resolve_json_path(response_json, expr)
                    except StepExecutionError:
                        raise
                    except Exception as exc:
                        raise StepExecutionError(f"【断言验证】JSONPath解析失败: {exc}") from exc

                    try:
                        success = ConditionStepExecutor.compare(actual_value, operation, except_value)
                    except StepExecutionError:
                        raise
                    except Exception as exc:
                        raise StepExecutionError(f"【断言验证】比较失败: {exc}") from exc
                    results.append({
                        "name": name,
                        "expr": expr,
                        "operation": operation,
                        "except_value": except_value,
                        "actual_value": actual_value,
                        "success": success,
                    })
            elif isinstance(assert_validators, dict):
                # 单个对象格式：兼容旧格式
                expr = assert_validators.get("expr")
                operation = assert_validators.get("operation")
                except_value = assert_validators.get("except_value")
                name = assert_validators.get("name", "")
                if not expr or not operation:
                    raise StepExecutionError(
                        f"【断言验证】配置不完整: "
                        f"缺少JSONPath表达式(expr)或比较操作符(operation), "
                        f"当前配置: expr={expr}, operation={operation}"
                    )
                try:
                    actual_value = self._resolve_json_path(response_json, expr)
                except StepExecutionError:
                    raise
                except Exception as e:
                    raise StepExecutionError(f"【断言验证】JSONPath解析失败: {e}") from e

                try:
                    success = ConditionStepExecutor.compare(actual_value, operation, except_value)
                except StepExecutionError:
                    raise
                except Exception as exc:
                    raise StepExecutionError(f"【断言验证】比较失败: {exc}") from exc
                results.append({
                    "name": name,
                    "expr": expr,
                    "operation": operation,
                    "except_value": except_value,
                    "actual_value": actual_value,
                    "success": success,
                })
            else:
                raise StepExecutionError(f"【断言验证】不支持的assert_validators格式: {type(assert_validators)}")

            return results
        except StepExecutionError:
            raise
        except Exception as e:
            raise StepExecutionError(f"【断言验证】执行异常: {e}") from e

    @staticmethod
    def _resolve_json_path(data: Any, expr: str) -> Any:
        try:
            if not expr or not isinstance(expr, str):
                raise StepExecutionError(
                    f"【JSONPath解析】格式错误: 表达式必须是非空字符串, 当前值: {expr} (类型: {type(expr).__name__})")

            if not expr.startswith("$."):
                raise StepExecutionError(
                    f"【JSONPath解析】格式错误: 表达式必须以 '$.' 开头, 当前表达式: '{expr}', 示例: '$.data.user.name'")

            if data is None:
                raise StepExecutionError("【JSONPath解析】响应数据为空, 无法从空数据中提取值, 请检查响应是否正常返回")

            parts = [part for part in expr[2:].split(".") if part]
            if not parts:
                raise StepExecutionError(
                    f"【JSONPath解析】路径为空, 表达式 '{expr}' 在去除 '$.' 前缀后没有有效的路径部分")

            current: Any = data
            for i, part in enumerate(parts):
                if isinstance(current, dict):
                    if part not in current:
                        current_path = '$.' + '.'.join(parts[:i + 1])
                        available_keys = list(current.keys())[:10]  # 只显示前10个键
                        keys_hint = ', '.join(available_keys) + ('...' if len(current) > 10 else '')
                        raise StepExecutionError(
                            f"【JSONPath解析】路径不存在: "
                            f"路径 '{current_path}' 中的键 '{part}' 在数据中不存在, 可用键: [{keys_hint}]"
                        )
                    current = current.get(part)
                elif isinstance(current, list):
                    try:
                        index = int(part)
                    except ValueError as e:
                        raise StepExecutionError(
                            f"【JSONPath解析】列表索引错误: 路径中的索引 '{part}' 不是有效的整数, 列表索引必须是数字"
                        ) from e
                    try:
                        current = current[index]
                    except IndexError as e:
                        current_path = '$.' + '.'.join(parts[:i + 1])
                        raise StepExecutionError(
                            f"【JSONPath解析】列表索引越界: 路径 '{current_path}' 中的索引 {part} 超出范围, "
                            f"列表长度为 {len(current)}, 有效索引范围: 0-{len(current) - 1}"
                        ) from e
                else:
                    current_path = '$.' + '.'.join(parts[:i + 1])
                    raise StepExecutionError(
                        f"【JSONPath解析】类型错误: "
                        f"路径 '{current_path}' 中的 '{part}' 无法在 {type(current).__name__} 类型上应用, "
                        f"期望字典(dict)或列表(list)类型"
                    )

            return current
        except StepExecutionError:
            raise
        except Exception as e:
            raise StepExecutionError(f"【JSONPath解析】异常: {e}") from e


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
            report_type: Optional[ReportType] = None,
            execute_environment: Optional[str] = None
    ) -> Tuple[List[StepExecutionResult], Dict[int, List[str]], Optional[str], Dict[str, Any], Dict[str, Any]]:
        """
        执行测试用例并返回：(结果列表, 日志, 报告码, 统计信息, 会话变量)

        Args:
            case: 用例信息字典
            steps: 步骤列表
            initial_variables: 初始变量
            report_type: 报告类型, 默认为 EXEC1（执行方式1）
            execute_environment: 批量执行用例时可指定统一环境
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
                # 如果没有指定report_type, 默认使用EXEC1（执行方式1）
                final_report_type = report_type if report_type is not None else ReportType.EXEC1
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
                    created_user=user_name
                )
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
                    error_message: str = f"更新测试报告失败: 报告编码={report_code}, 错误详情: {e}"
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
            root_step_no: int
    ) -> None:
        """
        汇总根步骤的所有子步骤日志`

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

        # 收集所有子步骤的编号（递归收集, 包括子步骤的子步骤）
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
            # 如果根步骤没有自己的日志, 直接使用子步骤的汇总日志
            context.logs[root_step_no] = aggregated_logs
