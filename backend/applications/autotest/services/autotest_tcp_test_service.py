# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_tcp_test_service
@DateTime: 2026/11/19 10:00:00
"""
import asyncio
import datetime
import traceback
from typing import Any, Callable, Dict, List, Optional

import orjson
from lxml import etree

from backend.applications.autotest.schemas.autotest_tcp_test_schema import (
    AutoTestTcpTestServerStartIn,
    DEFAULT_TCP_TEST_SERVER_CONFIGS,
)
from backend.applications.autotest.services.autotest_runtime.protocol_tcp import (
    TCP_MAX_RESPONSE_BYTES,
    resolve_tcp_frame_config,
    tcp_enum_value,
)
from backend.common import TcpFrameMode
from backend.configure import LOGGER, PROJECT_CONFIG
from backend.core.exceptions import ParameterException

# ---------------------------------------------------------------------------
# 业务 Mock 响应构造（无状态纯函数：JSON请求→银行交易查询JSON / XML请求→贷款审批XML）
# ---------------------------------------------------------------------------

_MOCK_ACCOUNT_BALANCE = 125680.50

_TRANSACTION_TEMPLATES: List[Dict[str, Any]] = [
    {
        "date_offset": 0,
        "time": "09:30:00",
        "amount": 5000.00,
        "type": "存入",
        "sub_type": "工资",
        "description": "7月工资入账",
        "counterparty": "某科技有限公司",
        "channel": "企业网银"
    },
    {
        "date_offset": 1,
        "time": "14:20:30",
        "amount": 3200.00,
        "type": "支出",
        "sub_type": "消费",
        "description": "商场购物",
        "counterparty": "某商场",
        "channel": "手机银行"
    },
    {
        "date_offset": 4,
        "time": "10:15:00",
        "amount": 20000.00,
        "type": "存入",
        "sub_type": "转账",
        "description": "李四转账",
        "counterparty": "李四",
        "channel": "手机银行"
    },
    {
        "date_offset": 9,
        "time": "16:45:20",
        "amount": 1500.00,
        "type": "支出",
        "sub_type": "水电费",
        "description": "7月水电费",
        "counterparty": "供电局",
        "channel": "自动扣款"
    },
    {
        "date_offset": 14,
        "time": "11:00:00",
        "amount": 800.00,
        "type": "支出",
        "sub_type": "取现",
        "description": "ATM取现",
        "counterparty": "ATM-001",
        "channel": "ATM"
    },
    {
        "date_offset": 19,
        "time": "08:50:00",
        "amount": 12000.00,
        "type": "存入",
        "sub_type": "理财收益",
        "description": "理财产品到期",
        "counterparty": "某基金公司",
        "channel": "网银"
    },
    {
        "date_offset": 24,
        "time": "15:30:00",
        "amount": 680.00,
        "type": "支出",
        "sub_type": "通讯费",
        "description": "手机话费充值",
        "counterparty": "中国移动",
        "channel": "手机银行"
    },
    {
        "date_offset": 29,
        "time": "12:00:00",
        "amount": 3000.00,
        "type": "支出",
        "sub_type": "转账",
        "description": "转账给王五",
        "counterparty": "王五",
        "channel": "手机银行"
    },
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


def _build_json_error_payload(message: str) -> Dict[str, Any]:
    """
    构造JSON端口统一错误响应对象。

    :param message: 错误描述
    :return: 错误响应对象
    """
    return {
        "response_header": {
            "response_code": "999999",
            "response_message": message,
            "response_time": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "processed_by": "TCP_TEST_SERVER",
        }
    }


def _build_json_business_payload(text: str) -> Dict[str, Any]:
    """
    构造JSON端口的银行账户交易查询响应对象：响应头/账户信息嵌套对象 + 交易流水列表 + 汇总对象。

    :param text: 请求报文JSON文本
    :return: 交易查询结果对象
    """
    if not text:
        return _build_json_error_payload("空请求")
    try:
        req: Dict[str, Any] = orjson.loads(text)
    except orjson.JSONDecodeError as e:
        return _build_json_error_payload(f"JSON解析失败: {e}")

    header = req.get("request_header") or req.get("header") or {}
    account = req.get("account_info") or req.get("account") or {}
    query = req.get("query_condition") or req.get("query") or {}
    account_type = account.get("account_type", "savings")
    currency = account.get("currency", "CNY")
    page_no = query.get("page_no", 1)
    page_size = query.get("page_size", 5)

    transactions = _generate_transactions(page_size)
    total_income = sum(float(t["amount"]) for t in transactions if t["type"] == "存入")
    total_expense = sum(float(t["amount"]) for t in transactions if t["type"] == "支出")

    return {
        "response_header": {
            "response_code": "000000",
            "response_message": "查询成功",
            "request_id": header.get("request_id", "UNKNOWN"),
            "response_time": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "channel": header.get("channel", "unknown"),
            "institution": header.get("institution", "KRUN_TEST_BANK"),
            "processed_by": "TCP_TEST_SERVER_JSON",
        },
        "account_info": {
            "account_no": account.get("account_no", "6228480012345678"),
            "account_name": account.get("account_name", "张三"),
            "account_type": "储蓄账户" if account_type == "savings" else account_type,
            "currency": currency,
            "customer_id": account.get("customer_id", "CUST00001"),
            "balance": _MOCK_ACCOUNT_BALANCE,
            "available_balance": round(_MOCK_ACCOUNT_BALANCE - 5000, 2),
            "open_date": "2020-03-15",
            "last_transaction_date": transactions[0]["date"] if transactions else "",
        },
        "transaction_list": [
            {**txn, "currency": currency, "status": "成功"} for txn in transactions
        ],
        "summary": {
            "total_count": len(transactions),
            "total_income": round(total_income, 2),
            "total_expense": round(total_expense, 2),
            "net_amount": round(total_income - total_expense, 2),
            "page_no": page_no,
            "page_size": page_size,
            "has_next_page": False,
        },
    }


def _build_json_business_response(text: str) -> str:
    """
    将JSON端口响应对象序列化为缩进JSON文本。

    :param text: 请求报文JSON文本
    :return: 交易查询结果JSON文本
    """
    return orjson.dumps(_build_json_business_payload(text), option=orjson.OPT_INDENT_2).decode("utf-8")


def _build_xml_business_response(text: str) -> str:
    """
    构造XML端口的贷款申请XML响应报文。

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

    # 显式判None：lxml元素真值按子节点数判定，空节点会被or误判为缺失（FutureWarning）
    head_elem = root.find(".//Head")
    if head_elem is None:
        head_elem = root.find(".//head")
    body_elem = root.find(".//Body")
    if body_elem is None:
        body_elem = root.find(".//body")

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
# TCP 测试服务器实现（业务mock端口 + 帧诊断端口，统一由 TcpTestServerManager 编排）
# ---------------------------------------------------------------------------

async def _read_until_idle(reader: asyncio.StreamReader, idle_timeout: float) -> bytes:
    """
    无显式边界报文的收尾读取：持续读取直至静默窗口超时或对端关闭，超时按正常收尾处理而非异常。

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


class TcpTestServerBase:
    """TCP测试服务器基类：收敛监听套接字生命周期与连接收尾，子类只关注业务读写。"""

    def __init__(self, label: str) -> None:
        self._label: str = label
        self._server: Optional[asyncio.base_events.Server] = None

    @property
    def is_running(self) -> bool:
        """运行状态以监听套接字存在为唯一事实源。"""
        return self._server is not None

    async def stop(self) -> None:
        """关闭监听套接字，幂等语义：未启动时仅归位状态。"""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            LOGGER.info(f"{self._label}已停止")

    @staticmethod
    async def _close_writer(writer: asyncio.StreamWriter) -> None:
        """统一连接收尾：关闭写端并等待对端确认；对端可能已先行断开，异常不外抛。"""
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


class TcpMockServer(TcpTestServerBase):
    """
    单端口业务 Mock TCP 服务器。
    """
    # 帧自动检测启发式：首读为纯数字文本时按8位十进制长度前缀精确读正文，否则按RAW读到静默窗口收尾；
    # 响应侧与请求同帧。业务响应报文由_TCP_MOCK_RESPONSE_BUILDERS按类型路由生成

    _LENGTH_FIELD_SIZE = 8
    _READ_TIMEOUT = 10.0
    _IDLE_TIMEOUT = 3.0

    def __init__(self) -> None:
        super().__init__(label="TCP mock服务器")
        self._port: int = 0
        self._mock_type: str = ""
        self._host: str = ""
        self._conn_count: int = 0

    # -- 生命周期 ----------------------------------------------------------

    async def start(self, cfg: AutoTestTcpTestServerStartIn, host: str) -> Dict[str, Any]:
        """
        按配置启动mock服务器：已运行时先停旧实例。

        :param cfg: 启动入参（取端口与mock类型，与帧诊断服务器统一签名）
        :param host: 监听地址（后端启动地址）
        :return: 服务器状态快照
        """
        await self.stop()
        self._port = cfg.port
        self._mock_type = cfg.mock_type
        self._label = f"TCP mock服务器({cfg.mock_type})端口{cfg.port}"
        self._host = host
        self._conn_count = 0
        self._server = await asyncio.start_server(self._handle_client, host, self._port)
        LOGGER.info(f"TCP mock服务器启动: {host}:{self._port}, 类型={self._mock_type}")
        return self.status()

    def status(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
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
            body_bytes, is_length_prefixed = await self._read_request(reader)
            response_text = build_response(body_bytes.decode("utf-8", errors="ignore").strip())
            await self._write_framed(writer, response_text.encode("utf-8"), is_length_prefixed)
        except Exception as e:
            LOGGER.error(f"TCP mock服务器处理异常({self._port}): {e}\n{traceback.format_exc()}")
            error_message = f"服务器内部错误: {e}"
            error_text = (
                orjson.dumps(_build_json_error_payload(error_message), option=orjson.OPT_INDENT_2).decode("utf-8")
                if self._mock_type == "json" else _build_error_xml(error_message)
            )
            try:
                # 错误响应统一补长度前缀，保证前缀形态客户端可解帧
                await self._write_framed(writer, error_text.encode("utf-8"), True)
            except Exception:
                pass
        finally:
            await self._close_writer(writer)

    async def _read_request(self, reader: asyncio.StreamReader) -> tuple[bytes, bool]:
        """
        读取请求数据并自动检测帧协议。

        :param reader: 流读取器
        :return: (请求正文字节, 是否长度前缀帧)
        """
        # 长度前缀路径按声明长度精确读正文；RAW/结束符路径无显式长度边界，读到静默窗口或对端关闭收尾
        first_chunk = await asyncio.wait_for(
            reader.read(self._LENGTH_FIELD_SIZE), timeout=self._READ_TIMEOUT,
        )
        if not first_chunk:
            return b"", False

        body_length = self._detect_length_prefix(first_chunk)
        if body_length is not None:
            body_bytes = await asyncio.wait_for(reader.readexactly(body_length), timeout=self._READ_TIMEOUT)
            return body_bytes, True

        body_bytes = first_chunk + await _read_until_idle(reader, self._IDLE_TIMEOUT)
        return body_bytes, False

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


class TcpFrameTestServer(TcpTestServerBase):
    """
    按帧配置收发的TCP诊断服务器：读取侧镜像客户端AioTcpClient的组帧逻辑，每次收发记录诊断快照供统一/status查询比对。
    响应侧按behavior模拟回显/沉默/即关/合法空帧/部分字节/前缀缺正文/前缀超限/非法前缀/延迟等行为，
    供验证客户端tcp_async_utils的收发判定口径（0字节容忍/合法空帧/部分字节失败等）。
    """
    # 诊断快照覆盖前缀文本/声明长度/实际长度/结束符/HEX/行为动作/错误细节；用于验证TCP步骤帧配置的字段组合
    # 是否产生预期报文、响应侧解析是否按同一配置工作

    _READ_TIMEOUT = 10.0
    _IDLE_TIMEOUT = 1.0
    # silent行为保持连接的上限：客户端读超时后会主动断开，此窗口仅防异常客户端长期占用连接
    _SILENT_HOLD_TIMEOUT = 60.0

    def __init__(self) -> None:
        super().__init__(label="TCP帧诊断服务器")
        self._host: str = ""
        self._port: int = 0
        self._frame_config: Any = None
        self._frame_desc: Dict[str, Any] = {}
        self._response_text: Optional[str] = None
        self._behavior: str = "echo"
        self._delay_seconds: float = 6.0
        self._exchange_count: int = 0
        self._last_report: Dict[str, Any] = {}

    # -- 生命周期 ----------------------------------------------------------

    async def start(self, req: AutoTestTcpTestServerStartIn, host: str) -> Dict[str, Any]:
        """
        按帧配置启动诊断服务器：已运行时先停旧实例。

        :param req: 启动入参（tcp_*字段语义与步骤schema一致）
        :param host: 监听地址（与业务mock端口共用外层host）
        :return: 服务器状态快照
        """
        await self.stop()
        self._frame_config = resolve_tcp_frame_config(req)
        self._behavior = req.behavior or "echo"
        self._port = req.port
        self._validate_behavior_frame_compat()
        self._response_text = req.response_text
        self._delay_seconds = float(req.delay_seconds or 6.0)
        self._host = host
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
            "behavior": self._behavior,
            "delay_seconds": self._delay_seconds,
        }
        self._server = await asyncio.start_server(
            self._handle_client, host, req.port,
            limit=max(TCP_MAX_RESPONSE_BYTES, 65536),
        )
        LOGGER.info(f"TCP帧诊断服务器启动: {host}:{req.port}, 帧配置: {self._frame_desc}")
        return self.status()

    def status(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
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
            "behavior": self._behavior,
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
            await self._respond_by_behavior(reader, writer, body_bytes, report)
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

    def _validate_behavior_frame_compat(self) -> None:
        """
        启动入口校验行为与帧模式兼容性，非法组合快速失败，避免运行期不可达兜底分支。

        :raises ParameterException: 行为与帧模式不兼容
        """
        cfg = self._frame_config
        behavior = self._behavior
        if behavior == "empty_frame" and cfg.frame_mode == TcpFrameMode.RAW:
            raise ParameterException(message=f"端口[{self._port}]行为[empty_frame]与RAW帧模式不兼容: 0字节+EOF即未响应语义, 无法构造合法空帧")
        if behavior == "empty_frame" and cfg.frame_mode == TcpFrameMode.TERMINATOR and not cfg.response_end_symbol:
            raise ParameterException(message=f"端口[{self._port}]行为[empty_frame]要求结束符模式配置响应结束符")
        if behavior in ("prefix_no_body", "oversize_prefix", "invalid_prefix") and cfg.frame_mode != TcpFrameMode.LENGTH_PREFIX:
            raise ParameterException(message=f"端口[{self._port}]行为[{behavior}]仅适用于长度前缀帧模式")

    def _format_prefix(self, value: int) -> bytes:
        """
        按进制与宽度生成定宽文本数字长度前缀，响应组帧与行为模拟共用。

        :param value: 待写入前缀的长度数值
        :return: 前缀字节
        """
        cfg = self._frame_config
        return format(value, "d" if cfg.radix == 10 else "x").zfill(cfg.radix_length).encode("ascii")

    async def _respond_by_behavior(
            self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, body_bytes: bytes, report: Dict[str, Any]
    ) -> None:
        """
        按behavior模拟响应动作：echo按帧回显/固定内容，其余行为构造客户端判定口径所需的异常/边界场景。
        非echo行为写完即由_handle_client的finally收尾关闭连接；动作描述写入诊断快照action字段。

        :param reader: 流读取器（silent行为等待客户端断开用）
        :param writer: 流写入器
        :param body_bytes: 请求正文（echo/delay回显用）
        :param report: 诊断快照（就地写入动作描述）
        """
        cfg = self._frame_config
        behavior = self._behavior
        if behavior == "silent":
            report["action"] = "读完整请求后保持连接不回复, 等待客户端读超时自行断开"
            try:
                # 读到EOF即客户端已断开；保持窗口仅防异常客户端长期占用连接
                await asyncio.wait_for(reader.read(), timeout=self._SILENT_HOLD_TIMEOUT)
            except asyncio.TimeoutError:
                report["errors"].append(f"客户端未在{self._SILENT_HOLD_TIMEOUT}s保持窗口内断开, 服务器主动收尾")
            return
        if behavior == "close":
            report["action"] = "读完整请求后立即关闭不回复"
            return
        if behavior == "delay":
            if cfg.frame_mode == TcpFrameMode.LENGTH_PREFIX:
                # 长度前缀模式整体延迟：客户端首段读超时0字节按通讯级口径容忍成功
                report["action"] = f"延迟{self._delay_seconds}s后才发长度前缀与正文"
                await asyncio.sleep(self._delay_seconds)
                writer.write(self._build_response(body_bytes, report))
            else:
                # RAW/结束符模式先发一半再延迟：客户端已收字节后读超时→接收阶段超时失败
                response_bytes = self._build_response(body_bytes, report)
                split = len(response_bytes) // 2
                report["action"] = f"先发{split}字节再延迟{self._delay_seconds}s发剩余{len(response_bytes) - split}字节"
                writer.write(response_bytes[:split])
                await writer.drain()
                await asyncio.sleep(self._delay_seconds)
                writer.write(response_bytes[split:])
            await writer.drain()
            return
        if behavior == "empty_frame":
            # 启动入口已校验兼容性：长度前缀或配响应结束符的结束符模式，二者必居其一
            if cfg.frame_mode == TcpFrameMode.LENGTH_PREFIX:
                report["action"] = "仅回0长度正文前缀(合法空帧)"
                writer.write(self._format_prefix(0))
            else:
                report["action"] = "仅回响应结束符(合法空帧)"
                writer.write(cfg.response_end_symbol)
            await writer.drain()
            return
        if behavior == "partial":
            if cfg.frame_mode == TcpFrameMode.LENGTH_PREFIX:
                report["action"] = "前缀声明100字节只发10字节正文后关闭"
                writer.write(self._format_prefix(100) + b"0123456789")
            else:
                report["action"] = "只发10字节无结束符后关闭"
                writer.write(b"0123456789")
            await writer.drain()
            return
        if behavior == "prefix_no_body":
            report["action"] = "前缀声明100字节不发正文即关闭"
            writer.write(self._format_prefix(100))
            await writer.drain()
            return
        if behavior == "oversize_prefix":
            report["action"] = f"前缀声明正文{TCP_MAX_RESPONSE_BYTES + 1}字节超出上限后关闭(仅发前缀)"
            writer.write(self._format_prefix(TCP_MAX_RESPONSE_BYTES + 1))
            await writer.drain()
            return
        if behavior == "invalid_prefix":
            report["action"] = "回非数字前缀后关闭"
            writer.write(b"X" * cfg.radix_length)
            await writer.drain()
            return
        # echo（缺省）：按帧回显请求或固定内容
        report["action"] = "回显请求" if self._response_text is None else "固定内容响应"
        writer.write(self._build_response(body_bytes, report))
        await writer.drain()

    def _build_response(self, body_bytes: bytes, report: Dict[str, Any]) -> bytes:
        """
        按帧配置组装响应报文：客户端响应读取依赖同一帧规则。

        :param body_bytes: 请求正文（response_text未配置时用于回显）
        :param report: 诊断快照（就地写入响应信息）
        :return: 响应报文字节
        """
        cfg = self._frame_config
        out = body_bytes if self._response_text is None else self._response_text.encode(cfg.encoding, errors="replace")
        report["response_bytes"] = len(out)
        if cfg.frame_mode == TcpFrameMode.LENGTH_PREFIX:
            value = len(out) + cfg.radix_length if cfg.include_length_prefix else len(out)
            prefix = self._format_prefix(value)
            report["response_prefix"] = prefix.decode("ascii")
            return prefix + out
        if cfg.frame_mode == TcpFrameMode.TERMINATOR and cfg.response_end_symbol:
            return out + cfg.response_end_symbol
        return out


class TcpTestServerManager:
    """
    TCP测试服务器统一管理器：按端口维护多实例，覆盖业务mock端口与帧诊断端口，支持一次启动内置组合。
    """

    # 声明式语义：每次start后运行中的端口与传入配置一一对应，未列出的存量端口将被停止；
    # 启动中途失败时回停本次已启动的实例，避免残留半可用状态

    def __init__(self) -> None:
        self._servers: Dict[int, TcpTestServerBase] = {}

    async def start(self, host: str, configs: List[AutoTestTcpTestServerStartIn]) -> List[Dict[str, Any]]:
        """
        按传入配置列表启动端口集合：mock类型端口建TcpMockServer，其余建TcpFrameTestServer。

        :param host: 统一监听地址（外层host）
        :param configs: 端口配置列表，每项一个端口
        :return: 各端口状态快照列表
        """
        target_ports = {cfg.port for cfg in configs}
        for port in list(self._servers):
            if port not in target_ports:
                await self._servers.pop(port).stop()
        statuses: List[Dict[str, Any]] = []
        started: List[TcpTestServerBase] = []
        try:
            for cfg in configs:
                server = self._servers.get(cfg.port)
                if server is None:
                    server = TcpMockServer() if cfg.mock_type else TcpFrameTestServer()
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
        停止全部端口，保留实例以供状态查询。

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


_tcp_test_server_manager = TcpTestServerManager()

# ---------------------------------------------------------------------------
# 示例报文（供视图 /sample/* 展示与响应预览，与mock端口实际响应构造同源）
# ---------------------------------------------------------------------------

_JSON_REQUEST_SAMPLE: Dict[str, Any] = {
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

_XML_REQUEST_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
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
        <LoanInfo>
            <LoanType>个人汽车贷款</LoanType>
            <Amount>150000</Amount>
            <Term>24</Term>
            <Purpose>购置家用轿车</Purpose>
            <RepaymentMethod>等额本金</RepaymentMethod>
            <Collateral>所购车辆抵押</Collateral>
        </LoanInfo>
        <LoanInfo>
            <LoanType>个人经营贷款</LoanType>
            <Amount>500000</Amount>
            <Term>60</Term>
            <Purpose>经营周转</Purpose>
            <RepaymentMethod>先息后本</RepaymentMethod>
            <Collateral>房产抵押</Collateral>
        </LoanInfo>
        <GuarantorInfo>
            <Name>王五</Name>
            <IDNumber>310101198501011234</IDNumber>
            <Phone>13900139000</Phone>
            <Relation>朋友</Relation>
        </GuarantorInfo>
    </Body>
</Request>"""


def _mock_port(mock_type: str) -> int:
    """
    按mock类型查内置业务mock端口，与DEFAULT_TCP_TEST_SERVER_CONFIGS保持单一事实源。

    :param mock_type: mock类型json/xml
    :return: 监听端口
    """
    return next(cfg.port for cfg in DEFAULT_TCP_TEST_SERVER_CONFIGS if cfg.mock_type == mock_type)


class TcpTestServerService:
    """TCP测试服务器服务：编排内置端口组合的启停与状态查询，提供示例报文与响应预览。"""

    @staticmethod
    async def start() -> List[Dict[str, Any]]:
        """
        按内置端口组合一键启动全部TCP测试端口，监听地址取后端启动地址PROJECT_CONFIG.SERVER_HOST。

        :return: 各端口状态快照列表
        """
        # mock端口：9091为JSON请求→银行交易查询JSON响应(嵌套对象+交易列表+汇总)，9092为XML贷款请求→XML审批响应，帧自动检测8位十进制长度前缀或RAW；
        # 帧诊断端口9093~9099：一次启动全部帧配置组合10进制8位/16进制4位包含/结束符/HEX/GBK/RAW/共存组合，按各端口配置组帧/解帧并回显；
        # 行为模拟端口9100~9110：沉默/即关/合法空帧/部分字节/前缀缺正文/前缀超限/非法前缀/延迟响应，验证客户端收发判定口径
        return await _tcp_test_server_manager.start(PROJECT_CONFIG.SERVER_HOST, DEFAULT_TCP_TEST_SERVER_CONFIGS)

    @staticmethod
    async def stop() -> List[Dict[str, Any]]:
        """
        统一停止全部TCP测试端口。

        :return: 各端口状态快照列表
        """
        return await _tcp_test_server_manager.stop()

    @staticmethod
    def status() -> List[Dict[str, Any]]:
        """
        统一查询全部TCP测试端口的运行状态。

        :return: 各端口状态快照列表
        """
        return _tcp_test_server_manager.status()

    @staticmethod
    def json_request_sample() -> Dict[str, Any]:
        """
        获取JSON端口的银行账户交易查询请求报文示例。

        :return: 含端口/帧说明/请求对象的结构化示例；将此报文通过TCP连接发送到JSON端口，服务器将返回JSON格式的交易明细响应
        """
        return {
            "port": _mock_port("json"),
            "mock_type": "json",
            "content_type": "json",
            "frame": "8位十进制长度前缀/RAW自动检测",
            "request": _JSON_REQUEST_SAMPLE,
        }

    @staticmethod
    def xml_request_sample() -> Dict[str, Any]:
        """
        获取XML端口的贷款申请请求报文示例。

        :return: 含端口/帧说明/请求XML文本的结构化示例；将此报文通过TCP连接发送到XML端口，服务器将返回XML格式的贷款审批结果
        """
        return {
            "port": _mock_port("xml"),
            "mock_type": "xml",
            "content_type": "xml",
            "frame": "8位十进制长度前缀/RAW自动检测",
            "request": _XML_REQUEST_SAMPLE,
        }

    @staticmethod
    def json_response_preview() -> Dict[str, Any]:
        """
        预览JSON端口对示例请求返回的JSON响应，与端口实际响应构造同源。

        :return: 含端口与响应对象（嵌套对象+交易列表+汇总）的预览结果
        """
        return {
            "port": _mock_port("json"),
            "content_type": "json",
            "response": _build_json_business_payload(orjson.dumps(_JSON_REQUEST_SAMPLE).decode("utf-8")),
        }

    @staticmethod
    def xml_response_preview() -> Dict[str, Any]:
        """
        预览XML端口对示例请求返回的XML响应，与端口实际响应构造同源。

        :return: 含端口与响应XML文本（还款计划/贷款条款列表）的预览结果
        """
        return {
            "port": _mock_port("xml"),
            "content_type": "xml",
            "response": _build_xml_business_response(_XML_REQUEST_SAMPLE),
        }
