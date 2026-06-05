# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : audit_crud
@DateTime: 2026/4/20 16:53
"""
from typing import List, Optional, Any, Tuple, Dict

from tortoise.expressions import Q

from backend.applications.base.models.audit_model import Audit
from backend.applications.base.schemas.audit_schema import AuditCreate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import ParameterException, NotFoundException


class AuditCrud(ScaffoldCrud[Audit, AuditCreate, Any]):
    def __init__(self):
        super().__init__(model=Audit)

    async def get_by_id(self, audit_id: int, on_error: bool = True) -> Optional[Audit]:
        """根据ID获取单条审计日志"""
        if not audit_id:
            error_message: str = "查询审计日志失败, 参数(audit_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.get_or_none(id=audit_id)
        if not instance and on_error:
            error_message: str = f"查询审计日志失败, 审计日志(id={audit_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_user_id(self, user_id: int, on_error: bool = True) -> Optional[List[Audit]]:
        """根据用户ID获取该用户的所有审计日志"""
        if not user_id:
            error_message: str = "查询审计日志失败, 参数(user_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instances = await self.model.filter(user_id=user_id).all()
        if not instances and on_error:
            error_message: str = f"查询审计日志失败, 用户(user_id={user_id})没有审计日志"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instances

    async def create_audit(self, audit_in: AuditCreate) -> Audit:
        """创建审计日志记录"""
        return await self.create(audit_in)

    async def list_audit(
            self,
            page: int = 1,
            page_size: int = 10,
            search: Q = Q(),
            order: Optional[list] = None
    ) -> Tuple[int, List[Audit]]:
        """分页查询审计日志列表"""
        return await self.list(page=page, page_size=page_size, search=search, order=order or ["-created_time"])

    async def delete_by_id(self, audit_id: int) -> Audit:
        """根据ID删除单条审计日志"""
        instance = await self.get_by_id(audit_id=audit_id, on_error=True)
        await instance.delete()
        return instance

    async def delete_by_ids(self, audit_ids: Optional[List[int]]) -> int:
        """按主键列表批量物理删除"""
        if not audit_ids:
            return 0
        ids = [int(x) for x in audit_ids]
        return int(await self.model.filter(id__in=ids).delete())

    async def delete_by_user_id(self, user_id: int) -> int:
        """根据用户ID删除该用户的所有审计日志"""
        if not user_id:
            error_message: str = "删除审计日志失败, 参数(user_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        return int(await self.model.filter(user_id=user_id).delete())

    async def delete_by_time_range(
            self,
            start_time: str,
            end_time: str
    ) -> int:
        """根据时间范围删除审计日志"""
        if not start_time or not end_time:
            error_message: str = "删除审计日志失败, 时间范围参数不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        return int(await self.model.filter(created_time__range=[start_time, end_time]).delete())

    async def get_statistics_by_user(self, user_id: int) -> Dict[str, Any]:
        """获取指定用户的审计日志统计信息"""
        if not user_id:
            error_message: str = "统计审计日志失败, 参数(user_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        total_count = await self.model.filter(user_id=user_id).count()

        # 按请求方式统计
        method_stats = {}
        methods = await self.model.filter(user_id=user_id).values_list("request_method", flat=True)
        for method in methods:
            method_stats[method] = method_stats.get(method, 0) + 1

        # 按响应代码统计
        code_stats = {}
        codes = await self.model.filter(user_id=user_id).values_list("response_code", flat=True)
        for code in codes:
            if code:
                code_stats[code] = code_stats.get(code, 0) + 1

        return {
            "user_id": user_id,
            "total_count": total_count,
            "method_statistics": method_stats,
            "code_statistics": code_stats,
        }

    async def get_recent_audits(
            self,
            limit: int = 10,
            user_id: Optional[int] = None
    ) -> List[Audit]:
        """获取最近的审计日志"""
        query = self.model.all()
        if user_id:
            query = query.filter(user_id=user_id)
        return await query.order_by("-created_time").limit(limit)

    async def clear_all(self) -> int:
        """清空所有审计日志（危险操作）"""
        count = await self.model.all().count()
        await self.model.all().delete()
        LOGGER.warning(f"已清空所有审计日志, 删除数量: {count}")
        return count


AUDIT_CRUD = AuditCrud()
