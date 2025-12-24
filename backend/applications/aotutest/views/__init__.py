# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : __init__.py
@DateTime: 2025/11/9 11:58
"""
from fastapi import APIRouter

from .autotest_case_view import autotest_case
from .autotest_step_view import autotest_step
from .autotest_report_view import autotest_report
from .autotest_detail_view import autotest_detail

autotest = APIRouter()

autotest.include_router(autotest_case, prefix="/case", tags=["用例相关"])
autotest.include_router(autotest_step, prefix="/step", tags=["步骤相关"])
autotest.include_router(autotest_report, prefix="/report", tags=["报告相关"])
autotest.include_router(autotest_detail, prefix="/detail", tags=["明细相关"])
