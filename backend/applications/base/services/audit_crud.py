# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : audit_crud
@DateTime: 2026/4/20 16:53
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any, List, Optional, Tuple, Dict

from tortoise.expressions import Q
from tortoise.functions import Count

from backend.applications.base.models.audit_model import Audit
from backend.applications.base.schemas.audit_schema import AuditCreate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.configure.global_config import GlobalConfig
from backend.core.exceptions import ParameterException, NotFoundException
from backend.enums import ResourceTag

# 列表/最近日志查询不拉取大字段，完整报文仍由GET返回
AUDIT_LIST_ONLY_FIELDS: Tuple[str, ...] = (
    "id",
    "user_id",
    "username",
    "request_time",
    "request_tags",
    "request_summary",
    "request_method",
    "request_router",
    "request_client",
    "response_time",
    "response_code",
    "response_message",
    "response_elapsed",
    "created_time",
    "updated_time",
)
# 列表序列化排除请求/响应头与参数等大字段，避免列表响应体膨胀
AUDIT_LIST_EXCLUDE_FIELDS: Tuple[str, ...] = (
    "request_header",
    "request_params",
    "response_header",
    "response_params",
)


class AuditCrud(ScaffoldCrud[Audit, AuditCreate, Any]):

    def __init__(self):
        super().__init__(model=Audit)

    @staticmethod
    def build_search_q(
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

        :param username: 用户账号，前缀匹配
        :param request_tags: 请求模块，资源族 code 或中文标签的包含匹配
        :param request_summary: 请求接口，包含匹配
        :param request_method: 请求方式，等值匹配（大小写不敏感）
        :param request_router: 请求路由，前缀匹配
        :param response_code: 响应代码，等值匹配
        :param start_time: 起始时间，格式与GLOBAL_CONFIG.DATETIME_FORMAT2一致
        :param end_time: 结束时间，格式同上
        :param apply_default_time_window: 未传时间范围时是否默认只查最近7天
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
            # 未传时间范围时默认只查最近N天，缩小扫描范围以命中created_time索引；需要全量历史时显式传入时间范围
            default_start = (datetime.now() - timedelta(days=7)).strftime(GlobalConfig.DATETIME_FORMAT2)
            q &= Q(created_time__gte=default_start)

        return q

    @staticmethod
    async def serialize_audit_list(audit_log_objs) -> list:
        """
        将审计日志模型批量序列化为列表字典。

        :param audit_log_objs: 审计日志模型列表
        :return: 字典列表，主键字段为audit_id，并补充request_tags_label
        """
        result = []
        for audit_log in audit_log_objs:
            data = await audit_log.to_dict(
                exclude_fields=AUDIT_LIST_EXCLUDE_FIELDS,
                replace_fields={"id": "audit_id"}
            )
            data["request_tags_label"] = ResourceTag.label_of(data.get("request_tags"))
            result.append(data)
        return result

    async def get_by_id(self, audit_id: int, on_error: bool = True) -> Optional[Audit]:
        """
        根据主键ID查询单条审计日志。

        :param audit_id: 审计日志ID
        :param on_error: 未找到时是否抛出异常
        :return: 审计日志实例或None
        """
        if not audit_id:
            error_message: str = "查询审计日志失败, 参数[audit_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.get_or_none(id=audit_id)
        if not instance and on_error:
            error_message: str = f"查询审计日志失败, 记录[id={audit_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_user_id(self, user_id: int, on_error: bool = True) -> Optional[List[Audit]]:
        """
        根据用户ID查询该用户的全部审计日志。

        :param user_id: 用户ID
        :param on_error: 未找到时是否抛出异常
        :return: 审计日志列表；无匹配且on_error为False时为空列表
        """
        if not user_id:
            error_message: str = "查询审计日志失败, 参数[user_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instances = await self.model.filter(user_id=user_id).all()
        if not instances and on_error:
            error_message: str = f"查询审计日志失败, 记录[user_id={user_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instances

    async def list_audit(
            self,
            page: int = 1,
            page_size: int = 10,
            search: Q = Q(),
            order: Optional[list] = None
    ) -> Tuple[int, List[Audit]]:
        """
        根据条件分页查询审计日志列表。

        :param page: 页码，从1开始
        :param page_size: 每页记录数
        :param search: 搜索条件(Q对象)
        :param order: 排序字段列表；由调用方提供，空则["-created_time"]
        :return: (总记录数, 当前页审计日志列表)
        """
        order_fields: list = self.normalize_order_fields(order) or ["-created_time"]
        base_query = self.model.filter(search)
        page_query = (
            base_query
            .only(*AUDIT_LIST_ONLY_FIELDS)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(*order_fields)
        )
        total, rows = await asyncio.gather(
            base_query.count(),
            page_query,
        )
        return int(total), list(rows)

    async def delete_by_id(self, audit_id: int) -> Audit:
        """
        根据ID物理删除单条审计日志。

        :param audit_id: 审计日志ID
        :return: 被删除的审计日志实例
        """
        instance = await self.get_by_id(audit_id=audit_id, on_error=True)
        await instance.delete()
        return instance

    async def delete_by_ids(self, audit_ids: Optional[List[int]]) -> int:
        """
        根据主键列表批量物理删除审计日志。

        :param audit_ids: 审计日志ID列表；为空则不删除
        :return: 实际删除的记录数
        """
        if not audit_ids:
            return 0
        ids = [int(x) for x in audit_ids]
        return int(await self.model.filter(id__in=ids).delete())

    async def delete_by_user_id(self, user_id: int) -> int:
        """
        根据用户ID物理删除该用户的全部审计日志。

        :param user_id: 用户ID
        :return: 实际删除的记录数
        """
        if not user_id:
            error_message: str = "删除审计日志失败, 参数[user_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        return int(await self.model.filter(user_id=user_id).delete())

    async def delete_by_time_range(self, start_time: str, end_time: str) -> int:
        """
        根据创建时间范围物理删除审计日志。

        :param start_time: 起始时间
        :param end_time: 结束时间
        :return: 实际删除的记录数
        """
        if not start_time or not end_time:
            error_message: str = "删除审计日志失败, 参数[start_time, end_time]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        return int(await self.model.filter(created_time__range=[start_time, end_time]).delete())

    async def get_statistics_by_user(self, user_id: int) -> Dict[str, Any]:
        """
        统计指定用户的审计日志：总量、根据请求方式、根据响应代码分布。

        :param user_id: 用户ID
        :return: 含user_id、total_count、method_statistics、code_statistics的字典
        """
        if not user_id:
            error_message: str = "统计审计日志失败, 参数[user_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        base = self.model.filter(user_id=user_id)
        total_count, method_rows, code_rows = await asyncio.gather(
            base.count(),
            base.annotate(cnt=Count("id")).group_by("request_method").values("request_method", "cnt"),
            base.annotate(cnt=Count("id")).group_by("response_code").values("response_code", "cnt"),
        )

        method_stats = {
            str(row["request_method"]): int(row["cnt"])
            for row in method_rows
            if row.get("request_method") is not None
        }
        code_stats = {
            str(row["response_code"]): int(row["cnt"])
            for row in code_rows
            if row.get("response_code")
        }

        return {
            "user_id": user_id,
            "total_count": int(total_count),
            "method_statistics": method_stats,
            "code_statistics": code_stats,
        }

    async def get_recent_audits(self, limit: int = 10, user_id: Optional[int] = None) -> List[Audit]:
        """
        根据创建时间倒序获取最近的审计日志（仅列表字段）。

        :param limit: 返回条数上限，默认10
        :param user_id: 可选，仅查询该用户的日志
        :return: 审计日志列表
        """
        query = self.model.all().only(*AUDIT_LIST_ONLY_FIELDS)
        if user_id:
            query = query.filter(user_id=user_id)
        return await query.order_by("-created_time").limit(limit)

    async def clear_all(self) -> int:
        """
        清空全部审计日志，物理删除且不可恢复。

        :return: 清空前的记录总数(即删除数量)
        """
        count = await self.model.all().count()
        await self.model.all().delete()
        LOGGER.warning(f"已清空所有审计日志, 删除数量: {count}")
        return count
