# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : department_schema.py
@DateTime: 2025/2/3 16:27
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from backend.applications.base.services.scaffold import UpperStr


class DepartmentCreate(BaseModel):
    """新增部门入参。"""

    code: str = Field(..., description="部门代码")
    name: str = Field(..., description="部门名称")
    description: Optional[str] = Field(default=None, description="部门描述")
    order: int = Field(default=0, description="排序")
    parent_id: int = Field(default=0, description="父部门ID")
    created_user: Optional[UpperStr] = Field(default=None, max_length=16, description="创建人员")

    def create_dict(self):
        """
        转为落库字典，仅包含请求中显式设置的字段。

        :return: 可直接传入DepartmentCrud.create的字段字典
        """
        return self.model_dump(exclude_unset=True)


class DepartmentUpdate(BaseModel):
    """更新部门入参。"""

    id: int = Field(..., description="部门ID")
    code: Optional[str] = Field(default=None, max_length=16, description="部门代码")
    name: Optional[str] = Field(default=None, max_length=64, description="部门名称")
    description: Optional[str] = Field(default=None, max_length=255, description="部门描述")
    order: Optional[int] = Field(default=None, ge=0, description="排序")
    parent_id: Optional[int] = Field(default=None, ge=0, description="父部门ID")
    updated_user: Optional[UpperStr] = Field(default=None, max_length=16, description="更新人员")

    def update_dict(self):
        """
        转为更新字典，排除id与未设置字段。

        :return: 可直接用于update_from_dict的字段字典
        """
        return self.model_dump(exclude_unset=True, exclude={"id"})


class DepartmentSelect(BaseModel):
    """分页查询部门入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="数据数量")
    order: List[str] = Field(default_factory=lambda: ["id"], description="排序字段")
    code: Optional[str] = Field(default=None, description="部门代码")
    name: Optional[str] = Field(default=None, description="部门名称")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")
    created_user: Optional[UpperStr] = Field(default=None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(default=None, max_length=16, description="更新人员")
    created_time: Optional[datetime] = Field(default=None, description="创建时间")
    updated_time: Optional[datetime] = Field(default=None, description="更新时间")


class DepartmentBatchDelete(BaseModel):
    """批量删除部门入参。"""

    department_ids: Optional[List[int]] = Field(None, description="部门ID列表")
