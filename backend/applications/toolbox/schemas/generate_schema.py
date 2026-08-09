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

# 前端展示文案 → 虚拟人员字段键名
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

# 前端展示文案 → 随机时间类型键名
DATETIME_OPTION_MAP: Dict[str, str] = {
    "现在": "now",
    "历史": "history",
    "未来": "future",
}

# 前端展示文案 → 随机数/标识类型键名
RANDOM_OPTION_MAP: Dict[str, str] = {
    "UUID": "uuid",
    "时间戳": "timestamp",
    "流水号": "global",
    "随机数": "random",
}


class GenerateVirtualInfo(BaseModel):
    """工具箱：批量生成虚拟人员/时间/随机标识的请求入参。"""

    number: int = Field(ge=1, description="生成条数")
    minAge: int = Field(ge=1, description="随机年龄下限")
    maxAge: int = Field(ge=1, description="随机年龄上限")
    personOption: List[str] = Field(default_factory=lambda: list(PERSON_OPTION_MAP.keys()), description="人员字段选项（中文文案）")
    datetimeOption: List[str] = Field(default_factory=lambda: list(DATETIME_OPTION_MAP.keys()), description="时间类型选项（中文文案）")
    randomOption: List[str] = Field(default_factory=lambda: list(RANDOM_OPTION_MAP.keys()), description="随机标识选项（中文文案）")

    @field_validator('personOption')
    @classmethod
    def person_option_conversion(cls, personOption) -> list:
        """
        校验人员选项并转换为 GENERATE 使用的英文字段键。

        :param personOption: 中文选项列表
        :return: 映射后的字段键列表
        """
        _option_key: set = set(PERSON_OPTION_MAP.keys())
        if not set(personOption).issubset(_option_key):
            raise ValueError("personOption字段存在未预定义元素")
        personOption = [PERSON_OPTION_MAP[item] for item in personOption]
        return personOption

    @field_validator('datetimeOption')
    @classmethod
    def datetime_option_conversion(cls, datetimeOption) -> list:
        """
        校验时间选项并转换为 now/history/future 键名。

        :param datetimeOption: 中文选项列表
        :return: 映射后的时间类型键列表
        """
        _option_key: set = set(DATETIME_OPTION_MAP.keys())
        if not set(datetimeOption).issubset(_option_key):
            raise ValueError("datetimeOption字段存在未预定义元素")
        datetimeOption = [DATETIME_OPTION_MAP[item] for item in datetimeOption]
        return datetimeOption

    @field_validator('randomOption')
    @classmethod
    def random_option_conversion(cls, randomOption) -> list:
        """
        校验随机标识选项并转换为 uuid/timestamp 等键名。

        :param randomOption: 中文选项列表
        :return: 映射后的随机类型键列表
        """
        _option_key: set = set(RANDOM_OPTION_MAP.keys())
        if not set(randomOption).issubset(_option_key):
            raise ValueError("randomOption字段存在未预定义元素")
        randomOption = [RANDOM_OPTION_MAP[item] for item in randomOption]
        return randomOption

    @model_validator(mode='after')
    def check_age_range(self):
        """
        校验年龄区间：maxAge 不得小于 minAge。

        :return: 校验通过的模型实例
        """
        min_age = self.minAge
        max_age = self.maxAge
        if max_age < min_age:
            raise ValueError("maxAge字段必须大于等于minAge字段")
        return self
