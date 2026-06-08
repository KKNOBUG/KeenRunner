# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : audit_view.py
@DateTime: 2025/2/22 12:31
"""
import traceback

from fastapi import APIRouter, Body, Query, Depends
from tortoise.expressions import Q

from backend.applications.base.dependencies import get_audit_crud
from backend.applications.base.schemas.audit_schema import AuditBatchDelete, AuditSelect
from backend.applications.base.services.audit_crud import AuditCrud
from backend.configure import LOGGER
from backend.core.exceptions import NotFoundException
from backend.core.responses import FailureResponse, SuccessResponse

audit = APIRouter()


@audit.get("/list", summary="查看操作日志", description="支持分页按条件查询审计日志列表信息（Query）")
async def list_audit(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        username: str = Query(default=None, description="用户名称"),
        request_tags: str = Query(default=None, description="请求模块"),
        request_summary: str = Query(default=None, description="请求接口"),
        request_method: str = Query(default=None, description="请求方式"),
        request_router: str = Query(default=None, description="请求路由"),
        response_code: str = Query(default=None, description="响应代码"),
        start_time: str = Query(default=None, description="开始时间"),
        end_time: str = Query(default=None, description="结束时间"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
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
    if request_router:
        q &= Q(request_router__icontains=request_router)
    if response_code:
        q &= Q(response_code__icontains=response_code)
    if start_time and end_time:
        q &= Q(created_time__range=[start_time, end_time])
    elif start_time:
        q &= Q(created_time__gte=start_time)
    elif end_time:
        q &= Q(created_time__lte=end_time)

    total, audit_log_objs = await audit_crud.list_audit(page=page, page_size=page_size, search=q)
    data = [await audit_log.to_dict() for audit_log in audit_log_objs]
    return SuccessResponse(data=data, total=total)


@audit.post("/search", summary="查询操作日志", description="支持分页按条件查询审计日志列表信息（Body）")
async def search_audit(
        user_in: AuditSelect = Body(),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    q = Q()
    if user_in.username:
        q &= Q(username__icontains=user_in.username)
    if user_in.request_tags:
        q &= Q(request_tags__icontains=user_in.request_tags)
    if user_in.request_summary:
        q &= Q(request_summary__icontains=user_in.request_summary)
    if user_in.request_method:
        q &= Q(request_method__icontains=user_in.request_method)
    if user_in.request_router:
        q &= Q(request_router__icontains=user_in.request_router)
    if user_in.response_code:
        q &= Q(response_code__icontains=user_in.response_code)
    if user_in.start_time and user_in.end_time:
        q &= Q(created_time__range=[user_in.start_time, user_in.end_time])
    elif user_in.start_time:
        q &= Q(created_time__gte=user_in.start_time)
    elif user_in.end_time:
        q &= Q(created_time__lte=user_in.end_time)

    total, audit_log_objs = await audit_crud.list_audit(
        page=user_in.page, page_size=user_in.page_size, search=q, order=user_in.order
    )
    data = [await audit_log.to_dict() for audit_log in audit_log_objs]
    return SuccessResponse(data=data, total=total)


@audit.get("/get", summary="查询单条审计日志", description="根据id查询审计日志信息")
async def get_audit(
        audit_id: int = Query(..., description="审计日志ID"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    try:
        instance = await audit_crud.get_by_id(audit_id=audit_id)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except NotFoundException as e:
        return FailureResponse(message=str(e))
    except Exception as e:
        LOGGER.error(f"查询审计日志失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@audit.get("/byUser", summary="查询用户审计日志", description="根据用户ID查询该用户的所有审计日志")
async def get_audit_by_user(
        user_id: int = Query(..., description="用户ID"),
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    try:
        q = Q(user_id=user_id)
        total, audit_log_objs = await audit_crud.list_audit(page=page, page_size=page_size, search=q)
        data = [await audit_log.to_dict() for audit_log in audit_log_objs]
        return SuccessResponse(data=data, total=total)
    except Exception as e:
        LOGGER.error(f"查询用户审计日志失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@audit.get("/recent", summary="查询最近审计日志", description="获取最近的审计日志记录")
async def get_recent_audits(
        limit: int = Query(default=10, ge=1, le=100, description="返回数量"),
        user_id: int = Query(default=None, description="用户ID"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    try:
        audit_logs = await audit_crud.get_recent_audits(limit=limit, user_id=user_id)
        data = [await audit_log.to_dict() for audit_log in audit_logs]
        return SuccessResponse(data=data, total=len(data))
    except Exception as e:
        LOGGER.error(f"查询最近审计日志失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@audit.get("/statistics", summary="审计日志统计", description="获取指定用户的审计日志统计信息")
async def get_audit_statistics(
        user_id: int = Query(..., description="用户ID"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    try:
        data = await audit_crud.get_statistics_by_user(user_id=user_id)
        return SuccessResponse(data=data)
    except Exception as e:
        LOGGER.error(f"统计审计日志失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"统计失败，异常描述: {e}")


@audit.delete("/delete", summary="删除审计日志", description="根据id删除单条审计日志")
async def delete_audit(
        audit_id: int = Query(..., description="审计日志ID"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    try:
        instance = await audit_crud.delete_by_id(audit_id=audit_id)
        data = await instance.to_dict()
        LOGGER.info(f"删除审计日志成功, id: {audit_id}")
        return SuccessResponse(message="删除成功", data=data)
    except NotFoundException as e:
        return FailureResponse(message=str(e))
    except Exception as e:
        LOGGER.error(f"删除审计日志失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@audit.post("/delete", summary="批量删除审计日志")
async def delete_audits_batch(
        body_in: AuditBatchDelete = Body(..., description="批量删除参数"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    try:
        count = await audit_crud.delete_by_ids(body_in.audit_ids)
        LOGGER.info(f"批量删除审计日志成功, 数量: {count}")
        return SuccessResponse(message="删除成功", data={"affected": count}, total=count)
    except Exception as e:
        LOGGER.error(f"批量删除审计日志失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@audit.delete("/deleteByUser", summary="按用户删除", description="删除指定用户的所有审计日志")
async def delete_audits_by_user(
        user_id: int = Query(..., description="用户ID"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    try:
        count = await audit_crud.delete_by_user_id(user_id=user_id)
        LOGGER.info(f"按用户删除审计日志成功, user_id: {user_id}, 数量: {count}")
        return SuccessResponse(message="删除成功", data={"affected": count})
    except Exception as e:
        LOGGER.error(f"按用户删除审计日志失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@audit.delete("/deleteByTime", summary="按时间删除", description="删除指定时间范围内的审计日志")
async def delete_audits_by_time(
        start_time: str = Query(..., description="开始时间"),
        end_time: str = Query(..., description="结束时间"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    try:
        count = await audit_crud.delete_by_time_range(start_time=start_time, end_time=end_time)
        LOGGER.info(f"按时间删除审计日志成功, 范围: {start_time} ~ {end_time}, 数量: {count}")
        return SuccessResponse(message="删除成功", data={"affected": count})
    except Exception as e:
        LOGGER.error(f"按时间删除审计日志失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@audit.delete("/clearAll", summary="清空所有审计日志", description="清空所有审计日志（危险操作）")
async def clear_all_audits(
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    try:
        count = await audit_crud.clear_all()
        LOGGER.warning(f"清空所有审计日志, 数量: {count}")
        return SuccessResponse(message="清空成功", data={"affected": count})
    except Exception as e:
        LOGGER.error(f"清空审计日志失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"清空失败，异常描述: {e}")
