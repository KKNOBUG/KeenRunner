# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : backend_main.py
@DateTime: 2025/1/12 19:41
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute
from tortoise import Tortoise

from backend.core.initalization.app_initialization import (
    register_logging, register_exceptions, register_routers, register_database, register_middlewares
)
from backend.core.initalization.data_initialization import init_database_table
from backend.core.response.http_response import SuccessResponse

try:
    from backend import PROJECT_CONFIG, GLOBAL_CONFIG, LOGGER
except ImportError as e:
    from backend.core.exceptions.base_exceptions import NotImplementedException

    raise NotImplementedException(message="导入依赖配置失败,请检查 configure.project_config.py 文件")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await register_database(app)
    await init_database_table(app)

    for route in app.routes:
        if isinstance(route, APIRoute):
            GLOBAL_CONFIG.ROUTER_SUMMARY[route.path] = route.summary
            GLOBAL_CONFIG.ROUTER_TAGS[route.path] = route.tags

    yield

    await Tortoise.close_connections()


app = FastAPI(
    title=PROJECT_CONFIG.APP_TITLE,
    description=PROJECT_CONFIG.APP_DESCRIPTION,
    version=PROJECT_CONFIG.APP_VERSION,
    docs_url=PROJECT_CONFIG.APP_DOCS_URL,
    redoc_url=PROJECT_CONFIG.APP_REDOC_URL,
    openapi_url=PROJECT_CONFIG.APP_OPENAPI_URL,
    debug=PROJECT_CONFIG.SERVER_DEBUG,
    lifespan=lifespan,
)

logger = register_logging()
register_exceptions(app)
register_middlewares(app)
register_routers(app)


@app.get("/")
async def root():
    return SuccessResponse(message="FastAPI Started Successfully!")


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        app=PROJECT_CONFIG.SERVER_APP,
        host=PROJECT_CONFIG.SERVER_HOST,
        port=PROJECT_CONFIG.SERVER_PORT,
        reload=PROJECT_CONFIG.SERVER_DEBUG,
        reload_delay=PROJECT_CONFIG.SERVER_DELAY,
        log_config=None,
    )

    # 记录依赖：pip list --format=freeze > requirements.txt
