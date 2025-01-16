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


class ProjectConfig:
    # 项目描述
    APP_VERSION = "0.1.1"
    APP_TITLE = "KRUN - 测管平台"
    APP_DESCRIPTION = """
    KRUN 测管平台是一款基于 Python 的 FastAPI 框架开发的实用型测试管理系统，旨在满足软件测试工作的日常需求。
    它专注于提供最实用的功能，涵盖测试用例管理、测试环境配置、测试任务调度以及测试报告生成等多个关键环节。
    用户可以轻松导入和导出测试用例，灵活调整测试计划，根据不同的测试阶段和项目需求对测试任务进行精确管理。
    凭借 FastAPI 的高效性能，平台能够迅速响应各种操作，确保测试工作的连贯性和高效性。
    同时，系统还支持历史测试数据的回溯和对比，帮助团队持续优化测试流程，为软件质量的提升提供强大支持。
    """
    APP_DOCS_URL = "/krun/docs"
    APP_REDOC_URL = "/krun/redoc"
    APP_OPENAPI_URL = "/krun/openapi_url"
    APP_OPENAPI_JS_URL = "/static/openapi/swagger-ui-bundle.js"
    APP_OPENAPI_CSS_URL = "/static/openapi/swagger-ui.css"
    APP_OPENAPI_FAVICON_URL = "/static/openapi/favicon.png"

    # 调试配置
    SERVER_APP = "backend_main:app"
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
