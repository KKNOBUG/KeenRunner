# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_report_crud
@DateTime: 2025/11/27 09:34
"""
from typing import Optional, Dict, Any

from tortoise.exceptions import IntegrityError
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
    DataAlreadyExistsException, NotFoundException, ParameterException
)


class AutoTestApiReportCrud(ScaffoldCrud[AutoTestApiReportInfo, AutoTestApiReportCreate, AutoTestApiReportUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestApiReportInfo)

    async def get_by_id(self, report_id: int) -> Optional[AutoTestApiReportInfo]:
        """根据ID查询报告信息"""
        return await self.model.filter(id=report_id, state__not=1).first()

    async def get_by_code(self, report_code: str) -> Optional[AutoTestApiReportInfo]:
        """根据ID查询报告信息"""
        return await self.model.filter(report_code=report_code, state__not=1).first()

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True
    ) -> Optional[AutoTestApiReportInfo]:
        stmt: QuerySet = self.model.filter(**conditions, state__not=1)
        return await (stmt.first() if only_one else stmt.all())

    async def create_report(self, report_in: AutoTestApiReportCreate) -> AutoTestApiReportInfo:
        """创建报告信息"""
        case_id: int = report_in.case_id
        case_code: str = report_in.case_code
        case_instance = await AUTOTEST_API_CASE_CRUD.get_by_conditions(
            only_one=True,
            conditions={"id": case_id, "case_code": case_code}
        )
        if not case_instance:
            raise NotFoundException(message=f"用例(id={case_id}, case_code={case_code})信息不存在")
        try:
            report_dict = report_in.dict(exclude_unset=True)
            instance = await self.create(report_dict)
            return instance
        except IntegrityError as e:
            raise DataAlreadyExistsException(message=f"创建报告失败: {str(e)}")

    async def update_report(self, report_in: AutoTestApiReportUpdate) -> AutoTestApiReportInfo:
        """更新报告信息"""
        report_id = report_in.report_id
        report_code = report_in.report_code
        if not report_id and not report_code:
            raise ParameterException(message=f"参数缺失, 更新报告信息必须传递id或code")

        if report_id:
            instance = await self.query(report_id)
        else:
            instance = await self.model.filter(report_code=report_code).first()
        if not instance:
            condition = f"id={report_id}" if report_id else f"report_code={report_code}"
            raise NotFoundException(message=f"报告({condition})信息不存在")

        try:
            # 构建更新字典
            report_id = instance.id
            update_dict = report_in.model_dump(
                exclude_unset=True,
                exclude={"id", "case_id", "case_name", "report_code"}
            )
            instance = await self.update(id=report_id, obj_in=update_dict)
            return instance
        except IntegrityError as e:
            raise DataAlreadyExistsException(message=f"更新用例失败: {str(e)}")

    async def delete_report(
            self,
            report_id: Optional[int] = None,
            report_code: Optional[int] = None
    ) -> AutoTestApiReportInfo:
        """删除测试报告信息"""
        if not report_id and not report_code:
            raise ParameterException(message=f"参数缺失, 删除报告信息必须传递id或code")
        if report_id:
            instance = await self.query(report_id)
        else:
            instance = await self.model.filter(report_code=report_code).first()
            report_id = instance.id
        if not instance:
            condition = f"id={report_id}" if report_id else f"report_code={report_code}"
            raise NotFoundException(message=f"测试报告({condition})信息不存在")

        # 检查是否存在步骤明细关联，如果存在则删除
        ...

        instance.state = 1
        await instance.save()
        return instance

    async def select_reports(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        """按条件查询报告信息"""
        return await self.list(
            page=page,
            page_size=page_size,
            search=search,
            order=order
        )


AUTOTEST_API_REPORT_CRUD = AutoTestApiReportCrud()
