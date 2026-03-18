# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_env_schema
@DateTime: 2026/1/2 16:44
"""
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator

from backend.applications.base.services.scaffold import UpperStr


class AutoTestApiEnvCreate(BaseModel):
    project_id: int = Field(..., description="环境所属项目")
    env_name: UpperStr = Field(..., max_length=64, description="环境名称")
    env_port: Optional[str] = Field(None, description="环境端口(8000)，可选，直接请求域名时可省略")
    env_host: str = Field(..., max_length=128, description="环境主机(http|https://127.0.0.1)")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")

    @field_validator('env_port', mode='before')
    @classmethod
    def normalize_env_port(cls, v):
        # 如果值为 None，直接返回（符合可选字段要求）
        if v is None:
            return None

        # 确保输入是字符串类型
        if not isinstance(v, str):
            raise ValueError("环境端口必须是字符串格式")

        # 去除两端空白字符（处理 " 8080 " 这类情况）
        port_str = v.strip()

        # 检查端口字符串是否为空（比如输入空字符串 "" 或全空格 "   "）
        if not port_str:
            raise ValueError("环境端口不能为空字符串")

        # 检查是否为纯数字（排除字母、小数点、符号等）
        if not port_str.isdigit():
            raise ValueError(f"环境端口必须是纯数字字符串，当前值: {port_str}")

        # 转换为数字并检查是否大于 0 且在合法端口范围（0-65535）
        port = int(port_str)
        if port <= 0:
            raise ValueError(f"环境端口必须大于0，当前值: {port}")
        if port > 65535:
            raise ValueError(f"环境端口不能超过65535（TCP/UDP最大端口号），当前值: {port}")

        # 返回处理后的纯数字字符串（去除空白）
        return port_str


class AutoTestApiEnvBase(BaseModel):
    env_id: Optional[int] = Field(None, description="环境ID")
    env_code: Optional[str] = Field(None, max_length=64, description="环境标识代码")
    project_id: Optional[int] = Field(None, description="环境所属项目")
    env_name: Optional[UpperStr] = Field(None, max_length=64, description="环境名称")
    env_port: Optional[int] = Field(None, ge=0, description="环境端口(8000)，可选")
    env_host: Optional[str] = Field(None, max_length=128, description="环境主机(http|https://127.0.0.1)")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestApiEnvUpdate(AutoTestApiEnvBase):
    pass


class AutoTestApiEnvSelect(AutoTestApiEnvBase):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["-updated_time"], description="排序字段")

    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")
