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
from backend import PROJECT_CONFIG

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
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': f'{PROJECT_CONFIG.OUTPUT_LOGS_DIR}/{datetime.now().strftime("%Y%m%d")}_INFO_执行日志.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 10,
            'formatter': 'main_formatter',
            'filters': ['require_debug_false'],
        },
        'debug_file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': f'{PROJECT_CONFIG.OUTPUT_LOGS_DIR}/{datetime.now().strftime("%Y%m%d")}_DEBUG_执行日志.log',
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
        },

    }
}


class RequireDebugFalse(logging.Filter):
    def filter(self, record):
        return not PROJECT_CONFIG.SERVER_DEBUG


class RequireDebugTrue(logging.Filter):
    def filter(self, record):
        return PROJECT_CONFIG.SERVER_DEBUG
