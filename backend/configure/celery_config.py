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
        self.CELERY_BROKER_URL = project.build_redis_url(db=1)
        self.CELERY_RESULT_BACKEND = project.build_redis_url(db=2)
        self.CELERY_REDBEAT_REDIS_URL = project.build_redis_url(db=3)

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
                    "queue": "autotest_queue"
                },
                "backend.celery_scheduler.tasks.task_execute_assign_case.execute_step_tree_task": {
                    "queue": "autotest_queue"
                },
            },
            "task_default_queue": "default",
            "task_default_exchange": "default",
            "task_default_exchange_type": "direct",
            "task_default_routing_key": "default",
            "worker_max_tasks_per_child": 1000,
            "worker_disable_rate_limits": False,
            "task_acks_on_failure_or_timeout": False,
            "task_time_limit": 3600,
            "task_soft_time_limit": 3300,
            "beat_scheduler": self.CELERY_BEAT_SCHEDULER,
            "redbeat_redis_url": self.CELERY_REDBEAT_REDIS_URL,
            "redbeat_lock_timeout": 600,
            "redbeat_lock_renewal_interval": 420,
            "beat_schedule": {
                "scan-autotest-tasks": {
                    "task": (
                        "backend.celery_scheduler.tasks.task_autotest_case"
                        ".scan_and_dispatch_autotest_tasks"
                    ),
                    "schedule": 60.0,
                    "options": {"queue": "default"},
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
        }
        return self


@lru_cache(maxsize=1)
def get_celery_config() -> CeleryConfig:
    return CeleryConfig()


CELERY_CONFIG = get_celery_config()
