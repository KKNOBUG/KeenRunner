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

from pydantic_settings import BaseSettings

from backend.common.file_utils import FileUtils
from backend.configure.project_config import PROJECT_CONFIG


class CeleryConfig(BaseSettings):
    # Celery Broker配置（Redis作为消息队列）
    # 使用不同的Redis数据库避免冲突
    PROJECT_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    APPLICATIONS_DIR: str = os.path.abspath(os.path.join(PROJECT_ROOT, "applications"))
    CELERY_SCHEDULER_DIR: str = os.path.abspath(os.path.join(PROJECT_ROOT, "celery_scheduler"))
    CELERY_BROKER_URL: str = (
        f"redis://"
        f"{PROJECT_CONFIG.REDIS_USERNAME + ':' if PROJECT_CONFIG.REDIS_USERNAME else ''}"
        f"{PROJECT_CONFIG.REDIS_PASSWORD + '@' if PROJECT_CONFIG.REDIS_PASSWORD else ''}"
        f"{PROJECT_CONFIG.REDIS_HOST or 'localhost'}:"
        f"{PROJECT_CONFIG.REDIS_PORT or '6379'}/1"
    )

    # Celery Result Backend配置（Redis作为结果存储）
    CELERY_RESULT_BACKEND: str = (
        f"redis://"
        f"{PROJECT_CONFIG.REDIS_USERNAME + ':' if PROJECT_CONFIG.REDIS_USERNAME else ''}"
        f"{PROJECT_CONFIG.REDIS_PASSWORD + '@' if PROJECT_CONFIG.REDIS_PASSWORD else ''}"
        f"{PROJECT_CONFIG.REDIS_HOST or 'localhost'}:"
        f"{PROJECT_CONFIG.REDIS_PORT or '6379'}/2"
    )

    # Celery Beat调度器配置（使用Redis Beat解决多服务器单点问题）
    CELERY_BEAT_SCHEDULER: str = "redbeat.schedulers:RedBeatScheduler"
    CELERY_REDBEAT_REDIS_URL: str = (
        f"redis://"
        f"{PROJECT_CONFIG.REDIS_USERNAME + ':' if PROJECT_CONFIG.REDIS_USERNAME else ''}"
        f"{PROJECT_CONFIG.REDIS_PASSWORD + '@' if PROJECT_CONFIG.REDIS_PASSWORD else ''}"
        f"{PROJECT_CONFIG.REDIS_HOST or 'localhost'}:"
        f"{PROJECT_CONFIG.REDIS_PORT or '6379'}/3"
    )

    # Celery配置字典
    CELERY_CONFIG: Dict[str, Any] = {
        # 基础配置
        "broker_url": CELERY_BROKER_URL,
        "result_backend": CELERY_RESULT_BACKEND,
        "timezone": "Asia/Shanghai",
        "enable_utc": True,
        "task_serializer": "json",
        "accept_content": ["json"],
        "result_serializer": "json",
        "result_accept_content": ["json"],

        # 任务执行配置
        "task_acks_late": True,  # 任务完成后才确认，避免任务丢失
        "worker_prefetch_multiplier": 1,  # 每个worker预取任务数，避免任务堆积
        "task_reject_on_worker_lost": True,  # worker丢失时重新分配任务

        # 结果存储配置
        "result_expires": 3600,  # 结果过期时间（秒）
        "result_persistent": True,  # 持久化结果

        # 任务配置
        "task_default_queue": "default",
        "task_default_exchange": "default",
        "task_default_exchange_type": "direct",
        "task_default_routing_key": "default",

        # 并发配置（解决多进程冲突）
        "worker_max_tasks_per_child": 1000,  # 每个worker子进程执行任务数上限，防止内存泄漏
        "worker_disable_rate_limits": False,  # 启用速率限制

        # 任务重试配置
        "task_acks_on_failure_or_timeout": False,  # 任务失败或超时后不自动确认
        "task_time_limit": 3600,  # 任务硬超时时间（秒）
        "task_soft_time_limit": 3300,  # 任务软超时时间（秒）

        # Beat调度器配置（使用Redis Beat解决多服务器单点问题）
        "beat_scheduler": CELERY_BEAT_SCHEDULER,
        "redbeat_redis_url": CELERY_REDBEAT_REDIS_URL,
        "redbeat_lock_timeout": 120,  # Beat锁超时时间（秒），防止多Beat进程冲突
        "redbeat_lock_renewal_interval": 90,

        # 日志配置
        "worker_log_format": "[%(asctime)s][%(levelname)s] -> [%(name)s][%(filename)s][line:%(lineno)d] -> %(message)s",
        "worker_task_log_format": "[%(asctime)s][%(levelname)s] -> [%(name)s][%(filename)s][line:%(lineno)d] -> %(message)s",
        "worker_log_color": False,  # 禁用日志颜色（文件日志不需要）

        # 任务导入配置
        "imports": [
            tasks
            for tasks in FileUtils.get_all_files(
                abspath=os.path.join(CELERY_SCHEDULER_DIR, "tasks"),
                return_full_path=False,
                return_precut_path=f"celery_scheduler.tasks.",
                startswith="task",
                extension=".py",
                exclude_startswith="__",
                exclude_endswith="__.py",
            )
        ],

        # 任务发送配置（解决多服务器冲突）
        "task_send_sent_event": True,  # 发送任务事件
        "task_track_started": True,  # 跟踪任务开始

        # 任务结果配置
        "task_ignore_result": False,  # 不忽略任务结果
        "task_store_eager_result": False,  # 不存储eager模式的结果

        # 安全配置
        "worker_send_task_events": True,  # 发送任务事件
        "broker_connection_retry_on_startup": True,  # 发送任务事件
    }

    # Celery日志文件路径
    CELERY_LOG_DIR: str = os.path.join(PROJECT_CONFIG.OUTPUT_LOGS_DIR, "celery")
    CELERY_WORKER_LOG_FILE: str = os.path.join(CELERY_LOG_DIR, "celery_worker.log")
    CELERY_BEAT_LOG_FILE: str = os.path.join(CELERY_LOG_DIR, "celery_beat.log")
    CELERY_TASK_LOG_FILE: str = os.path.join(CELERY_LOG_DIR, "celery_task.log")

    # 确保日志目录存在
    os.makedirs(CELERY_LOG_DIR, exist_ok=True)


@lru_cache(maxsize=1)
def get_celery_config():
    return CeleryConfig()


CELERY_CONFIG = get_celery_config()
