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
    env_id: int = Field(..., ge=1, description="环境ID")
    project_id: int = Field(..., ge=1, description="应用ID")
    config_type: AutoTestConfigNodeType = Field(..., description="配置类型")
    config_name: str = Field(..., description="配置名称")
    config_host: str = Field(..., max_length=128, description="数据库/服务器主机地址")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class AutoTestApiConfigUpdate(AutoTestApiConfigBase):
    config_id: Optional[int] = Field(None, ge=1, description="配置主键ID")
    config_code: Optional[str] = Field(None, max_length=64, description="配置标识代码")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestApiConfigDelete(BaseModel):
    config_ids: Optional[List[int]] = Field(None, description="配置主键ID列表")
    config_codes: Optional[List[str]] = Field(None, description="配置标识代码列表")


class AutoTestApiConfigSelect(AutoTestApiConfigBase):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["-created_time"], description="排序字段")

    config_id: Optional[int] = Field(None, ge=1, description="配置主键ID")
    config_code: Optional[str] = Field(None, max_length=64, description="配置标识代码")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")
