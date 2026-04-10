# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_xlsx_create
@DateTime: 2026/4/10 15:54
"""

import json
import random
import string
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

from backend.applications.aotutest.services.autotest_data_source2_crud import AUTOTEST_API_DATA_CREATE_CRUD
# =============================
# 数据模型
# =============================
from backend.applications.aotutest.schemas.autotest_data_generate_schema import AutoTestApiDataCreateUpdate


@dataclass
class Field:
    cn_name: str
    en_name: str
    data_type: str
    length: Optional[str]
    required: Optional[str]
    enum: Optional[str]


# =============================
# Excel读取
# =============================

def read_excel_template(file_path: str) -> List[Field]:
    df = pd.read_excel(file_path, sheet_name=0, header=None)

    header_row = None
    header_filed = ["英文名称", "中文名称", "数据类型", "长度", "是否必输", "枚举值"]
    input_row = None
    output_row = None
    header_all = []

    for i, row in df.iterrows():
        row_values = [str(v).strip() for v in row.values]

        if "英文名称" in row_values and header_row is None:
            header_row = i
            header_all = [x for x in header_filed if x not in row_values]

        if "输入" in row_values and input_row is None:
            input_row = i

        if "输出" in row_values and output_row is None:
            output_row = i

    if header_row is None:
        raise ValueError("未找到表头行缺少【英文名称】")
    if header_row and header_all != []:
        raise ValueError(f"未找到表头行缺少【{header_all}】")
    if input_row is None:
        raise ValueError("未找到【输入】标识行")

    headers = []
    for v in df.iloc[header_row].values:
        if pd.isna(v):
            break
        headers.append(str(v).strip())

    start = input_row + 1
    end = output_row if output_row else len(df)

    data_df = df.iloc[start:end, :len(headers)].copy()
    data_df.columns = headers

    fields: List[Field] = []

    for _, row in data_df.iterrows():

        cn_name = str(row.get("中文名称", "")).strip()
        en_name = str(row.get("英文名称", "")).strip()
        data_type = str(row.get("数据类型", "")).strip()
        length = str(row.get("长度", "")).strip()
        required = str(row.get("是否必输", "")).strip()
        enum = str(row.get("枚举值", "")).strip()

        if not en_name or en_name == "nan":
            continue

        fields.append(
            Field(
                cn_name=cn_name,
                en_name=en_name,
                data_type=data_type,
                length=None if length in ["", "nan"] else length,
                required=None if required in ["", "nan"] else required,
                enum=None if enum in ["", "nan"] else enum,
            )
        )

        # 处理 list / array 子字段结构
    processed_fields: List[Field] = []
    current_parent: Optional[str] = None

    for f in fields:
        dtype = (f.data_type or "").lower()

        # 如果是 list / array 字段
        if dtype in ["list", "array"]:
            current_parent = f.en_name
            processed_fields.append(f)
            continue

        # 如果当前存在父字段，则认为是子字段
        if current_parent:
            f = Field(
                cn_name=f.cn_name,
                en_name=f"{current_parent}[0].{f.en_name}",
                data_type=f.data_type,
                length=f.length,
                required=f.required,
                enum=f.enum,
            )

        processed_fields.append(f)

    return processed_fields


# =============================
# 工具函数
# =============================

def is_required(value: Optional[str]) -> bool:
    if not value:
        return False
    return str(value).strip().lower() in ["是", "m", "y", "true"]


def random_string(length: int) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def random_enum_invalid(enum_str: str, length: int):
    values = [v.strip() for v in enum_str.split(',') if v.strip()]
    max_int = length * 9
    while True:
        if length == 1 and len(values) == 10 and all(x in "0123456789" for x in values):
            val = str(random.choice(string.ascii_letters))
        else:
            val = str(random.randint(0, max_int))
        if val not in values:
            return val


def generate_length_invalid(field: Field, rule: str):
    if not field.length:
        return None, None
    s = field.length.replace("，", ",")
    s = s.replace("(", "").replace(")", "")
    s = s.replace("（", "").replace("）", "")
    if rule == 'length_int':
        if ',' in s:
            all_length = int(s.split(',')[0].strip())
            float_length = int(s.split(',')[1].strip())
            length = all_length - float_length
            if length <= 0:
                raise ValueError(f"{field.cn_name}小数位数大于等于整数位数")
        else:
            length = int(s.strip())
        invalid_len = length + 1
        value = "9" * invalid_len
        return value, length
    else:
        if ',' not in s:
            return None, None
        print(field.cn_name)
        float_length = int(s.split(',')[1].strip())
        invalid_len = float_length + 1
        value = "9." + "9" * invalid_len
        return value, float_length


def generate_decimal_invalid(field: Field, decimal_flag: str):
    if not field.length:
        return None
    s = field.length.replace("，", ",")
    if ',' not in s:
        return None
    s = s.replace("(", "").replace(")", "")
    s = s.replace("（", "").replace("）", "")
    all_length = int(s.split(',')[0].strip())
    float_length = int(s.split(',')[1].strip())
    int_length = all_length - float_length
    if int_length <= 0:
        raise ValueError(f"{field.cn_name}小数位数大于等于整数位数")
    if decimal_flag == "decimal_nine":
        value = "9" * int_length + "." + "9" * float_length
    elif decimal_flag == "decimal_nine_max":
        value = "9" * int_length + "." + "9" * float_length
        decimal_value = Decimal(value)
        decimal_value += Decimal(f"0.{'0' * (float_length - 1)}1")
        value = decimal_value.__str__()
    elif decimal_flag == "decimal_nine_min":
        value = "9" * int_length + "." + "9" * float_length
        decimal_value = Decimal(value)
        decimal_value -= Decimal(f"0.{'0' * (float_length - 1)}1")
        value = decimal_value.__str__()
    elif decimal_flag == "decimal_zero":
        value = "0"
    elif decimal_flag == "decimal_zero_min":
        value = f"-0.{'0' * (float_length - 1)}1"
    else:
        value = f"0.{'0' * (float_length - 1)}1"
    return value


def generate_cases_np(fields: List[Field], selected_rules: List[str], base_json: Dict[str, Any]):
    if "body" in base_json.keys() or "Body" in base_json.keys():
        base_json = base_json.get("body", base_json.get("Body"))
    base_json_neo = {}
    for k, v in base_json.items():
        if isinstance(v, list) and isinstance(v[0], dict):
            for a, b in v[0].items():
                base_json_neo[f"{k}[0].{a}"] = b
        elif isinstance(v, dict):
            for a, b in v.items():
                base_json_neo[f"{k}.{a}"] = b
        else:
            base_json_neo[k] = v

    base_array = np.array([base_json_neo for _ in range(len(fields) * len(selected_rules))], dtype=object)
    idx = 1
    row = base_json_neo.copy()
    row["case_name"] = "正交易场景"
    base_array[0] = row
    for field in fields:
        dtype = (field.data_type or "").lower()
        if dtype in ["list", "array"]:
            continue
        rule_flag = True
        for rule in selected_rules:
            row = base_json_neo.copy()
            if rule in ("required_", "required_null"):
                if not field.required:
                    if rule_flag:
                        row["case_name"] = f"【{field.cn_name}】【{field.en_name}】接口文档的是否必输项为空，请检查"
                        rule_flag = False
                else:
                    if is_required(field.required):
                        if rule == "required_":
                            row[field.en_name] = ""
                            config_val = "空"
                        else:
                            row[field.en_name] = "null"
                            config_val = "null"
                        row["case_name"] = f"【{field.cn_name}】【{field.en_name}】必输项校验，生成{config_val}值"
            elif rule in ("length_int", "length_float"):
                value, config_len = generate_length_invalid(field, rule)
                config_val = "整数" if rule == "length_int" else "小数"
                if value:
                    row[field.en_name] = value
                    row[
                        "case_name"] = f"【{field.cn_name}】【{field.en_name}】长度校验，配置{config_val}长度{config_len}，生成长度{config_len + 1}"
            elif rule in ("decimal_nine", "decimal_nine_max", "decimal_nine_min", "decimal_zero", "decimal_zero_min",
                          "decimal_zero_max"):
                value = generate_decimal_invalid(field, rule)
                if value:
                    row[field.en_name] = value
                    row["case_name"] = f"【{field.cn_name}】【{field.en_name}】边界值校验校验，配置长度{field.length}，生成值{value}"
            elif rule == "enum":
                if field.enum:
                    try:
                        length = int(field.length)
                    except Exception:
                        raise ValueError(f"{field.cn_name}枚举值长度异常")
                    invalid = random_enum_invalid(field.enum, length)
                    row[field.en_name] = invalid
                    row["case_name"] = f"【{field.cn_name}】【{field.en_name}】枚举值校验，配置枚举值为[{field.enum}]，生成枚举值{invalid}"
                else:
                    if not field.length:
                        row["case_name"] = f"【{field.cn_name}】【{field.en_name}】接口文档的长度项和枚举值项均为空，请检查"
            else:
                continue
            if row.get("case_name"):
                base_array[idx] = row
                idx += 1
    return base_array[:idx].tolist()


# =============================
# Excel导出
# =============================

def export_excel(cases: List[Dict[str, Any]], fields: List[Field], output_file: str):
    # 父字段(list/array)不作为导出行
    export_fields = [f for f in fields if (f.data_type or "").lower() not in ["list", "array"]]

    columns = ["case_name"] + [f.en_name for f in export_fields]

    df = pd.DataFrame(cases)

    for col in columns:
        if col not in df.columns:
            df[col] = ""

    df = df[columns]

    # 以case_name作为列标题进行转置
    df.set_index("case_name", inplace=True)

    df = df.T

    # 第一列作为字段名
    df.index.name = ""

    df = df.reset_index()

    # 插入 Body 行（表头第二行第一列）
    # body_row = {col: "" for col in df.columns}
    # body_row[""] = "Body"
    # df = pd.concat([pd.DataFrame([body_row]), df], ignore_index=True)

    body_row = pd.Series([None] * len(df.columns), index=df.columns)
    body_row.iloc[0] = "Body"
    df = pd.concat([body_row.to_frame().T, df], ignore_index=True)

    df.to_excel(output_file, index=False)


async def generate_test_data(input_excel: str, output_excel: str, rules: List[str], json_message: Union[str, dict],
                             create_id: int):
    await AUTOTEST_API_DATA_CREATE_CRUD.update_data_create(
        data_in=(
            AutoTestApiDataCreateUpdate(
                id=create_id,
                create_status="1"
            )
        )
    )
    if "length" in rules:
        append_rules = ["length_int", "length_float"]
        rules.extend(append_rules)
    if "decimal" in rules:
        append_rules = ["decimal_nine", "decimal_nine_max", "decimal_nine_min", "decimal_zero", "decimal_zero_min",
                        "decimal_zero_max", ]
        rules.extend(append_rules)
    if "required" in rules:
        append_rules = ["required_", "required_null"]
        rules.extend(append_rules)
    try:
        fields = read_excel_template(input_excel)
        if isinstance(json_message, dict):
            base_json = json_message
        else:
            base_json = json.loads(json_message)
        cases = generate_cases_np(fields, rules, base_json)
        export_excel(cases, fields, output_excel)
        # print("成功")
        await AUTOTEST_API_DATA_CREATE_CRUD.update_data_create(
            data_in=(
                AutoTestApiDataCreateUpdate(
                    id=create_id,
                    create_status="3",
                    file_desc=""
                )
            )
        )
    except Exception as e:
        #     print(e)
        await AUTOTEST_API_DATA_CREATE_CRUD.update_data_create(
            data_in=(
                AutoTestApiDataCreateUpdate(
                    id=create_id,
                    create_status="2",
                    file_desc=f"{e}"
                )
            )
        )


if __name__ == "__main__":
    input_excel = r"E:\KF5726\Doc\IIMClient\cs0077\file\司库查询当日余额.xlsx"
    output_excel = r"E:\KF5726\桌面\测试数据1.xlsx"

    selected_rule = [
        "required",
        "length",
        "decimal",
        "enum",
    ]

    # 报文输入(JSON)
    #     base_message = """
    # {"Body": {"dbMedmAcctTp": "6000000056", "maxAmt": 30000000000000, "minAmt": 1, "lstFeeIn": [{"medmAcctTp": "03003938254"}], "currency": "CNY"}, "Head": {"TxnDt": "20250808", "TxnTm": "103858", "CnlTxnCd": "DEFAULT", "MsgVerNo": "3.0", "GlblSrlNo": "2025080819510802002700002319", "InttCnlCd": "SK", "CnsmrSrlNo": "20250808195108c66965efa3fed01", "CnsmrSysId": "TBS.AZ"}}
    #     """
    base_message = {
        "Body": {
            "custNo": "6000000056",
            "maxAmt": 30000000000000,
            "minAmt": 1,
            "accList": [
                {
                    "accNo": "03003938254"
                }
            ],
            "currency": "CNY"
        },
        "Head": {
            "TxnDt": "20250808",
            "TxnTm": "103858",
            "CnlTxnCd": "DEFAULT",
            "MsgVerNo": "3.0",
            "GlblSrlNo": "2025080819510802002700002319",
            "InttCnlCd": "SK",
            "CnsmrSrlNo": "20250808195108c66965efa3fed01",
            "CnsmrSysId": "TBS.AZ"
        }
    }
    import asyncio

    # await generate_test_data(
    #         input_excel,
    #         output_excel,
    #         selected_rules,
    #         base_message,
    #         2
    #     )
    asyncio.run(generate_test_data(
        input_excel,
        output_excel,
        selected_rule,
        base_message,
        2
    ))
