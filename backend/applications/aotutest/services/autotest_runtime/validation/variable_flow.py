# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : variable_flow.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

from typing import Any, Dict, List, Set

from backend.applications.aotutest.schemas.autotest_step_schema import (
    AutoTestStepTreeUpdateItem,
    StepVariablesBase,
)
from backend.applications.aotutest.services.autotest_runtime.sandbox import RE_PLACEHOLDER


class VariableFlowValidation:
    @classmethod
    def collect_session_variables(cls, steps: List[AutoTestStepTreeUpdateItem]) -> List[StepVariablesBase]:
        """
        递归收集步骤树中所有步骤的session_variables，合并为扁平列表。

        :param steps: 根步骤或子步骤列表
        :return: 合并后的StepVariablesBase列表（不去重）
        """
        variables: List[StepVariablesBase] = []
        if not steps:
            return variables
        for step in steps:
            variables.extend(step.session_variables or [])
            variables.extend(cls.collect_session_variables(step.children or []))
            variables.extend(cls.collect_session_variables(step.quote_steps or []))
        return variables

    @classmethod
    def validate_variable_flow(
            cls,
            steps: List[AutoTestStepTreeUpdateItem],
    ) -> List[Dict[str, Any]]:
        """
        校验步骤树中${var}引用是否有对应的变量产出（第四层校验）。

        收集所有变量产出源（session_variables、defined_variables、extract_variables、
        数据库/Redis操作产出的variable_name及variable_name_count、
        循环注入的loop_index/loop_value/loop_key），再遍历所有字符串值中的${...}引用，
        检查是否存在未匹配的引用。

        :param steps: 根步骤列表
        :return: 未匹配的引用错误项列表
        """
        produced: Set[str] = set()
        # 引擎内置循环变量
        produced.update({"loop_index", "loop_value", "loop_key"})

        def _collect_produced(step: AutoTestStepTreeUpdateItem) -> None:
            """递归收集步骤树上可产出的变量名到produced。"""
            for var in (step.session_variables or []):
                key = getattr(var, "key", None) or (var.get("key") if isinstance(var, dict) else None)
                if key:
                    produced.add(str(key))
            for var in (step.defined_variables or []):
                key = getattr(var, "key", None) or (var.get("key") if isinstance(var, dict) else None)
                if key:
                    produced.add(str(key))
            for ext in (step.extract_variables or []):
                name = getattr(ext, "name", None) or (ext.get("name") if isinstance(ext, dict) else None)
                if name:
                    produced.add(str(name))
            # 数据库/Redis 操作自动产出 {variable_name} 和 {variable_name}_count
            for op in (step.database_operates or []):
                vn = getattr(op, "variable_name", None) or (op.get("variable_name") if isinstance(op, dict) else None)
                if vn:
                    produced.add(str(vn))
                    produced.add(f"{vn}_count")
            for op in (step.redis_operates or []):
                vn = getattr(op, "variable_name", None) or (op.get("variable_name") if isinstance(op, dict) else None)
                if vn:
                    produced.add(str(vn))
                    produced.add(f"{vn}_count")
            for child in (step.children or []):
                _collect_produced(child)
            if step.branch_items:
                for branch in step.branch_items:
                    branch_children = branch.branch_children if hasattr(branch, "branch_children") else (
                        branch.get("branch_children") if isinstance(branch, dict) else None)
                    for child in (branch_children or []):
                        _collect_produced(child)
            for quote_step in (step.quote_steps or []):
                _collect_produced(quote_step)

        def _collect_refs_in_value(value: Any) -> List[str]:
            """递归收集任意值中的${...}占位符内部变量名（排除函数调用形式）。"""
            refs: List[str] = []
            if isinstance(value, str):
                for match in RE_PLACEHOLDER.finditer(value):
                    inner = match.group(1).strip()
                    # 排除函数调用形式，如 generate_phone()
                    if "(" in inner and inner.endswith(")"):
                        continue
                    refs.append(inner)
            elif isinstance(value, dict):
                for v in value.values():
                    refs.extend(_collect_refs_in_value(v))
            elif isinstance(value, (list, tuple)):
                for item in value:
                    refs.extend(_collect_refs_in_value(item))
            return refs

        def _step_ref_fields(step: AutoTestStepTreeUpdateItem) -> Dict[str, Any]:
            """返回该步骤中可能含${...}的字段及其值，供引用收集。"""
            fields: Dict[str, Any] = {}
            for attr in (
                    "request_url", "request_port", "request_text", "request_body",
                    "request_header", "request_params", "request_form_data",
                    "request_form_urlencoded", "request_form_file",
                    "code", "loop_iterable", "loop_maximums", "wait",
            ):
                val = getattr(step, attr, None)
                if val is not None:
                    fields[attr] = val
            if step.loop_conditions is not None:
                fields["loop_conditions"] = step.loop_conditions
            if step.branch_items:
                for bi, branch in enumerate(step.branch_items):
                    cond = branch.branch_conditions if hasattr(branch, "branch_conditions") else (
                        branch.get("branch_conditions") if isinstance(branch, dict) else None)
                    if cond is not None:
                        fields[f"branch_items[{bi}].branch_conditions"] = cond
            if step.session_variables:
                fields["session_variables"] = step.session_variables
            if step.defined_variables:
                fields["defined_variables"] = step.defined_variables
            if step.extract_variables:
                fields["extract_variables"] = step.extract_variables
            if step.assert_validators:
                fields["assert_validators"] = step.assert_validators
            if step.database_operates:
                fields["database_operates"] = step.database_operates
            if step.redis_operates:
                fields["redis_operates"] = step.redis_operates
            return fields

        errors: List[Dict[str, Any]] = []

        def _check_refs(step: AutoTestStepTreeUpdateItem) -> None:
            """检查步骤字段中的${var}是否均已产出，未匹配则写入errors。"""
            fields = _step_ref_fields(step)
            for field_name, field_value in fields.items():
                refs = _collect_refs_in_value(field_value)
                for ref_name in refs:
                    if ref_name not in produced:
                        errors.append({
                            "step_code": step.step_code,
                            "step_name": step.step_name,
                            "step_type": str(step.step_type),
                            "field": field_name,
                            "variable": ref_name,
                            "message": (
                                f"步骤({step.step_code or step.step_name or 'N/A'})"
                                f"字段[{field_name}]引用了变量({ref_name}), "
                                f"但该变量未在任何前置步骤或本步骤中定义"
                            ),
                        })
            for child in (step.children or []):
                _check_refs(child)
            if step.branch_items:
                for branch in step.branch_items:
                    branch_children = branch.branch_children if hasattr(branch, "branch_children") else (
                        branch.get("branch_children") if isinstance(branch, dict) else None)
                    for child in (branch_children or []):
                        _check_refs(child)
            for quote_step in (step.quote_steps or []):
                _check_refs(quote_step)

        # 先收集全部产出
        for root_step in steps:
            _collect_produced(root_step)
        # 再检查全部引用（产出在前，引用在后，允许后置引用前置产出）
        for root_step in steps:
            _check_refs(root_step)
        return errors
