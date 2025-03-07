# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : audit_schema.py
@DateTime: 2025/3/7 21:48
"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field

from backend.enums.http_enum import HTTPMethod


class AuditCreate(BaseModel):
    user_id: int
    username: str
    request_time: datetime
    request_tags: Optional[str]
    request_summary: Optional[str]
    request_method: HTTPMethod
    request_router: str
    request_client: Optional[str]
    request_header: Optional[dict]
    request_params: Optional[str]
    response_time: datetime
    response_header: Optional[dict]
    response_code: Optional[str]
    response_message: Optional[str]
    response_params: Optional[str]
    response_elapsed: str
