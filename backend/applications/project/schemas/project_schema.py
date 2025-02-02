# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : project_schema.py
@DateTime: 2025/2/2 13:38
"""
from typing import Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(example="爱吃大锅饭")
    initiator: str = Field(example="张三")
    test_captain: str = Field(default=None, example="李四")
    test_team: str = Field(default=None, example="测试一部")
    dev_captain: str = Field(default=None, example="王五")
    dev_team: str = Field(default=None, example="开发一部")
    release: str = Field(example="0.1.5")
    is_active: Optional[bool] = True
    created_user: str = Field(default=None, example="赵六")

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class ProjectUpdate(BaseModel):
    id: int
    name: Optional[str] = None
    initiator: Optional[str] = None
    test_captain: Optional[str] = None
    test_team: Optional[str] = None
    dev_captain: Optional[str] = None
    dev_team: Optional[str] = None
    release: Optional[str] = None
    updated_at: Optional[str] = None
    is_active: Optional[bool] = True
