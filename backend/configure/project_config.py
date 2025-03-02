# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : project_config.py
@DateTime: 2025/1/15 16:08
"""
import os.path
from pathlib import Path

from backend.common.file_utils import FileUtils
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
    APP_OPENAPI_JS_URL = "/static/swagger-ui/swagger-ui-bundle.js"
    APP_OPENAPI_CSS_URL = "/static/swagger-ui/swagger-ui.css"
    APP_OPENAPI_FAVICON_URL = "/static/swagger-ui/favicon-32x32.png"
    APP_OPENAPI_VERSION = "3.0.2"

    # 调试配置
    SERVER_APP = "backend_main:app"
    SERVER_HOST = ShellUtils.acquire_localhost()
    SERVER_PORT = 8518
    SERVER_DEBUG = True
    SERVER_DELAY = 5

    # 安全认证配置
    AUTH_SECRET_KEY: str = "3488a63e1765035d386f05409663f55c83bfae3b3c61a932744b20ad14244dcf"  # openssl rand -hex 32
    AUTH_JWT_ALGORITHM: str = "HS256"
    AUTH_JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 day

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
    OUTPUT_DOCS_DIR = os.path.abspath(os.path.join(OUTPUT_DIR, "docs"))
    SERVICES_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "services"))
    STATIC_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "static"))
    STATIC_IMG_DIR = os.path.abspath(os.path.join(STATIC_DIR, "image"))
    MIGRATION_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "migrations"))

    # 跨域配置
    CORS_ORIGINS = [
        "http://localhost",
        "http://localhost:5000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://localhost:8515",
        "*",
    ]
    CORS_ALLOW_CREDENTIALS = True
    CORS_ALLOW_METHODS = ["*"]
    CORS_ALLOW_HEADERS = ["*"]
    CORS_EXPOSE_METHODS = ["*"]
    CORS_MAX_AGE = 600

    # 应用注册
    APPLICATIONS_MODULE = "backend.applications"
    APPLICATIONS_INSTALLED = FileUtils.get_all_dirs(
        abspath=APPLICATIONS_DIR,
        return_full_path=False,
        exclude_startswith="__",
        exclude_endswith="__",
    )

    @property
    def APPLICATIONS_MODELS(self):
        models = [
            models
            for app in self.APPLICATIONS_INSTALLED
            for models in FileUtils.get_all_files(
                abspath=os.path.join(self.APPLICATIONS_DIR, app, "models"),
                return_full_path=False,
                return_precut_path=f"{self.APPLICATIONS_MODULE}.{app}.models.",
                endswith="model",
                exclude_startswith="__",
                exclude_endswith="__.py"
            )
        ]
        models.append("aerich.models")
        return models

    # 数据库配置
    # DATABASE_USERNAME = quote("admin@usr")
    # DATABASE_PASSWORD = quote("admin@Pwd123")
    DATABASE_USERNAME = "root"
    DATABASE_PASSWORD = "root"
    DATABASE_HOST = "10.211.55.3"
    # DATABASE_HOST = "43.156.105.196"
    DATABASE_PORT = "3306"
    DATABASE_NAME = "krun"
    DATABASE_URL = f"mysql://{DATABASE_USERNAME}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}?charset=utf8mb4&time_zone=+08:00"
    DATABASE_CONNECTIONS = {
        "default": {
            "engine": "tortoise.backends.mysql",  # 使用mysql引擎
            "db_url": DATABASE_URL,
            "credentials": {
                "host": DATABASE_HOST,  # 数据库地址
                "port": DATABASE_PORT,  # 数据库端口
                "user": DATABASE_USERNAME,  # 数据库账户
                "password": DATABASE_PASSWORD,  # 数据库密码
                "database": DATABASE_NAME,  # 数据库名称
                "minsize": 10,  # 连接池最小连接数
                "maxsize": 40,  # 连接池最大连接数
                "charset": "utf8mb4",  # 数据库字符编码
                "echo": False,  # 数据库是否开启SQL语句回响
                "autocommit": False  # 数据库是否开启SQL语句自动提交
            }
        }
    }

    # Redis 配置
    REDIS_USERNAME = ""
    REDIS_PASSWORD = ""
    REDIS_HOST = ""
    REDIS_PORT = ""
    REDIS_URL = f"redis://{REDIS_USERNAME}:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"


PROJECT_CONFIG = ProjectConfig()
