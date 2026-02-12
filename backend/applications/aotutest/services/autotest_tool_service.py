# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_tool_service
@DateTime: 2026/1/17 12:20
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple, Callable

from jsonpath_ng import parse as jsonpath_parse

from backend.applications.aotutest.schemas.autotest_step_schema import AutoTestStepTreeUpdateItem
from backend.common.generate_utils import GenerateUtils


class AutoTestToolService:
    """自动化测试步骤与断言相关的工具类，不依赖实例状态，方法均为类方法或静态方法。"""

    @classmethod
    def resolve_json_path(cls, data: Any, expr: str) -> Any:
        """
        使用 JSONPath 表达式从 data 中取值，支持标准 JSONPath（如 $.data[0].id、$.list[*].name）。

        :param data: 待取值的对象（dict/list 或嵌套结构）。
        :param expr: 非空字符串，合法 JSONPath 表达式（如 $.a.b、$.data[0].id、$.items[*].id）。
        :return: 单匹配时返回该值，多匹配时返回值的列表。无匹配时抛出 ValueError。
        :raises ValueError: 表达式非法、路径无匹配或解析异常时。
        """
        expr = expr.strip()
        if not expr or not isinstance(expr, str):
            raise ValueError(f"【JSONPath解析】表达式必须是非空字符串, 当前表达式: {expr} (类型: {type(expr).__name__})")
        if not expr.startswith("$."):
            raise ValueError(f"【JSONPath解析】表达式必须以$.字符开头, 当前表达式: {expr} (示例: $.data.user.name)")
        if data is None:
            raise ValueError("【JSONPath解析】表达式执行数据源不允许为空, 请检查响应数据是否正常返回")

        try:
            json_path_expr = jsonpath_parse(expr)
        except Exception as e:
            raise ValueError(f"【JSONPath解析】表达式{expr}解析异常, 错误描述: {e} (示例: '$.list[0].id', '$.list[*].name')") from e

        json_path_matches = json_path_expr.find(data)
        if not json_path_matches:
            raise ValueError(f"【JSONPath解析】表达式{expr}在当前数据源中无任何匹配结果, 请检查路径或响应结构")

        values = [match.value for match in json_path_matches]
        return values[0] if len(values) == 1 else values

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        """
        将值标准化为便于比较的类型：数字字符串转 int/float，'true'/'false' 转 bool，其余原样返回。

        :param value: 任意值。
        :return: 标准化后的值，或原值。
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
        类型感知的相等比较：先直接比较，若不等则对两值做 _normalize_value 后再比较。

        :param actual: 实际值。
        :param expected: 期望值。
        :return: 是否相等。
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
        类型感知的大小比较：先标准化再比较；若标准化后均为数值则用数值比较，否则用字符串比较。

        :param actual: 实际值。
        :param expected: 期望值。
        :param comparator: 二元谓词 (a, b) -> bool，如 lambda x, y: x > y。
        :return: 比较结果。
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
        """
        根据操作符对实际值与期望值做断言比较，支持等于、不等于、大于、小于、包含、非空等。

        :param actual: 实际值。
        :param operation: 操作符名称（如 "等于"、"包含"、"非空"）。
        :param expected: 期望值（部分操作符可忽略）。
        :return: 断言是否通过。
        :raises ValueError: 不支持的操作符或比较过程异常。
        """
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
            "非空": lambda a, _: a is not None and a != "",
            "为空": lambda a, _: a is None or a == "",
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
        校验步骤树结构：无自循环引用，且仅有「循环结构」「条件分支」类型可包含子步骤。

        :param steps_data: 根步骤列表（每项可为带 children 的树节点）。
        :return: (True, None) 表示通过；(False, str) 表示失败及错误信息。
        """
        from backend.enums.autotest_enum import AutoTestStepType

        # 允许有子步骤的步骤类型
        allowed_children_types = {AutoTestStepType.LOOP, AutoTestStepType.IF}

        def check_step_recursive(step: AutoTestStepTreeUpdateItem, visited_ids: set, path: list) -> tuple:
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
        规范化单条步骤数据：conditions 转为 JSON 字符串、移除 case/quote_case，并递归规范化 children 与 quote_steps。

        :param step: 步骤数据字典（可含 conditions、children、quote_steps 等）。
        :return: 规范化后的新字典，不修改入参。
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
    def collect_session_variables(cls, steps_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        递归收集步骤树中所有步骤的 session_variables，合并为扁平列表（每项含 key、value、desc）。

        :param steps_list: 步骤列表，每项可含 children、quote_steps。
        :return: 合并后的变量列表。
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
    def _parse_funcname_funcargs(cls, func_string: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        从形如 "func_name(key1=val1, key2=val2)" 的字符串中解析出函数名与参数字典。

        :param func_string: 函数调用形式的字符串。
        :return: (函数名, 参数字典)，无法解析时返回 (None, None)。
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
                key, value = item.split("=")
                args_dict[str(key).strip()] = eval(value)
        return func_name.strip(), args_dict

    @classmethod
    def execute_func_string2(cls, session_variables: List[Dict[str, Any]]):
        """
        对会话变量列表中 value 为 "func_name(...)" 形式的项，调用 GenerateUtils 中同名函数并用返回值替换 value。

        :param session_variables: 变量列表，每项为含 key、value、desc 的字典。
        :raises AttributeError: 函数不存在、参数不匹配或执行失败时。
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
            func_name, func_args = cls._parse_funcname_funcargs(func_string)
            if not func_name and not func_args:
                continue
            if not hasattr(GenerateUtils, func_name):
                raise AttributeError(f"辅助函数[{func_name}]不存在, 无法替换其值")
            try:
                item["value"] = getattr(GenerateUtils, func_name)(**func_args or {})
            except TypeError as e:
                raise AttributeError(f"辅助函数[{func_name}]参数数量或类型不匹配: {e}")
            except SyntaxError as e:
                raise AttributeError(f"辅助函数[{func_name}]语法解析失败或未定义: {e}")
            except Exception as e:
                raise AttributeError(f"辅助函数[{func_name}]执行失败, 错误描述: {e}")

    @classmethod
    def execute_func_string_single(cls, content: str) -> Any:
        """
        将 content 解析为 func_name(...) 并调用 GenerateUtils 中同名方法，返回结果。
        供 resolve_placeholders 在「含括号」占位符时调用。

        :param content: 如 "generate_uuid()"、"generate_string(length=2)"。
        :return: 函数返回值。
        :raises AttributeError: 非函数形式或函数不存在/执行失败。
        """
        func_name, func_args = cls._parse_funcname_funcargs(content)
        if not func_name:
            raise AttributeError(f"占位符内容不是有效的函数调用形式: {content!r}")
        if not hasattr(GenerateUtils, func_name):
            raise AttributeError(f"辅助函数[{func_name}]不存在, 无法替换其值")
        try:
            execute_result = getattr(GenerateUtils(), func_name)(**(func_args or {}))
            return execute_result
        except TypeError as e:
            raise AttributeError(f"辅助函数[{func_name}]参数数量或类型不匹配: {e}") from e
        except SyntaxError as e:
            raise AttributeError(f"辅助函数[{func_name}]语法解析失败: {e}") from e
        except Exception as e:
            raise AttributeError(f"辅助函数[{func_name}]执行失败: {e}") from e

    _RE_PLACEHOLDER = re.compile(r"\$\{([^}]+)}")

    @classmethod
    def resolve_value_placeholders(
            cls,
            value_str: str,
            get_variable: Callable[[str], Any],
    ) -> str:
        """
        对字符串中的每个 ${...} 做一次遍历：内容为函数调用则执行并替换，否则按变量名用 get_variable 替换。
        支持混合形式如 name_${name}、${name}${age}、${name}${generate_uuid()} 等，无需先变量后函数两遍遍历。

        :param value_str: 可能包含 ${var} 或 ${func()} 的字符串。
        :param get_variable: 按变量名取值的可调用对象，未定义时应抛出 KeyError。
        :return: 替换后的字符串；变量未定义时保留原占位符。
        """
        if not isinstance(value_str, str):
            return value_str

        def replace(match: re.Match[str]) -> str:
            content = match.group(1).strip()
            if not content:
                return match.group(0)
            func_name, func_args = cls._parse_funcname_funcargs(content)
            if func_name and hasattr(GenerateUtils, func_name):
                try:
                    result = getattr(GenerateUtils, func_name)(**(func_args or {}))
                    return str(result)
                except (TypeError, SyntaxError, Exception) as e:
                    raise AttributeError(f"辅助函数[{func_name}]执行失败: {e}") from e
            try:
                resolved = get_variable(content)
                return str(resolved) if resolved is not None else ""
            except KeyError:
                return match.group(0)
            except Exception:
                return match.group(0)

        return cls._RE_PLACEHOLDER.sub(replace, value_str)
