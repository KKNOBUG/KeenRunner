# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_source_parser.py
@DateTime: 2026/3/6
参数化驱动：将 xlsx 解析为约定 JSON 结构。
输出格式：{ "step_code"(sheet名): { "场景1": { "head": {...}, "body": {...}, "assert": {...} }, ... }, ... }
xlsx 约定：无表头(header=None)；第 0 行第 2 列起为场景名；第 1 列为行标签（head/body/assert 及字段名）；Head/Body 行值为 KV 文本可解析。
"""
import asyncio
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Tuple

import pandas as pd

from backend import LOGGER

_executor = ThreadPoolExecutor(max_workers=4)


def parse_kv_string(text: str) -> Dict[str, str]:
    """
    把：
        Ammy:7860000182_x000D_
        Ccy:CNY
    转成：
        {"Ammy": "7860000182", "Ccy": "CNY"}
    """
    if not isinstance(text, str):
        return {}

    text = text.replace("_x000D_", "").strip()
    result = {}
    for line in re.split(r"[\n\r]+", text):
        if ":" in line:
            k, v = line.split(":", 1)
            result[k.strip()] = v.strip()
    return result


def _parse_sheet_fast(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """单 sheet 解析：首行第 2 列起为场景名，首列为 head/body/assert 及字段，返回 { 场景名: { head, body, assert } }。"""
    values = df.values
    if values.size == 0:
        return {}

    scene_names = values[0, 1:]
    first_col = values[1:, 0]
    data_values = values[1:, 1:]

    sections: Dict[str, List[int]] = {"head": [], "body": [], "assert": []}
    section_row_index: Dict[str, Any] = {"head": None, "body": None}
    current_section = None

    for i, cell in enumerate(first_col):
        if not isinstance(cell, str):
            continue
        text = cell.strip().lower()
        if text == "head":
            current_section = "head"
            section_row_index["head"] = i
            continue
        if text == "body":
            current_section = "body"
            section_row_index["body"] = i
            continue
        if text in ("响应报文校验", "assert"):
            current_section = "assert"
            continue
        if current_section:
            sections[current_section].append(i)

    result: Dict[str, Dict[str, Any]] = {}
    col_count = data_values.shape[1]

    for col_idx in range(col_count):
        scene_name = scene_names[col_idx]
        if pd.isna(scene_name) or not str(scene_name).strip():
            continue
        scene_name = str(scene_name).strip()
        record: Dict[str, Any] = {"head": {}, "body": {}, "assert": {}}
        has_data = False

        for section in ("head", "body"):
            row_idx = section_row_index.get(section)
            if row_idx is not None:
                raw_text = data_values[row_idx, col_idx]
                if pd.notna(raw_text):
                    parsed_dict = parse_kv_string(str(raw_text))
                    if parsed_dict:
                        record[section].update(parsed_dict)
                        has_data = True

        for section, rows in sections.items():
            for r in rows:
                key = first_col[r]
                value = data_values[r, col_idx]
                if key and pd.notna(value):
                    record[section][str(key).strip()] = value
                    has_data = True

        if has_data:
            result[scene_name] = record

    return result


async def _parse_sheet_async(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _parse_sheet_fast, df)


async def _excel_to_json_async(file_path: str) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """读 xlsx 全部 sheet(header=None)，异步解析每个 sheet，返回 { sheet_name: { 场景名: { head, body, assert } } }。"""
    sheets = pd.read_excel(file_path, sheet_name=None, header=None, engine="openpyxl")
    tasks = [
        _parse_sheet_async(df)
        for df in sheets.values()
        if not df.empty
    ]
    results = await asyncio.gather(*tasks)
    sheet_names = [k for k, v in sheets.items() if not v.empty]
    return dict(zip(sheet_names, results))


async def parse_xlsx_first_sheet_async(file_path: str) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """
    仅解析 xlsx 的第一个 sheet 页（单步骤数据集上传用）。

    :param file_path: xlsx 文件路径。
    :return: (step_data, dataset_names)。step_data 为单 sheet 解析结果：
             { "场景1": { "head": {...}, "body": {...}, "assert": {...} }, ... }
             dataset_names 为该 sheet 中的场景名称列表（已排序）。
    :raises FileNotFoundError: 文件不存在。
    :raises ValueError: 解析失败。
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    # 只读第一个 sheet
    df = pd.read_excel(file_path, sheet_name=0, header=None, engine="openpyxl")
    if df.empty:
        return {}, []
    step_data = await _parse_sheet_async(df)
    dataset_names = sorted(step_data.keys()) if step_data else []
    LOGGER.info(f"解析 xlsx 首 sheet 完成: {file_path}, dataset_names={dataset_names}")
    return step_data, dataset_names


async def parse_xlsx_to_parsed_data_async(file_path: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    解析 xlsx 全部 sheet 为约定结构并提取数据集名称列表（多步骤数据集上传用）。

    :param file_path: xlsx 文件路径。
    :return: (parsed_data, dataset_names)。parsed_data 结构：
             { "sheet_name_or_step_code": { "场景1": { "head": {...}, "body": {...}, "assert": {...} }, ... }, ... }
             dataset_names 为所有 sheet 中出现的去重排序后的场景名称列表。
    :raises FileNotFoundError: 文件不存在。
    :raises ValueError: 解析失败。
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    parsed_data = await _excel_to_json_async(file_path)
    all_dataset_names: set = set()
    for sheet_data in parsed_data.values():
        all_dataset_names.update(sheet_data.keys())
    dataset_names = sorted(all_dataset_names)
    LOGGER.info(f"解析 xlsx 完成: {file_path}, sheets={len(parsed_data)}, dataset_names={dataset_names}")
    return parsed_data, dataset_names
