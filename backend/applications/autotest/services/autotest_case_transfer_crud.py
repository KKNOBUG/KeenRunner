# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_case_transfer_crud.py
@DateTime: 2026/8/17
"""
import traceback
from typing import Optional, List, Tuple

from tortoise.exceptions import IntegrityError, FieldError
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from backend.applications.autotest.models.autotest_case_transfer_model import AutoTestCaseTransferModel
from backend.applications.autotest.schemas.autotest_case_transfer_schema import AutoTestCaseTransferCreate
from backend.applications.autotest.services.autotest_case_crud import AutoTestCaseCrud
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)
from backend.services import get_current_username, normalize_username


class AutoTestCaseTransferCrud(ScaffoldCrud[AutoTestCaseTransferModel, AutoTestCaseTransferCreate, AutoTestCaseTransferCreate]):
    """
    用例转让记录CRUD：转让唯一入口为 transfer_case。

    转让不改 created_user，仅变更 owner_user（数据归属随转让转移）；
    改写归属与写转让记录在同一事务内完成，保证两侧结果一致。
    """

    def __init__(self):
        """绑定转让记录模型，供基类通用CRUD复用。"""
        super().__init__(model=AutoTestCaseTransferModel)

    async def get_by_id(
            self,
            transfer_id: int,
            on_error: bool = False,
            **kwargs,
    ) -> Optional[AutoTestCaseTransferModel]:
        """
        根据主键ID查询转让记录。

        :param transfer_id: 转让记录主键ID，必填
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 转让记录或None
        :raises ParameterException: transfer_id 为空
        :raises NotFoundException: on_error=True 且记录不存在
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

    async def transfer_case(self, transfer_in: AutoTestCaseTransferCreate) -> AutoTestCaseTransferModel:
        """
        转让用例所属人：仅当前所属人可操作，写入转让记录并改owner_user，不改created_user。

        转让前先按目标唯一键（应用+名称+类型+转入人）做冲突预检，避免事务提交时
        撞上唯一索引只能向用户抛笼统的落库失败；写入记录时 created_user 由基类按登录态自动盖章。

        :param transfer_in: 转让入参（case_id/next_owner_user/transfer_desc）
        :return: 新增的转让记录
        :raises ParameterException: 转入人为空、登录态为空、用例无归属人、非当前所属人操作、转入人与当前所属人相同
        :raises NotFoundException: 用例不存在或已软删
        :raises DataAlreadyExistsException: 转入人名下已存在同应用同类型同名用例
        :raises DataBaseStorageException: 事务落库失败（并发冲突或状态已变）
        """
        case_id: int = transfer_in.case_id
        next_owner_user = normalize_username(transfer_in.next_owner_user)
        if not next_owner_user:
            error_message: str = "转让用例失败, 参数[next_owner_user]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        operator = get_current_username()
        if not operator:
            error_message: str = "转让用例失败, 当前登录账号为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        case_crud = AutoTestCaseCrud()
        case_instance = await case_crud.get_by_id(case_id=case_id, on_error=True, state__not=1)
        prev_owner_user = normalize_username(case_instance.owner_user)
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
            message_error: str = "转让用例失败，转入人名下已存在同应用、同类型、同名称的用例，请更换转入人或先调整同名用例"
            LOGGER.error(
                f"{message_error}, "
                f"查询条件: ["
                f"case_project={case_instance.case_project}, "
                f"case_name={case_instance.case_name}, "
                f"case_type={case_instance.case_type}, "
                f"owner_user={next_owner_user}"
                f"]"
            )
            raise DataAlreadyExistsException(message=message_error)

        try:
            async with in_transaction():
                # 先改归属再记流水：任一写入失败均回滚，避免出现“有转让记录但归属未变”
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
            error_message: str = "转让用例失败，转入人名下可能已存在同名用例，或用例状态已发生变化，请刷新后重试"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def select_transfers(
            self,
            search: Q,
            page: int,
            page_size: int,
            order: List[str],
    ) -> Tuple[int, List[AutoTestCaseTransferModel]]:
        """
        根据条件分页查询转让记录。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: 总条数与当前页记录
        :raises ParameterException: 查询/排序字段不被ORM支持
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = "查询用例转让记录失败，查询或排序条件包含不支持的字段，请调整筛选或排序条件"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
