# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, Optional

from backend.applications.aotutest.services.autotest_data_source_parser import normalize_dataset_record


class DatasetLoader:
    """用例步骤数据源场景加载与结构规范化。"""

    @classmethod
    def _acquire_dataset_payload(cls, step_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        将数据源单行场景dict规范为步骤内使用的分区结构。

        :param step_data: 原始场景dict
        :return: 键为head、body、assert_head、assert_body的字典
        """
        return normalize_dataset_record(step_data)

    @staticmethod
    def has_dataset_payload(step_struct: Optional[Dict[str, Any]]) -> bool:
        """
        判断步骤是否具备数据驱动所需的head/body/断言配置。

        :param step_struct: _acquire_dataset_payload的返回值
        :return: 任一块非空则为True
        """
        if not isinstance(step_struct, dict):
            return False
        return bool(
            step_struct.get("head")
            or step_struct.get("body")
            or step_struct.get("assert_head")
            or step_struct.get("assert_body")
        )

    @classmethod
    async def load_dataset_for_request_step(
            cls,
            *,
            case_id: int,
            step_code: Optional[str],
            dataset_name: Optional[str],
            executing_quote_case_id: Optional[int],
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        按dataset_name与用例步骤标识加载数据源场景，引用公共脚本时不加载。

        :param case_id: 用例ID
        :param step_code: 步骤标识
        :param dataset_name: 数据集名称
        :param executing_quote_case_id: 非空表示处于引用公共脚本链，此时不加载数据源
        :return: _acquire_dataset_payload结构；不满足加载条件或查无数据时返回None
        """
        if not (dataset_name and step_code and not executing_quote_case_id):
            return None
        from backend.applications.aotutest.services.autotest_data_source_crud import AutoTestDataSourceCrud

        step_data = await AutoTestDataSourceCrud().get_dataset_scenario(
            case_id=case_id,
            step_code=step_code,
            dataset_name=dataset_name,
            state__not=1
        )
        if not isinstance(step_data, dict):
            return None
        return cls._acquire_dataset_payload(step_data)
