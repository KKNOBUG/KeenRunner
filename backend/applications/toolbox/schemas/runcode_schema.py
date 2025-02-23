# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : runcode_schema.py
@DateTime: 2025/2/23 12:03
"""
from pydantic import BaseModel


class CodeRequest(BaseModel):
    code: str
