# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : generate_service.py
@DateTime: 2026/11/16 10:40
"""
from typing import Any, Dict, List, Tuple

from backend.applications.toolbox.schemas.generate_schema import GenerateVirtualInfo
from backend.common import GENERATE
from backend.configure import LOGGER

# 生成结果的年月日时分秒输出字段：键为 generate_datetime 的格式编号，值为响应字段名
DATETIME_OUTPUT_FIELDS: Dict[int, str] = {
    11: "Y",
    12: "M",
    13: "D",
    14: "H",
    15: "M",
    16: "S",

    21: "YMD1",
    22: "YMD2",
    23: "YMD3",

    31: "HMS1",
    32: "HMS2",
    33: "HMS3",

    41: "YMDHMS1",
    42: "YMDHMS2",
    43: "YMDHMS3",

    51: "YMDHMSF1",
    52: "YMDHMSF2",
    53: "YMDHMSF3",
}

# 历史与未来时间的偏移区间：键为年月日时分秒，值为随机偏移的最小值与最大值
DATETIME_OFFSET_RANGES: Dict[str, Dict[str, Tuple[int, int]]] = {
    "history": {
        "year": (-50, -10),
        "month": (-12, -1),
        "day": (-31, -1),
        "hour": (-60, -1),
        "minute": (-60, -1),
        "second": (-60, -1),
    },
    "future": {
        "year": (5, 50),
        "month": (1, 12),
        "day": (1, 31),
        "hour": (1, 60),
        "minute": (1, 60),
        "second": (1, 60),
    },
}


def generate_virtual_info(generate_in: GenerateVirtualInfo) -> Dict[str, Any]:
    """
    按入参生成人员、时间与随机标识数据。

    :param generate_in: 虚拟信息生成入参
    :return: 生成结果，键位为 person、now、history、future 与随机标识类型
    """
    data: Dict[str, Any] = {}

    if generate_in.personOption:
        data["person"] = _generate_persons(generate_in)

    for datetime_option in generate_in.datetimeOption:
        data[datetime_option] = _generate_datetime_group(datetime_option)

    for random_option in generate_in.randomOption:
        data[random_option] = _generate_random_values(generate_in.number, random_option)

    LOGGER.info(
        f"随机生成虚拟信息成功, 关键字段: [number={generate_in.number}, "
        f"person={generate_in.personOption}, datetime={generate_in.datetimeOption}, "
        f"random={generate_in.randomOption}]"
    )
    return data


def _generate_persons(generate_in: GenerateVirtualInfo) -> List[Dict[str, Any]]:
    """
    批量生成随机人员信息并按选中字段裁剪。

    :param generate_in: 虚拟信息生成入参
    :return: 人员信息字典列表
    """
    persons: List[Dict[str, Any]] = []
    for _ in range(generate_in.number):
        info: Dict[str, Any] = GENERATE.generate_information(
            minAge=generate_in.minAge,
            maxAge=generate_in.maxAge,
            convert="capitalize",
        )
        persons.append({key: value for key, value in info.items() if key in generate_in.personOption})
    return persons


def _generate_datetime_group(datetime_option: str) -> Dict[str, str]:
    """
    生成指定时间维度的全部格式结果。

    :param datetime_option: 时间类型，取值为 now、history、future
    :return: 格式编号对应的输出字段字典
    """
    offsets: Dict[str, int] = {}
    if datetime_option in DATETIME_OFFSET_RANGES:
        offsets = {
            field: GENERATE.generate_random_int(minimum, maximum)
            for field, (minimum, maximum) in DATETIME_OFFSET_RANGES[datetime_option].items()
        }

    group: Dict[str, str] = {}
    for fmt, field in DATETIME_OUTPUT_FIELDS.items():
        # 月份与分钟共用输出字段 M，保留先写入的月份，避免覆盖
        group.setdefault(field, GENERATE.generate_datetime(
            **offsets,
            fmt=fmt,
            is_microsecond=fmt > 50,
        ))
    return group


def _generate_random_values(number: int, random_option: str) -> List[Any]:
    """
    生成指定类型的随机标识列表。

    :param number: 生成条数
    :param random_option: 随机标识类型，取值为 uuid、timestamp、global、random
    :return: 随机标识列表
    """
    if random_option == "uuid":
        return [GENERATE.generate_uuid() for _ in range(number)]
    if random_option == "timestamp":
        return [GENERATE.generate_timestamp() for _ in range(number)]
    if random_option == "global":
        return [GENERATE.generate_global_serial_number() for _ in range(number)]
    return [GENERATE.generate_string(length=GENERATE.generate_random_int(6, 30)) for _ in range(number)]
