# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : tcp_async_utils
@DateTime: 2026/3/24 09:50

异步 TCP 请求封装(风格参考 `backend/common/request/request_async_utils.py`)。

说明:

- 短连接: 使用 `AioTcpClient` + `AsyncTcpUtils`。每次 `execute()/json_resp()` 都会建连、收发、关闭。
- 长连接: 使用 `AsyncTcpConnection`。`async with` 内复用同一条连接多次 `send/receive`。

帧协议:

- `TcpFrameMode.LENGTH_PREFIX_JSON`: 长度前缀(固定宽度十进制字符串)+ 正文；接收先读长度再读正文。
- `TcpFrameMode.RAW`: 无长度前缀；接收读到对端关闭或读超时为止。
"""
from __future__ import annotations

import asyncio
import json
import random
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from lxml import etree

from backend.core.exceptions.base_exceptions import ReqInvalidException, ResInvalidException


class TcpFrameMode(str, Enum):
    """
    TCP 收发帧格式(短连接 `AioTcpClient.exchange` / 长连接 `AsyncTcpConnection` 均可能用到子集)。

    - LENGTH_PREFIX_JSON: 长度前缀 + 正文(正文通常为 JSON 或文本)。
    - RAW: 无长度前缀, 仅用于短连接 RAW 模式下的原始收发。
    """

    LENGTH_PREFIX_JSON = "length_prefix_json"
    RAW = "raw"


class AsyncTcpUtils:
    """
    异步 TCP 请求统一调度工具类构造(短连接)。

    :param client: 请求客户端；必填选项；AioTcpClient 实例。
    :param host: 字符类型；必填选项；TCP 服务主机地址。
    :param port: 整数类型；必填选项；TCP 服务端口。
    :param data: 发送数据；非必填项；str/bytes/dict/None。
    :param frame_mode: 帧协议；非必填项；默认 LENGTH_PREFIX_JSON。
    :param length_field_size: 整数类型；非必填项；长度前缀宽度(位数), 默认使用 client.length_field_size。
    :param encoding: 字符类型；非必填项；文本编码(默认 utf-8)。
    :param connect_timeout: 时间类型；非必填项；连接超时, 默认使用 client.connect_timeout。
    :param read_timeout: 时间类型；非必填项；读写超时, 默认使用 client.default_timeout。
    :param kwargs: 其他关键字参数(预留扩展)。
    """

    def __init__(
            self,
            client: "AioTcpClient",
            host: str,
            port: int,
            data: Union[str, bytes, dict, None] = None,
            *,
            frame_mode: TcpFrameMode = TcpFrameMode.LENGTH_PREFIX_JSON,
            length_field_size: Optional[int] = None,
            encoding: str = "utf-8",
            connect_timeout: Optional[timedelta] = None,
            read_timeout: Optional[timedelta] = None,
            **kwargs: Any,
    ):
        self.client = client
        self.host = host
        self.port = port
        self.data = data
        self.frame_mode = frame_mode
        self.length_field_size = length_field_size or client.length_field_size
        self.encoding = encoding
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.kwargs = kwargs

    async def execute(self) -> bytes:
        """
        TCP 请求统一调度方法, 执行 TCP 收发并返回响应字节。

        :return: 响应体字节(若协议包含长度前缀, 已在内部剥离)。
        :raises ReqInvalidException: 当连接、发送、接收或协议解析发生异常时抛出。
        """
        try:
            return await self.client.exchange(
                host=self.host,
                port=self.port,
                data=self.data,
                frame_mode=self.frame_mode,
                length_field_size=self.length_field_size,
                encoding=self.encoding,
                connect_timeout=self.connect_timeout,
                read_timeout=self.read_timeout,
                **self.kwargs,
            )
        except ReqInvalidException:
            raise
        except Exception as e:
            raise ReqInvalidException(message=f"TCP请求失败: {e}")

    async def json_resp(self) -> Any:
        """
        获取响应的 JSON 数据。

        :return: 解析后的 JSON 对象；空响应返回 None。
        :raises ReqInvalidException: 当 TCP 请求失败时抛出。
        :raises ResInvalidException: 当响应体不是合法 JSON 或解析失败时抛出。
        """
        try:
            raw = await self.execute()
            if not raw:
                return None
            return json.loads(raw.decode(self.encoding))
        except ReqInvalidException:
            raise
        except json.JSONDecodeError as e:
            raise ResInvalidException(message=f"TCP响应解析失败, 响应体无法进行JSON格式处理: {e}")
        except Exception as e:
            raise ResInvalidException(message=f"TCP响应解析异常: {e}")

    async def text_resp(self) -> str:
        """
        获取响应的文本数据。

        :return: 解码后的文本字符串。
        :raises ReqInvalidException: 当 TCP 请求失败时抛出。
        :raises ResInvalidException: 当解码失败或处理异常时抛出。
        """
        try:
            raw = await self.execute()
            return raw.decode(self.encoding)
        except ReqInvalidException:
            raise
        except UnicodeDecodeError as e:
            raise ResInvalidException(message=f"TCP响应解析失败, 响应体无法进行{self.encoding}格式解码: {e}")
        except Exception as e:
            raise ResInvalidException(message=f"TCP响应解析异常: {e}")

    async def bytes_resp(self) -> bytes:
        """
        获取响应的字节数据。

        :return: 响应体字节。
        :raises ReqInvalidException: 当 TCP 请求失败时抛出。
        :raises ResInvalidException: 当处理异常时抛出。
        """
        try:
            return await self.execute()
        except ReqInvalidException:
            raise
        except Exception as e:
            raise ResInvalidException(message=f"TCP响应解析失败, 响应体无法进行字节内容读取: {e}")

    async def xml_resp(self) -> Optional[str]:
        """
        获取响应的 XML 文本, 并格式化后返回。

        :return: 格式化后的 XML 字符串；空响应返回 None。
        :raises ReqInvalidException: 当 TCP 请求失败时抛出。
        :raises ResInvalidException: 当响应体不是合法 XML 或解析失败时抛出。
        """
        try:
            raw = await self.execute()
            if not raw or not raw.strip():
                return None
            parser = etree.XMLParser(
                recover=False,
                # 去除仅用于缩进排版的空白文本节点, 配合 pretty_print 输出更稳定。
                remove_blank_text=True,
                encoding=self.encoding,
            )
            root = etree.fromstring(raw, parser=parser)
            text = etree.tostring(
                root,
                encoding=str,
                pretty_print=True,
                xml_declaration=False,
            )
            return text.strip()
        except ReqInvalidException:
            raise
        except etree.XMLSyntaxError as e:
            raise ResInvalidException(message=f"TCP响应解析失败, 响应体无法进行XML格式处理: {e}")
        except Exception as e:
            raise ResInvalidException(message=f"TCP响应解析异常: {e}")


class AioTcpClient:
    """
    构造异步 TCP 客户端(联合 AsyncTcpUtils 的统一调度特性, 实现支持链式调用)。
    """

    def __init__(
            self,
            *,
            timeout: timedelta = timedelta(seconds=30),
            connect_timeout: Optional[timedelta] = None,
            length_field_size: int = 8,
            concurrency_limit: int = 50,
            max_response_bytes: int = 10 * 1024 * 1024,
            **kwargs: Any,
    ):
        """
        :param timeout: 时间类型；非必填项；默认读写超时时间。
        :param connect_timeout: 时间类型；非必填项；默认连接超时时间。
        :param length_field_size: 整数类型；非必填项；长度前缀宽度(位数), 默认 8。
        :param concurrency_limit: 整数类型；非必填项；并发连接限制, 默认 50。
        :param max_response_bytes: 整数类型；非必填项；最大响应体字节数限制, 默认 10MB。
        :param kwargs: 其他关键字参数(预留扩展)。
        """
        self.default_timeout = timeout
        self.connect_timeout = connect_timeout or timeout
        self.length_field_size = length_field_size
        self.concurrency_limit = concurrency_limit
        self.max_response_bytes = max_response_bytes
        self.semaphore: asyncio.Semaphore = asyncio.Semaphore(value=self.concurrency_limit)
        self.kwargs = kwargs

    async def __aenter__(self) -> "AioTcpClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        return None

    async def close(self) -> None:
        """
        关闭当前请求会话(TCP 短连接模式下为保持与 HTTP 客户端一致的接口, 默认无操作)。
        """
        return None

    async def tcp(
            self,
            host: str,
            port: int,
            data: Union[str, bytes, dict, None] = None,
            *,
            frame_mode: TcpFrameMode = TcpFrameMode.LENGTH_PREFIX_JSON,
            length_field_size: Optional[int] = None,
            encoding: str = "utf-8",
            connect_timeout: Optional[timedelta] = None,
            read_timeout: Optional[timedelta] = None,
            **kwargs: Any,
    ) -> AsyncTcpUtils:
        """
        发起 TCP 请求(返回 AsyncTcpUtils 实例, 用于链式调用获取响应)。

        :param host: 目标主机。
        :param port: 目标端口。
        :param data: 发送内容。
        :param frame_mode: 帧协议, 见 TcpFrameMode。
        :param length_field_size: 长度前缀宽度(位数)。
        :param encoding: 文本编码。
        :param connect_timeout: 连接超时。
        :param read_timeout: 读写超时。
        :param kwargs: 其他关键字参数。
        :return: AsyncTcpUtils 实例。
        """
        return AsyncTcpUtils(
            self,
            host,
            port,
            data,
            frame_mode=frame_mode,
            length_field_size=length_field_size,
            encoding=encoding,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            **kwargs,
        )

    @staticmethod
    def _encode_body(data: Union[str, bytes, dict, None], encoding: str) -> bytes:
        if data is None:
            return b""
        if isinstance(data, bytes):
            return data
        if isinstance(data, dict):
            return json.dumps(data, ensure_ascii=False).encode(encoding)
        return str(data).encode(encoding)

    def _build_payload(
            self,
            data: Union[str, bytes, dict, None],
            frame_mode: TcpFrameMode,
            length_field_size: int,
            encoding: str,
    ) -> bytes:
        body = self._encode_body(data, encoding)
        if frame_mode == TcpFrameMode.LENGTH_PREFIX_JSON:
            prefix = str(len(body)).zfill(length_field_size).encode(encoding)
            return prefix + body
        if frame_mode == TcpFrameMode.RAW:
            return body
        raise ReqInvalidException(message=f"不被支持的 TcpFrameMode 枚举: {frame_mode}")

    async def _read_until_eof(self, reader: asyncio.StreamReader, read_timeout: float, max_bytes: int) -> bytes:
        total = 0
        chunks: List[bytes] = []
        while True:
            chunk = await asyncio.wait_for(reader.read(65536), timeout=read_timeout)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ReqInvalidException(message=f"RAW模式读取数据超出最大限制({max_bytes} bytes), 请检查对端是否未关闭连接或返回过大数据")
            chunks.append(chunk)
        return b"".join(chunks)

    async def exchange(
            self,
            *,
            host: str,
            port: int,
            data: Union[str, bytes, dict, None],
            frame_mode: TcpFrameMode,
            length_field_size: int,
            encoding: str,
            connect_timeout: Optional[timedelta],
            read_timeout: Optional[timedelta],
            **kwargs: Any,
    ) -> bytes:
        """
        内部请求实现: 建立连接、发送数据、接收响应并返回(短连接)。

        :return: 响应体字节。
        :raises ReqInvalidException: 当连接/读写/协议解析异常时抛出。
        """
        del kwargs  # 预留扩展(如 local_addr/ssl 等)
        conn_timeout = (connect_timeout or self.connect_timeout).total_seconds()
        read_to = (read_timeout or self.default_timeout).total_seconds()

        payload = self._build_payload(data, frame_mode, length_field_size, encoding)

        async with self.semaphore:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=conn_timeout,
                )
            except Exception as e:
                raise ReqInvalidException(message=f"TCP服务连接失败({host}:{port}, 超时={conn_timeout}s): {e}")

            try:
                writer.write(payload)
                await asyncio.wait_for(writer.drain(), timeout=read_to)

                if frame_mode == TcpFrameMode.LENGTH_PREFIX_JSON:
                    length_bytes = await asyncio.wait_for(
                        reader.readexactly(length_field_size),
                        timeout=read_to,
                    )
                    length_str = length_bytes.decode(encoding, errors="ignore").strip()
                    if not length_str.isdigit():
                        raise ReqInvalidException(message=f"长度前缀非法, 期待的是十进制数字, 而得到的是: {length_str}, 请确认对端协议")
                    length = int(length_str)
                    if length < 0:
                        raise ReqInvalidException(message=f"长度前缀非法, length={length}")
                    if length > self.max_response_bytes:
                        raise ReqInvalidException(message=f"响应体积过大({length} bytes), 超出最大限制: {self.max_response_bytes} bytes")
                    return await asyncio.wait_for(reader.readexactly(length), timeout=read_to)

                if frame_mode == TcpFrameMode.RAW:
                    return await self._read_until_eof(reader, read_to, self.max_response_bytes)

                raise ReqInvalidException(message=f"不被支持的 TcpFrameMode 枚举: {frame_mode}")
            except asyncio.TimeoutError as e:
                raise ReqInvalidException(message=f"TCP服务读写超时({host}:{port}, 超时={conn_timeout}s): {e}")
            except asyncio.IncompleteReadError as e:
                raise ReqInvalidException(message=f"TCP服务读数据不完整({host}:{port}): {e}")
            except ReqInvalidException:
                raise
            except Exception as e:
                raise ReqInvalidException(message=f"TCP服务异常({host}:{port}): {e}")
            finally:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass


class AsyncTcpConnection:
    """
    长连接 TCP 封装: 在同一条 TCP 连接上多次发送/接收。

    :param host: TCP 服务主机地址。
    :param port: TCP 服务端口。
    :param length_field_size: 长度前缀宽度(位数)。
    :param retries: 自动重连次数(auto_reconnect=True 时生效)。
    :param buffer_size: 预留参数(兼容旧实现)。
    :param auto_reconnect: 是否自动重连。
    :param timeout: 连接与读写的默认超时时间。
    :param encoding: 文本编码。
    :param max_response_bytes: 最大响应体字节数限制。
    """

    def __init__(
            self,
            host: str,
            port: int,
            *,
            length_field_size: int = 8,
            retries: int = 3,
            buffer_size: int = 1024,
            auto_reconnect: bool = False,
            timeout: timedelta = timedelta(seconds=30),
            encoding: str = "utf-8",
            max_response_bytes: int = 10 * 1024 * 1024,
    ):
        self.host = host
        self.port = port
        self.length_field_size = length_field_size
        self.retries = retries
        self.buffer_size = buffer_size
        self.auto_reconnect = auto_reconnect
        self.timeout = timeout
        self.encoding = encoding
        self.max_response_bytes = max_response_bytes
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected: bool = False

    async def __aenter__(self) -> "AsyncTcpConnection":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def connect(self) -> None:
        await self._connection()

    async def _connection(self) -> None:
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(host=self.host, port=self.port),
                timeout=self.timeout.total_seconds(),
            )
            self.connected = True
        except asyncio.TimeoutError:
            if self.auto_reconnect and self.retries > 0:
                await self._reconnection()
            else:
                raise ReqInvalidException(message=f"TCP服务连接超时({self.host}:{self.port}, 超时={self.timeout.total_seconds()}s)")
        except Exception as e:
            raise ReqInvalidException(message=f"TCP服务连接失败({self.host}:{self.port}): {e}")

    async def _reconnection(self) -> None:
        self.retries -= 1
        if self.retries < 0:
            raise ReqInvalidException(message=f"TCP服务自动重连次数已用尽({self.host}:{self.port})")
        await asyncio.sleep(random.randint(1, 3))
        await self._connection()

    async def send(self, data: Union[str, bytes, dict]) -> None:
        body = AioTcpClient._encode_body(data, self.encoding)
        length_str = str(len(body)).zfill(self.length_field_size)
        packet = length_str.encode(self.encoding) + body
        if self.writer and self.connected:
            self.writer.write(packet)
            await self.writer.drain()
            return
        if self.auto_reconnect:
            await self._reconnection()
            if self.writer and self.connected:
                self.writer.write(packet)
                await self.writer.drain()
                return
        raise ReqInvalidException(message="TCP服务暂未连接, 无法发送请求")

    async def receive_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if not (self.reader and self.connected):
            if self.auto_reconnect:
                await self._reconnection()
            if not (self.reader and self.connected):
                return headers
        while True:
            line = await self.reader.readline()
            if line in (b"\r\n", b"\n", b""):
                break
            text = line.decode(self.encoding).strip()
            if ": " in text:
                key, value = text.split(": ", 1)
                headers[key.strip()] = value.strip()
            elif text:
                headers[text] = ""
        return headers

    async def receive(self) -> Any:
        if not (self.reader and self.connected):
            if self.auto_reconnect:
                await self._reconnection()
            if not (self.reader and self.connected):
                raise ReqInvalidException(message="TCP服务暂未连接, 无法接收读写流")
        try:
            length_data = await asyncio.wait_for(
                self.reader.readexactly(self.length_field_size),
                timeout=self.timeout.total_seconds(),
            )
        except asyncio.TimeoutError as e:
            raise ReqInvalidException(message=f"TCP服务接收长度前缀超时({self.host}:{self.port}): {e}")
        length_str = length_data.decode(self.encoding, errors="ignore").strip()
        if not length_str.isdigit():
            raise ReqInvalidException(message=f"长度前缀非法, 期待的是十进制数字, 而得到的是: {length_str}, 请确认对端协议")
        length = int(length_str)
        if length > self.max_response_bytes:
            raise ReqInvalidException(message=f"响应体积过大({length} bytes), 超出最大限制: {self.max_response_bytes} bytes")
        try:
            data = await asyncio.wait_for(
                self.reader.readexactly(length),
                timeout=self.timeout.total_seconds(),
            )
        except asyncio.TimeoutError as e:
            raise ReqInvalidException(message=f"TCP服务接收正文超时({self.host}:{self.port}, bytes={length}): {e}")
        text = data.decode(self.encoding).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    async def close(self) -> None:
        try:
            if self.writer and self.connected:
                self.writer.close()
                await self.writer.wait_closed()
        finally:
            self.connected = False
            self.reader = None
            self.writer = None


async def tcp_json(
        host: str,
        port: int,
        data: dict,
        *,
        client: Optional[AioTcpClient] = None,
        **kwargs: Any,
) -> Any:
    """
    【短连接】便捷函数: 等价于 ``AioTcpClient().tcp(...).json_resp()``。

    内部仍为 **一次建连、收发后关闭**；若需多次交互请改用 ``AsyncTcpConnection``。
    """
    own = client is None
    cli = client or AioTcpClient()
    try:
        utils = await cli.tcp(host, port, data, **kwargs)
        return await utils.json_resp()
    finally:
        if own:
            await cli.close()
