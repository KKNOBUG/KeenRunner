# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : celery_base
@DateTime: 2026/1/27 16:25
"""
from __future__ import annotations

import logging
import threading
import traceback
from contextvars import ContextVar
from datetime import datetime
from typing import Dict, Any, Union, Coroutine, Awaitable, Iterator, Tuple
from typing import List, Optional

from tortoise import Tortoise, connections
from tortoise.exceptions import DBConnectionError
from tortoise.expressions import Q

from backend import PROJECT_CONFIG, LOGGER

# 全局变量，标记数据库是否已初始化
_tortoise_orm_initialized = False
_init_threading_safe_lock = threading.Lock()
logger = logging.getLogger(__name__)


def reset_tortoise_orm_state() -> None:
    """
    重置 Tortoise 初始化标记，供 Celery worker_process_init 在 prefork 子进程里调用。
    子进程不应沿用父进程的 _tortoise_orm_initialized，否则会误以为已 init 而跳过，导致
    使用的连接池实为父进程的、与当前进程的池 loop 不一致。
    """
    global _tortoise_orm_initialized
    _tortoise_orm_initialized = False


def run_async(func: Union[Coroutine, Awaitable]) -> Any:
    """
    在 Celery 任务（同步上下文）中执行异步协程的入口。
    统一通过 AsyncEventLoopContextIOPool.run_in_pool 投递到池的 loop 执行，保证 Tortoise 等
    与池的 loop 一致；禁止在任务里 asyncio.run()/run_until_complete() 新建并关闭 loop，
    否则 Tortoise 连接池会绑到已关闭的 loop，出现 "Event loop is closed" 等。
    """
    from backend.common.async_or_sync_convert import AsyncEventLoopContextIOPool
    return AsyncEventLoopContextIOPool.run_in_pool(func)


async def init_tortoise_orm() -> None:
    """
    在「当前 running loop」所在线程中初始化 Tortoise（创建连接池）。
    必须在池线程、池的 loop 里调用（即由 run(init_tortoise_orm()) 或 run(_ensure_tortoise_then_...) 调用），
    这样 Tortoise/aiomysql 绑定的 loop 与后续 _create_task_record、业务任务使用的 loop 一致；
    若在其它 loop 或线程中 init，会触发 "Task got Future attached to a different loop"。
    若已初始化则仅做连接可用性检查（SELECT 1）。
    """
    global _tortoise_orm_initialized

    # 使用线程锁保护初始化过程
    with _init_threading_safe_lock:
        # 如果已经初始化，检查连接是否可用
        if _tortoise_orm_initialized:
            try:
                # 尝试获取连接来验证连接是否可用
                conn = connections.get("default")
                if conn and hasattr(conn, '_pool') and conn._pool:
                    try:
                        # 连接池存在，尝试执行一个简单查询来验证连接
                        await conn.execute_query("SELECT 1")
                        return
                    except Exception:
                        # 连接可能已断开，需要重新初始化
                        LOGGER.warning("数据库连接已断开，将重新初始化")
                        _tortoise_orm_initialized = False
                        try:
                            await Tortoise.close_connections()
                        except:
                            pass
                else:
                    # 连接池不存在，需要初始化
                    _tortoise_orm_initialized = False
            except Exception as e:
                LOGGER.warning(f"数据库连接检查失败，将重新初始化: {str(e)}")
                _tortoise_orm_initialized = False
                try:
                    # 关闭现有连接
                    await Tortoise.close_connections()
                except:
                    pass

        # 初始化数据库配置
        config: Dict[str, Any] = {
            "connections": PROJECT_CONFIG.DATABASE_CONNECTIONS,
            "apps": {
                "models": {
                    "models": PROJECT_CONFIG.APPLICATIONS_MODELS,
                    "default_connection": "default"
                }
            },
            "use_tz": False,
            "timezone": "Asia/Shanghai",
        }

        try:
            # 初始化 Tortoise ORM
            # 注意：如果已经初始化过，Tortoise.init 会重新初始化
            await Tortoise.init(config=config)
            _tortoise_orm_initialized = True
            LOGGER.info("Tortoise ORM 数据库连接初始化成功")
        except DBConnectionError as e:
            LOGGER.error(f"数据库连接失败: {str(e)}")
            raise RuntimeError(f"数据库连接失败, 请检查主机地址是否可达: {str(e)}")
        except Exception as e:
            LOGGER.error(f"数据库初始化失败: {str(e)}")
            raise


def ensure_tortoise_orm_initialized():
    """
    同步封装：在池的 loop 里执行 init_tortoise_orm()，阻塞直到完成。
    用于：扫描任务的 task_prerun（只 init 不写记录）；ContextTask.__call__ 的兜底（保证任务体
    跑前 Tortoise 已可用）。非扫描任务的「init + 写记录」由 _ensure_tortoise_then_create_task_record
    在一次 run() 内完成，不依赖本函数做 init。
    """
    from backend.common.async_or_sync_convert import AsyncEventLoopContextIOPool

    try:
        # 使用 AsyncIOPool 执行异步初始化
        # 注意：这里传递的是协程对象，AsyncIOPool.run_in_pool 会处理它
        AsyncEventLoopContextIOPool.run_in_pool(init_tortoise_orm())
    except Exception as e:
        LOGGER.error(f"确保数据库初始化失败: {str(e)}")
        # 不抛出异常，让任务继续执行，但记录错误
        # 如果数据库连接真的有问题，任务执行时会再次报错


def get_trace_id():
    """从 Worker 上下文获取 trace_id，用于日志定位。"""
    return getattr(LOCAL_CONTEXT_VAR, "trace_id", None) or ""


def get_step_crud():
    from backend.applications.aotutest.services.autotest_step_crud import AUTOTEST_API_STEP_CRUD
    return AUTOTEST_API_STEP_CRUD


def get_task_model():
    from backend.applications.aotutest.models.autotest_model import AutoTestApiTaskInfo
    return AutoTestApiTaskInfo


def get_task_status_enum():
    from backend.enums.autotest_enum import AutoTestTaskStatus
    return AutoTestTaskStatus


def get_report_type_enum():
    from backend.enums.autotest_enum import AutoTestReportType
    return AutoTestReportType


def get_scheduler_value(scheduler: Any) -> Optional[str]:
    """将调度类型枚举或字符串转为小写字符串（cron/interval/datetime）。"""
    if scheduler is None:
        return None
    if hasattr(scheduler, "value"):
        return (scheduler.value or "").strip().lower() or None
    return str(scheduler).strip().lower() or None


async def get_scheduled_tasks(task_type: str) -> List[Any]:
    """
    拉取未删除、已启用且配置了调度的任务列表，按 task_type 过滤，避免非自动化任务被下发到 run_autotest_task。

    :param task_type: 任务类型。
    传 "autotest"（默认）时只返回自动化测试任务
    """
    if not task_type:
        return []
    Model = get_task_model()
    q = Q(state=0) & Q(task_enabled=True) & ~Q(task_scheduler__isnull=True) & Q(task_type=task_type)
    tasks = await Model.filter(q).all()
    return list(tasks)


async def check_task_expired(task: Any) -> bool:
    """
    判断任务是否已到执行时间。

    :param task: 任务模型实例（含 task_scheduler、cron/interval/datetime 表达式等）
    :return: 是否到期
    """
    scheduler = getattr(task, "task_scheduler", None)
    scheduler_str = get_scheduler_value(scheduler)
    if not scheduler_str:
        return False

    now = datetime.now()
    last_run = getattr(task, "last_execute_time", None) or getattr(task, "created_time", None)
    # 统一为 naive datetime 比较
    if last_run and getattr(last_run, "tzinfo", None):
        last_run = last_run.replace(tzinfo=None) if last_run.tzinfo else last_run

    if scheduler_str == "cron":
        expr = (getattr(task, "task_crontabs_expr", None) or "").strip()
        if not expr:
            return False
        try:
            from croniter import croniter
            base = last_run or now
            if getattr(base, "tzinfo", None):
                base = base.replace(tzinfo=None)
            it = croniter(expr, base)
            next_run = it.get_next(datetime)
            return next_run <= now
        except Exception as e:
            logger.warning(
                f"【Krun-Celery-Worker】<==> 【trace_id={get_trace_id()}】任务触发器Cron表达式解析失败: "
                f" task_id={getattr(task, 'id', None)}",
                f"错误类型: {type(e).__name__}, "
                f"错误描述: {e}, \n"
                f"错误回溯: {traceback.format_exc()}"
            )
            return False

    if scheduler_str == "interval":
        seconds = getattr(task, "task_interval_expr", None) or 0
        if seconds <= 0:
            return False
        if not last_run:
            return True
        diff = now - last_run
        delta = diff.total_seconds() if hasattr(diff, "total_seconds") else diff.seconds
        return delta >= seconds

    if scheduler_str == "datetime":
        expr = (task.task_datetime_expr or "").strip()
        if not expr:
            return False
        try:
            target = datetime.strptime(expr, "%Y-%m-%d %H:%M:%S")
            if last_run and last_run >= target:
                return False
            return now >= target
        except Exception as e:
            logger.warning(
                f"【Krun-Celery-Worker】<==> 【trace_id={get_trace_id()}】任务触发器Datetime表达式解析失败: "
                f" task_id={task.id}",
                f"错误类型: {type(e).__name__}, "
                f"错误描述: {e}, \n"
                f"错误回溯: {traceback.format_exc()}"
            )
            return False

    return False


class LocalContextVar:
    """
    基于 ContextVar 的本地上下文变量类
    用于在异步环境中传递上下文信息（如 trace_id）
    """
    __slots__ = ("_storage",)

    def __init__(self) -> None:
        object.__setattr__(self, "_storage", ContextVar("local_storage"))

    def __iter__(self) -> Iterator[Tuple[int, Any]]:
        return iter(self._storage.get({}).items())

    def __release_local__(self) -> None:
        self._storage.set({})

    def __getattr__(self, name: str) -> Any:
        values = self._storage.get({})
        try:
            return values[name]
        except KeyError:
            return None

    def __setattr__(self, name: str, value: Any) -> None:
        values = self._storage.get({}).copy()
        values[name] = value
        self._storage.set(values)

    def __delattr__(self, name: str) -> None:
        values = self._storage.get({}).copy()
        try:
            del values[name]
            self._storage.set(values)
        except KeyError:
            ...


LOCAL_CONTEXT_VAR = LocalContextVar()
