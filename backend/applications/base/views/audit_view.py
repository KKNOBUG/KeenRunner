# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : audit_view.py
@DateTime: 2025/2/22 12:31
"""
import traceback
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Body, Query, Depends
from tortoise.expressions import Q

from backend.applications.base.dependencies import get_audit_crud
from backend.applications.base.schemas.audit_schema import AuditBatchDelete, AuditSelect
from backend.applications.base.services.audit_crud import AuditCrud
from backend.configure import GLOBAL_CONFIG, LOGGER
from backend.core.exceptions import NotFoundException
from backend.core.responses import FailureResponse, NotFoundResponse, SuccessResponse

audit = APIRouter()

# 未传时间范围时默认只查最近 N 天，缩小扫描范围以命中 created_time 相关索引；
# 需要全量历史时显式传入足够大的 start_time/end_time。
AUDIT_DEFAULT_LOOKBACK_DAYS = 7


def _build_audit_search_q(
        *,
        username: Optional[str] = None,
        request_tags: Optional[str] = None,
        request_summary: Optional[str] = None,
        request_method: Optional[str] = None,
        request_router: Optional[str] = None,
        response_code: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        apply_default_time_window: bool = True,
) -> Q:
    """
    组装审计列表查询条件（偏向索引友好）：
    - method / response_code：等值匹配（可用单列或组合索引）
    - username / router：前缀匹配（可用 BTREE 最左前缀）
    - tags / summary：仍为包含匹配（无法很好走索引，建议配合时间范围）
    - 时间：优先使用区间；都未传时默认最近 AUDIT_DEFAULT_LOOKBACK_DAYS 天
    """
    q = Q()

    username = (username or "").strip()
    request_tags = (request_tags or "").strip()
    request_summary = (request_summary or "").strip()
    request_method = (request_method or "").strip().upper()
    request_router = (request_router or "").strip()
    response_code = (response_code or "").strip()
    start_time = (start_time or "").strip() or None
    end_time = (end_time or "").strip() or None

    if username:
        # 前缀匹配可利用 username 索引；全模糊改为 startswith
        q &= Q(username__startswith=username)
    if request_tags:
        q &= Q(request_tags__contains=request_tags)
    if request_summary:
        q &= Q(request_summary__contains=request_summary)
    if request_method:
        q &= Q(request_method=request_method)
    if request_router:
        q &= Q(request_router__startswith=request_router)
    if response_code:
        q &= Q(response_code=response_code)

    if start_time and end_time:
        q &= Q(created_time__range=[start_time, end_time])
    elif start_time:
        q &= Q(created_time__gte=start_time)
    elif end_time:
        q &= Q(created_time__lte=end_time)
    elif apply_default_time_window:
        default_start = (datetime.now() - timedelta(days=AUDIT_DEFAULT_LOOKBACK_DAYS)).strftime(
            GLOBAL_CONFIG.DATETIME_FORMAT2
        )
        q &= Q(created_time__gte=default_start)

    return q


async def _serialize_audit_list(audit_log_objs) -> list:
    """列表序列化：显式排除大字段，避免 only() 后触发惰性补查。"""
    return [
        await audit_log.to_dict(
            exclude_fields={
                "request_header",
                "request_params",
                "response_header",
                "response_params",
            }
        )
        for audit_log in audit_log_objs
    ]


@audit.get("/list", summary="查询日志列表", description="根据条件分页查询日志信息(Query)")
async def list_audit(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        order: list = Query(default_factory=lambda: ["-created_time"], description="排序字段"),
        username: str = Query(default=None, description="用户名称(前缀匹配)"),
        request_tags: str = Query(default=None, description="请求模块"),
        request_summary: str = Query(default=None, description="请求接口"),
        request_method: str = Query(default=None, description="请求方式(精确匹配，如 GET)"),
        request_router: str = Query(default=None, description="请求路由(前缀匹配)"),
        response_code: str = Query(default=None, description="响应代码(精确匹配)"),
        start_time: str = Query(default=None, description="开始时间"),
        end_time: str = Query(default=None, description="结束时间"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    根据条件分页查询审计日志（Query 方式）。

    :param page: 页码
    :param page_size: 每页条数
    :param order: 排序字段
    :param username: 用户名称
    :param request_tags: 请求模块
    :param request_summary: 请求接口
    :param request_method: 请求方式
    :param request_router: 请求路由
    :param response_code: 响应代码
    :param start_time: 开始时间
    :param end_time: 结束时间
    :param audit_crud: 审计日志CRUD服务
    :return: 统一HTTP响应
    """
    q = _build_audit_search_q(
        username=username,
        request_tags=request_tags,
        request_summary=request_summary,
        request_method=request_method,
        request_router=request_router,
        response_code=response_code,
        start_time=start_time,
        end_time=end_time,
    )

    try:
        total, audit_log_objs = await audit_crud.list_audit(page=page, page_size=page_size, order=order, search=q)
        data = await _serialize_audit_list(audit_log_objs)
        LOGGER.info(f"查询审计日志列表成功, 数量: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception as e:
        LOGGER.error(f"查询审计日志列表失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@audit.post("/search", summary="查询日志列表", description="根据条件分页查询日志信息(Body)")
async def search_audit(
        audit_in: AuditSelect = Body(..., description="查询条件"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    根据条件分页查询审计日志（Body 方式）。

    :param audit_in: 审计日志查询入参
    :param audit_crud: 审计日志CRUD服务
    :return: 统一HTTP响应
    """
    method_value = audit_in.request_method.value if hasattr(audit_in.request_method, "value") else audit_in.request_method
    q = _build_audit_search_q(
        username=audit_in.username,
        request_tags=audit_in.request_tags,
        request_summary=audit_in.request_summary,
        request_method=method_value,
        request_router=audit_in.request_router,
        response_code=audit_in.response_code,
        start_time=audit_in.start_time,
        end_time=audit_in.end_time,
    )

    try:
        total, audit_log_objs = await audit_crud.list_audit(
            page=audit_in.page, page_size=audit_in.page_size, search=q, order=audit_in.order
        )
        data = await _serialize_audit_list(audit_log_objs)
        LOGGER.info(f"查询审计日志列表成功, 数量: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception as e:
        LOGGER.error(f"查询审计日志列表失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@audit.get("/get", summary="查询日志", description="根据id查询日志信息")
async def get_audit(
        audit_id: int = Query(..., description="日志ID"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    根据 id 查询审计日志。

    :param audit_id: 审计日志ID
    :param audit_crud: 审计日志CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await audit_crud.get_by_id(audit_id=audit_id)
        data = await instance.to_dict()
        LOGGER.info(f"查询审计日志成功, audit_id: {audit_id}")
        return SuccessResponse(message="查询成功", data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询审计日志失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@audit.get("/byUser", summary="查询用户日志", description="根据用户id分页查询日志信息")
async def get_audit_by_user(
        user_id: int = Query(..., description="用户ID"),
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        order: list = Query(default_factory=lambda: ["-created_time"], description="排序字段"),
        start_time: str = Query(default=None, description="开始时间"),
        end_time: str = Query(default=None, description="结束时间"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    获取指定用户的审计日志（默认最近若干天，可按时间范围扩大）。

    :param user_id: 用户ID
    :param page: 页码
    :param page_size: 每页条数
    :param order: 排序字段
    :param start_time: 开始时间
    :param end_time: 结束时间
    :param audit_crud: 审计日志CRUD服务
    :return: 统一HTTP响应
    """
    try:
        q = Q(user_id=user_id) & _build_audit_search_q(
            start_time=start_time,
            end_time=end_time,
            apply_default_time_window=True,
        )
        total, audit_log_objs = await audit_crud.list_audit(
            page=page, page_size=page_size, search=q, order=order
        )
        data = await _serialize_audit_list(audit_log_objs)
        LOGGER.info(f"查询用户审计日志成功, user_id: {user_id}, 数量: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception as e:
        LOGGER.error(f"查询用户审计日志失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@audit.get("/recent", summary="查询最近日志", description="根据条件获取最近日志信息")
async def get_recent_audits(
        limit: int = Query(default=10, ge=1, le=100, description="返回数量"),
        user_id: int = Query(default=None, description="用户ID"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    根据条件获取最近审计日志。

    :param limit: 返回数量
    :param user_id: 用户ID
    :param audit_crud: 审计日志CRUD服务
    :return: 统一HTTP响应
    """
    try:
        audit_logs = await audit_crud.get_recent_audits(limit=limit, user_id=user_id)
        data = await _serialize_audit_list(audit_logs)
        LOGGER.info(f"查询最近审计日志成功, 数量: {len(data)}")
        return SuccessResponse(message="查询成功", data=data, total=len(data))
    except Exception as e:
        LOGGER.error(f"查询最近审计日志失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@audit.get("/statistics", summary="查询日志统计", description="根据用户id查询日志统计信息")
async def get_audit_statistics(
        user_id: int = Query(..., description="用户ID"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    获取指定用户的审计日志统计信息。

    :param user_id: 用户ID
    :param audit_crud: 审计日志CRUD服务
    :return: 统一HTTP响应
    """
    try:
        data = await audit_crud.get_statistics_by_user(user_id=user_id)
        LOGGER.info(f"统计审计日志成功, user_id: {user_id}")
        return SuccessResponse(message="统计成功", data=data)
    except Exception as e:
        LOGGER.error(f"统计审计日志失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"统计失败，异常描述: {e}")


@audit.delete("/delete", summary="删除日志", description="根据id删除日志信息")
async def delete_audit(
        audit_id: int = Query(..., description="审计日志ID"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    根据 id 删除审计日志。

    :param audit_id: 审计日志ID
    :param audit_crud: 审计日志CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await audit_crud.delete_by_id(audit_id=audit_id)
        data = await instance.to_dict()
        LOGGER.info(f"删除审计日志成功, id: {audit_id}")
        return SuccessResponse(message="删除成功", data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"删除审计日志失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@audit.post("/delete", summary="批量删除日志", description="根据id列表批量删除日志信息")
async def batch_delete_audits(
        body_in: AuditBatchDelete = Body(..., description="审计日志ID列表"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    根据 id 列表删除审计日志。

    :param body_in: 审计日志批量删除入参
    :param audit_crud: 审计日志CRUD服务
    :return: 统一HTTP响应
    """
    try:
        count = await audit_crud.delete_by_ids(body_in.audit_ids)
        LOGGER.info(f"批量删除审计日志成功, 数量: {count}")
        return SuccessResponse(message="删除成功", data={"affected": count}, total=count)
    except Exception as e:
        LOGGER.error(f"批量删除审计日志失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@audit.delete("/delete_by_user", summary="删除用户日志", description="根据用户id删除全部日志信息")
async def delete_audits_by_user(
        user_id: int = Query(..., description="用户ID"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    删除指定用户的所有审计日志。

    :param user_id: 用户ID
    :param audit_crud: 审计日志CRUD服务
    :return: 统一HTTP响应
    """
    try:
        count = await audit_crud.delete_by_user_id(user_id=user_id)
        LOGGER.info(f"根据用户删除审计日志成功, user_id: {user_id}, 数量: {count}")
        return SuccessResponse(message="删除成功", data={"affected": count})
    except Exception as e:
        LOGGER.error(f"根据用户删除审计日志失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@audit.delete("/delete_by_time", summary="删除时间范围日志", description="根据时间范围删除日志信息")
async def delete_audits_by_time(
        start_time: str = Query(..., description="开始时间"),
        end_time: str = Query(..., description="结束时间"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    删除指定时间范围内的审计日志。

    :param start_time: 开始时间
    :param end_time: 结束时间
    :param audit_crud: 审计日志CRUD服务
    :return: 统一HTTP响应
    """
    try:
        count = await audit_crud.delete_by_time_range(start_time=start_time, end_time=end_time)
        LOGGER.info(f"根据时间删除审计日志成功, 范围: {start_time} ~ {end_time}, 数量: {count}")
        return SuccessResponse(message="删除成功", data={"affected": count})
    except Exception as e:
        LOGGER.error(f"根据时间删除审计日志失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@audit.delete("/clear_all", summary="清空审计日志", description="清空所有审计日志(危险操作)")
async def clear_all_audits(
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    清空所有审计日志（危险操作）。

    :param audit_crud: 审计日志CRUD服务
    :return: 统一HTTP响应
    """
    try:
        count = await audit_crud.clear_all()
        LOGGER.warning(f"清空所有审计日志, 数量: {count}")
        return SuccessResponse(message="清空成功", data={"affected": count})
    except Exception as e:
        LOGGER.error(f"清空审计日志失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"清空失败，异常描述: {e}")
