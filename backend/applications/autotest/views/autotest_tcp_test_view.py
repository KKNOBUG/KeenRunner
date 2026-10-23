# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_tcp_test_view
@DateTime: 2026/7/21 10:00:00
"""
import asyncio
import datetime
import traceback
from typing import Any, Callable, Dict, List, Optional

import orjson
from fastapi import APIRouter
from lxml import etree
from pydantic import BaseModel, Field, field_validator

from backend.applications.autotest.services.autotest_runtime.protocol_tcp import (
    TCP_MAX_RESPONSE_BYTES,
    resolve_tcp_frame_config,
    tcp_enum_value,
)
from backend.common import TcpFrameMode
from backend.configure import LOGGER, PROJECT_CONFIG
from backend.core.responses import SuccessResponse, FailureResponse
from backend.enums import AutoTestTcpDatagramLength, AutoTestTcpEndSymbol, AutoTestTcpRadix

autotest_tcp_test = APIRouter()


# ---------------------------------------------------------------------------
# 启动入参 Schema 与内置端口组合
# ---------------------------------------------------------------------------

class _TcpFrameServerStartIn(BaseModel):
    """
    TCP测试服务器端口启动入参（内置声明用，/start无外部入参）。

    mock_type非空时为业务mock端口（json/xml），空时为帧诊断回显端口；
    tcp_*字段取值与步骤schema完全一致且相互独立不互斥，帧模式复用 resolve_tcp_frame_config 按优先级推导
    （进制数≠不使用 → 长度前缀，结束符字段保留但不参与成帧；进制数=不使用且配置了结束符 → 结束符；均未配置 → RAW）。
    """

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


_DEFAULT_FRAME_CONFIGS: List[_TcpFrameServerStartIn] = [
    # 业务mock端口：JSON请求(银行账户交易查询→XML响应)、XML请求(贷款申请→XML响应)，帧自动检测(8位十进制长度前缀/RAW)
    _TcpFrameServerStartIn(port=9091, mock_type="json"),
    _TcpFrameServerStartIn(port=9092, mock_type="xml"),
    # TCP协议：10进制/8位长度位/不包含长度位
    _TcpFrameServerStartIn(
        port=9093,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE
    ),
    # TCP协议：16进制/4位长度位/包含长度位
    _TcpFrameServerStartIn(
        port=9094,
        tcp_radix=AutoTestTcpRadix.HEX,
        tcp_radix_length=4,
        tcp_datagram_length=AutoTestTcpDatagramLength.INCLUDE
    ),
    # TCP协议：进制数不使用，请求/响应结束符\r\n
    _TcpFrameServerStartIn(
        port=9095,
        tcp_radix=AutoTestTcpRadix.NONE,
        tcp_request_end_symbol=AutoTestTcpEndSymbol.CRLF,
        tcp_response_end_symbol="\\r\\n"
    ),
    # TCP协议：10进制/8位/不包含长度位/HEX开启
    _TcpFrameServerStartIn(
        port=9096,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE,
        tcp_hex_string=True
    ),
    # TCP协议：10进制/8位/不包含长度位/GBK编码
    _TcpFrameServerStartIn(
        port=9097,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE,
        tcp_encoding="GBK"
    ),
    # TCP协议：进制数不使用且无结束符，报文原样收发
    _TcpFrameServerStartIn(
        port=9098,
        tcp_radix=AutoTestTcpRadix.NONE
    ),
    # TCP协议：帧字段共存组合（进制数与结束符不互斥）：推导按优先级取长度前缀，结束符保留不参与成帧
    _TcpFrameServerStartIn(
        port=9099,
        tcp_radix=AutoTestTcpRadix.DECIMAL,
        tcp_radix_length=8,
        tcp_datagram_length=AutoTestTcpDatagramLength.EXCLUDE,
        tcp_request_end_symbol=AutoTestTcpEndSymbol.CRLF,
        tcp_response_end_symbol="\\r\\n"
    ),
]


# ---------------------------------------------------------------------------
# 业务 Mock 响应构造（无状态纯函数：JSON请求→银行交易查询XML / XML请求→贷款审批XML）
# ---------------------------------------------------------------------------

_MOCK_ACCOUNT_BALANCE = 125680.50

_TRANSACTION_TEMPLATES: List[Dict[str, Any]] = [
    {"date_offset": 0, "time": "09:30:00", "amount": 5000.00, "type": "存入", "sub_type": "工资", "description": "7月工资入账",
     "counterparty": "某科技有限公司", "channel": "企业网银"},
    {"date_offset": 1, "time": "14:20:30", "amount": 3200.00, "type": "支出", "sub_type": "消费", "description": "商场购物",
     "counterparty": "某商场", "channel": "手机银行"},
    {"date_offset": 4, "time": "10:15:00", "amount": 20000.00, "type": "存入", "sub_type": "转账", "description": "李四转账",
     "counterparty": "李四", "channel": "手机银行"},
    {"date_offset": 9, "time": "16:45:20", "amount": 1500.00, "type": "支出", "sub_type": "水电费", "description": "7月水电费",
     "counterparty": "供电局", "channel": "自动扣款"},
    {"date_offset": 14, "time": "11:00:00", "amount": 800.00, "type": "支出", "sub_type": "取现", "description": "ATM取现",
     "counterparty": "ATM-001", "channel": "ATM"},
    {"date_offset": 19, "time": "08:50:00", "amount": 12000.00, "type": "存入", "sub_type": "理财收益", "description": "理财产品到期",
     "counterparty": "某基金公司", "channel": "网银"},
    {"date_offset": 24, "time": "15:30:00", "amount": 680.00, "type": "支出", "sub_type": "通讯费", "description": "手机话费充值",
     "counterparty": "中国移动", "channel": "手机银行"},
    {"date_offset": 29, "time": "12:00:00", "amount": 3000.00, "type": "支出", "sub_type": "转账", "description": "转账给王五",
     "counterparty": "王五", "channel": "手机银行"},
]

_LOAN_TERMS: List[str] = [
    "根据月等额本息还款",
    "提前还款需支付剩余本金2%违约金",
    "逾期罚息为日利率0.05%",
    "贷款发放后30天内不可提前还款",
]


def _build_error_xml(message: str) -> str:
    """
    构造mock服务器统一错误响应报文。

    :param message: 错误描述
    :return: 错误响应XML文本
    """
    root = etree.Element("Response")
    head = etree.SubElement(root, "Head")
    etree.SubElement(head, "ResponseCode").text = "999999"
    etree.SubElement(head, "ResponseMessage").text = message
    etree.SubElement(head, "ResponseTime").text = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    etree.SubElement(head, "ProcessedBy").text = "TCP_TEST_SERVER"
    return etree.tostring(root, encoding="unicode", pretty_print=True)


def _xml_text(parent: Optional[etree._Element], tag: str, default: str = "") -> str:
    """
    读取XML子节点文本，节点缺失或无文本时返回默认值。

    :param parent: 父节点
    :param tag: 子节点标签名
    :param default: 默认值
    :return: 节点文本（已去除首尾空白）
    """
    if parent is None:
        return default
    elem = parent.find(tag)
    if elem is not None and elem.text:
        return elem.text.strip()
    return default


def _generate_transactions(count: int) -> List[Dict[str, Any]]:
    """
    按模板生成递减日期与滚动余额的交易流水明细。

    :param count: 生成条数（超过模板数时取全部模板）
    :return: 交易流水列表，元素含txn_id/date/time/amount/type/sub_type/description/counterparty/channel/balance
    """
    base_date = datetime.date(2026, 7, 19)
    result = []
    balance = _MOCK_ACCOUNT_BALANCE
    for tpl in _TRANSACTION_TEMPLATES[:count]:
        txn_date = base_date - datetime.timedelta(days=tpl["date_offset"])
        date_str = txn_date.strftime("%Y-%m-%d")
        txn_id = f"TXN{date_str.replace('-', '')}{int(tpl['amount']):03d}"
        balance = balance + tpl["amount"] if tpl["type"] == "存入" else balance - tpl["amount"]
        result.append({
            "txn_id": txn_id,
            "date": date_str,
            "time": tpl["time"],
            "amount": tpl["amount"],
            "type": tpl["type"],
            "sub_type": tpl["sub_type"],
            "description": tpl["description"],
            "counterparty": tpl["counterparty"],
            "channel": tpl["channel"],
            "balance": balance,
        })
    return result


def _build_json_business_response(text: str) -> str:
    """
    构造JSON端口（银行账户交易查询）的XML响应报文。

    :param text: 请求报文JSON文本
    :return: 交易查询结果XML文本
    """
    if not text:
        return _build_error_xml("空请求")
    try:
        req: Dict[str, Any] = orjson.loads(text)
    except orjson.JSONDecodeError as e:
        return _build_error_xml(f"JSON解析失败: {e}")

    header = req.get("request_header") or req.get("header") or {}
    request_id = header.get("request_id", "UNKNOWN")
    channel = header.get("channel", "unknown")
    institution = header.get("institution", "KRUN_TEST_BANK")

    account = req.get("account_info") or req.get("account") or {}
    account_no = account.get("account_no", "6228480012345678")
    account_name = account.get("account_name", "张三")
    account_type = account.get("account_type", "savings")
    currency = account.get("currency", "CNY")
    customer_id = account.get("customer_id", "CUST00001")

    query = req.get("query_condition") or req.get("query") or {}
    page_no = query.get("page_no", 1)
    page_size = query.get("page_size", 5)

    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    transactions = _generate_transactions(page_size)
    total_income = sum(float(t["amount"]) for t in transactions if t["type"] == "存入")
    total_expense = sum(float(t["amount"]) for t in transactions if t["type"] == "支出")
    net = total_income - total_expense
    current_balance = _MOCK_ACCOUNT_BALANCE

    root = etree.Element("Response")
    head = etree.SubElement(root, "Head")
    etree.SubElement(head, "ResponseCode").text = "000000"
    etree.SubElement(head, "ResponseMessage").text = "查询成功"
    etree.SubElement(head, "RequestID").text = request_id
    etree.SubElement(head, "ResponseTime").text = now
    etree.SubElement(head, "Channel").text = channel
    etree.SubElement(head, "Institution").text = institution
    etree.SubElement(head, "ProcessedBy").text = "TCP_TEST_SERVER_JSON"

    body = etree.SubElement(root, "Body")
    acct = etree.SubElement(body, "AccountInfo")
    etree.SubElement(acct, "AccountNo").text = account_no
    etree.SubElement(acct, "AccountName").text = account_name
    etree.SubElement(acct, "AccountType").text = "储蓄账户" if account_type == "savings" else account_type
    etree.SubElement(acct, "Currency").text = currency
    etree.SubElement(acct, "CustomerID").text = customer_id
    etree.SubElement(acct, "Balance").text = f"{current_balance:.2f}"
    etree.SubElement(acct, "AvailableBalance").text = f"{current_balance - 5000:.2f}"
    etree.SubElement(acct, "OpenDate").text = "2020-03-15"
    etree.SubElement(acct, "LastTransactionDate").text = transactions[0]["date"] if transactions else ""

    txn_list = etree.SubElement(body, "TransactionList")
    txn_list.set("count", str(len(transactions)))
    for txn in transactions:
        elem = etree.SubElement(txn_list, "Transaction")
        etree.SubElement(elem, "TxnID").text = txn["txn_id"]
        etree.SubElement(elem, "Date").text = txn["date"]
        etree.SubElement(elem, "Time").text = txn["time"]
        etree.SubElement(elem, "Amount").text = f"{txn['amount']:.2f}"
        etree.SubElement(elem, "Currency").text = currency
        etree.SubElement(elem, "Type").text = txn["type"]
        etree.SubElement(elem, "SubType").text = txn["sub_type"]
        etree.SubElement(elem, "Description").text = txn["description"]
        etree.SubElement(elem, "Counterparty").text = txn["counterparty"]
        etree.SubElement(elem, "Balance").text = f"{txn['balance']:.2f}"
        etree.SubElement(elem, "Channel").text = txn["channel"]
        etree.SubElement(elem, "Status").text = "成功"

    summary = etree.SubElement(body, "Summary")
    etree.SubElement(summary, "TotalCount").text = str(len(transactions))
    etree.SubElement(summary, "TotalIncome").text = f"{total_income:.2f}"
    etree.SubElement(summary, "TotalExpense").text = f"{total_expense:.2f}"
    etree.SubElement(summary, "NetAmount").text = f"{net:.2f}"
    etree.SubElement(summary, "PageNo").text = str(page_no)
    etree.SubElement(summary, "PageSize").text = str(page_size)
    etree.SubElement(summary, "HasNextPage").text = "false"

    return etree.tostring(root, encoding="unicode", pretty_print=True)


def _build_xml_business_response(text: str) -> str:
    """
    构造XML端口（贷款申请）的XML响应报文。

    :param text: 请求报文XML文本
    :return: 贷款审批结果XML文本（含还款计划与贷款条款）
    """
    if not text:
        return _build_error_xml("空请求")
    try:
        parser = etree.XMLParser(recover=False, remove_blank_text=True, encoding="utf-8")
        root = etree.fromstring(text.encode("utf-8"), parser=parser)
    except etree.XMLSyntaxError as e:
        return _build_error_xml(f"XML解析失败: {e}")

    head_elem = root.find(".//Head") or root.find(".//head")
    body_elem = root.find(".//Body") or root.find(".//body")

    request_id = _xml_text(head_elem, "RequestID", "UNKNOWN")
    channel = _xml_text(head_elem, "Channel", "unknown")
    institution = _xml_text(head_elem, "Institution", "KRUN_TEST_BANK")

    applicant_elem = body_elem.find(".//ApplicantInfo") if body_elem is not None else None
    loan_elem = body_elem.find(".//LoanInfo") if body_elem is not None else None

    annual_income = _xml_text(applicant_elem, "AnnualIncome", "500000")
    applied_amount = float(_xml_text(loan_elem, "Amount", "200000"))
    term = int(_xml_text(loan_elem, "Term", "36"))
    repayment_method = _xml_text(loan_elem, "RepaymentMethod", "等额本息")

    # 风控决策：根据年收入和申请金额计算批准额度
    income_ratio = min(float(annual_income) / max(applied_amount, 1), 3.0)
    approved_ratio = 0.8 + 0.1 * min(income_ratio, 1.0)
    approved_amount = int(applied_amount * min(approved_ratio, 0.95))
    annual_rate = 0.0475
    monthly_rate = annual_rate / 12

    if repayment_method == "等额本息" and term > 0 and approved_amount > 0:
        monthly_payment = (
                approved_amount * monthly_rate * (1 + monthly_rate) ** term
                / ((1 + monthly_rate) ** term - 1)
        )
    else:
        monthly_payment = approved_amount / term
    total_interest = monthly_payment * term - approved_amount
    total_repayment = monthly_payment * term

    now = datetime.datetime.now()
    app_no = f"APP{now.strftime('%Y%m%d')}001"

    resp_root = etree.Element("Response")
    resp_head = etree.SubElement(resp_root, "Head")
    etree.SubElement(resp_head, "ResponseCode").text = "000000"
    etree.SubElement(resp_head, "ResponseMessage").text = "贷款申请处理成功"
    etree.SubElement(resp_head, "RequestID").text = request_id
    etree.SubElement(resp_head, "ResponseTime").text = now.strftime("%Y-%m-%dT%H:%M:%S")
    etree.SubElement(resp_head, "Channel").text = channel
    etree.SubElement(resp_head, "Institution").text = institution
    etree.SubElement(resp_head, "ProcessedBy").text = "TCP_TEST_SERVER_XML"

    resp_body = etree.SubElement(resp_root, "Body")
    approval = etree.SubElement(resp_body, "ApprovalInfo")
    etree.SubElement(approval, "ApplicationNo").text = app_no
    etree.SubElement(approval, "ApprovalStatus").text = "已批准"
    etree.SubElement(approval, "ApprovedAmount").text = f"{approved_amount:.2f}"
    etree.SubElement(approval, "AppliedAmount").text = f"{applied_amount:.2f}"
    etree.SubElement(approval, "InterestRate").text = f"{annual_rate:.4f}"
    etree.SubElement(approval, "AnnualRate").text = f"{annual_rate * 100:.2f}%"
    etree.SubElement(approval, "Term").text = str(term)
    etree.SubElement(approval, "RepaymentMethod").text = repayment_method
    etree.SubElement(approval, "MonthlyPayment").text = f"{monthly_payment:.2f}"
    etree.SubElement(approval, "TotalInterest").text = f"{total_interest:.2f}"
    etree.SubElement(approval, "TotalRepayment").text = f"{total_repayment:.2f}"
    etree.SubElement(approval, "ApprovalDate").text = now.strftime("%Y-%m-%d")
    etree.SubElement(approval, "ExpiryDate").text = (now + datetime.timedelta(days=30)).strftime("%Y-%m-%d")

    # 前 12 期还款计划（数组）
    plan = etree.SubElement(resp_body, "RepaymentPlan")
    plan.set("count", "12")
    remaining = float(approved_amount)
    for period in range(1, 13):
        interest = remaining * monthly_rate
        principal = monthly_payment - interest
        remaining -= principal
        due_date = (
                datetime.datetime.now().replace(day=20) + datetime.timedelta(days=30 * period)
        ).strftime("%Y-%m-%d")
        inst = etree.SubElement(plan, "Installment")
        etree.SubElement(inst, "Period").text = str(period)
        etree.SubElement(inst, "DueDate").text = due_date
        etree.SubElement(inst, "Principal").text = f"{principal:.2f}"
        etree.SubElement(inst, "Interest").text = f"{interest:.2f}"
        etree.SubElement(inst, "Total").text = f"{monthly_payment:.2f}"
        etree.SubElement(inst, "RemainingBalance").text = f"{remaining:.2f}"
        etree.SubElement(inst, "Status").text = "未到期"

    # 贷款条款（数组）
    terms_elem = etree.SubElement(resp_body, "Terms")
    for idx, content in enumerate(_LOAN_TERMS, 1):
        term_elem = etree.SubElement(terms_elem, "Term")
        etree.SubElement(term_elem, "Sequence").text = str(idx)
        etree.SubElement(term_elem, "Content").text = content

    # 联系方式
    contact = etree.SubElement(resp_body, "ContactInfo")
    etree.SubElement(contact, "Hotline").text = "95588"
    etree.SubElement(contact, "Email").text = "service@krun-test-bank.com"
    etree.SubElement(contact, "Website").text = "www.krun-test-bank.com"

    return etree.tostring(resp_root, encoding="unicode", pretty_print=True)


# mock端口类型→响应构造函数注册表
_TCP_MOCK_RESPONSE_BUILDERS: Dict[str, Callable[[str], str]] = {
    "json": _build_json_business_response,
    "xml": _build_xml_business_response,
}


# ---------------------------------------------------------------------------
# TCP 测试服务器实现（业务mock端口 + 帧诊断端口，统一由 _TcpFrameServerManager 编排）
# ---------------------------------------------------------------------------

async def _read_until_idle(reader: asyncio.StreamReader, idle_timeout: float) -> bytes:
    """
    无显式边界报文的收尾读取：持续读取直至静默窗口超时或对端关闭（超时按正常收尾处理而非异常）。

    :param reader: 流读取器
    :param idle_timeout: 静默窗口时长（秒）
    :return: 读取到的报文字节
    """
    chunks: List[bytes] = []
    while True:
        try:
            chunk = await asyncio.wait_for(reader.read(65536), timeout=idle_timeout)
        except asyncio.TimeoutError:
            break
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


class _TcpTestServerBase:
    """TCP测试服务器基类：收敛监听套接字生命周期与连接收尾，子类只关注业务读写。"""

    def __init__(self, label: str) -> None:
        self._label: str = label
        self._server: Optional[asyncio.base_events.Server] = None
        self._is_running: bool = False

    async def stop(self) -> None:
        """关闭监听套接字（幂等，未启动时仅归位状态）。"""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            LOGGER.info(f"{self._label}已停止")
        self._is_running = False

    @staticmethod
    async def _close_writer(writer: asyncio.StreamWriter) -> None:
        """统一连接收尾：关闭写端并等待对端确认；对端可能已先行断开，异常不外抛。"""
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


class _TcpMockServer(_TcpTestServerBase):
    """
    单端口业务 Mock TCP 服务器。

    帧自动检测（启发式）：首读为纯数字文本时按8位十进制长度前缀精确读正文，否则按RAW读到静默窗口收尾；
    响应侧与请求同帧（前缀请求回前缀响应）。业务响应报文由 _TCP_MOCK_RESPONSE_BUILDERS 按类型路由生成。
    """

    _LENGTH_FIELD_SIZE = 8
    _READ_TIMEOUT = 10.0
    _IDLE_TIMEOUT = 3.0

    def __init__(self, port: int, mock_type: str) -> None:
        super().__init__(label=f"TCP mock服务器({mock_type})端口{port}")
        self._port: int = port
        self._mock_type: str = mock_type
        self._host: str = ""
        self._conn_count: int = 0

    # -- 生命周期 ----------------------------------------------------------

    async def start(self, cfg: "_TcpFrameServerStartIn", host: str) -> Dict[str, Any]:
        """
        启动mock服务器（已运行时先停旧实例）。

        :param cfg: 保持与帧诊断服务器统一签名（端口与mock类型在构造时已确定）
        :param host: 监听地址（后端启动地址）
        :return: 服务器状态快照
        """
        await self.stop()
        self._host = host
        self._conn_count = 0
        self._server = await asyncio.start_server(self._handle_client, host, self._port)
        self._is_running = True
        LOGGER.info(f"TCP mock服务器启动: {host}:{self._port}, 类型={self._mock_type}")
        return self.status()

    def status(self) -> Dict[str, Any]:
        return {
            "is_running": self._is_running,
            "host": self._host,
            "port": self._port,
            "mock_type": self._mock_type,
            "connection_count": self._conn_count,
        }

    # -- 连接处理 --------------------------------------------------------

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._conn_count += 1
        peer = writer.get_extra_info("peername")
        LOGGER.info(f"TCP-{self._mock_type}收到连接: {peer}, 第{self._conn_count}次")
        await self._process_connection(reader, writer)

    async def _process_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        build_response = _TCP_MOCK_RESPONSE_BUILDERS[self._mock_type]
        try:
            response_xml, is_length_prefixed = await self._read_and_detect(reader, build_response)
            await self._write_framed(writer, response_xml.encode("utf-8"), is_length_prefixed)
        except Exception as e:
            LOGGER.error(f"TCP mock服务器处理异常({self._port}): {e}\n{traceback.format_exc()}")
            error_bytes = _build_error_xml(f"服务器内部错误: {e}").encode("utf-8")
            try:
                # 错误响应统一补长度前缀，保证前缀形态客户端可解帧
                await self._write_framed(writer, error_bytes, True)
            except Exception:
                pass
        finally:
            await self._close_writer(writer)

    async def _read_and_detect(self, reader: asyncio.StreamReader, build_response: Callable[[str], str]) -> tuple[str, bool]:
        """
        读取请求数据，自动检测帧协议，调用build_response构造响应。

        长度前缀路径按声明长度精确读正文；RAW/结束符路径无显式长度边界，读到静默窗口或对端关闭收尾。

        :param reader: 流读取器
        :param build_response: 业务响应构造函数
        :return: (response_xml文本, 是否长度前缀帧)
        """
        first_chunk = await asyncio.wait_for(
            reader.read(self._LENGTH_FIELD_SIZE), timeout=self._READ_TIMEOUT,
        )
        if not first_chunk:
            return build_response(""), False

        body_length = self._detect_length_prefix(first_chunk)
        if body_length is not None:
            body_bytes = await asyncio.wait_for(reader.readexactly(body_length), timeout=self._READ_TIMEOUT)
            return build_response(body_bytes.decode("utf-8", errors="ignore").strip()), True

        body_bytes = first_chunk + await _read_until_idle(reader, self._IDLE_TIMEOUT)
        return build_response(body_bytes.decode("utf-8", errors="ignore").strip()), False

    def _detect_length_prefix(self, first_chunk: bytes) -> Optional[int]:
        """
        识别首读是否为纯数字文本长度前缀。

        :param first_chunk: 首读字节
        :return: 声明正文长度；非前缀形态返回None
        """
        try:
            prefix_text = first_chunk.decode("ascii")
        except UnicodeDecodeError:
            return None
        return int(prefix_text) if prefix_text.isdigit() else None

    async def _write_framed(self, writer: asyncio.StreamWriter, payload: bytes, with_length_prefix: bool) -> None:
        """
        按帧形态写出响应报文。

        :param writer: 流写入器
        :param payload: 响应正文字节
        :param with_length_prefix: 是否补8位十进制长度前缀
        """
        if with_length_prefix:
            writer.write(str(len(payload)).zfill(self._LENGTH_FIELD_SIZE).encode("ascii"))
        writer.write(payload)
        await writer.drain()


class _TcpFrameTestServer(_TcpTestServerBase):
    """
    按帧配置收发的TCP诊断服务器：读取侧镜像客户端（AioTcpClient）的组帧逻辑，
    每次收发记录诊断快照（前缀文本/声明长度/实际长度/结束符/HEX/错误），供统一 /status 查询比对。

    用于验证TCP步骤帧配置的字段组合是否产生预期报文、响应侧解析是否按同一配置工作。
    """

    _READ_TIMEOUT = 10.0
    _IDLE_TIMEOUT = 1.0

    def __init__(self) -> None:
        super().__init__(label="TCP帧诊断服务器")
        self._host: str = ""
        self._port: int = 0
        self._frame_config: Any = None
        self._frame_desc: Dict[str, Any] = {}
        self._response_text: Optional[str] = None
        self._exchange_count: int = 0
        self._last_report: Dict[str, Any] = {}

    # -- 生命周期 ----------------------------------------------------------

    async def start(self, req: _TcpFrameServerStartIn, host: str) -> Dict[str, Any]:
        """
        按帧配置启动诊断服务器（已运行时先停旧实例）。

        :param req: 启动入参（tcp_*字段语义与步骤schema一致）
        :param host: 监听地址（与业务mock端口共用外层host）
        :return: 服务器状态快照
        """
        await self.stop()
        self._frame_config = resolve_tcp_frame_config(req)
        self._response_text = req.response_text
        self._host = host
        self._port = req.port
        self._exchange_count = 0
        self._last_report = {}
        self._frame_desc = {
            "frame_mode": self._frame_config.frame_mode.value,
            "tcp_radix": tcp_enum_value(req.tcp_radix) or "不使用",
            "tcp_radix_length": int(req.tcp_radix_length or 8),
            "tcp_datagram_length": tcp_enum_value(req.tcp_datagram_length) or "不包含长度位",
            "tcp_request_end_symbol": tcp_enum_value(req.tcp_request_end_symbol) or "无",
            "tcp_response_end_symbol": (req.tcp_response_end_symbol or "").strip() or "无",
            "tcp_hex_string": bool(req.tcp_hex_string),
            "tcp_encoding": self._frame_config.encoding,
            "response_mode": "回显请求" if req.response_text is None else "固定内容",
        }
        self._server = await asyncio.start_server(
            self._handle_client, host, req.port,
            limit=max(TCP_MAX_RESPONSE_BYTES, 65536),
        )
        self._is_running = True
        LOGGER.info(f"TCP帧诊断服务器启动: {host}:{req.port}, 帧配置: {self._frame_desc}")
        return self.status()

    def status(self) -> Dict[str, Any]:
        return {
            "is_running": self._is_running,
            "host": self._host,
            "port": self._port,
            "frame_config": self._frame_desc,
            "exchange_count": self._exchange_count,
            "last_report": self._last_report,
        }

    # -- 收发处理 ----------------------------------------------------------

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._exchange_count += 1
        cfg = self._frame_config
        report: Dict[str, Any] = {
            "exchange_no": self._exchange_count,
            "peer": str(writer.get_extra_info("peername")),
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "frame_mode": cfg.frame_mode.value,
            "radix": cfg.radix,
            "radix_length": cfg.radix_length,
            "include_length_prefix": cfg.include_length_prefix,
            "hex_string": cfg.hex_string,
            "encoding": cfg.encoding,
            "success": False,
            "errors": [],
        }
        self._last_report = report
        LOGGER.info(f"TCP帧诊断服务器收到连接: {report['peer']}, 第{self._exchange_count}次")
        try:
            body_bytes = await self._read_request(reader, report)
            report["request_bytes"] = len(body_bytes)
            report["request_hex"] = body_bytes.hex().upper()
            report["request_text"] = body_bytes.decode(cfg.encoding, errors="replace")[:4096]
            response_bytes = self._build_response(body_bytes, report)
            writer.write(response_bytes)
            await writer.drain()
            report["success"] = True
        except asyncio.IncompleteReadError as e:
            report["errors"].append(f"请求体不完整: 前缀声明的字节数不足, 已收到{len(e.partial)}字节")
        except asyncio.TimeoutError:
            report["errors"].append(f"读请求超时({self._READ_TIMEOUT}s)")
        except asyncio.LimitOverrunError:
            report["errors"].append("请求数据超过流上限仍未读到结束符")
        except ValueError as e:
            report["errors"].append(str(e))
        except Exception as e:
            report["errors"].append(f"处理异常: {type(e).__name__}: {e}")
            LOGGER.error(f"TCP帧诊断服务器处理异常: {e}\n{traceback.format_exc()}")
        finally:
            await self._close_writer(writer)

    async def _read_request(self, reader: asyncio.StreamReader, report: Dict[str, Any]) -> bytes:
        """
        按帧配置读取请求正文，逻辑镜像 AioTcpClient._build_payload 的组帧规则。

        :param reader: 流读取器
        :param report: 诊断快照（就地写入读取过程信息）
        :return: 请求正文字节
        """
        cfg = self._frame_config
        if cfg.frame_mode == TcpFrameMode.LENGTH_PREFIX:
            prefix_bytes = await asyncio.wait_for(reader.readexactly(cfg.radix_length), timeout=self._READ_TIMEOUT)
            prefix_text = prefix_bytes.decode("ascii", errors="replace")
            report["prefix_text"] = prefix_text
            try:
                declared = int(prefix_text, cfg.radix)
            except ValueError:
                raise ValueError(f"长度前缀[{prefix_text}]不是合法的{cfg.radix}进制数字")
            report["declared_length"] = declared
            if cfg.include_length_prefix and declared < cfg.radix_length:
                raise ValueError(f"声明长度[{declared}]小于长度位宽度[{cfg.radix_length}]")
            body_length = declared - cfg.radix_length if cfg.include_length_prefix else declared
            report["expect_body_length"] = body_length
            body = await asyncio.wait_for(reader.readexactly(body_length), timeout=self._READ_TIMEOUT) if body_length else b""
            report["length_match"] = True
            return body
        if cfg.frame_mode == TcpFrameMode.TERMINATOR:
            symbol = cfg.request_end_symbol
            if symbol is None:
                raise ValueError("结束符模式缺少请求结束符配置")
            data = await asyncio.wait_for(reader.readuntil(symbol), timeout=self._READ_TIMEOUT)
            report["terminator_found"] = True
            return data[:-len(symbol)]
        # RAW请求无显式边界；客户端保持连接等待响应不会主动EOF，按静默窗口收尾
        return await _read_until_idle(reader, self._IDLE_TIMEOUT)

    def _build_response(self, body_bytes: bytes, report: Dict[str, Any]) -> bytes:
        """
        按帧配置组装响应报文（客户端响应读取依赖同一帧规则）。

        :param body_bytes: 请求正文（response_text未配置时用于回显）
        :param report: 诊断快照（就地写入响应信息）
        :return: 响应报文字节
        """
        cfg = self._frame_config
        out = body_bytes if self._response_text is None else self._response_text.encode(cfg.encoding, errors="replace")
        report["response_bytes"] = len(out)
        if cfg.frame_mode == TcpFrameMode.LENGTH_PREFIX:
            value = len(out) + cfg.radix_length if cfg.include_length_prefix else len(out)
            prefix = format(value, "d" if cfg.radix == 10 else "x").zfill(cfg.radix_length).encode("ascii")
            report["response_prefix"] = prefix.decode("ascii")
            return prefix + out
        if cfg.frame_mode == TcpFrameMode.TERMINATOR and cfg.response_end_symbol:
            return out + cfg.response_end_symbol
        return out


class _TcpFrameServerManager:
    """
    TCP测试服务器统一管理器：按端口维护多实例（业务mock端口+帧诊断端口），支持一次启动内置组合。

    声明式语义：每次start后运行中的端口与传入配置一一对应，未列出的存量端口将被停止；
    启动中途失败时回停本次已启动的实例，避免残留半可用状态。
    """

    def __init__(self) -> None:
        self._servers: Dict[int, _TcpTestServerBase] = {}

    async def start(self, host: str, configs: List[_TcpFrameServerStartIn]) -> List[Dict[str, Any]]:
        """
        按传入配置列表启动端口集合（mock类型端口建 _TcpMockServer，其余建 _TcpFrameTestServer）。

        :param host: 统一监听地址（外层host）
        :param configs: 端口配置列表，每项一个端口
        :return: 各端口状态快照列表
        """
        target_ports = {cfg.port for cfg in configs}
        for port in list(self._servers):
            if port not in target_ports:
                await self._servers.pop(port).stop()
        statuses: List[Dict[str, Any]] = []
        started: List[_TcpTestServerBase] = []
        try:
            for cfg in configs:
                server = self._servers.get(cfg.port)
                if server is None:
                    server = _TcpMockServer(cfg.port, cfg.mock_type) if cfg.mock_type else _TcpFrameTestServer()
                    self._servers[cfg.port] = server
                started.append(server)
                statuses.append(await server.start(cfg, host))
        except Exception:
            for server in started:
                await server.stop()
            raise
        return statuses

    async def stop(self) -> List[Dict[str, Any]]:
        """
        停止全部端口（保留实例以供状态查询）。

        :return: 各端口状态快照列表
        """
        for server in self._servers.values():
            await server.stop()
        return self.status()

    def status(self) -> List[Dict[str, Any]]:
        """
        查询全部端口状态快照。

        :return: 各端口状态快照列表（含端口、帧配置/连接计数、诊断快照）
        """
        return [server.status() for server in self._servers.values()]


_tcp_frame_servers = _TcpFrameServerManager()


# ---------------------------------------------------------------------------
# 路由（仅用于启动/停止/状态/获取示例，实际 TCP 通信不走 HTTP）
# ---------------------------------------------------------------------------

@autotest_tcp_test.post("/start", summary="启动TCP测试服务器",
                        description="按内置端口组合统一启动TCP测试服务器（业务mock端口9091/9092 + 帧协议诊断端口9093~9099），监听地址固定为后端启动地址")
async def start_tcp_test_server():
    """
    按内置端口组合一键启动全部TCP测试端口，监听地址取后端启动地址(PROJECT_CONFIG.SERVER_HOST)。

    - **mock端口**：9091(JSON请求→银行交易查询XML响应)、9092(XML贷款请求→XML响应)，帧自动检测(8位十进制长度前缀/RAW)
    - **帧诊断端口**（9093~9099）：一次启动全部帧配置组合
      （10进制8位/16进制4位包含/结束符/HEX/GBK/RAW/共存组合），按各端口配置组帧/解帧并回显

    :return: 统一HTTP响应，data含 frame 各端口状态快照列表
    """
    try:
        frame_statuses = await _tcp_frame_servers.start(PROJECT_CONFIG.SERVER_HOST, _DEFAULT_FRAME_CONFIGS)
        return SuccessResponse(message="启动成功", data={"frame": frame_statuses})
    except Exception as e:
        LOGGER.error(f"启动TCP测试服务器失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"启动失败，异常描述: {e}")


@autotest_tcp_test.post("/stop", summary="停止TCP测试服务器", description="统一停止全部TCP测试端口（业务mock端口与帧协议诊断端口）")
async def stop_tcp_test_server():
    """
    统一停止全部TCP测试端口。

    :return: 统一HTTP响应，data含 frame 各端口状态快照列表
    """
    try:
        frame_statuses = await _tcp_frame_servers.stop()
        return SuccessResponse(message="停止成功", data={"frame": frame_statuses})
    except Exception as e:
        LOGGER.error(f"停止TCP测试服务器失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"停止失败，异常描述: {e}")


@autotest_tcp_test.get("/status", summary="查询TCP测试服务器状态",
                       description="统一查询全部TCP测试端口（业务mock端口与帧协议诊断端口）运行状态、连接计数与最近收发诊断快照")
async def get_tcp_test_server_status():
    """
    统一查询全部TCP测试端口的运行状态。

    :return: 统一HTTP响应，data含 frame 各端口状态快照列表
    """
    return SuccessResponse(message="查询成功", data={"frame": _tcp_frame_servers.status()})


@autotest_tcp_test.get("/sample/json", summary="查询JSON请求示例报文", description="获取JSON端口银行账户交易查询请求示例")
async def get_json_sample():
    """
    获取JSON端口的请求报文示例（银行账户交易查询）。

    将此报文通过TCP连接发送到JSON端口（默认9091），
    服务器将返回XML格式的交易明细响应。

    :return: 统一HTTP响应
    """
    sample = {
        "request_header": {
            "channel": "mobile",
            "request_id": "REQ20260720001",
            "timestamp": "2026-07-20 10:00:00",
            "institution": "KRUN_TEST_BANK",
        },
        "account_info": {
            "account_no": "6228480012345678",
            "account_type": "savings",
            "currency": "CNY",
            "customer_id": "CUST00001",
            "account_name": "张三",
        },
        "query_condition": {
            "start_date": "2026-01-01",
            "end_date": "2026-07-20",
            "transaction_type": "all",
            "min_amount": 0,
            "max_amount": 100000,
            "page_no": 1,
            "page_size": 5,
        },
    }
    return SuccessResponse(message="查询成功", data=sample)


@autotest_tcp_test.get("/sample/xml", summary="查询XML请求示例报文", description="获取XML端口贷款申请请求示例")
async def get_xml_sample():
    """
    获取XML端口的请求报文示例（贷款申请）。

    将此报文通过TCP连接发送到XML端口（默认9092），
    服务器将返回XML格式的贷款审批结果。

    :return: 统一HTTP响应
    """
    sample = """<?xml version="1.0" encoding="UTF-8"?>
<Request>
  <Head>
    <Channel>web</Channel>
    <RequestID>LN20260720001</RequestID>
    <Timestamp>2026-07-20T10:00:00</Timestamp>
    <Institution>KRUN_TEST_BANK</Institution>
  </Head>
  <Body>
    <ApplicantInfo>
      <Name>李四</Name>
      <IDType>身份证</IDType>
      <IDNumber>310101199001011234</IDNumber>
      <Phone>13800138000</Phone>
      <Email>lisi@example.com</Email>
      <Address>上海市浦东新区XX路XX号</Address>
      <AnnualIncome>500000</AnnualIncome>
      <Employer>某科技有限公司</Employer>
      <WorkYears>5</WorkYears>
    </ApplicantInfo>
    <LoanInfo>
      <LoanType>个人消费贷款</LoanType>
      <Amount>200000</Amount>
      <Term>36</Term>
      <Purpose>房屋装修</Purpose>
      <RepaymentMethod>等额本息</RepaymentMethod>
      <Collateral>无</Collateral>
    </LoanInfo>
    <GuarantorInfo>
      <Name>王五</Name>
      <IDNumber>310101198501011234</IDNumber>
      <Phone>13900139000</Phone>
      <Relation>朋友</Relation>
    </GuarantorInfo>
  </Body>
</Request>"""
    return SuccessResponse(message="查询成功", data=sample)


@autotest_tcp_test.get("/sample/response/json", summary="查询JSON端口的XML响应", description="预览JSON端口对示例请求返回的XML响应")
async def get_json_response_preview():
    """
    预览JSON端口对示例请求返回的XML响应。

    :return: 统一HTTP响应
    """
    sample = orjson.dumps({
        "request_header": {"request_id": "PREVIEW", "channel": "mobile", "institution": "KRUN_TEST_BANK"},
        "account_info": {"account_no": "6228480012345678", "currency": "CNY", "customer_id": "CUST00001"},
        "query_condition": {"page_no": 1, "page_size": 5},
    }).decode("utf-8")
    return SuccessResponse(message="查询成功", data=_build_json_business_response(sample))


@autotest_tcp_test.get("/sample/response/xml", summary="查询XML端口的XML响应", description="预览XML端口对示例请求返回的XML响应")
async def get_xml_response_preview():
    """
    预览XML端口对示例请求返回的XML响应。

    :return: 统一HTTP响应
    """
    sample = """<?xml version="1.0" encoding="UTF-8"?>
<Request>
  <Head><Channel>web</Channel><RequestID>PREVIEW</RequestID><Institution>KRUN_TEST_BANK</Institution></Head>
  <Body>
    <ApplicantInfo><Name>李四</Name><IDNumber>310101199001011234</IDNumber><Phone>13800138000</Phone><AnnualIncome>500000</AnnualIncome><Employer>某科技有限公司</Employer></ApplicantInfo>
    <LoanInfo><LoanType>个人消费贷款</LoanType><Amount>200000</Amount><Term>36</Term><Purpose>房屋装修</Purpose><RepaymentMethod>等额本息</RepaymentMethod></LoanInfo>
  </Body>
</Request>"""
    return SuccessResponse(message="查询成功", data=_build_xml_business_response(sample))
