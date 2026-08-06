# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_http_xml_test_view
@DateTime: 2026/7/23 10:00:00
"""
import datetime
import traceback
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import Response as FastAPIResponse
from lxml import etree

from backend.configure import LOGGER
from backend.core.responses import SuccessResponse, FailureResponse

autotest_http_xml_test = APIRouter()


def _xml_text(parent: Optional[etree._Element], tag: str, default: str = "") -> str:
    if parent is None:
        return default
    elem = parent.find(tag)
    if elem is not None and elem.text:
        return elem.text.strip()
    return default


def _build_error_xml(message: str) -> str:
    root = etree.Element("Response")
    head = etree.SubElement(root, "Head")
    etree.SubElement(head, "ResponseCode").text = "999999"
    etree.SubElement(head, "ResponseMessage").text = message
    etree.SubElement(head, "ResponseTime").text = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    etree.SubElement(head, "ProcessedBy").text = "HTTP_XML_TEST_SERVER"
    return etree.tostring(root, encoding="unicode", pretty_print=True)


def _build_claim_response(text: str) -> str:
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
    institution = _xml_text(head_elem, "Institution", "KRUN_TEST_INSURANCE")

    policy_elem = body_elem.find(".//PolicyInfo") if body_elem is not None else None
    claimant_elem = body_elem.find(".//ClaimantInfo") if body_elem is not None else None
    claim_elem = body_elem.find(".//ClaimInfo") if body_elem is not None else None

    policy_no = _xml_text(policy_elem, "PolicyNo", "POL20260001")
    policy_type = _xml_text(policy_elem, "PolicyType", "综合意外险")
    effective_date = _xml_text(policy_elem, "EffectiveDate", "2025-01-01")
    expiry_date = _xml_text(policy_elem, "ExpiryDate", "2026-12-31")
    premium = float(_xml_text(policy_elem, "Premium", "3600"))

    claimant_name = _xml_text(claimant_elem, "Name", "赵六")
    claimant_id = _xml_text(claimant_elem, "IDNumber", "310101199201011234")
    claimant_phone = _xml_text(claimant_elem, "Phone", "13700137000")
    claimant_email = _xml_text(claimant_elem, "Email", "zhaoliu@example.com")
    bank_account = _xml_text(claimant_elem, "BankAccount", "6222021234567890123")

    claim_type = _xml_text(claim_elem, "ClaimType", "意外医疗")
    claim_amount = float(_xml_text(claim_elem, "Amount", "15000"))
    incident_date = _xml_text(claim_elem, "IncidentDate", "2026-07-10")
    incident_desc = _xml_text(claim_elem, "Description", "意外摔伤导致骨折")
    hospital = _xml_text(claim_elem, "Hospital", "市第一人民医院")

    deductible = 500.0
    reimbursement_ratio = 0.85
    reimbursable = max(claim_amount - deductible, 0)
    approved_amount = reimbursable * reimbursement_ratio
    if approved_amount > premium * 10:
        approved_amount = premium * 10

    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    claim_no = f"CLM{datetime.datetime.now().strftime('%Y%m%d')}001"

    resp_root = etree.Element("Response")
    resp_head = etree.SubElement(resp_root, "Head")
    etree.SubElement(resp_head, "ResponseCode").text = "000000"
    etree.SubElement(resp_head, "ResponseMessage").text = "理赔申请处理成功"
    etree.SubElement(resp_head, "RequestID").text = request_id
    etree.SubElement(resp_head, "ResponseTime").text = now
    etree.SubElement(resp_head, "Channel").text = channel
    etree.SubElement(resp_head, "Institution").text = institution
    etree.SubElement(resp_head, "ProcessedBy").text = "HTTP_XML_TEST_SERVER"

    resp_body = etree.SubElement(resp_root, "Body")

    policy_resp = etree.SubElement(resp_body, "PolicyInfo")
    etree.SubElement(policy_resp, "PolicyNo").text = policy_no
    etree.SubElement(policy_resp, "PolicyType").text = policy_type
    etree.SubElement(policy_resp, "EffectiveDate").text = effective_date
    etree.SubElement(policy_resp, "ExpiryDate").text = expiry_date
    etree.SubElement(policy_resp, "Premium").text = f"{premium:.2f}"
    etree.SubElement(policy_resp, "PolicyStatus").text = "有效"

    claimant_resp = etree.SubElement(resp_body, "ClaimantInfo")
    etree.SubElement(claimant_resp, "Name").text = claimant_name
    etree.SubElement(claimant_resp, "IDNumber").text = claimant_id
    etree.SubElement(claimant_resp, "Phone").text = claimant_phone
    etree.SubElement(claimant_resp, "Email").text = claimant_email
    etree.SubElement(claimant_resp, "BankAccount").text = bank_account

    approval = etree.SubElement(resp_body, "ApprovalInfo")
    etree.SubElement(approval, "ClaimNo").text = claim_no
    etree.SubElement(approval, "ClaimType").text = claim_type
    etree.SubElement(approval, "ApprovalStatus").text = "已批准"
    etree.SubElement(approval, "AppliedAmount").text = f"{claim_amount:.2f}"
    etree.SubElement(approval, "Deductible").text = f"{deductible:.2f}"
    etree.SubElement(approval, "ReimbursementRatio").text = f"{reimbursement_ratio:.2%}"
    etree.SubElement(approval, "ApprovedAmount").text = f"{approved_amount:.2f}"
    etree.SubElement(approval, "IncidentDate").text = incident_date
    etree.SubElement(approval, "IncidentDescription").text = incident_desc
    etree.SubElement(approval, "Hospital").text = hospital
    etree.SubElement(approval, "ApprovalDate").text = datetime.datetime.now().strftime("%Y-%m-%d")
    etree.SubElement(approval, "PaymentDate").text = (
            datetime.datetime.now() + datetime.timedelta(days=5)
    ).strftime("%Y-%m-%d")

    documents = etree.SubElement(resp_body, "RequiredDocuments")
    doc_list = [
        ("1", "身份证正反面复印件"),
        ("2", "医院诊断证明书"),
        ("3", "医疗费用发票原件"),
        ("4", "费用明细清单"),
        ("5", "银行卡复印件"),
    ]
    documents.set("count", str(len(doc_list)))
    for seq, content in doc_list:
        doc_elem = etree.SubElement(documents, "Document")
        etree.SubElement(doc_elem, "Sequence").text = seq
        etree.SubElement(doc_elem, "Name").text = content
        etree.SubElement(doc_elem, "Required").text = "是"
        etree.SubElement(doc_elem, "Status").text = "待提交"

    timeline = etree.SubElement(resp_body, "ProcessTimeline")
    timeline.set("count", "5")
    steps = [
        ("报案登记", incident_date, "已完成"),
        ("材料收集", datetime.datetime.now().strftime("%Y-%m-%d"), "进行中"),
        ("审核评估", (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y-%m-%d"), "待处理"),
        ("审批决定", (datetime.datetime.now() + datetime.timedelta(days=3)).strftime("%Y-%m-%d"), "待处理"),
        ("赔款支付", (datetime.datetime.now() + datetime.timedelta(days=5)).strftime("%Y-%m-%d"), "待处理"),
    ]
    for step_name, step_date, step_status in steps:
        step_elem = etree.SubElement(timeline, "Step")
        etree.SubElement(step_elem, "Name").text = step_name
        etree.SubElement(step_elem, "Date").text = step_date
        etree.SubElement(step_elem, "Status").text = step_status

    contact = etree.SubElement(resp_body, "ContactInfo")
    etree.SubElement(contact, "Hotline").text = "95500"
    etree.SubElement(contact, "Email").text = "claim@krun-test-insurance.com"
    etree.SubElement(contact, "Website").text = "www.krun-test-insurance.com"
    etree.SubElement(contact, "Adjuster").text = "理赔专员：孙七"
    etree.SubElement(contact, "AdjusterPhone").text = "021-88886666"

    return etree.tostring(resp_root, encoding="unicode", pretty_print=True)


_SAMPLE_REQUEST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Request>
  <Head>
    <Channel>web</Channel>
    <RequestID>CLM20260723001</RequestID>
    <Timestamp>2026-07-23T10:00:00</Timestamp>
    <Institution>KRUN_TEST_INSURANCE</Institution>
  </Head>
  <Body>
    <PolicyInfo>
      <PolicyNo>POL20260001</PolicyNo>
      <PolicyType>综合意外险</PolicyType>
      <EffectiveDate>2025-01-01</EffectiveDate>
      <ExpiryDate>2026-12-31</ExpiryDate>
      <Premium>3600</Premium>
    </PolicyInfo>
    <ClaimantInfo>
      <Name>赵六</Name>
      <IDType>身份证</IDType>
      <IDNumber>310101199201011234</IDNumber>
      <Phone>13700137000</Phone>
      <Email>zhaoliu@example.com</Email>
      <BankAccount>6222021234567890123</BankAccount>
    </ClaimantInfo>
    <ClaimInfo>
      <ClaimType>意外医疗</ClaimType>
      <Amount>15000</Amount>
      <IncidentDate>2026-07-10</IncidentDate>
      <Description>意外摔伤导致骨折</Description>
      <Hospital>市第一人民医院</Hospital>
      <Diagnosis>左腿胫骨骨折</Diagnosis>
    </ClaimInfo>
  </Body>
</Request>"""


@autotest_http_xml_test.post(path="/xml", summary="HTTP XML测试接口", description="保险理赔申请")
async def http_xml_test(request: Request):
    """
    接收XML格式请求报文（保险理赔申请），返回XML格式响应。

    请求体为XML格式，包含Head（请求头）和Body（保单信息 + 报案人信息 + 理赔信息），
    响应为XML格式，包含保单信息、报案人信息、审批结果、所需材料清单、处理时间线、联系方式等40+字段。

    用于测试 HTTP 请求步骤中 XML 报文类型的发送与响应解析。
    """
    try:
        body_bytes = await request.body()
        text = body_bytes.decode("utf-8", errors="ignore").strip()
    except Exception as e:
        LOGGER.error(f"HTTP XML测试接口读取请求体失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"读取请求体失败，异常描述: {e}")

    response_xml = _build_claim_response(text)
    LOGGER.info(f"HTTP XML测试接口处理完成, 请求长度: {len(text)}")

    return FastAPIResponse(
        content=response_xml,
        media_type="application/xml; charset=utf-8",
    )


@autotest_http_xml_test.get("/sample/request", summary="获取XML请求示例报文")
async def get_http_xml_sample_request():
    """
    获取HTTP、XML测试接口的请求报文示例（保险理赔申请）。

    将此XML报文作为HTTP请求步骤的请求体（选择xml类型），
    发送到 POST/xml 接口，服务器将返回XML格式的理赔审批结果。
    """
    return SuccessResponse(message="查询成功", data=_SAMPLE_REQUEST_XML)


@autotest_http_xml_test.get("/sample/response", summary="预览XML响应报文")
async def get_http_xml_sample_response():
    """预览 HTTP XML 测试接口对示例请求返回的 XML 响应。"""
    return SuccessResponse(message="查询成功", data=_build_claim_response(_SAMPLE_REQUEST_XML))
