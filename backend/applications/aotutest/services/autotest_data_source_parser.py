# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_source_parser.py
@DateTime: 2026/3/6
参数化驱动：将 xlsx 解析为约定 JSON 结构。
输出格式：{ "场景1": { "head": {...}, "body": {...}, "assert_head": {...}, "assert_body": {...} }, ... }
xlsx 约定：无表头(header=None)；第 0 行第 2 列起为场景名；第 1 列为分区标签，固定四种：
HEAD（请求头参数）、BODY（请求体参数）、ASSERT_HEAD（响应头断言）、ASSERT_BODY（响应体断言）。
文件中某分区可缺省（表示不做对应操作）；落库时四个键始终补齐，缺省分区值为空对象 {}。
"""
import asyncio
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from backend.configure import LOGGER

_executor = ThreadPoolExecutor(max_workers=4)


def json_safe_value(value: Any) -> Any:
    """将单元格/字段值转为 JSON 可序列化类型；NaN/Inf/NaT → None。"""
    if value is None:
        return None
    try:
        if value is pd.NA or value is pd.NaT:
            return None
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    if isinstance(value, np.ndarray):
        return [json_safe_value(v) for v in value.tolist()]
    if isinstance(value, dict):
        return {str(k): json_safe_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe_value(v) for v in value]
    return value


def json_safe_obj(obj: Any) -> Any:
    """递归清洗任意嵌套结构，保证可被标准 JSON 序列化。"""
    return json_safe_value(obj)


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


# 落库固定四键；Excel 分区标签（不区分大小写）→ 落库键
_SECTION_LABEL_TO_KEY = {
    "head": "head",
    "body": "body",
    "assert_head": "assert_head",
    "assert_body": "assert_body",
}
_DATASET_SECTION_KEYS = ("head", "body", "assert_head", "assert_body")


def empty_dataset_record() -> Dict[str, Dict[str, Any]]:
    """返回始终含四键的空场景结构。"""
    return {k: {} for k in _DATASET_SECTION_KEYS}


def normalize_dataset_record(step_data: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    规范化单场景结构：仅保留 head/body/assert_head/assert_body，缺失键补 {}。
    """
    src = step_data if isinstance(step_data, dict) else {}
    out = empty_dataset_record()
    for key in _DATASET_SECTION_KEYS:
        val = src.get(key)
        out[key] = dict(val) if isinstance(val, dict) else {}
    return out


def _parse_sheet_fast(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    单 sheet 解析：返回 { 场景名: { head, body, assert_head, assert_body } }。
    分区标签仅识别 HEAD / BODY / ASSERT_HEAD / ASSERT_BODY（大小写不敏感）；
    某分区在文件中不存在时，落库仍保留该键且值为 {}。
    """
    values = df.values
    if values.size == 0:
        return {}

    scene_names = values[0, 1:]
    first_col = values[1:, 0]
    data_values = values[1:, 1:]

    sections: Dict[str, List[int]] = {k: [] for k in _DATASET_SECTION_KEYS}
    # HEAD/BODY 标签行自身可能带 KV 文本块
    section_row_index: Dict[str, Any] = {"head": None, "body": None}
    current_section = None

    for i, cell in enumerate(first_col):
        if not isinstance(cell, str):
            continue
        text = cell.strip().lower()
        section_key = _SECTION_LABEL_TO_KEY.get(text)
        if section_key is not None:
            current_section = section_key
            if section_key in ("head", "body"):
                section_row_index[section_key] = i
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
        record = empty_dataset_record()
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
                    safe_val = json_safe_value(value)
                    if safe_val is None and not isinstance(value, str):
                        continue
                    record[section][str(key).strip()] = safe_val
                    has_data = True

        if has_data:
            # 即使某分区无字段，四键已由 empty_dataset_record 补齐
            result[scene_name] = record

    return result


async def _parse_sheet_async(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _parse_sheet_fast, df)


def _cell_is_blank(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _dataframe_to_matrix(df: pd.DataFrame) -> Union[List[Any], object]:
    """将 DataFrame 转为二维矩阵（NaN/NaT/Inf 置为 None），剔除子项全为空白(None/NaN/空串)的行。"""
    if df is None or df.empty:
        return []
    safe_df = df.where(pd.notna(df), None)
    rows: List[List[Any]] = []
    for row in safe_df.values.tolist():
        cleaned = [json_safe_value(c) for c in row]
        if not all(_cell_is_blank(c) for c in cleaned):
            rows.append(cleaned)
    return rows


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


async def parse_dataframe_matrix_async(matrix: List[List[Any]]) -> Tuple[Dict[str, Dict[str, Any]], List[str], List[List[Any]]]:
    """
    将二维矩阵（与单步骤 xlsx 首 sheet、header=None 结构一致）解析为 dataset / dataset_names / 规范化 matrix。

    供「数据预览」表格保存时与服务端上传解析结果对齐。
    """
    if not isinstance(matrix, list):
        raise ValueError("dataframe 须为二维列表")
    if not matrix:
        return {}, [], []
    df = pd.DataFrame(matrix)
    if df.empty:
        return {}, [], []
    step_data = await _parse_sheet_async(df)
    dataset_names = sorted(step_data.keys()) if step_data else []
    norm_matrix = _dataframe_to_matrix(df)
    return step_data, dataset_names, norm_matrix


async def parse_xlsx_first_sheet_async(file_path: str) -> Tuple[Dict[str, Dict[str, Any]], List[str], List[List[Any]]]:
    """
    仅解析 xlsx 的第一个 sheet 页（单步骤数据集上传用）。

    :param file_path: xlsx 文件路径。
    :return: (step_data, dataset_names, dataframe)。step_data 为单 sheet 解析结果：
             { "场景1": { "head": {...}, "body": {...}, "assert_head": {...}, "assert_body": {...} }, ... }
             dataset_names 为该 sheet 中的场景名称列表（已排序）；
             dataframe 为该 sheet 原始二维矩阵（NaN 已转为 None）。
    :raises FileNotFoundError: 文件不存在。
    :raises ValueError: 解析失败。
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    # 只读第一个 sheet
    df = pd.read_excel(file_path, sheet_name=0, header=None, engine="openpyxl")
    if df.empty:
        return {}, [], []
    step_data = await _parse_sheet_async(df)
    dataset_names = sorted(step_data.keys()) if step_data else []
    dataframe = _dataframe_to_matrix(df)
    LOGGER.info(f"解析 xlsx 首 sheet 完成: {file_path}, dataset_names={dataset_names}")
    return step_data, dataset_names, dataframe


async def parse_xlsx_to_parsed_data_async(file_path: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    解析 xlsx 全部 sheet 为约定结构并提取数据集名称列表（多步骤数据集上传用）。

    :param file_path: xlsx 文件路径。
    :return: (parsed_data, dataset_names)。parsed_data 结构：
             { "sheet_name_or_step_code": { "场景1": { "head": {...}, "body": {...}, "assert_head": {...}, "assert_body": {...} }, ... }, ... }
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
