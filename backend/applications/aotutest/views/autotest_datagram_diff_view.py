# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_datagram_diff_view.py
@DateTime: 2026/8/11
"""
import json
import re
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

from fastapi import APIRouter

from backend.applications.aotutest.schemas.autotest_datagram_diff_schema import (
    AlignedDiffRow,
    CharHighlight,
    DiffLineItem,
    RepDiffResponse,
)

rep_diff_router = APIRouter()

JSON_FIELD_RE = re.compile(r'^(\s*)"((?:\\.|[^"\\])*)"\s*:\s*(.*?)(,?\s*)$')
XML_TAG_RE = re.compile(r"^\s*</?([\w:.-]+)")
LENGTH_HEADER_LINE_RE = re.compile(r"^\d{4,10}$")
LENGTH_INLINE_XML_RE = re.compile(r"^(\d{4,10})(<\?xml[\s\S]*)", re.IGNORECASE)
LENGTH_INLINE_TAG_RE = re.compile(r"^(\d{4,10})(<[A-Za-z][\s\S]*)")


class _FieldLine:
    __slots__ = ("line_no", "key", "match_key", "content", "value")

    def __init__(self, line_no: int, key: str, match_key: str, content: str, value: str):
        self.line_no = line_no
        self.key = key
        self.match_key = match_key
        self.content = content
        self.value = value


def _strip_length_prefix(text: str) -> str:
    stripped = text.strip()
    inline_xml = LENGTH_INLINE_XML_RE.match(stripped)
    if inline_xml:
        return inline_xml.group(2)
    inline_tag = LENGTH_INLINE_TAG_RE.match(stripped)
    if inline_tag:
        return inline_tag.group(2)
    lines = stripped.splitlines()
    if lines and LENGTH_HEADER_LINE_RE.match(lines[0].strip()):
        return "\n".join(lines[1:])
    return stripped


def _is_length_header_line(line: str) -> bool:
    return bool(LENGTH_HEADER_LINE_RE.match(line.strip()))


def _detect_format(left_text: str, right_text: str) -> str:
    for text in (left_text, right_text):
        stripped = text.strip()
        if not stripped:
            continue
        try:
            json.loads(stripped)
            return "json"
        except json.JSONDecodeError:
            pass
        try:
            ET.fromstring(_strip_length_prefix(stripped))
            return "xml"
        except ET.ParseError:
            pass
    return "text"


def _parse_json_field(line: str) -> Optional[Tuple[str, str]]:
    matched = JSON_FIELD_RE.match(line)
    if not matched:
        return None
    key = matched.group(2)
    value = matched.group(3).strip().rstrip(",")
    return key, value


def _parse_xml_field(line: str) -> Optional[Tuple[str, str]]:
    matched = XML_TAG_RE.match(line.strip())
    if not matched:
        return None
    tag = matched.group(1)
    if line.strip().startswith("</"):
        return None
    if line.strip().endswith("/>"):
        return tag, line.strip()
    return tag, line.strip()


def _parse_field_line(line: str, format_type: str) -> Optional[Tuple[str, str]]:
    if format_type == "json":
        return _parse_json_field(line)
    if format_type == "xml":
        return _parse_xml_field(line)
    return None


def _make_match_key(tag: str, counters: dict, format_type: str) -> Tuple[str, str]:
    if format_type != "xml":
        return tag, tag
    idx = counters.get(tag, 0)
    counters[tag] = idx + 1
    return tag, f"{tag}#{idx}"


def _extract_field_lines(lines: List[str], format_type: str) -> List[_FieldLine]:
    field_lines: List[_FieldLine] = []
    counters: dict = {}
    for index, line in enumerate(lines, start=1):
        parsed = _parse_field_line(line, format_type)
        if parsed:
            key, value = parsed
            display_key, match_key = _make_match_key(key, counters, format_type)
            field_lines.append(_FieldLine(index, display_key, match_key, line, value))
    return field_lines


def _extract_structural_lines(lines: List[str], format_type: str) -> List[Tuple[int, str]]:
    structural: List[Tuple[int, str]] = []
    for index, line in enumerate(lines, start=1):
        if _parse_field_line(line, format_type):
            continue
        if line.strip():
            structural.append((index, line))
    return structural


def _normalize_value(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1]
    return text


def _char_highlights(left: str, right: str) -> Tuple[List[CharHighlight], List[CharHighlight]]:
    matcher = SequenceMatcher(None, left, right)
    left_highlights: List[CharHighlight] = []
    right_highlights: List[CharHighlight] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in {"replace", "delete"} and i1 < i2:
            left_highlights.append(CharHighlight(start=i1, end=i2))
        if tag in {"replace", "insert"} and j1 < j2:
            right_highlights.append(CharHighlight(start=j1, end=j2))
    return left_highlights, right_highlights


def _empty_item() -> DiffLineItem:
    return DiffLineItem(source_line_no=None, content="", diff_type="empty")


def _build_line_item(
        *,
        content: str,
        diff_type: str,
        source_line_no: Optional[int],
        key: Optional[str] = None,
        highlights: Optional[List[CharHighlight]] = None,
) -> DiffLineItem:
    return DiffLineItem(
        source_line_no=source_line_no,
        content=content,
        diff_type=diff_type,
        key=key,
        highlights=highlights or [],
    )


def _classify_pair(left_line: str, right_line: str, format_type: str) -> str:
    left_field = _parse_field_line(left_line, format_type)
    right_field = _parse_field_line(right_line, format_type)
    if left_field and right_field:
        left_key, left_value = left_field
        right_key, right_value = right_field
        if left_key != right_key:
            return "conflict"
        if _normalize_value(left_value) == _normalize_value(right_value):
            return "equal"
        return "modified"
    if left_line == right_line:
        return "equal"
    return "modified"


def _is_different_field_pair(left_line: str, right_line: str, format_type: str) -> bool:
    left_field = _parse_field_line(left_line, format_type)
    right_field = _parse_field_line(right_line, format_type)
    return bool(left_field and right_field and left_field[0] != right_field[0])


def _append_row(
        rows: List[AlignedDiffRow],
        *,
        left_line: Optional[str],
        right_line: Optional[str],
        left_no: Optional[int],
        right_no: Optional[int],
        diff_type: str,
        format_type: str,
) -> None:
    row_no = len(rows) + 1
    left_key = None
    right_key = None
    if left_line:
        parsed = _parse_field_line(left_line, format_type)
        left_key = parsed[0] if parsed else None
    if right_line:
        parsed = _parse_field_line(right_line, format_type)
        right_key = parsed[0] if parsed else None

    if diff_type == "left_only":
        left_item = _build_line_item(
            content=left_line or "",
            diff_type="left_only",
            source_line_no=left_no,
            key=left_key,
        )
        right_item = _empty_item()
    elif diff_type == "right_only":
        left_item = _empty_item()
        right_item = _build_line_item(
            content=right_line or "",
            diff_type="right_only",
            source_line_no=right_no,
            key=right_key,
        )
    elif diff_type == "modified":
        left_highlights, right_highlights = _char_highlights(left_line or "", right_line or "")
        left_item = _build_line_item(
            content=left_line or "",
            diff_type="modified",
            source_line_no=left_no,
            key=left_key or right_key,
            highlights=left_highlights,
        )
        right_item = _build_line_item(
            content=right_line or "",
            diff_type="modified",
            source_line_no=right_no,
            key=left_key or right_key,
            highlights=right_highlights,
        )
    elif diff_type == "conflict":
        left_item = _build_line_item(
            content=left_line or "",
            diff_type="left_only",
            source_line_no=left_no,
            key=left_key,
        )
        right_item = _build_line_item(
            content=right_line or "",
            diff_type="right_only",
            source_line_no=right_no,
            key=right_key,
        )
    else:
        left_item = _build_line_item(
            content=left_line or "",
            diff_type="equal",
            source_line_no=left_no,
            key=left_key,
        )
        right_item = _build_line_item(
            content=right_line or "",
            diff_type="equal",
            source_line_no=right_no,
            key=right_key,
        )

    rows.append(AlignedDiffRow(row_no=row_no, left=left_item, right=right_item))


def _build_line_tokens(lines: List[str], format_type: str) -> List[Tuple[str, str]]:
    counters: dict = {}
    tokens: List[Tuple[str, str]] = []
    for line in lines:
        if format_type == "xml" and _is_length_header_line(line):
            tokens.append(("length_header", line.strip()))
            continue
        parsed = _parse_field_line(line, format_type)
        if parsed:
            _, match_key = _make_match_key(parsed[0], counters, format_type)
            tokens.append(("field", match_key))
        else:
            tokens.append(("struct", line.strip()))
    return tokens


def _line_match_token(line: str, format_type: str) -> Tuple[str, str]:
    if format_type == "xml" and _is_length_header_line(line):
        return "length_header", line.strip()
    parsed = _parse_field_line(line, format_type)
    if parsed:
        return "field", parsed[0]
    return "struct", line.strip()


def _diff_lines_positional(
        left_lines: List[str],
        right_lines: List[str],
        format_type: str,
) -> List[AlignedDiffRow]:
    rows: List[AlignedDiffRow] = []
    if format_type in {"json", "xml"}:
        left_tokens = _build_line_tokens(left_lines, format_type)
        right_tokens = _build_line_tokens(right_lines, format_type)
        matcher = SequenceMatcher(None, left_tokens, right_tokens, autojunk=False)
    else:
        matcher = SequenceMatcher(None, left_lines, right_lines)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                left_line = left_lines[i1 + offset]
                right_line = right_lines[j1 + offset]
                pair_type = _classify_pair(left_line, right_line, format_type)
                _append_row(
                    rows,
                    left_line=left_line,
                    right_line=right_line,
                    left_no=i1 + offset + 1,
                    right_no=j1 + offset + 1,
                    diff_type=pair_type,
                    format_type=format_type,
                )
        elif tag == "replace":
            left_chunk = left_lines[i1:i2]
            right_chunk = right_lines[j1:j2]
            max_len = max(len(left_chunk), len(right_chunk))
            for offset in range(max_len):
                left_line = left_chunk[offset] if offset < len(left_chunk) else None
                right_line = right_chunk[offset] if offset < len(right_chunk) else None
                if left_line is not None and right_line is not None:
                    if _is_different_field_pair(left_line, right_line, format_type):
                        pair_type = "conflict"
                    else:
                        pair_type = _classify_pair(left_line, right_line, format_type)
                    _append_row(
                        rows,
                        left_line=left_line,
                        right_line=right_line,
                        left_no=i1 + offset + 1,
                        right_no=j1 + offset + 1,
                        diff_type=pair_type,
                        format_type=format_type,
                    )
                elif left_line is not None:
                    _append_row(
                        rows,
                        left_line=left_line,
                        right_line=None,
                        left_no=i1 + offset + 1,
                        right_no=None,
                        diff_type="left_only",
                        format_type=format_type,
                    )
                else:
                    _append_row(
                        rows,
                        left_line=None,
                        right_line=right_line,
                        left_no=None,
                        right_no=j1 + offset + 1,
                        diff_type="right_only",
                        format_type=format_type,
                    )
        elif tag == "delete":
            for offset in range(i1, i2):
                _append_row(
                    rows,
                    left_line=left_lines[offset],
                    right_line=None,
                    left_no=offset + 1,
                    right_no=None,
                    diff_type="left_only",
                    format_type=format_type,
                )
        elif tag == "insert":
            for offset in range(j1, j2):
                _append_row(
                    rows,
                    left_line=None,
                    right_line=right_lines[offset],
                    left_no=None,
                    right_no=offset + 1,
                    diff_type="right_only",
                    format_type=format_type,
                )
    return rows


def _diff_lines_by_key(
        left_lines: List[str],
        right_lines: List[str],
        format_type: str,
) -> List[AlignedDiffRow]:
    left_fields = _extract_field_lines(left_lines, format_type)
    right_fields = _extract_field_lines(right_lines, format_type)
    left_map = {item.match_key: item for item in left_fields}
    right_map = {item.match_key: item for item in right_fields}

    ordered_keys: List[str] = []
    seen: set = set()
    for item in left_fields:
        if item.match_key not in seen:
            ordered_keys.append(item.match_key)
            seen.add(item.match_key)
    for item in right_fields:
        if item.match_key not in seen:
            ordered_keys.append(item.match_key)
            seen.add(item.match_key)

    rows: List[AlignedDiffRow] = []

    left_struct = _extract_structural_lines(left_lines, format_type)
    right_struct = _extract_structural_lines(right_lines, format_type)
    struct_rows = _diff_lines_positional(
        [line for _, line in left_struct],
        [line for _, line in right_struct],
        format_type,
    )
    rows.extend(struct_rows)

    for key in ordered_keys:
        left_item = left_map.get(key)
        right_item = right_map.get(key)
        if left_item and right_item:
            if _normalize_value(left_item.value) == _normalize_value(right_item.value):
                diff_type = "equal"
            else:
                diff_type = "modified"
            _append_row(
                rows,
                left_line=left_item.content,
                right_line=right_item.content,
                left_no=left_item.line_no,
                right_no=right_item.line_no,
                diff_type=diff_type,
                format_type=format_type,
            )
        elif left_item:
            _append_row(
                rows,
                left_line=left_item.content,
                right_line=None,
                left_no=left_item.line_no,
                right_no=None,
                diff_type="left_only",
                format_type=format_type,
            )
        elif right_item:
            _append_row(
                rows,
                left_line=None,
                right_line=right_item.content,
                left_no=None,
                right_no=right_item.line_no,
                diff_type="right_only",
                format_type=format_type,
            )
    return rows


def _check_field_order(left_lines: List[str], right_lines: List[str], format_type: str) -> Tuple[bool, Optional[str]]:
    left_keys = [item.match_key for item in _extract_field_lines(left_lines, format_type)]
    right_keys = [item.match_key for item in _extract_field_lines(right_lines, format_type)]
    if not left_keys or not right_keys:
        return True, None
    if set(left_keys) == set(right_keys) and left_keys != right_keys:
        return False, "字段顺序不一致"
    return True, None


def _rows_is_equal(rows: List[AlignedDiffRow]) -> bool:
    for row in rows:
        if row.left.diff_type != "equal" or row.right.diff_type != "equal":
            return False
    return True


def compare_messages(left_text: str, right_text: str, order_control: int) -> RepDiffResponse:
    format_type = _detect_format(left_text, right_text)
    left_lines = left_text.splitlines()
    right_lines = right_text.splitlines()
    respect_order = order_control == 1

    order_consistent = True
    order_message = None
    if respect_order and format_type in {"json", "xml"}:
        order_consistent, order_message = _check_field_order(left_lines, right_lines, format_type)

    if respect_order or format_type == "text":
        rows = _diff_lines_positional(left_lines, right_lines, format_type)
    else:
        rows = _diff_lines_by_key(left_lines, right_lines, format_type)

    is_equal = _rows_is_equal(rows)
    if respect_order and not order_consistent:
        is_equal = False

    return RepDiffResponse(
        is_equal=is_equal,
        format_type=format_type,
        order_consistent=order_consistent,
        order_message=order_message,
        rows=rows,
    )
