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

_option_map: Dict[str, str] = {
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


class GeneratePerson(BaseModel):
    number: int = Field(ge=1)
    minAge: int = Field(ge=1)
    maxAge: int = Field(ge=1)
    option: List[str] = list(_option_map.keys())

    @field_validator('option')
    def option_conversion(cls, option) -> list:
        _option_key: set = set(_option_map.keys())
        if not set(option).issubset(_option_key):
            raise ValueError("option字段存在未预定义元素")
        options = [_option_map[item] for item in option]
        return options

    @model_validator(mode='after')
    def check_age_range(cls, model):
        min_age = model.minAge
        max_age = model.maxAge
        if max_age < min_age:
            raise ValueError("maxAge字段必须大于等于minAge字段")
        return model
