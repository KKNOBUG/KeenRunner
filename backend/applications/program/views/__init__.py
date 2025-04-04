# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : __init__.py.py
@DateTime: 2025/3/7 12:28
"""
from fastapi import APIRouter

from .project_view import project
from .env_view import env

program = APIRouter()

program.include_router(project, prefix="/project")
program.include_router(env, prefix="/env")
