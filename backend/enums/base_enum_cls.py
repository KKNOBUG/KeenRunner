# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : base_enum_cls.py
@DateTime: 2025/1/12 22:58
"""
from enum import Enum


class BaseEnumCls(Enum):

    def __new__(cls, value, desc=None, *args, **kwargs):
        """

        :param value:
        :param desc:
        :param args:
        :param kwargs:
        """

        if issubclass(cls, int):
            obj = int.__new__(cls, value)
        elif issubclass(cls, str):
            obj = str.__new__(cls, value)
        else:
            obj = object.__new__(cls)

        obj._value_ = value
        obj.desc = desc
        return obj

    @classmethod
    def get_members(cls, exclude_enums: list = None,
                    only_value: bool = False, only_desc: bool = False) -> list:
        """
        获取枚举的所有成员
        :param exclude_enums:
        :param only_value:
        :param only_desc:
        :return:
        """

        members = list(cls)
        if exclude_enums:
            members = [m for m in members if m not in exclude_enums]
            return members

        if only_value:
            members = [m.value for m in members]
            return members

        if only_desc:
            members = [m.desc for m in members]
            return members

        return members

    @classmethod
    def get_names(cls):
        return list(cls._member_names_)

    @classmethod
    def get_values(cls, exclude_enums: list = None):
        return cls.get_members(exclude_enums=exclude_enums, only_value=True)

    @classmethod
    def get_desc(cls, exclude_enums: list = None):
        return cls.get_members(exclude_enums=exclude_enums, only_desc=True)

    @classmethod
    def get_member_by_desc(cls, enum_desc, only_value: bool = False):
        members = cls.get_members()
        members_dict = {m.desc: m for m in members}
        member = members_dict.get(enum_desc)
        return member.value if only_value else member


class StringEnum(str, BaseEnumCls):
    pass


class IntegerEnum(int, BaseEnumCls):
    pass


if __name__ == '__main__':
    class Color(BaseEnumCls):
        RED = 1, "红色"
        GREEN = 2, "绿色"
        BLUE = 3, "蓝色"


    print("获取所有名称：", Color.get_names())
    print("获取所有数据：", Color.get_values())
    print("获取所有描述：", Color.get_desc())
    print("获取所有对象：", Color.get_members())
    print("获取所有对象：", Color.get_members(only_desc=True, exclude_enums=[Color.RED]))
    print("通过条件获取：", Color.get_member_by_desc("蓝色"))
    print("通过条件获取：", Color.get_member_by_desc("蓝色", only_value=True))
