# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : logging_config.py
@DateTime: 2025/1/16 15:33
"""
import logging
import os
import sys
import threading
from datetime import datetime, timedelta
from typing import Optional

from concurrent_log_handler import ConcurrentTimedRotatingFileHandler
from loguru import logger

from backend.common.request_context import get_parent_span_id, get_span_id, get_trace_id
from backend.configure.project_config import PROJECT_CONFIG

# 自定义日志格式
LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: ^8}</level> | "
    "<yellow>{extra[trace_id]}</yellow>:<yellow>{extra[span_id]}</yellow> | "
    "process [<cyan>{process}</cyan>]:<cyan>{thread}</cyan> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> -> "
    "<level>{message}</level>"
)


def _inject_trace_context(record: dict) -> None:
    """Loguru patcher：每条日志自动附带trace_id/span_id。"""
    extra = record["extra"]
    if not extra.get("trace_id"):
        extra["trace_id"] = get_trace_id()
    if not extra.get("span_id"):
        extra["span_id"] = get_span_id()
    parent = get_parent_span_id()
    if parent and not extra.get("parent_span_id"):
        extra["parent_span_id"] = parent


# 写入 ConcurrentTimedRotatingFileHandler 时只落纯文本 message，格式由 Loguru format= 负责
_HANDLER_PASSTHROUGH = logging.Formatter("%(message)s")

# 部署在 Gunicorn + Uvicorn 下需要接管的 logger 名称（与 wire_standard_loggers 一致）
# gunicorn/gunicorn.error 不接管：gunicorn 自身运行日志按设计丢弃，HTTP 请求日志由 uvicorn.access 记录
_WIRED_STD_LOGGER_NAMES = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "gunicorn.access",
)

_intercept_handler: Optional["InterceptHandler"] = None
_intercept_guard = threading.local()


def resolve_daily_log_path(log_dir: str, body: str) -> str:
    """
    按天复用的日志文件路径：{log_dir}/{YYYYmmdd}-{HHMMSS}-{body}.log

    - 先扫描目录中今日已创建的匹配文件（如前次进程重启残留），命中即复用最新一个；
    - 未命中则以当前时刻 O_CREAT|O_EXCL 抢占创建，输掉同秒竞态的进程重新扫描复用赢家文件。

    滚动备份（*.log.1、*.log.YYYY-MM-DD）与锁文件（.__*.lock）不以 .log 结尾，天然不会命中复用。

    :param log_dir: 日志目录
    :param body: 文件名主体（如 Worker-8520 / Beat-8520，Celery 专用；应用日志已改固定名不走此函数）
    :return: 完整日志文件路径
    """
    os.makedirs(log_dir, exist_ok=True)
    now = datetime.now()
    today = now.strftime("%Y%m%d")
    suffix = f"-{body}.log"
    existing = [
        name for name in os.listdir(log_dir)
        if name.startswith(f"{today}-") and name.endswith(suffix)
    ]
    if existing:
        return os.path.join(log_dir, sorted(existing)[-1])
    candidate = os.path.join(log_dir, f"{now.strftime('%Y%m%d-%H%M%S')}-{body}.log")
    try:
        fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.close(fd)
        return candidate
    except FileExistsError:
        pass
    existing = [
        name for name in os.listdir(log_dir)
        if name.startswith(f"{today}-") and name.endswith(suffix)
    ]
    if existing:
        return os.path.join(log_dir, sorted(existing)[-1])
    return candidate


def build_log_path() -> str:
    """
    应用日志路径：{OUTPUT_LOGS_DIR}/执行日志.log（固定名，不带日期前缀）

    日期由零点轮转拼接到归档后缀（执行日志.log.YYYY-MM-DD）；
    gunicorn master 与各 worker 共写同一文件，重启后继续复用。
    """
    return os.path.join(PROJECT_CONFIG.OUTPUT_LOGS_DIR, f"{PROJECT_CONFIG.LOGGER_FILE_NAME_PREFIX}.log")


def cleanup_expired_log_files() -> None:
    """
    按 LOGGER_RETENTION_DAYS 清理过期的应用与 Celery 日志（含滚动备份与孤儿锁文件）。

    判定用文件最后修改时间（mtime）：按天复用模式下文件名日期可能落后于内容日期
    （服务跨天仍写原文件），按文件名日期判定会误删仍活跃的日志。
    """
    retention_days = PROJECT_CONFIG.LOGGER_RETENTION_DAYS
    if retention_days <= 0:
        return
    celery_logs_dir = os.path.join(PROJECT_CONFIG.OUTPUT_LOGS_DIR, "celery_logs")
    targets = (
        (PROJECT_CONFIG.OUTPUT_LOGS_DIR, (f"{PROJECT_CONFIG.LOGGER_FILE_NAME_PREFIX}.log",)),
        (celery_logs_dir, ("-Worker-", "-Beat-", "celery_worker_", "celery_beat_")),
    )
    deadline = datetime.now() - timedelta(days=retention_days)
    for log_dir, markers in targets:
        if not os.path.isdir(log_dir):
            continue
        for name in os.listdir(log_dir):
            if not any(marker in name for marker in markers):
                continue
            path = os.path.join(log_dir, name)
            try:
                st = os.lstat(path)
            except OSError:
                continue
            if datetime.fromtimestamp(st.st_mtime) >= deadline:
                continue
            try:
                os.remove(path)
            except OSError:
                pass


def registry_file_handler() -> None:
    """
    注册文件处理器：INFO及以上全部写入同一日志文件。

    每天零点轮转（一天一个完整文件，不做大小截断），旧内容归档为 *.log.YYYY-MM-DD；
    跨进程轮转由 ConcurrentTimedRotatingFileHandler 的文件锁协调，多 worker 共写安全。
    """
    os.makedirs(PROJECT_CONFIG.OUTPUT_LOGS_DIR, exist_ok=True)
    handler = ConcurrentTimedRotatingFileHandler(
        filename=build_log_path(),
        when="midnight",
        backupCount=PROJECT_CONFIG.LOGGER_ROTATION_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(_HANDLER_PASSTHROUGH)
    logger.add(
        sink=handler,
        format=LOG_FORMAT,
        level="INFO",
        colorize=False,
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )


class InterceptHandler(logging.Handler):
    """
    将Python标准库logging.LogRecord重定向到Loguru

    - 使用logger.opt(depth=...)尽量保留真实调用栈（模块/函数/行号）
    - EXCLUDED_LOGGERS 过滤噪声或易引发递归的logger
    - _intercept_guard 在同一线程内避免emit重入
    """

    EXCLUDED_LOGGERS = frozenset({
        "asyncmy",
        "aiomysql",
        "asyncio",
        "tortoise",
        "tortoise.db_client",
        "uvicorn.asgi",
        "uvicorn.middleware.*",
        "python_multipart.*",
        "faker.factory",
        "httpcore.*",
        "passlib.*",
        "concurrent_log_handler",
        "portalocker",
        "loguru",
    })

    @classmethod
    def is_excluded(cls, name: str) -> bool:
        """支持精确匹配与 前缀.* 通配排除。"""
        for pattern in cls.EXCLUDED_LOGGERS:
            if pattern.endswith(".*") and name.startswith(pattern[:-1]):
                return True
            if name == pattern:
                return True
        return False

    @staticmethod
    def _map_level(record: logging.LogRecord) -> str:
        """stdlib levelno -> Loguru 级别名（不把所有记录都当成 INFO）。"""
        if record.levelno >= logging.ERROR:
            return "ERROR"
        if record.levelno >= logging.WARNING:
            return "WARNING"
        if record.levelno >= logging.INFO:
            return "INFO"
        return "DEBUG"

    def emit(self, record: logging.LogRecord) -> None:
        if self.is_excluded(record.name) or getattr(_intercept_guard, "active", False):
            return

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        _intercept_guard.active = True
        try:
            logger.opt(depth=depth, exception=record.exc_info).log(
                self._map_level(record),
                record.getMessage(),
            )
        finally:
            _intercept_guard.active = False


def _get_intercept_handler() -> InterceptHandler:
    """进程内单例 InterceptHandler，供 wire_standard_loggers 与 Gunicorn Logger 复用同一逻辑。"""
    global _intercept_handler
    if _intercept_handler is None:
        _intercept_handler = InterceptHandler()
    return _intercept_handler


def wire_standard_loggers() -> None:
    """
    将root及uvicorn/gunicorn相关logger的handler替换为InterceptHandler。

    调用时机：
    - loguru_logging() 末尾（import 应用时）；
    - Gunicorn post_worker_init（worker 内 Gunicorn 重新 setup 之后须再调一次）。

    须与 uvicorn.run(log_config=None, log_level=None) 及
    gunicorn_config.UvicornWorker 的 CONFIG_KWARGS 配合使用。
    """
    intercept = _get_intercept_handler()
    logging.root.handlers = [intercept]
    logging.root.setLevel(logging.NOTSET)
    for name in _WIRED_STD_LOGGER_NAMES:
        stdlog = logging.getLogger(name)
        stdlog.handlers = [intercept]
        stdlog.propagate = False
        stdlog.setLevel(logging.INFO)


def loguru_logging() -> logging.Logger:
    """
    初始化 Loguru：移除默认 handler，注册文件 sink、可选控制台 sink，并接管 stdlib。

    - SERVER_DEBUG=True：额外输出到 stdout（着色、diagnose）。
    - SERVER_DEBUG=False：仅写文件（生产常见）。
    """
    logger.remove()
    cleanup_expired_log_files()
    registry_file_handler()

    if PROJECT_CONFIG.SERVER_DEBUG:
        logger.add(
            sys.stdout,
            format=LOG_FORMAT,
            enqueue=True,
            backtrace=True,
            colorize=True,
            diagnose=True,
        )

    wire_standard_loggers()
    logger.configure(patcher=_inject_trace_context)
    return logger


LOGGER = logger
