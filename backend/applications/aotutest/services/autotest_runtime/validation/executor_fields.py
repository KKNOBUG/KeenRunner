# -*- coding: utf-8 -*-
"""
按步骤类型校验执行器必填字段组合（第三层校验）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.applications.aotutest.schemas.autotest_step_schema import AutoTestStepTreeUpdateItem


class ExecutorFieldsValidation:
    """保存前第三层：HTTP/TCP/DB/Redis/Python 等执行器字段完整性。"""

    @classmethod
    def validate_executor_fields(
            cls,
            steps: List[AutoTestStepTreeUpdateItem],
    ) -> List[Dict[str, Any]]:
        """
        按步骤类型校验各执行器的必填字段组合（第三层校验）。

        :param steps: 根步骤列表
        :return: 错误项列表，每项含 step_code、step_name、step_type、missing（缺失字段名列表）、message
        """
        from backend.enums import AutoTestStepType, AutoTestLoopMode

        errors: List[Dict[str, Any]] = []

        def _norm_step_type(raw: Any) -> Optional[AutoTestStepType]:
            if raw is None:
                return None
            if isinstance(raw, AutoTestStepType):
                return raw
            try:
                return AutoTestStepType(str(raw).strip())
            except (ValueError, TypeError):
                return None

        def _check_step(step: AutoTestStepTreeUpdateItem) -> None:
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
                if not step.conditions:
                    missing.append("conditions")
                else:
                    cond = step.conditions
                    if not getattr(cond, "condition_expr", None):
                        missing.append("conditions.condition_expr")
                    if not getattr(cond, "condition_compare", None):
                        missing.append("conditions.condition_compare")

            elif step_type == AutoTestStepType.WAIT:
                if step.wait is None:
                    missing.append("wait")

            elif step_type == AutoTestStepType.QUOTE:
                if not step.quote_case_id:
                    missing.append("quote_case_id")

            elif step_type == AutoTestStepType.USER_VARIABLES:
                if not step.session_variables:
                    missing.append("session_variables")

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
            for quote_step in (step.quote_steps or []):
                _check_step(quote_step)

        for root_step in steps:
            _check_step(root_step)
        return errors
