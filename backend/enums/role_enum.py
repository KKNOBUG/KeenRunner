# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : role_enum.py
@DateTime: 2026/10/28
"""
from typing import Iterable, Optional

from backend.enums.base_enum_cls import StringEnum


class BuiltinRoleCode(StringEnum):
    """
    内置角色编码。

    管理员角色在运行期直接拥有全量菜单、接口与数据权限，不依赖菜单/路由绑定记录；
    其余角色一律只按角色上显式配置的菜单、接口与标签范围生效。
    """

    ADMIN = ("Administrators", "管理员")
    USER = ("Users", "标准用户")
    GUEST = ("Guests", "访客用户")

    @classmethod
    def includes_admin(cls, role_codes: Iterable[Optional[str]]) -> bool:
        """
        判断角色编码集合中是否包含管理员角色。

        :param role_codes: 角色编码集合，允许含空值
        :return: 包含管理员角色返回True
        """
        admin_code: str = cls.ADMIN.value
        return admin_code in {str(code or "").strip() for code in role_codes}