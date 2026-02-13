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
from backend.applications.aotutest.models.autotest_model import AutoTestApiDetailInfo
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


class AutoTestApiDetailCrud(ScaffoldCrud[AutoTestApiDetailInfo, AutoTestApiDetailCreate, AutoTestApiDetailUpdate]):
    """自动化测试步骤执行明细的 CRUD 服务，负责明细的增删改查。"""

    def __init__(self):
        """初始化 CRUD，绑定模型 AutoTestApiDetailInfo。"""
        super().__init__(model=AutoTestApiDetailInfo)

    async def get_by_id(self, detail_id: int, on_error: bool = False) -> Optional[AutoTestApiDetailInfo]:
        """根据明细主键 ID 查询单条明细（排除已删除）。

        :param detail_id: 明细主键 ID。
        :param on_error: 为 True 时若未找到则抛出 NotFoundException。
        :returns: 明细实例或 None。
        :raises ParameterException: 当 detail_id 为空时。
        :raises NotFoundException: 当 on_error 为 True 且记录不存在时。
        """
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

    async def get_by_code(self, detail_code: str, on_error: bool = False) -> Optional[AutoTestApiDetailInfo]:
        """根据明细标识（report_code）查询单条明细（排除已删除）。

        :param detail_code: 报告标识代码 report_code，此处参数名为 detail_code。
        :param on_error: 为 True 时若未找到则抛出 NotFoundException。
        :returns: 明细实例或 None。
        :raises ParameterException: 当 detail_code 为空时。
        :raises NotFoundException: 当 on_error 为 True 且记录不存在时。
        """
        if not detail_code:
            error_message: str = "查询明细信息失败, 参数(detail_code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(report_code=detail_code, state__not=1).first()
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
    ) -> Optional[Union[AutoTestApiDetailInfo, List[AutoTestApiDetailInfo]]]:
        """根据条件查询明细（排除已删除）。

        :param conditions: 查询条件字典。
        :param only_one: 为 True 时返回单条记录，否则返回列表。
        :param on_error: 为 True 时若未找到则抛出 NotFoundException。
        :returns: 单条明细、明细列表或 None。
        :raises ParameterException: 条件非法或查询异常时。
        :raises NotFoundException: 当 on_error 为 True 且无匹配记录时。
        """
        try:
            stmt: QuerySet = self.model.filter(**conditions, state__not=1)
            instances = await (stmt.first() if only_one else stmt.all())
        except FieldError as e:
            error_message: str = f"查询明细信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
        except Exception as e:
            error_message: str = f"查询明细信息发生未知异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

        if not instances and on_error:
            error_message: str = f"查询明细信息失败, 条件{conditions}不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instances

    async def create_detail(self, detail_in: AutoTestApiDetailCreate, *, skip_report_check: bool = False) -> AutoTestApiDetailInfo:
        """创建一条执行明细，校验用例与报告存在性（可选跳过报告校验）。

        :param detail_in: 明细创建 schema。
        :param skip_report_check: 为 True 时不校验 report 是否存在。
        :returns: 创建后的明细实例。
        :raises NotFoundException: 用例或报告不存在时。
        :raises DataBaseStorageException: 违反唯一约束时。
        :raises DataAlreadyExistsException: 其他写入冲突时。
        """
        case_id: int = detail_in.case_id
        case_code: str = detail_in.case_code

        # 业务层验证：检查用例是否存在
        await AUTOTEST_API_CASE_CRUD.get_by_conditions(
            only_one=True,
            on_error=True,
            conditions={"id": case_id, "case_code": case_code}
        )

        # 业务层验证：检查报告是否存在
        if not skip_report_check:
            report_code: str = detail_in.report_code
            await AUTOTEST_API_REPORT_CRUD.get_by_conditions(
                only_one=True,
                on_error=True,
                conditions={"case_id": case_id, "case_code": case_code, "report_code": report_code}
            )
        try:
            report_dict = detail_in.model_dump(exclude_none=True, exclude_unset=True)
            instance = await self.create(report_dict)
            return instance
        except IntegrityError as e:
            error_message: str = f"新增明细信息失败, 违反联合唯一约束规则(report_code, case_code, step_code, num_cycles)"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e
        except Exception as e:
            error_message: str = f"新增明细信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataAlreadyExistsException(message=error_message) from e

    async def update_detail(self, detail_in: AutoTestApiDetailUpdate) -> AutoTestApiDetailInfo:
        """更新明细，需提供 detail_id 或 (report_code, step_code) 定位。

        :param detail_in: 明细更新 schema，含 case_id/case_code 及定位字段。
        :returns: 更新后的明细实例。
        :raises ParameterException: 定位参数缺失或用例/报告不存在时。
        :raises NotFoundException: 明细不存在时。
        :raises DataBaseStorageException: 违反约束时。
        """
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
            error_message: str = f"更新明细信息失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_detail(
            self,
            detail_id: Optional[int] = None,
            step_code: Optional[str] = None,
            report_code: Optional[str] = None
    ) -> AutoTestApiDetailInfo:
        """软删除明细，需提供 detail_id 或 (report_code, step_code)。

        :param detail_id: 明细主键 ID，与 (report_code, step_code) 二选一。
        :param step_code: 步骤标识代码，与 detail_id 二选一时必填。
        :param report_code: 报告标识代码，与 detail_id 二选一时必填。
        :returns: 软删除后的明细实例。
        :raises ParameterException: 参数缺失时。
        :raises NotFoundException: 明细不存在时。
        """
        if not detail_id and (not report_code or not step_code):
            error_message: str = f"参数缺失, 删除明细信息时必须传递(detail_id)或(report_code, step_code)字段"
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
        """分页查询明细列表。

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
            error_message: str = f"查询明细信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e


AUTOTEST_API_DETAIL_CRUD = AutoTestApiDetailCrud()
