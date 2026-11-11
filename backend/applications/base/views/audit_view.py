# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
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
from backend.enums import ResourceTag

audit = APIRouter()


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
    组装审计列表查询条件。

    各筛选项按索引友好方式匹配：账号/路由前缀匹配，方法/响应码等值匹配；标签同时兼容
    资源族 code 与历史中文标签；未显式传时间范围时默认只查最近 7 天。

    :param username: 用户账号，前缀匹配
    :param request_tags: 请求模块，资源族 code 或中文标签的包含匹配
    :param request_summary: 请求接口，包含匹配
    :param request_method: 请求方式，等值匹配（大小写不敏感）
    :param request_router: 请求路由，前缀匹配
    :param response_code: 响应代码，等值匹配
    :param start_time: 起始时间，格式与 GLOBAL_CONFIG.DATETIME_FORMAT2 一致
    :param end_time: 结束时间，格式同上
    :param apply_default_time_window: 未传时间范围时是否默认只查最近 7 天
    :return: Tortoise Q 查询条件
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
        # 账号使用前缀匹配以命中 username 索引，不做全模糊查询
        q &= Q(username__startswith=username)
    if request_tags:
        # 新数据存资源族 code，历史数据存中文标签；两种口径同时匹配
        matched_tags = {request_tags, ResourceTag.label_of(request_tags)}
        tag_q = Q()
        for value in matched_tags:
            if value:
                tag_q |= Q(request_tags__contains=value)
        q &= tag_q
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
        # 未传时间范围时默认只查最近N天，缩小扫描范围以命中created_time相关索引；需要全量历史时显式传入足够大的start_time/end_time。
        default_start = (datetime.now() - timedelta(days=7)).strftime(GLOBAL_CONFIG.DATETIME_FORMAT2)
        q &= Q(created_time__gte=default_start)

    return q


async def _serialize_audit_list(audit_log_objs) -> list:
    """
    将审计日志模型批量序列化为列表字典。

    显式排除请求/响应头与参数等大字段，避免列表响应体膨胀；同时把资源族 code
    映射为展示用 label。

    :param audit_log_objs: 审计日志模型列表
    :return: 字典列表，主键字段为 audit_id，并补充 request_tags_label
    """
    result = []
    for audit_log in audit_log_objs:
        data = await audit_log.to_dict(
            exclude_fields={
                "request_header",
                "request_params",
                "response_header",
                "response_params",
            },
            replace_fields={"id": "audit_id"}
        )
        data["request_tags_label"] = ResourceTag.label_of(data.get("request_tags"))
        result.append(data)
    return result


@audit.get("/list", summary="查询日志列表(Query)", description="根据条件分页查询日志信息(Query)")
async def list_audit(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, le=99999, description="每页数量"),
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
    按条件分页查询审计日志（Query 入参）。

    未传时间范围时默认只查最近 7 天；结果不包含请求/响应头等大字段。

    :param page: 页码
    :param page_size: 每页条数
    :param order: 排序字段，默认按创建时间倒序
    :param username: 用户账号，前缀匹配
    :param request_tags: 请求模块，支持资源族 code 或中文标签
    :param request_summary: 请求接口，包含匹配
    :param request_method: 请求方式，等值匹配
    :param request_router: 请求路由，前缀匹配
    :param response_code: 响应代码，等值匹配
    :param start_time: 开始时间
    :param end_time: 结束时间
    :param audit_crud: 审计日志 CRUD 服务
    :return: 统一响应，成功时 data 为日志列表，total 为总条数
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
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception:
        error_message: str = "查询审计日志失败，暂时无法获取日志数据，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [page={page}, page_size={page_size}, username={username}, request_router={request_router}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@audit.post("/search", summary="查询日志列表(Body)", description="根据条件分页查询日志信息(Body)")
async def search_audit(
        audit_in: AuditSelect = Body(..., description="查询条件"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    按条件分页查询审计日志（Body 入参）。

    与 Query 版本共用筛选规则；request_method 同时接受枚举与字符串。

    :param audit_in: 审计日志查询入参
    :param audit_crud: 审计日志 CRUD 服务
    :return: 统一响应，成功时 data 为日志列表，total 为总条数
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
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception:
        error_message: str = "查询审计日志失败，暂时无法获取日志数据，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [page={audit_in.page}, page_size={audit_in.page_size}, "
            f"username={audit_in.username}, request_router={audit_in.request_router}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@audit.get("/get", summary="查询日志", description="根据id查询日志信息")
async def get_audit(
        audit_id: int = Query(..., description="日志ID"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    根据 ID 查询单条审计日志详情。

    详情包含请求/响应头等完整字段，并补充 request_tags_label；记录不存在时返回 404。

    :param audit_id: 审计日志 ID
    :param audit_crud: 审计日志 CRUD 服务
    :return: 统一响应，成功时 data 为日志详情，主键字段为 audit_id
    """
    try:
        instance = await audit_crud.get_by_id(audit_id=audit_id)
        data = await instance.to_dict(replace_fields={"id": "audit_id"})
        data["request_tags_label"] = ResourceTag.label_of(data.get("request_tags"))
        return SuccessResponse(message="查询成功", data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "查询审计日志详情失败，暂时无法获取该条日志，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [audit_id={audit_id}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@audit.get("/by_user", summary="查询用户日志", description="根据用户id分页查询日志信息")
async def get_audit_by_user(
        user_id: int = Query(..., description="用户ID"),
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, le=99999, description="每页数量"),
        order: list = Query(default_factory=lambda: ["-created_time"], description="排序字段"),
        start_time: str = Query(default=None, description="开始时间"),
        end_time: str = Query(default=None, description="结束时间"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    分页查询指定用户的审计日志。

    未传时间范围时默认只查最近 7 天，需要更早数据时显式传 start_time 与 end_time。

    :param user_id: 用户 ID
    :param page: 页码
    :param page_size: 每页条数
    :param order: 排序字段，默认按创建时间倒序
    :param start_time: 开始时间
    :param end_time: 结束时间
    :param audit_crud: 审计日志 CRUD 服务
    :return: 统一响应，成功时 data 为日志列表，total 为总条数
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
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception:
        error_message: str = "查询用户审计日志失败，暂时无法获取日志数据，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [user_id={user_id}, page={page}, page_size={page_size}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@audit.get("/recent", summary="查询最近日志", description="根据条件获取最近日志信息")
async def get_recent_audits(
        limit: int = Query(default=10, ge=1, le=100, description="返回数量"),
        user_id: int = Query(default=None, description="用户ID"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    获取最近若干条审计日志（按创建时间倒序）。

    :param limit: 返回条数上限，范围 1～100
    :param user_id: 用户 ID，不传则查询全部用户
    :param audit_crud: 审计日志 CRUD 服务
    :return: 统一响应，成功时 data 为日志列表，total 为实际返回条数
    """
    try:
        audit_logs = await audit_crud.get_recent_audits(limit=limit, user_id=user_id)
        data = await _serialize_audit_list(audit_logs)
        return SuccessResponse(message="查询成功", data=data, total=len(data))
    except Exception:
        error_message: str = "查询最近审计日志失败，暂时无法获取日志数据，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [limit={limit}, user_id={user_id}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@audit.get("/statistics", summary="查询日志统计", description="根据用户id查询日志统计信息")
async def get_audit_statistics(
        user_id: int = Query(..., description="用户ID"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    统计指定用户的审计日志分布。

    :param user_id: 用户 ID
    :param audit_crud: 审计日志 CRUD 服务
    :return: 统一响应，data 含 total_count、method_statistics 与 code_statistics
    """
    try:
        data = await audit_crud.get_statistics_by_user(user_id=user_id)
        return SuccessResponse(message="统计成功", data=data)
    except Exception:
        error_message: str = "统计审计日志失败，暂时无法生成统计数据，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [user_id={user_id}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@audit.delete("/delete", summary="删除日志", description="根据id删除日志信息")
async def delete_audit(
        audit_id: int = Query(..., description="审计日志ID"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    根据 ID 删除单条审计日志（物理删除）。

    :param audit_id: 审计日志 ID
    :param audit_crud: 审计日志 CRUD 服务
    :return: 统一响应，成功时 data 为被删除的日志，主键字段为 audit_id
    """
    try:
        instance = await audit_crud.delete_by_id(audit_id=audit_id)
        data = await instance.to_dict(replace_fields={"id": "audit_id"})
        return SuccessResponse(message="删除成功", data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "删除审计日志失败，暂时无法完成删除，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [audit_id={audit_id}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@audit.post("/deletes", summary="批量删除日志", description="根据id列表批量删除日志信息")
async def batch_delete_audits(
        body_in: AuditBatchDelete = Body(..., description="审计日志ID列表"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    根据 ID 列表批量删除审计日志（物理删除）。

    :param body_in: 批量删除入参，audit_ids 为空时不执行删除
    :param audit_crud: 审计日志 CRUD 服务
    :return: 统一响应，data 中 affected 为实际删除条数，total 同值
    """
    try:
        count = await audit_crud.delete_by_ids(body_in.audit_ids)
        return SuccessResponse(message="删除成功", data={"affected": count}, total=count)
    except Exception:
        error_message: str = "批量删除审计日志失败，暂时无法完成删除，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [audit_count={len(body_in.audit_ids or [])}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@audit.delete("/delete_by_user", summary="删除用户日志", description="根据用户id删除全部日志信息")
async def delete_audits_by_user(
        user_id: int = Query(..., description="用户ID"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    删除指定用户的全部审计日志（物理删除）。

    :param user_id: 用户 ID
    :param audit_crud: 审计日志 CRUD 服务
    :return: 统一响应，data 中 affected 为实际删除条数
    """
    try:
        count = await audit_crud.delete_by_user_id(user_id=user_id)
        return SuccessResponse(message="删除成功", data={"affected": count})
    except Exception:
        error_message: str = "删除用户审计日志失败，暂时无法完成删除，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [user_id={user_id}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@audit.delete("/delete_by_time", summary="删除时间范围日志", description="根据时间范围删除日志信息")
async def delete_audits_by_time(
        start_time: str = Query(..., description="开始时间"),
        end_time: str = Query(..., description="结束时间"),
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    删除指定时间范围内的审计日志（物理删除）。

    :param start_time: 开始时间
    :param end_time: 结束时间
    :param audit_crud: 审计日志 CRUD 服务
    :return: 统一响应，data 中 deleted 为实际删除条数
    """
    try:
        count = await audit_crud.delete_by_time_range(start_time=start_time, end_time=end_time)
        return SuccessResponse(message="删除成功", data={"deleted": count})
    except Exception:
        error_message: str = "删除时间范围审计日志失败，暂时无法完成删除，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [start_time={start_time}, end_time={end_time}]\n"
            f"{traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@audit.delete("/clear_all", summary="删除全部审计日志", description="删除所有审计日志(危险操作)")
async def clear_all_audits(
        audit_crud: AuditCrud = Depends(get_audit_crud),
):
    """
    清空全部审计日志（危险操作，物理删除）。

    :param audit_crud: 审计日志 CRUD 服务
    :return: 统一响应，data 中 affected 为删除前的记录总数
    """
    try:
        count = await audit_crud.clear_all()
        return SuccessResponse(message="清空成功", data={"affected": count})
    except Exception:
        error_message: str = "清空审计日志失败，暂时无法完成清空，请稍后重试"
        LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
        return FailureResponse(message=error_message)
