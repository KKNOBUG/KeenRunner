# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : project_config.py
@DateTime: 2025/1/15 16:08
"""
import os.path
import platform
from typing import List, Dict, Any

from pydantic_settings import BaseSettings

from backend.common.file_utils import FileUtils
from backend.common.shell_utils import ShellUtils


class ProjectConfig(BaseSettings):
    # 项目描述
    APP_VERSION: str = "0.1.1"
    APP_TITLE: str = "KRUN - 测管平台"
    APP_DESCRIPTION: str = """
    KRUN 测管平台是一款基于 Python 的 FastAPI 框架开发的实用型测试管理系统，旨在满足软件测试工作的日常需求。
    它专注于提供最实用的功能，涵盖测试用例管理、测试环境配置、测试任务调度以及测试报告生成等多个关键环节。
    用户可以轻松导入和导出测试用例，灵活调整测试计划，根据不同的测试阶段和项目需求对测试任务进行精确管理。
    凭借 FastAPI 的高效性能，平台能够迅速响应各种操作，确保测试工作的连贯性和高效性。
    同时，系统还支持历史测试数据的回溯和对比，帮助团队持续优化测试流程，为软件质量的提升提供强大支持。
    """
    APP_DOCS_URL: str = "/krun/docs"
    APP_REDOC_URL: str = "/krun/redoc"
    APP_OPENAPI_URL: str = "/krun/openapi_url"
    APP_OPENAPI_JS_URL: str = "/static/swagger-ui/swagger-ui-bundle.js"
    APP_OPENAPI_CSS_URL: str = "/static/swagger-ui/swagger-ui.css"
    APP_OPENAPI_FAVICON_URL: str = "/static/swagger-ui/favicon-32x32.png"
    APP_OPENAPI_VERSION: str = "3.0.2"

    # 调试配置
    SERVER_APP: str = "backend_main:app"
    SERVER_HOST: str = ShellUtils.acquire_localhost()
    SERVER_SYSTEM: str = platform.system()
    SERVER_PORT: int = 8518
    SERVER_DEBUG: bool = SERVER_SYSTEM != "Linux"  # Windows | Linux | Darwin
    SERVER_DELAY: int = 5

    # 安全认证配置
    AUTH_SECRET_KEY: str = "3488a63e1765035d386f05409663f55c83bfae3b3c61a932744b20ad14244dcf"  # openssl rand -hex 32
    AUTH_JWT_ALGORITHM: str = "HS256"
    AUTH_JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 day

    # 日志相关参数配置
    # 文件名称前缀
    LOGGER_FILE_NAME_PREFIX: str = "执行日志"
    # 是否开启文件名称后缀（是否增加年月日标识）
    LOGGER_FILE_NAME_SUFFIX: bool = True
    # 日志文件轮转频率
    LOGGER_TIMED_ROTATING: str = "天"
    # 保留的备份日志文件的数量，当超过超过这个数量时，最旧的备份文件将被删除，默认值为0，标识不保留备份
    LOGGER_BACKUP_COUNT: int = 0
    # 文件大小轮转
    LOGGER_ROTATION: str = '10 MB'
    # 保留30天
    LOGGER_RETENTION: str = '30 days'
    # 压缩格式
    LOGGER_COMPRESSION: str = "zip"

    # 项目路径相关配置
    PROJECT_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    APPLICATIONS_DIR: str = os.path.abspath(os.path.join(PROJECT_ROOT, "applications"))
    COMMON_DIR: str = os.path.abspath(os.path.join(PROJECT_ROOT, "common"))
    CONFIGURE_DIR: str = os.path.abspath(os.path.join(PROJECT_ROOT, "configure"))
    CORE_DIR: str = os.path.abspath(os.path.join(PROJECT_ROOT, "core"))
    DECORATORS_DIR: str = os.path.abspath(os.path.join(PROJECT_ROOT, "decorators"))
    ENUMS_DIR: str = os.path.abspath(os.path.join(PROJECT_ROOT, "enums"))
    OUTPUT_DIR: str = os.path.abspath(os.path.join(PROJECT_ROOT, "output"))
    OUTPUT_LOGS_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "logs"))
    OUTPUT_UPLOAD_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "upload"))
    OUTPUT_DOWNLOAD_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "download"))
    OUTPUT_MEDIA_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "media"))
    OUTPUT_DATAGRAM_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "datagram"))
    OUTPUT_JMX_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "jmx"))
    OUTPUT_XLSX_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "xlsx"))
    OUTPUT_DOCS_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "docs"))
    SERVICES_DIR: str = os.path.abspath(os.path.join(PROJECT_ROOT, "services"))
    STATIC_DIR: str = os.path.abspath(os.path.join(PROJECT_ROOT, "static"))
    STATIC_IMG_DIR: str = os.path.abspath(os.path.join(STATIC_DIR, "image"))
    MIGRATION_DIR: str = os.path.abspath(os.path.join(PROJECT_ROOT, "migrations"))

    # 跨域配置
    CORS_ORIGINS: List[str] = [
        "http://localhost",
        "http://localhost:5000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://localhost:8515",
        "*",
    ]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    CORS_EXPOSE_METHODS: List[str] = ["*"]
    CORS_MAX_AGE: int = 600

    # 应用注册
    APPLICATIONS_MODULE: str = "backend.applications"
    APPLICATIONS_INSTALLED: List[str] = FileUtils.get_all_dirs(
        abspath=APPLICATIONS_DIR,
        return_full_path=False,
        exclude_startswith="__",
        exclude_endswith="__",
    )

    @property
    def APPLICATIONS_MODELS(self) -> List[str]:
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
    # DATABASE_USERNAME: str = quote("admin@usr")
    # DATABASE_PASSWORD: str = quote("admin@Pwd123")
    DATABASE_USERNAME: str = "root"
    DATABASE_PASSWORD: str = "root"
    DATABASE_HOST: str = "10.211.55.3"
    # DATABASE_HOST: str = "43.156.105.196"
    DATABASE_PORT: str = "3306"
    DATABASE_NAME: str = "krun"
    DATABASE_URL: str = f"mysql://{DATABASE_USERNAME}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}?charset=utf8mb4&time_zone=+08:00"
    DATABASE_CONNECTIONS: Dict[str, Any] = {
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
                "autocommit": True  # 数据库是否开启SQL语句自动提交
            }
        }
    }

    # Redis 配置
    REDIS_USERNAME: str = ""
    REDIS_PASSWORD: str = ""
    REDIS_HOST: str = ""
    REDIS_PORT: str = ""
    REDIS_URL: str = f"redis://{REDIS_USERNAME}:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"


PROJECT_CONFIG = ProjectConfig()
