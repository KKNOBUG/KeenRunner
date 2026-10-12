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
from tortoise.functions import Count, Max, Min, Sum
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
    AutoTestReportScriptReportSelect,
)
from backend.applications.autotest.services.autotest_case_crud import AutoTestCaseCrud
from backend.applications.autotest.services.autotest_task_crud import AutoTestTaskCrud
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
    def _assemble_batch_item(
            cls,
            batch_code: str,
            task_name: Optional[str],
            script_aggs: List[Dict[str, Any]],
            detail_rows: List[Dict[str, Any]],
            task_case_ids: List[int],
            is_running: bool,
    ) -> AutoTestReportBatchItem:
        """
        把一个批次的脚本汇总行和报告明细行拼成一条批次记录, 即任务执行历史列表中的一行。

        通过/失败数、起止时间来自脚本汇总行; 执行人/涉及环境/总耗时来自报告明细行(需按case_st_time升序传入)。
        绑定脚本数区分口径: 运行中批次取任务当前绑定数(当批落库尚不完整), 历史批次取当批实际落库脚本数
        (任务绑定数随后续编辑漂移, 不能回填历史行)。

        :param batch_code: 批次标识
        :param task_name: 任务名称
        :param script_aggs: 脚本汇总行列表, 每行一个脚本, 含round_total/round_passed/first_case_st_time/last_case_ed_time
        :param detail_rows: 批次内报告行列表(case_st_time升序)
        :param task_case_ids: 任务当前绑定的用例ID列表, 仅运行中批次取其长度为绑定脚本数
        :param is_running: 该批次是否为正在执行的批次
        :return: 批次汇总数据
        """
        report_script_count: int = len(script_aggs)
        success_script_count: int = sum(1 for agg in script_aggs if 0 < agg["round_total"] == agg["round_passed"])
        if 0 < report_script_count == success_script_count:
            exec_status: AutoTestTaskStatus = AutoTestTaskStatus.SUCCESS
        elif success_script_count >= 1:
            exec_status = AutoTestTaskStatus.PARTIAL_SUCCESS
        else:
            exec_status = AutoTestTaskStatus.FAILURE
        st_times: List[str] = [agg["first_case_st_time"] for agg in script_aggs if agg["first_case_st_time"]]
        ed_times: List[str] = [agg["last_case_ed_time"] for agg in script_aggs if agg["last_case_ed_time"]]
        execute_users: List[Any] = [user for user in (row.get("created_user") for row in detail_rows) if user]
        return AutoTestReportBatchItem(
            batch_code=batch_code,
            task_name=task_name,
            task_exec_status=exec_status,
            task_bind_script=len(task_case_ids) if is_running else report_script_count,
            task_exec_passed=success_script_count,
            task_exec_failed=report_script_count - success_script_count,
            task_pass_rate=round(success_script_count / report_script_count * 100.0, 2) if report_script_count else None,
            created_user=str(execute_users[0]) if execute_users else None,
            task_st_time=min(st_times) if st_times else None,
            task_ed_time=max(ed_times) if ed_times else None,
            task_elapsed=round(sum(cls._parse_elapsed_seconds(row.get("case_elapsed")) for row in detail_rows), 3),
            involve_envs=cls._merge_involve_envs(detail_rows),
        )

    async def _acquire_task_fields(self, task_code: str) -> Tuple[Optional[str], List[int], Optional[AutoTestTaskStatus]]:
        """
        点查任务表取任务名称、绑定用例ID和最近一次执行状态, 一次查询供整页批次共用。

        :param task_code: 任务标识代码
        :return: (任务名称, 绑定用例ID列表, 最近一次执行状态)
        """
        task_rows: List[Dict[str, Any]] = await AutoTestTaskCrud().model.filter(
            task_code=task_code,
        ).limit(1).values(
            "task_name", "task_case_ids", "last_execute_state"
        )
        if not task_rows:
            raise NotFoundException(message=f"查询任务信息失败, 记录[code={task_code}]不存在")

        task_name: Optional[str] = task_rows[0].get("task_name")
        task_case_ids: List[int] = task_rows[0].get("task_case_ids") or []
        last_execute_state: Optional[AutoTestTaskStatus] = task_rows[0].get("last_execute_state")
        return task_name, task_case_ids, last_execute_state

    async def search_task_batches(self, batch_in: AutoTestReportBatchSelect) -> Tuple[int, List[AutoTestReportBatchItem]]:
        """
        任务执行历史查询(任务维度): 按task_code把报告聚合成批次列表, 一行代表一次任务执行, 供/search_task_batches接口渲染执行历史。

        查询分三层, 每次只取必要数据, 翻页代价不随该任务历史报告总量增长:
        第1层按batch_code分组取每批次的最早开始时间, 用于批次排序和分页;
        第2、3层只查当前页批次, 分别取脚本维度的汇总(轮次数/成功数/起止时间)和执行人/环境/耗时明细。
        绑定脚本数分口径: 运行中批次取任务当前绑定数, 历史批次取当批实际落库脚本数(任务绑定数随后续编辑漂移);
        任务正在执行时, 最近批次的结束时间留空且状态返回"正在执行",
        等全部绑定脚本执行完落库后自然给出结束时间和最终状态。任务执行链路的报告必然携带batch_code;
        脚本/报告维度的下钻由/search_batch_scripts与/search_script_round_reports接口承担。

        :param batch_in: 批次查询入参
        :return: (批次总数, 当前页批次列表)
        """
        batch_count: int = 0
        batch_statement: List[AutoTestReportBatchItem] = []
        task_code: str = (batch_in.task_code or "").strip()
        if not task_code:
            raise ParameterException(message="参数[task_code]不允许为空")

        # 第1层：按batch_code分组, 每个批次只取最早开始时间这一行, 行数=批次数, 用来排序和分页
        state: int = 0 if batch_in.state is None else batch_in.state
        report_batch_statement: List[Dict[str, Any]] = await self.model.filter(
            task_code=task_code,
            state=state,
        ).annotate(
            first_case_st_time=Min("case_st_time")
        ).group_by("batch_code").values("batch_code", "first_case_st_time")
        if not report_batch_statement:
            return batch_count, batch_statement

        # 点查任务行一次: 任务名称给整页共用, 绑定脚本数和"正在执行"的判定要用后两个字段
        task_name, task_case_ids, last_execute_state = await self._acquire_task_fields(task_code=task_code)

        # 把第1层结果整理成排序条目, 按最早开始时间倒序后内存切页; 没有batch_code的分组不属于任务执行批次, 丢弃
        batch_sorted_statement: List[Dict[str, Any]] = [
            {
                "batch_code": row["batch_code"],
                "first_case_st_time": row.get("first_case_st_time"),
            }
            for row in report_batch_statement if row.get("batch_code")
        ]
        batch_sorted_statement.sort(key=lambda item: item["first_case_st_time"], reverse=True)
        page: int = (batch_in.page - 1) * batch_in.page_size
        page_entries: List[Dict[str, Any]] = batch_sorted_statement[page:page + batch_in.page_size]

        # 任务正在执行时, 报告行是陆续落库的, 最近开始的批次大概率还没跑完, 记下它后面单独修正
        running_batch_code: Optional[str] = None
        if last_execute_state == AutoTestTaskStatus.RUNNING and task_case_ids and batch_sorted_statement:
            running_entry: Dict[str, Any] = max(batch_sorted_statement, key=lambda item: item["first_case_st_time"])
            running_batch_code = running_entry["batch_code"]

        # 下钻只查当前页的批次, 页外的批次不浪费查询
        page_batch_codes: List[str] = [item["batch_code"] for item in page_entries]
        scripts_by_batch: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        details_by_batch: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        if page_batch_codes:
            # 第2层：脚本汇总, 当前页批次内按batch_code+case_id分组, 一行=一个脚本, 轮次总数/成功轮次数/起止时间
            script_rows: List[Dict[str, Any]] = await self.model.filter(
                task_code=task_code,
                state=state,
                batch_code__in=page_batch_codes,
            ).annotate(
                round_total=Count("id"),
                round_passed=Count("id", _filter=Q(case_state=True)),
                first_case_st_time=Min("case_st_time"),
                last_case_ed_time=Max("case_ed_time"),
            ).group_by("batch_code", "case_id").values(
                "batch_code", "case_id",
                "round_total", "round_passed",
                "first_case_st_time", "last_case_ed_time",
            )
            for row in script_rows:
                scripts_by_batch[row["batch_code"]].append(row)

            # 第3层：报告明细, 当前页批次内逐行取执行人/环境/耗时(耗时是字符串只能取回来求和), 按开始时间升序
            detail_rows: List[Dict[str, Any]] = await self.model.filter(
                task_code=task_code,
                state=state,
                batch_code__in=page_batch_codes,
            ).order_by("case_st_time").values(
                "batch_code",
                "case_st_time", "case_elapsed",
                "created_user", "involve_envs",
            )
            for row in detail_rows:
                details_by_batch[row["batch_code"]].append(row)

        # 把当前页批次的汇总和明细拼成最终列表; 运行中的批次结束时间留空、状态改为"正在执行", 避免误报终态
        batches: List[AutoTestReportBatchItem] = []
        for item in page_entries:
            is_running: bool = item["batch_code"] == running_batch_code
            batch: AutoTestReportBatchItem = self._assemble_batch_item(
                batch_code=item["batch_code"],
                task_name=task_name,
                script_aggs=scripts_by_batch.get(item["batch_code"], []),
                detail_rows=details_by_batch.get(item["batch_code"], []),
                task_case_ids=task_case_ids,
                is_running=is_running,
            )
            if is_running:
                batch.task_ed_time = None
                batch.task_exec_status = AutoTestTaskStatus.RUNNING
            batches.append(batch)
        return len(batch_sorted_statement), batches

    async def search_batch_scripts(self, script_in: AutoTestReportBatchScriptSelect) -> Tuple[int, List[AutoTestReportBatchScriptItem]]:
        """
        批次内脚本维度下钻查询：按批次标识聚合脚本执行信息(一行=一个脚本), 供/search_batch_scripts接口渲染“脚本执行信息”抽屉。
        脚本行按最早开始时间升序排列, 自上而下即执行先后顺序: 串行模式等价于任务绑定顺序, 并行模式呈现脚本被调度的先后。
        轮次列表由前端按case_execute_count构建, 轮次内数据源名称由/search_script_round_reports按全轮次计算返回。

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
            # 单次遍历完成轮次分组与数据源名称收集, 避免逐轮次重扫报告行
            round_rows: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
            dataset_names: Set[str] = set()
            for row in case_rows:
                round_no_value = row.get("round_no")
                if round_no_value is not None:
                    round_rows[round_no_value].append(row)
                dataset_name_value = str(row.get("dataset_name") or "").strip()
                if dataset_name_value:
                    dataset_names.add(dataset_name_value)
            if round_rows:
                # 轮次口径: 执行次数=round_no去重数, 一轮内多数据源产生多条报告仅计1次; 成功数=全部报告成功的轮次数
                case_execute_count: int = len(round_rows)
                case_exec_passed: int = sum(
                    1 for rows in round_rows.values()
                    if all(self._is_case_success(row.get("case_state")) for row in rows)
                )
            else:
                # 历史数据无轮次标识, 退化为报告行数口径
                case_execute_count = len(case_rows)
                case_exec_passed = sum(1 for row in case_rows if self._is_case_success(row.get("case_state")))
            if case_execute_count and case_exec_passed == case_execute_count:
                case_exec_status: AutoTestTaskStatus = AutoTestTaskStatus.SUCCESS
            elif case_exec_passed >= 1:
                case_exec_status = AutoTestTaskStatus.PARTIAL_SUCCESS
            else:
                case_exec_status = AutoTestTaskStatus.FAILURE
            execute_users: List[str] = [user for user in (row.get("created_user") for row in case_rows) if user]
            st_times: List[str] = sorted(st_time for st_time in (row.get("case_st_time") for row in case_rows) if st_time)
            ed_times: List[str] = [ed_time for ed_time in (row.get("case_ed_time") for row in case_rows) if ed_time]
            script_items.append(
                AutoTestReportBatchScriptItem(
                    case_id=case_rows[0].get("case_id"),
                    case_name="",
                    case_exec_status=case_exec_status,
                    case_execute_count=case_execute_count,
                    case_exec_passed=case_exec_passed,
                    case_exec_failed=case_execute_count - case_exec_passed,
                    case_pass_rate=round(case_exec_passed / case_execute_count * 100.0, 2) if case_execute_count else None,
                    # 语义对齐/search_reports的has_multiple_dataset: 多数据源判定=数据源名称去重数>1
                    has_multiple_dataset=len(dataset_names) > 1,
                    involve_envs=self._merge_involve_envs(case_rows),
                    created_user=str(execute_users[0]) if execute_users else None,
                    case_st_time=st_times[0] if st_times else None,
                    case_ed_time=max(ed_times) if ed_times else None,
                    case_elapsed=round(sum(self._parse_elapsed_seconds(row.get("case_elapsed")) for row in case_rows), 3),
                )
            )

        # 按最早开始时间升序, 自上而下即执行先后; 空开始时间的脚本垫底, 不参与时序比较
        script_items.sort(key=lambda item: (item.case_st_time is None, item.case_st_time or ""))
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
        脚本执行明细分页查询(报告维度)：按批次标识+用例ID分页返回执行报告(一行记录代表一次场景执行), 供/search_script_round_reports接口渲染明细表格。

        双形态：传入round_no时按轮次过滤(轮次内明细)；缺省时返回全部轮次明细(执行次数模式无数据源场景),
        两种形态统一按执行时间升序排列。

        :param report_in: 脚本明细查询入参
        :return: (报告总数, 当前页报告行列表)
        """
        batch_code: str = (report_in.batch_code or "").strip()
        if not batch_code:
            raise ParameterException(message="参数[batch_code]不允许为空")
        if not report_in.case_id:
            raise ParameterException(message="参数[case_id]不允许为空")

        state: int = 0 if report_in.state is None else report_in.state
        query: Q = Q(batch_code=batch_code) & Q(case_id=report_in.case_id) & Q(state=state)
        if report_in.round_no:
            # 轮次形态：命中复合索引(batch_code, case_id, round_no)全列
            query &= Q(round_no=report_in.round_no)
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
        # 同一批次必属同一任务, 任务名称用一次唯一索引点查取回, 页内所有报告行共用
        task_code_of_batch: Optional[str] = data[0].get("task_code") if data else None
        task_name: Optional[str] = None
        if task_code_of_batch:
            task_rows: List[str] = await AutoTestTaskCrud().model.filter(
                task_code=task_code_of_batch,
            ).limit(1).values_list("task_name", flat=True)
            task_name = task_rows[0] if task_rows else None
        for row in data:
            row["task_name"] = task_name
            row["case_name"] = case_name_map.get(report_in.case_id, "")
            row["step_pass_ratio"] = round(float(row.get("step_pass_ratio") or 0), 2)
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

    async def search_batch_reports(
            self,
            page: int,
            page_size: int,
            order: List[str],
            batch_code: str,
            state: int,
            case_id: Optional[int] = None,
    ) -> Tuple[int, List[Dict]]:
        """
        报告维度下钻查询：按批次标识精确分页返回同批次全部报告(一行=一条报告, 不做批次唯一化), 供/search_batch_reports接口渲染“执行报告”抽屉。

        :param page: 页码
        :param page_size: 每页数量
        :param order: 排序字段列表
        :param batch_code: 批次标识代码(精确等值, 命中batch_code索引)
        :param state: 状态(0:启用, 1:禁用)
        :param case_id: 用例ID(可选, 传入时按用例过滤, 与batch_code命中复合索引(batch_code, case_id, round_no)左前缀)
        :return: (报告总数, 当前页报告行列表)
        """
        q: Q = Q(batch_code=batch_code) & Q(state=state)
        if case_id:
            q &= Q(case_id=case_id)
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
