# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_tcp_test_schema
@DateTime: 2026/11/19 10:00:00
"""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from backend.enums import AutoTestTcpDatagramLength, AutoTestTcpEndSymbol, AutoTestTcpRadix


class AutoTestTcpTestServerStartIn(BaseModel):
    """
    TCP测试服务器端口启动入参：仅内置声明使用，/start无外部入参。
    """
    # mock_type非空时为业务mock端口(json/xml)，空时为帧诊断回显端口；
    # tcp_*字段取值与步骤schema完全一致且相互独立不互斥，帧模式复用resolve_tcp_frame_config按优先级推导：
    # 进制数≠不使用→长度前缀，结束符字段保留不参与成帧；进制数=不使用且配置结束符→结束符；均未配置→RAW

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
    # 业务mock端口：JSON请求(银行账户交易查询→XML响应)、XML请求(贷款申请→XML响应)，帧自动检测(8位十进制长度前缀/RAW)
    AutoTestTcpTestServerStartIn(port=9091, mock_type="json"),
    AutoTestTcpTestServerStartIn(port=9092, mock_type="xml"),
    # TCP协议：10进制/8位长度位/不包含长度位
    AutoTestTcpTestServerStartIn(
        port=9093,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE
    ),
    # TCP协议：16进制/4位长度位/包含长度位
    AutoTestTcpTestServerStartIn(
        port=9094,
        tcp_radix=AutoTestTcpRadix.HEX,
        tcp_radix_length=4,
        tcp_datagram_length=AutoTestTcpDatagramLength.INCLUDE
    ),
    # TCP协议：进制数不使用，请求/响应结束符\r\n
    AutoTestTcpTestServerStartIn(
        port=9095,
        tcp_radix=AutoTestTcpRadix.NONE,
        tcp_request_end_symbol=AutoTestTcpEndSymbol.CRLF,
        tcp_response_end_symbol="\\r\\n"
    ),
    # TCP协议：10进制/8位/不包含长度位/HEX开启
    AutoTestTcpTestServerStartIn(
        port=9096,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE,
        tcp_hex_string=True
    ),
    # TCP协议：10进制/8位/不包含长度位/GBK编码
    AutoTestTcpTestServerStartIn(
        port=9097,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE,
        tcp_encoding="GBK"
    ),
    # TCP协议：进制数不使用且无结束符，报文原样收发
    AutoTestTcpTestServerStartIn(
        port=9098,
        tcp_radix=AutoTestTcpRadix.NONE
    ),
    # TCP协议：帧字段共存组合（进制数与结束符不互斥）：推导按优先级取长度前缀，结束符保留不参与成帧
    AutoTestTcpTestServerStartIn(
        port=9099,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE,
        tcp_request_end_symbol=AutoTestTcpEndSymbol.CRLF,
        tcp_response_end_symbol="\\r\\n"
    ),
]