# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : __init__.py
@DateTime: 2025/1/12 19:42
"""
from fastapi import APIRouter

from .audit_view import audit
from .file_transfer_view import file_transfer
from .menu_view import menu
from .role_view import role
from .router_view import router

router_secure = APIRouter()
menu_secure = APIRouter()
role_secure = APIRouter()
audit_secure = APIRouter()
file_secure = APIRouter()

# 安全端点(要求认证+ RBAC依赖)
router_secure.include_router(router, prefix="/router")
menu_secure.include_router(menu, prefix="/menu")
role_secure.include_router(role, prefix="/role")
audit_secure.include_router(audit, prefix="/audit")
file_secure.include_router(file_transfer, prefix="/filetransfer")
