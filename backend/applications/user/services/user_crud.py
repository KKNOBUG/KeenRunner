# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : user_crud.py
@DateTime: 2025/1/18 11:36
"""
from datetime import datetime
from typing import Optional, Union, List

from tortoise.exceptions import DoesNotExist

from backend.applications.base.schemas.token_schema import CredentialsSchema
from backend.applications.user.models.user_model import User
from backend.applications.user.schemas.user_schema import UserCreate, UserUpdate
from backend.core.exceptions.base_exceptions import NotFoundException, BaseExceptions, DataAlreadyExistsException
from backend.services.password import verify_password, get_password_hash
from backend.services.base_crud import BaseCrud


class UserCrud(BaseCrud[User, UserCreate, UserUpdate]):
    def __init__(self):
        super().__init__(model=User)

    async def get_by_id(self, user_id: int) -> Optional[User]:
        return await self.model.filter(id=user_id).first()

    async def get_by_username(self, username: str) -> Optional[User]:
        return await self.model.filter(username=username).first()

    async def get_by_alias(self, username: str) -> Optional[List[User]]:
        return await self.model.filter(username=username).all()

    async def authenticate(self, credentials: CredentialsSchema) -> Optional[Union[BaseExceptions, User]]:
        user = await self.model.filter(username=credentials.username).first()
        if not user:
            raise NotFoundException(message="用户名不存在")
        verified = verify_password(credentials.password, user.password)
        if not verified:
            raise NotFoundException(message="用户名或密码错误")
        if not user.is_deleted:
            raise NotFoundException(message="用户无效或已被禁用")
        return user

    async def update_last_login(self, id: int) -> None:
        user = await self.model.get(id=id)
        user.last_login = datetime.now()
        await user.save()

    async def create_user(self, user_in: UserCreate) -> User:
        username = user_in.username
        instances = await self.model.filter(username=username).all()
        if instances:
            raise DataAlreadyExistsException(message=f"用户(username={username})信息已存在")

        user_in.password = get_password_hash(password=user_in.password)
        instance = await self.create(user_in)
        return instance

    async def delete_user(self, user_id: int) -> User:
        instance = await self.select(user_id)
        if not instance:
            raise NotFoundException(message=f"用户(id={user_id})信息不存在")

        instance.is_deleted = 1
        await instance.save()
        return instance

    async def update_user(self, user_in: UserUpdate) -> User:
        user_id: int = user_in.id
        user_if: dict = {
            key: value for key, value in user_in.items()
            if value is not None
        }
        try:
            instance = await self.update(id=user_id, obj_in=user_if)
        except DoesNotExist as e:
            raise NotFoundException(message=f"用户(id={user_id})信息不存在")

        data = await instance.to_dict()
        return data


USER_CRUD = UserCrud()
