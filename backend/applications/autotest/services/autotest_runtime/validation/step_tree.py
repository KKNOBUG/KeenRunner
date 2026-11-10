# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : step_tree.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

from typing import Any, List, Optional, Set, Tuple

from backend.applications.autotest.schemas.autotest_step_schema import AutoTestStepTreeUpdateItem


class StepTreeValidation:
    """
    步骤树结构校验：循环引用检测与子步骤挂载类型限制。

    循环检测只沿祖先链判定（每个子节点复制visited/path），兄弟分支间复用同一step_id
    不视为循环；quote_steps（引用的公共脚本）不在本校验范围。
    """

    @classmethod
    def validate_step_tree_structure(cls, steps_data: List[AutoTestStepTreeUpdateItem]) -> Tuple[bool, Optional[str]]:
        """
        校验步骤树结构：无自循环引用，且仅有「循环结构」「条件分支」类型可包含子步骤。

        递归覆盖children与branch_items.branch_children；branch_items仅允许出现在条件分支。

        :param steps_data: 根步骤列表(每项可为带children的树节点)
        :return: (True, None)表示通过；(False, str)表示失败及错误信息
        """
        from backend.enums import AutoTestStepType

        # 仅允许循环结构和条件分支包含子步骤
        allowed_children_types = {AutoTestStepType.LOOP, AutoTestStepType.IF}

        def check_step_recursive(step: AutoTestStepTreeUpdateItem, visited_ids: Set[Any], path: List[Any]) -> Tuple[bool, Optional[str]]:
            """
            递归校验单个步骤节点及其子步骤。

            visited_ids/path为当前祖先链快照（调用方对每个子节点传入副本），
            因此只拦截祖先链上的重复step_id/step_code，不拦截兄弟分支复用。

            :param step: 当前步骤节点
            :param visited_ids: 当前祖先链上已访问的step_id集合
            :param path: 当前祖先链的step_code列表
            :return: (True, None)表示通过；(False, str)表示失败及错误信息
            """
            step_id = step.step_id
            step_code = step.step_code

            # 祖先链查重：step_id优先；step_code兼容尚未分配step_id的草稿节点
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
                    return False, (
                        f"步骤(step_id={step_id}, step_code={step_code or 'N/A'}, "
                        f"step_type={step.step_type})不允许包含子步骤, 仅允许'循环结构'和'条件分支'类型的步骤包含子步骤"
                    )

                # 递归检查子步骤；副本保证循环判定仅沿各自的祖先链
                for child in step.children:
                    child_is_valid, child_error_msg = check_step_recursive(child, visited_ids.copy(), path.copy())
                    if not child_is_valid:
                        return False, child_error_msg

            # 检查条件分支的 branch_items 子步骤
            if step.branch_items:
                if step.step_type != AutoTestStepType.IF:
                    return False, (
                        f"步骤(step_id={step_id}, step_code={step_code or 'N/A'}, "
                        f"step_type={step.step_type})不允许配置 branch_items, 仅'条件分支'类型允许"
                    )
                for branch in step.branch_items:
                    branch_children = branch.branch_children if hasattr(branch, "branch_children") else (
                        branch.get("branch_children") if isinstance(branch, dict) else None)
                    for child in (branch_children or []):
                        child_is_valid, child_error_msg = check_step_recursive(child, visited_ids.copy(), path.copy())
                        if not child_is_valid:
                            return False, child_error_msg

            return True, None

        # 检查所有根步骤
        for step_data in steps_data:
            root_is_valid, root_error_msg = check_step_recursive(step_data, set(), [])
            if not root_is_valid:
                return False, root_error_msg

        return True, None
