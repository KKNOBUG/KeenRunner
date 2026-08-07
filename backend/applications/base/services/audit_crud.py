# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : audit_crud
@DateTime: 2026/4/20 16:53
"""
import asyncio
from typing import List, Optional, Any, Tuple, Dict

from tortoise.expressions import Q
from tortoise.functions import Count

from backend.applications.base.models.audit_model import Audit
from backend.applications.base.schemas.audit_schema import AuditCreate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import ParameterException, NotFoundException

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

AUDIT_LIST_EXCLUDE_FIELDS = {
    "request_header",
    "request_params",
    "response_header",
    "response_params",
}


class AuditCrud(ScaffoldCrud[Audit, AuditCreate, Any]):

    def __init__(self):
        super().__init__(model=Audit)

    async def get_by_id(self, audit_id: int, on_error: bool = True) -> Optional[Audit]:
        """
        根据主键ID查询单条审计日志。

        :param audit_id: 审计日志ID
        :param on_error: 未找到时是否抛出NotFoundException
        :return: 审计日志实例或None
        :raises ParameterException: audit_id为空
        :raises NotFoundException: on_error为True且记录不存在
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
        :param on_error: 无记录时是否抛出NotFoundException
        :return: 审计日志列表；无匹配且on_error为False时为空列表
        :raises ParameterException: user_id空
        :raises NotFoundException: on_error为True且该用户无审计日志
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

    async def create_audit(self, audit_in: AuditCreate) -> Audit:
        """
        创建审计日志记录。

        :param audit_in: 新增审计日志入参
        :return: 新建的审计日志实例
        """
        return await self.create(audit_in)

    async def list_audit(
            self,
            page: int = 1,
            page_size: int = 10,
            search: Q = Q(),
            order: Optional[list] = None
    ) -> Tuple[int, List[Audit]]:
        """
        根据条件分页查询审计日志列表。

        查询方式优化：
        - 默认/空排序回落到 -created_time，便于命中 (created_time) / (user_id, created_time) 索引
        - 仅 SELECT 列表字段，避免拉取 request/response 大字段
        - count 与分页查询并行执行

        :param page: 页码，从1开始
        :param page_size: 每页记录数
        :param search: 搜索条件(Q对象)
        :param order: 排序字段列表；由调用方提供，空则 ["-created_time"]
        :return: (总记录数, 当前页审计日志列表)
        """
        order_fields: list = self._normalize_order(order) or ["-created_time"]
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
        :raises NotFoundException: 记录不存在
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
        :raises ParameterException: user_id为空
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
        :raises ParameterException: start_time或end_time为空
        """
        if not start_time or not end_time:
            error_message: str = "删除审计日志失败, 参数[start_time, end_time]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        return int(await self.model.filter(created_time__range=[start_time, end_time]).delete())

    async def get_statistics_by_user(self, user_id: int) -> Dict[str, Any]:
        """
        统计指定用户的审计日志：总量、根据请求方式、根据响应代码分布。

        使用 group_by + Count，避免把明细列全部加载到内存。

        :param user_id: 用户ID
        :return: 含user_id、total_count、method_statistics、code_statistics的字典
        :raises ParameterException: user_id为空
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
        清空全部审计日志(危险操作，物理删除)。

        :return: 清空前的记录总数(即删除数量)
        """
        count = await self.model.all().count()
        await self.model.all().delete()
        LOGGER.warning(f"已清空所有审计日志, 删除数量: {count}")
        return count
