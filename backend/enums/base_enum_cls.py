# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : base_enum_cls.py
@DateTime: 2025/1/12 22:58
"""
from enum import Enum
from typing import cast


class BaseEnumCls(Enum):
    """
    基础枚举类，为自定义枚举提供通用的功能。

    该类继承自Python内置的Enum类，通过重写__new__方法，为枚举成员添加描述信息，并提供类一系列类方法。
    用于获取枚举成员的各种信息。
    """

    def __new__(cls, value, desc=None, *args, **kwargs):
        """
        创建并返回一个新的枚举成员实例。
        此方法重写类Enum类的__new__方法，用于为枚举成员添加自定义的描述信息。

        :param value: 枚举成员的值，可以是任意类型，具体取决于枚举类的类型（如str或int）。
        :param desc: 枚举成员的描述信息，默认为None。
        :param args: 位置参数。
        :param kwargs: 关键字参数。
        :return: 新创建的枚举成员实例。
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
        获取枚举的所有成员，可以根据条件进行筛选和转换。

        :param exclude_enums: 要排除的枚举成员列表，默认为None。
        :param only_value: 是否只返回枚举成员的值，默认为False。
        :param only_desc: 是否只返回枚举成员的描述信息，默认为False。
        :return: 符合条件的枚举成员列表。
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
    def get_names(cls) -> list:
        """
        获取枚举的所有成员名称。
        :return: 包含所有枚举成员名称的列表
        """
        return list(cls._member_names_)

    @classmethod
    def get_values(cls, exclude_enums: list = None):
        """
        获取枚举的所有成员值，可以排除指定的枚举成员

        :param exclude_enums: 要排除的枚举成员列表，默认为None。
        :return: 包含所有枚举成员值的列表。
        """
        return cls.get_members(exclude_enums=exclude_enums, only_value=True)

    @classmethod
    def get_desc(cls, exclude_enums: list = None):
        """
        获取枚举的所有成员描述信息，可以排除指定的枚举成员

        :param exclude_enums: 要排除的枚举成员列表，默认为None。
        :return: 包含所有枚举成员值的列表。
        """
        return cls.get_members(exclude_enums=exclude_enums, only_desc=True)

    @classmethod
    def get_member_by_desc(cls, enum_desc, only_value: bool = False):
        """
        根据描述信息获取对应的枚举成员

        :param enum_desc: 要查找的枚举成员的描述信息
        :param only_value:  是否只返回枚举成员的值，默认为False。
        :return: 对应的枚举成员或其值（根据only_value参数觉得）。
        """
        members = cls.get_members()
        members_dict = {m.desc: m for m in members}
        member = members_dict.get(enum_desc)
        return member.value if only_value else member


class StringEnum(str, BaseEnumCls):
    """
    字符串类型的枚举类，继承自BaseEnumCls，用于创建字符串类型的枚举
    """
    pass


class IntegerEnum(int, BaseEnumCls):
    """
    整数类型的枚举类，继承自BaseEnumCls，用于创建整数类型的枚举
    """
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
