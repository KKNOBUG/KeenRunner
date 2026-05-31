# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : logging_config.py
@DateTime: 2025/1/16 15:33

统一日志方案：Loguru（LOGGER）+ InterceptHandler 接管标准库 logging。

架构说明
--------
1. 应用与第三方库仍使用 logging.getLogger(...) 或 uvicorn/gunicorn 内置 logger
2. InterceptHandler 将上述记录转发到 Loguru，控制台/文件均使用 LOG_FORMAT
3. 文件落盘经 ConcurrentRotatingFileHandler：多 Gunicorn worker 可共写同一文件
   按 PROJECT_CONFIG.LOGGER_ROTATION 大小轮转，保留 LOGGER_ROTATION_BACKUP_COUNT 个
   备份 xxx.log.1 不压缩。

落盘文件命名规则：
--------------------
INFO 及以上、低于 ERROR： {OUTPUT_LOGS_DIR}/{YYYYMMDD}_INFO_执行日志.log
ERROR 及以上： {OUTPUT_LOGS_DIR}/{YYYYMMDD}_ERROR_执行日志.log
"""
import logging
import os
import re
import sys
import threading
from datetime import datetime
from typing import Optional

from concurrent_log_handler import ConcurrentRotatingFileHandler
from loguru import logger

from backend.common.request_context import get_parent_span_id, get_span_id, get_trace_id
from backend.configure.project_config import PROJECT_CONFIG

# 自定义日志格式(控制台与文件共用；文件设置colorize=False)
# trace_id（X-Trace-ID）/ span_id（X-Span-ID）由 patcher 注入，未绑定则为 -
LOG_FORMAT = (
    # 时间信息
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    # 日志级别，居中对齐
    "<level>{level: ^8}</level> | "
    # 分布式追踪：TraceID（一次前端操作） + SpanID（当前入站/任务）
    "<yellow>{extra[trace_id]}</yellow>:<yellow>{extra[span_id]}</yellow> | "
    # 进程和线程信息
    "process [<cyan>{process}</cyan>]:<cyan>{thread}</cyan> | "
    # 文件、函数和行号
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> -> "
    # 日志消息
    "<level>{message}</level>"
)


def _inject_trace_context(record: dict) -> None:
    """Loguru patcher：每条日志自动附带 trace_id / span_id。"""
    extra = record["extra"]
    if not extra.get("trace_id"):
        extra["trace_id"] = get_trace_id()
    if not extra.get("span_id"):
        extra["span_id"] = get_span_id()
    parent = get_parent_span_id()
    if parent and not extra.get("parent_span_id"):
        extra["parent_span_id"] = parent


# 写入 ConcurrentRotatingFileHandler 时只落纯文本 message，格式由 Loguru format= 负责
_HANDLER_PASSTHROUGH = logging.Formatter("%(message)s")

# 部署在 Gunicorn + Uvicorn 下需要接管的 logger 名称（与 wire_standard_loggers 一致）
_WIRED_STD_LOGGER_NAMES = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "gunicorn",
    "gunicorn.error",
    "gunicorn.access",
)

_intercept_handler: Optional["InterceptHandler"] = None
# 防止 InterceptHandler -> Loguru -> 再次触发 stdlib logging 的递归
_intercept_guard = threading.local()


def rotation_to_max_bytes(rotation: str) -> int:
    """
    将 project_config 中的 LOGGER_ROTATION 字符串转为 ConcurrentRotatingFileHandler 的 maxBytes
    :param rotation: 文件大小
    :return:
    """
    text = rotation.strip().upper()
    match = re.match(r"^(\d+(?:\.\d+)?)\s*(B|KB|MB|GB)?$", text)
    if not match:
        raise ValueError(f"无法解析 LOGGER_ROTATION: {rotation!r}，示例: 200 MB")
    value = float(match.group(1))
    unit = (match.group(2) or "B").upper()
    return int(value * {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3}[unit])


def build_log_path(level_label: str) -> str:
    """
    按日期与级别标签生成当日日志文件路径
    :param level_label: 文件名中的级别段，如 INFO、ERROR
    :return:
    """
    prefix = PROJECT_CONFIG.LOGGER_FILE_NAME_PREFIX
    day = datetime.now().strftime("%Y%m%d")
    return os.path.join(PROJECT_CONFIG.OUTPUT_LOGS_DIR, f"{day}-{level_label}-{prefix}.log")


def registry_file_handler(*, level_label: str, min_level: str, max_level: Optional[str] = None) -> None:
    """
    注册一个按级别分流的文件处理器

    :param level_label: 文件名中的级别段，如 INFO、ERROR
    :param min_level: Loguru 最低级别
    :param max_level: 若指定，则只记录严格低于该级别的日志
    """
    os.makedirs(PROJECT_CONFIG.OUTPUT_LOGS_DIR, exist_ok=True)
    handler = ConcurrentRotatingFileHandler(
        filename=build_log_path(level_label),
        maxBytes=rotation_to_max_bytes(PROJECT_CONFIG.LOGGER_ROTATION),
        backupCount=PROJECT_CONFIG.LOGGER_ROTATION_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(_HANDLER_PASSTHROUGH)

    kwargs = dict(
        sink=handler,
        format=LOG_FORMAT,
        level=min_level,
        colorize=False,
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )
    if max_level is not None:
        ceiling = logger.level(max_level).no
        kwargs["filter"] = lambda record: record["level"].no < ceiling
    logger.add(**kwargs)


class InterceptHandler(logging.Handler):
    """
    将Python标准库logging.LogRecord重定向到Loguru

    - 使用 logger.opt(depth=...) 尽量保留真实调用栈（模块/函数/行号）
    - EXCLUDED_LOGGERS 过滤噪声或易引发递归的 logger（如 loguru、文件锁库）
    - _intercept_guard 在同一线程内避免 emit 重入
    """

    EXCLUDED_LOGGERS = frozenset({
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

        # 跳过 logging 内部栈帧，使 Loguru 显示的调用位置指向业务代码
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
    将 root 及 uvicorn/gunicorn 相关 logger 的 handler 替换为 InterceptHandler。

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


def loguru_logging() -> logger:
    """
    初始化 Loguru：移除默认 handler，注册文件 sink、可选控制台 sink，并接管 stdlib。

    - SERVER_DEBUG=True：额外输出到 stdout（着色、diagnose）。
    - SERVER_DEBUG=False：仅写文件（生产常见）。
    """
    logger.remove()

    registry_file_handler(level_label="ERROR", min_level="ERROR")
    registry_file_handler(level_label="INFO", min_level="INFO", max_level="ERROR")

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


# 模块加载时完成一次性配置；各 Gunicorn worker 为独立进程，会各自 import 一次
LOGGER = loguru_logging()
