# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : user_schema.py
@DateTime: 2025/1/18 11:58
"""
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field

from backend.applications.base.services.scaffold import UpperStr


class UserBase(BaseModel):
    """用户公共字段。"""

    username: Optional[str] = Field(default=None, max_length=32, description="用户账号")
    alias: Optional[str] = Field(default=None, max_length=32, description="用户姓名")
    phone: Optional[str] = Field(default=None, max_length=20, description="用户电话")
    email: Optional[EmailStr] = Field(default=None, max_length=64, description="用户邮箱")
    motto: Optional[str] = Field(default=None, max_length=255, description="用户签名")
    avatar: Optional[str] = Field(default=None, max_length=255, description="用户头像")
    address: Optional[str] = Field(default=None, max_length=255, description="用户住址")
    gender: Optional[int] = Field(default=None, le=2, description="用户性别: 0未知 1男 2女")
    user_type: Optional[int] = Field(default=None, le=9, description="用户类型：0xx 1xx 2xx")
    is_superuser: Optional[bool] = Field(default=None, description="是否为超级管理员")
    emergency_name: Optional[str] = Field(default=None, max_length=32, description="紧急联系人")
    emergency_phone: Optional[str] = Field(default=None, max_length=20, description="紧急联系电话")
    dept_id: Optional[int] = Field(default=None, description="所属部门ID")
    role_ids: Optional[List[int]] = Field(default=None, description="角色ID列表")


class UserCreate(UserBase):
    """新增用户入参。"""

    username: str = Field(..., max_length=32, description="用户账号")
    password: str = Field(..., max_length=255, description="用户密码")
    alias: str = Field(..., max_length=32, description="用户姓名")
    email: EmailStr = Field(..., max_length=64, description="用户邮箱")
    gender: int = Field(default=0, ge=0, le=2, description="用户性别: 0未知 1男 2女")
    avatar: str = Field(default="/static/avatar/default/20250101010101.png", max_length=255, description="用户头像")
    user_type: int = Field(default=0, ge=0, le=9, description="用户类型：0xx 1xx 2xx")
    is_superuser: bool = Field(default=False, description="是否为超级管理员")
    role_ids: Optional[List[int]] = Field(default_factory=list, description="角色ID列表")
    created_user: Optional[UpperStr] = Field(default=None, max_length=16, description="创建人员")

    def create_dict(self):
        """
        转为落库字典：排除未设置字段，并移除role_ids（角色单独绑定）。

        :return: 可直接传入 UserCrud.create 的字段字典
        """
        data = self.model_dump(exclude_unset=True)
        data.pop("role_ids", None)
        return data


class UserUpdate(UserBase):
    """更新用户入参。"""

    user_id: int = Field(..., ge=1, description="用户ID")
    state: Optional[int] = Field(default=None, description="状态(0:启用, 1:禁用)")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class UserBatchDelete(BaseModel):
    """批量删除用户入参。"""

    user_ids: Optional[List[int]] = Field(None, description="用户ID列表")


class UserSelect(UserBase):
    """分页查询用户入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["id"], description="排序字段")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")


class UpdatePassword(BaseModel):
    """用户修改密码入参。"""

    old_password: str = Field(description="旧密码")
    new_password: str = Field(description="新密码")
