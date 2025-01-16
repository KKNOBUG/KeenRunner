# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : request_async_utils.py
@DateTime: 2025/1/16 20:11
"""
import asyncio
import httpx

from datetime import timedelta
from pathlib import Path
from typing import Optional, Dict, Union, Any
from httpx import Response
from aiohttp import ClientSession, ClientTimeout, HttpVersion, TCPConnector, ClientResponse, FormData

from backend.common.file_utils import FileUtils
from backend.core.exceptions.base_exceptions import ResInvalidException, ReqInvalidException

from backend.enums.http_enum import HTTPMethod


class AsyncHttpUtils:
    def __init__(self, client, method: HTTPMethod, url: str, **kwargs):
        """
        异步 HTTP 请求统一调度工具类构造。

        :param client: 请求会话；必填选项；AioHttp 请求会话或 Httpx 会话。
        :param method: 字符类型；必填选型；请求方式。
        :param url: 字符类型；必填选型；请求地址。
        :param kwargs: 其他关键字参数（通过底层代码查看可传递关键字）。
        """
        self.client = client
        self.method = method
        self.url = url
        self.params = kwargs.pop("params", None)
        self.data = kwargs.pop("data", None)
        self.json = kwargs.pop("json", None)
        self.timeout = kwargs.pop("timeout", None)
        self.headers = kwargs.pop("headers", None)
        self.kwargs = kwargs

    async def execute(self) -> Union[ClientResponse, Response]:
        """
        HTTP 请求统一调度方法，执行 HTTP 请求并返回响应对象。

        :return: 响应对象。
        :raises Exception: 当请求发生异常时抛出异常。
        """
        try:
            return await self.client.request(
                method=self.method, url=self.url,
                params=self.params, data=self.data, json=self.json,
                timeout=self.timeout, headers=self.headers, **self.kwargs
            )
        except Exception as e:
            raise ReqInvalidException(message=f"{e}")

    async def json_resp(self):
        """
        获取响应的 JSON 数据。

        :return: 响应的 JSON 数据。
        :raises Exception: 当请求或解析 JSON 数据发生异常时抛出异常。
        """
        try:
            if isinstance(self.client, AioHttpClient):
                async with await self.execute() as response:
                    return await response.json()
            elif isinstance(self.client, HttpxClient):
                response = await self.execute()
                return response.json()
        except Exception as e:
            raise ResInvalidException(message=f"{e}")

    async def text_resp(self):
        """
        获取响应的文本数据。

        :return: 响应的文本数据。
        :raises Exception: 当请求或获取文本数据发生异常时抛出异常。
        """
        try:
            if isinstance(self.client, AioHttpClient):
                async with await self.execute() as response:
                    return await response.text()
            elif isinstance(self.client, HttpxClient):
                response = await self.execute()
                return response.text
        except Exception as e:
            raise ResInvalidException(message=f"{e}")

    async def bytes_resp(self):
        """
        获取响应的字节数据。

        :return: 响应的字节数据。
        :raises Exception: 当请求或获取字节数据发生异常时抛出异常。
        """
        try:
            if isinstance(self.client, AioHttpClient):
                async with await self.execute() as response:
                    return await response.read()
            elif isinstance(self.client, HttpxClient):
                response = await self.execute()
                return response.content
        except Exception as e:
            raise ResInvalidException(message=f"{e}")

    async def stream_resp(self, chunk_size=1024):
        """
        以流的方式获取响应内容。

        :param chunk_size: 流的块大小，默认为 1024 字节。
        :return: 响应的字节数据块的生成器。
        :raises Exception: 当请求或获取流数据发生异常时抛出异常。
        """
        try:
            if isinstance(self.client, AioHttpClient):
                async with await self.execute() as response:
                    async for chunk in response.content.iter_chunked(chunk_size):
                        yield chunk
            elif isinstance(self.client, HttpxClient):
                response = await self.execute()
                async for chunk in response.aiter_bytes(chunk_size):
                    yield chunk
        except Exception as e:
            raise ResInvalidException(message=f"{e}")

    async def headers_resp(self):
        """
        获取响应头跟响应体信息。

        :return: 包含响应体和响应头的元组。
        :raises Exception: 当请求或解析 JSON 数据发生异常时抛出异常。
        """
        try:
            if isinstance(self.client, AioHttpClient):
                async with await self.execute() as response:
                    body = await response.json()
                    headers = dict(response.headers)
                    return body, headers
            elif isinstance(self.client, HttpxClient):
                response = await self.execute()
                headers = response.headers
                body = response.json()
                return body, headers
        except Exception as e:
            raise ResInvalidException(message=f"{e}")


class AioHttpClient:

    def __init__(self, headers: Optional[Dict] = None, timeout: timedelta = timedelta(seconds=300),
                 concurrency_limit: int = 10, **kwargs):
        """
        构造异步 HTTP 客户端（联合 AsyncHttpUtils 类的统一调度特性，实现支持链式调用）。

        :param headers: 字典类型；非必填项；默认接口请求携带的头部信息。
        :param timeout: 时间类型；非必填项；默认接口请求超时时间，单位为秒。
        :param concurrency_limit: 整数类型；非必填项；默认并发限制 10 个线程处理。
        :param kwargs: 其他关键字参数。
        """
        self.default_headers: dict = headers or {}
        self.default_timeout: ClientTimeout = ClientTimeout(timeout.total_seconds())
        self.concurrency_limit: int = concurrency_limit
        self.semaphore: asyncio.Semaphore = asyncio.Semaphore(value=self.concurrency_limit)
        self.kwargs = kwargs
        self.session: Optional[ClientSession] = None

    async def __aenter__(self):
        """支持异步上下文管理"""
        if not self.session:
            connector = TCPConnector(ssl=True, limit=self.concurrency_limit, enable_cleanup_closed=True)
            self.session = ClientSession(
                headers=self.default_headers,
                timeout=self.default_timeout,
                version=HttpVersion(1, 1),
                connector=connector,
                **self.kwargs
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出异步上下文管理"""
        if self.session:
            await self.session.close()
            self.session = None

    async def close(self):
        """关闭当前请求会话"""
        if self.session:
            await self.session.close()
            self.session = None

    async def request(self, method: HTTPMethod, url: str, params: dict = None,
                      data: dict = None, json: str = None, timeout: timedelta = None, headers: dict = None, **kwargs):
        """
        内部请求实现，创建客户端会话，构造并发生 HTTP 请求，获取响应对象，并返回。

        :param method: 枚举类型，必填选项；请求方式。
        :param url: 字符类型；必填选项；请求地址。
        :param params: 字典类型；非必填项；请求参数（查询字符串：k1=v1&k2=v2）。
        :param data: 字典类型；非必填项；请求参数（表单）。
        :param json: 字典类型；非必填项；请求参数（对象）。
        :param timeout: 时间类型；非必填项；默认接口请求超时时间，单位为秒。
        :param headers: 字典类型；非必填项；默认接口请求携带的头部信息。
        :param kwargs: 其他关键字参数（通过底层代码查看可传递关键字）。
        :return: ClientSession 的响应对象。
        :raises Exception: 当请求发生异常时抛出异常。
        """
        timeout = timeout or self.default_timeout
        if isinstance(timeout, timedelta):
            timeout = ClientTimeout(timeout.total_seconds())

        headers = headers or {}
        headers = {**self.default_headers, **headers}

        try:
            async with self.semaphore:
                return await self.session.request(
                    method=method.value, url=url,
                    params=params, data=data, json=json,
                    timeout=timeout, headers=headers,
                    **kwargs
                )
        except Exception as e:
            raise ReqInvalidException(message=f"{e}")

    async def get(self, url: str, params: dict = None, timeout: timedelta = None, **kwargs) -> AsyncHttpUtils:
        """
        发起 GET 请求。

        :param url: 请求地址。
        :param params: 请求参数。
        :param timeout: 请求超时时间。
        :param kwargs: 其他关键字参数。
        :return: AsyncHttpUtils 实例。
        """
        return AsyncHttpUtils(self, HTTPMethod.GET, url, params=params, timeout=timeout, **kwargs)

    async def post(self, url: str, data: Union[dict, Any] = None, json: Union[dict, Any] = None,
                   timeout: timedelta = None, **kwargs) -> AsyncHttpUtils:
        """
        发起 POST 请求。

        :param url: 请求地址。
        :param data: 请求表单数据或对象。
        :param json: 请求对象。
        :param timeout: 请求超时时间。
        :param kwargs: 其他关键字参数。
        :return: AsyncHttpUtils 实例。
        """
        data = data or None
        json = json or None
        return AsyncHttpUtils(self, HTTPMethod.POST, url, data=data, json=json, timeout=timeout, **kwargs)

    async def put(self, url: str, data: Union[dict, Any] = None, timeout: timedelta = None, **kwargs) -> AsyncHttpUtils:
        """
        发起 PUT 请求。

        :param url: 请求地址。
        :param data: 请求表单数据或对象。
        :param timeout: 请求超时时间。
        :param kwargs: 其他关键字参数。
        :return: AsyncHttpUtils 实例。
        """
        return AsyncHttpUtils(self, HTTPMethod.PUT, url, data=data, timeout=timeout, **kwargs)

    async def delete(self, url: str, data: Union[dict, Any] = None, timeout: timedelta = None,
                     **kwargs) -> AsyncHttpUtils:
        """
        发起 DELETE 请求。

        :param url: 请求地址。
        :param data: 请求表单数据或对象。
        :param timeout: 请求超时时间。
        :param kwargs: 其他关键字参数。
        :return: AsyncHttpUtils 实例。
        """
        return AsyncHttpUtils(self, HTTPMethod.DELETE, url, data=data, timeout=timeout, **kwargs)

    async def upload_file(self, url: str, file: Union[str, bytes, Path], file_field: str = "file",
                          filename: Optional[str] = None, method: HTTPMethod = HTTPMethod.POST,
                          timeout: Optional[timedelta] = None, content_type: Optional[str] = str,
                          **kwargs) -> AsyncHttpUtils:
        """
        上传文件。

        :param url: 请求地址。
        :param file: 文件路径或字节数据。
        :param file_field: 字符类型；非必填项；文件参数字段，默认 file。
        :param filename: 字符类型；非必填项；文件名称。
        :param method: 枚举类型，必填选项；请求方式。
        :param timeout: 时间类型；非必填项；默认接口请求超时时间，单位为秒。
        :param content_type: 内容类型。
        :param kwargs: 其他关键字参数。
        :return: AsyncHttpUtils 实例。
        :raises Exception: 当文件处理或请求发生异常时抛出异常。
        """
        try:
            form_data = FormData()
            file_name = file_bytes, mime_type = FileUtils.get_file_info(file, filename=filename)
            filename = filename or file_name
            content_type = content_type or mime_type
            form_data.add_field(name=file_field, value=file_bytes, filename=filename, content_type=content_type)
        except Exception as e:
            raise ResInvalidException(message=f"{e}")

        return AsyncHttpUtils(self, method, url, data=form_data, timeout=timeout, **kwargs)


class HttpxClient:

    def __init__(self, timeout: float = 300, headers: Dict[str, Any] = None, **kwargs) -> None:
        """
        异步 HTTP 请求客户端构造方法。

        :param timeout: 时间类型；非必填项；默认接口请求超时时间，单位为秒。
        :param headers: 字典类型；非必填项；默认接口请求携带的头部信息。
        :param kwargs: 其他关键字参数。
        """
        self.default_timeout: float = timeout
        self.default_headers: dict = headers or {}
        self.kwargs = kwargs
        self.session: Optional[httpx.AsyncClient] = None
        self.response: Optional[httpx.Response] = None

    async def __aenter__(self):
        """支持异步上下文管理"""
        if not self.session:
            self.session = httpx.AsyncClient(
                headers=self.default_headers,
                timeout=self.default_timeout,
                **self.kwargs
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出异步上下文管理"""
        if self.session:
            await self.session.aclose()

    async def close(self):
        """关闭当前请求会话"""
        if self.session:
            await self.session.aclose()

    async def request(self, method: HTTPMethod, url: str, params: Union[str, dict] = None, data: dict = None,
                      json: dict = None, headers: dict = None, timeout: float = None, **kwargs) -> Response:
        """
        内部请求实现，创建客户端会话，构造并发生 HTTP 请求，获取响应对象，并返回。

        :param method: 枚举类型；必填选型；接口请求方式。
        :param url: 字符类型；必填选型；接口请求地址。
        :param params: 字典类型；非必填项；请求参数（查询字符串：k1=v1&k2=v2）。
        :param data: 字典类型；非必填项；请求参数（表单）。
        :param json: 字典类型；非必填项；请求参数（对象）。
        :param timeout: 接口超时时间。
        :param kwargs: 其他关键字参数（通过底层代码查看可传递关键字）。
        :return: httpx.Response 对象。
        :raises Exception: 当请求发生异常时抛出异常。
        """
        timeout = timeout or self.default_timeout

        headers = headers or {}
        headers = {**self.default_headers, **headers}
        try:
            return await self.session.request(
                method=method.value, url=url,
                params=params, data=data, json=json,
                timeout=timeout, headers=headers,
                **kwargs
            )
        except Exception as e:
            raise ResInvalidException(message=f"{e}")

    async def get(self, url: str, params: dict = None, timeout: timedelta = None, **kwargs) -> AsyncHttpUtils:
        """
        发起 GET 请求。

        :param url: 请求地址。
        :param params: 请求参数。
        :param timeout: 请求超时时间。
        :param kwargs: 其他关键字参数。
        :return: AsyncHttpUtils 实例。
        """
        return AsyncHttpUtils(self, HTTPMethod.GET, url, params=params, timeout=timeout, **kwargs)

    async def post(self, url: str, data: Union[dict, Any] = None, json: Union[dict, Any] = None,
                   timeout: timedelta = None, **kwargs) -> AsyncHttpUtils:
        """
        发起 POST 请求。

        :param url: 请求地址。
        :param data: 请求表单数据或对象。
        :param json: 请求对象。
        :param timeout: 请求超时时间。
        :param kwargs: 其他关键字参数。
        :return: AsyncHttpUtils 实例。
        """
        data = data or None
        json = json or None
        return AsyncHttpUtils(self, HTTPMethod.POST, url, data=data, json=json, timeout=timeout, **kwargs)

    async def put(self, url: str, data: Union[dict, Any] = None, timeout: timedelta = None,
                  **kwargs) -> AsyncHttpUtils:
        """
        发起 PUT 请求。

        :param url: 请求地址。
        :param data: 请求表单数据或对象。
        :param timeout: 请求超时时间。
        :param kwargs: 其他关键字参数。
        :return: AsyncHttpUtils 实例。
        """
        return AsyncHttpUtils(self, HTTPMethod.PUT, url, data=data, timeout=timeout, **kwargs)

    async def delete(self, url: str, data: Union[dict, Any] = None, timeout: timedelta = None,
                     **kwargs) -> AsyncHttpUtils:
        """
        发起 DELETE 请求。

        :param url: 请求地址。
        :param data: 请求表单数据或对象。
        :param timeout: 请求超时时间。
        :param kwargs: 其他关键字参数。
        :return: AsyncHttpUtils 实例。
        """
        return AsyncHttpUtils(self, HTTPMethod.DELETE, url, data=data, timeout=timeout, **kwargs)
