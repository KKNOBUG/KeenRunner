# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : backend_main.py
@DateTime: 2025/1/12 19:41
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from tortoise import Tortoise
from tortoise.exceptions import DBConnectionError

from backend.core.initializations import (
    register_database,
    register_exceptions,
    register_middlewares,
    register_routers,
    init_database_table,
)
from backend.core.initializations.permission_contract import bind_route_contracts, validate_route_contracts
from backend.core.responses import SuccessResponse

try:
    from backend.configure import LOGGER, PROJECT_CONFIG
except ImportError as e:
    from backend.core.exceptions import NotImplementedException

    raise NotImplementedException(message="导入依赖配置失败,请检查 configure.project_config.py 文件") from e


@asynccontextmanager
async def lifespan(app: FastAPI):
    if PROJECT_CONFIG.AUTH_TEMPORARY_TOKEN:
        LOGGER.warning("[安全] 已启用开发联通阶段临时令牌(AUTH_TEMPORARY_TOKEN), 生产环境请置空禁用;")
    # 路由已全部注册，启动时统一绑定契约并自检；问题只告警不阻断启动
    bind_route_contracts(app)
    validate_route_contracts(app)
    try:
        await register_database(app)
    except DBConnectionError as e:
        raise RuntimeError(f"数据库连接失败, 请检查主机地址是否可达: {e}") from e
    await init_database_table(app)

    yield

    await Tortoise.close_connections()


app = FastAPI(
    docs_url=None,
    title=PROJECT_CONFIG.APP_TITLE,
    description=PROJECT_CONFIG.APP_DESCRIPTION,
    version=PROJECT_CONFIG.APP_VERSION,
    redoc_url=PROJECT_CONFIG.APP_REDOC_URL,
    openapi_url=PROJECT_CONFIG.APP_OPENAPI_URL,
    debug=PROJECT_CONFIG.SERVER_DEBUG,
    lifespan=lifespan,
)

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
        # reload=PROJECT_CONFIG.SERVER_DEBUG,
        # reload_delay=PROJECT_CONFIG.SERVER_DELAY,
        log_config=None,
        log_level=None,
    )

    # 记录依赖：pip list --format=freeze > requirements.txt
    # Redis停止：终端执行 sudo lsof -i:6379 | grep -v PID | awk '{print $2}' | xargs sudo kill -9
    # Redis停止：终端执行 sudo lsof -i:6379 | grep -v PID | awk '{print $2}' | xargs sudo kill -9 2>/dev/null
    # Redis启动：终端执行 /usr/local/bin/redis-server
    # redis配置文件：/usr/local/etc/redis-6.2.9/redis.conf
    # redis持久文件：/usr/local/etc/redis-6.2.9/dump
    # echo "alias redis-server='/usr/local/bin/redis-server /usr/local/etc/redis-6.2.9/redis.conf'" >> ~/.zshrc
    # source ~/.zshrc
    # redis-server

    # MacOS: gunicorn -c backend/gunicorn.conf.py backend.backend_main:app
    # MacOS: OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES backend/.venv/bin/gunicorn -c backend/gunicorn.conf.py backend.backend_main:app
