# -*- coding: utf-8 -*-
"""
提取与断言领域：Extractors 注册表、批量管线与操作符比较。
"""
from backend.applications.aotutest.services.autotest_runtime.exchange.extractors import Extractors, EXTRACTORS
from backend.applications.aotutest.services.autotest_runtime.exchange.extract_pipeline import ExtractPipeline
from backend.applications.aotutest.services.autotest_runtime.exchange.assert_pipeline import AssertPipeline
from backend.applications.aotutest.services.autotest_runtime.exchange.assert_compare import AssertionCompare
from backend.applications.aotutest.services.autotest_runtime.exchange.pipeline import ExtractAssertPipeline

__all__ = [
    "Extractors",
    "EXTRACTORS",
    "ExtractPipeline",
    "AssertPipeline",
    "AssertionCompare",
    "ExtractAssertPipeline",
]
