# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : variable_flow.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

from typing import Any, Dict, List, Set

from backend.applications.autotest.schemas.autotest_step_schema import (
    AutoTestStepTreeUpdateItem,
    StepVariablesBase,
)
from backend.applications.autotest.services.autotest_runtime.sandbox import UserCodeSandbox


class VariableFlowValidation:
    """
    变量流校验：汇总步骤树可产出的变量名，并检查${...}引用是否均已定义。

    覆盖children、branch_items.branch_children与quote_steps；不做定义/引用先后校验
    （全树先收集产出，再统一检查引用），即允许引用后置步骤的产出。
    """

    @classmethod
    def collect_session_variables(cls, steps: List[AutoTestStepTreeUpdateItem]) -> List[StepVariablesBase]:
        """
        递归收集步骤树中所有步骤的session_variables，合并为扁平列表。

        仅递归children与quote_steps，不进入branch_items（条件分支子步骤的变量不参与合并）；
        结果不去重，同名覆盖由调用方自行处理。

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
    def validate_variable_flow(cls, steps: List[AutoTestStepTreeUpdateItem]) -> List[Dict[str, Any]]:
        """
        校验步骤树中${var}引用是否有对应的变量产出。

        产出集合包含：循环内置变量（loop_index/loop_value/loop_key）、循环自定义变量名、
        session_variables/defined_variables/extract_variables的key、DB/Redis操作的
        variable_name及variable_name_count。全树先收集产出再检查引用，不校验先后顺序。

        边界：引用收集只递归str/dict/list/tuple，Pydantic模型子项内部字段不深入。

        :param steps: 根步骤列表
        :return: 未匹配的引用错误项列表
        """
        produced: Set[str] = set()
        # 循环结构内置产出：未自定义循环变量名时也视为已定义
        produced.update({"loop_index", "loop_value", "loop_key"})

        def _collect_produced(step: AutoTestStepTreeUpdateItem) -> None:
            """递归收集步骤树上可产出的变量名到produced（含分支子步骤与引用步骤）。"""
            # 循环结构自定义变量名同样视为产出项
            for attr in ("loop_index", "loop_key", "loop_value"):
                name = getattr(step, attr, None)
                if name:
                    produced.add(str(name))
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
            # 数据库/Redis操作自动产出variable_name及variable_name_count
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
            """
            递归收集任意值中的${...}占位符内部变量名（排除函数调用形式）。

            仅深入str/dict/list/tuple；模型对象字段不递归，故模型内部字段的占位符不参与校验。
            """
            refs: List[str] = []
            if isinstance(value, str):
                for match in UserCodeSandbox.RE_PLACEHOLDER.finditer(value):
                    inner = match.group(1).strip()
                    # 排除函数调用形式
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
            """返回该步骤中可能含${...}的字段及其值，供引用收集（值保持原类型，由收集函数递归）。"""
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
            """检查步骤字段中的${var}是否均已产出，未匹配则写入errors（含分支子步骤与引用步骤）。"""
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

        # 先全树收集产出，再全树检查引用：不校验先后顺序，引用后置步骤的产出也视为已定义
        for root_step in steps:
            _collect_produced(root_step)
        for root_step in steps:
            _check_refs(root_step)
        return errors
