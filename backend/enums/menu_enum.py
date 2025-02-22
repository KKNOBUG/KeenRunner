# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : menu_enum.py
@DateTime: 2025/2/18 19:43
"""
from backend.enums.base_enum_cls import StringEnum


class MenuType(StringEnum):
    CATALOG = "catalog"     # 目录
    MENU = "menu"           # 菜单
