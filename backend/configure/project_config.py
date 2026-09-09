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

_PROJECT_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_PROJECT_CONF: str = os.path.join(_PROJECT_ROOT, ".env")


class ProjectConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_PROJECT_CONF,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 项目描述
    APP_VERSION: str = "0.1.1"
    APP_TITLE: str = "KeenRunner - 测管平台"
    APP_DESCRIPTION: str = """
一款基于 Python 的 FastAPI 框架开发的实用型测试管理系统，旨在满足软件测试工作的日常需求。

- 它专注于提供最实用的功能，涵盖测试用例管理、测试环境配置、测试任务调度以及测试报告生成等多个关键环节。
- 用户可以轻松导入和导出测试用例，灵活调整测试计划，根据不同的测试阶段和项目需求对测试任务进行精确管理。
- 凭借 FastAPI 的高效性能，平台能够迅速响应各种操作，确保测试工作的连贯性和高效性。
- 同时，系统还支持历史测试数据的回溯和对比，帮助团队持续优化测试流程，为软件质量的提升提供强大支持。

## 业务模块

- **自动化测试**：用例、步骤、数据源、数据生成、报告、执行明细、调试
- **应用管理**：项目、环境、配置节点、标签
- **任务管理**：手动/定时任务、执行记录与状态回写
- **系统管理**：用户、角色、菜单、路由、部门、认证与权限
- **便捷工具**：报文比对、工具箱

## 自动化测试引擎

用例以树形步骤编排，提供以下操作步骤类型：

- **HTTP/TCP请求**：发送HTTP/HTTPS或TCP协议请求，支持变量提取、断言与参数化数据驱动
- **DB/Redis请求**：按环境配置连接目标服务执行SQL/Redis命令，结果可存为会话变量
- **代码请求(Python)**：执行自定义Python代码，编排复杂业务逻辑
- **条件分支**：if/elif/else 语义，按序评估、命中即执行
- **循环结构**：次数/列表/字典/条件四种模式，支持中断循环、停止用例、继续下一轮三类错误策略
- **断言**：等于、大小、长度、包含、集合归属、前后缀、空值等十余种比较方式
- **引用公共脚本/接口**：复用公共用例步骤，实现测试资产复用
- **报文比对**：请求/响应报文字段级差异比对

## 任务与调度

- **任务中心**：Celery 承载耗时后台作业（用例编排执行、单用例执行、导出用例数据、导出公共接口脚本），执行记录与结果全量落库，trace_id/span_id 全链路追踪
- **调度机制**：手动触发 + 定时调度（分钟级精度）；Beat 每 60 秒扫描业务表下发到期任务，RedBeat 基于 Redis 持久化并持分布式锁，多实例部署调度不重复

## 认证与权限

- JWT 无状态认证（argon2 密码加密），Token 可吊销
- 按 summary 前缀识别接口行为，为管理员/标准用户/宾客用户三类内置角色自动绑定路由与菜单

## 接口规范

- 路由 `tags` 采用「一级目录:二级模块」（如 `自动化测试:用例`），与侧边栏菜单对齐
- `summary` 必须以行为动词开头（查询/新增/更新/删除/执行/导入/刷新），权限自动绑定依赖该前缀分类
    """
    APP_DOCS_URL: str = "/KeenRunner/docs"
    APP_REDOC_URL: str = "/KeenRunner/redoc"
    APP_OPENAPI_URL: str = "/KeenRunner/openapi_url"
    APP_OPENAPI_JS_URL: str = "/static/swagger-ui/swagger-ui-bundle.js"
    APP_OPENAPI_CSS_URL: str = "/static/swagger-ui/swagger-ui.css"
    APP_OPENAPI_ENHANCER_URL: str = "/static/swagger-ui/swagger-ui-enhancer.js"
    APP_OPENAPI_FAVICON_URL: str = "/static/swagger-ui/favicon-32x32.png"
    APP_OPENAPI_JS_URL_REDOC: str = "/static/redoc/bundles/redoc.standalone.js"
    APP_OPENAPI_FAVICON_URL_REDOC: str = "/static/redoc/favicon-32x32.svg"
    APP_OPENAPI_VERSION: str = "3.0.2"

    # 调试配置
    SERVER_APP: str = "backend_main:app"
    SERVER_HOST: str = ShellUtils.acquire_localhost()
    SERVER_SYSTEM: str = platform.system()
    SERVER_PORT: int = 8518
    SERVER_DEBUG: bool = SERVER_SYSTEM != "Linux"  # Windows | Linux | Darwin
    SERVER_DELAY: int = 5

    # 安全认证配置
    AUTH_JWT_ALGORITHM: str = "HS256"
    AUTH_JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 day
    AUTH_SECRET_KEY: str = Field(..., min_length=64, description="JWT密钥")
    AUTH_TEMPORARY_TOKEN: str = Field(..., min_length=128, description="临时令牌")

    # 日志相关参数配置
    LOGGER_FILE_NAME_PREFIX: str = "执行日志"
    # 大小轮转："200 MB"
    # 日期轮转："1 day"、"1 week"、"1 month"
    # 时间轮转："HH:MM:SS"、"00:00"、"00:00:00"
    LOGGER_ROTATION: str = "100 MB"
    # 大小轮转后保留的备份文件个数（单文件多进程模式）
    LOGGER_ROTATION_BACKUP_COUNT: int = 30

    # 项目路径相关配置
    APPLICATIONS_DIR: str = os.path.abspath(os.path.join(_PROJECT_ROOT, "applications"))
    CELERY_SCHEDULER_DIR: str = os.path.abspath(os.path.join(_PROJECT_ROOT, "celery_scheduler"))
    COMMON_DIR: str = os.path.abspath(os.path.join(_PROJECT_ROOT, "common"))
    CONFIGURE_DIR: str = os.path.abspath(os.path.join(_PROJECT_ROOT, "configure"))
    CORE_DIR: str = os.path.abspath(os.path.join(_PROJECT_ROOT, "core"))
    ENUMS_DIR: str = os.path.abspath(os.path.join(_PROJECT_ROOT, "enums"))
    OUTPUT_DIR: str = os.path.abspath(os.path.join(_PROJECT_ROOT, "output"))
    OUTPUT_DATAGRAM_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "datagram"))
    OUTPUT_DOCS_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "docs"))
    OUTPUT_DOWNLOAD_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "download"))
    OUTPUT_JMX_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "jmx"))
    OUTPUT_LOGS_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "logs"))
    OUTPUT_TEMPLATE_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "template"))
    OUTPUT_UPLOAD_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "upload"))
    OUTPUT_MEDIA_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "media"))
    OUTPUT_XLSX_DIR: str = os.path.abspath(os.path.join(OUTPUT_DIR, "xlsx"))
    SERVICES_DIR: str = os.path.abspath(os.path.join(_PROJECT_ROOT, "services"))
    STATIC_DIR: str = os.path.abspath(os.path.join(_PROJECT_ROOT, "static"))
    STATIC_IMG_DIR: str = os.path.abspath(os.path.join(STATIC_DIR, "avatar"))
    MIGRATION_DIR: str = os.path.abspath(os.path.join(_PROJECT_ROOT, "migrations"))

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
    DATABASE_URL: str = Field("", description="数据库地址")
    DATABASE_HOST: str = Field(..., description="数据库主机")
    DATABASE_PORT: str = Field(..., description="数据库端口")
    DATABASE_NAME: str = Field(..., description="数据库名称")
    DATABASE_USERNAME: str = Field(..., description="数据库账户")
    DATABASE_PASSWORD: str = Field(..., description="数据库密码")
    DEV_DATABASE_HOST: str = Field(..., description="数据库主机(开发环境)")
    DEV_DATABASE_PORT: str = Field(..., description="数据库端口(开发环境)")
    DEV_DATABASE_NAME: str = Field(..., description="数据库名称(开发环境)")
    DEV_DATABASE_USERNAME: str = Field(..., description="数据库账户(开发环境)")
    DEV_DATABASE_PASSWORD: str = Field(..., description="数据库密码(开发环境)")

    # Redis 配置（仅 requirepass 时用户名留空；密码含 @/: 等会在连接 URL 中做编码）
    REDIS_URL: str = Field("", description="Redis地址(开发/测试)")
    REDIS_HOST: str = Field(..., description="Redis主机(开发/测试)")
    REDIS_PORT: str = Field(..., description="Redis端口(开发/测试)")
    REDIS_USERNAME: str = Field("", description="Redis账户(开发/测试)")
    REDIS_PASSWORD: str = Field(..., description="Redis密码(开发/测试)")

    # Celery Redis 数据库编号配置
    CELERY_BROKER_DB: int = Field(..., description="消息代理")
    CELERY_BACKEND_DB: int = Field(..., description="结果存储")
    CELERY_REDBEAT_DB: int = Field(..., description="任务持久")
    DEV_CELERY_BROKER_DB: int = Field(..., description="消息代理(开发环境)")
    DEV_CELERY_BACKEND_DB: int = Field(..., description="结果存储(开发环境)")
    DEV_CELERY_REDBEAT_DB: int = Field(..., description="任务持久(开发环境)")

    # 自动化模块：数据库操作中Oracle连接模式，空值按thick；thin不兼容11g/部分12.1
    ORACLE_CLIENT_MODE: str = Field(default="", description="Oracle Instant 连接模式，仅允许：thick/thin")
    ORACLE_CLIENT_PATH: str = Field(default="", description="Oracle Instant Client 存放目录")

    @model_validator(mode="after")
    def validate_env_and_assemble_urls(self) -> Self:
        if not self.AUTH_SECRET_KEY or len(self.AUTH_SECRET_KEY) < 64:
            raise ValueError("配置[AUTH_SECRET_KEY]不允许为空或少于64位")

        for field_name in (
                "DATABASE_HOST", "DATABASE_PORT", "DATABASE_NAME", "DATABASE_USERNAME", "DATABASE_PASSWORD",
                "DEV_DATABASE_HOST", "DEV_DATABASE_PORT", "DEV_DATABASE_NAME", "DEV_DATABASE_USERNAME", "DEV_DATABASE_PASSWORD",
                "REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD",
                "CELERY_BROKER_DB", "CELERY_BACKEND_DB", "CELERY_REDBEAT_DB",
                "DEV_CELERY_BROKER_DB", "DEV_CELERY_BACKEND_DB", "DEV_CELERY_REDBEAT_DB",
        ):
            value = getattr(self, field_name)
            if value is None or (isinstance(value, str) and not value):
                raise ValueError(f"配置[{field_name}]不允许为空")

        return self.assemble_connection_urls()

    def assemble_connection_urls(self) -> Self:
        # 根据环境选择数据库配置
        if self.SERVER_DEBUG:
            # 开发环境
            database_username = self.DEV_DATABASE_USERNAME
            database_password = self.DEV_DATABASE_PASSWORD
            database_host = self.DEV_DATABASE_HOST
            database_port = self.DEV_DATABASE_PORT
            database_name = self.DEV_DATABASE_NAME
        else:
            # 生产环境
            database_username = self.DATABASE_USERNAME
            database_password = self.DATABASE_PASSWORD
            database_host = self.DATABASE_HOST
            database_port = self.DATABASE_PORT
            database_name = self.DATABASE_NAME

        self.DATABASE_URL = (
            f"mysql://{database_username}:{database_password}@{database_host}:"
            f"{database_port}/{database_name}"
            f"?charset=utf8mb4&time_zone=+08:00"
        )
        self.DATABASE_CONNECTIONS = {
            "default": {
                "engine": "tortoise.backends.mysql",
                "db_url": self.DATABASE_URL,
                "credentials": {
                    "host": database_host,
                    "port": database_port,
                    "user": database_username,
                    "password": database_password,
                    "database": database_name,
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
        return f"redis://{auth}{host}:{port}/{db}"

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
