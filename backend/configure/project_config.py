# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : project_config.py
@DateTime: 2025/1/15 16:08
"""
import os.path

from backend.common.shell_utils import ShellUtils
from backend.core.decorators.block import singleton


@singleton
class ProjectConfig:
    # 项目描述
    APP_VERSION = "0.0.1"
    APP_TITLE = "FastAPI Application"
    APP_DESCRIPTION = "FastAPI Application"
    APP_DOCS_URL = "/docs"
    APP_REDOC_URL = "/redoc"
    APP_SWAGGER_URL = "/openapi_url"

    # 调试配置
    SERVER_APP = "backend.main:app"
    SERVER_HOST = ShellUtils.acquire_localhost()
    SERVER_PORT = 8518
    SERVER_DEBUG = True
    SERVER_DELAY = 5

    # 日志相关参数配置
    # 文件名称前缀
    LOGGER_FILE_NAME_PREFIX = "执行日志"
    # 是否开启文件名称后缀（是否增加年月日标识）
    LOGGER_FILE_NAME_SUFFIX = True
    # 日志文件轮转频率
    LOGGER_TIMED_ROTATING = "天"
    # 保留的备份日志文件的数量，当超过超过这个数量时，最旧的备份文件将被删除，默认值为0，标识不保留备份
    LOGGER_BACKUP_COUNT = 0

    # 项目路径相关配置
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    APPLICATIONS_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "applications"))
    COMMON_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "common"))
    CONFIGURE_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "configure"))
    CORE_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "core"))
    DECORATORS_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "decorators"))
    ENUMS_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "enums"))
    OUTPUT_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "output"))
    OUTPUT_LOGS_DIR = os.path.abspath(os.path.join(OUTPUT_DIR, "logs"))
    OUTPUT_UPLOAD_DIR = os.path.abspath(os.path.join(OUTPUT_DIR, "upload"))
    OUTPUT_DOWNLOAD_DIR = os.path.abspath(os.path.join(OUTPUT_DIR, "download"))
    OUTPUT_MEDIA_DIR = os.path.abspath(os.path.join(OUTPUT_DIR, "media"))
    OUTPUT_DATAGRAM_DIR = os.path.abspath(os.path.join(OUTPUT_DIR, "datagram"))
    OUTPUT_JMX_DIR = os.path.abspath(os.path.join(OUTPUT_DIR, "jmx"))
    OUTPUT_XLSX_DIR = os.path.abspath(os.path.join(OUTPUT_DIR, "xlsx"))
    SERVICES_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "services"))
    STATIC_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "static"))


PROJECT_CONFIG = ProjectConfig()
