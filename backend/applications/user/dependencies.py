# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : dependencies.py
@DateTime: 2026/6/8 09:47
"""
from backend.applications.user.services.user_crud import UserCrud


async def get_user_crud() -> UserCrud:
    """获取用户 CRUD 服务实例"""
    return UserCrud()
