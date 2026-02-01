# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : celery_worker
@DateTime: 2026/1/27 16:25
"""
import asyncio
import logging
import traceback
import uuid
from abc import ABC
from datetime import datetime
from typing import Dict, Any, List, Optional

from celery import Celery
from celery import Task
from celery._state import _task_stack
from celery.signals import setup_logging, task_prerun
from celery.worker.request import Request

from backend import LOGGER
from backend.common.async_or_sync_convert import AsyncEventLoopContextIOPool
from backend.configure.celery_config import CELERY_CONFIG
from backend.configure.logging_config import InterceptHandler
from .celery_base import ensure_tortoise_orm_initialized, LOCAL_CONTEXT_VAR

_async_event_loop_pool = None


def get_async_event_loop_pool():
    """
    惰性获取异步事件循环池，仅在 Worker 执行任务时创建，避免 Web 进程导入时创建事件循环。
    :return:
    """
    global _async_event_loop_pool
    if _async_event_loop_pool is None:
        _async_event_loop_pool = AsyncEventLoopContextIOPool()
    return _async_event_loop_pool


async def _create_task_record(
        trace_id: str,
        celery_id: str,
        celery_node: str,
        celery_trace_id: str,
        task_id: str,
        celery_task_name: str,
        trigger_type: int,
        task_args: Dict[str, Any],
        task_kwargs: Dict[str, Any],
):
    """
    创建任务执行记录（状态 RUNNING），由 task_prerun 通过事件循环池调用。
    :param celery_id: 对应 celery_id
    :param celery_node: 调度节点（Celery 任务完全限定名，如 run_autotest_task）
    :param celery_trace_id: 对应 celery_trace_id（调度回溯ID）
    :param task_id: 对应 task_id（任务信息表主键，来自 __task_id，可为空）
    :param celery_task_name: Celery 任务完全限定名，用于判断是否从业务任务表取 task_name/case_ids
    :param trigger_type: __task_type（10 手动 20 调度），用于解析 celery_scheduler
    :param task_args: 定时任务实现函数的位置参数（request.args），写入记录 task_args
    :param task_kwargs: 定时任务实现函数的关键字参数（request.kwargs），写入记录 task_kwargs
    """
    from backend.applications.aotutest.models.autotest_model import AutoTestApiTaskInfo
    from backend.applications.aotutest.services.autotest_record_crud import AUTOTEST_API_RECORD_CRUD
    from backend.enums.autotest_enum import AutoTestTaskStatus, AutoTestTaskScheduler, AutoTestReportType
    task_args = list(task_args) if task_args else []
    task_kwargs = dict(task_kwargs) if task_kwargs else {}
    task_case_ids: List[int] = []
    celery_scheduler: Optional[str] = None
    record_task_name: str = ""
    if task_id is not None and celery_task_name and "run_autotest_task" in celery_task_name:
        t = await AutoTestApiTaskInfo.filter(id=task_id).first()
        if t:
            record_task_name = (getattr(t, "task_name", None) or "").strip() or ""
            task_case_ids = getattr(t, "case_ids", None) or []
            if trigger_type == 20 and getattr(t, "task_scheduler", None):
                try:
                    celery_scheduler = AutoTestTaskScheduler(t.task_scheduler) if isinstance(
                        t.task_scheduler, str) else t.task_scheduler
                except (ValueError, TypeError):
                    pass
            # 将 task_args/task_kwargs 替换为真正调用 batch_execute_cases 时的参数
            rpt_enum = getattr(AutoTestReportType, "SCHEDULE_EXEC", None)
            task_args = []
            task_kwargs = {
                "case_ids": list(task_case_ids),
                "initial_variables": [],
                "execute_environment": (getattr(t, "task_env", None) or "").strip() or None,
                "report_type": rpt_enum.value if rpt_enum else "定时执行",
            }
    data: Dict[str, Any] = {
        "task_id": task_id,
        "task_name": record_task_name or None,
        "task_args": task_args,
        "task_kwargs": task_kwargs,
        "task_case_ids": task_case_ids,
        "celery_id": celery_id,
        "celery_node": (celery_node or "").strip() or None,
        "celery_trace_id": (celery_trace_id or "").strip() or None,
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
        "task_result": summary,
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
    任务执行前：初始化 Tortoise、写入任务执行记录（RUNNING），扫描任务不落表。
    :param task: task 实例
    :param args: 位置参数
    :param kwargs: 关键字参数
    :return:
    """
    try:
        ensure_tortoise_orm_initialized()
        task_id = task.request.properties.get("__task_id", None)
        task_type = task.request.properties.get("__task_type", None)
        trace_id = task.request.headers.get("trace_id", None)
        LOGGER.info(
            f"【Krun-Celery-Worker】【trace_id={trace_id}】任务提交完成: "
            f"task_id=[{task_id}], "
            f"task_name=[{task.name}], "
            f"task_type=[{task_type}]"
            f"celery_id=[{task.request.id}], "
        )
        # 写入任务执行记录（含 celery_trace_id）；扫描任务不落表
        # trace_id 作用：在 send_task 时自动注入到消息 headers，Worker 执行时从 request.headers 取出，
        # 用于一次“用户操作 → API → Celery”的整条链路追踪。记录到表的 celery_trace_id 后，便于按记录
        # 反查日志（grep trace_id=xxx）或与前端/网关的 trace 关联。
        _SCAN_TASK_NAME = "backend.celery_scheduler.tasks.task_autotest_case.scan_and_dispatch_autotest_tasks"
        if task.name != _SCAN_TASK_NAME:
            try:
                req_args = getattr(task.request, "args", []) or []
                req_kwargs = getattr(task.request, "kwargs", {}) or {}
                h = getattr(task.request, "headers", None) or {}
                if isinstance(h, dict):
                    celery_trace_id_val = h.get("trace_id") or (h.get("headers") or {}).get("trace_id") or ""
                else:
                    celery_trace_id_val = ""
                celery_node_val = (task.name or "").strip() or ""
                get_async_event_loop_pool().run(
                    _create_task_record(
                        trace_id=trace_id,
                        celery_id=task.request.id,
                        celery_node=celery_node_val,
                        celery_trace_id=celery_trace_id_val,
                        task_id=task_id,
                        celery_task_name=task.name,
                        trigger_type=task_type if task_type is not None else 10,
                        task_args=req_args,
                        task_kwargs=req_kwargs,
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
    原生Celery采取的是对象入列模式因此只能执行同步函数，无法直接调用async def函数；
    由于所有的数据库操作都是异步的（Tortoise-ORM是纯异步实现，不像Sqlalchemy属于同步异步混合模式），
    改造异步至同步代码存在工作量，且为了celery降低数据库方面的性能不值得，
    所以需要改造Celery，让其支持异步函数调用（利用单例线程池整合异步事件循环的环境信息）
    :return:
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
        """自定义 Task：支持异步 run、apply_async 注入 trace_id/__task_type，结束时更新任务记录。"""

        Request = TaskRequest

        def delay(self, *args, **kwargs):
            return self.apply_async(args, kwargs)

        def apply_async(self, args=None, kwargs=None, task_id=None, producer=None,
                        link=None, link_error=None, shadow=None, **options):
            """下发时注入 trace_id 与 __task_type。"""

            __task_type = options.get("__task_type", None)
            __task_type = __task_type if __task_type else 10

            headers = {
                "headers": {
                    "trace_id": LOCAL_CONTEXT_VAR.trace_id or str(uuid.uuid4())
                },
                "__task_type": __task_type
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
            """执行任务：恢复 trace_id、推请求入栈，异步任务经事件循环池执行，最后出栈。"""
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

# celery_worker 专用于 celery 的 worker
# worker windows 启动，只能单线程
# celery -A celery_worker.worker worker --pool=solo -l INFO
# worker linux  启动
# celery -A celery_worker.worker worker --pool=solo -c 10 -l INFO
# beat
# celery -A celery_worker.worker beat -l INFO  启动节拍器，定时任务需要
# beat 数据库
# celery -A celery_worker.worker beat -S celery_worker.scheduler.schedulers:DatabaseScheduler -l INFO
# ========== 启动命令（在项目根目录 Krun_副本_new 下执行，且保证 PYTHONPATH 含 backend 所在目录）==========
# Worker（消费 default + autotest_queue）：
#   Windows（单线程）：celery -A backend.celery_scheduler.celery_worker worker -Q default,autotest_queue --pool=solo -l INFO
#   Linux：          celery -A backend.celery_scheduler.celery_worker worker -Q default,autotest_queue -c 4 -l INFO
# Beat（定时下发 scan_and_dispatch_autotest_tasks，必须单独起一个进程）：
#   celery -A backend.celery_scheduler.celery_worker beat -l INFO

if __name__ == '__main__':
    import sys

    celery.start(argv=sys.argv[1:])
