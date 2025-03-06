# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : app_middleware.py
@DateTime: 2025/1/17 22:29
"""
import time
from io import BytesIO
from urllib.parse import unquote

from fastapi import Request, Response
from starlette.types import ASGIApp, Scope, Receive, Send

from backend import PROJECT_CONFIG, GLOBAL_CONFIG, LOGGER


def is_upload_request(request: Request) -> bool:
    path: str = request.url.path.lower()
    content_type: str = request.headers.get("content-type", "")
    return "multipart/form-data" in content_type.lower() or path.startswith("upload") or path.endswith("upload")


def is_html_response(response: Response) -> bool:
    content_type: str = response.headers.get("content-type", "")
    return "text/html" in content_type.lower() or "application/xml" in content_type.lower()


def is_image_response(response: Response) -> bool:
    content_type: str = response.headers.get("content-type", "")
    return "image" in content_type.lower()


def is_download_response(response: Response) -> bool:
    content_disposition: str = response.headers.get("content-disposition", "")
    return "attachment" in content_disposition.lower()


async def logging_middleware(request: Request, call_next):
    # 接口服务时间
    start_time = time.time()
    request_time: str = time.strftime(GLOBAL_CONFIG.DATETIME_FORMAT, time.localtime(start_time))

    # 变量初始化
    request_body, response_body = b'', b''
    is_html, is_upload, is_download = False, False, False

    # 判断是否为文件上传清洁
    is_upload: bool = is_upload_request(request)
    if is_upload:
        request_body: bytes = b"<FILE UPLOAD>"
    else:
        # 消费请求体并重置请求流
        request_body: bytes = await request.body()
        request._body = request_body
        request._stream = BytesIO(request_body)

    # 记录请求信息
    request_method: str = request.method
    request_router: str = request.url.path
    request_header: dict = dict(request.headers)
    request_client: str = request.client.host if request.client else "127.0.0.1"
    request_alias: str = GLOBAL_CONFIG.ROUTE_ALIAS.get(request_router or "未定义", "未定义")
    request_body: bytes = request_body if is_upload else request_body.decode("utf-8", errors="ignore")
    request_params: str = unquote(request.query_params.__str__())

    # 请求流传递并获取响应
    response = await call_next(request)

    # 判断是否管控响应
    is_download: bool = is_download_response(response)
    is_html: bool = is_html_response(response)
    is_image: bool = is_image_response(response)

    response_headers: dict = dict(response.headers)

    # 消费响应体
    if is_download:
        response_body = b"<FILE DOWNLOAD>"
    elif is_html:
        response_body = b"<HTML CONTENT>"
    elif is_image:
        response_body = b"IMAGE CONTENT"
    else:
        body_chunks = []
        async for chunk in response.body_iterator:
            body_chunks.append(chunk)

        response_body = b"".join(body_chunks).decode("utf-8", errors="ignore")

        # 重置响应体
        response = Response(
            content=response_body,
            status_code=response.status_code,
            headers=response_headers,
            media_type=response.media_type
        )

    # 接口服务结束时间
    end_time = time.time()
    response_time: str = time.strftime(GLOBAL_CONFIG.DATETIME_FORMAT, time.localtime(end_time))
    elapsed_time = end_time - start_time

    # 记录日志
    request_message: str = f"\n> > > > > > > > > > > > > > > > > > > >\n" \
                           f"请求时间：{request_time}\n" \
                           f"请求接口：{request_alias}\n" \
                           f"请求方式：{request_method}\n" \
                           f"请求路由：{request_router}\n" \
                           f"请求来源：{request_client}\n" \
                           f"请求头部：{request_header}\n" \
                           f"请求参数：{request_body or request_params}\n" \
                           f"响应头部：{response_headers}\n" \
                           f"响应参数：{response_body}\n" \
                           f"响应时间：{response_time}\n" \
                           f"响应耗时：{elapsed_time:.4f}s\n" \
                           f"< < < < < < < < < < < < < < < < < < < < "

    LOGGER.info(request_message)

    # 审计落库
    ...

    return response


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
                if "image" not in self.response_headers["content-type"]:
                    self.response_body = body.decode(errors='ignore')
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
