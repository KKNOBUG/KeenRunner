# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_detail_crud
@DateTime: 2025/11/27 14:25
"""
import traceback
from typing import Optional, List, Tuple

from tortoise.exceptions import IntegrityError, FieldError
from tortoise.expressions import Q

from backend.applications.aotutest.models.autotest_model import AutoTestApiDetailInfo
from backend.applications.aotutest.schemas.autotest_detail_schema import (
    AutoTestApiDetailCreate,
    AutoTestApiDetailUpdate
)
from backend.applications.aotutest.services.autotest_case_crud import AutoTestApiCaseCrud
from backend.applications.aotutest.services.autotest_report_crud import AutoTestApiReportCrud
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
)


class AutoTestApiDetailCrud(ScaffoldCrud[AutoTestApiDetailInfo, AutoTestApiDetailCreate, AutoTestApiDetailUpdate]):

    def __init__(self):
        super().__init__(model=AutoTestApiDetailInfo)

    async def get_by_id(self, detail_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestApiDetailInfo]:
        """
        根据主键ID查询明细。

        :param detail_id: 明细主键ID
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 明细实例或None
        """
        if not detail_id:
            error_message: str = "查询明细信息失败, 参数[detail_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.get_or_none(id=detail_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询明细信息失败, 记录[id={detail_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, detail_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestApiDetailInfo]:
        """
        根据报告标识代码查询明细。

        :param detail_code: 报告标识代码report_code
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 明细实例或None
        """
        if not detail_code:
            error_message: str = "查询明细信息失败, 参数[detail_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(report_code=detail_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询明细信息失败, 记录[detail_code={detail_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def create_detail(self, detail_in: AutoTestApiDetailCreate, *, skip_report_check: bool = False) -> AutoTestApiDetailInfo:
        """
        创建执行明细，校验用例与报告存在(可跳过报告校验)。

        :param detail_in: 明细创建schema
        :param skip_report_check: 为True时不校验报告是否存在
        :return: 创建后的明细实例
        """
        case_id: int = detail_in.case_id
        case_code: str = detail_in.case_code

        await AutoTestApiCaseCrud().get_by_conditions(
            only_one=True,
            on_error=True,
            id=case_id,
            case_code=case_code,
            state__not=1,
        )

        if not skip_report_check:
            report_code: str = detail_in.report_code
            await AutoTestApiReportCrud().get_by_conditions(
                only_one=True,
                on_error=True,
                case_id=case_id,
                case_code=case_code,
                report_code=report_code,
                state__not=1,
            )
        try:
            report_dict = detail_in.model_dump(exclude_none=True, exclude_unset=True)
            instance = await self.create(report_dict)
            return instance
        except IntegrityError as e:
            error_message: str = f"新增明细信息失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e
        except Exception as e:
            error_message: str = f"新增明细信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_detail(self, detail_in: AutoTestApiDetailUpdate) -> AutoTestApiDetailInfo:
        """
        更新明细，需提供detail_id或(report_code, step_code)定位。

        :param detail_in: 明细更新schema
        :return: 更新后的明细实例
        """
        case_id: Optional[int] = detail_in.case_id
        case_code: Optional[str] = detail_in.case_code

        await AutoTestApiCaseCrud().get_by_conditions(
            only_one=True,
            on_error=True,
            id=case_id,
            case_code=case_code,
            state__not=1,
        )

        report_code = detail_in.report_code
        await AutoTestApiReportCrud().get_by_conditions(
            only_one=True,
            on_error=True,
            case_id=case_id,
            case_code=case_code,
            report_code=report_code,
            state__not=1,
        )

        detail_id: Optional[int] = detail_in.detail_id
        step_code: Optional[str] = detail_in.step_code
        if not detail_id and (not report_code or not step_code):
            error_message: str = f"参数[detail_id]或[report_code, step_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if detail_id:
            await self.get_by_id(detail_id=detail_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_conditions(
                only_one=True,
                on_error=True,
                report_code=report_code,
                step_code=step_code,
                state__not=1,
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
            error_message: str = f"更新明细信息失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_detail(
            self,
            detail_id: Optional[int] = None,
            step_code: Optional[str] = None,
            report_code: Optional[str] = None
    ) -> AutoTestApiDetailInfo:
        """
        软删除明细，需提供detail_id或(report_code, step_code)。

        :param detail_id: 明细主键ID，与(report_code, step_code)二选一
        :param step_code: 步骤标识代码
        :param report_code: 报告标识代码
        :return: 软删除后的明细实例
        """
        if not detail_id and (not report_code or not step_code):
            error_message: str = f"参数[detail_id]或[report_code, step_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        if detail_id:
            instance = await self.get_by_id(detail_id=detail_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_conditions(
                only_one=True,
                on_error=True,
                report_code=report_code,
                step_code=step_code,
                state__not=1,
            )
        return await self.soft_delete(id=instance.id)

    async def select_details(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestApiDetailInfo]]:
        """
        根据条件分页查询明细列表。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询明细信息失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
