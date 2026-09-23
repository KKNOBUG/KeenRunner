# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_env_config_schema
@DateTime: 2026/4/16 10:19
"""
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field, model_validator

from backend.applications.base.services.scaffold import UpperStr
from backend.enums import AutoTestDataBaseType, AutoTestConfigNodeType


def _validate_db_required_fields(database_name: Any, database_type: Any, config_username: Any, config_password: Any) -> None:
    """校验DB类型必填字段。"""
    missing = [
        name for name, val in (
            ("database_name", database_name),
            ("database_type", database_type),
            ("config_username", config_username),
            ("config_password", config_password),
        ) if val in (None, "")
    ]
    if missing:
        raise ValueError(f"节点类型[DB]配置缺少必填字段: [{', '.join(missing)}]")


class AutoTestEnvConfigBase(BaseModel):
    """环境配置公共字段。"""

    env_id: Optional[int] = Field(None, ge=1, description="环境绑定ID")
    project_id: Optional[int] = Field(None, ge=1, description="环境绑定应用ID")

    env_name: Optional[str] = Field(None, max_length=64, description="环境名称")
    env_type: Optional[AutoTestConfigNodeType] = Field(None, description="环境绑定节点类型")

    config_name: Optional[str] = Field(None, max_length=128, description="配置名称")
    config_desc: Optional[str] = Field(None, max_length=2048, description="配置描述")
    config_host: Optional[str] = Field(None, max_length=128, description="数据库/服务器主机地址")
    config_port: Optional[str] = Field(None, max_length=8, description="数据库/服务器端口")
    config_group: Optional[str] = Field(None, max_length=128, description="数据库/服务器分组")
    config_params: Optional[Dict[str, Any]] = Field(None, description="数据库/服务器参数")
    config_username: Optional[str] = Field(None, max_length=128, description="数据库/服务器用户名")
    config_password: Optional[str] = Field(None, max_length=128, description="数据库/服务器密码")
    config_kwargs: Optional[List[Dict[str, Any]]] = Field(None, description="通用环境变量配置")
    config_header: Optional[List[Dict[str, Any]]] = Field(None, description="通用请求头配置")
    is_no_password: Optional[bool] = Field(None, description="是否免密")

    database_name: Optional[str] = Field(None, max_length=128, description="数据库名称/Redis库编号")
    database_type: Optional[AutoTestDataBaseType] = Field(None, description="数据库类型")


class AutoTestEnvConfigCreate(AutoTestEnvConfigBase):
    """创建环境配置入参。"""

    project_id: int = Field(..., ge=1, description="环境绑定应用ID")
    env_name: str = Field(..., max_length=64, description="环境名称")
    env_type: AutoTestConfigNodeType = Field(..., description="环境绑定节点类型")
    config_name: str = Field(..., max_length=128, description="配置名称")
    config_host: str = Field(..., max_length=128, description="数据库/服务器主机地址")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")

    @model_validator(mode="after")
    def _validate_by_env_type(self):
        """按节点类型校验必填字段。"""
        if self.env_type == AutoTestConfigNodeType.DB:
            _validate_db_required_fields(
                database_name=self.database_name,
                database_type=self.database_type,
                config_username=self.config_username,
                config_password=self.config_password,
            )
        return self


class AutoTestEnvConfigUpdate(AutoTestEnvConfigBase):
    """更新环境配置入参。"""

    config_id: Optional[int] = Field(None, ge=1, description="配置ID")
    config_code: Optional[str] = Field(None, max_length=64, description="配置标识代码")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")

    @model_validator(mode="after")
    def _validate_by_env_type(self):
        """更新时若携带env_type=DB，则校验DB必填字段。"""
        if self.env_type is None:
            return self
        if self.env_type == AutoTestConfigNodeType.DB:
            _validate_db_required_fields(
                database_name=self.database_name,
                database_type=self.database_type,
                config_username=self.config_username,
                config_password=self.config_password,
            )
        return self


class AutoTestEnvConfigDelete(BaseModel):
    """批量删除环境配置入参。"""

    config_ids: Optional[List[int]] = Field(None, description="配置ID列表")
    config_codes: Optional[List[str]] = Field(None, description="配置标识代码列表")


class AutoTestEnvConfigTypedDelete(BaseModel):
    """按节点类型删除单条环境配置入参。"""

    config_id: int = Field(..., ge=1, description="配置ID")
    env_type: AutoTestConfigNodeType = Field(..., description="环境绑定节点类型")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestEnvConfigSelect(AutoTestEnvConfigBase):
    """分页查询环境配置入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["-created_time"], description="排序字段")

    config_id: Optional[int] = Field(None, ge=1, description="配置ID")
    config_code: Optional[str] = Field(None, max_length=64, description="配置标识代码")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    state: Optional[int] = Field(default=0, description="状态")


class AutoTestEnvConfigQueryByProjectsIn(BaseModel):
    """根据应用ID列表查询环境配置并分类的请求体。"""

    project_ids: List[int] = Field(..., min_length=1, description="环境绑定应用ID列表")
    config_names: Optional[List[str]] = Field(None, description="配置名称列表")


class TestDBConnectionRequest(BaseModel):
    """测试数据库连接入参。"""

    config_id: int = Field(..., ge=1, description="配置ID")
    project_id: int = Field(..., ge=1, description="环境绑定应用ID")
    env_name: str = Field(..., description="环境名称")
    config_name: str = Field(..., description="配置名称")
    database_name: str = Field(..., description="数据库名称/Redis库编号")


class APPEnvConfigCreate(AutoTestEnvConfigCreate):
    """新增APP类型环境配置入参。"""

    env_type: AutoTestConfigNodeType = Field(default=AutoTestConfigNodeType.APP, description="环境绑定节点类型")


class APPEnvConfigUpdate(AutoTestEnvConfigUpdate):
    """修改APP类型环境配置入参。"""

    env_name: str = Field(..., max_length=64, description="环境名称")
    project_id: int = Field(..., ge=1, description="环境绑定应用ID")
    config_id: int = Field(..., ge=1, description="配置ID")
    config_name: str = Field(..., max_length=128, description="配置名称")
    config_host: str = Field(..., max_length=128, description="数据库/服务器主机地址")
    env_type: AutoTestConfigNodeType = Field(default=AutoTestConfigNodeType.APP, description="环境绑定节点类型")


class DBEnvConfigCreate(AutoTestEnvConfigCreate):
    """新增DB(database)类型环境配置入参。"""

    env_type: AutoTestConfigNodeType = Field(default=AutoTestConfigNodeType.DB, description="环境绑定节点类型")
    database_name: str = Field(..., max_length=128, description="数据库名称")
    database_type: AutoTestDataBaseType = Field(..., description="数据库类型")
    config_username: str = Field(..., max_length=128, description="数据库用户名")
    config_password: str = Field(..., max_length=128, description="数据库密码")


class DBEnvConfigUpdate(AutoTestEnvConfigUpdate):
    """修改DB(database)类型环境配置入参。"""

    env_name: str = Field(..., max_length=64, description="环境名称")
    project_id: int = Field(..., ge=1, description="环境绑定应用ID")

    config_id: int = Field(..., ge=1, description="配置ID")
    config_name: str = Field(..., max_length=128, description="配置名称")
    config_host: str = Field(..., max_length=128, description="数据库/服务器主机地址")

    env_type: AutoTestConfigNodeType = Field(default=AutoTestConfigNodeType.DB, description="环境绑定节点类型")
    database_name: str = Field(..., max_length=128, description="数据库名称")
    database_type: AutoTestDataBaseType = Field(..., description="数据库类型")
    config_username: str = Field(..., max_length=128, description="数据库用户名")
    config_password: str = Field(..., max_length=128, description="数据库密码")


class FILEEnvConfigCreate(AutoTestEnvConfigCreate):
    """新增FILE类型环境配置入参。"""

    env_type: AutoTestConfigNodeType = Field(default=AutoTestConfigNodeType.FILE, description="环境绑定节点类型")


class FILEEnvConfigUpdate(AutoTestEnvConfigUpdate):
    """修改FILE类型环境配置入参。"""

    env_name: str = Field(..., max_length=64, description="环境名称")
    project_id: int = Field(..., ge=1, description="环境绑定应用ID")
    config_id: int = Field(..., ge=1, description="配置ID")
    config_name: str = Field(..., max_length=128, description="配置名称")
    config_host: str = Field(..., max_length=128, description="数据库/服务器主机地址")
    env_type: AutoTestConfigNodeType = Field(default=AutoTestConfigNodeType.FILE, description="环境绑定节点类型")


class RedisEnvConfigCreate(AutoTestEnvConfigCreate):
    """新增REDIS类型环境配置入参。"""

    env_type: AutoTestConfigNodeType = Field(default=AutoTestConfigNodeType.REDIS, description="环境绑定节点类型")
    config_host: str = Field(..., max_length=128, description="Redis地址")
    config_port: str = Field(..., max_length=8, description="Redis端口")
    database_name: Optional[str] = Field(None, max_length=128, description="Redis库编号")
    config_username: Optional[str] = Field(None, max_length=128, description="Redis用户名")
    config_password: Optional[str] = Field(None, max_length=128, description="Redis密码")


class RedisEnvConfigUpdate(AutoTestEnvConfigUpdate):
    """修改REDIS类型环境配置入参。"""

    env_name: str = Field(..., max_length=64, description="环境名称")
    project_id: int = Field(..., ge=1, description="环境绑定应用ID")
    config_id: int = Field(..., ge=1, description="配置ID")
    config_name: str = Field(..., max_length=128, description="配置名称")

    env_type: AutoTestConfigNodeType = Field(default=AutoTestConfigNodeType.REDIS, description="环境绑定节点类型")
    config_host: str = Field(..., max_length=128, description="Redis地址")
    config_port: str = Field(..., max_length=8, description="Redis端口")
    database_name: Optional[str] = Field(None, max_length=128, description="Redis库编号")
    config_username: Optional[str] = Field(None, max_length=128, description="Redis用户名")
    config_password: Optional[str] = Field(None, max_length=128, description="Redis密码")


class QueryAssignConfigEnv(BaseModel):
    """按应用+配置名称+节点类型查询环境名称列表入参。"""

    project_id: Optional[int] = Field(None, description="环境绑定应用ID")
    config_name: Optional[str] = Field(None, description="配置名称")
    env_type: Optional[AutoTestConfigNodeType] = Field(None, description="环境绑定节点类型")
