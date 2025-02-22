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
        username: str = Query(default="", description="操作人名称"),
        module: str = Query(default="", description="功能模块"),
        method: str = Query(default="", description="请求方法"),
        summary: str = Query(default="", description="接口描述"),
        status: int = Query(default=None, description="状态码"),
        start_time: str = Query(default="", description="开始时间"),
        end_time: str = Query(default="", description="结束时间"),
):
    q = Q()
    if username:
        q &= Q(username__icontains=username)
    if module:
        q &= Q(module__icontains=module)
    if method:
        q &= Q(method__icontains=method)
    if summary:
        q &= Q(summary__icontains=summary)
    if status:
        q &= Q(status__icontains=status)
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
