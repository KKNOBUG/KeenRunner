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
from typing import Any, Dict, List, Optional, Tuple

from backend.applications.aotutest.schemas.autotest_step_schema import AutoTestStepTreeUpdateItem
from backend.common.generate_utils import GenerateUtils


class AutoTestToolService:

    def __init__(self):
        ...

    @classmethod
    def resolve_json_path(cls, data: Any, expr: str) -> Any:
        try:
            if not expr or not isinstance(expr, str):
                raise ValueError(
                    f"【JSONPath解析】格式错误: 表达式必须是非空字符串, 当前值: {expr} (类型: {type(expr).__name__})")

            if not expr.startswith("$."):
                raise ValueError(
                    f"【JSONPath解析】格式错误: 表达式必须以 '$.' 开头, 当前表达式: '{expr}', 示例: '$.data.user.name'")

            if data is None:
                raise ValueError("【JSONPath解析】响应数据为空, 无法从空数据中提取值, 请检查响应是否正常返回")

            parts = [part for part in expr[2:].split(".") if part]
            if not parts:
                raise ValueError(
                    f"【JSONPath解析】路径为空, 表达式 '{expr}' 在去除 '$.' 前缀后没有有效的路径部分")

            current: Any = data
            for i, part in enumerate(parts):
                if isinstance(current, dict):
                    if part not in current:
                        current_path = '$.' + '.'.join(parts[:i + 1])
                        available_keys = list(current.keys())[:10]  # 只显示前10个键
                        keys_hint = ', '.join(available_keys) + ('...' if len(current) > 10 else '')
                        raise ValueError(
                            f"【JSONPath解析】路径不存在: "
                            f"路径 '{current_path}' 中的键 '{part}' 在数据中不存在, 可用键: [{keys_hint}]"
                        )
                    current = current.get(part)
                elif isinstance(current, list):
                    try:
                        index = int(part)
                    except ValueError as e:
                        raise ValueError(
                            f"【JSONPath解析】列表索引错误: 路径中的索引 '{part}' 不是有效的整数, 列表索引必须是数字"
                        ) from e
                    try:
                        current = current[index]
                    except IndexError as e:
                        current_path = '$.' + '.'.join(parts[:i + 1])
                        raise ValueError(
                            f"【JSONPath解析】列表索引越界: 路径 '{current_path}' 中的索引 {part} 超出范围, "
                            f"列表长度为 {len(current)}, 有效索引范围: 0-{len(current) - 1}"
                        ) from e
                else:
                    current_path = '$.' + '.'.join(parts[:i + 1])
                    raise ValueError(
                        f"【JSONPath解析】类型错误: "
                        f"路径 '{current_path}' 中的 '{part}' 无法在 {type(current).__name__} 类型上应用, "
                        f"期望字典(dict)或列表(list)类型"
                    )

            return current
        except Exception as e:
            raise ValueError(f"【JSONPath解析】异常: {e}") from e

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
        校验步骤树结构合法性

        Args:
            steps_data: 步骤树数据

        Returns:
            tuple[bool, Optional[str]]: (是否合法, 错误信息)
        """
        from backend.applications.aotutest.models.autotest_model import AutoTestStepType

        # 允许有子步骤的步骤类型
        allowed_children_types = {AutoTestStepType.LOOP, AutoTestStepType.IF}

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
    def collect_session_variables(cls, steps_list: List[Dict[str, Any]]) -> Dict[str, Any]:
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
            variables.update(cls.collect_session_variables(children))
            variables.update(cls.collect_session_variables(quote_steps))
        return variables

    @classmethod
    def _parse_funcname_funcargs(cls, func_string: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        if not isinstance(func_string, str):
            return None, None
        if not func_string.endswith(")") or func_string.find("(") == -1:
            return None, None
        func_name, func_args = func_string.split("(", 1)
        func_args: str = func_args.rstrip(")")
        args_dict: Dict[str, Any] = {}
        if func_args.strip():
            args_ast = ast.parse(f"dict({func_args})", mode="eval")
            args_dict = ast.literal_eval(args_ast)
        return func_name.strip(), args_dict

    @classmethod
    def execute_func_string(cls, session_variables: Dict[str, Any]):
        for key, func_string in session_variables.items():
            func_name, func_args = cls._parse_funcname_funcargs(func_string)
            if not func_name and not func_args:
                continue
            if not hasattr(GenerateUtils, func_name):
                raise AttributeError(f"辅助函数[{func_name}]不存在, 无法替换其值")
            try:
                session_variables[key] = getattr(GenerateUtils, func_name)(**func_args or {})
            except TypeError as e:
                raise AttributeError(f"辅助函数[{func_name}]参数数量或类型不匹配: {e}")
            except SyntaxError as e:
                raise AttributeError(f"辅助函数[{func_name}]语法解析失败或未定义: {e}")
            except Exception as e:
                raise AttributeError(f"辅助函数[{func_name}]执行失败, 错误描述: {e}")
