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
import uuid
from abc import ABC
from datetime import datetime
from typing import Dict, Any, Optional

from celery import Celery
from celery import Task
from celery._state import _task_stack
from celery.signals import setup_logging, task_prerun, worker_process_init
from celery.worker.request import Request

from backend import LOGGER
from backend.common.async_or_sync_convert import AsyncEventLoopContextIOPool
from backend.configure.celery_config import CELERY_CONFIG
from backend.configure.logging_config import InterceptHandler
from .celery_base import (
    ensure_tortoise_orm_initialized,
    init_tortoise_orm,
    reset_tortoise_orm_state,
    LOCAL_CONTEXT_VAR,
)

_async_event_loop_pool = None


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
    LOGGER.debug("【Krun-Celery-Worker】worker_process_init: 已重置异步池与 Tortoise 状态")


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
        trace_id: str,
        celery_id: str,
        celery_node: str,
        celery_trace_id: str,
        task_id: str,
        celery_task_name: str,
):
    """
    在同一协程内先 init Tortoise 再写执行记录，保证「连接池创建」与「使用连接池写记录」在
    同一次 run()、同一个 event loop 中完成，从而避免 aiomysql Pool._wakeup 等 Future 绑定到
    与当前运行 loop 不一致的 loop（"Task got Future attached to a different loop"）。
    执行顺序：await init_tortoise_orm() → await _create_task_record(...)。
    """
    await init_tortoise_orm()
    await _create_task_record(
        trace_id=trace_id,
        celery_id=celery_id,
        celery_node=celery_node,
        celery_trace_id=celery_trace_id,
        task_id=task_id,
        celery_task_name=celery_task_name,
    )


async def _create_task_record(
        trace_id: str,
        celery_id: str,
        celery_node: str,
        celery_trace_id: str,
        task_id: str,
        celery_task_name: str,
):
    """
    创建任务执行记录（状态 RUNNING），由 _ensure_tortoise_then_create_task_record 或事件循环池调用。
    :param celery_id: 对应 celery_id
    :param celery_node: 调度节点（Celery 任务完全限定名，如 run_autotest_task）
    :param celery_trace_id: 对应 celery_trace_id（调度回溯ID）
    :param task_id: 对应 task_id（任务信息表主键，来自 __task_id，可为空）
    :param celery_task_name: Celery 任务完全限定名，用于判断是否从业务任务表取 task_name/case_ids
    """
    from backend.applications.aotutest.models.autotest_model import AutoTestApiTaskInfo
    from backend.applications.aotutest.services.autotest_record_crud import AUTOTEST_API_RECORD_CRUD
    from backend.enums.autotest_enum import AutoTestTaskStatus, AutoTestTaskScheduler
    task_name: Optional[str] = None
    task_kwargs: Dict[str, Any] = {}
    celery_scheduler: Optional[str] = None
    # task_id 来自 apply_async(..., __task_id=task_id)；未传 __task_id 时此处为 None，不查任务表，record 无 task_id/task_name。
    if task_id is not None and celery_task_name and "run_autotest_task" in celery_task_name:
        task_instance = await AutoTestApiTaskInfo.filter(id=task_id).first()
        if task_instance:
            task_name = getattr(task_instance, "task_name", None)
            task_kwargs = getattr(task_instance, "task_kwargs", None) or {}
            celery_scheduler = AutoTestTaskScheduler(task_instance.task_scheduler) if isinstance(
                task_instance.task_scheduler, str) else task_instance.task_scheduler
    data: Dict[str, Any] = {
        "task_id": task_id,
        "task_name": task_name,
        "task_kwargs": task_kwargs,
        "celery_id": celery_id,
        "celery_node": celery_node,
        "celery_trace_id": celery_trace_id,
        "celery_status": AutoTestTaskStatus.RUNNING,
        "celery_scheduler": celery_scheduler,
        "celery_start_time": datetime.now(),
    }
    await AUTOTEST_API_RECORD_CRUD.create_record(data)
    LOGGER.info(f"【Krun-Celery-Worker】【trace_id={trace_id}】更新执行记录成功, 已更新[celery_id={celery_id}]记录")


async def _update_task_record_on_end(
        trace_id: str,
        celery_id: str,
        success: bool,
        result_or_error: str,
        traceback_str: str = None,
):
    """
    将任务执行记录更新为终态（SUCCESS/FAILURE），由 on_success/on_failure 通过事件循环池调用。

    :param celery_id: Celery 任务 ID
    :param success: 是否成功
    :param result_or_error: 结果或错误摘要
    :param traceback_str: 失败时的堆栈（可选）
    """
    if not celery_id:
        return
    from backend.applications.aotutest.services.autotest_record_crud import AUTOTEST_API_RECORD_CRUD
    from backend.enums.autotest_enum import AutoTestTaskStatus

    now = datetime.now()
    status_enum = AutoTestTaskStatus.SUCCESS if success else AutoTestTaskStatus.FAILURE
    summary = (result_or_error or "").strip() or ""
    data = {
        "celery_status": status_enum,
        "celery_end_time": now,
        "task_summary": summary,
        "task_error": None if success else (traceback_str or summary),
    }
    record = await AUTOTEST_API_RECORD_CRUD.get_by_celery_id(celery_id=celery_id)
    if not record:
        LOGGER.error(f"【Krun-Celery-Worker】【trace_id={trace_id}】更新执行记录失败, 未找到[celery_id={celery_id}]记录")
        return
    if record.celery_start_time:
        start = record.celery_start_time
        if getattr(start, "tzinfo", None) is not None:
            start = start.replace(tzinfo=None)
        delta = now - start
        data["celery_duration"] = f"{delta.total_seconds():.2f}s"
    await AUTOTEST_API_RECORD_CRUD.update_record_by_celery_id(celery_id=celery_id, data=data)
    LOGGER.info(f"【Krun-Celery-Worker】【trace_id={trace_id}】更新执行记录成功, 已更新[celery_id={celery_id}]记录")


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
        trace_id = task.request.headers.get("trace_id", None)
        LOGGER.info(
            f"【Krun-Celery-Worker】【trace_id={trace_id}】任务提交完成: "
            f"task_id=[{task_id}], "
            f"task_name=[{task.name}], "
            f"celery_id=[{task.request.id}], "
        )
        _SCAN_TASK_NAME = "backend.celery_scheduler.tasks.task_autotest_case.scan_and_dispatch_autotest_tasks"
        if task.name == _SCAN_TASK_NAME:
            # 扫描任务：只做 Tortoise 初始化（一次 run(init_tortoise_orm())），不写执行记录
            ensure_tortoise_orm_initialized()
        else:
            # 非扫描任务：单次 run( init → create_record )，保证 Tortoise 与写记录同一 loop
            try:
                h = getattr(task.request, "headers", None) or {}
                if isinstance(h, dict):
                    celery_trace_id_val = h.get("trace_id") or (h.get("headers") or {}).get("trace_id") or ""
                else:
                    celery_trace_id_val = ""
                celery_node_val = (task.name or "").strip() or ""
                get_async_event_loop_pool().run(
                    _ensure_tortoise_then_create_task_record(
                        trace_id=trace_id,
                        task_id=task_id,
                        celery_id=task.request.id,
                        celery_node=celery_node_val,
                        celery_trace_id=celery_trace_id_val,
                        celery_task_name=task.name,
                    )
                )
            except Exception as e:
                LOGGER.error(
                    f"【Krun-Celery-Worker】【trace_id={trace_id}】创建执行记录失败:"
                    f"task_id=[{task.request.id}], "
                    f"错误类型: {type(e).__name__}, "
                    f"错误描述: {e}, \n"
                    f"错误回溯: {traceback.format_exc()}"
                )
    except Exception as e:
        trace_id = task.request.headers.get("trace_id", None)
        LOGGER.error(
            f"【Krun-Celery-Worker】【trace_id={trace_id}】定时任务挂载异常: "
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
    """自定义 Request：从 request_dict 读取 trace_id 并写入线程上下文，供链路追踪。"""

    def __init__(self, *args, **kwargs):
        super(TaskRequest, self).__init__(*args, **kwargs)
        self.set_trace_id()

    def set_trace_id(self):
        """将 trace_id 写入 LOCAL_CONTEXT_VAR，与发送端保持一致。"""
        trace_id = self.request_dict.get("trace_id", str(uuid.uuid4()))
        LOCAL_CONTEXT_VAR.trace_id = trace_id


def create_celery():
    """
    创建支持 async 任务体的 Celery 应用：通过自定义 Task.__call__ 将 async 任务投递到
    AsyncEventLoopContextIOPool 的 loop 执行，保证 Tortoise 与任务体在同一 loop（见模块头原理说明）。
    """

    class NewCelery(Celery):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def send_task(self, *args, **kwargs):
            """发送任务时注入 trace_id 到 headers。"""
            headers = {
                "headers": {
                    "trace_id": LOCAL_CONTEXT_VAR.trace_id or str(uuid.uuid4())
                }
            }
            if kwargs:
                kwargs.update(headers)
            else:
                kwargs = headers
            return super().send_task(*args, **kwargs)

    class ContextTask(Task, ABC):
        """自定义 Task：支持异步 run、apply_async 注入 trace_id，结束时更新任务记录。"""

        Request = TaskRequest

        def delay(self, *args, **kwargs):
            return self.apply_async(args, kwargs)

        def apply_async(self, args=None, kwargs=None, task_id=None, producer=None,
                        link=None, link_error=None, shadow=None, **options):
            """下发时注入 trace_id、__task_id（业务任务主键），供 Worker task_prerun 写 record 用。"""

            __task_id = options.get("__task_id", None)

            headers = {
                "headers": {
                    "trace_id": LOCAL_CONTEXT_VAR.trace_id or str(uuid.uuid4())
                },
                "__task_id": __task_id,
            }

            if options:
                options.update(headers)
            else:
                options = headers

            return super(ContextTask, self).apply_async(
                args, kwargs, task_id, producer, link, link_error, shadow, **options
            )

        def handel_task_record(self, success: bool, result_or_error: str, traceback_str: str = None):
            """在同步回调中通过事件循环池更新任务记录为 SUCCESS/FAILURE，扫描任务不更新。"""
            trace_id = self.request.headers.get("trace_id", None)
            _SCAN_TASK_NAME = "backend.celery_scheduler.tasks.task_autotest_case.scan_and_dispatch_autotest_tasks"
            if self.request.id and self.name != _SCAN_TASK_NAME:
                try:
                    get_async_event_loop_pool().run(
                        _update_task_record_on_end(
                            trace_id=trace_id,
                            celery_id=self.request.id,
                            success=success,
                            result_or_error=result_or_error or "",
                            traceback_str=traceback_str,
                        )
                    )
                except Exception as e:
                    LOGGER.error(
                        f"【Krun-Celery-Worker】【trace_id={trace_id}】更新执行记录异常: "
                        f"task_id=[{self.request.id}], "
                        f"错误类型: {type(e).__name__}, "
                        f"错误描述: {str(e)}, \n"
                        f"错误回溯: {traceback.format_exc()}"
                    )

        def on_success(self, retval, task_id, args, kwargs):
            """Celery-Worker 任务执行成功时回调，更新执行记录为: SUCCESS"""
            trace_id = self.request.headers.get("trace_id", None)
            LOGGER.info(f"【Krun-Celery-Worker】【trace_id={trace_id}】任务执行成功: task_id=[{task_id}]")
            self.handel_task_record(True, str(retval) if retval is not None else "")
            return super(ContextTask, self).on_success(retval, task_id, args, kwargs)

        def on_failure(self, exc, task_id, args, kwargs, einfo):
            """Celery-Worker 任务执行失败时回调，更新执行记录为: FAILURE"""
            trace_id = self.request.headers.get("trace_id", None)
            LOGGER.error(
                f"【Krun-Celery-Worker】【trace_id={trace_id}】任务执行失败: "
                f"task_id=[{task_id}], "
                f"错误类型: {type(exc).__name__}, "
                f"错误描述: {str(exc)}, \n"
                f"错误回溯: {einfo.traceback}"
            )
            self.handel_task_record(False, str(exc) if exc else "", getattr(einfo, "traceback", None) or "")
            return super(ContextTask, self).on_failure(exc, task_id, args, kwargs, einfo)

        def __call__(self, *args, **kwargs):
            """
            执行任务：恢复 trace_id、推请求入栈；若为 async 任务则投递到池的 loop 执行，否则直接执行。
            非扫描任务在 task_prerun 里已通过 _ensure_tortoise_then_create_task_record 完成 init+写记录；
            此处 ensure_tortoise_orm_initialized() 用于扫描任务或兜底，保证任务体跑前 Tortoise 可用。
            """
            try:
                ensure_tortoise_orm_initialized()

                trace_id = self.request.headers.get("trace_id", None)
                if trace_id:
                    LOCAL_CONTEXT_VAR.trace_id = trace_id
                else:
                    LOCAL_CONTEXT_VAR.trace_id = LOCAL_CONTEXT_VAR.trace_id or str(uuid.uuid4())
            except Exception:
                LOCAL_CONTEXT_VAR.trace_id = LOCAL_CONTEXT_VAR.trace_id or str(uuid.uuid4())

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
