# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_report_crud
@DateTime: 2025/11/27 09:34
"""
import traceback
from collections import defaultdict
from typing import Optional, List, Tuple, Dict, Any

from tortoise.exceptions import IntegrityError, FieldError
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from backend.applications.aotutest.models.autotest_model import AutoTestApiReportInfo
from backend.applications.aotutest.schemas.autotest_report_schema import (
    AutoTestApiReportCreate,
    AutoTestApiReportUpdate,
    AutoTestApiReportBatchSelect,
    AutoTestApiReportBatchItem,
)
from backend.applications.aotutest.services.autotest_case_crud import AutoTestApiCaseCrud
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    ParameterException,
    NotFoundException,
    DataBaseStorageException,
)
from backend.enums import AutoTestTaskStatus


class AutoTestApiReportCrud(ScaffoldCrud[AutoTestApiReportInfo, AutoTestApiReportCreate, AutoTestApiReportUpdate]):

    def __init__(self):
        super().__init__(model=AutoTestApiReportInfo)

    async def get_by_id(self, report_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestApiReportInfo]:
        """
        根据主键ID查询报告。

        :param report_id: 报告主键ID
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 报告实例或None
        :raises ParameterException: report_id为空
        :raises NotFoundException: on_error为True且记录不存在
        """
        if not report_id:
            error_message: str = "查询报告信息失败, 参数[report_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(id=report_id, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询报告信息失败, 记录[id={report_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, report_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestApiReportInfo]:
        """
        根据报告标识代码查询报告。

        :param report_code: 报告标识代码
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 报告实例或None
        :raises ParameterException: report_code为空
        :raises NotFoundException: on_error为True且记录不存在
        """
        if not report_code:
            error_message: str = "查询报告信息失败, 参数[report_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(report_code=report_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询报告信息失败, 记录[code={report_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def create_report(self, report_in: AutoTestApiReportCreate) -> AutoTestApiReportInfo:
        """
        创建报告，校验用例存在。

        :param report_in: 报告创建schema
        :return: 创建后的报告实例
        :raises NotFoundException: 用例不存在
        :raises DataBaseStorageException: 违反数据库约束
        """
        case_id: int = report_in.case_id
        case_code: str = report_in.case_code

        # 业务层验证：检查用例是否存在
        await AutoTestApiCaseCrud().get_by_conditions(
            only_one=True,
            on_error=True,
            id=case_id,
            case_code=case_code,
            state__not=1,
        )

        try:
            report_dict = report_in.model_dump(exclude_none=True, exclude_unset=True)
            instance = await self.create(report_dict)
            return instance
        except IntegrityError as e:
            error_message: str = f"新增报告信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_report(self, report_in: AutoTestApiReportUpdate) -> AutoTestApiReportInfo:
        """
        更新报告，根据report_id或report_code定位。

        :param report_in: 报告更新schema
        :return: 更新后的报告实例
        :raises NotFoundException: 报告不存在
        :raises DataBaseStorageException: 违反约束
        """
        report_id: Optional[int] = report_in.report_id
        report_code: Optional[str] = report_in.report_code

        # 业务层验证：检查用例是否存在
        if report_id:
            await self.get_by_id(report_id=report_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(report_code=report_code, on_error=True, state__not=1)
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

    async def delete_report(self, report_id: Optional[int] = None, report_code: Optional[str] = None) -> AutoTestApiReportInfo:
        """
        软删除报告，并同步软删除该报告下所有明细。

        :param report_id: 报告主键ID，与report_code二选一
        :param report_code: 报告标识代码，与report_id二选一
        :return: 软删除后的报告实例
        :raises NotFoundException: 报告不存在
        """
        # 业务层验证：检查用例是否存在
        if report_id:
            instance = await self.get_by_id(report_id=report_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(report_code=report_code, on_error=True, state__not=1)

        # 业务层验证：检查报告是否存在明细信息, 如果存在则删除
        async with in_transaction():
            report_code = instance.report_code
            from backend.applications.aotutest.services.autotest_detail_crud import AutoTestApiDetailCrud
            count = await AutoTestApiDetailCrud().model.filter(report_code=report_code, state__not=1).update(state=1)
            LOGGER.warning(f"成功删除报告[report_code={report_code}]关联的{count}条明细信息")
            instance.state = 1
            await instance.save()
        return instance

    async def select_reports(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestApiReportInfo]]:
        """
        根据条件分页查询报告列表。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)
        :raises ParameterException: 查询字段非法
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询报告信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    @staticmethod
    def _parse_elapsed_seconds(val: Any) -> float:
        if val is None or val == "":
            return 0.0
        text = str(val).strip().rstrip("sS")
        try:
            return float(text)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _is_case_success(case_state: Any) -> bool:
        return case_state is True or case_state == "true"

    @classmethod
    def _resolve_batch_execute_result(cls, reports: List[Dict[str, Any]]) -> AutoTestTaskStatus:
        """
        按脚本维度汇总批次结果。

        - 成功：每个脚本的全部运行（含数据驱动）均成功
        - 部分成功：至少一个脚本的全部运行均成功，但并非全部脚本都如此
        - 失败：没有任何一个脚本达到「其全部运行均成功」
        """
        by_case: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in reports:
            case_id = row.get("case_id")
            key = (
                str(case_id)
                if case_id is not None
                else f"unknown:{row.get('report_code') or row.get('report_id')}"
            )
            by_case[key].append(row)

        fully_ok = 0
        for rows in by_case.values():
            if rows and all(cls._is_case_success(r.get("case_state")) for r in rows):
                fully_ok += 1

        script_count = len(by_case)
        if 0 < script_count == fully_ok:
            return AutoTestTaskStatus.SUCCESS
        if fully_ok >= 1:
            return AutoTestTaskStatus.PARTIAL_SUCCESS
        return AutoTestTaskStatus.FAILURE

    async def search_batches(self, batch_in: AutoTestApiReportBatchSelect) -> Tuple[int, List[AutoTestApiReportBatchItem]]:
        """
        按task_code拉取报告，按batch_code聚合并计算执行结果，再按批次分页。

        :param batch_in: 批次查询入参
        :return: (批次总数, 当前页批次列表)
        """
        task_code = (batch_in.task_code or "").strip()
        if not task_code:
            raise ParameterException(message="参数[task_code]不允许为空")

        state = 0 if batch_in.state is None else batch_in.state
        instances: List[AutoTestApiReportInfo] = await self.model.filter(
            task_code=task_code,
            state=state,
        ).order_by("case_st_time").all()

        if not instances:
            return 0, []

        case_ids = list({obj.case_id for obj in instances if obj.case_id is not None})
        case_name_map: Dict[int, str] = {}
        if case_ids:
            case_name_map = dict(
                await AutoTestApiCaseCrud().model.filter(
                    id__in=case_ids,
                    state__not=1
                ).values_list("id", "case_name")
            )

        exclude_fields = {"state", "created_time", "updated_time", "reserve_1", "reserve_2", "reserve_3"}
        report_dicts: List[Dict[str, Any]] = []
        for obj in instances:
            item = await obj.to_dict(exclude_fields=exclude_fields, replace_fields={"id": "report_id"})
            item["case_name"] = case_name_map.get(item.get("case_id"), "")
            report_dicts.append(item)

        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in report_dicts:
            bc = row.get("batch_code")
            bc_text = str(bc).strip() if bc is not None else ""
            key = bc_text if bc_text else f"single:{row.get('report_code') or row.get('report_id')}"
            grouped[key].append(row)

        batches: List[AutoTestApiReportBatchItem] = []
        for key, rows in grouped.items():
            pass_count = sum(1 for r in rows if self._is_case_success(r.get("case_state")))
            total = len(rows)
            times = sorted(t for t in (r.get("case_st_time") for r in rows) if t)
            users = [u for u in (r.get("created_user") for r in rows) if u]
            result = self._resolve_batch_execute_result(rows)
            batches.append(
                AutoTestApiReportBatchItem(
                    batch_code=None if key.startswith("single:") else key,
                    execute_result=result,
                    pass_rate=round(pass_count / total * 100.0, 2) if total else None,
                    pass_count=pass_count,
                    report_count=total,
                    created_user=str(users[0]) if users else None,
                    execute_time=times[0] if times else None,
                    elapsed_seconds=round(sum(self._parse_elapsed_seconds(r.get("case_elapsed")) for r in rows), 3),
                    reports=rows if batch_in.include_reports else [],
                )
            )

        batches.sort(key=lambda b: b.execute_time or "", reverse=True)
        start = (batch_in.page - 1) * batch_in.page_size
        end = start + batch_in.page_size
        return len(batches), batches[start:end]
