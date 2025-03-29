# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : __init__.py.py
@DateTime: 2025/3/28 15:10
"""
from fastapi import APIRouter

from .api_testcase_view import api_testcase

testcase = APIRouter()

testcase.include_router(api_testcase, prefix="/api")
