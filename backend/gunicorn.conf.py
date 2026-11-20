# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : gunicorn_config.py
@DateTime: 2025/1/12 19:41
"""
import logging

from gunicorn.glogging import Logger
from uvicorn.workers import UvicornWorker as _BaseUvicornWorker

from backend.configure import PROJECT_CONFIG


class InterceptGunicornLogger(Logger):
    """
    Gunicorn 日志策略：自身运行日志（启动/worker管理）丢弃，只保留 HTTP 请求日志。

    UvicornWorker 下 HTTP 访问实际由 uvicorn.access 发出（经 InterceptHandler 落应用日志），
    gunicorn.access 不会触发；gunicorn.error 置 NullHandler 避免混入业务日志。
    """

    def setup(self, cfg) -> None:
        super().setup(cfg)
        from backend.configure.logging_config import InterceptHandler

        self.error_log.handlers = [logging.NullHandler()]
        self.error_log.propagate = False
        self.access_log.handlers = [InterceptHandler()]
        self.access_log.propagate = False
        self.access_log.setLevel(logging.INFO)


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

# 输出目标由 InterceptGunicornLogger.setup 接管：error 丢弃、access 走 Loguru（实际 HTTP 访问由 uvicorn.access 记录）
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
