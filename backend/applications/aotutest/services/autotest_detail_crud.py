# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_detail_crud
@DateTime: 2025/11/27 14:25
"""
import traceback
from typing import Optional, Dict, Any, Union, List

from tortoise.exceptions import IntegrityError, FieldError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from backend import LOGGER
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
            error_message: str = "查询明细信息失败, 参数(detail_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(id=detail_id, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询明细信息失败, 明细(id={detail_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, detail_code: str, on_error: bool = False) -> Optional[AutoTestApiDetailsInfo]:
        if not detail_code:
            error_message: str = "查询明细信息失败, 参数(detail_code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(detail_code=detail_code, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询明细信息失败, 明细(detail_code={detail_code})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True,
            on_error: bool = False
    ) -> Optional[Union[AutoTestApiDetailsInfo, List[AutoTestApiDetailsInfo]]]:
        try:
            stmt: QuerySet = self.model.filter(**conditions, state__not=1)
            instances = await (stmt.first() if only_one else stmt.all())
        except FieldError as e:
            error_message: str = f"查询明细信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

        if not instances and on_error:
            error_message: str = f"查询明细信息失败, 条件{conditions}不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instances

    async def create_detail(self, detail_in: AutoTestApiDetailCreate) -> AutoTestApiDetailsInfo:
        case_id: int = detail_in.case_id
        case_code: str = detail_in.case_code

        # 业务层验证：检查用例是否存在
        await AUTOTEST_API_CASE_CRUD.get_by_conditions(
            only_one=True,
            on_error=True,
            conditions={"id": case_id, "case_code": case_code}
        )

        # 业务层验证：检查报告是否存在
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
        except IntegrityError as e:
            error_message: str = f"新增明细信息失败, 违法联合唯一约束规则(report_code, case_code, step_code, num_cycles)"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e
        except Exception as e:
            error_message: str = f"新增明细信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataAlreadyExistsException(message=error_message) from e

    async def update_detail(self, detail_in: AutoTestApiDetailUpdate) -> AutoTestApiDetailsInfo:
        case_id: Optional[int] = detail_in.case_id
        case_code: Optional[str] = detail_in.case_code

        # 业务层验证：检查用例是否存在
        await AUTOTEST_API_CASE_CRUD.get_by_conditions(
            only_one=True,
            on_error=True,
            conditions={"id": case_id, "case_code": case_code}
        )

        # 业务层验证：检查报告是否存在
        report_code = detail_in.report_code
        await AUTOTEST_API_REPORT_CRUD.get_by_conditions(
            only_one=True,
            on_error=True,
            conditions={"case_id": case_id, "case_code": case_code, "report_code": report_code}
        )

        # 业务层验证：更新明细传递参数
        detail_id: Optional[int] = detail_in.detail_id
        step_code: Optional[str] = detail_in.step_code
        if not detail_id and (not report_code or not step_code):
            error_message: str = f"参数缺失, 更新明细信息时必须传递(detail_id)或(report_code, step_code)字段"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
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
            error_message: str = f"更新明细信息失败, 违法约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_detail(
            self,
            detail_id: Optional[int] = None,
            step_code: Optional[int] = None,
            report_code: Optional[int] = None
    ) -> AutoTestApiDetailsInfo:
        if not detail_id and (not report_code or not step_code):
            error_message: str = f"参数缺失, 更新明细信息时必须传递(detail_id)或(report_code, step_code)字段"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 业务层验证：检查明细信息是否存在
        if detail_id:
            instance = await self.get_by_id(detail_id=detail_id, on_error=False)
        else:
            instance = await self.get_by_conditions(
                only_one=True,
                on_error=False,
                conditions={"report_code": report_code, "step_code": step_code},
            )
        if not instance:
            error_message: str = (
                f"根据(detail_id={detail_id}或report_code={report_code}, step_code={step_code})条件检查失败, "
                f"明细信息不存在"
            )
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)

        instance.state = 1
        await instance.save()
        return instance

    async def select_details(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询明细信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e


AUTOTEST_API_DETAIL_CRUD = AutoTestApiDetailCrud()
