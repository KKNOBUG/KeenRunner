# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : request_sync_utils.py
@DateTime: 2025/1/13 09:17
"""
import threading
import json as JSON
import requests
from typing import Optional, Dict, Any, Union, List, Literal

from requests import exceptions

from backend.enums.http_enum import HTTPMethod


class RequestSyncUtils:
    """
    RequestSyncUtils 类用于构建同步的 HTTP 请求客户端，提供了一系列功能来处理 HTTP 请求和响应。

    代码设计思想：
    1. 利用 `requests` 模块构建 HTTP 请求客户端。
    2. 通过魔术方法 `__new__` 实现单例模式，确保整个应用程序中仅存在一个 HTTP 请求客户端实例，避免重复实例化。
    3. 在实例化时可配置接口请求超时时间，默认设置为 120 秒。
    4. 自动处理请求头部信息，若未提供请求头，则使用常用默认值；若已提供，则与默认值合并。
    5. 处理不同类型的请求参数（`params`、`data` 和 `json`），实现参数类型与参数数据的双向绑定。
    6. 支持多种 HTTP 请求方法，如 `GET`、`POST`、`PUT`、`DELETE`、`HEAD`、`OPTIONS`、`CONNECT`、`TRACE` 等。
    7. 将响应对象中的常用信息封装成字典，包括 `url`、`headers`、`method`、`time`、`cookie`等。
    """

    # 用于存储该类的唯一实例
    __private_instance = None
    __private_initialized = False
    __private_lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> object:
        """
        创建并返回类的唯一实例。

        使用单例模式，在整个应用程序的生命周期内仅创建一个 `RequestSyncUtils` 实例。
        在多线程环境下，通过 `threading.Lock` 确保线程安全。

        :param args: 位置参数
        :param kwargs: 关键字参数
        :return: `RequestSyncUtils` 类的实例
        """
        if not cls.__private_instance and not cls.__private_initialized:
            with cls.__private_lock:
                if not cls.__private_instance and not cls.__private_initialized:
                    cls.__private_instance = super().__new__(cls)
                    cls.__private_initialized = True
        return cls.__private_instance

    def __init__(self, timeout: int = 120) -> None:
        """
        初始化 `RequestSyncUtils` 类的实例。

        :param timeout: 接口请求超时时间，单位为秒，默认值为 120 秒。
        """
        self.timeout = timeout
        self.session = requests.session()

    def request(self, *,
                url: str,
                method: HTTPMethod,
                params: Optional[str] = None,
                data: Optional[Dict[str, Any]] = None,
                json: Optional[Union[str, List, Dict[str, Any]]] = None,
                headers: Optional[Union[str, Dict[str, Any]]] = None,
                **kwargs) -> Dict[str, Any]:
        """
        发送 HTTP 请求并返回处理后的响应信息。

        :param url: 请求的 URL 地址。
        :param method: HTTP 请求方法，如 `GET`、`POST`、`PUT`、`DELETE` 等。
        :param params: URL 参数，可选，通常用于 GET 请求，以字符串形式表示。
        :param data: 发送到服务器的数据，可选，常用于 `POST`、`PUT` 等请求，以字典形式表示。
        :param json: 发送到服务器的 JSON 数据，可选，会自动设置 `Content - Type` 为 `application/json`，可以是字符串、列表或字典。
        :param headers: 请求头信息，可选，可以是字典或 JSON 字符串。
        :param kwargs: 其他 `requests.request` 支持的参数。
        :return: 包含响应信息的字典，结构如下：
            {
                "response_url": str,            # 响应的 URL
                "response_code": int,           # 响应状态码
                "response_reason": str,         # 响应原因
                "response_text": str,           # 响应文本内容
                "response_time": float,         # 响应时间（秒）
                "response_microseconds": int,   # 响应时间（微秒）
                "response_milliseconds": float, # 响应时间（毫秒）
                "response_headers": dict,       # 响应头字典
                "response_cookie": dict,        # 响应中的 cookie 字典
                "response_object": response,    # `requests` 的响应对象
                "response_json": Any            # 解析后的 JSON 数据，如果解析失败则为错误信息字符串
            }
        :raises ValueError: 如果请求方式不被支持或请求过程中出现错误。
        :raises requests.exceptions.HTTPError: 如果服务器返回的 HTTP 状态码不是 200。
        """

        # 1.检查请求方式是否被允许
        if method not in HTTPMethod.get_members():
            raise ValueError(f"请求方式[{method.value}]不被支持")

        # 2.检查是否指定请求头信息
        headers = self.headers_convert(headers=headers, params=params, data=data, json=json)

        # 3.构建请求对象
        try:
            response = self.session.request(
                url=url,
                method=method.value,
                params=params,
                data=data,
                json=json,
                headers=headers,
                timeout=int(self.timeout),
                **kwargs
            )
            if response.status_code != 200 and response.reason != "OK":
                raise ValueError("请求失败，服务器响应状态不是 [200 OK]")
        except exceptions.Timeout as e:
            raise ValueError("请求失败，网络连接超时或服务器响应超时")
        except exceptions.InvalidURL as e:
            raise ValueError("请求失败，URL解析失败或无效")
        except exceptions.HTTPError as e:
            raise ValueError("请求失败，服务器响应异常")
        except exceptions.ConnectionError as e:
            raise ValueError("请求失败，网络连接失败或服务器拒绝连接")

        response_dict: dict = self.response_convert(response=response)

        return response_dict

    @staticmethod
    def headers_convert(*, params: Optional[str] = None,
                        data: Optional[Dict[str, Any]] = None,
                        json: Optional[Union[str, List, Dict[str, Any]]] = None,
                        headers: Optional[Union[str, Dict[str, Any]]] = None):
        """
        处理并转换请求头信息。

        :param params: URL 参数，用于判断请求数据类型。
        :param data: 发送到服务器的数据，用于判断请求数据类型。
        :param json: 发送到服务器的 JSON 数据，用于判断请求数据类型。
        :param headers: 请求头信息，可以是字典或 JSON 字符串。
        :return: 处理后的请求头字典。
        :raises TypeError: 如果 `headers` 参数类型不正确。
        :raises ValueError: 如果 `headers` 字符串无法转换为字典。
        """
        # 1.检查headers类型是否符合预定义类型
        if not isinstance(headers, (type(None), dict, str)):
            raise TypeError(f"请求头[headers]参数应为None、字符串、字典类型，但得到了[{type(headers)}]类型")

        # 2.预定义请求头信息
        precast_headers: Dict[str, str] = {
            "Accept-Language": "zh-CN, zh;q=0.9",
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br",
        }

        # 3.转换上送的headers请求头信息
        if headers and isinstance(headers, str):
            try:
                headers_to_dict = JSON.loads(headers)

                if isinstance(headers_to_dict, dict):
                    precast_headers.update(headers_to_dict)
                else:
                    raise ValueError("字符串异常，无法转换字典类型")

            except JSON.decoder.JSONDecodeError:
                raise ValueError("字符串异常，无法转换字典类型")

        elif headers and isinstance(headers, dict):
            precast_headers.update(headers)

        # 4.根据参数类型设置请求头的客户端数据类型
        if params or data:
            # 将数据编码改为键值对
            form_url_encoded = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}
            precast_headers.update(form_url_encoded)
        elif json:
            # 将数据编码改为JSON对象（可以忽略，因为使用JSON参数时，不需要手动序列化数据或设置Content-Type属性，requests底层会自动处理）
            json_encoded = {"Content-Type": "application/json;charset=UTF-8"}
            precast_headers.update(json_encoded)

        return precast_headers

    @staticmethod
    def data_type_bind(params_type: Literal["params", "PARAMS", "data", "DATA", "json", "JSON"] = None,
                       params_data: Any = None):
        """
        绑定请求参数类型和参数数据。

        :param params_type: 参数类型，取值为`params`、`data`或`json`（不区分大小写）。
        :param params_data: 参数数据。
        :return: 包含参数类型和数据的字典。
        """
        if params_type:
            return {params_type.lower(): params_data}

        return {"json": None, "data": None, "params": None}

    @staticmethod
    def response_convert(response) -> Dict[str, Any]:
        """
        将响应对象转换为字典。

        :param response: `requests`库的响应对象。
        :return: 包含响应信息的字典。
        """
        response_dict: Dict[str, Any] = {}
        response_dict.setdefault("response_url", response.url)
        response_dict.setdefault("response_code", response.status_code)
        response_dict.setdefault("response_reason", response.reason)
        response_dict.setdefault("response_text", response.text)
        response_dict.setdefault("response_time", response.elapsed.total_seconds())
        response_dict.setdefault("response_microseconds", response.elapsed.microseconds)
        response_dict.setdefault("response_milliseconds", response.elapsed.microseconds / 1000)
        response_dict.setdefault("response_headers", dict(response.headers))
        response_dict.setdefault("response_cookie", dict(response.cookies))
        response_dict.setdefault("response_object", response)

        try:
            response_dict.setdefault("response_json", response.json())
        except Exception as e:
            response_dict.setdefault("response_json", e.__str__())

        return response_dict


if __name__ == '__main__':
    # 测试单例模式
    cls1 = RequestSyncUtils()
    cls2 = RequestSyncUtils()
    print(cls1 is cls2)

    # 测试接口
    test_get = cls2.request(url="https://httpbin.org/get", method=HTTPMethod.GET)
    print(test_get)

    headers = {"Content-Type": "1111"}
    data = {"name": "张三", "age": 20, "phone": "10086", "address": "上海市浦东新区"}
    test_post = cls2.request(url="http://httpbin.org/post", method=HTTPMethod.POST, json=data, headers=headers)
    print(test_post)
