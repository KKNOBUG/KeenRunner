# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : backend_main.py
@DateTime: 2025/1/12 19:41
"""
import sys

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from backend.core.response.base_response import SuccessResponse

try:
    from backend.core import PROJECT_CONFIG
except ImportError as e:
    from backend.core.exceptions.base_exceptions import NotImplementedException

    raise NotImplementedException(message="导入依赖配置失败,请检查 configure.project_config.py 文件")

app = FastAPI(
    title=PROJECT_CONFIG.APP_TITLE,
    description=PROJECT_CONFIG.APP_DESCRIPTION,
    version=PROJECT_CONFIG.APP_VERSION,
    docs_url=PROJECT_CONFIG.APP_DOCS_URL,
    redoc_url=PROJECT_CONFIG.APP_REDOC_URL,
    openapi_url=PROJECT_CONFIG.APP_OPENAPI_URL,
    debug=PROJECT_CONFIG.SERVER_DEBUG,

)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")
static_modules = sys.modules["fastapi.openapi.docs"].get_swagger_ui_html.__kwdefaults__
static_modules["swagger_js_url"] = PROJECT_CONFIG.APP_OPENAPI_JS_URL
static_modules["swagger_css_url"] = PROJECT_CONFIG.APP_OPENAPI_CSS_URL
static_modules["swagger_favicon_url"] = PROJECT_CONFIG.APP_OPENAPI_FAVICON_URL


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
        # log_config=None,
    )
