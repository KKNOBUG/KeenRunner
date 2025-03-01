# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : generate_schema.py
@DateTime: 2025/2/28 15:02
"""
from typing import List, Dict

from pydantic import BaseModel, Field, field_validator, model_validator

PERSON_OPTION_MAP: Dict[str, str] = {
    "中文姓名": "name",
    "英文姓名": "alias",
    "年龄": "age",
    "性别": "gender",
    "证件号码": "ssn",
    "银行卡号": "card",
    "手机号码": "phone",
    "电子邮箱": "email",
    "家庭住址": "address",
    "公司名称": "company",
    "公司地址": "company_address",
    "工作职位": "job",
    "出生年月(Ymd)": "birthday1",
    "出生年月(Y-m-d)": "birthday2",
}
DATETIME_OPTION_MAP: Dict[str, str] = {
    "现在": "now",
    "历史": "history",
    "未来": "future",
}
RANDOM_OPTION_MAP: Dict[str, str] = {
    "UUID": "uuid",
    "时间戳": "timestamp",
    "流水号": "global",
    "随机数": "random",
}


class GenerateVirtualInfo(BaseModel):
    number: int = Field(ge=1)
    minAge: int = Field(ge=1)
    maxAge: int = Field(ge=1)
    personOption: List[str] = list(PERSON_OPTION_MAP.keys())
    datetimeOption: List[str] = list(DATETIME_OPTION_MAP.keys())
    randomOption: List[str] = list(RANDOM_OPTION_MAP.keys())

    @field_validator('personOption')
    def person_option_conversion(cls, personOption) -> list:
        _option_key: set = set(PERSON_OPTION_MAP.keys())
        if not set(personOption).issubset(_option_key):
            raise ValueError("personOption字段存在未预定义元素")
        personOption = [PERSON_OPTION_MAP[item] for item in personOption]
        return personOption

    @field_validator('datetimeOption')
    def datetime_option_conversion(cls, datetimeOption) -> list:
        _option_key: set = set(DATETIME_OPTION_MAP.keys())
        if not set(datetimeOption).issubset(_option_key):
            raise ValueError("datetimeOption字段存在未预定义元素")
        datetimeOption = [DATETIME_OPTION_MAP[item] for item in datetimeOption]
        return datetimeOption

    @field_validator('randomOption')
    def random_option_conversion(cls, randomOption) -> list:
        _option_key: set = set(RANDOM_OPTION_MAP.keys())
        if not set(randomOption).issubset(_option_key):
            raise ValueError("randomOption字段存在未预定义元素")
        randomOption = [RANDOM_OPTION_MAP[item] for item in randomOption]
        return randomOption

    @model_validator(mode='after')
    def check_age_range(cls, model):
        min_age = model.minAge
        max_age = model.maxAge
        if max_age < min_age:
            raise ValueError("maxAge字段必须大于等于minAge字段")
        return model
