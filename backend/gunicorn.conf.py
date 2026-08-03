# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : gunicorn_config.py
@DateTime: 2025/1/12 19:41
"""
import logging

from gunicorn.glogging import Logger
from uvicorn.workers import UvicornWorker as _BaseUvicornWorker

from backend.configure import PROJECT_CONFIG


class InterceptGunicornLogger(Logger):
    """
    替换 Gunicorn 默认的 error/access 输出格式，统一走 Loguru
    """

    def setup(self, cfg) -> None:
        super().setup(cfg)
        from backend.configure.logging_config import InterceptHandler

        intercept = InterceptHandler()
        for stdlog in (self.error_log, self.access_log):
            stdlog.handlers = [intercept]
            stdlog.propagate = False
            stdlog.setLevel(logging.INFO)


class UvicornWorker(_BaseUvicornWorker):
    """
    ASGI Worker：在 Gunicorn 进程内运行 Uvicorn
    """

    CONFIG_KWARGS = {
        **getattr(_BaseUvicornWorker, "CONFIG_KWARGS", {}),
        "log_config": None,
        "log_level": None,
    }


# --- Gunicorn 识别的配置项（字符串形式便于 Gunicorn 根据路径动态加载类） ---
worker_class = f"{__name__}.UvicornWorker"
logger_class = f"{__name__}.InterceptGunicornLogger"

# 进程与并发（可根据机器 CPU 与业务调整）
workers = 4
threads = 4
bind = f"{PROJECT_CONFIG.SERVER_HOST}:{PROJECT_CONFIG.SERVER_PORT}"

# False：每个 worker 独立 import 应用，避免 preload 与 fork 下部分资源状态共享问题
preload_app = False

#  worker 处理一定请求后重启，缓解内存泄漏；jitter 避免同时重启
max_requests = 1000
max_requests_jitter = 200

# 仍输出到 stdout/stderr，但经 InterceptGunicornLogger 已是 Loguru 格式
accesslog = "-"
errorlog = "-"
loglevel = "info"
timeout = 300


def post_worker_init(worker) -> None:
    """
    Worker 进程初始化完成后的钩子。

    Gunicorn:Logger.setup() 可能在应用 import 之后再次覆盖 handler
    此处重新 wire_standard_loggers() 保证 uvicorn/gunicorn 日志只走 Loguru

    :param worker: Gunicorn Worker 实例（本函数未使用，签名由 Gunicorn 约定）
    """
    from backend.configure.logging_config import wire_standard_loggers

    wire_standard_loggers()
