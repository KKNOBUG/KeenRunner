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
from tortoise.expressions import F

from backend.applications.base.schemas.token_schema import CredentialsSchema
from backend.applications.base.services.role_crud import RoleCrud
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.user.models.user_model import User
from backend.applications.user.schemas.user_schema import UserCreate, UserUpdate, UserBatchDelete
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    BaseExceptions,
    DataAlreadyExistsException,
    ParameterException,
    NoPermissionException
)
from backend.core.responses import ForbiddenResponse
from backend.services import verify_password, get_password_hash


class UserCrud(ScaffoldCrud[User, UserCreate, UserUpdate]):
    """用户 CRUD 与认证相关业务。"""

    def __init__(self):
        super().__init__(model=User)

    async def get_by_id(self, user_id: int, on_error: bool = True, **kwargs) -> Optional[User]:
        """
        按主键 ID 查询用户。

        :param user_id: 用户 ID
        :param on_error: 未找到时是否抛出 NotFoundException
        :param kwargs: 额外过滤条件
        :return: 用户实例或 None
        :raises ParameterException: user_id 为空
        :raises NotFoundException: on_error 为 True 且用户不存在
        """
        if not user_id:
            error_message: str = "查询用户信息失败, 参数(user_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.get_or_none(id=user_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询用户信息失败, 用户(id={user_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_username(self, username: str, on_error: bool = False, **kwargs) -> Optional[User]:
        """
        按登录账号查询用户。

        :param username: 用户账号
        :param on_error: 未找到时是否抛出 NotFoundException
        :param kwargs: 额外过滤条件
        :return: 用户实例或 None
        :raises ParameterException: username 为空
        :raises NotFoundException: on_error 为 True 且用户不存在
        """
        if not username:
            error_message: str = "查询用户信息失败, 参数(username)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.model.filter(username=username, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询用户信息失败, 用户(username={username})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_alias(self, alias: str, on_error: bool = False, **kwargs) -> Optional[User]:
        """
        按用户姓名（alias）查询单条用户。

        :param alias: 用户姓名
        :param on_error: 未找到时是否抛出 NotFoundException
        :param kwargs: 额外过滤条件
        :return: 用户实例或 None
        :raises ParameterException: alias 为空
        :raises NotFoundException: on_error 为 True 且用户不存在
        """
        if not alias:
            error_message: str = "查询用户信息失败, 参数(alias)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.model.filter(alias=alias, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询用户信息失败, 用户(alias={alias})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def authenticate(self, credentials: CredentialsSchema) -> Optional[Union[BaseExceptions, User]]:
        """
        校验用户名与密码，返回可登录用户。

        :param credentials: 登录凭证（username、password）
        :return: 用户实例
        :raises NotFoundException: 用户不存在或密码错误
        :raises NoPermissionException: 用户已禁用（state=1）
        """
        user = await self.model.filter(username=credentials.username).first()
        if not user:
            raise NotFoundException(message="用户名不存在")
        verified = verify_password(credentials.password, user.password)
        if not verified:
            raise NotFoundException(message="用户名或密码错误")
        if user.state == 1:
            raise NoPermissionException(message="用户待岗或已离职")
        return user

    async def update_last_login(self, user_id: int) -> None:
        """
        更新用户最后登录时间为当前时刻。

        :param user_id: 用户 ID
        :return: None
        :raises NotFoundException: 用户不存在
        """
        user = await self.get_by_id(user_id=user_id, on_error=True)
        user.last_login = datetime.now()
        await user.save()

    async def create_user(self, user_in: UserCreate) -> User:
        """
        创建用户：校验唯一性、哈希密码、落库并绑定角色。

        :param user_in: 新增用户入参
        :return: 新建的用户实例
        :raises DataAlreadyExistsException: 邮箱或账号已存在
        """
        email = user_in.email
        username = user_in.username
        instances = await self.get_by_conditions(only_one=True, on_error=False, email=email, username=username)
        if instances:
            raise DataAlreadyExistsException(message=f"用户(email={email},username={username})信息已存在")

        user_in.password = get_password_hash(password=user_in.password)
        instance = await self.create(user_in)
        await self.update_roles(instance, user_in.role_ids)
        return instance

    async def delete_user(self, user_id: int, **kwargs) -> User:
        """
        软删除单个用户并吊销全部 Token。

        :param user_id: 用户 ID
        :param kwargs: 额外查询条件
        :return: 更新后的用户实例
        :raises NotFoundException: 用户不存在
        """
        instance = await self.get_by_id(user_id=user_id, on_error=True, **kwargs)
        instance.state = 1
        instance.is_active = 0
        instance.token_version += 1  # 吊销用户所有Token
        await instance.save()
        return instance

    async def delete_users(self, user_in: UserBatchDelete) -> List[int]:
        """
        批量软删除用户并吊销 Token。

        :param user_in: 含 user_ids 的批量删除入参
        :return: 实际删除的用户 ID 列表
        """
        user_ids: Optional[List[int]] = user_in.user_ids
        if user_ids:
            deleted_ids = await self.model.filter(id__in=user_ids).exclude(state=1).values_list("id", flat=True)
            if deleted_ids:
                await self.model.filter(id__in=deleted_ids).update(state=1, token_version=F('token_version') + 1)
        else:
            deleted_ids = []
        return deleted_ids

    async def update_user(self, user_in: UserUpdate) -> User:
        """
        按 user_id 更新用户基础字段（不含角色，角色由 update_roles 单独处理）。

        :param user_in: 更新入参
        :return: 更新后的用户实例
        :raises NotFoundException: 用户不存在
        """
        user_id: int = user_in.user_id
        user_if: dict = user_in.model_dump(exclude_none=True)
        try:
            instance = await self.update(id=user_id, obj_in=user_if)
        except DoesNotExist as e:
            raise NotFoundException(message=f"用户(id={user_id})信息不存在")

        return instance

    @classmethod
    async def update_roles(cls, user: User, role_ids: List[int]) -> None:
        """
        重置用户角色关联：先清空再按 role_ids 重新绑定。

        :param user: 用户实例
        :param role_ids: 角色 ID 列表；空列表表示清空
        :return: None
        """
        await user.roles.clear()
        for role_id in role_ids or []:
            role_obj = await RoleCrud().get_or_error(id=role_id)
            await user.roles.add(role_obj)

    async def reset_password(self, user_id: int):
        """
        管理员重置用户密码为默认值并吊销 Token；超级用户不可重置。

        :param user_id: 用户 ID
        :return: 不含密码的用户字典，或 ForbiddenResponse
        """
        instance = await self.get_or_error(id=user_id)
        if instance.is_superuser:
            return ForbiddenResponse(message="不允许重置超级用户密码")

        instance.password = get_password_hash(password="123456")
        instance.token_version += 1  # 吊销用户所有Token
        await instance.save()
        data = await instance.to_dict(exclude_fields=["id", "password"])
        return data

    async def update_password(self, user_id: int, new_password: str) -> User:
        """
        用户修改密码：更新密码并吊销所有Token

        :param user_id: 用户ID
        :param new_password: 新密码（明文）
        :return: 更新后的用户实例
        """
        instance = await self.get_by_id(user_id=user_id, on_error=True)
        instance.password = get_password_hash(password=new_password)
        instance.token_version += 1  # 吊销用户所有Token
        await instance.save()
        return instance

    async def logout(self, user_id: int) -> User:
        """
        用户主动登出：吊销所有Token

        :param user_id: 用户ID
        :return: 更新后的用户实例
        """
        instance = await self.get_by_id(user_id=user_id, on_error=True)
        instance.token_version += 1  # 吊销用户所有Token
        await instance.save()
        return instance
