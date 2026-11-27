# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_tcp_test_schema
@DateTime: 2026/11/19 10:00:00
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from backend.enums import AutoTestTcpDatagramLength, AutoTestTcpEndSymbol, AutoTestTcpRadix


class AutoTestTcpTestServerStartIn(BaseModel):
    """
    TCP测试服务器端口启动入参：仅内置声明使用，/start无外部入参。
    """
    # mock_type非空时为业务mock端口(json/xml)，空时为帧诊断端口；
    # tcp_*字段取值与步骤schema完全一致且相互独立不互斥，帧模式复用resolve_tcp_frame_config按优先级推导：
    # 进制数≠不使用→长度前缀，结束符字段保留不参与成帧；进制数=不使用且配置结束符→结束符；均未配置→RAW
    # behavior为帧诊断端口的响应行为模拟（缺省echo回显），用于验证客户端tcp_async_utils的收发判定口径

    port: int = Field(ge=1, le=65535, description="监听端口")
    mock_type: Optional[str] = Field(default=None, description="业务mock类型：json=银行账户交易查询，xml=贷款申请；空为帧诊断回显端口")
    tcp_radix: Optional[AutoTestTcpRadix] = Field(default=None, description="TCP报文头进制数")
    tcp_radix_length: Optional[int] = Field(default=None, ge=2, le=10, description="TCP长度位宽度")
    tcp_datagram_length: Optional[AutoTestTcpDatagramLength] = Field(default=None, description="TCP报文总长度")
    tcp_request_end_symbol: Optional[AutoTestTcpEndSymbol] = Field(default=None, description="TCP请求报文结束符")
    tcp_response_end_symbol: Optional[str] = Field(default=None, max_length=64, description="TCP响应报文结束符(自定义文本, 无或空=不使用)")
    tcp_hex_string: Optional[bool] = Field(default=None, description="TCP HEX报文开关")
    tcp_encoding: Optional[str] = Field(default=None, max_length=32, description="TCP文本编码")
    response_text: Optional[str] = Field(default=None, max_length=65536, description="响应报文内容；缺省回显请求内容")
    behavior: Optional[Literal[
        "echo", "silent", "close", "empty_frame", "partial",
        "prefix_no_body", "oversize_prefix", "invalid_prefix", "delay",
    ]] = Field(default=None,
               description="响应行为模拟：缺省echo回显；silent读后不回复/close读后即关/empty_frame合法空帧/partial部分字节/prefix_no_body前缀缺正文/oversize_prefix前缀超限/invalid_prefix非法前缀/delay延迟响应")
    delay_seconds: Optional[float] = Field(default=None, ge=1, le=30, description="delay行为的延迟秒数，缺省6秒")

    @field_validator("mock_type")
    @classmethod
    def _validate_mock_type(cls, v: Optional[str]) -> Optional[str]:
        """
        校验mock类型仅允许json/xml/null。

        :param v: mock类型
        :return: 规范化后的mock类型
        """
        if v is not None and v not in ("json", "xml"):
            raise ValueError("参数[mock_type]仅允许json、xml、null")
        return v


DEFAULT_TCP_TEST_SERVER_CONFIGS: List[AutoTestTcpTestServerStartIn] = [
    # 9091 业务mock：帧自动检测(8位十进制长度前缀/RAW) | JSON银行交易查询请求→JSON响应(嵌套对象+交易列表+汇总)
    AutoTestTcpTestServerStartIn(port=9091, mock_type="json"),
    # 9092 业务mock：帧自动检测(8位十进制长度前缀/RAW) | XML贷款申请请求→XML审批响应
    AutoTestTcpTestServerStartIn(port=9092, mock_type="xml"),
    # 9093 帧诊断：10进制/8位长度位/不包含长度位 | 回显响应
    AutoTestTcpTestServerStartIn(
        port=9093,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE
    ),
    # 9094 帧诊断：16进制/4位长度位/包含长度位 | 回显响应
    AutoTestTcpTestServerStartIn(
        port=9094,
        tcp_radix=AutoTestTcpRadix.HEX,
        tcp_radix_length=4,
        tcp_datagram_length=AutoTestTcpDatagramLength.INCLUDE
    ),
    # 9095 帧诊断：进制不使用/请求与响应结束符\r\n | 回显响应
    AutoTestTcpTestServerStartIn(
        port=9095,
        tcp_radix=AutoTestTcpRadix.NONE,
        tcp_request_end_symbol=AutoTestTcpEndSymbol.CRLF,
        tcp_response_end_symbol="\\r\\n"
    ),
    # 9096 帧诊断：10进制/8位长度位/不包含长度位/HEX报文开启 | 回显响应
    AutoTestTcpTestServerStartIn(
        port=9096,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE,
        tcp_hex_string=True
    ),
    # 9097 帧诊断：10进制/8位长度位/不包含长度位/GBK编码 | 回显响应
    AutoTestTcpTestServerStartIn(
        port=9097,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE,
        tcp_encoding="GBK"
    ),
    # 9098 帧诊断：RAW(进制不使用且无结束符) | 报文原样回显
    AutoTestTcpTestServerStartIn(
        port=9098,
        tcp_radix=AutoTestTcpRadix.NONE
    ),
    # 9099 帧诊断：10进制/8位长度位/不包含长度位+结束符\r\n共存(推导按优先级取长度前缀) | 回显响应
    AutoTestTcpTestServerStartIn(
        port=9099,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE,
        tcp_request_end_symbol=AutoTestTcpEndSymbol.CRLF,
        tcp_response_end_symbol="\\r\\n"
    ),
    # 9100 行为模拟：10进制/8位长度位/不包含长度位 | silent读后不回复(客户端首段0字节容忍→成功, response_received=False)
    AutoTestTcpTestServerStartIn(
        port=9100,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE,
        behavior="silent"
    ),
    # 9101 行为模拟：RAW | close读后即关不回复(客户端EOF 0字节容忍→成功, response_received=False)
    AutoTestTcpTestServerStartIn(
        port=9101,
        tcp_radix=AutoTestTcpRadix.NONE,
        behavior="close"
    ),
    # 9102 行为模拟：10进制/8位长度位/不包含长度位 | 仅回0长度前缀(合法空帧→成功, response_received=True)
    AutoTestTcpTestServerStartIn(
        port=9102,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE,
        behavior="empty_frame"
    ),
    # 9103 行为模拟：结束符\r\n | 仅回响应结束符(合法空帧→成功, response_received=True)
    AutoTestTcpTestServerStartIn(
        port=9103,
        tcp_radix=AutoTestTcpRadix.NONE,
        tcp_request_end_symbol=AutoTestTcpEndSymbol.CRLF,
        tcp_response_end_symbol="\\r\\n",
        behavior="empty_frame"
    ),
    # 9104 行为模拟：10进制/8位长度位/不包含长度位 | 前缀声明100字节只发10字节后关闭(客户端失败:对端提前关闭)
    AutoTestTcpTestServerStartIn(
        port=9104,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE,
        behavior="partial"
    ),
    # 9105 行为模拟：结束符\r\n | 发10字节无结束符后关闭(客户端失败:未匹配到结束符)
    AutoTestTcpTestServerStartIn(
        port=9105,
        tcp_radix=AutoTestTcpRadix.NONE,
        tcp_request_end_symbol=AutoTestTcpEndSymbol.CRLF,
        tcp_response_end_symbol="\\r\\n",
        behavior="partial"
    ),
    # 9106 行为模拟：10进制/8位长度位/不包含长度位 | 前缀声明100字节不发正文即关闭(客户端失败:承诺正文缺失)
    AutoTestTcpTestServerStartIn(
        port=9106,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE,
        behavior="prefix_no_body"
    ),
    # 9107 行为模拟：10进制/8位长度位/不包含长度位 | 前缀声明正文超10MB上限仅发前缀(客户端失败:超出体积限制)
    AutoTestTcpTestServerStartIn(
        port=9107,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE,
        behavior="oversize_prefix"
    ),
    # 9108 行为模拟：10进制/8位长度位/不包含长度位 | 回非数字前缀XXXXXXXX后关闭(客户端失败:长度前缀非法)
    AutoTestTcpTestServerStartIn(
        port=9108,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE,
        behavior="invalid_prefix"
    ),
    # 9109 行为模拟：RAW | 先发一半字节再延迟6秒发剩余(客户端read_timeout<6s时接收阶段超时失败)
    AutoTestTcpTestServerStartIn(
        port=9109,
        tcp_radix=AutoTestTcpRadix.NONE,
        behavior="delay",
        delay_seconds=6
    ),
    # 9110 行为模拟：10进制/8位长度位/不包含长度位 | 延迟6秒才发前缀(客户端read_timeout<6s时首段0字节容忍→成功)
    AutoTestTcpTestServerStartIn(
        port=9110,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE,
        behavior="delay",
        delay_seconds=6
    ),
]
