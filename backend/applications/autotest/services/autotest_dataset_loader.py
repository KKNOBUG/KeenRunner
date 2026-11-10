# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_dataset_loader.py
@DateTime: 2026/8/17

用例步骤数据源加载器：按用例/步骤/数据集名称取出单行数据源场景，并规范为步骤内使用的分区结构。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from backend.applications.autotest.services.autotest_data_source_parser import DataSourceMatrixParser


class DatasetLoader:
    """
    用例步骤的数据源场景加载：按用例+步骤+数据集名称取出单行场景并规范为分区结构。

    由请求类步骤在执行/调试时调用；引用公共脚本链不加载数据源。
    """

    @classmethod
    def _acquire_dataset_payload(cls, step_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        将数据源单行场景dict规范为步骤内使用的分区结构。

        委托DataSourceMatrixParser统一矩阵清洗口径，保证加载与保存两侧结构一致。

        :param step_data: 原始场景dict
        :return: 键为head、body、assert_head、assert_body的字典
        """
        return DataSourceMatrixParser.normalize_dataset_record(step_data)

    @staticmethod
    def has_dataset_payload(step_struct: Optional[Dict[str, Any]]) -> bool:
        """
        判断步骤是否具备数据驱动所需的head/body/断言配置。

        仅判断四块是否存在非空内容，不校验内部格式。

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
        根据dataset_name与用例步骤标识加载数据源场景，引用公共脚本时不加载。

        加载条件：dataset_name与step_code均非空，且不处于引用公共脚本链；
        查询过滤软删记录（state=1）；查无记录或返回非dict时返回None。

        :param case_id: 用例ID
        :param step_code: 步骤标识
        :param dataset_name: 数据集名称
        :param executing_quote_case_id: 非空表示处于引用公共脚本链，此时不加载数据源
        :return: _acquire_dataset_payload结构；不满足加载条件或查无数据时返回None
        """
        if not (dataset_name and step_code and not executing_quote_case_id):
            return None
        # 局部导入避免与数据源Crud形成模块级循环依赖
        from backend.applications.autotest.services.autotest_data_source_crud import AutoTestDataSourceCrud

        step_data = await AutoTestDataSourceCrud().get_dataset_scenario(
            case_id=case_id,
            step_code=step_code,
            dataset_name=dataset_name,
            state__not=1
        )
        if not isinstance(step_data, dict):
            return None
        return cls._acquire_dataset_payload(step_data)
