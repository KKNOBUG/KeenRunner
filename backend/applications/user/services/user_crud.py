# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : user_crud.py
@DateTime: 2025/1/18 11:36
"""
import traceback
from datetime import datetime
from typing import Any, Dict, Tuple, Optional, Union, List

from email_validator import EmailNotValidError, validate_email
from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.transactions import in_transaction

from backend.applications.base.models.role_model import Role
from backend.applications.base.schemas.token_schema import CredentialsSchema
from backend.applications.base.services.role_crud import RoleCrud
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.department.services.department_crud import DepartmentCrud
from backend.applications.user.models.user_model import User
from backend.applications.user.schemas.user_schema import UserCreate, UserUpdate, UserBatchDelete
from backend.common.request.request_async_utils import HttpxClient
from backend.configure import LOGGER
from backend.core.exceptions import (
    BaseExceptions,
    DataAlreadyExistsException,
    NoPermissionException,
    NotFoundException,
    NoAuthenticateException,
    ParameterException,
    ResInvalidException,
)
from backend.enums import BuiltinRoleCode
from backend.services import verify_password, get_password_hash


class UserCrud(ScaffoldCrud[User, UserCreate, UserUpdate]):

    def __init__(self):
        super().__init__(model=User)

    async def get_by_id(self, user_id: int, on_error: bool = True, **kwargs) -> Optional[User]:
        """
        根据主键ID查询用户。

        :param user_id: 用户ID
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 用户实例或None
        """
        if not user_id:
            error_message: str = "查询用户信息失败, 参数[user_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.get_or_none(id=user_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询用户信息失败, 记录[id={user_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_username(self, username: str, on_error: bool = False, **kwargs) -> Optional[User]:
        """
        根据登录账号查询用户。

        :param username: 用户账号
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 用户实例或None
        """
        if not username:
            error_message: str = "查询用户信息失败, 参数[username]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.model.filter(username=username, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询用户信息失败, 记录[username={username}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_alias(self, alias: str, on_error: bool = False, **kwargs) -> Optional[User]:
        """
        根据用户姓名(alias)查询单条用户。

        :param alias: 用户姓名
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 用户实例或None
        """
        if not alias:
            error_message: str = "查询用户信息失败, 参数[alias]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.model.filter(alias=alias, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询用户信息失败, 记录[alias={alias}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def authenticate(self, credentials: CredentialsSchema) -> Optional[Union[BaseExceptions, User]]:
        """
        校验用户名与密码，返回可登录用户。

        :param credentials: 登录凭证(username、password)
        :return: 用户实例
        """
        user = await self.model.filter(username=credentials.username).first()
        if not user:
            error_message: str = "用户名不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        verified = verify_password(credentials.password, user.password)
        if not verified:
            error_message: str = "用户名或密码错误"
            LOGGER.error(error_message)
            raise NoAuthenticateException(message=error_message)
        if user.state == 1:
            error_message: str = "用户待岗或已离职"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)
        return user

    async def update_last_login(self, user_id: int) -> None:
        """
        更新用户最后登录时间为当前时刻。

        :param user_id: 用户ID
        :return: None
        """
        user = await self.get_by_id(user_id=user_id, on_error=True)
        user.last_login = datetime.now()
        await user.save()

    async def create_user(self, user_in: UserCreate) -> User:
        """
        创建用户：校验唯一性、哈希密码、单事务落库并绑定角色。

        :param user_in: 新增用户入参
        :return: 新建的用户实例
        """
        username = user_in.username
        if await self.model.filter(username=username).exists():
            error_message: str = f"新增用户信息失败, 记录[username={username}]已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        # 先校验角色再落库：角色非法时不能留下无角色用户，也避免并发下只写一半
        roles: List[Role] = await self._load_bind_roles(user_in.role_ids)
        user_data = user_in.create_dict()
        user_data["password"] = get_password_hash(password=user_in.password)
        try:
            async with in_transaction():
                instance = await self.create(user_data)
                if roles:
                    await instance.roles.add(*roles)
        except IntegrityError as e:
            # 并发同名：预校验会同时通过，靠username唯一索引收敛为业务已存在并回滚角色绑定
            error_message: str = f"新增用户信息失败, 记录[username={username}]信息已存在"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataAlreadyExistsException(message=error_message) from e
        return instance

    async def delete_user(self, user_id: int, **kwargs) -> User:
        """
        软删除单个用户并吊销全部Token。

        :param user_id: 用户ID
        :param kwargs: 额外查询条件
        :return: 更新后的用户实例
        """
        instance = await self.get_by_id(user_id=user_id, on_error=True, **kwargs)
        instance = await self.soft_delete(id=instance.id)
        # 吊销用户所有Token
        instance.token_version += 1
        await instance.save(update_fields=["token_version"])
        return instance

    async def delete_users(self, user_in: UserBatchDelete) -> List[int]:
        """
        批量软删除用户并吊销Token。

        :param user_in: 含user_ids的批量删除入参
        :return: 实际删除的用户ID列表
        """
        user_ids: Optional[List[int]] = user_in.user_ids
        if not user_ids:
            return []

        deleted_ids: List[int] = []
        for uid in user_ids:
            try:
                await self.delete_user(int(uid))
                deleted_ids.append(int(uid))
            except NotFoundException:
                continue
        return deleted_ids

    async def update_user(self, user_in: UserUpdate) -> User:
        """
        根据user_id更新用户信息。

        :param user_in: 更新入参
        :return: 更新后的用户实例
        """
        user_id: int = user_in.user_id
        user_if: dict = user_in.model_dump(exclude_none=True)
        # 邮箱非必填：显式传空表示清空，exclude_none 会把它当成未修改，需要单独回填
        if "email" in user_in.model_fields_set:
            user_if["email"] = user_in.email
        try:
            instance = await self.update(id=user_id, obj_in=user_if)
        except DoesNotExist:
            error_message: str = f"更新用户信息失败, 记录[id={user_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        except IntegrityError as e:
            # 并发改名撞username唯一索引与创建同口径，返回已存在而非服务异常
            error_message: str = f"更新用户信息失败, 记录[id={user_id}]的账号与已有记录冲突"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataAlreadyExistsException(message=error_message) from e

        return instance

    @classmethod
    async def _load_bind_roles(cls, role_ids: Optional[List[int]]) -> List[Role]:
        """
        批量校验待绑定角色：一次查库，非法ID统一报400400，避免逐条查询与半途清空。

        :param role_ids: 待绑定角色ID列表
        :return: 有效角色实例列表
        """
        unique_ids: List[int] = list(dict.fromkeys(role_ids or []))
        if not unique_ids:
            return []
        # Role 采用硬删除，无 state 字段；按主键一次取全，缺失即视为非法引用
        roles: List[Role] = await Role.filter(id__in=unique_ids)
        found_ids = {role.id for role in roles}
        missing_ids = [role_id for role_id in unique_ids if role_id not in found_ids]
        if missing_ids:
            error_message: str = f"角色信息不存在, 非法角色ID: {missing_ids}"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        return roles

    @classmethod
    async def update_roles(cls, user: User, role_ids: List[int]) -> None:
        """
        重置用户角色关联：先校验再清空后重建，非法角色不会破坏已有绑定。

        :param user: 用户实例
        :param role_ids: 角色ID列表；空列表表示清空
        :return: None
        """
        roles: List[Role] = await cls._load_bind_roles(role_ids)
        await user.roles.clear()
        if roles:
            await user.roles.add(*roles)

    async def reset_password(self, user_id: int) -> Dict[str, Any]:
        """
        管理员重置用户密码为默认值并吊销Token；超级用户不可重置。

        :param user_id: 用户ID
        :return: 不含密码的用户字典
        :raises NoPermissionException: 目标用户为超级用户
        """
        instance = await self.get_or_error(id=user_id)
        if instance.is_superuser:
            error_message: str = "不允许重置超级用户密码"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)

        instance.password = get_password_hash(password="KFuser01@!")
        instance.token_version += 1  # 吊销用户所有Token
        await instance.save()
        data = await instance.to_dict(exclude_fields=["id", "password"])
        return data

    async def update_password(self, user_id: int, new_password: str) -> User:
        """
        用户修改密码：更新密码并吊销所有Token。

        :param user_id: 用户ID
        :param new_password: 新密码(明文)
        :return: 更新后的用户实例
        """
        instance = await self.get_by_id(user_id=user_id, on_error=True)
        instance.password = get_password_hash(password=new_password)
        instance.token_version += 1  # 吊销用户所有Token
        await instance.save()
        return instance

    async def logout(self, user_id: int) -> User:
        """
        用户主动登出：吊销所有Token。

        :param user_id: 用户ID
        :return: 更新后的用户实例
        """
        instance = await self.get_by_id(user_id=user_id, on_error=True)
        instance.token_version += 1
        await instance.save()
        return instance

    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        """
        第三方字段归一：去首尾空白，空值统一为None。

        :param value: 第三方返回的原始字段值
        :return: 归一后的字符串或None
        """
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def _normalize_int(cls, value: Any, default: int = 0, minimum: int = 0, maximum: Optional[int] = None) -> int:
        """
        第三方字段转整数：非数字或越界值一律回落默认值，避免脏数据打断自动注册。

        :param value: 第三方返回的原始字段值
        :param default: 无法转换或越界时的默认值
        :param minimum: 允许的下界
        :param maximum: 允许的上界，None表示不限制
        :return: 合法的整数或默认值
        """
        try:
            number = int(str(value).strip())
        except (TypeError, ValueError):
            return default
        if number < minimum or (maximum is not None and number > maximum):
            return default
        return number

    @classmethod
    def _normalize_email(cls, value: Any) -> Optional[str]:
        """
        第三方邮箱归一：缺失或格式非法一律降级为None；邮箱已非必填，不能因脏数据阻断自动注册。

        :param value: 第三方返回的邮箱
        :return: 合法邮箱或None
        """
        email = cls._normalize_text(value)
        if not email:
            return None
        try:
            return validate_email(email, check_deliverability=False).normalized
        except EmailNotValidError:
            LOGGER.warning(f"第三方邮箱[{email}]格式非法, 自动注册时按未填写处理")
            return None

    @classmethod
    async def confirm_user_authenticate(cls, username: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        请求第三方平台校验用户名的真实性，并映射为本平台用户信息字段。

        字段映射：
            - loginName -> username
            - username -> alias（缺失时回落username）
            - telPhone -> phone（缺失为None）
            - gender -> gender（非数字或越界值回落0）
            - email -> email（缺失或非法为None，邮箱非必填）
            - userType -> user_type（非数字或越界值回落0）

        :param username: 用户账号
        :return: (是否真实有效, 本平台用户信息字段字典)；无效时返回(False, None)
        """
        if username in ["CS1001", "CS1002", "CS1003", "CS1004", "CS1005", "CS1006", "CS1007", "CS1008", "CS1009"]:
            return True, {
                "username": username,
                "alias": f"村上春树-{username}",
                "phone": f"1580000{username[-4:]}",
                "gender": 0,
                "email": f"{username}@test.com",
                "user_type": 0,
                "is_superuser": False,
                "dept_id": 2,
                "role_ids": [2],
            }
        try:
            async with HttpxClient(timeout=5) as client:
                utils = await client.post(
                    url="http://10.240.105.88:9999/userInfo/findByLoginName",
                    data={"loginName": username, "state": "1"},
                )
                payload: Dict[str, Any] = await utils.json_resp()
        except Exception as e:
            if isinstance(e, ResInvalidException):
                e = e.message
            LOGGER.error(f"用户名[{username}]真实性校验异常: {e}")
            return False, None

        data: Dict[str, Any] = payload.get("data") or {}
        if payload.get("retCd") != "000000" or not data or data.get("loginName") != username:
            LOGGER.error(f"用户名[{username}]真实性校验失败, 拒绝自动注册")
            return False, None

        role = await RoleCrud().get_by_code(role_code=BuiltinRoleCode.USER.value, on_error=True)
        dept = await DepartmentCrud().get_by_code(code="AUTOTEST_DEPT", name="技术测试团队", on_error=True)
        build_user: Dict[str, Any] = {
            "username": username,
            # 第三方可能不返回姓名/邮箱/电话等字段，缺失值必须归一，避免触发必填校验或落库失败
            "alias": cls._normalize_text(data.get("username")) or username,
            "phone": cls._normalize_text(data.get("telPhone")),
            "gender": cls._normalize_int(data.get("gender"), maximum=2),
            "email": cls._normalize_email(data.get("email")),
            "user_type": cls._normalize_int(data.get("userType"), maximum=9),
            "is_superuser": False,
            "dept_id": dept.id,
            "role_ids": [role.id],
            "created_user": "ADMIN",
        }
        LOGGER.info(f"用户名[{username}]真实性校验成功: {build_user}")
        return True, build_user
