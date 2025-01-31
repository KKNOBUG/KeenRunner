# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : user_crud.py
@DateTime: 2025/1/18 11:36
"""
from datetime import datetime
from typing import Optional, Union

from backend.applications.base.schemas.tokens_schema import CredentialsSchema
from backend.applications.users.models.user_model import User
from backend.applications.users.schemas.user_schmea import UserCreate, UserUpdate
from backend.core.exceptions.base_exceptions import NotFoundException, BaseExceptions
from backend.services.password import verify_password, get_password_hash
from backend.services.base_crud import BaseCrud


class UserCrud(BaseCrud[User, UserCreate, UserUpdate]):
    def __init__(self):
        super().__init__(model=User)

    async def get_by_id(self, user_id: int) -> Optional[User]:
        return await self.model.filter(id=user_id).first()

    async def get_by_username(self, username: str) -> Optional[User]:
        return await self.model.filter(username=username).first()

    async def authenticate(self, credentials: CredentialsSchema) -> Optional[Union[BaseExceptions, User]]:
        user = await self.model.filter(username=credentials.username).first()
        if not user:
            return NotFoundException(message="无效的用户名")
        verified = verify_password(credentials.password, user.password)
        if not verified:
            raise NotFoundException(message="密码错误!")
        if not user.is_active:
            raise NotFoundException(message="用户已被禁用")
        return user

    async def update_last_login(self, id: int) -> None:
        user = await self.model.get(id=id)
        user.last_login = datetime.now()
        await user.save()

    async def create_user(self, user_in: UserCreate) -> User:
        user_in.password = get_password_hash(password=user_in.password)
        user_instance = await self.create(user_in)
        return user_instance

    async def delete_user(self, user_id: int) -> User:
        user_instance = await self.get(user_id)
        user_instance.is_active = 0
        await user_instance.save()
        return user_instance

USER_CRUD = UserCrud()
