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
from .auth_view import auth_public, auth_secure
from .menu_view import menu
from .role_view import role
from .audit_view import audit
from .file_transfer_view import file_transfer

base_public = APIRouter()
base_secure = APIRouter()

# 公共端点(无全局认证/ RBAC依赖)
base_public.include_router(auth_public, prefix="/auth")

# 安全端点(要求认证+ RBAC依赖)
base_secure.include_router(router, prefix="/router")
base_secure.include_router(auth_secure, prefix="/auth")
base_secure.include_router(menu, prefix="/menu")
base_secure.include_router(role, prefix="/role")
base_secure.include_router(audit, prefix="/audit")
base_secure.include_router(file_transfer, prefix="/filetransfer")
