# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : app_initalization.py
@DateTime: 2025/1/17 21:55
"""
import sys

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from backend import PROJECT_CONFIG
from backend.applications.example.views.example_view import example


def register_routers(app: FastAPI) -> None:
    # 挂载静态文件
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.openapi_version = PROJECT_CONFIG.APP_OPENAPI_VERSION
    static_modules = sys.modules["fastapi.openapi.docs"].get_swagger_ui_html.__kwdefaults__
    static_modules["swagger_js_url"] = PROJECT_CONFIG.APP_OPENAPI_JS_URL
    static_modules["swagger_css_url"] = PROJECT_CONFIG.APP_OPENAPI_CSS_URL
    static_modules["swagger_favicon_url"] = PROJECT_CONFIG.APP_OPENAPI_FAVICON_URL
    # 挂在路由蓝图
    app.include_router(router=example, prefix="/example", tags=["示例"])
