# -*- coding: utf-8 -*-
"""
压测数据作业服务: 执行下发前置业务与Celery执行链编排。

作业执行复用 autotest 单用例执行链(execute_single_case, 含报告/明细落库与
DB/Redis/HTTP/断言全部能力), 不新造执行器: 顺序跑 loop_times 轮, prepare 作业
每轮从执行明细提取 extract_fields 组一行数据, 全部轮次成功后把提取行转换成
数据场景(列名按归属接口报文解析为字段路径写入 head/body 分区)整体回写数据集
(source_type=job, 归属接口由 bind_api_id 派生), 任一轮失败即中止不产出半成品。
verify/cleanup 跑完轮次即成功(报告与明细即产出, 独立追溯)。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_job_service.py
@DateTime: 2026/9/17 17:50
"""
import traceback
from typing import Any, Dict, List, Optional, Tuple

from backend.applications.autotest.services.autotest_case_crud import AutoTestCaseCrud
from backend.applications.autotest.services.autotest_data_source_parser import (
    AXIS_VERTICAL,
    cell_text_value,
)
from backend.applications.autotest.services.autotest_data_source_service import collect_step_report_original
from backend.applications.autotest.services.autotest_step_crud import AutoTestStepCrud
from backend.applications.performance.models.perf_api_model import PerfApiModel
from backend.applications.performance.models.perf_dataset_model import PerfDatasetModel
from backend.applications.performance.models.perf_job_model import PerfJobModel
from backend.applications.performance.schemas.perf_dataset_schema import PerfDatasetCreate
from backend.applications.performance.schemas.perf_job_schema import PerfJobLocate
from backend.applications.performance.services.perf_dataset_crud import PerfDatasetCrud
from backend.applications.performance.services.perf_job_crud import PerfJobCrud
from backend.configure import LOGGER
from backend.core.exceptions import ParameterException
from backend.enums import AutoTestReportType, PerfDatasetSource, PerfJobStatus, PerfJobType
from backend.services.ctx import CTX_USERNAME

# 提取未命中哨兵: 提取值可能为None/空串/0, 不能用None判定「未命中」
_MISSING = object()


class PerfJobService:
    """数据作业服务: 下发闸门与执行链编排。"""

    @staticmethod
    async def run_job(job_in: PerfJobLocate) -> PerfJobModel:
        """
        作业执行下发前置业务: 定位、执行中闸门、原子置排队(apply_async由视图层编排)。

        执行期引用校验提前到下发时: 让用户点击时得到确定反馈, 而非排队后才发现
        脚本用例已被删除。

        :param job_in: 作业定位入参(job_id/job_code二选一)
        :return: 已置排队状态的作业实例
        """
        crud = PerfJobCrud()
        if job_in.job_id:
            job: PerfJobModel = await crud.get_by_id(job_id=job_in.job_id, on_error=True, state__not=1)
        else:
            job = await crud.get_by_code(job_code=job_in.job_code, on_error=True, state__not=1)
        if job.status == PerfJobStatus.RUNNING:
            error_message: str = (
                f"执行压测数据作业失败, 作业[{job.job_name}]正在执行中, 请等待执行完成后再下发"
            )
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        await PerfJobCrud.resolve_quote_case(quote_case_id=job.quote_case_id)

        # 原子置排队: 排除执行锁定态, 与并发点击/执行链状态回写竞争互斥
        if not await crud.mark_pending(job_id=job.id):
            error_message = (
                f"执行压测数据作业失败, 作业[{job.job_name}]正在执行中, 请等待执行完成后再下发"
            )
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        LOGGER.info(f"压测数据作业已置排队: job_id={job.id}, job_code={job.job_code}")
        return await crud.get_by_id(job_id=job.id, on_error=True)

    @staticmethod
    async def execute_job(job_code: str, celery_id: Optional[str],
                          created_user: Optional[str]) -> Dict[str, Any]:
        """
        数据作业执行链(Celery impl): 抢占置running → 顺序跑N轮功能执行 → 提取回写 → 终态。

        任一轮功能执行失败或(prepare)提取失败即中止: 造数要求数据完整, 部分行产出
        会造成场景消费期取值歧义, 已执行轮次不回写。失败原因与最近报告回填作业表。

        :param job_code: 数据作业标识代码
        :param celery_id: Celery任务ID
        :param created_user: 触发人账号(worker无HTTP上下文, 用于执行归因)
        :return: 执行结果字典, 形如:
            {"job_code": "xx", "job_type": "prepare", "status": "success", "skipped": False,
             "loop_times": 10, "result_rows": 10, "result_dataset_id": 1, "report_code": "xx"}
        """
        crud = PerfJobCrud()
        job: PerfJobModel = await crud.get_by_code(job_code=job_code, on_error=True, state__not=1)
        # 抢占闸门: 仅pending可流转, 消息重投/并发消费时直接跳过(状态已被其他消费接管)
        if not await crud.claim_running(job_id=job.id, celery_id=celery_id):
            LOGGER.warning(
                f"数据作业[{job.job_code}]当前状态为[{job.status}], 跳过本次消费(消息重投或并发下发)"
            )
            return {
                "job_code": job_code, "job_type": job.job_type.value if job.job_type else None,
                "status": job.status.value if job.status else None,
                "skipped": True, "loop_times": job.loop_times, "result_rows": job.result_rows,
                "result_dataset_id": job.result_dataset_id, "report_code": job.report_code,
            }
        # Worker进程无HTTP鉴权上下文, 用提交任务时传入的用户账号埋点
        if created_user:
            CTX_USERNAME.set(str(created_user).strip())

        last_report_code: Optional[str] = None
        try:
            # 执行期再校验用例存在(作业创建后可能被删除/禁用), 失败由下方兜底置failed
            await AutoTestCaseCrud().get_by_id(case_id=job.quote_case_id, on_error=True, state__not=1)

            step_crud = AutoTestStepCrud()
            rows: List[Dict[str, Any]] = []
            for round_no in range(1, (job.loop_times or 1) + 1):
                result: Dict[str, Any] = await step_crud.execute_single_case(
                    case_id=job.quote_case_id,
                    report_type=AutoTestReportType.ASYNC_EXEC,
                    batch_code=job.job_code,
                    dataset_name=job.dataset_name,
                    round_no=round_no,
                )
                last_report_code = result.get("report_code") or last_report_code
                if not result.get("success"):
                    return await _abort_job(
                        job=job, round_no=round_no,
                        reason=f"功能执行失败(步骤通过率{result.get('passed_ratio')}%)",
                        report_code=last_report_code,
                    )
                if job.job_type == PerfJobType.PREPARE:
                    row: Optional[Dict[str, Any]] = await _extract_row(
                        report_code=result.get("report_code"), fields=list(job.extract_fields or []),
                    )
                    if row is None:
                        return await _abort_job(
                            job=job, round_no=round_no,
                            reason=f"提取列{list(job.extract_fields or [])}未在执行明细与会话变量中全部命中",
                            report_code=last_report_code,
                        )
                    rows.append(row)
                LOGGER.info(
                    f"数据作业[{job.job_code}]第{round_no}/{job.loop_times}轮执行完成, "
                    f"report_code={result.get('report_code')}"
                )

            result_dataset_id: Optional[int] = None
            result_rows: int = 0
            if job.job_type == PerfJobType.PREPARE:
                dataset: PerfDatasetModel = await _write_back_dataset(
                    job=job, rows=rows, created_user=created_user,
                )
                result_dataset_id = dataset.id
                result_rows = len(rows)
            await crud.mark_success(
                job_id=job.id, result_dataset_id=result_dataset_id,
                result_rows=result_rows, report_code=last_report_code,
            )
            LOGGER.info(
                f"数据作业[{job.job_code}]执行成功: loop_times={job.loop_times}, "
                f"result_rows={result_rows}, result_dataset_id={result_dataset_id}"
            )
            return {
                "job_code": job_code, "job_type": job.job_type.value if job.job_type else None,
                "status": PerfJobStatus.SUCCESS.value, "skipped": False,
                "loop_times": job.loop_times, "result_rows": result_rows,
                "result_dataset_id": result_dataset_id, "report_code": last_report_code,
            }
        except Exception as e:
            # 执行链全量兜底: 任何残余异常(引用资产断链/DB异常)置failed, 不卡running
            error_message: str = f"数据作业执行异常: {type(e).__name__}: {e}"
            LOGGER.error(f"数据作业[{job.job_code}]执行失败: {error_message}\n{traceback.format_exc()}")
            try:
                await crud.mark_failed(job_id=job.id, error_message=error_message, report_code=last_report_code)
            except Exception as fallback_error:
                LOGGER.error(
                    f"数据作业[{job.job_code}]兜底状态回填失败: {fallback_error}\n{traceback.format_exc()}"
                )
            raise


async def _abort_job(*, job: PerfJobModel, round_no: int, reason: str,
                     report_code: Optional[str]) -> Dict[str, Any]:
    """
    中止作业并置失败终态(轮次级fail-fast, 不产出半成品数据)。

    :param job: 作业实例
    :param round_no: 失败轮次(从1开始)
    :param reason: 失败原因描述
    :param report_code: 失败轮次的功能执行报告标识代码
    :return: 执行结果字典(status=failed)
    """
    error_message: str = f"第{round_no}/{job.loop_times}轮作业中止: {reason}"
    LOGGER.error(f"数据作业[{job.job_code}]执行失败: {error_message}")
    await PerfJobCrud().mark_failed(job_id=job.id, error_message=error_message, report_code=report_code)
    return {
        "job_code": job.job_code, "job_type": job.job_type.value if job.job_type else None,
        "status": PerfJobStatus.FAILED.value, "skipped": False,
        "loop_times": job.loop_times, "result_rows": 0,
        "result_dataset_id": None, "report_code": report_code,
    }


async def _extract_row(*, report_code: Optional[str], fields: List[str]) -> Optional[Dict[str, Any]]:
    """
    从一轮功能执行的明细提取数据行。

    提取协议: 优先取提取快照(extract_variables)中同名且成功的最后一次取值,
    未命中时回退到最后一条明细的会话变量终态(session_variables按key兜底,
    兜底用户脚本直接写会话变量而未声明提取器的写法); 任一列未命中返回None,
    由调用方按轮次fail-fast(造数要求数据完整)。

    :param report_code: 本轮功能执行报告标识代码
    :param fields: 提取列名列表
    :return: 列名到取值的字典(全列命中)或None(存在未命中列)
    """
    # 跨模块引用走函数内导入(对齐本模块既有模式, 避免模块加载环)
    from backend.applications.autotest.models.autotest_detail_model import AutoTestDetailModel

    if not report_code:
        return None
    details: List[Dict[str, Any]] = await AutoTestDetailModel.filter(
        report_code=report_code,
    ).order_by("id").values("extract_variables", "session_variables")
    if not details:
        return None

    row: Dict[str, Any] = {}
    for field in fields:
        value: Any = _MISSING
        for detail in details:
            for item in (detail.get("extract_variables") or []):
                if item.get("name") == field and item.get("success") and "extract_value" in item:
                    value = item.get("extract_value")
        if value is _MISSING:
            for item in (details[-1].get("session_variables") or []):
                if item.get("key") == field:
                    value = item.get("value")
                    break
        if value is _MISSING:
            return None
        row[field] = value
    return row


def _match_path_tail(paths: List[str], field: str) -> Optional[str]:
    """
    按路径末段匹配提取列名, 命中返回完整路径。

    JSONPath与XPath统一取尾段(属性路径剥离@), 与提取变量名直接对齐报文字段名;
    大小写敏感口径与占位符渲染一致。

    :param paths: 报文字段路径列表(如$.Token、$.data.id、./Child/@attr)
    :param field: 提取列名
    :return: 命中的完整路径或None
    """
    for path in paths:
        tail: str = str(path or "").rstrip("/").split("/")[-1].split(".")[-1].lstrip("@")
        if tail == field:
            return path
    return None


def _resolve_field_paths(api: PerfApiModel, fields: List[str]) -> Dict[str, Tuple[str, str]]:
    """
    提取列名 → 参数化字段路径的分区归属解析。

    以归属接口报文现存的字段路径为准(路径规则与功能数据源同步协议一致: 请求头$.Key、
    键值型$.Key、JSON叶子JSONPath、XML叶子XPath), 列名按路径末段匹配, 先 head 后 body;
    未命中列由调用方 fail-fast(造数产出无处写入, 静默丢弃会造成场景消费期取值歧义)。

    :param api: 产出归属压测接口实例
    :param fields: 提取列名列表
    :return: {列名: (分区, 完整路径)}, 分区取值 head|body
    """
    originals: Dict[str, Dict[str, str]] = collect_step_report_original(api)
    section_paths: Dict[str, List[str]] = {
        "head": list(originals.get("HEAD") or {}),
        "body": list(originals.get("BODY") or {}),
    }
    resolved: Dict[str, Tuple[str, str]] = {}
    for field in fields:
        for section in ("head", "body"):
            path: Optional[str] = _match_path_tail(section_paths[section], field)
            if path:
                resolved[field] = (section, path)
                break
    return resolved


def _build_job_dataframe(api: PerfApiModel, fields: List[str],
                         rows: List[Dict[str, Any]]) -> List[List[Any]]:
    """
    造数提取行 → 数据源垂直矩阵(每轮一个场景)。

    列名经归属接口报文解析为字段路径后按分区落位(值经cell_text_value文本化,
    与数据源dataset字符串化存储协议对齐, 类型语义由注入侧按报文原字段适配);
    任一列未命中报文路径即中止造数。

    :param api: 产出归属压测接口实例
    :param fields: 提取列名列表(作业声明顺序)
    :param rows: 提取行数据(每轮一行, 列名→取值)
    :return: 垂直方向二维矩阵(首行场景名, 首列分区标记/字段路径)
    :raises ParameterException: 存在无法归属到接口报文字段的提取列
    """
    resolved: Dict[str, Tuple[str, str]] = _resolve_field_paths(api, fields)
    missing_fields: List[str] = [field for field in fields if field not in resolved]
    if missing_fields:
        error_message: str = (
            f"数据作业产出回写失败, 提取列{missing_fields}未在归属压测接口"
            f"[{api.api_name}]的报文字段中命中, 无法参数化"
        )
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)

    # 垂直矩阵: 首行场景名, HEAD/BODY分区标记行+字段路径行(与autotest空白场景模板同构)
    scene_names: List[str] = [f"第{no}轮" for no in range(1, len(rows) + 1)]
    matrix: List[List[Any]] = [["", *scene_names]]
    for section in ("head", "body"):
        matrix.append([section.upper(), *[""] * len(scene_names)])
        for field in fields:
            target_section, path = resolved[field]
            if target_section != section:
                continue
            matrix.append([path, *(cell_text_value(row.get(field)) for row in rows)])
    return matrix


async def _write_back_dataset(*, job: PerfJobModel, rows: List[Dict[str, Any]],
                              created_user: Optional[str]) -> PerfDatasetModel:
    """
    prepare作业产出回写数据集(source_type=job, 归属接口由bind_api_id派生)。

    产出协议与数据集矩阵协议对齐: 每轮提取行转换为一个场景, 列名按归属接口
    报文解析为字段路径写入 head/body 分区, 落库经数据集CRUD同一解析链路
    (apply_dataframe_payload)派生四分区。
    同名数据集恢复覆盖(create_perf_dataset既有语义), 重跑作业即刷新产出;
    归属接口保证数据集挂到正确应用并随归属链被场景消费。

    :param job: prepare类型作业实例
    :param rows: 提取行数据(每轮一行)
    :param created_user: 触发人账号
    :return: 创建或恢复后的数据集实例
    """
    api = await PerfJobCrud.resolve_bind_api(bind_api_id=job.bind_api_id)
    if api is None:
        # schema已强制prepare必填归属接口, 此处防御存量脏数据
        error_message: str = (
            f"数据作业[{job.job_code}]缺少产出归属压测接口, 无法回写数据集"
        )
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)

    ds_in = PerfDatasetCreate(
        ds_name=job.job_name,
        ds_desc=f"数据作业[{job.job_code}]产出, 执行{job.loop_times}轮, 每轮一个场景",
        bind_api_id=api.id,
        dataframe=_build_job_dataframe(api=api, fields=list(job.extract_fields or []), rows=rows),
        axis=AXIS_VERTICAL,
        ds_source=PerfDatasetSource.JOB,
        created_user=created_user,
    )
    dataset: PerfDatasetModel = await PerfDatasetCrud().create_perf_dataset(ds_in=ds_in)
    # 造数溯源列收敛在数据集CRUD窄方法回填, 不在执行链直写模型
    await PerfDatasetCrud().mark_job_trace(ds_id=dataset.id, job_id=job.id, job_code=job.job_code)
    LOGGER.info(
        f"数据作业[{job.job_code}]产出已回写数据集: ds_id={dataset.id}, "
        f"ds_code={dataset.ds_code}, rows={len(rows)}"
    )
    return dataset
