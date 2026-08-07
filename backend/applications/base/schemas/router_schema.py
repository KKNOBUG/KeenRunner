# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : router_schema.py
@DateTime: 2025/1/31 17:36
"""
from typing import Optional, List

from pydantic import BaseModel, Field

from backend.enums import HTTPMethod


class RouterBase(BaseModel):
    """路由公共字段（创建/更新/查询共用）。"""

    path: Optional[str] = Field(default=None, max_length=255, description="路由请求路径")
    method: Optional[HTTPMethod] = Field(default=None, description="路由请求方式")
    summary: Optional[str] = Field(default=None, max_length=255, description="路由作用简介")
    description: Optional[str] = Field(default=None, description="路由功能描述")
    tags: Optional[str] = Field(default=None, max_length=255, description="路由所属标签")


class RouterCreate(RouterBase):
    """新增路由入参。"""

    path: str = Field(..., max_length=255, description="路由请求路径")
    method: HTTPMethod = Field(..., description="路由请求方式")
    summary: str = Field(..., max_length=255, description="路由作用简介")
    tags: str = Field(..., max_length=255, description="路由所属标签")
    description: Optional[str] = Field(default=None, description="路由功能描述")

    def create_dict(self):
        """
        转为落库字典，仅包含请求中显式设置的字段。

        :return: 可直接传入 RouterCrud.create 的字段字典
        """
        return self.model_dump(exclude_unset=True)


class RouterUpdate(RouterBase):
    """更新路由入参。"""

    id: int = Field(..., description="路由ID")

    def update_dict(self):
        """
        转为更新字典，排除 id 与未设置字段。

        :return: 可直接用于 update_from_dict 的字段字典
        """
        return self.model_dump(exclude_unset=True, exclude={"id"})


class RouterSelect(RouterBase):
    """分页查询路由入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["id"], description="排序字段")
