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
        根据条件分页查询审计日志列表，默认根据创建时间倒序。

        :param page: 页码，从1开始
        :param page_size: 每页记录数
        :param search: 搜索条件(Q对象)
        :param order: 排序字段列表；为空时使用 ["-created_time"]
        :return: (总记录数, 当前页审计日志列表)
        """
        return await self.list(page=page, page_size=page_size, search=search, order=order)

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

        :param user_id: 用户ID
        :return: 含user_id、total_count、method_statistics、code_statistics的字典
        :raises ParameterException: user_id为空
        """
        if not user_id:
            error_message: str = "统计审计日志失败, 参数[user_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        total_count = await self.model.filter(user_id=user_id).count()

        # 根据请求方式统计
        method_stats = {}
        methods = await self.model.filter(user_id=user_id).values_list("request_method", flat=True)
        for method in methods:
            method_stats[method] = method_stats.get(method, 0) + 1

        # 根据响应代码统计
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

    async def get_recent_audits(self, limit: int = 10, user_id: Optional[int] = None) -> List[Audit]:
        """
        根据创建时间倒序获取最近的审计日志。

        :param limit: 返回条数上限，默认10
        :param user_id: 可选，仅查询该用户的日志
        :return: 审计日志列表
        """
        query = self.model.all()
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
