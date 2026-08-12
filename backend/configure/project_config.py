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
from functools import lru_cache
from typing import List, Dict, Any
from urllib.parse import quote_plus

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self

from backend.common import FileUtils, ShellUtils

_BACKEND_PROJECT_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_BACKEND_PROJECT_CONF: str = os.path.join(_BACKEND_PROJECT_ROOT, ".env")


class ProjectConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_PROJECT_CONF,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

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
    APP_OPENAPI_JS_URL_REDOC: str = "/static/redoc/bundles/redoc.standalone.js"
    APP_OPENAPI_FAVICON_URL_REDOC: str = "/static/redoc/favicon.png"
    APP_OPENAPI_VERSION: str = "3.0.2"

    # 调试配置
    SERVER_APP: str = "backend_main:app"
    SERVER_HOST: str = ShellUtils.acquire_localhost()
    SERVER_SYSTEM: str = platform.system()
    SERVER_PORT: int = 8519
    SERVER_DEBUG: bool = SERVER_SYSTEM != "Linux"  # Windows | Linux | Darwin
    SERVER_DELAY: int = 5

    # 安全认证配置（须在 backend/.env 或环境变量中配置）
    AUTH_SECRET_KEY: str = Field(..., min_length=64, description="JWT密钥，建议: openssl rand -hex 32")
    AUTH_JWT_ALGORITHM: str = "HS256"
    AUTH_JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 day
    AUTH_JWT_TEMPORARY_TOKEN: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJ1c2VybmFtZSI6ImFkbWluIiwicGFzc3dvcmQiOm51bGwsImFsaWFzIjpudWxsLCJlbWFpbCI6bnVsbCwicGhvbmUiOm51bGwsImF2YXRhciI6bnVsbCwic3RhdGUiOjAsImlzX2FjdGl2ZSI6bnVsbCwiaXNfc3VwZXJ1c2VyIjp0cnVlLCJsYXN0X2xvZ2luIjpudWxsLCJhY2Nlc3NfdG9rZW4iOm51bGwsImV4cCI6MTgxNzQzMzM5NCwidG9rZW5fdmVyc2lvbiI6MH0.k6ue_ZpEvsaDx9LrBHjDTaSpzS0dfGPsZif3r4ArK2Y"

    # 日志相关参数配置
    LOGGER_FILE_NAME_PREFIX: str = "执行日志"
    # 大小轮转："200 MB"
    # 日期轮转："1 day"、"1 week"、"1 month"
    # 时间轮转："HH:MM:SS"、"00:00"、"00:00:00"
    LOGGER_ROTATION: str = "1 MB"
    # 大小轮转后保留的备份文件个数（单文件多进程模式）
    LOGGER_ROTATION_BACKUP_COUNT: int = 30

    # 项目路径相关配置
    APPLICATIONS_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "applications"))
    CELERY_SCHEDULER_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "celery_scheduler"))
    COMMON_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "common"))
    CONFIGURE_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "configure"))
    CORE_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "core"))
    ENUMS_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "enums"))
    OUTPUT_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "output"))
    OUTPUT_LOGS_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "logs"))
    OUTPUT_UPLOAD_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "upload"))
    OUTPUT_DOWNLOAD_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "download"))
    OUTPUT_MEDIA_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "media"))
    OUTPUT_DATAGRAM_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "datagram"))
    OUTPUT_JMX_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "jmx"))
    OUTPUT_XLSX_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "xlsx"))
    OUTPUT_DOCS_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "docs"))
    SERVICES_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "services"))
    STATIC_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "static"))
    STATIC_IMG_DIR: str = os.path.abspath(os.path.join(STATIC_DIR, "image"))
    MIGRATION_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "migrations"))

    # # 允许访问的源（域名）列表
    CORS_ORIGINS: List[str] = [
        "http://localhost",
        "http://localhost:5000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://localhost:8515",
        "*",
    ]
    # 是否允许携带凭证（如 cookies）
    CORS_ALLOW_CREDENTIALS: bool = True
    # 允许的 HTTP 方法列表
    CORS_ALLOW_METHODS: List[str] = ["*"]
    # 允许的请求头列表
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    # 允许客户端访问的响应头列表
    CORS_EXPOSE_METHODS: List[str] = ["*"]
    # 预检请求的缓存时间（秒）
    CORS_MAX_AGE: int = 600

    # 文件上传设置
    UPLOAD_FILE_BASE_SIZE: int = 1024 * 1024  # 1MB
    UPLOAD_FILE_PEAK_SIZE: Dict[str, int] = {
        "tiny": UPLOAD_FILE_BASE_SIZE * 16,
        "micro": UPLOAD_FILE_BASE_SIZE * 32,
        "small": UPLOAD_FILE_BASE_SIZE * 64,
        "medium": UPLOAD_FILE_BASE_SIZE * 128,
        "large": UPLOAD_FILE_BASE_SIZE * 256,
        "huge": UPLOAD_FILE_BASE_SIZE * 512,
    }
    UPLOAD_FILE_SUFFIX: List[str] = [
        'image/jepg',
        'image/png',
        'text/csv',
        'text/plain',
        'text/markdown',
        'application/pdf',
        'application/zip',
        'application/msword',  # doc
        'application/octet-stream',  # dat
        'application/vnd.ms-excel',  # xls
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # xlsx
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'  # docx
    ]

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

    # 常用的用户代理字符串列表
    USER_AGENTS: List[str] = [
        # Chrome
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",

        # Firefox
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (X11; Linux i686; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:119.0) Gecko/20100101 Firefox/119.0",

        # Safari
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",

        # Edge
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",

        # Mobile
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    ]

    # 数据库配置
    DATABASE_AUTO_MIGRATION: bool = True
    DATABASE_CONNECTIONS: Dict[str, Any] = {}
    DATABASE_URL: str = Field(default="", description="数据库地址")
    DATABASE_HOST: str = Field(..., min_length=1, description="数据库主机")
    DATABASE_PORT: str = Field(..., min_length=1, description="数据库端口")
    DATABASE_NAME: str = Field(..., min_length=1, description="数据库名称")
    DATABASE_USERNAME: str = Field(..., min_length=1, description="数据库用户名")
    DATABASE_PASSWORD: str = Field(..., min_length=1, description="数据库密码")

    # Redis 配置（仅 requirepass 时用户名留空；密码含 @/: 等会在连接 URL 中做编码）
    REDIS_URL: str = ""
    REDIS_HOST: str = Field(..., min_length=1, description="Redis主机")
    REDIS_PORT: str = Field(..., min_length=1, description="Redis端口")
    REDIS_USERNAME: str = Field(default="", description="Redis用户名")
    REDIS_PASSWORD: str = Field(..., min_length=1, description="Redis密码")

    # 自动化模块：数据库操作中Oracle连接模式，空值按thick；thin不兼容11g/部分12.1
    ORACLE_CLIENT_MODE: str = Field(default="", description="Oracle Instant 连接模式，仅允许：thick/thin")
    ORACLE_CLIENT_PATH: str = Field(default="", description="Oracle Instant Client 存放目录")

    @model_validator(mode="after")
    def validate_env_and_assemble_urls(self) -> Self:
        if not self.AUTH_SECRET_KEY or len(self.AUTH_SECRET_KEY) < 64:
            raise ValueError("AUTH_SECRET_KEY 配置为空或长度少于64位，请检查.env文件或环境变量")

        for field_name in ("DATABASE_USERNAME", "DATABASE_HOST", "DATABASE_PORT", "DATABASE_NAME", "REDIS_HOST", "REDIS_PORT"):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} 配置为空，请请检查.env文件或环境变量")

        return self.assemble_connection_urls()

    def assemble_connection_urls(self) -> Self:
        db_user = quote_plus(self.DATABASE_USERNAME)
        db_password = quote_plus(self.DATABASE_PASSWORD)
        self.DATABASE_URL = (
            f"mysql://{db_user}:{db_password}@{self.DATABASE_HOST}:"
            f"{self.DATABASE_PORT}/{self.DATABASE_NAME}"
            f"?charset=utf8mb4&time_zone=+08:00"
        )
        self.DATABASE_CONNECTIONS = {
            "default": {
                "engine": "tortoise.backends.mysql",
                "db_url": self.DATABASE_URL,
                "credentials": {
                    "host": self.DATABASE_HOST,
                    "port": self.DATABASE_PORT,
                    "user": self.DATABASE_USERNAME,
                    "password": self.DATABASE_PASSWORD,
                    "database": self.DATABASE_NAME,
                    "minsize": 10,
                    "maxsize": 40,
                    "pool_recycle": 3600,
                    "charset": "utf8mb4",
                    "echo": False,
                    "autocommit": True,
                },
            }
        }
        self.REDIS_URL = self.build_redis_url(db=0)
        return self

    @staticmethod
    def format_redis_url(*, username: str, password: str, host: str, port: str, db: int) -> str:
        auth = ""
        if username:
            auth += quote_plus(username)
        auth += ":"
        if password:
            auth += quote_plus(password)
        auth += "@"
        return f"redis://{auth}{host or '127.0.0.1'}:{port or '6379'}/{db}"

    def build_redis_url(self, db: int = 0) -> str:
        return self.format_redis_url(
            username=self.REDIS_USERNAME,
            password=self.REDIS_PASSWORD,
            host=self.REDIS_HOST,
            port=self.REDIS_PORT,
            db=db,
        )

    # Aerich：是否在应用启动时执行 init_db / migrate / upgrade 指令
    # - 生产(Linux 且 SERVER_DEBUG=False)：始终执行迁移（不提供关闭选项）
    # - 开发(SERVER_DEBUG=True)：默认不迁移；需要时由开发者手动把 DATABASE_AUTO_MIGRATION 改为 True
    @property
    def aerich_should_run_on_startup(self) -> bool:
        if (not self.SERVER_DEBUG) and (self.SERVER_SYSTEM == "Linux"):
            return True
        if self.SERVER_DEBUG and self.DATABASE_AUTO_MIGRATION:
            return True
        return False


@lru_cache(maxsize=1)
def get_project_config() -> ProjectConfig:
    return ProjectConfig()


PROJECT_CONFIG = get_project_config()
