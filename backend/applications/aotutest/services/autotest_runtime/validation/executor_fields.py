# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : executor_fields.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.applications.aotutest.schemas.autotest_step_schema import AutoTestStepTreeUpdateItem


class ExecutorFieldsValidation:

    @classmethod
    def validate_executor_fields(cls, steps: List[AutoTestStepTreeUpdateItem]) -> List[Dict[str, Any]]:
        """
        根据步骤类型校验各执行器的必填字段组合（第三层校验）。

        :param steps: 根步骤列表
        :return: 错误项列表，每项含step_code、step_name、step_type、missing（缺失字段名列表）、message
        """
        from backend.enums import AutoTestStepType, AutoTestLoopMode

        errors: List[Dict[str, Any]] = []

        def _norm_step_type(raw: Any) -> Optional[AutoTestStepType]:
            """将原始step_type规范为枚举；非法则返回None。"""
            if raw is None:
                return None
            if isinstance(raw, AutoTestStepType):
                return raw
            try:
                return AutoTestStepType(str(raw).strip())
            except (ValueError, TypeError):
                return None

        def _check_step(step: AutoTestStepTreeUpdateItem) -> None:
            """根据步骤类型校验必填字段，缺失则写入errors。"""
            step_type = _norm_step_type(step.step_type)
            step_code = step.step_code
            step_name = step.step_name
            missing: List[str] = []

            if step_type is None:
                errors.append({
                    "step_code": step_code,
                    "step_name": step_name,
                    "step_type": str(step.step_type),
                    "missing": [],
                    "message": f"步骤类型未定义或不合法: {step.step_type!r}",
                })
                return

            if step_type == AutoTestStepType.HTTP:
                if not step.request_url:
                    missing.append("request_url")
                if not step.request_method:
                    missing.append("request_method")
                if not step.request_project_id:
                    missing.append("request_project_id")
                if not step.request_config_name:
                    missing.append("request_config_name")

            elif step_type == AutoTestStepType.TCP:
                if not step.request_url:
                    missing.append("request_url")
                if not step.request_port:
                    missing.append("request_port")
                if not step.request_project_id:
                    missing.append("request_project_id")
                if not step.request_config_name:
                    missing.append("request_config_name")
                if not (step.request_text or step.request_body):
                    missing.append("request_text|request_body")

            elif step_type == AutoTestStepType.DATABASE:
                if not step.database_operates:
                    missing.append("database_operates")
                else:
                    for idx, op in enumerate(step.database_operates):
                        op_label = f"database_operates[{idx}]"
                        if not getattr(op, "expr", None):
                            missing.append(f"{op_label}.expr")
                        if not getattr(op, "variable_name", None):
                            missing.append(f"{op_label}.variable_name")
                        if not getattr(op, "config_name", None):
                            missing.append(f"{op_label}.config_name")
                        if not getattr(op, "database_name", None):
                            missing.append(f"{op_label}.database_name")
                        if not getattr(op, "project_name", None) and not getattr(op, "project_id", None):
                            missing.append(f"{op_label}.project_name|project_id")

            elif step_type == AutoTestStepType.REDIS:
                if not step.redis_operates:
                    missing.append("redis_operates")
                else:
                    for idx, op in enumerate(step.redis_operates):
                        op_label = f"redis_operates[{idx}]"
                        if not getattr(op, "expr", None):
                            missing.append(f"{op_label}.expr")
                        if not getattr(op, "variable_name", None):
                            missing.append(f"{op_label}.variable_name")
                        if not getattr(op, "config_name", None):
                            missing.append(f"{op_label}.config_name")
                        if not getattr(op, "database_name", None):
                            missing.append(f"{op_label}.database_name")
                        if not getattr(op, "project_name", None) and not getattr(op, "project_id", None):
                            missing.append(f"{op_label}.project_name|project_id")

            elif step_type == AutoTestStepType.PYTHON:
                if not step.code:
                    missing.append("code")

            elif step_type == AutoTestStepType.LOOP:
                if not step.loop_mode:
                    missing.append("loop_mode")
                if not step.loop_on_error:
                    missing.append("loop_on_error")
                if step.loop_mode:
                    raw_mode = step.loop_mode
                    if isinstance(raw_mode, AutoTestLoopMode):
                        mode = raw_mode
                    else:
                        try:
                            mode = AutoTestLoopMode(str(raw_mode).strip())
                        except (ValueError, TypeError):
                            missing.append(f"loop_mode(无效值: {raw_mode!r})")
                            mode = None
                    if mode is not None:
                        if mode == AutoTestLoopMode.COUNT and not step.loop_maximums:
                            missing.append("loop_maximums")
                        elif mode in (AutoTestLoopMode.LIST, AutoTestLoopMode.DICT) and not step.loop_iterable:
                            missing.append("loop_iterable")
                        elif mode == AutoTestLoopMode.CONDITION and not step.conditions:
                            missing.append("conditions")

            elif step_type == AutoTestStepType.IF:
                if not step.branch_items:
                    missing.append("branch_items")
                else:
                    for bi, branch in enumerate(step.branch_items):
                        bt = branch.branch_type if hasattr(branch, "branch_type") else branch.get("branch_type")
                        if bt in ("if", "elif"):
                            cond = branch.branch_conditions if hasattr(branch, "branch_conditions") else branch.get("branch_conditions")
                            if not cond:
                                missing.append(f"branch_items[{bi}].branch_conditions")
                            else:
                                expr = cond.condition_expr if hasattr(cond, "condition_expr") else cond.get("condition_expr")
                                compare = cond.condition_compare if hasattr(cond, "condition_compare") else cond.get("condition_compare")
                                if not expr:
                                    missing.append(f"branch_items[{bi}].branch_conditions.condition_expr")
                                if not compare:
                                    missing.append(f"branch_items[{bi}].branch_conditions.condition_compare")

            elif step_type == AutoTestStepType.WAIT:
                if step.wait is None:
                    missing.append("wait")

            elif step_type == AutoTestStepType.QUOTE:
                if not step.quote_case_id:
                    missing.append("quote_case_id")

            elif step_type == AutoTestStepType.USER_VARIABLES:
                if not step.session_variables:
                    missing.append("session_variables")

            elif step_type == AutoTestStepType.ASSERT:
                if not step.assert_validators:
                    missing.append("assert_validators")
                else:
                    for idx, item in enumerate(step.assert_validators):
                        op_label = f"assert_validators[{idx}]"
                        if not getattr(item, "name", None):
                            missing.append(f"{op_label}.name")
                        if not getattr(item, "source", None):
                            missing.append(f"{op_label}.source")
                        if not getattr(item, "expr", None):
                            missing.append(f"{op_label}.expr")
                        if not getattr(item, "operation", None):
                            missing.append(f"{op_label}.operation")

            if missing:
                errors.append({
                    "step_code": step_code,
                    "step_name": step_name,
                    "step_type": step_type.value,
                    "missing": missing,
                    "message": f"步骤({step_code or step_name or 'N/A'})缺少必填字段: {', '.join(missing)}",
                })

            for child in (step.children or []):
                _check_step(child)
            if step.branch_items:
                for branch in step.branch_items:
                    branch_children = branch.branch_children if hasattr(branch, "branch_children") else branch.get("branch_children")
                    for child in (branch_children or []):
                        _check_step(child)
            for quote_step in (step.quote_steps or []):
                _check_step(quote_step)

        for root_step in steps:
            _check_step(root_step)
        return errors
