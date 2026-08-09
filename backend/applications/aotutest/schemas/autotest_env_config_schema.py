# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_config_schema
@DateTime: 2026/4/16 10:19
"""
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field

from backend.applications.base.services.scaffold import UpperStr
from backend.enums import AutoTestDataBaseType, AutoTestConfigNodeType


class AutoTestApiConfigBase(BaseModel):
    """环境配置公共字段。"""

    env_id: Optional[int] = Field(None, ge=1, description="环境ID")
    project_id: Optional[int] = Field(None, ge=1, description="应用ID")
    config_name: Optional[str] = Field(None, description="配置名称")
    config_desc: Optional[str] = Field(None, description="配置描述")
    config_type: Optional[AutoTestConfigNodeType] = Field(None, description="配置类型")
    config_host: Optional[str] = Field(None, max_length=128, description="数据库/服务器主机地址")
    config_port: Optional[str] = Field(None, max_length=8, description="数据库/服务器端口")
    config_group: Optional[str] = Field(None, max_length=128, description="数据库/服务器分组")
    config_params: Optional[Dict[str, Any]] = Field(None, description="数据库/服务器参数")
    config_kwargs: Optional[List[Dict[str, Any]]] = Field(None, description="通用环境变量配置")
    config_header: Optional[List[Dict[str, Any]]] = Field(None, description="通用请求头配置")
    config_username: Optional[str] = Field(None, max_length=16, description="数据库/服务器用户名")
    config_password: Optional[str] = Field(None, max_length=16, description="数据库/服务器密码")
    database_name: Optional[str] = Field(None, max_length=128, description="数据库名称")
    database_type: Optional[AutoTestDataBaseType] = Field(None, description="数据库类型")
    is_authorization: Optional[bool] = Field(None, description="是否免密")


class AutoTestApiConfigCreate(AutoTestApiConfigBase):
    """创建环境配置入参。"""

    env_id: int = Field(..., ge=1, description="环境ID")
    project_id: int = Field(..., ge=1, description="应用ID")
    config_type: AutoTestConfigNodeType = Field(..., description="配置类型")
    config_name: str = Field(..., description="配置名称")
    config_host: str = Field(..., max_length=128, description="数据库/服务器主机地址")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class AutoTestApiConfigUpdate(AutoTestApiConfigBase):
    """更新环境配置入参。"""

    config_id: Optional[int] = Field(None, ge=1, description="配置主键ID")
    config_code: Optional[str] = Field(None, max_length=64, description="配置标识代码")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestApiConfigDelete(BaseModel):
    """删除环境配置入参。"""

    config_ids: Optional[List[int]] = Field(None, description="配置主键ID列表")
    config_codes: Optional[List[str]] = Field(None, description="配置标识代码列表")


class AutoTestApiConfigSelect(AutoTestApiConfigBase):
    """分页查询环境配置入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["-created_time"], description="排序字段")

    config_id: Optional[int] = Field(None, ge=1, description="配置主键ID")
    config_code: Optional[str] = Field(None, max_length=64, description="配置标识代码")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")


class AutoTestEnvConfigQueryByProjectsIn(BaseModel):
    """根据应用ID列表查询环境配置并分类的请求体。"""

    project_ids: List[int] = Field(..., min_length=1, description="应用(project)ID 列表")


class AutoTestEnvConfigClassifiedLeaf(BaseModel):
    """分类结果中每个配置名称下的字段说明。"""

    config_host: Optional[str] = Field(None, description="主机地址")
    config_port: Optional[str] = Field(None, description="主机端口")
    database_name: Optional[str] = Field(None, description="数据库名称")


class APPEnvConfigCreate(BaseModel):
    """新增 APP 类型环境配置入参。"""

    env_info_id: int = Field(..., description="应用ID")
    config_name: str = Field(..., description="配置名称", max_length=64)
    env: str = Field(..., description="环境", max_length=64)
    env_host: str = Field(..., description="IP地址", max_length=128)
    env_port: str = Field(..., description="端口", max_length=128)
    maintainer: str = Field(..., description="维护人", max_length=128)
    remark: Optional[str] = Field(None, description="备注", max_length=256)
    operation: int = Field(1, description="操作类型：1-新增")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class FILEEnvConfigCreate(BaseModel):
    """新增 FILE 类型环境配置入参。"""

    env_info_id: int = Field(..., description="应用ID")
    config_name: str = Field(..., description="配置名称", max_length=64)
    env: str = Field(..., description="环境", max_length=64)
    server_ip: str = Field(..., description="服务器IP", max_length=128)
    server_port: str = Field(..., description="服务器端口", max_length=128)
    server_account: str = Field(..., description="服务器账号", max_length=128)
    server_password: str = Field(..., description="服务器密码", max_length=128)
    is_no_password: int = Field(..., description="是否免密", ge=0, le=1)
    maintainer: str = Field(..., description="维护人", max_length=128)
    remark: Optional[str] = Field(None, description="备注", max_length=256)
    operation: int = Field(1, description="操作类型：1-新增")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class DBEnvConfigCreate(BaseModel):
    """新增 DB 类型环境配置入参。"""

    env_info_id: int = Field(..., description="应用ID")
    config_name: str = Field(..., description="配置名称", max_length=64)
    env: str = Field(..., description="环境", max_length=64)
    db_name: str = Field(..., description="数据库名称", max_length=128)
    db_host: str = Field(..., description="数据库IP", max_length=128)
    db_port: str = Field(..., description="数据库端口", max_length=128)
    db_user: str = Field(..., description="数据库账号", max_length=128)
    db_password: str = Field(..., description="数据库密码", max_length=128)
    db_type: str = Field(..., description="数据库类型", max_length=128)
    maintainer: str = Field(..., description="维护人", max_length=128)
    remark: Optional[str] = Field(None, description="备注", max_length=256)
    operation: int = Field(1, description="操作类型：1-新增")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class RedisEnvConfigCreate(BaseModel):
    """新增 REDIS 类型环境配置入参。"""

    env_info_id: int = Field(..., description="应用ID")
    config_name: str = Field(..., description="配置名称", max_length=64)
    env: str = Field(..., description="环境", max_length=64)
    redis_host: str = Field(..., description="Redis主机", max_length=128)
    redis_port: str = Field(..., description="Redis端口", max_length=8)
    redis_db: str = Field(default="0", description="Redis库编号", max_length=128)
    redis_username: Optional[str] = Field(default="", description="Redis用户名", max_length=128)
    redis_password: Optional[str] = Field(default="", description="Redis密码", max_length=128)
    maintainer: str = Field(..., description="维护人", max_length=128)
    remark: Optional[str] = Field(None, description="备注", max_length=256)
    operation: int = Field(1, description="操作类型：1-新增")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class APPEnvConfigUpdate(BaseModel):
    """修改 APP 类型环境配置入参。"""

    id: int = Field(..., description="配置ID")
    project_id: str = Field(..., description="应用ID", max_length=64)
    config_name: str = Field(..., description="配置名称", max_length=64)
    env: str = Field(..., description="环境", max_length=64)
    env_host: str = Field(..., description="IP地址", max_length=128)
    env_port: str = Field(..., description="端口", max_length=128)
    maintainer: str = Field(..., description="维护人", max_length=128)
    remark: Optional[str] = Field(None, description="备注", max_length=256)
    operation: int = Field(2, description="操作类型：2-修改")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class FILEEnvConfigUpdate(BaseModel):
    """修改 FILE 类型环境配置入参。"""

    id: int = Field(..., description="配置ID")
    project_id: str = Field(..., description="应用ID", max_length=64)
    config_name: str = Field(..., description="配置名称", max_length=64)
    env: str = Field(..., description="环境", max_length=64)
    server_ip: str = Field(..., description="服务器IP", max_length=128)
    server_port: str = Field(..., description="服务器端口", max_length=128)
    server_account: str = Field(..., description="服务器账号", max_length=128)
    server_password: str = Field(..., description="服务器密码", max_length=128)
    is_no_password: int = Field(..., description="是否免密", ge=0, le=1)
    maintainer: str = Field(..., description="维护人", max_length=128)
    remark: Optional[str] = Field(None, description="备注", max_length=256)
    operation: int = Field(2, description="操作类型：2-修改")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class DBEnvConfigUpdate(BaseModel):
    """修改 DB 类型环境配置入参。"""

    id: int = Field(..., description="配置ID")
    project_id: str = Field(..., description="应用ID", max_length=64)
    config_name: str = Field(..., description="配置名称", max_length=64)
    env: str = Field(..., description="环境", max_length=64)
    db_name: str = Field(..., description="数据库名称", max_length=128)
    db_host: str = Field(..., description="数据库IP", max_length=128)
    db_port: str = Field(..., description="数据库端口", max_length=128)
    db_user: str = Field(..., description="数据库账号", max_length=128)
    db_password: str = Field(..., description="数据库密码", max_length=128)
    db_type: str = Field(..., description="数据库类型", max_length=128)
    maintainer: str = Field(..., description="维护人", max_length=128)
    remark: Optional[str] = Field(None, description="备注", max_length=256)
    operation: int = Field(2, description="操作类型：2-修改")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class EnvConfigDelete(BaseModel):
    """按节点类型删除环境配置入参。"""

    id: int = Field(..., description="配置主键ID")
    env_type: int = Field(..., description="节点类型")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class TestDBConnectionRequest(BaseModel):
    """测试数据库连接入参。"""

    id: int = Field(..., description="配置主键ID")
    project_id: str = Field(..., description="应用主键ID")
    env_name: str = Field(..., description="环境名称")
    config_name: str = Field(..., description="配置名称")
    db_name: str = Field(..., description="数据库名称")
