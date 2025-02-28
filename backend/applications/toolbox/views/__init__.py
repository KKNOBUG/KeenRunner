# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : __init__.py.py
@DateTime: 2025/2/23 12:02
"""
from fastapi import APIRouter

from .runcode_view import runcode
from .generate_view import generate

toolbox = APIRouter()

toolbox.include_router(runcode, prefix="/runcode")
toolbox.include_router(generate, prefix="/generate")
