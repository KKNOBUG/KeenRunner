# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : app_initalization.py
@DateTime: 2025/1/17 21:55
"""
import logging.config
import sys

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.types import HTTPExceptionHandler

from backend import PROJECT_CONFIG
from backend.applications.example.views.example_view import example
from backend.configure.logging_config import DEFAULT_LOGGING_CONFIG
from backend.core.exceptions.http_exceptions import (
    validation_exception_handler, http_exception_handler, app_exception_handler
)


def register_logging() -> None:
    logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)


# 注册异常处理器
def register_exceptions(app: FastAPI) -> None:
    # 注册参数验证错误处理器
    app.add_exception_handler(
        exc_class_or_status_code=RequestValidationError,
        handler=validation_exception_handler
    )
    # 验证HTTP通讯异常错误处理器
    app.add_exception_handler(
        exc_class_or_status_code=HTTPException,
        handler=http_exception_handler
    )

    app.add_exception_handler(
        exc_class_or_status_code=Exception,
        handler=app_exception_handler
    )


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
