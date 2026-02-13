# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_report_crud
@DateTime: 2025/11/27 09:34
"""
import traceback
from typing import Optional, Dict, Any

from tortoise.exceptions import IntegrityError, FieldError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet
from tortoise.transactions import in_transaction

from backend import LOGGER
from backend.applications.aotutest.models.autotest_model import AutoTestApiReportInfo
from backend.applications.aotutest.schemas.autotest_report_schema import (
    AutoTestApiReportCreate,
    AutoTestApiReportUpdate
)
from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import (
    ParameterException,
    NotFoundException,
    DataBaseStorageException,
)


class AutoTestApiReportCrud(ScaffoldCrud[AutoTestApiReportInfo, AutoTestApiReportCreate, AutoTestApiReportUpdate]):
    """自动化测试报告的 CRUD 服务，负责报告的增删改查；删除报告会同步软删除关联明细。"""

    def __init__(self):
        """初始化 CRUD，绑定模型 AutoTestApiReportInfo。"""
        super().__init__(model=AutoTestApiReportInfo)

    async def get_by_id(self, report_id: int, on_error: bool = False) -> Optional[AutoTestApiReportInfo]:
        """根据报告主键 ID 查询单条报告（排除已删除）。

        :param report_id: 报告主键 ID。
        :param on_error: 为 True 时若未找到则抛出 NotFoundException。
        :returns: 报告实例或 None。
        :raises ParameterException: 当 report_id 为空时。
        :raises NotFoundException: 当 on_error 为 True 且记录不存在时。
        """
        if not report_id:
            error_message: str = "查询报告信息失败, 参数(report_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(id=report_id, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询报告信息失败, 报告(code={report_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, report_code: str, on_error: bool = False) -> Optional[AutoTestApiReportInfo]:
        """根据报告标识代码查询单条报告（排除已删除）。

        :param report_code: 报告标识代码。
        :param on_error: 为 True 时若未找到则抛出 NotFoundException。
        :returns: 报告实例或 None。
        :raises ParameterException: 当 report_code 为空时。
        :raises NotFoundException: 当 on_error 为 True 且记录不存在时。
        """
        if not report_code:
            error_message: str = "查询报告信息失败, 参数(report_code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(report_code=report_code, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询报告信息失败, 报告(code={report_code})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True,
            on_error: bool = False
    ) -> Optional[AutoTestApiReportInfo]:
        """根据条件查询报告（排除已删除）。

        :param conditions: 查询条件字典。
        :param only_one: 为 True 时返回单条记录，否则返回列表。
        :param on_error: 为 True 时若未找到则抛出 NotFoundException。
        :returns: 单条报告、报告列表或 None。
        :raises ParameterException: 条件非法或查询异常时。
        :raises NotFoundException: 当 on_error 为 True 且无匹配记录时。
        """
        try:
            stmt: QuerySet = self.model.filter(**conditions, state__not=1)
            instances = await (stmt.first() if only_one else stmt.all())
        except FieldError as e:
            error_message: str = f"查询报告信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
        except Exception as e:
            error_message: str = f"查询报告信息发生未知异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

        if not instances and on_error:
            error_message: str = f"查询报告信息失败, 条件{conditions}不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instances

    async def create_report(self, report_in: AutoTestApiReportCreate) -> AutoTestApiReportInfo:
        """创建报告，校验用例存在性。

        :param report_in: 报告创建 schema。
        :returns: 创建后的报告实例。
        :raises NotFoundException: 用例不存在时。
        :raises DataBaseStorageException: 违反数据库约束时。
        """
        case_id: int = report_in.case_id
        case_code: str = report_in.case_code

        # 业务层验证：检查用例是否存在
        await AUTOTEST_API_CASE_CRUD.get_by_conditions(
            only_one=True,
            on_error=True,
            conditions={"id": case_id, "case_code": case_code}
        )

        try:
            report_dict = report_in.dict(exclude_none=True, exclude_unset=True)
            instance = await self.create(report_dict)
            return instance
        except IntegrityError as e:
            error_message: str = f"新增报告信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_report(self, report_in: AutoTestApiReportUpdate) -> AutoTestApiReportInfo:
        """更新报告，支持按 report_id 或 report_code 定位。

        :param report_in: 报告更新 schema。
        :returns: 更新后的报告实例。
        :raises NotFoundException: 报告不存在时。
        :raises DataBaseStorageException: 违反约束时。
        """
        report_id: Optional[int] = report_in.report_id
        report_code: Optional[str] = report_in.report_code

        # 业务层验证：检查用例是否存在
        if report_id:
            await self.get_by_id(report_id=report_id, on_error=True)
        else:
            instance = await self.get_by_code(report_code=report_code, on_error=True)
            report_id: int = instance.id

        try:
            update_dict = report_in.model_dump(
                exclude_none=True,
                exclude_unset=True,
                exclude={"report_id", "report_code"}
            )
            instance = await self.update(id=report_id, obj_in=update_dict)
            return instance
        except IntegrityError as e:
            error_message: str = f"更新报告信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_report(
            self,
            report_id: Optional[int] = None,
            report_code: Optional[str] = None
    ) -> AutoTestApiReportInfo:
        """软删除报告（state=1），并同步软删除该报告下所有明细。

        :param report_id: 报告主键 ID，与 report_code 二选一。
        :param report_code: 报告标识代码，与 report_id 二选一。
        :returns: 软删除后的报告实例。
        :raises NotFoundException: 报告不存在时。
        """
        # 业务层验证：检查用例是否存在
        if report_id:
            instance = await self.get_by_id(report_id=report_id, on_error=True)
        else:
            instance = await self.get_by_code(report_code=report_code, on_error=True)

        # 业务层验证：检查报告是否存在明细信息, 如果存在则删除
        async with in_transaction():
            report_code = instance.report_code
            from backend.applications.aotutest.services.autotest_detail_crud import AUTOTEST_API_DETAIL_CRUD
            count = await AUTOTEST_API_DETAIL_CRUD.model.filter(report_code=report_code, state__not=1).update(state=1)
            LOGGER.warning(f"成功删除报告(report_code={report_code})关联的{count}条明细信息")

        instance.state = 1
        await instance.save()
        return instance

    async def select_reports(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        """分页查询报告列表。

        :param search: Tortoise Q 查询条件。
        :param page: 页码。
        :param page_size: 每页条数。
        :param order: 排序字段列表。
        :returns: 由 (总条数, 当前页记录列表) 组成的元组。
        :raises ParameterException: 查询条件非法导致 FieldError 时。
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询报告信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e


AUTOTEST_API_REPORT_CRUD = AutoTestApiReportCrud()
