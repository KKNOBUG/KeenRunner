# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : app_initialization.py
@DateTime: 2025/1/17 21:55
"""
import logging.config
import sys
from typing import Dict, Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from tortoise.contrib.fastapi import register_tortoise

from backend import PROJECT_CONFIG
from backend.applications.example.views.example_view import example
from backend.applications.base.views.token_view import base
from backend.applications.users.views.users import user
from backend.configure.logging_config import DEFAULT_LOGGING_CONFIG
from backend.core.exceptions.http_exceptions import (
    validation_exception_handler, http_exception_handler, app_exception_handler
)


def register_logging() -> None:
    logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)


def register_database(app: FastAPI):
    config: Dict[str, Any] = {
        "connections": PROJECT_CONFIG.DATABASE_CONNECTIONS,
        "apps": {
            "models": {
                "models": PROJECT_CONFIG.APPLICATIONS_MODELS,
                "default_connection": "default"
            }
        },
        "use_tz": False,
        "timezone": "Asia/Shanghai",
    }
    register_tortoise(
        app=app,
        config=config,
        generate_schemas=False,
        add_exception_handlers=PROJECT_CONFIG.SERVER_DEBUG,
    )


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


def register_middlewares(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=PROJECT_CONFIG.CORS_ORIGINS,
        allow_credentials=PROJECT_CONFIG.CORS_ALLOW_CREDENTIALS,
        allow_methods=PROJECT_CONFIG.CORS_ALLOW_METHODS,
        allow_headers=PROJECT_CONFIG.CORS_ALLOW_HEADERS,
        expose_headers=PROJECT_CONFIG.CORS_EXPOSE_METHODS,
        max_age=PROJECT_CONFIG.CORS_MAX_AGE,
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
    app.include_router(router=base, prefix="/base", tags=["基础服务"])
    app.include_router(router=user, prefix="/user", tags=["用户服务"])
