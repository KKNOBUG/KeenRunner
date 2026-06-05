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

from backend.enums import HTTPMethod


class AuditBase(BaseModel):
    user_id: Optional[int] = Field(default=None, description="用户ID")
    username: Optional[str] = Field(default=None, max_length=32, description="用户名称")
    request_time: Optional[datetime] = Field(default=None, description="请求时间")
    request_tags: Optional[str] = Field(default=None, max_length=255, description="请求模块")
    request_summary: Optional[str] = Field(default=None, max_length=255, description="请求接口")
    request_method: Optional[HTTPMethod] = Field(default=None, description="请求方式")
    request_router: Optional[str] = Field(default=None, max_length=255, description="请求路由")
    request_client: Optional[str] = Field(default=None, max_length=16, description="请求来源")
    request_header: Optional[dict] = Field(default=None, description="请求头部")
    request_params: Optional[str] = Field(default=None, description="请求参数")
    response_time: Optional[datetime] = Field(default=None, description="响应时间")
    response_header: Optional[dict] = Field(default=None, description="响应头部")
    response_code: Optional[str] = Field(default=None, max_length=16, description="响应代码")
    response_message: Optional[str] = Field(default=None, max_length=512, description="响应消息")
    response_params: Optional[str] = Field(default=None, description="响应参数")
    response_elapsed: Optional[str] = Field(default=None, max_length=16, description="响应耗时")


class AuditCreate(AuditBase):
    user_id: int = Field(..., description="用户ID")
    username: str = Field(..., max_length=32, description="用户名称")
    request_time: datetime = Field(..., description="请求时间")
    request_method: HTTPMethod = Field(..., description="请求方式")
    request_router: str = Field(..., max_length=255, description="请求路由")
    response_time: datetime = Field(..., description="响应时间")
    response_elapsed: str = Field(..., max_length=16, description="响应耗时")

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class AuditSelect(AuditBase):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: Optional[list] = Field(default=[], examples=["-created_time"], description="排序字段")
    start_time: Optional[str] = Field(default=None, description="开始时间")
    end_time: Optional[str] = Field(default=None, description="结束时间")


class AuditBatchDelete(BaseModel):
    audit_ids: Optional[List[int]] = Field(default=None, description="审计日志ID列表")
