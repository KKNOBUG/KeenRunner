# -*- coding: utf-8 -*-
"""
步骤树结构校验：自循环检测与「仅循环/条件可含子步骤」规则。
"""
from __future__ import annotations

from typing import List

from backend.applications.aotutest.schemas.autotest_step_schema import AutoTestStepTreeUpdateItem


class StepTreeValidation:
    """保存前第一步：步骤树拓扑与嵌套合法性校验。"""

    @classmethod
    def validate_step_tree_structure(cls, steps_data: List[AutoTestStepTreeUpdateItem]) -> tuple:
        """
        校验步骤树结构：无自循环引用, 且仅有「循环结构」「条件分支」类型可包含子步骤

        :param steps_data: 根步骤列表(每项可为带 children 的树节点)
        :return: (True, None) 表示通过；(False, str) 表示失败及错误信息
        """
        from backend.enums import AutoTestStepType

        # 允许有子步骤的步骤类型
        allowed_children_types = {AutoTestStepType.LOOP, AutoTestStepType.IF}

        def check_step_recursive(step: AutoTestStepTreeUpdateItem, visited_ids: set, path: list) -> tuple:
            """
            递归校验单个步骤节点及其 children：
            - 检查 step_id / step_code 自循环
            - 检查非允许类型是否包含 children

            :param step: 当前步骤节点
            :param visited_ids: 已访问 step_id 集合(用于检测自循环)
            :param path: 访问路径 step_code 列表(用于检测自循环)
            :returns: (True, None) 表示通过；(False, str) 表示失败及错误信息
            """
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
                    return False, (
                        f"步骤(step_id={step_id}, step_code={step_code or 'N/A'}, "
                        f"step_type={step.step_type})不允许包含子步骤, 仅允许'循环结构'和'条件分支'类型的步骤包含子步骤"
                    )

                # 递归检查子步骤
                for child in step.children:
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
