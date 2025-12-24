# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_detail_crud
@DateTime: 2025/11/27 14:25
"""
from typing import Optional, List, Dict, Any

from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from backend.applications.aotutest.models.autotest_model import AutoTestApiDetailsInfo
from backend.applications.aotutest.schemas.autotest_detail_schema import (
    AutoTestApiDetailCreate,
    AutoTestApiDetailUpdate
)
from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
from backend.applications.aotutest.services.autotest_report_crud import AUTOTEST_API_REPORT_CRUD
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import (
    DataAlreadyExistsException, NotFoundException, ParameterException
)


class AutoTestApiReportCrud(ScaffoldCrud[AutoTestApiDetailsInfo, AutoTestApiDetailCreate, AutoTestApiDetailUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestApiDetailsInfo)

    async def get_by_id(self, report_id: int) -> Optional[AutoTestApiDetailsInfo]:
        return await self.model.filter(id=report_id, state__not=1).first()

    async def get_by_code(self, report_code: int) -> Optional[List[AutoTestApiDetailsInfo]]:
        return await self.model.filter(report_code=report_code, state__not=1).all()

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True,
    ) -> Optional[AutoTestApiDetailsInfo]:
        """根据条件查询用例信息"""
        stmt: QuerySet = self.model.filter(**conditions, state__not=1)
        return await (stmt.first() if only_one else stmt.all())

    async def create_step_detail(self, detail_in: AutoTestApiDetailCreate) -> AutoTestApiDetailsInfo:
        case_id: int = detail_in.case_id
        case_code: str = detail_in.case_code
        case_instance = await AUTOTEST_API_CASE_CRUD.get_by_conditions(
            only_one=True,
            conditions={"id": case_id, "case_code": case_code}
        )
        if not case_instance:
            raise NotFoundException(message=f"用例(id={case_id}, case_code={case_code})信息不存在")

        report_code: str = detail_in.report_code
        report_instance = await AUTOTEST_API_REPORT_CRUD.get_by_conditions(
            only_one=True,
            conditions={"case_id": case_id, "case_code": case_code, "report_code": report_code}
        )
        if not report_instance:
            raise NotFoundException(
                message=f"测试报告(case_id={case_id}, case_code={case_code}, report_code={report_code})信息不存在"
            )
        try:
            report_dict = detail_in.dict(exclude_unset=True)
            instance = await self.create(report_dict)
            return instance
        except IntegrityError as e:
            raise DataAlreadyExistsException(message=f"创建报告失败: {str(e)}")

    async def update_step_detail(self, detail_in: AutoTestApiDetailUpdate) -> AutoTestApiDetailsInfo:
        """更新步骤明细信息"""
        # 检查用例是否存在
        case_id = detail_in.case_id
        case_code = detail_in.case_code
        case_instance = await AUTOTEST_API_CASE_CRUD.get_by_conditions(
            only_one=True,
            conditions={"id": case_id, "case_code": case_code}
        )
        if not case_instance:
            raise NotFoundException(message=f"用例(id={case_id}, case_code={case_code})信息不存在")

        # 检查报告清单是否存在
        report_code = detail_in.report_code
        report_instance = await AUTOTEST_API_REPORT_CRUD.get_by_conditions(
            only_one=True,
            conditions={"case_id": case_id, "case_code": case_code, "report_code": report_code}
        )
        if not report_instance:
            raise NotFoundException(
                message=f"测试报告(case_id={case_id}, case_code={case_code}, report_code={report_code})信息不存在"
            )
        # 更新报告明细
        detail_id = detail_in.detail_id
        step_code = detail_in.step_code
        if not detail_id and (not report_code and not step_code):
            raise ParameterException(message=f"参数缺失, 更新步骤明细信息必须传递id或步骤代码和报告代码")

        if detail_id:
            instance = await self.query(detail_id)
        else:
            instance = await self.get_by_conditions(
                only_one=True,
                conditions={"report_code": report_code, "step_code": step_code},
            )
            detail_id = instance.id
        if not instance:
            condition = f"id={detail_id}" if detail_id else f"report_code={report_code}, step_code={step_code}"
            raise NotFoundException(message=f"步骤明细({condition})信息不存在")

        try:
            # 构建更新字典
            update_dict = detail_in.model_dump(exclude_unset=True,
                                               exclude={"report_code", "step_code", "case_code", "case_id"})
            instance = await self.update(id=detail_id, obj_in=update_dict)
            return instance
        except IntegrityError as e:
            raise DataAlreadyExistsException(message=f"更新步骤明细失败: {str(e)}")

    async def delete_step_detail(
            self,
            detail_id: Optional[int] = None,
            step_code: Optional[int] = None,
            report_code: Optional[int] = None
    ) -> AutoTestApiDetailsInfo:
        if not detail_id and (not report_code and not step_code):
            raise ParameterException(message=f"参数缺失, 删除步骤明细信息必须传递id或步骤代码和报告代码")
        if detail_id:
            instance = await self.query(detail_id)
        else:
            instance = await self.get_by_conditions(
                only_one=True,
                conditions={"report_code": report_code, "step_code": step_code},
            )
        if not instance:
            condition = f"id={detail_id}" if detail_id else f"report_code={report_code}, step_code={step_code}"
            raise NotFoundException(message=f"步骤明细({condition})信息不存在")
        # 检查是否存在步骤明细关联，如果存在则删除
        ...

        instance.state = 1
        await instance.save()
        return instance

    async def select_step_details(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        return await self.list(
            page=page,
            page_size=page_size,
            search=search,
            order=order
        )


AUTOTEST_API_DETAIL_CRUD = AutoTestApiReportCrud()
