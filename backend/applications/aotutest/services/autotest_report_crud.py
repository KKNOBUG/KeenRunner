# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_report_crud
@DateTime: 2025/11/27 09:34
"""
from typing import Optional, Dict, Any

from tortoise.exceptions import IntegrityError, FieldError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

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
    DataAlreadyExistsException,
)


class AutoTestApiReportCrud(ScaffoldCrud[AutoTestApiReportInfo, AutoTestApiReportCreate, AutoTestApiReportUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestApiReportInfo)

    async def get_by_id(self, report_id: int, on_error: bool = False) -> Optional[AutoTestApiReportInfo]:
        if not report_id:
            raise ParameterException(message="参数(report_id)不允许为空")
        instance = await self.model.filter(id=report_id, state__not=1).first()
        if not instance and on_error:
            raise NotFoundException(message=f"报告(id={report_id})不存在")
        return instance

    async def get_by_code(self, report_code: str, on_error: bool = False) -> Optional[AutoTestApiReportInfo]:
        if not report_code:
            raise ParameterException(message="参数(report_code)不允许为空")
        instance = await self.model.filter(report_code=report_code, state__not=1).first()
        if not instance and on_error:
            raise NotFoundException(message=f"报告(code={report_code})不存在")
        return instance

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True,
            on_error: bool = False
    ) -> Optional[AutoTestApiReportInfo]:
        try:
            stmt: QuerySet = self.model.filter(**conditions, state__not=1)
            instances = await (stmt.first() if only_one else stmt.all())
        except FieldError as e:
            raise ParameterException(message=f"查询'报告'异常, 发现未知字段: {e}")

        if not instances and on_error:
            raise NotFoundException(message=f"按条件{conditions}查询'报告'无记录")
        return instances

    async def create_report(self, report_in: AutoTestApiReportCreate) -> AutoTestApiReportInfo:
        case_id: int = report_in.case_id
        case_code: str = report_in.case_code
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
            raise DataBaseStorageException(message=f"创建报告失败, 违法约束规则: {str(e)}")

    async def update_report(self, report_in: AutoTestApiReportUpdate) -> AutoTestApiReportInfo:
        report_id: Optional[int] = report_in.report_id
        report_code: Optional[str] = report_in.report_code
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
            raise DataBaseStorageException(message=f"更新报告失败, 违法约束规则: {e}")

    async def delete_report(
            self,
            report_id: Optional[int] = None,
            report_code: Optional[str] = None
    ) -> AutoTestApiReportInfo:
        if report_id:
            instance = await self.get_by_id(report_id=report_id, on_error=True)
        else:
            instance = await self.get_by_code(report_code=report_code, on_error=True)
            report_id = instance.id

        # todo: 检查是否存在明细关联，如果存在则删除

        instance.state = 1
        await instance.save()
        return instance

    async def select_reports(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            raise ParameterException(message=f"查询'报告'异常, 错误描述: {e}")


AUTOTEST_API_REPORT_CRUD = AutoTestApiReportCrud()
