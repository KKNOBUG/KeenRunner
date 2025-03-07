# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : __init__.py.py
@DateTime: 2025/1/12 19:42
"""
from fastapi import APIRouter

from .router_view import router
from .auth_view import auth
from .menu_view import menu
from .role_view import role
from .audit_view import audit

base = APIRouter()

base.include_router(router, prefix="/router")
base.include_router(auth, prefix="/auth")
base.include_router(menu, prefix="/menu")
base.include_router(role, prefix="/role")
base.include_router(audit, prefix="/audit")
