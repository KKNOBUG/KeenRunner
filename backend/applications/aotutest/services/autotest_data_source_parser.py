# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_source_parser.py
@DateTime: 2026/3/6
"""
import asyncio
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from backend.configure import LOGGER

_executor = ThreadPoolExecutor(max_workers=5)


def json_safe_value(value: Any) -> Any:
    """
    将单元格/字段值递归转为JSON可序列化类型。

    :param value: 原始值(可能为NaN/Inf/NaT/numpy类型或嵌套结构)
    :return: JSON可序列化值，NaN/Inf/NaT转为None
    """
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


def parse_kv_string(text: str) -> Dict[str, str]:
    """
    将多行key:value文本解析为字典(去除_x000D_回车符)。

    :param text: 形如 "Ammy:7860000182_x000D_\nCcy:CNY" 的多行文本
    :return: 解析后的字典，如 {"Ammy": "7860000182", "Ccy": "CNY"}；非字符串入参返回 {}
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
_SECTION_MARKERS_UPPER = {"HEAD", "BODY", "ASSERT_HEAD", "ASSERT_BODY"}

# 数据矩阵方向：水平(场景为行) / 垂直(场景为列)
AXIS_HORIZONTAL = 0
AXIS_VERTICAL = 1


def is_section_marker(value: Any) -> bool:
    """
    判断单元格是否为分区标记。

    :param value: 单元格值
    :return: HEAD/BODY/ASSERT_HEAD/ASSERT_BODY(大小写不敏感)返回True
    """
    return isinstance(value, str) and value.strip().upper() in _SECTION_MARKERS_UPPER


def _row_has_section_marker(cells: Any) -> bool:
    """
    判断一组单元格中是否包含分区标记。

    :param cells: 单元格序列(如某一行或某一列)
    :return: 含HEAD/BODY/ASSERT_HEAD/ASSERT_BODY(大小写不敏感)返回True，否则False
    """
    for cell in cells:
        if isinstance(cell, str) and cell.strip().lower() in _SECTION_LABEL_TO_KEY:
            return True
    return False


def detect_matrix_axis(values: Any) -> int:
    """
    检测二维矩阵方向并校验合法性。

    :param values: 二维矩阵(DataFrame.values)
    :return: 方向，水平模式(第0行含分区标记)返回AXIS_HORIZONTAL，垂直模式(第0列含分区标记)返回AXIS_VERTICAL
    """
    if values.size == 0:
        raise ValueError("数据矩阵为空，无法识别方向")
    if _row_has_section_marker(values[0]):
        return AXIS_HORIZONTAL
    first_col = values[1:, 0] if values.shape[0] > 1 else np.array([])
    if _row_has_section_marker(first_col):
        return AXIS_VERTICAL
    raise ValueError("无法识别数据矩阵方向：第 0 行或第 0 列需包含 HEAD/BODY/ASSERT_HEAD/ASSERT_BODY 分区标记")


def resolve_matrix_axis(matrix: List[List[Any]], declared_axis: Optional[int] = None) -> int:
    """
    按分区标记识别矩阵方向；识别失败时回落到调用方声明的 axis。

    客户端/库中的 axis 可能与矩阵结构不一致（例如模型默认 0，实际为垂直矩阵），
    清洗与解析必须以矩阵本身为准。

    :param matrix: 二维矩阵
    :param declared_axis: 调用方声明的方向
    :return: 实际使用的方向
    """
    padded = _pad_matrix(matrix)
    if not padded:
        return declared_axis if declared_axis in (AXIS_HORIZONTAL, AXIS_VERTICAL) else AXIS_VERTICAL
    try:
        return detect_matrix_axis(pd.DataFrame(padded).values)
    except ValueError:
        if declared_axis in (AXIS_HORIZONTAL, AXIS_VERTICAL):
            return declared_axis
        raise


def normalize_dataset_record(step_data: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    规范化单场景结构，仅保留head/body/assert_head/assert_body，缺失键补 {}。

    :param step_data: 单场景原始数据(可能非dict)
    :return: 含四个分区键的规范化字典
    """
    src = step_data if isinstance(step_data, dict) else {}
    return {
        key: dict(src[key]) if isinstance(src.get(key), dict) else {}
        for key in _DATASET_SECTION_KEYS
    }


def _parse_sheet_fast(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    垂直模式解析单个sheet(第0行为场景名，第0列为分区标签/字段名)。

    :param df: 无表头(header=None)的sheet DataFrame
    :return: { 场景名: { head, body, assert_head, assert_body } }；某分区缺省时其值为 {}
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
        record = {k: {} for k in _DATASET_SECTION_KEYS}
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
            # 即使某分区无字段，四键已由记录初始化补齐
            result[scene_name] = record

    return result


def _parse_sheet_horizontal(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    水平模式解析单个sheet：第0行为分区标记与字段名，第0列为场景名。

    :param df: 无表头(header=None)的sheet DataFrame
    :return: { 场景名: { head, body, assert_head, assert_body } }；某分区缺省时其值为 {}
    """
    values = df.values
    if values.size == 0:
        return {}

    header = values[0, 1:]  # 第 0 行 col1+：分区标记 + 字段名
    scene_col = values[1:, 0]  # col0 row1+：场景名
    data_values = values[1:, 1:]  # 数据块

    # 为每个字段列确定 (数据列下标, 分区, 字段名)；分区标记列仅作切换，不作为字段
    field_columns: List[Tuple[int, str, str]] = []
    current_section = None
    for col_idx, cell in enumerate(header):
        if not isinstance(cell, str) or not cell.strip():
            continue
        section_key = _SECTION_LABEL_TO_KEY.get(cell.strip().lower())
        if section_key is not None:
            current_section = section_key
            continue
        if current_section:
            field_columns.append((col_idx, current_section, cell.strip()))

    result: Dict[str, Dict[str, Any]] = {}
    for row_idx, scene_name in enumerate(scene_col):
        if pd.isna(scene_name) or not str(scene_name).strip():
            continue
        scene_name = str(scene_name).strip()
        record = {k: {} for k in _DATASET_SECTION_KEYS}
        has_data = False
        for col_idx, section, field_key in field_columns:
            value = data_values[row_idx, col_idx]
            if pd.notna(value):
                safe_val = json_safe_value(value)
                if safe_val is None and not isinstance(value, str):
                    continue
                record[section][field_key] = safe_val
                has_data = True
        if has_data:
            result[scene_name] = record
    return result


def _parse_sheet_by_axis(df: pd.DataFrame, axis: int) -> Dict[str, Dict[str, Any]]:
    """
    根据方向分发解析单个sheet。

    :param df: 无表头(header=None)的sheet DataFrame
    :param axis: 矩阵方向，AXIS_HORIZONTAL走水平解析，否则走垂直解析
    :return: { 场景名: { head, body, assert_head, assert_body } }
    """
    if axis == AXIS_HORIZONTAL:
        return _parse_sheet_horizontal(df)
    return _parse_sheet_fast(df)


async def _parse_sheet_async(df: pd.DataFrame, axis: int) -> Dict[str, Dict[str, Any]]:
    """
    在线程池中根据方向异步解析单个sheet。

    :param df: 无表头(header=None)的sheet DataFrame
    :param axis: 矩阵方向
    :return: { 场景名: { head, body, assert_head, assert_body } }
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _parse_sheet_by_axis, df, axis)


def _cell_is_blank(value: Any) -> bool:
    """
    判断单元格是否为空白。

    :param value: 单元格值
    :return: None/NaN/纯空白字符串返回True，否则False
    """
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


def _pad_matrix(matrix: List[List[Any]]) -> List[List[Any]]:
    """
    将不规则二维列表补齐为矩形矩阵。

    :param matrix: 原始二维列表
    :return: 列宽对齐后的矩阵，短行右侧补None
    """
    if not matrix:
        return []
    width = 0
    for row in matrix:
        if isinstance(row, list) and len(row) > width:
            width = len(row)
    padded: List[List[Any]] = []
    for row in matrix:
        cells = list(row) if isinstance(row, list) else []
        if len(cells) < width:
            cells.extend([None] * (width - len(cells)))
        padded.append([json_safe_value(c) for c in cells[:width]])
    return padded


def extract_scene_names_from_matrix(matrix: List[List[Any]], axis: int) -> List[str]:
    """
    按矩阵方向提取场景名，保留出现顺序，不去重、不排序。

    :param matrix: 已对齐的二维矩阵
    :param axis: 0水平(第0列场景名) / 1垂直(第0行场景名)
    :return: 非空场景名列表
    """
    names: List[str] = []
    if not matrix:
        return names
    if axis == AXIS_HORIZONTAL:
        for row in matrix[1:]:
            if not row:
                continue
            text = "" if row[0] is None else str(row[0]).strip()
            if text:
                names.append(text)
        return names
    header = matrix[0] if matrix else []
    for cell in header[1:]:
        text = "" if cell is None else str(cell).strip()
        if text:
            names.append(text)
    return names


def _drop_empty_scene_rows(padded: List[List[Any]]) -> List[List[Any]]:
    """
    水平模式：剔除第0行以外、第0列以外全部为空的场景行。

    :param padded: 已对齐的矩形矩阵
    :return: 去掉空场景行后的矩阵，第0行始终保留
    """
    if not padded:
        return padded
    kept: List[List[Any]] = [padded[0]]
    for row in padded[1:]:
        if not all(_cell_is_blank(cell) for cell in row[1:]):
            kept.append(row)
    return kept


def _drop_empty_scene_cols(padded: List[List[Any]]) -> List[List[Any]]:
    """
    垂直模式：剔除第0列以外、第0行以外全部为空的场景列。

    :param padded: 已对齐的矩形矩阵
    :return: 去掉空场景列后的矩阵，第0列始终保留
    """
    if not padded:
        return padded
    col_count = len(padded[0])
    row_count = len(padded)
    keep_cols: List[int] = [0]
    for col_idx in range(1, col_count):
        if not all(_cell_is_blank(padded[row_idx][col_idx]) for row_idx in range(1, row_count)):
            keep_cols.append(col_idx)
    return [[row[col_idx] for col_idx in keep_cols] for row in padded]


def clean_matrix_by_axis(matrix: List[List[Any]], axis: int) -> List[List[Any]]:
    """
    按矩阵方向剔除空白字段行/列，以及无数据的场景行/列；分区标记始终保留。

    水平模式(axis=0)：剔除除HEAD/BODY/ASSERT_HEAD/ASSERT_BODY列以外的整列为空列，
    再剔除第0行以外、第0列以外全部为空的场景行。
    垂直模式(axis=1)：剔除除HEAD/BODY/ASSERT_HEAD/ASSERT_BODY行以外的整行为空行，
    再剔除第0列以外、第0行以外全部为空的场景列。
    第0列(垂直字段名 / 水平场景名)与第0行始终保留。

    :param matrix: 原始二维矩阵
    :param axis: 0水平 / 1垂直
    :return: 清洗后的二维矩阵
    """
    padded = _pad_matrix(matrix)
    if not padded:
        return []
    row_count = len(padded)
    col_count = len(padded[0])

    if axis == AXIS_HORIZONTAL:
        keep_cols: List[int] = []
        for col_idx in range(col_count):
            if col_idx == 0:
                keep_cols.append(col_idx)
                continue
            header_cell = padded[0][col_idx] if row_count else None
            if is_section_marker(header_cell):
                keep_cols.append(col_idx)
                continue
            column_cells = [padded[row_idx][col_idx] for row_idx in range(row_count)]
            if not all(_cell_is_blank(cell) for cell in column_cells):
                keep_cols.append(col_idx)
        trimmed = [[row[col_idx] for col_idx in keep_cols] for row in padded]
        return _drop_empty_scene_rows(trimmed)

    kept_rows: List[List[Any]] = []
    for row_idx, row in enumerate(padded):
        if row_idx == 0:
            kept_rows.append(row)
            continue
        if row and is_section_marker(row[0]):
            kept_rows.append(row)
            continue
        if not all(_cell_is_blank(cell) for cell in row):
            kept_rows.append(row)
    return _drop_empty_scene_cols(kept_rows)


def _dataframe_to_matrix(df: pd.DataFrame) -> List[List[Any]]:
    """
    将DataFrame转为二维矩阵，剔除全空白(None/NaN/空串)的行与列(第0列始终保留)。

    :param df: sheet DataFrame
    :return: 二维列表，NaN/NaT/Inf置为None
    """
    if df is None or df.empty:
        return []
    safe_df = df.where(pd.notna(df), None)
    col_count = len(safe_df.columns)

    # 剔除全空白列（第 0 列始终保留）
    blank_cols: Set[int] = set()
    for col_idx in range(1, col_count):
        col_values = safe_df.iloc[:, col_idx]
        if all(_cell_is_blank(json_safe_value(c)) for c in col_values):
            blank_cols.add(col_idx)
    keep_cols = [i for i in range(col_count) if i not in blank_cols]

    rows: List[List[Any]] = []
    for row in safe_df.values.tolist():
        cleaned = [json_safe_value(c) for c in row]
        projected = [cleaned[i] for i in keep_cols]
        if not all(_cell_is_blank(c) for c in projected):
            rows.append(projected)
    return rows


async def _excel_to_json_async(file_path: str) -> Tuple[Dict[str, Dict[str, Dict[str, Any]]], Dict[str, int], Dict[str, List[List[Any]]]]:
    """
    读取xlsx全部sheet，逐sheet检测方向并异步解析。

    :param file_path: xlsx文件路径
    :return: (parsed_data, sheet_axes, sheet_matrices)，分别为各sheet场景数据、方向与原始二维矩阵
    """
    sheets: Dict[str, pd.DataFrame] = pd.read_excel(file_path, sheet_name=None, header=None, engine="openpyxl")
    sheet_items: List[Tuple[str, pd.DataFrame]] = [(name, df) for name, df in sheets.items() if not df.empty]

    async def _parse_one(df: pd.DataFrame) -> Tuple[Dict[str, Dict[str, Any]], int]:
        axis = detect_matrix_axis(df.values)
        data = await _parse_sheet_async(df, axis)
        return data, axis

    results = await asyncio.gather(*[_parse_one(df) for _, df in sheet_items])
    parsed_data: Dict[str, Any] = {name: data for (name, _), (data, _) in zip(sheet_items, results)}
    sheet_axes: Dict[str, int] = {name: axis for (name, _), (_, axis) in zip(sheet_items, results)}
    sheet_matrices: Dict[str, List[List[Any]]] = {name: _dataframe_to_matrix(df) for name, df in sheet_items}
    return parsed_data, sheet_axes, sheet_matrices


async def parse_dataframe_matrix_async(
        matrix: List[List[Any]],
        axis: Optional[int] = None,
) -> Tuple[Dict[str, Dict[str, Any]], List[str], List[List[Any]], int]:
    """
    将二维矩阵按方向清洗后解析为dataset结构。

    :param matrix: 二维列表(与单步骤xlsx首sheet、header=None结构一致)
    :param axis: 调用方声明的方向，仅在无法从矩阵识别时回落；与矩阵结构冲突时以分区标记为准
    :return: (step_data, dataset_names, norm_matrix, axis)，dataset_names保持矩阵中的场景顺序
    """
    if not isinstance(matrix, list):
        raise ValueError("dataframe 须为二维列表")
    if not matrix:
        return {}, [], [], AXIS_VERTICAL if axis not in (AXIS_HORIZONTAL, AXIS_VERTICAL) else axis

    axis = resolve_matrix_axis(matrix, declared_axis=axis)
    norm_matrix = clean_matrix_by_axis(matrix, axis)
    if not norm_matrix:
        return {}, [], [], axis

    df = pd.DataFrame(norm_matrix)
    if df.empty:
        return {}, [], [], axis

    parsed = await _parse_sheet_async(df, axis)
    ordered_names = extract_scene_names_from_matrix(norm_matrix, axis)
    step_data: Dict[str, Dict[str, Any]] = {}
    dataset_names: List[str] = []
    for scene_name in ordered_names:
        record = parsed.get(scene_name)
        if not record:
            continue
        step_data[scene_name] = normalize_dataset_record(record)
        dataset_names.append(scene_name)
    for scene_name, record in parsed.items():
        if scene_name not in step_data:
            step_data[scene_name] = normalize_dataset_record(record)
            dataset_names.append(scene_name)
    return step_data, dataset_names, norm_matrix, axis


async def parse_xlsx_first_sheet_async(file_path: str) -> Tuple[Dict[str, Dict[str, Any]], List[str], List[List[Any]], int]:
    """
    仅解析xlsx首个sheet，自动识别矩阵方向。

    :param file_path: xlsx文件路径
    :return: (step_data, dataset_names, dataframe, axis)，dataframe为原始二维矩阵，axis为矩阵方向
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    # 只读第一个 sheet
    df = pd.read_excel(file_path, sheet_name=0, header=None, engine="openpyxl")
    if df.empty:
        return {}, [], [], AXIS_VERTICAL
    axis = detect_matrix_axis(df.values)
    step_data = await _parse_sheet_async(df, axis)
    dataset_names = sorted(step_data.keys()) if step_data else []
    dataframe = _dataframe_to_matrix(df)
    LOGGER.info(f"解析 xlsx 首 sheet 完成: {file_path}, axis={axis}, dataset_names={dataset_names}")
    return step_data, dataset_names, dataframe, axis


async def parse_xlsx_to_parsed_data_async(file_path: str) -> Tuple[Dict[str, Any], List[str], Dict[str, int], Dict[str, List[List[Any]]]]:
    """
    解析xlsx全部sheet为约定结构并提取数据集名称列表。

    :param file_path: xlsx文件路径
    :return: (parsed_data, dataset_names, sheet_axes, sheet_matrices)，dataset_names为去重排序后的场景名列表
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    parsed_data, sheet_axes, sheet_matrices = await _excel_to_json_async(file_path)
    all_dataset_names: Set[str] = set()
    for sheet_data in parsed_data.values():
        all_dataset_names.update(sheet_data.keys())
    dataset_names = sorted(all_dataset_names)
    LOGGER.info(f"解析 xlsx 完成: {file_path}, sheets={len(parsed_data)}, dataset_names={dataset_names}")
    return parsed_data, dataset_names, sheet_axes, sheet_matrices
