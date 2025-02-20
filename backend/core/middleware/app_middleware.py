# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : app_middleware.py
@DateTime: 2025/1/17 22:29
"""
import time
from typing import Any

from fastapi import Request
from starlette.types import ASGIApp, Scope, Receive, Send

from backend import PROJECT_CONFIG, GLOBAL_CONFIG, LOGGER


class ReqResLoggerMiddleware:

    def __init__(self, app: ASGIApp):
        self.app: ASGIApp = app
        self.response_body = {}
        self.response_headers = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send, *args, **kwargs):
        # 仅处理HTTP请求
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 接口服务开始时间
        start_time = time.time()
        request_time: str = time.strftime(GLOBAL_CONFIG.DATETIME_FORMAT, time.localtime(start_time))

        # 重载 starlette 的 receive 函数，转存消费
        receive_ = await receive()

        async def receive():
            return receive_

        # 创建请求对象，消费请求体
        request_instance = Request(scope, receive)

        # 判断请求方式
        request_method: str = request_instance.scope.get("method")
        if request_method in (
                "OPTIONS",
        ):
            await self.app(scope, receive, send)
            return

        # 判断请求路径
        request_url: str = str(request_instance.url)
        request_path: str = request_instance.scope.get("path")
        if request_path in (
                PROJECT_CONFIG.APP_DOCS_URL,
                PROJECT_CONFIG.APP_REDOC_URL,
                PROJECT_CONFIG.APP_OPENAPI_URL,
                PROJECT_CONFIG.APP_OPENAPI_JS_URL,
                PROJECT_CONFIG.APP_OPENAPI_CSS_URL,
                PROJECT_CONFIG.APP_OPENAPI_FAVICON_URL,
        ):
            await self.app(scope, receive, send)
            return

        request_alias: str = GLOBAL_CONFIG.ROUTE_ALIAS.get(request_path or "未定义", "未定义")
        request_client: str = request_instance.scope.get("client")[0]
        request_header: dict = dict(request_instance.headers)
        request_body: bytes = await request_instance.body()

        # 获取json格式响应数据
        try:
            request_json = await request_instance.json()
        except Exception as e:
            request_json = None
        finally:
            ...

        # 转存请求体
        request_instance.state.body = request_body

        # 转存响应体
        original_send = send

        # 响应体处理
        async def send_process(message):
            if message["type"] == "http.response.start":
                self.response_headers = {k.decode(): v.decode() for k, v in message.get("headers", {})}
            elif message["type"] == "http.response.body":
                body = message.get("body", "")
                self.response_body = body.decode()
            await original_send(message)

        # 中间件传递
        await self.app(scope, receive, send_process)

        # 接口服务结束时间
        end_time = time.time()
        response_time: str = time.strftime(GLOBAL_CONFIG.DATETIME_FORMAT, time.localtime(end_time))

        # 计算耗时
        elapsed_time = end_time - start_time
        request_message: str = f"\n> > > > > > > > > > > > > > > > > > > >\n" \
                               f"请求时间：{request_time}\n" \
                               f"请求接口：{request_alias}\n" \
                               f"请求方式：{request_method}\n" \
                               f"请求地址：{request_url}\n" \
                               f"请求来源：{request_client}\n" \
                               f"请求头部：{request_header}\n" \
                               f"请求参数：{request_json or request_body}\n" \
                               f"响应头部：{self.response_headers}\n" \
                               f"响应参数：{self.response_body}\n" \
                               f"响应时间：{response_time}\n" \
                               f"响应耗时：{elapsed_time:.4f}s\n" \
                               f"> > > > > > > > > > > > > > > > > > > >"
        LOGGER.info(request_message)
