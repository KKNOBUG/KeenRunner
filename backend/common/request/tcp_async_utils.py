# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
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
    """TCP收发帧格式枚举，对齐JMeter TCP取样器，短连接与长连接均可使用。"""

    # 长度前缀（默认）: 
    # 发送: 先写固定宽度的文本数字长度前缀（进制由radix决定，如8位十进制00000123）再写正文；
    # 接收: 先读同宽度长度字段按radix解析出N再读恰好N字节正文；
    LENGTH_PREFIX = "length_prefix"
    # 结束符:
    # 发送: 在正文后追加请求结束符（未配置时只发正文）；
    # 接收: 持续读至响应结束符（未配置时读至对端关闭）；
    TERMINATOR = "terminator"
    # RAW:
    # 发送: 只发正文不加帧标记；
    # 接收: 读至对端关闭（EOF）拼成完整响应；
    RAW = "raw"


class AsyncTcpUtils:
    """
    异步TCP短连接调度工具，由AioTcpClient.tcp构造，链式调用取响应。

    :param client: AioTcpClient实例
    :param host: TCP服务主机地址
    :param port: TCP服务端口
    :param data: 发送数据（str/bytes/dict/None）
    :param frame_mode: 帧协议，默认LENGTH_PREFIX
    :param length_field_size: 长度前缀宽度（位数）
    :param radix: 长度前缀数字进制（10或16），默认10
    :param include_length_prefix: 长度值是否包含长度位自身宽度，默认不包含
    :param request_end_symbol: 请求结束符字节序列（TERMINATOR模式发送时追加）
    :param response_end_symbol: 响应结束符字节序列（TERMINATOR模式读取的停止标记）
    :param hex_string: 启用后发送数据按HEX文本解码为二进制（每2个字符1字节）
    :param send_only: 只发不收（发送后立即返回空响应，不读取对端数据）
    :param encoding: 文本编码，默认utf-8
    :param connect_timeout: 连接超时；缺省取client.connect_timeout
    :param read_timeout: 读写超时；缺省取client.default_timeout
    """

    def __init__(
            self,
            client: "AioTcpClient",
            host: str,
            port: int,
            data: Union[str, bytes, dict, None] = None,
            *,
            frame_mode: TcpFrameMode = TcpFrameMode.LENGTH_PREFIX,
            length_field_size: Optional[int] = None,
            radix: int = 10,
            include_length_prefix: bool = False,
            request_end_symbol: Optional[bytes] = None,
            response_end_symbol: Optional[bytes] = None,
            hex_string: bool = False,
            send_only: bool = False,
            encoding: str = "utf-8",
            connect_timeout: Optional[timedelta] = None,
            read_timeout: Optional[timedelta] = None,
    ):
        self.client = client
        self.host = host
        self.port = port
        self.data = data
        self.frame_mode = frame_mode
        self.length_field_size = length_field_size or client.length_field_size
        self.radix = radix
        self.include_length_prefix = include_length_prefix
        self.request_end_symbol = request_end_symbol
        self.response_end_symbol = response_end_symbol
        self.hex_string = hex_string
        self.send_only = send_only
        self.encoding = encoding
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        # 最近一次收发对端是否响应过字节：合法空帧（如0长度正文/仅结束符）为True，0字节未响应与send_only为False
        self.response_received: bool = False

    async def execute(self) -> bytes:
        """
        执行一次TCP收发，返回响应正文字节。

        :return: 响应体字节（长度前缀与结束符已在内部剥离；send_only时返回空字节），对端是否响应过字节记录于response_received
        :raises ReqInvalidException: 连接、读写或底层发送失败
        """
        body, received = await self.client.exchange(
            host=self.host,
            port=self.port,
            data=self.data,
            frame_mode=self.frame_mode,
            length_field_size=self.length_field_size,
            radix=self.radix,
            include_length_prefix=self.include_length_prefix,
            request_end_symbol=self.request_end_symbol,
            response_end_symbol=self.response_end_symbol,
            hex_string=self.hex_string,
            send_only=self.send_only,
            encoding=self.encoding,
            connect_timeout=self.connect_timeout,
            read_timeout=self.read_timeout,
        )
        self.response_received = received
        return body

    async def json_resp(self) -> Any:
        """
        收发并将响应解析为JSON。

        :return: 解析后的JSON对象；空响应返回None
        :raises ReqInvalidException: 请求侧失败
        :raises ResInvalidException: 响应无法按JSON解析
        """
        try:
            raw = await self.execute()
            if not raw:
                return None
            return orjson.loads(raw)
        except ReqInvalidException:
            raise
        except orjson.JSONDecodeError as e:
            raise ResInvalidException(message=f"TCP响应解析失败: 响应不是合法JSON: {e}")
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
            raise ResInvalidException(message=f"TCP响应解析失败: 响应无法按{self.encoding}解码: {e}")
        except Exception as e:
            raise ResInvalidException(message=f"TCP响应解析异常: {e}")

    async def bytes_resp(self) -> bytes:
        """
        收发并返回原始响应字节。

        :return: 响应体字节（长度前缀与结束符已剥离；对端未响应或send_only时为空字节）
        :raises ReqInvalidException: 连接、发送或接收失败
        """
        return await self.execute()

    async def xml_resp(self) -> Optional[str]:
        """
        收发并将响应解析为格式化XML文本。

        :return: 格式化后的XML字符串；空响应返回None
        :raises ReqInvalidException: 请求侧失败
        :raises ResInvalidException: XML语法或解析异常
        """
        try:
            raw = await self.execute()
            if not raw or not raw.strip():
                return None
            parser = etree.XMLParser(
                recover=False,
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
            raise ResInvalidException(message=f"TCP响应解析失败: 响应不是合法XML: {e}")
        except Exception as e:
            raise ResInvalidException(message=f"TCP响应解析异常: {e}")


class AioTcpClient:
    """异步TCP短连接客户端，每次调用独立建连、收发后关闭，与AsyncTcpUtils配合链式调用取响应。"""

    def __init__(
            self,
            *,
            timeout: timedelta = timedelta(seconds=30),
            connect_timeout: Optional[timedelta] = None,
            length_field_size: int = 8,
            concurrency_limit: int = 50,
            max_response_bytes: int = 10 * 1024 * 1024,
    ):
        """
        初始化客户端默认超时、帧宽与容量参数。

        :param timeout: 默认读写超时
        :param connect_timeout: 默认连接超时；缺省与timeout相同
        :param length_field_size: 长度前缀宽度（位数），默认8
        :param concurrency_limit: 并发连接上限，默认50
        :param max_response_bytes: 单次响应正文最大字节数，默认10MB
        """
        self.default_timeout = timeout
        self.connect_timeout = connect_timeout or timeout
        self.length_field_size = length_field_size
        self.concurrency_limit = concurrency_limit
        self.max_response_bytes = max_response_bytes
        self.semaphore: asyncio.Semaphore = asyncio.Semaphore(value=self.concurrency_limit)

    async def __aenter__(self) -> "AioTcpClient":
        """异步上下文进入，返回自身。"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文退出；短连接客户端无额外资源释放。"""
        return None

    async def close(self) -> None:
        """关闭会话接口，短连接无持久会话故为空操作，形态与HTTP客户端对齐。"""
        return None

    async def tcp(
            self,
            host: str,
            port: int,
            data: Union[str, bytes, dict, None] = None,
            *,
            frame_mode: TcpFrameMode = TcpFrameMode.LENGTH_PREFIX,
            length_field_size: Optional[int] = None,
            radix: int = 10,
            include_length_prefix: bool = False,
            request_end_symbol: Optional[bytes] = None,
            response_end_symbol: Optional[bytes] = None,
            hex_string: bool = False,
            send_only: bool = False,
            encoding: str = "utf-8",
            connect_timeout: Optional[timedelta] = None,
            read_timeout: Optional[timedelta] = None,
    ) -> AsyncTcpUtils:
        """
        构造一次TCP请求调度对象，供链式调用取响应。

        :param host: 目标主机
        :param port: 目标端口
        :param data: 发送内容
        :param frame_mode: 帧协议，见TcpFrameMode
        :param length_field_size: 长度前缀宽度（位数）；缺省用客户端默认值
        :param radix: 长度前缀数字进制（10或16）
        :param include_length_prefix: 长度值是否包含长度位自身宽度
        :param request_end_symbol: 请求结束符字节序列
        :param response_end_symbol: 响应结束符字节序列
        :param hex_string: 发送数据按HEX文本解码为二进制
        :param send_only: 只发不收
        :param encoding: 文本编码
        :param connect_timeout: 连接超时
        :param read_timeout: 读写超时
        :return: AsyncTcpUtils实例
        """
        return AsyncTcpUtils(
            self,
            host,
            port,
            data,
            frame_mode=frame_mode,
            length_field_size=length_field_size,
            radix=radix,
            include_length_prefix=include_length_prefix,
            request_end_symbol=request_end_symbol,
            response_end_symbol=response_end_symbol,
            hex_string=hex_string,
            send_only=send_only,
            encoding=encoding,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )

    @staticmethod
    def _encode_body(data: Union[str, bytes, dict, None], encoding: str, *, hex_string: bool = False) -> bytes:
        """
        将发送数据规范为字节正文。

        :param data: 原始发送数据
        :param encoding: 字符串编码
        :param hex_string: 启用后文本按HEX解码
        :return: 正文字节
        :raises ReqInvalidException: hex_string启用但含非法字符或有效HEX字符为奇数位
        """
        if data is None:
            return b""
        if isinstance(data, bytes):
            return data
        if isinstance(data, dict):
            return orjson.dumps(data)
        text = str(data)
        if hex_string:
            compact = "".join(text.split())
            # 非法字符与奇数长度分开报错，避免偶数位非法字符被误提示为长度问题
            invalid_char = next((ch for ch in compact if ch not in "0123456789abcdefABCDEF"), None)
            if invalid_char is not None:
                raise ReqInvalidException(message=f"HEX报文格式非法, 启用Hex String后报文只能包含0-9/a-f/A-F字符, 首个非法字符: {invalid_char!r}")
            if len(compact) % 2 != 0:
                raise ReqInvalidException(message=f"HEX报文格式非法, 启用Hex String后去空格的有效HEX字符需为偶数位, 当前长度: {len(compact)}")
            return bytes.fromhex(compact)
        return text.encode(encoding)

    @staticmethod
    def _format_length_prefix(length_value: int, radix: int, length_field_size: int, encoding: str) -> bytes:
        """
        按进制与宽度生成文本数字长度前缀。

        :param length_value: 待写入前缀的长度数值
        :param radix: 进制（10或16）
        :param length_field_size: 前缀宽度（位数）
        :param encoding: 文本编码
        :return: 前缀字节（固定宽度个字符，对齐JMeter为文本数字而非二进制整数）
        :raises ReqInvalidException: 进制非法或长度数值按指定进制所需位数超出前缀宽度
        """
        if radix not in (10, 16):
            raise ReqInvalidException(message=f"长度前缀进制非法, 仅支持10/16进制, 当前: {radix}")
        text = format(length_value, "x" if radix == 16 else "d").zfill(length_field_size)
        if len(text) > length_field_size:
            raise ReqInvalidException(message=f"长度前缀位数非法, 按{radix}进制需要{len(text)}位, 超出宽度{length_field_size}")
        return text.encode(encoding)

    def _build_payload(
            self,
            data: Union[str, bytes, dict, None],
            frame_mode: TcpFrameMode,
            length_field_size: int,
            encoding: str,
            *,
            radix: int = 10,
            include_length_prefix: bool = False,
            request_end_symbol: Optional[bytes] = None,
            hex_string: bool = False,
    ) -> bytes:
        """
        按帧模式组装待发送报文。

        :param data: 发送数据
        :param frame_mode: 帧协议
        :param length_field_size: 长度前缀宽度（位数）
        :param encoding: 文本编码
        :param radix: 长度前缀数字进制（10或16）
        :param include_length_prefix: 长度值是否包含长度位自身宽度
        :param request_end_symbol: 请求结束符字节序列（TERMINATOR模式追加在正文末尾）
        :param hex_string: 发送数据按HEX文本解码为二进制
        :return: 完整待发送字节（含可选长度前缀/结束符）
        :raises ReqInvalidException: HEX格式非法、长度前缀溢出
        """
        body = self._encode_body(data, encoding, hex_string=hex_string)
        if frame_mode == TcpFrameMode.LENGTH_PREFIX:
            length_value = len(body) + length_field_size if include_length_prefix else len(body)
            prefix = self._format_length_prefix(length_value, radix, length_field_size, encoding)
            return prefix + body
        if frame_mode == TcpFrameMode.TERMINATOR:
            return body + request_end_symbol if request_end_symbol else body
        # RAW：只发正文不加帧标记（frame_mode由resolve_tcp_frame_config推导，三值枚举必居其一）
        return body

    async def _read_until_eof(self, reader: asyncio.StreamReader, read_timeout: float, max_bytes: int) -> tuple[bytes, bool]:
        """
        读至对端关闭或超时，RAW模式与未配置响应结束符的TERMINATOR模式共用。

        :param reader: 流读取器
        :param read_timeout: 单次read超时秒数
        :param max_bytes: 累计可读上限
        :return: (拼接后的响应字节, 对端是否响应过字节)；通讯级口径下一字节未收即超时/对端关闭视为对端未响应，返回空字节与False
        :raises ReqInvalidException: 超出max_bytes；已收部分字节后读超时
        """
        total = 0
        chunks: List[bytes] = []
        while True:
            try:
                chunk = await asyncio.wait_for(reader.read(65536), timeout=read_timeout)
            except asyncio.TimeoutError:
                if total == 0:
                    return b"", False
                raise ReqInvalidException(message=f"TCP响应报文接收超时(超时={read_timeout}s): 已收{total}字节后对端停止响应")
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ReqInvalidException(message=f"TCP响应报文接收失败: RAW模式读取数据超出最大限制({max_bytes} bytes)")
            chunks.append(chunk)
        return b"".join(chunks), total > 0

    async def _read_exactly(
            self,
            reader: asyncio.StreamReader,
            n: int,
            read_timeout: float,
            *,
            host: str,
            port: int,
            phase: str,
            empty_hint: str = "",
            empty_ok: bool = False,
    ) -> bytes:
        """
        读满恰好n字节，语义等价readexactly。

        :param reader: 流读取器
        :param n: 期待字节数
        :param read_timeout: 单次read超时秒数
        :param host: 目标主机（报错定位用）
        :param port: 目标端口（报错定位用）
        :param phase: 读取阶段描述（如长度前缀/响应正文）
        :param empty_hint: 一字节未收且判定失败时附加的排查指引，缺省不附加（首段0字节容忍成功无需指引）
        :param empty_ok: 首段读取0字节容忍开关，属读取阶段语义而非帧模式限制：True时超时/对端关闭且一字节未收
                         返回空字节按通讯级口径判定访达成功，与TERMINATOR/RAW读取器的0字节容忍同口径；
                         长度前缀模式读前缀传True，前缀已收后读正文必须为False（对端已响应而承诺正文缺失=协议异常）；
                         已收部分字节一律报错
        :return: 读满的n字节；增量累积，超时/提前关闭时报错回显实收字节数
        :raises ReqInvalidException: 读超时或对端提前关闭
        """
        chunks: List[bytes] = []
        received = 0
        while received < n:
            try:
                chunk = await asyncio.wait_for(reader.read(n - received), timeout=read_timeout)
            except asyncio.TimeoutError:
                if empty_ok and received == 0:
                    return b""
                detail = f", {empty_hint}" if received == 0 and empty_hint else ""
                raise ReqInvalidException(
                    message=f"TCP响应报文读取{phase}超时({host}:{port}, 超时={read_timeout}s): 期待{n}字节, 收到{received}字节{detail}"
                )
            if not chunk:
                if empty_ok and received == 0:
                    return b""
                detail = f", {empty_hint}" if received == 0 and empty_hint else ""
                raise ReqInvalidException(
                    message=f"TCP响应报文读取{phase}失败: 对端提前关闭连接({host}:{port}): 期待{n}字节, 收到{received}字节{detail}"
                )
            chunks.append(chunk)
            received += len(chunk)
        return b"".join(chunks)

    async def _read_until_symbol(
            self,
            reader: asyncio.StreamReader,
            symbol: bytes,
            read_timeout: float,
            max_bytes: int,
            *,
            host: str,
            port: int,
    ) -> tuple[bytes, bool]:
        """
        增量读取至结束符。

        :param reader: 流读取器
        :param symbol: 结束符字节序列
        :param read_timeout: 单次read超时秒数
        :param max_bytes: 累计可读上限
        :param host: 目标主机（报错定位用）
        :param port: 目标端口（报错定位用）
        :return: (结束符前的响应字节, 对端是否响应过字节)；仅收到结束符的空帧为(b"", True)，超时/对端关闭且0字节为(b"", False)
        :raises ReqInvalidException: 超出读取上限、已收字节未匹配结束符
        """
        buf = bytearray()
        while True:
            try:
                chunk = await asyncio.wait_for(reader.read(65536), timeout=read_timeout)
            except asyncio.TimeoutError:
                if not buf:
                    return b"", False
                raise ReqInvalidException(
                    message=f"TCP响应报文读取超时({host}:{port}, 超时={read_timeout}s): 已收{len(buf)}字节未匹配到结束符"
                )
            if not chunk:
                if not buf:
                    return b"", False
                raise ReqInvalidException(message=f"TCP响应报文接收失败: 对端提前关闭连接({host}:{port}), 已读{len(buf)}字节未匹配到结束符")
            buf += chunk
            if len(buf) > max_bytes:
                raise ReqInvalidException(message=f"TCP响应报文接收失败: 响应体积超出最大限制({max_bytes} bytes)仍未读到结束符({host}:{port})")
            scan_from = max(0, len(buf) - len(chunk) - len(symbol) + 1)
            idx = buf.find(symbol, scan_from)
            if idx >= 0:
                return bytes(buf[:idx]), True

    def _parse_response_length(
            self,
            length_bytes: bytes,
            length_field_size: int,
            radix: int,
            encoding: str,
            *,
            include_length_prefix: bool,
    ) -> int:
        """
        解析并校验响应长度前缀，返回正文字节数。单次调用，仅用于主干解耦，无复用意图。

        :param length_bytes: 已读满的长度前缀字节
        :param length_field_size: 长度前缀宽度（位数）
        :param radix: 长度前缀数字进制（10 或 16）
        :param encoding: 文本编码
        :param include_length_prefix: 长度值是否包含长度位自身宽度
        :return: 正文字节数（已按总长度口径扣除长度位自身宽度）
        :raises ReqInvalidException: 前缀非指定进制文本数字、扣除后为负、超出响应体积上限
        """
        length_str = length_bytes.decode(encoding, errors="ignore").strip()
        try:
            length = int(length_str, radix)
        except ValueError:
            raise ReqInvalidException(
                message=f"TCP响应报文接收失败: 长度前缀非法, 期待{length_field_size}位{radix}进制文本数字, "
                        f"实收内容(HEX): {length_bytes.hex(' ')}, "
                        f"请确认帧模式/进制/长度位宽度/编码是否与对端协议一致"
            )
        if include_length_prefix:
            length -= length_field_size
        if length < 0:
            raise ReqInvalidException(message="TCP响应报文接收失败: 长度前缀非法, 扣除长度位自身宽度后为负, 请确认总长度口径(是否包含长度位)")
        if length > self.max_response_bytes:
            raise ReqInvalidException(
                message=f"TCP响应报文接收失败: 长度前缀指示正文{length}字节, 超出响应体积最大限制({self.max_response_bytes} bytes)")
        return length

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
            radix: int = 10,
            include_length_prefix: bool = False,
            request_end_symbol: Optional[bytes] = None,
            response_end_symbol: Optional[bytes] = None,
            hex_string: bool = False,
            send_only: bool = False,
    ) -> tuple[bytes, bool]:
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
        :param radix: 长度前缀数字进制（10或16）
        :param include_length_prefix: 长度值是否包含长度位自身宽度
        :param request_end_symbol: 请求结束符字节序列
        :param response_end_symbol: 响应结束符字节序列
        :param hex_string: 发送数据按HEX文本解码为二进制
        :param send_only: 只发不收（发送后立即返回空字节）
        :return: (响应正文字节, 对端是否响应过字节)，正文不含长度前缀与结束符；通讯级口径对齐JMeter：对端未响应任何数据（0字节读超时/对端关闭）视为访达成功返回空字节与False，合法空帧（0长度正文/仅结束符）返回空字节与True，部分字节/非法帧/连接异常仍失败；send_only返回空字节与False
        :raises ReqInvalidException: 连接失败、超时、长度非法、响应过大、HEX非法等
        """
        conn_timeout = (connect_timeout or self.connect_timeout).total_seconds()
        read_to = (read_timeout or self.default_timeout).total_seconds()
        if conn_timeout <= 0:
            raise ReqInvalidException(message=f"TCP连接超时配置必须大于0秒, 当前: {conn_timeout}")
        if read_to <= 0:
            raise ReqInvalidException(message=f"TCP响应超时配置必须大于0秒, 当前: {read_to}")

        payload = self._build_payload(
            data,
            frame_mode,
            length_field_size,
            encoding,
            radix=radix,
            include_length_prefix=include_length_prefix,
            request_end_symbol=request_end_symbol,
            hex_string=hex_string,
        )
        async with self.semaphore:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        host=host,
                        port=port,
                        limit=max(self.max_response_bytes, 65536)
                    ),
                    timeout=conn_timeout,
                )
            except Exception as e:
                raise ReqInvalidException(message=f"TCP连接建立失败({host}:{port}, 连接超时={conn_timeout}s): {e}")

            try:
                try:
                    writer.write(payload)
                    await asyncio.wait_for(writer.drain(), timeout=read_to)
                except asyncio.TimeoutError:
                    raise ReqInvalidException(message=f"TCP请求报文发送超时({host}:{port}, 超时={read_to}s): 报文未完整写入, 请检查环境配置是否可达")
                except Exception as e:
                    raise ReqInvalidException(message=f"TCP请求报文发送失败({host}:{port}): {e}")
                if send_only:
                    return b"", False

                if frame_mode == TcpFrameMode.LENGTH_PREFIX:
                    length_bytes = await self._read_exactly(
                        reader=reader,
                        n=length_field_size,
                        read_timeout=read_to,
                        host=host,
                        port=port,
                        phase="长度前缀",
                        empty_ok=True,
                    )
                    # 通讯级：对端未响应任何数据视为访达成功（连接建立+请求发送完成），空响应
                    if not length_bytes:
                        return b"", False
                    length = self._parse_response_length(
                        length_bytes=length_bytes,
                        length_field_size=length_field_size,
                        radix=radix,
                        encoding=encoding,
                        include_length_prefix=include_length_prefix,
                    )
                    # 前缀已收即对端已响应，0长度正文属合法空帧
                    body = await self._read_exactly(
                        reader=reader,
                        n=length,
                        read_timeout=read_to,
                        host=host,
                        port=port,
                        phase="响应正文",
                        empty_hint="长度前缀已接收, 但对端未响应正文数据: 请确认帧模式/进制/长度位宽度/编码是否与对端协议一致",
                    )
                    return body, True

                if frame_mode == TcpFrameMode.TERMINATOR:
                    if response_end_symbol:
                        return await self._read_until_symbol(
                            reader=reader,
                            symbol=response_end_symbol,
                            read_timeout=read_to,
                            max_bytes=self.max_response_bytes,
                            host=host,
                            port=port,
                        )
                    return await self._read_until_eof(reader, read_to, self.max_response_bytes)

                # RAW：读至对端关闭（frame_mode由resolve_tcp_frame_config推导，三值枚举必居其一）
                return await self._read_until_eof(reader, read_to, self.max_response_bytes)
            except ReqInvalidException:
                raise
            except Exception as e:
                raise ReqInvalidException(message=f"TCP请求异常({host}:{port}): {e}")
            finally:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    # 对端RST等关闭异常不影响已完成的收发结论，静默清理
                    pass


class AsyncTcpConnection:
    """
    长连接TCP封装，同一条连接上按长度前缀帧多次发送接收。

    :param host: TCP服务主机地址
    :param port: TCP服务端口
    :param length_field_size: 长度前缀宽度（位数）
    :param retries: 自动重连剩余次数（auto_reconnect=True时生效）
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
        建立到目标主机的TCP连接。

        :raises ReqInvalidException: 连接失败或超时且无法重连
        """
        await self._connection()

    async def _connection(self) -> None:
        """
        实际建连，超时且开启自动重连时转入_reconnection。

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
                raise ReqInvalidException(
                    message=f"TCP连接建立失败: 连接超时({self.host}:{self.port}, 超时={self.timeout.total_seconds()}s), 请检查环境配置是否可达"
                )
        except Exception as e:
            raise ReqInvalidException(message=f"TCP连接建立异常({self.host}:{self.port}): {e}")

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

        :param data: 发送内容（str/bytes/dict）
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
        按行读取类HTTP头直至空行。

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
        按长度前缀帧读取一帧。

        :return: JSON对象或文本字符串，优先尝试JSON解析失败则返回文本
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
        except asyncio.TimeoutError:
            raise ReqInvalidException(
                message=f"TCP响应报文接收失败: 长度前缀读取超时({self.host}:{self.port}, 超时={self.timeout.total_seconds()}s)"
            )
        length_str = length_data.decode(self.encoding, errors="ignore").strip()
        if not length_str.isdigit():
            raise ReqInvalidException(message=f"TCP响应报文接收失败: 长度前缀非法, 期待十进制文本数字, 实收: {length_str!r}")
        length = int(length_str)
        if length > self.max_response_bytes:
            raise ReqInvalidException(message=f"TCP响应报文接收失败: 响应体积超出最大限制: {self.max_response_bytes} bytes")
        try:
            data = await asyncio.wait_for(
                self.reader.readexactly(length),
                timeout=self.timeout.total_seconds(),
            )
        except asyncio.TimeoutError:
            raise ReqInvalidException(
                message=f"TCP响应报文接收失败: 响应正文读取超时({self.host}:{self.port}, 超时={self.timeout.total_seconds()}s)"
            )
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


async def tcp_json(host: str, port: int, data: dict, *, client: Optional[AioTcpClient] = None, **kwargs: Any) -> Any:
    """
    短连接便捷函数，等价于AioTcpClient().tcp(...).json_resp()。

    :param host: 目标主机
    :param port: 目标端口
    :param data: JSON请求体（dict）
    :param client: 可选复用的AioTcpClient；未传则临时创建并在finally中close
    :param kwargs: 透传至tcp（如frame_mode/encoding/超时等）
    :return: 解析后的JSON响应
    :raises ReqInvalidException: 请求侧失败
    :raises ResInvalidException: 响应非合法JSON
    """
    own = client is None
    cli = client or AioTcpClient()
    try:
        utils = await cli.tcp(host, port, data, **kwargs)
        return await utils.json_resp()
    finally:
        if own:
            await cli.close()
