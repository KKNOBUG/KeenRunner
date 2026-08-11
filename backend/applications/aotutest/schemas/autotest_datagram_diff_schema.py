# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_datagram_diff_schema.py
@DateTime: 2026/8/11
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

DiffType = Literal["equal", "left_only", "right_only", "modified", "empty"]


class RepDiffRequest(BaseModel):
    left_text: str = Field(..., description="左侧报文文本")
    right_text: str = Field(..., description="右侧报文文本")
    order_control: int = Field(
        0,
        description="是否控制比对顺序，1=按行顺序比对，0=按字段名比对忽略顺序",
        ge=0,
        le=1,
    )


class CharHighlight(BaseModel):
    start: int = Field(..., ge=0, description="高亮起始字符下标")
    end: int = Field(..., ge=0, description="高亮结束字符下标(不含)")


class DiffLineItem(BaseModel):
    source_line_no: Optional[int] = Field(None, description="原文行号，占位行为空")
    content: str = Field("", description="行文本内容")
    diff_type: DiffType = Field(
        ...,
        description="equal=相同无高亮, left_only=左侧多标红, right_only=右侧多标绿, modified=同字段值不同标蓝, empty=占位",
    )
    key: Optional[str] = Field(None, description="字段名(JSON键名/XML标签名)")
    highlights: List[CharHighlight] = Field(default_factory=list, description="行内差异高亮区间")


class AlignedDiffRow(BaseModel):
    row_no: int = Field(..., ge=1, description="对齐后的展示行号")
    left: DiffLineItem = Field(..., description="左侧行")
    right: DiffLineItem = Field(..., description="右侧行")


class RepDiffResponse(BaseModel):
    is_equal: bool = Field(..., description="两侧报文是否完全一致")
    format_type: str = Field(..., description="识别到的报文格式: json/xml/text")
    order_consistent: bool = Field(True, description="字段顺序是否一致(order_control=1时有效)")
    order_message: Optional[str] = Field(None, description="顺序不一致时的描述")
    rows: List[AlignedDiffRow] = Field(default_factory=list, description="左右对齐的逐行比对结果")