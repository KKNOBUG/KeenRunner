# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : tcp_async_utils
@DateTime: 2026/3/24 09:50
"""
from __future__ import annotations

import asyncio
import random
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import orjson
from lxml import etree

from backend.core.exceptions import ReqInvalidException, ResInvalidException


class TcpFrameMode(str, Enum):
    """
    TCP 收发帧格式；短连接与长连接均可使用（长连接默认 LENGTH_PREFIX_JSON）。

    LENGTH_PREFIX_JSON（默认）：
        - 发送：先写固定宽度十进制长度字符串（如 8 位 ``00000123``），再写正文。
        - 接收：先读同样宽度的长度字段解析出 N，再读恰好 N 字节正文。
        - 适用：需预先知道正文长度的协议；支持连接保持下的连续多帧。

    RAW：
        - 发送：只发正文，不加长度前缀。
        - 接收：读至对端关闭连接（或读超时），拼成完整响应。
        - 适用：对端「发完即关」或只能靠 EOF 界定响应；不适合长连接连续多帧。
    """

    LENGTH_PREFIX_JSON = "length_prefix_json"
    RAW = "raw"


class AsyncTcpUtils:
    """
    异步 TCP 短连接统一调度工具；由 ``AioTcpClient.tcp`` 构造，支持链式取响应。

    :param client: AioTcpClient 实例
    :param host: TCP 服务主机地址
    :param port: TCP 服务端口
    :param data: 发送数据（str / bytes / dict / None）
    :param frame_mode: 帧协议，默认 LENGTH_PREFIX_JSON
    :param length_field_size: 长度前缀宽度（位数）；缺省取 client.length_field_size
    :param encoding: 文本编码，默认 utf-8
    :param connect_timeout: 连接超时；缺省取 client.connect_timeout
    :param read_timeout: 读写超时；缺省取 client.default_timeout
    :param kwargs: 预留扩展关键字参数
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
        执行一次 TCP 收发，返回响应正文字节。

        :return: 响应体字节（若协议含长度前缀，已在内部剥离）
        :raises ReqInvalidException: 连接、读写或底层发送失败
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
        收发并将响应解析为 JSON。

        :return: 解析后的 JSON 对象；空响应返回 None
        :raises ReqInvalidException: 请求侧失败
        :raises ResInvalidException: 响应无法按 JSON 解析
        """
        try:
            raw = await self.execute()
            if not raw:
                return None
            return orjson.loads(raw)
        except ReqInvalidException:
            raise
        except orjson.JSONDecodeError as e:
            raise ResInvalidException(message=f"TCP响应解析失败, 响应体无法进行JSON格式处理: {e}")
        except Exception as e:
            raise ResInvalidException(message=f"TCP响应解析异常: {e}")

    async def text_resp(self) -> str:
        """
        收发并将响应按编码解码为文本。

        :return: 解码后的文本字符串
        :raises ReqInvalidException: 请求侧失败
        :raises ResInvalidException: 解码失败
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
        收发并返回原始响应字节。

        :return: 响应体字节
        :raises ReqInvalidException: 请求侧失败
        :raises ResInvalidException: 读取异常
        """
        try:
            return await self.execute()
        except ReqInvalidException:
            raise
        except Exception as e:
            raise ResInvalidException(message=f"TCP响应解析失败, 响应体无法进行字节内容读取: {e}")

    async def xml_resp(self) -> Optional[str]:
        """
        收发并将响应解析为格式化 XML 文本。

        :return: pretty-print 后的 XML 字符串；空响应返回 None
        :raises ReqInvalidException: 请求侧失败
        :raises ResInvalidException: XML 语法或解析异常
        """
        try:
            raw = await self.execute()
            if not raw or not raw.strip():
                return None
            parser = etree.XMLParser(
                recover=False,
                # 去除仅用于缩进排版的空白文本节点, 配合pretty_print输出更稳定。
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
    异步 TCP 短连接客户端；与 AsyncTcpUtils 配合实现 ``tcp(...).json_resp()`` 链式调用。

    每次 ``exchange`` / 链式调用均为独立建连、收发后关闭；多次交互请用 AsyncTcpConnection。
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
        :param timeout: 默认读写超时
        :param connect_timeout: 默认连接超时；缺省与 timeout 相同
        :param length_field_size: 长度前缀宽度（位数），默认 8
        :param concurrency_limit: 并发连接上限，默认 50
        :param max_response_bytes: 单次响应正文最大字节数，默认 10MB
        :param kwargs: 预留扩展关键字参数
        """
        self.default_timeout = timeout
        self.connect_timeout = connect_timeout or timeout
        self.length_field_size = length_field_size
        self.concurrency_limit = concurrency_limit
        self.max_response_bytes = max_response_bytes
        self.semaphore: asyncio.Semaphore = asyncio.Semaphore(value=self.concurrency_limit)
        self.kwargs = kwargs

    async def __aenter__(self) -> "AioTcpClient":
        """异步上下文进入，返回自身。"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文退出；短连接客户端无额外资源释放。"""
        return None

    async def close(self) -> None:
        """
        关闭会话接口（与 HTTP 客户端形态对齐）。

        短连接模式下无持久会话，默认空操作。
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
        构造一次 TCP 请求调度对象，供链式调用取响应。

        :param host: 目标主机
        :param port: 目标端口
        :param data: 发送内容
        :param frame_mode: 帧协议，见 TcpFrameMode
        :param length_field_size: 长度前缀宽度（位数）；缺省用客户端默认值
        :param encoding: 文本编码
        :param connect_timeout: 连接超时
        :param read_timeout: 读写超时
        :param kwargs: 透传至 exchange 的预留参数
        :return: AsyncTcpUtils 实例
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
        """
        将发送数据规范为字节正文。

        :param data: 原始发送数据；None 视为空正文
        :param encoding: 字符串编码
        :return: 正文字节（dict 经 orjson 序列化）
        """
        if data is None:
            return b""
        if isinstance(data, bytes):
            return data
        if isinstance(data, dict):
            return orjson.dumps(data)
        return str(data).encode(encoding)

    def _build_payload(
            self,
            data: Union[str, bytes, dict, None],
            frame_mode: TcpFrameMode,
            length_field_size: int,
            encoding: str,
    ) -> bytes:
        """
        按帧模式组装待发送报文。

        :param data: 发送数据
        :param frame_mode: 帧协议
        :param length_field_size: 长度前缀宽度（位数）
        :param encoding: 文本编码
        :return: 完整待发送字节（含可选长度前缀）
        :raises ReqInvalidException: 未知帧模式
        """
        body = self._encode_body(data, encoding)
        if frame_mode == TcpFrameMode.LENGTH_PREFIX_JSON:
            prefix = str(len(body)).zfill(length_field_size).encode(encoding)
            return prefix + body
        if frame_mode == TcpFrameMode.RAW:
            return body
        raise ReqInvalidException(message=f"不被允许的TcpFrameMode枚举: {frame_mode}")

    async def _read_until_eof(self, reader: asyncio.StreamReader, read_timeout: float, max_bytes: int) -> bytes:
        """
        RAW 模式下读至对端关闭（EOF）或超时。

        :param reader: 流读取器
        :param read_timeout: 单次 read 超时秒数
        :param max_bytes: 累计可读上限
        :return: 拼接后的响应字节
        :raises ReqInvalidException: 超出 max_bytes 或读超时等
        """
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
        短连接收发：建连、发送、按帧模式接收、关闭连接。

        :param host: 目标主机
        :param port: 目标端口
        :param data: 发送数据
        :param frame_mode: 帧协议
        :param length_field_size: 长度前缀宽度（位数）
        :param encoding: 文本编码
        :param connect_timeout: 连接超时；缺省用客户端默认
        :param read_timeout: 读写超时；缺省用客户端默认
        :param kwargs: 预留扩展（当前忽略）
        :return: 响应正文字节（不含长度前缀）
        :raises ReqInvalidException: 连接失败、超时、长度非法、响应过大等
        """
        del kwargs  # 预留扩展(如local_addr/ssl等)
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

                raise ReqInvalidException(message=f"不被允许的TcpFrameMode枚举: {frame_mode}")
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
    长连接 TCP 封装：同一条连接上多次发送/接收（发送与接收均按长度前缀帧）。

    :param host: TCP 服务主机地址
    :param port: TCP 服务端口
    :param length_field_size: 长度前缀宽度（位数）
    :param retries: 自动重连剩余次数（auto_reconnect=True 时生效）
    :param buffer_size: 预留缓冲区参数
    :param auto_reconnect: 是否在断连或超时后自动重连
    :param timeout: 连接与读写默认超时
    :param encoding: 文本编码
    :param max_response_bytes: 单次响应正文最大字节数
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
        """进入上下文时建立连接。"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出上下文时关闭连接。"""
        await self.close()

    async def connect(self) -> None:
        """
        建立到目标主机的 TCP 连接。

        :raises ReqInvalidException: 连接失败或超时且无法重连
        """
        await self._connection()

    async def _connection(self) -> None:
        """
        实际建连；超时且开启自动重连时转入 ``_reconnection``。

        :raises ReqInvalidException: 连接失败或超时
        """
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
        """
        消耗一次重试额度后随机退避并重新建连。

        :raises ReqInvalidException: 重试次数耗尽
        """
        self.retries -= 1
        if self.retries < 0:
            raise ReqInvalidException(message=f"TCP服务自动重连次数已用尽({self.host}:{self.port})")
        await asyncio.sleep(random.randint(1, 3))
        await self._connection()

    async def send(self, data: Union[str, bytes, dict]) -> None:
        """
        按长度前缀帧发送一帧数据。

        :param data: 发送内容（str / bytes / dict）
        :raises ReqInvalidException: 未连接且无法重连
        """
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
        """
        按行读取类 HTTP 头直至空行（可选能力，非长度前缀协议必需）。

        :return: 头字段字典；未连接且无法重连时返回空字典
        """
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
        """
        按长度前缀帧读取一帧；优先尝试 JSON 解析，失败则返回文本。

        :return: JSON 对象或文本字符串
        :raises ReqInvalidException: 未连接、超时、长度非法或响应过大
        """
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
            return orjson.loads(text)
        except orjson.JSONDecodeError:
            return text

    async def close(self) -> None:
        """关闭写端并清理连接状态。"""
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
    短连接便捷函数：等价于 ``AioTcpClient().tcp(...).json_resp()``。

    内部仍为一次建连、收发后关闭；多次交互请使用 AsyncTcpConnection。

    :param host: 目标主机
    :param port: 目标端口
    :param data: JSON 请求体（dict）
    :param client: 可选复用的 AioTcpClient；未传则临时创建并在 finally 中 close
    :param kwargs: 透传至 ``tcp``（如 frame_mode / encoding / 超时等）
    :return: 解析后的 JSON 响应
    :raises ReqInvalidException: 请求侧失败
    :raises ResInvalidException: 响应非合法 JSON
    """
    own = client is None
    cli = client or AioTcpClient()
    try:
        utils = await cli.tcp(host, port, data, **kwargs)
        return await utils.json_resp()
    finally:
        if own:
            await cli.close()
