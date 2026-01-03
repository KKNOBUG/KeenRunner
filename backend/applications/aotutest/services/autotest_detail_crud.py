# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_detail_crud
@DateTime: 2025/11/27 14:25
"""
from typing import Optional, Dict, Any

from tortoise.exceptions import IntegrityError, FieldError
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
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)


class AutoTestApiDetailCrud(ScaffoldCrud[AutoTestApiDetailsInfo, AutoTestApiDetailCreate, AutoTestApiDetailUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestApiDetailsInfo)

    async def get_by_id(self, detail_id: int, on_error: bool = False) -> Optional[AutoTestApiDetailsInfo]:
        if not detail_id:
            raise ParameterException(message="参数(detail_id)不允许为空")
        instance = await self.model.filter(id=detail_id, state__not=1).first()
        if not instance and on_error:
            raise NotFoundException(message=f"明细(id={detail_id})不存在")
        return instance

    async def get_by_code(self, detail_code: str, on_error: bool = False) -> Optional[AutoTestApiDetailsInfo]:
        if not detail_code:
            raise ParameterException(message="参数(detail_code)不允许为空")
        instance = await self.model.filter(detail_code=detail_code, state__not=1).first()
        if not instance and on_error:
            raise NotFoundException(message=f"明细(code={detail_code})不存在")
        return instance

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True,
            on_error: bool = False
    ) -> Optional[AutoTestApiDetailsInfo]:
        try:
            stmt: QuerySet = self.model.filter(**conditions, state__not=1)
            instances = await (stmt.first() if only_one else stmt.all())
        except FieldError as e:
            raise ParameterException(message=f"查询'明细'异常, 错误描述: {e}")

        if not instances and on_error:
            raise NotFoundException(message=f"按条件{conditions}查询'明细'无记录")
        return instances

    async def create_detail(self, detail_in: AutoTestApiDetailCreate) -> AutoTestApiDetailsInfo:
        case_id: int = detail_in.case_id
        case_code: str = detail_in.case_code
        await AUTOTEST_API_CASE_CRUD.get_by_conditions(
            only_one=True,
            on_error=True,
            conditions={"id": case_id, "case_code": case_code}
        )
        # 检查报告是否存在
        report_code: str = detail_in.report_code
        await AUTOTEST_API_REPORT_CRUD.get_by_conditions(
            only_one=True,
            on_error=True,
            conditions={"case_id": case_id, "case_code": case_code, "report_code": report_code}
        )
        try:
            report_dict = detail_in.dict(exclude_none=True, exclude_unset=True)
            instance = await self.create(report_dict)
            return instance
        except IntegrityError:
            raise DataBaseStorageException(message=f"创建报告失败, 违法联合唯一约束规则(report_code、case_code、step_code、num_cycles)")
        except Exception as e:
            raise DataAlreadyExistsException(message=f"创建明细失败, 异常描述: {e}")

    async def update_detail(self, detail_in: AutoTestApiDetailUpdate) -> AutoTestApiDetailsInfo:
        # 检查用例是否存在
        case_id: Optional[int] = detail_in.case_id
        case_code: Optional[str] = detail_in.case_code
        await AUTOTEST_API_CASE_CRUD.get_by_conditions(
            only_one=True,
            on_error=True,
            conditions={"id": case_id, "case_code": case_code}
        )
        # 检查报告是否存在
        report_code = detail_in.report_code
        await AUTOTEST_API_REPORT_CRUD.get_by_conditions(
            only_one=True,
            on_error=True,
            conditions={"case_id": case_id, "case_code": case_code, "report_code": report_code}
        )
        # 更新报告明细
        detail_id: Optional[int] = detail_in.detail_id
        step_code: Optional[str] = detail_in.step_code
        if not detail_id and (not report_code or not step_code):
            raise ParameterException(message=f"参数缺失, 更新明细信息必须传递id或步骤代码和报告代码")
        if detail_id:
            await self.get_by_id(detail_id=detail_id, on_error=True)
        else:
            instance = await self.get_by_conditions(
                only_one=True,
                on_error=True,
                conditions={"report_code": report_code, "step_code": step_code},
            )
            detail_id = instance.id
        try:
            update_dict = detail_in.model_dump(
                exclude_none=True,
                exclude_unset=True,
                exclude={"report_code", "step_code", "case_code", "case_id", "detail_id"}
            )
            instance = await self.update(id=detail_id, obj_in=update_dict)
            return instance
        except IntegrityError as e:
            raise DataBaseStorageException(message=f"更新明细失败, 违法约束规则: {str(e)}")

    async def delete_detail(
            self,
            detail_id: Optional[int] = None,
            step_code: Optional[int] = None,
            report_code: Optional[int] = None
    ) -> AutoTestApiDetailsInfo:
        if not detail_id and (not report_code or not step_code):
            raise ParameterException(message=f"参数缺失, 删除步骤明细信息必须传递id或步骤代码和报告代码")
        if detail_id:
            instance = await self.get_by_id(detail_id=detail_id, on_error=True)
        else:
            instance = await self.get_by_conditions(
                only_one=True,
                on_error=True,
                conditions={"report_code": report_code, "step_code": step_code},
            )

        # todo: 检查是否存在步骤明细关联，如果存在则删除

        instance.state = 1
        await instance.save()
        return instance

    async def select_details(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            raise ParameterException(message=f"查询'明细'异常, 错误描述: {e}")


AUTOTEST_API_DETAIL_CRUD = AutoTestApiDetailCrud()
