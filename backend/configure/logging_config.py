# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : logging_config.py
@DateTime: 2025/1/16 15:33
"""
import logging.config
from datetime import datetime
from typing import Dict, Any

from concurrent_log_handler import ConcurrentRotatingFileHandler

from backend import PROJECT_CONFIG


def get_log_filename(log_type: str) -> str:
    """生成动态日志文件名"""
    return f'{PROJECT_CONFIG.OUTPUT_LOGS_DIR}/{datetime.now().strftime("%Y%m%d")}_{log_type}_执行日志.log'


# 可以使用 ConcurrentLogHandler 来处理多进程环境中的日志记录。这个处理器可以确保在多进程环境中安全地写入日志文件。
DEFAULT_LOGGING_CONFIG: Dict[str, Any] = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'configure.logging_config.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'configure.logging_config.RequireDebugTrue',
        },
    },
    'formatters': {
        'main_formatter': {
            "format": "[%(asctime)s][%(levelname)s] -> [%(name)s][%(filename)s][line:%(lineno)d] -> %(message)s",
            'default': '[%(levelname)s]:[%(name)s]: %(message)s (%(asctime)s; %(filename)s:%(lineno)d)',
            'datefmt': "%Y-%m-%d %H:%M:%S",
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'main_formatter',
        },
        'production_file': {
            'level': 'INFO',
            # 'class': 'logging.handlers.RotatingFileHandler',
            'class': 'concurrent_log_handler.ConcurrentRotatingFileHandler',
            # 'filename': f'{PROJECT_CONFIG.OUTPUT_LOGS_DIR}/{datetime.now().strftime("%Y%m%d")}_INFO_执行日志.log',
            'filename': get_log_filename("INFO"),  # 使用动态文件名
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 10,
            'formatter': 'main_formatter',
            'filters': ['require_debug_false'],
        },
        'debug_file': {
            'level': 'DEBUG',
            # 'class': 'logging.handlers.RotatingFileHandler',
            'class': 'concurrent_log_handler.ConcurrentRotatingFileHandler',
            # 'filename': f'{PROJECT_CONFIG.OUTPUT_LOGS_DIR}/{datetime.now().strftime("%Y%m%d")}_DEBUG_执行日志.log',
            'filename': get_log_filename("DEBUG"),  # 使用动态文件名
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 10,
            'formatter': 'main_formatter',
            'filters': ['require_debug_true'],
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'production_file', 'debug_file'],
            'level': "DEBUG",
            'propagate': True,
        },

    }
}


class RequireDebugFalse(logging.Filter):
    def filter(self, record):
        return not getattr(PROJECT_CONFIG, 'SERVER_DEBUG', True)


class RequireDebugTrue(logging.Filter):
    def filter(self, record):
        return getattr(PROJECT_CONFIG, 'SERVER_DEBUG', False)
