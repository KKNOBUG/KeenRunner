# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_transfer_crud.py
@DateTime: 2026/8/17
"""
import traceback
from typing import Optional, List, Tuple

from tortoise.exceptions import IntegrityError, FieldError
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from backend.applications.aotutest.models.autotest_model import AutoTestApiCaseTransferInfo
from backend.applications.aotutest.schemas.autotest_case_transfer_schema import AutoTestApiCaseTransferCreate
from backend.applications.aotutest.services.autotest_case_crud import AutoTestApiCaseCrud, _duplicate_case_message
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)
from backend.services import get_current_username


class AutoTestApiCaseTransferCrud(ScaffoldCrud[AutoTestApiCaseTransferInfo, AutoTestApiCaseTransferCreate, AutoTestApiCaseTransferCreate]):

    def __init__(self):
        super().__init__(model=AutoTestApiCaseTransferInfo)

    async def get_by_id(
            self,
            transfer_id: int,
            on_error: bool = False,
            **kwargs,
    ) -> Optional[AutoTestApiCaseTransferInfo]:
        """
        根据主键ID查询转让记录。

        :param transfer_id: 转让记录主键ID
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 转让记录或None
        """
        if not transfer_id:
            error_message: str = "查询用例转让记录失败, 参数[transfer_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.get_or_none(id=transfer_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询用例转让记录失败, 记录[id={transfer_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def transfer_case(self, transfer_in: AutoTestApiCaseTransferCreate) -> AutoTestApiCaseTransferInfo:
        """
        转让用例所属人：仅当前所属人可操作，写入转让记录并改owner_user，不改created_user。

        :param transfer_in: 转让入参
        :return: 新增的转让记录
        """
        case_id: int = transfer_in.case_id
        next_owner_user = str(transfer_in.next_owner_user or "").strip().upper()
        if not next_owner_user:
            error_message: str = "转让用例失败, 参数[next_owner_user]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        operator = get_current_username()
        if not operator:
            error_message: str = "转让用例失败, 当前登录账号为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        case_crud = AutoTestApiCaseCrud()
        case_instance = await case_crud.get_by_id(case_id=case_id, on_error=True, state__not=1)
        prev_owner_user = (case_instance.owner_user or "").strip().upper()
        if not prev_owner_user:
            error_message: str = "转让用例失败, 所属人员不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if prev_owner_user != operator:
            error_message: str = "转让用例失败, 仅当前所属人可转让"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if prev_owner_user == next_owner_user:
            error_message: str = "转让用例失败, 转入人与当前所属人相同"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        existing_case = await case_crud._get_by_owner_key(
            case_project=case_instance.case_project,
            case_name=case_instance.case_name,
            case_type=case_instance.case_type,
            owner_user=next_owner_user,
        )
        if existing_case:
            error_message: str = (
                f"转让用例失败, "
                f"{_duplicate_case_message(case_instance.case_project, case_instance.case_name, case_instance.case_type, next_owner_user)}"
            )
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        try:
            async with in_transaction():
                await case_crud.update(
                    id=case_id,
                    obj_in={
                        "owner_user": next_owner_user,
                        "case_version": (case_instance.case_version or 1) + 1,
                    },
                )
                instance = await self.create({
                    "case_id": case_id,
                    "prev_owner_user": prev_owner_user,
                    "next_owner_user": next_owner_user,
                    "transfer_desc": transfer_in.transfer_desc,
                })
                LOGGER.info(
                    f"转让用例成功: case_id={case_id}, "
                    f"prev_owner_user={prev_owner_user}, next_owner_user={next_owner_user}, created_user={operator}"
                )
                return instance
        except IntegrityError as e:
            error_message: str = f"转让用例失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def select_transfers(
            self,
            search: Q,
            page: int,
            page_size: int,
            order: List[str],
    ) -> Tuple[int, List[AutoTestApiCaseTransferInfo]]:
        """
        根据条件分页查询转让记录。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: 总条数与当前页记录
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询用例转让记录失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
