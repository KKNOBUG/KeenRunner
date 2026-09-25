# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_report_crud
@DateTime: 2025/11/27 09:34
"""
import asyncio
import traceback
from collections import defaultdict
from typing import Optional, List, Tuple, Dict, Any, Set

from tortoise.exceptions import IntegrityError, FieldError
from tortoise.expressions import Q
from tortoise.functions import Count, Max, Sum
from tortoise.transactions import in_transaction

from backend.applications.autotest.models.autotest_report_model import AutoTestReportModel
from backend.applications.autotest.schemas.autotest_report_schema import (
    AutoTestReportCreate,
    AutoTestReportSelect,
    AutoTestReportUpdate,
    AutoTestReportBatchSelect,
    AutoTestReportBatchItem,
    AutoTestReportBatchScriptSelect,
    AutoTestReportBatchScriptItem,
    AutoTestReportScriptRoundItem,
    AutoTestReportScriptReportSelect,
)
from backend.applications.autotest.services.autotest_case_crud import AutoTestCaseCrud
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    ParameterException,
    NotFoundException,
    DataBaseStorageException,
)
from backend.enums import AutoTestTaskStatus


class AutoTestReportCrud(ScaffoldCrud[AutoTestReportModel, AutoTestReportCreate, AutoTestReportUpdate]):

    def __init__(self):
        super().__init__(model=AutoTestReportModel)

    async def get_by_id(self, report_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestReportModel]:
        """
        根据主键ID查询报告。

        :param report_id: 报告主键ID
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 报告实例或None
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

    async def get_by_code(self, report_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestReportModel]:
        """
        根据报告标识代码查询报告。

        :param report_code: 报告标识代码
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 报告实例或None
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

    async def create_report(self, report_in: AutoTestReportCreate) -> AutoTestReportModel:
        """
        创建报告，校验用例存在。

        :param report_in: 报告创建schema
        :return: 创建后的报告实例
        """
        case_id: int = report_in.case_id
        case_code: str = report_in.case_code

        await AutoTestCaseCrud().get_by_conditions(
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

    async def update_report(self, report_in: AutoTestReportUpdate) -> AutoTestReportModel:
        """
        更新报告，根据report_id或report_code定位。

        :param report_in: 报告更新schema
        :return: 更新后的报告实例
        """
        report_id: Optional[int] = report_in.report_id
        report_code: Optional[str] = report_in.report_code

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

    async def delete_report(self, report_id: Optional[int] = None, report_code: Optional[str] = None) -> AutoTestReportModel:
        """
        软删除报告，并同步软删除该报告下所有明细。

        :param report_id: 报告主键ID，与report_code二选一
        :param report_code: 报告标识代码，与report_id二选一
        :return: 软删除后的报告实例
        """
        if report_id:
            instance = await self.get_by_id(report_id=report_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(report_code=report_code, on_error=True, state__not=1)

        async with in_transaction():
            report_code = instance.report_code
            from backend.applications.autotest.services.autotest_detail_crud import AutoTestDetailCrud
            detail_crud = AutoTestDetailCrud()
            detail_ids = await detail_crud.model.filter(
                report_code=report_code, state__not=1
            ).values_list("id", flat=True)
            count = await detail_crud.soft_delete_batch(ids=list(detail_ids))
            LOGGER.warning(f"成功删除报告[report_code={report_code}]关联的{count}条明细信息")

        return await self.soft_delete(id=instance.id)

    async def select_reports(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestReportModel]]:
        """
        根据条件分页查询报告列表。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询报告信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    @staticmethod
    def _parse_elapsed_seconds(val: Any) -> float:
        """
        将耗时字段解析为秒数浮点值。

        :param val: 耗时原始值
        :return: 秒数；无法解析时返回0.0
        """
        if val is None or val == "":
            return 0.0
        text = str(val).strip().rstrip("sS")
        try:
            return float(text)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _is_case_success(case_state: Any) -> bool:
        """
        判断用例执行状态是否表示成功。

        :param case_state: 用例执行状态
        :return: 是否成功
        """
        return case_state is True or case_state == "true"

    @staticmethod
    def _group_rows_by_case(rows: List[Dict[str, Any]]) -> Dict[Any, List[Dict[str, Any]]]:
        """
        将报告行按用例维度分组，无法定位用例的行单独归组兜底。

        :param rows: 报告行字典列表
        :return: 以case_id为键的分组字典
        """
        by_case: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
        for row in rows:
            case_id = row.get("case_id")
            key = (
                case_id
                if case_id is not None
                else f"unknown:{row.get('report_code') or row.get('report_id')}"
            )
            by_case[key].append(row)
        return by_case

    @staticmethod
    def _merge_involve_envs(rows: List[Dict[str, Any]]) -> List[str]:
        """
        合并报告行涉及环境列表，保持首次出现顺序去重。

        :param rows: 报告行字典列表
        :return: 去重后的环境名称列表
        """
        envs: List[str] = []
        seen: Set[str] = set()
        for row in rows:
            for env in (row.get("involve_envs") or []):
                text: str = str(env).strip()
                if text and text not in seen:
                    seen.add(text)
                    envs.append(text)
        return envs

    @classmethod
    def _summarize_batch_scripts(cls, by_case: Dict[Any, List[Dict[str, Any]]]) -> Tuple[int, int]:
        """
        按脚本维度汇总批次脚本数量与成功数量。

        :param by_case: 已按用例维度分组的批次报告行字典
        :return: (脚本数量, 全部轮次均成功的脚本数量)
        """
        script_count: int = len(by_case)
        success_script_count: int = sum(
            1 for rows in by_case.values()
            if rows and all(cls._is_case_success(row.get("case_state")) for row in rows)
        )
        return script_count, success_script_count

    @classmethod
    def _resolve_batch_execute_result(cls, by_case: Dict[Any, List[Dict[str, Any]]]) -> AutoTestTaskStatus:
        """
        按脚本维度汇总批次结果。

        :param by_case: 已按用例维度分组的批次报告行字典
        :return: 成功(各脚本全部运行均成功)、部分成功(至少一个脚本全部运行成功)或失败
        """
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

    async def search_task_batches(self, batch_in: AutoTestReportBatchSelect) -> Tuple[int, List[AutoTestReportBatchItem]]:
        """
        任务维度聚合查询：按任务标识聚合报告批次并计算执行结果/脚本维度通过率/耗时, 供/search_task_batches接口渲染任务执行历史。

        单段查询控制内存：仅加载聚合所需轻量字段完成全量聚合与分页, 批次行不再内嵌报告明细,
        脚本/报告维度下钻由/search_batch_scripts与/search_script_round_reports接口承担。

        :param batch_in: 批次查询入参
        :return: (批次总数, 当前页批次列表)
        """
        task_code: str = (batch_in.task_code or "").strip()
        if not task_code:
            raise ParameterException(message="参数[task_code]不允许为空")

        state: int = 0 if batch_in.state is None else batch_in.state
        aggregate_rows: List[Dict[str, Any]] = await self.model.filter(
            task_code=task_code,
            state=state,
        ).order_by("case_st_time").values(
            "id", "case_id", "case_state", "case_st_time", "case_ed_time",
            "created_user", "case_elapsed", "report_code", "batch_code", "involve_envs",
        )
        if not aggregate_rows:
            return 0, []

        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in aggregate_rows:
            row["report_id"] = row.pop("id")
            raw_batch_code: Optional[str] = row.get("batch_code")
            batch_code_text: str = (raw_batch_code or "").strip()
            group_key: str = batch_code_text or f"single:{row.get('report_code') or row.get('report_id')}"
            grouped[group_key].append(row)

        batches: List[AutoTestReportBatchItem] = []
        for group_key, batch_rows in grouped.items():
            # 同批行只分组一次, 供执行状态与脚本汇总两个辅助方法复用
            by_case: Dict[Any, List[Dict[str, Any]]] = self._group_rows_by_case(batch_rows)
            script_count: int
            success_script_count: int
            script_count, success_script_count = self._summarize_batch_scripts(by_case)
            execute_users: List[str] = [user for user in (row.get("created_user") for row in batch_rows) if user]
            st_times: List[str] = sorted(st_time for st_time in (row.get("case_st_time") for row in batch_rows) if st_time)
            ed_times: List[str] = [ed_time for ed_time in (row.get("case_ed_time") for row in batch_rows) if ed_time]
            batches.append(
                AutoTestReportBatchItem(
                    batch_code=None if group_key.startswith("single:") else group_key,
                    task_exec_status=self._resolve_batch_execute_result(by_case),
                    task_bind_script=script_count,
                    task_exec_passed=success_script_count,
                    task_exec_failed=script_count - success_script_count,
                    task_pass_rate=round(success_script_count / script_count * 100.0, 2) if script_count else None,
                    created_user=str(execute_users[0]) if execute_users else None,
                    task_st_time=st_times[0] if st_times else None,
                    task_ed_time=max(ed_times) if ed_times else None,
                    task_elapsed=round(sum(self._parse_elapsed_seconds(report_row.get("case_elapsed")) for report_row in batch_rows), 3),
                    involve_envs=self._merge_involve_envs(batch_rows),
                )
            )

        batches.sort(key=lambda item: item.task_st_time or "", reverse=True)
        start: int = (batch_in.page - 1) * batch_in.page_size
        end: int = start + batch_in.page_size
        page_batches: List[AutoTestReportBatchItem] = batches[start:end]

        batch_total: int = len(batches)
        return batch_total, page_batches

    async def search_batch_scripts(self, script_in: AutoTestReportBatchScriptSelect) -> Tuple[int, List[AutoTestReportBatchScriptItem]]:
        """
        批次内脚本维度下钻查询：按批次标识聚合脚本执行信息(一行=一个脚本, 含轮次元数据), 供/search_batch_scripts接口渲染“脚本执行信息”抽屉。

        :param script_in: 脚本维度查询入参
        :return: (脚本总数, 当前页脚本行列表)
        """
        batch_code: str = (script_in.batch_code or "").strip()
        if not batch_code:
            raise ParameterException(message="参数[batch_code]不允许为空")

        state: int = 0 if script_in.state is None else script_in.state
        aggregate_rows: List[Dict[str, Any]] = await self.model.filter(
            batch_code=batch_code,
            state=state,
        ).order_by("case_st_time").values(
            "case_id", "case_state", "case_st_time", "case_ed_time",
            "created_user", "case_elapsed", "involve_envs", "round_no", "dataset_name",
        )
        if not aggregate_rows:
            return 0, []

        grouped: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
        for row in aggregate_rows:
            grouped[row.get("case_id")].append(row)

        script_items: List[AutoTestReportBatchScriptItem] = []
        for case_rows in grouped.values():
            round_datasets: Dict[int, List[str]] = {}
            for row in case_rows:
                round_no_value = row.get("round_no")
                if round_no_value is None:
                    continue
                dataset_names = round_datasets.setdefault(round_no_value, [])
                dataset_name = str(row.get("dataset_name") or "").strip()
                if dataset_name and dataset_name not in dataset_names:
                    dataset_names.append(dataset_name)
            if round_datasets:
                case_execute_count: int = len(round_datasets)
                case_exec_passed: int = sum(
                    1 for round_no_value in round_datasets
                    if all(
                        self._is_case_success(row.get("case_state"))
                        for row in case_rows if row.get("round_no") == round_no_value
                    )
                )
                rounds: List[AutoTestReportScriptRoundItem] = [
                    AutoTestReportScriptRoundItem(round_no=round_no_value, dataset_names=dataset_names)
                    for round_no_value, dataset_names in sorted(round_datasets.items())
                ]
            else:
                # 历史数据无轮次标识, 退化为报告行数口径
                case_execute_count = len(case_rows)
                case_exec_passed = sum(1 for row in case_rows if self._is_case_success(row.get("case_state")))
                rounds = []
            execute_users: List[str] = [user for user in (row.get("created_user") for row in case_rows) if user]
            st_times: List[str] = sorted(st_time for st_time in (row.get("case_st_time") for row in case_rows) if st_time)
            ed_times: List[str] = [ed_time for ed_time in (row.get("case_ed_time") for row in case_rows) if ed_time]
            script_items.append(
                AutoTestReportBatchScriptItem(
                    case_id=case_rows[0].get("case_id"),
                    case_name="",
                    case_execute_count=case_execute_count,
                    case_exec_passed=case_exec_passed,
                    case_exec_failed=case_execute_count - case_exec_passed,
                    case_pass_rate=round(case_exec_passed / case_execute_count * 100.0, 2) if case_execute_count else None,
                    involve_envs=self._merge_involve_envs(case_rows),
                    rounds=rounds,
                    created_user=str(execute_users[0]) if execute_users else None,
                    case_st_time=st_times[0] if st_times else None,
                    case_ed_time=max(ed_times) if ed_times else None,
                    case_elapsed=round(sum(self._parse_elapsed_seconds(row.get("case_elapsed")) for row in case_rows), 3),
                )
            )

        script_items.sort(key=lambda item: item.case_st_time or "", reverse=True)
        start: int = (script_in.page - 1) * script_in.page_size
        end: int = start + script_in.page_size
        page_items: List[AutoTestReportBatchScriptItem] = script_items[start:end]

        page_case_ids: List[int] = [item.case_id for item in page_items if item.case_id is not None]
        case_name_map: Dict[int, str] = {}
        if page_case_ids:
            case_name_map = dict(
                await AutoTestCaseCrud().model.filter(
                    id__in=page_case_ids,
                    state__not=1
                ).values_list("id", "case_name")
            )
        for item in page_items:
            item.case_name = case_name_map.get(item.case_id, "")

        script_total: int = len(script_items)
        return script_total, page_items

    async def search_script_round_reports(self, report_in: AutoTestReportScriptReportSelect) -> Tuple[int, List[Dict[str, Any]]]:
        """
        脚本执行明细分页查询(报告维度)：按批次标识+用例ID+轮次分页返回该轮次内执行报告(一行=一次场景执行), 供/search_script_round_reports接口渲染轮次内明细表格。

        :param report_in: 脚本明细查询入参
        :return: (该轮次报告总数, 当前页报告行列表)
        """
        batch_code: str = (report_in.batch_code or "").strip()
        if not batch_code:
            raise ParameterException(message="参数[batch_code]不允许为空")
        if not report_in.case_id:
            raise ParameterException(message="参数[case_id]不允许为空")
        if not report_in.round_no:
            raise ParameterException(message="参数[round_no]不允许为空")

        state: int = 0 if report_in.state is None else report_in.state
        query: Q = Q(batch_code=batch_code) & Q(case_id=report_in.case_id) & Q(round_no=report_in.round_no) & Q(state=state)
        total: int = await self.model.filter(query).count()
        if not total:
            return 0, []

        instances: List[AutoTestReportModel] = await self.model.filter(query).order_by("case_st_time", "id").offset(
            (report_in.page - 1) * report_in.page_size
        ).limit(report_in.page_size)

        data: List[Dict[str, Any]] = await asyncio.gather(*[
            obj.to_dict(
                exclude_fields={"state", "created_time", "reserve_1", "reserve_2", "reserve_3"},
                replace_fields={"id": "report_id"},
            )
            for obj in instances
        ])
        case_name_map: Dict[int, str] = dict(
            await AutoTestCaseCrud().model.filter(
                id=report_in.case_id,
                state__not=1
            ).values_list("id", "case_name")
        )
        for index, row in enumerate(data):
            row["case_name"] = case_name_map.get(report_in.case_id, "")
            row["step_pass_ratio"] = round(float(row.get("step_pass_ratio") or 0), 2)
            row["dataset_no"] = (report_in.page - 1) * report_in.page_size + index + 1
        return total, data

    async def search_reports(self, search: Q, report_in: AutoTestReportSelect) -> Tuple[int, List[Dict[str, Any]]]:
        """
        执行维度主查询：将多数据源执行(同batch_code)唯一化为一行代表行, 批次行携带has_multiple_dataset与dataset_count, 多数据源批次行的step_pass_ratio为批内累积通过率; 批次明细由search_batch_reports按批次标识下钻。

        三段式查询控制资源: 段1a/1b并发聚合执行维度轻量行 → 内存合并排序分页 → 段2代表行按主键回查全字段。

        :param search: 查询条件(view层组装, 含state过滤, 不含batch_code空值分段)
        :param report_in: 报告查询入参(分页与state)
        :return: (执行维度总数, 当前页报告行列表)
        """
        case_curd: AutoTestCaseCrud = AutoTestCaseCrud()
        # gather返回List[Any], 经中转变量解包以保留两侧轻量行的类型注解
        batch_rep_rows, single_rows = await asyncio.gather(
            self.model.filter(
                search & Q(batch_code__isnull=False) & ~Q(batch_code=""),
            ).annotate(
                rep_id=Max("id"),
                rep_time=Max("case_st_time"),
                rep_count=Count("id"),
                # 批内步骤通过数/步骤总数合计, 供批次行计算累积通过率
                rep_pass_sum=Sum("step_pass_count"),
                rep_total_sum=Sum("step_total"),
            ).group_by("batch_code").values("batch_code", "rep_id", "rep_time", "rep_count", "rep_pass_sum", "rep_total_sum"),
            self.model.filter(search & (Q(batch_code__isnull=True) | Q(batch_code=""))).values("id", "case_st_time", "step_pass_ratio"),
        )
        exec_rows: List[Dict[str, Any]] = [{
            "rep_id": row["rep_id"],
            "rep_time": row["rep_time"],
            "dataset_count": row["rep_count"],
            # 批次累积通过率 = 批内步骤通过数合计 / 步骤总数合计
            "rep_pass_ratio": round(row["rep_pass_sum"] / row["rep_total_sum"] * 100, 2) if row["rep_total_sum"] else None
        } for row in batch_rep_rows] + [{
            "rep_id": row["id"],
            "rep_time": row["case_st_time"],
            "dataset_count": 1,
            # 单报告行累积通过率 = 自身步骤通过率
            "rep_pass_ratio": round(float(row["step_pass_ratio"] or 0), 2)
        } for row in single_rows]
        exec_rows.sort(key=lambda row: (row["rep_time"] or "", row["rep_id"]), reverse=True)
        total: int = len(exec_rows)
        offset: int = (report_in.page - 1) * report_in.page_size
        exec_rows = exec_rows[offset: offset + report_in.page_size]
        rep_ids: List[int] = [row["rep_id"] for row in exec_rows]
        instances: List[AutoTestReportModel] = await self.model.filter(id__in=rep_ids, state=report_in.state)
        instances_map: Dict[int, AutoTestReportModel] = {obj.id: obj for obj in instances}
        exec_rows = [row for row in exec_rows if row["rep_id"] in instances_map]
        ordered_instances: List[AutoTestReportModel] = [instances_map[report_id] for report_id in rep_ids if report_id in instances_map]
        all_case_ids: Set[int] = {obj.case_id for obj in ordered_instances}
        case_name_map: Dict[int, str] = {}
        if all_case_ids:
            case_name_map = dict(
                await case_curd.model.filter(
                    id__in=list(all_case_ids),
                    state__not=1
                ).values_list("id", "case_name")
            )
        data: List[Dict[str, Any]] = await asyncio.gather(*[
            obj.to_dict(
                exclude_fields={"state", "created_time", "reserve_1", "reserve_2", "reserve_3"},
                replace_fields={"id": "report_id"},
            )
            for obj in ordered_instances
        ])
        for row in data:
            row["step_pass_ratio"] = f"{round(float(row.get('step_pass_ratio') or 0), 2)}%"
            row["case_name"] = case_name_map.get(row["case_id"], "")
        for row, report_item in zip(exec_rows, data):
            report_item["has_multiple_dataset"] = bool(report_item.get("batch_code")) and row["dataset_count"] > 1
            report_item["dataset_count"] = row["dataset_count"]
            if report_item["has_multiple_dataset"]:
                # 多数据源批次行: step_pass_ratio覆盖为批内累积通过率(步骤通过数合计/步骤总数合计)
                report_item["step_pass_ratio"] = f"{round(float(row['rep_pass_ratio'] or 0), 2)}%"
        return total, data

    async def search_batch_reports(self, page: int, page_size: int, order: List[str], batch_code: str, state: int) -> Tuple[int, List[Dict]]:
        """
        报告维度下钻查询：按批次标识精确分页返回同批次全部报告(一行=一条报告, 不做批次唯一化), 供/search_batch_reports接口渲染“执行报告”抽屉。

        :param page: 页码
        :param page_size: 每页数量
        :param order: 排序字段列表
        :param batch_code: 批次标识代码(精确等值, 命中batch_code索引)
        :param state: 状态(0:启用, 1:禁用)
        :return: (报告总数, 当前页报告行列表)
        """
        q: Q = Q(batch_code=batch_code) & Q(state=state)
        select_result: Tuple[int, List[AutoTestReportModel]] = await self.select_reports(
            search=q,
            page=page,
            page_size=page_size,
            order=order
        )
        total: int = select_result[0]
        instances: List[AutoTestReportModel] = select_result[1]
        case_ids: List[int] = list({obj.case_id for obj in instances})
        case_name_map: Dict[int, str] = {}
        if case_ids:
            case_name_map = dict(
                await AutoTestCaseCrud().model.filter(
                    id__in=case_ids,
                    state__not=1
                ).values_list("id", "case_name")
            )
        data: List[Dict[str, Any]] = await asyncio.gather(*[
            obj.to_dict(
                exclude_fields={"state", "created_time", "reserve_1", "reserve_2", "reserve_3"},
                replace_fields={"id": "report_id"},
            )
            for obj in instances
        ])
        for row in data:
            row["step_pass_ratio"] = f"{round(float(row.get('step_pass_ratio') or 0), 2)}%"
            row["case_name"] = case_name_map.get(row["case_id"], "")
        return total, data
