# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : celery_config
@DateTime: 2026/1/3 22:09
"""
import os
from functools import lru_cache
from typing import Dict, Any

from pydantic import model_validator
from pydantic_settings import BaseSettings
from typing_extensions import Self

from backend.common import FileUtils
from backend.configure.project_config import PROJECT_CONFIG


class CeleryConfig(BaseSettings):
    CELERY_BEAT_SCHEDULER: str = "redbeat.schedulers:RedBeatScheduler"
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    CELERY_REDBEAT_REDIS_URL: str = ""
    CELERY_CONFIG: Dict[str, Any] = {}

    CELERY_LOG_DIR: str = ""
    CELERY_WORKER_LOG_FILE: str = ""
    CELERY_BEAT_LOG_FILE: str = ""
    CELERY_TASK_LOG_FILE: str = ""

    @model_validator(mode="after")
    def assemble_celery_settings(self) -> Self:
        project = PROJECT_CONFIG
        if project.SERVER_DEBUG:
            # 开发环境
            broker_db = project.DEV_CELERY_BROKER_DB
            backend_db = project.DEV_CELERY_BACKEND_DB
            redbeat_db = project.DEV_CELERY_REDBEAT_DB
        else:
            # 生产环境
            broker_db = project.CELERY_BROKER_DB
            backend_db = project.CELERY_BACKEND_DB
            redbeat_db = project.CELERY_REDBEAT_DB

        self.CELERY_BROKER_URL = project.build_redis_url(db=broker_db)
        self.CELERY_RESULT_BACKEND = project.build_redis_url(db=backend_db)
        self.CELERY_REDBEAT_REDIS_URL = project.build_redis_url(db=redbeat_db)

        # 队列名使用端口号拼接，确保多项目隔离
        server_port = project.SERVER_PORT
        default_queue = f"{server_port}_default"
        autotest_queue = f"{server_port}_autotest"

        self.CELERY_LOG_DIR = os.path.join(project.OUTPUT_LOGS_DIR, "celery_logs")
        os.makedirs(self.CELERY_LOG_DIR, exist_ok=True)
        self.CELERY_WORKER_LOG_FILE = os.path.join(self.CELERY_LOG_DIR, "celery_worker.log")
        self.CELERY_BEAT_LOG_FILE = os.path.join(self.CELERY_LOG_DIR, "celery_beat.log")
        self.CELERY_TASK_LOG_FILE = os.path.join(self.CELERY_LOG_DIR, "celery_task.log")

        task_imports = FileUtils.get_all_files(
            abspath=os.path.join(project.CELERY_SCHEDULER_DIR, "tasks"),
            return_full_path=False,
            return_precut_path="backend.celery_scheduler.tasks.",
            startswith="task",
            extension=".py",
            exclude_startswith="__",
            exclude_endswith="__.py",
        )

        self.CELERY_CONFIG = {
            "broker_url": self.CELERY_BROKER_URL,
            "result_backend": self.CELERY_RESULT_BACKEND,
            "timezone": "Asia/Shanghai",
            "enable_utc": True,
            "task_serializer": "json",
            "accept_content": ["json"],
            "result_serializer": "json",
            "result_accept_content": ["json"],
            "task_acks_late": True,
            "worker_prefetch_multiplier": 1,
            "task_reject_on_worker_lost": True,
            "result_expires": 3600,
            "result_persistent": True,
            "task_routes": {
                "backend.celery_scheduler.tasks.task_autotest_case.run_autotest_task": {
                    "queue": autotest_queue
                },
                "backend.celery_scheduler.tasks.task_execute_assign_case.execute_step_tree_task": {
                    "queue": autotest_queue
                },
            },
            "task_default_queue": default_queue,
            "task_default_exchange": default_queue,
            "task_default_exchange_type": "direct",
            "task_default_routing_key": default_queue,
            "worker_max_tasks_per_child": 1000,
            "worker_disable_rate_limits": False,
            "task_acks_on_failure_or_timeout": False,
            "task_time_limit": 3600,
            "task_soft_time_limit": 3300,
            "beat_scheduler": self.CELERY_BEAT_SCHEDULER,
            "redbeat_redis_url": self.CELERY_REDBEAT_REDIS_URL,
            # 显式置空阻断redbeat对broker_transport_options的回退透传：redbeat默认把该选项全量传给
            # redis-py连接构造，而visibility_timeout是kombu QoS层专有参数，redis-py不接受会导致beat启动崩溃
            "redbeat_redis_options": {},
            "redbeat_lock_timeout": 600,
            "redbeat_lock_renewal_interval": 420,
            "beat_schedule": {
                "scan-autotest-tasks": {
                    "task": (
                        "backend.celery_scheduler.tasks.task_autotest_case"
                        ".scan_and_dispatch_autotest_tasks"
                    ),
                    "schedule": 60.0,
                    "options": {"queue": default_queue},
                },
            },
            "worker_log_format": (
                "[%(asctime)s][%(levelname)s] -> [%(name)s][%(filename)s]"
                "[line:%(lineno)d] -> %(message)s"
            ),
            "worker_task_log_format": (
                "[%(asctime)s][%(levelname)s] -> [%(name)s][%(filename)s]"
                "[line:%(lineno)d] -> %(message)s"
            ),
            "worker_log_color": False,
            "imports": task_imports,
            "task_send_sent_event": True,
            "task_track_started": True,
            "task_ignore_result": False,
            "task_store_eager_result": False,
            "worker_send_task_events": True,
            "broker_connection_retry_on_startup": True,
            "broker_transport_options": {
                # 显式声明可见性超时：需大于全部任务硬时限最大值(run_autotest_task任务级28800)，
                # 防止长任务执行期间unacked消息被判失联重投导致重复执行
                "visibility_timeout": 36000,
            },
        }
        return self


@lru_cache(maxsize=1)
def get_celery_config() -> CeleryConfig:
    return CeleryConfig()


CELERY_CONFIG = get_celery_config()
