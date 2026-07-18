# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : celery_worker
@DateTime: 2026/1/27 16:25

=============================================================================
【原理】Celery 中跑 async + Tortoise 时的 "attached to a different loop" 与执行顺序
=============================================================================

一、问题根因
-----------
Celery 的 worker 主线程是同步的，async 任务通过 AsyncEventLoopContextIOPool 投递到「池线程」的
一个长期存活的 event loop 里执行。Tortoise/aiomysql 在初始化时会创建连接池，池内部的 Future（如
Pool._wakeup）会绑定到「调用 Tortoise.init() 时所在线程的 get_running_loop() / get_event_loop()」。
若「init 时绑定的 loop」和「执行 _create_task_record / 业务任务时所在的 loop」不是同一个，在
release 连接时就会报：Task got Future (Pool._wakeup) attached to a different loop。

导致不一致的典型情况：
  - 两次 run()：先 run(init_tortoise_orm())，再 run(_create_task_record(...))。两次虽然都进池，
    但若池线程内未对当前线程 set_event_loop，或 init 与 create_record 在不同「运行」中完成，
    aiomysql 池可能绑到错误的 loop。
  - prefork：子进程继承了父进程的池单例和 _tortoise_orm_initialized，但池的 loop_runner 线程
    不会在子进程中存在，导致子进程里用的池/loop 状态错乱。

二、当前机制与执行顺序
---------------------
1. worker_process_init（prefork 子进程刚启动）
   → 清空 _async_event_loop_pool、AsyncEventLoopContextIOPool.singleton、_tortoise_orm_initialized，
   保证子进程第一次跑任务时自己建池、自己 init Tortoise。

2. 任务开始：task_prerun (receiver_task_pre_run)
   - 扫描任务 (scan_and_dispatch_autotest_tasks)：只调 ensure_tortoise_orm_initialized()
     （一次 run(init_tortoise_orm())），不写执行记录。
   - 非扫描任务（如 run_autotest_task）：只调一次
     get_async_event_loop_pool().run(_ensure_tortoise_then_create_task_record(...))。
     该协程内顺序执行：await init_tortoise_orm() → await _create_task_record(...)。
     这样 Tortoise 的 init 与写记录在「同一次 run、同一个协程、同一个 loop」内完成，从根上避免
     连接池与使用方 loop 不一致。

3. 任务体执行：ContextTask.__call__
   - 主线程里 ensure_tortoise_orm_initialized()（若前面未 init 则补一次）。
   - 若 self.run 是 async：get_async_event_loop_pool().run(self.run(*args, **kwargs))，在池里跑。
   - 若 self.run 是 sync（如 run_autotest_task）：直接 self.run(...)，内部再 run_async(业务协程)。

4. 任务结束：on_success / on_failure
   → handel_task_record → get_async_event_loop_pool().run(_update_task_record_on_end(...))，在池里更新记录。

三、要点小结
-----------
- 所有涉及 Tortoise 的 async 逻辑（init、写记录、业务 _run_autotest_task_impl）都必须在「池的
  同一个 event loop」里执行；通过「单次 run 内先 init 再写记录」和 prefork 后重置状态保证这一点。
- 池单例 + 惰性创建：避免 Web 进程 import 时建池；子进程通过 worker_process_init 清空后各自建池。
"""
import asyncio
import logging
import traceback
from abc import ABC
from datetime import datetime
from typing import Dict, Any, Optional

from celery import Celery
from celery import Task
from celery._state import _task_stack
from celery.signals import setup_logging, task_prerun, worker_process_init
from celery.worker.request import Request

from backend.common import AsyncEventLoopContextIOPool
from backend.common.request_context import (
    celery_dispatch_trace_headers,
    enter_celery_span,
    get_span_id,
    _extract_celery_trace_fields,
)
from backend.configure import LOGGER, CELERY_CONFIG
from backend.configure.logging_config import InterceptHandler
from .celery_base import (
    ensure_tortoise_orm_initialized,
    init_tortoise_orm,
    reset_tortoise_orm_state,
    LOCAL_CONTEXT_VAR,
)

_async_event_loop_pool = None
# 扫描任务不写执行记录、不走终态更新
_SCAN_TASK_NAME = (
    "backend.celery_scheduler.tasks.task_autotest_case.scan_and_dispatch_autotest_tasks"
)


@worker_process_init.connect
def _reset_async_pool_and_tortoise_after_fork(**kwargs):
    """
    prefork 子进程初始化：清空事件循环池与 Tortoise 状态。
    子进程 fork 后只继承父进程内存，池的 loop_runner 线程不会在子进程中存在；若沿用父进程的
    池单例和 _tortoise_orm_initialized，子进程内跑任务时会用「不存在的线程/错误的 loop」，
    导致 "attached to a different loop"。清空后子进程首次任务会重新建池、重新 init Tortoise。
    """
    global _async_event_loop_pool
    _async_event_loop_pool = None
    AsyncEventLoopContextIOPool.reset_process_state()
    reset_tortoise_orm_state()
    # prefork 子进程继承父进程 Loguru 文件句柄，需重建 Sink 以免多进程共写/轮转失败
    from backend.configure.logging_config import loguru_logging

    loguru_logging()
    LOGGER.debug("【Krun-Celery-Worker】worker_process_init: 已重置异步池、Tortoise 与日志 Sink")


def get_async_event_loop_pool():
    """
    惰性获取异步事件循环池，仅在 Worker 执行任务时创建。
    避免 Web 进程 import celery_worker 时创建事件循环；prefork 子进程内由 worker_process_init
    清空后，每个子进程在首次执行任务时再创建自己的池。
    """
    global _async_event_loop_pool
    if _async_event_loop_pool is None:
        _async_event_loop_pool = AsyncEventLoopContextIOPool()
    return _async_event_loop_pool


async def _ensure_tortoise_then_create_task_record(
        celery_id: str,
        celery_node: str,
        celery_trace_id: str,
        task_id: str,
        celery_task_name: str,
        trigger_type=None,
        report_type=None,
):
    """同一协程内先 init Tortoise 再写执行记录，保证同 loop。"""
    await init_tortoise_orm()
    await _create_task_record(
        celery_id=celery_id,
        celery_node=celery_node,
        celery_trace_id=celery_trace_id,
        task_id=task_id,
        celery_task_name=celery_task_name,
        trigger_type=trigger_type,
        report_type=report_type,
    )


def _resolve_trigger_and_report(task: Task):
    """从 Celery request 解析触发来源与报告类型。"""
    from backend.enums import AutoTestReportType, AutoTestTaskTriggerType

    req_kwargs = getattr(task.request, "kwargs", None) or {}
    report_type = req_kwargs.get("report_type")
    if report_type is None:
        args = getattr(task.request, "args", None) or ()
        if len(args) >= 2:
            report_type = args[1]
    report_val = getattr(report_type, "value", report_type)
    is_manual = (
        report_type == AutoTestReportType.ASYNC_EXEC
        or (isinstance(report_val, str) and report_val.strip() == AutoTestReportType.ASYNC_EXEC.value)
    )
    if is_manual:
        return AutoTestTaskTriggerType.MANUAL, AutoTestReportType.ASYNC_EXEC
    return AutoTestTaskTriggerType.SCHEDULE, AutoTestReportType.SCHEDULE_EXEC


def _to_jsonable(value: Any) -> Any:
    """将任意对象转为可 JSON 落库结构（保留完整内容）。"""
    import json

    if value is None:
        return None
    if isinstance(value, (dict, list, str, int, float, bool)):
        try:
            return json.loads(json.dumps(value, ensure_ascii=False, default=str))
        except Exception:
            return {"raw": str(value)}
    return {"raw": str(value)}


async def _create_task_record(
        celery_id: str,
        celery_node: str,
        celery_trace_id: str,
        task_id: str,
        celery_task_name: str,
        trigger_type=None,
        report_type=None,
):
    """创建任务执行观测记录（RUNNING），并写入完整执行入参快照。"""
    from backend.applications.aotutest.models.autotest_model import AutoTestApiTaskInfo
    from backend.applications.aotutest.services.autotest_record_crud import AutoTestApiTaskRecordCrud
    from backend.enums import AutoTestTaskStatus

    report_val = getattr(report_type, "value", report_type)
    data: Dict[str, Any] = {
        "task_id": task_id,
        "celery_id": celery_id,
        "celery_node": celery_node,
        "celery_trace_id": celery_trace_id,
        "celery_status": AutoTestTaskStatus.RUNNING,
        "celery_start_time": datetime.now(),
        "trigger_type": trigger_type,
        "report_type": report_type,
    }
    if task_id is not None and celery_task_name and "run_autotest_task" in celery_task_name:
        task_instance = await AutoTestApiTaskInfo.filter(id=task_id).first()
        if task_instance:
            kwargs = getattr(task_instance, "task_kwargs", None) or {}
            if not isinstance(kwargs, dict):
                kwargs = {}
            case_ids = kwargs.get("case_ids") if isinstance(kwargs.get("case_ids"), list) else []
            cases_cfg = getattr(task_instance, "cases_execute_config", None) or {}
            if not cases_cfg and isinstance(kwargs, dict):
                cases_cfg = kwargs.get("cases_execute_config") or {}
            periodic = getattr(task_instance, "task_periodic_expr", None)
            data.update({
                "task_code": getattr(task_instance, "task_code", None),
                "task_name": getattr(task_instance, "task_name", None),
                "task_type": getattr(task_instance, "task_type", None),
                "task_project": getattr(task_instance, "task_project", None),
                "case_ids": case_ids,
                "exec_snapshot": _to_jsonable({
                    "report_type": report_val,
                    "task_kwargs": {
                        "case_ids": case_ids,
                        **(
                            {"initial_variables": kwargs["initial_variables"]}
                            if isinstance(kwargs.get("initial_variables"), list)
                            else {}
                        ),
                    },
                    "cases_execute_config": cases_cfg if isinstance(cases_cfg, dict) else {},
                    "task_crontabs_expr": getattr(task_instance, "task_crontabs_expr", None),
                    "task_periodic_expr": getattr(periodic, "value", periodic),
                    "task_enabled": getattr(task_instance, "task_enabled", None),
                }),
            })
    await AutoTestApiTaskRecordCrud().create_record(data)
    LOGGER.info(
        f"【Krun-Celery-Worker】【span_id={get_span_id()}】创建执行记录成功, celery_id={celery_id}"
    )


async def _update_task_record_on_end(
        celery_id: str,
        success: bool,
        task_summary: Any = None,
        traceback_str: str = None,
        batch_code: str = None,
):
    """将执行记录更新为终态；task_summary 保存完整响应对象。更新前先确保 Tortoise 可用。"""
    if not celery_id:
        return
    from backend.applications.aotutest.services.autotest_record_crud import AutoTestApiTaskRecordCrud
    from backend.enums import AutoTestTaskStatus

    # 长任务后连接可能失效；与 create 一样先 init/探活，避免终态写库失败导致永远「正在执行」
    await init_tortoise_orm()

    now = datetime.now()
    status_enum = AutoTestTaskStatus.SUCCESS if success else AutoTestTaskStatus.FAILURE
    summary_obj = _to_jsonable(task_summary)
    error_text = None
    if not success:
        if isinstance(task_summary, dict) and task_summary.get("error"):
            error_text = str(task_summary.get("error"))
        error_text = traceback_str or error_text or "执行失败"
    data = {
        "celery_status": status_enum,
        "celery_end_time": now,
        "task_summary": summary_obj,
        "task_error": error_text,
    }
    if batch_code:
        data["batch_code"] = batch_code
    record_crud = AutoTestApiTaskRecordCrud()
    record = await record_crud.get_by_celery_id(celery_id=celery_id)
    if not record:
        LOGGER.error(
            f"【Krun-Celery-Worker】【span_id={get_span_id()}】更新执行记录失败, 未找到[celery_id={celery_id}]记录"
        )
        return
    if record.celery_start_time:
        start = record.celery_start_time
        if getattr(start, "tzinfo", None) is not None:
            start = start.replace(tzinfo=None)
        delta = now - start
        data["celery_duration"] = f"{delta.total_seconds():.2f}s"
    await record_crud.update_record_by_celery_id(celery_id=celery_id, data=data)
    LOGGER.info(
        f"【Krun-Celery-Worker】【span_id={get_span_id()}】更新执行记录成功, "
        f"celery_id={celery_id}, status={status_enum}"
    )


@task_prerun.connect
def receiver_task_pre_run(task: Task, *args, **kwargs):
    """
    任务执行前：按任务类型初始化 Tortoise、写入执行记录（RUNNING）。
    扫描任务不写记录；非扫描任务通过「单次 run(_ensure_tortoise_then_create_task_record)」保证
    init 与写记录在同一 loop（见模块头注释）。
    """
    try:
        # 来自 apply_async(..., __task_id=...)，随 Celery 消息传到 Worker 的 request.properties。
        task_id = task.request.properties.get("__task_id", None)
        LOGGER.info(
            f"【Krun-Celery-Worker】【span_id={get_span_id()}】任务提交完成: "
            f"task_id=[{task_id}], "
            f"task_name=[{task.name}], "
            f"celery_id=[{task.request.id}], "
        )
        if task.name == _SCAN_TASK_NAME:
            ensure_tortoise_orm_initialized()
        else:
            try:
                h = getattr(task.request, "headers", None) or {}
                if isinstance(h, dict):
                    celery_trace_id_val = h.get("trace_id") or (h.get("headers") or {}).get("trace_id") or ""
                else:
                    celery_trace_id_val = ""
                celery_node_val = (task.name or "").strip() or ""
                trigger_type, report_type = _resolve_trigger_and_report(task)
                get_async_event_loop_pool().run(
                    _ensure_tortoise_then_create_task_record(
                        task_id=task_id,
                        celery_id=task.request.id,
                        celery_node=celery_node_val,
                        celery_trace_id=celery_trace_id_val,
                        celery_task_name=task.name,
                        trigger_type=trigger_type,
                        report_type=report_type,
                    )
                )
            except Exception as e:
                LOGGER.error(
                    f"【Krun-Celery-Worker】【span_id={get_span_id()}】创建执行记录失败:"
                    f"task_id=[{task.request.id}], "
                    f"错误类型: {type(e).__name__}, "
                    f"错误描述: {e}, \n"
                    f"错误回溯: {traceback.format_exc()}"
                )
    except Exception as e:
        LOGGER.error(
            f"【Krun-Celery-Worker】【span_id={get_span_id()}】定时任务挂载异常: "
            f"task_id=[{task.request.id}], "
            f"错误类型: {type(e).__name__}, "
            f"错误描述: {e}, \n"
            f"错误回溯: {traceback.format_exc()}"
        )


@setup_logging.connect
def setup_loggers(*args, **kwargs):
    """统一配置 Celery 日志格式。"""
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO)


class TaskRequest(Request):
    """自定义 Request：从消息头恢复 Trace/Span，供 task_prerun 与日志 patcher 使用。"""

    def __init__(self, *args, **kwargs):
        super(TaskRequest, self).__init__(*args, **kwargs)
        self._restore_trace_context()

    def _restore_trace_context(self):
        """从消息头绑定追踪上下文（无 span_id 时为本任务新建）。"""
        trace_id, span_id, parent_span_id = _extract_celery_trace_fields(self.request_dict)
        enter_celery_span(trace_id, parent_span_id, span_id)


def create_celery():
    """
    创建支持 async 任务体的 Celery 应用：通过自定义 Task.__call__ 将 async 任务投递到
    AsyncEventLoopContextIOPool 的 loop 执行，保证 Tortoise 与任务体在同一 loop（见模块头原理说明）。
    """

    class NewCelery(Celery):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def send_task(self, *args, **kwargs):
            """发送任务时注入 trace_id / span_id / parent_span_id 到 headers。"""
            headers = {
                "headers": celery_dispatch_trace_headers(),
            }
            if kwargs:
                kwargs.update(headers)
            else:
                kwargs = headers
            return super().send_task(*args, **kwargs)

    class ContextTask(Task, ABC):
        """自定义 Task：支持异步 run、apply_async 注入追踪头，结束时更新任务记录。"""

        Request = TaskRequest

        def delay(self, *args, **kwargs):
            return self.apply_async(args, kwargs)

        def apply_async(self, args=None, kwargs=None, task_id=None, producer=None,
                        link=None, link_error=None, shadow=None, **options):
            """下发时注入追踪头、__task_id（业务任务主键），供 Worker task_prerun 写 record 用。"""

            __task_id = options.get("__task_id", None)

            headers = {
                "headers": celery_dispatch_trace_headers(),
                "__task_id": __task_id,
            }

            if options:
                options.update(headers)
            else:
                options = headers

            return super(ContextTask, self).apply_async(
                args, kwargs, task_id, producer, link, link_error, shadow, **options
            )

        def handel_task_record(
            self,
            success: bool,
            task_summary: Any = None,
            traceback_str: str = None,
            batch_code: str = None,
        ):
            """更新观测记录终态；task_summary 为完整响应对象；扫描任务跳过。"""
            if self.request.id and self.name != _SCAN_TASK_NAME:
                try:
                    get_async_event_loop_pool().run(
                        _update_task_record_on_end(
                            celery_id=self.request.id,
                            success=success,
                            task_summary=task_summary,
                            traceback_str=traceback_str,
                            batch_code=batch_code,
                        )
                    )
                except Exception as e:
                    LOGGER.error(
                        f"【Krun-Celery-Worker】【span_id={get_span_id()}】更新执行记录异常: "
                        f"task_id=[{self.request.id}], "
                        f"错误类型: {type(e).__name__}, "
                        f"错误描述: {str(e)}, \n"
                        f"错误回溯: {traceback.format_exc()}"
                    )

        def on_success(self, retval, task_id, args, kwargs):
            """
            Celery 任务体未抛异常时回调。
            注意：业务侧可能 return {"success": False}（流程跑完但业务失败/早退），
            此时记录状态应按失败落库，不能一律标「成功」。
            """
            pipeline_ok = not (isinstance(retval, dict) and retval.get("success") is False)
            LOGGER.info(
                f"【Krun-Celery-Worker】【span_id={get_span_id()}】任务体结束: "
                f"task_id=[{task_id}], pipeline_ok={pipeline_ok}"
            )
            batch_code = retval.get("batch_code") if isinstance(retval, dict) else None
            summary = retval if retval is not None else {"success": True}
            self.handel_task_record(pipeline_ok, summary, batch_code=batch_code)
            return super(ContextTask, self).on_success(retval, task_id, args, kwargs)

        def on_failure(self, exc, task_id, args, kwargs, einfo):
            """任务抛异常：完整错误写入 task_summary，堆栈写入 task_error，状态=失败。"""
            LOGGER.error(
                f"【Krun-Celery-Worker】【span_id={get_span_id()}】任务执行失败: "
                f"task_id=[{task_id}], "
                f"错误类型: {type(exc).__name__}, "
                f"错误描述: {str(exc)}, \n"
                f"错误回溯: {einfo.traceback}"
            )
            summary = {
                "success": False,
                "error": str(exc) if exc else "执行失败",
                "error_type": type(exc).__name__ if exc else None,
            }
            self.handel_task_record(
                False,
                summary,
                traceback_str=getattr(einfo, "traceback", None) or "",
            )
            return super(ContextTask, self).on_failure(exc, task_id, args, kwargs, einfo)

        def __call__(self, *args, **kwargs):
            """
            执行任务：按消息头绑定 Trace/Span，推请求入栈；async 任务投递到池的 loop 执行。
            非扫描任务在 task_prerun 里已通过 _ensure_tortoise_then_create_task_record 完成 init+写记录；
            此处 ensure_tortoise_orm_initialized() 用于扫描任务或兜底，保证任务体跑前 Tortoise 可用。
            """
            try:
                ensure_tortoise_orm_initialized()
                hdr = self.request.headers or {}
                if isinstance(hdr, dict):
                    trace_id, span_id, parent_span_id = _extract_celery_trace_fields(hdr)
                else:
                    trace_id, span_id, parent_span_id = "", "", ""
                if not trace_id:
                    trace_id = getattr(LOCAL_CONTEXT_VAR, "trace_id", None) or ""
                enter_celery_span(trace_id, parent_span_id, span_id)
            except Exception:
                trace_id = getattr(LOCAL_CONTEXT_VAR, "trace_id", None) or ""
                enter_celery_span(trace_id, "", "")

            # 推送任务到堆栈
            _task_stack.push(self)
            self.push_request(args=args, kwargs=kwargs)

            try:
                if asyncio.iscoroutinefunction(self.run):
                    # 异步函数使用惰性初始化的池执行，避免在 Web 进程导入时创建事件循环
                    return get_async_event_loop_pool().run(self.run(*args, **kwargs))
                else:
                    # 同步函数直接执行
                    return self.run(*args, **kwargs)
            finally:
                # 清理
                self.pop_request()
                _task_stack.pop()

    # 创建 Celery 实例
    _celery_: Celery = NewCelery("Krun-Celery-Worker", task_cls=ContextTask)
    _celery_.config_from_object(CELERY_CONFIG.CELERY_CONFIG)
    return _celery_


celery = create_celery()

# ========== 启动命令（在项目根目录 Krun_副本_new 下执行，且保证 PYTHONPATH 含 backend 所在目录）==========
# Worker（消费 default + autotest_queue）：
#   Windows（单线程）：celery -A backend.celery_scheduler.celery_worker worker -Q default,autotest_queue --pool=solo -l INFO
#   Linux：          celery -A backend.celery_scheduler.celery_worker worker -Q default,autotest_queue -c 4 -l INFO
# Beat（定时下发 scan_and_dispatch_autotest_tasks，必须单独起一个进程）：
#   celery -A backend.celery_scheduler.celery_worker beat -l INFO

if __name__ == '__main__':
    import sys

    celery.start(argv=sys.argv[1:])
