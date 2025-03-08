# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : audit_view.py
@DateTime: 2025/2/22 12:31
"""
from fastapi import APIRouter, Query
from tortoise.expressions import Q

from backend.applications.base.models.audit_model import Audit
from backend.core.response.http_response import SuccessResponse

audit = APIRouter()


@audit.get("/list", summary="查看操作日志")
async def list_audit(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        username: str = Query(default="", description="用户名称"),
        request_tags: str = Query(default="", description="请求模块"),
        request_summary: str = Query(default="", description="请求接口"),
        request_method: str = Query(default="", description="请求方式"),
        response_code: int = Query(default=None, description="响应代码"),
        start_time: str = Query(default="", description="开始时间"),
        end_time: str = Query(default="", description="结束时间"),
):
    q = Q()
    if username:
        q &= Q(username__icontains=username)
    if request_tags:
        q &= Q(request_tags__icontains=request_tags)
    if request_summary:
        q &= Q(request_summary__icontains=request_summary)
    if request_method:
        q &= Q(request_method__icontains=request_method)
    if response_code:
        q &= Q(response_code__icontains=response_code)
    if start_time and end_time:
        q &= Q(created_time__range=[start_time, end_time])
    elif start_time:
        q &= Q(created_time__gte=start_time)
    elif end_time:
        q &= Q(created_time__lte=end_time)

    audit_log_objs = await Audit.filter(q).offset((page - 1) * page_size).limit(page_size).order_by("-created_time")
    total = await Audit.filter(q).count()
    data = [await audit_log.to_dict() for audit_log in audit_log_objs]
    return SuccessResponse(data=data, total=total)
