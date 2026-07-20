# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : celery_base
@DateTime: 2026/1/27 16:25

Celery Worker 公共能力：Tortoise 初始化、异步协程桥接、定时任务到期判断、链路上下文。
"""
from __future__ import annotations

import threading
import traceback
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Awaitable, Coroutine, Dict, List, Optional, Union

from tortoise import Tortoise, connections
from tortoise.exceptions import DBConnectionError
from tortoise.expressions import Q

from backend.configure import PROJECT_CONFIG, LOGGER

# 全局变量，标记数据库是否已初始化
_tortoise_orm_initialized = False
_init_threading_safe_lock = threading.Lock()


def reset_tortoise_orm_state() -> None:
    """
    重置 Tortoise 初始化标记，供 Celery worker_process_init 在 prefork 子进程中调用。

    子进程不应沿用父进程的 ``_tortoise_orm_initialized``，否则会误以为已 init 而跳过。

    :return: None
    """
    global _tortoise_orm_initialized
    _tortoise_orm_initialized = False


def run_async(func: Union[Coroutine, Awaitable]) -> Any:
    """
    在 Celery 任务（同步上下文）中执行异步协程。

    统一通过 ``AsyncEventLoopContextIOPool.run_in_pool`` 投递到池的 event loop，
    保证 Tortoise 与业务协程运行在同一 loop。

    :param func: 待执行的协程对象
    :return: 协程执行结果
    """
    from backend.common import AsyncEventLoopContextIOPool
    return AsyncEventLoopContextIOPool.run_in_pool(func)


async def init_tortoise_orm() -> None:
    """
    在当前 running loop 所在线程中初始化 Tortoise（创建连接池）。

    必须在池线程、池的 loop 内调用；若已初始化则执行连接可用性检查（SELECT 1），
    连接失效时关闭并重新初始化。

    :return: None
    :raises RuntimeError: 数据库主机不可达等连接失败
    """
    global _tortoise_orm_initialized

    with _init_threading_safe_lock:
        if _tortoise_orm_initialized:
            try:
                conn = connections.get("default")
                if conn and hasattr(conn, "_pool") and conn._pool:
                    try:
                        await conn.execute_query("SELECT 1")
                        return
                    except Exception:
                        LOGGER.warning("【Celery-Worker】数据库连接已断开，将重新初始化")
                        _tortoise_orm_initialized = False
                        try:
                            await Tortoise.close_connections()
                        except Exception:
                            pass
                else:
                    _tortoise_orm_initialized = False
            except Exception as e:
                LOGGER.warning(
                    f"【Celery-Worker】【span_id={get_span_id_for_log()}】数据库连接检查失败，将重新初始化: {str(e)}"
                )
                _tortoise_orm_initialized = False
                try:
                    await Tortoise.close_connections()
                except Exception:
                    pass

        config: Dict[str, Any] = {
            "connections": PROJECT_CONFIG.DATABASE_CONNECTIONS,
            "apps": {
                "models": {
                    "models": PROJECT_CONFIG.APPLICATIONS_MODELS,
                    "default_connection": "default",
                }
            },
            "use_tz": False,
            "timezone": "Asia/Shanghai",
        }

        try:
            await Tortoise.init(config=config)
            _tortoise_orm_initialized = True
            LOGGER.info("【Celery-Worker】Tortoise ORM 数据库连接初始化成功")
        except DBConnectionError as e:
            LOGGER.error(f"【Celery-Worker】数据库连接失败: {str(e)}")
            raise RuntimeError(f"数据库连接失败, 请检查主机地址是否可达: {str(e)}")
        except Exception as e:
            LOGGER.error(f"【Celery-Worker】数据库初始化失败: {str(e)}")
            raise


def ensure_tortoise_orm_initialized() -> None:
    """
    同步封装：在池的 loop 中执行 ``init_tortoise_orm()``。

    用于扫描任务 ``task_prerun``、以及 ``ContextTask.__call__`` 兜底。

    :return: None
    """
    from backend.common import AsyncEventLoopContextIOPool

    try:
        AsyncEventLoopContextIOPool.run_in_pool(init_tortoise_orm())
    except Exception as e:
        LOGGER.error(f"【Celery-Worker】确保数据库初始化失败: {str(e)}")


def get_span_id_for_log() -> str:
    """
    从 Worker 上下文获取 span_id，用于 Celery 业务日志定位。

    :return: span_id 字符串；不可用时返回空串
    """
    from backend.common.request_context import get_span_id as _get

    sid = _get()
    if sid and sid != "-":
        return sid
    return getattr(LOCAL_CONTEXT_VAR, "span_id", None) or ""


async def get_scheduled_tasks(task_type: Any) -> List[Any]:
    """
    拉取未删除、已启用且配置了 Cron 表达式的自动化任务。

    :param task_type: 任务类型枚举或字符串（如 AutoTestTaskType.AUTOTEST_API）
    :return: 满足条件的 AutoTestApiTaskInfo 列表；参数无效时返回空列表
    """
    if not task_type:
        return []
    type_val = getattr(task_type, "value", task_type)
    if not type_val:
        return []
    from backend.applications.aotutest.models.autotest_model import AutoTestApiTaskInfo

    q = (
        Q(state=0)
        & Q(task_enabled=True)
        & Q(task_type=type_val)
        & ~Q(task_crontabs_expr__isnull=True)
        & ~Q(task_crontabs_expr="")
    )
    return list(await AutoTestApiTaskInfo.filter(q).all())


def check_task_expired(task: Any) -> bool:
    """
    判断任务是否已到执行时间（仅基于 ``task_crontabs_expr``）。

    规则：最近一次 cron 触发点晚于 ``last_execute_time``（或从未执行）则视为到期。

    :param task: 任务模型实例（需含 task_crontabs_expr / last_execute_time 等字段）
    :return: 到期为 True，否则为 False；Cron 解析失败时返回 False
    """
    expr = (getattr(task, "task_crontabs_expr", None) or "").strip()
    if not expr:
        return False

    now = datetime.now()
    last_run = getattr(task, "last_execute_time", None) or getattr(task, "created_time", None)
    if last_run and getattr(last_run, "tzinfo", None):
        last_run = last_run.replace(tzinfo=None)
    if isinstance(last_run, str):
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                last_run = (
                    datetime.strptime(last_run[:26], fmt)
                    if "." in last_run
                    else datetime.strptime(last_run[:19], "%Y-%m-%d %H:%M:%S")
                )
                break
            except ValueError:
                continue
        else:
            last_run = None

    task_id = getattr(task, "id", None)
    try:
        from croniter import croniter

        prev_run = croniter(expr, now).get_prev(datetime)
        due = True if last_run is None else (last_run < prev_run)
        LOGGER.debug(
            f"【Celery-Worker】cron到期判断 task_id={task_id} expr={expr} "
            f"now={now} prev={prev_run} last_run={last_run} due={due}"
        )
        return due
    except Exception as e:
        LOGGER.warning(
            f"【Celery-Worker】【span_id={get_span_id_for_log()}】Cron 解析失败: "
            f"task_id={task_id}, 错误类型: {type(e).__name__}, 错误描述: {e}\n"
            f"{traceback.format_exc()}"
        )
        return False


class LocalContextVar:
    """基于 ContextVar 的轻量上下文，供 Celery 链路传递 trace_id / span_id。"""

    __slots__ = ("_storage",)

    def __init__(self) -> None:
        """
        初始化 ContextVar 存储。

        :return: None
        """
        object.__setattr__(self, "_storage", ContextVar("local_storage"))

    def __getattr__(self, name: str) -> Any:
        """
        读取上下文中的属性。

        :param name: 属性名
        :return: 属性值；不存在时返回 None
        """
        try:
            return self._storage.get({})[name]
        except KeyError:
            return None

    def __setattr__(self, name: str, value: Any) -> None:
        """
        写入上下文属性。

        :param name: 属性名
        :param value: 属性值
        :return: None
        """
        values = self._storage.get({}).copy()
        values[name] = value
        self._storage.set(values)


LOCAL_CONTEXT_VAR = LocalContextVar()
