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
from typing import Any, Dict, Tuple, Optional, List

from email_validator import EmailNotValidError, validate_email
from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.expressions import F, Q
from tortoise.transactions import in_transaction

from backend.applications.base.models.role_model import Role
from backend.applications.base.schemas.token_schema import CredentialsSchema
from backend.applications.base.services.role_crud import RoleCrud
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.department.services.department_crud import DepartmentCrud
from backend.applications.user.models.user_model import User
from backend.applications.user.schemas.user_schema import UserCreate, UserUpdate, UserBatchDelete
from backend.common.request.request_async_utils import HttpxClient
from backend.configure import LOGGER, PROJECT_CONFIG
from backend.core.exceptions import (
    DataAlreadyExistsException,
    NoPermissionException,
    NotFoundException,
    NoAuthenticateException,
    ParameterException,
    ResInvalidException,
)
from backend.enums import BuiltinRoleCode
from backend.services import verify_password, get_password_hash

# 管理员重置密码后的统一初始密码，用户登录后应自行修改
DEFAULT_RESET_PASSWORD: str = "KFuser01@!"

# 第三方迁移登录的演示账号，按账号规则直接放行，不请求第三方平台
THIRD_PARTY_DEMO_ACCOUNTS: Tuple[str, ...] = (
    "CS1001", "CS1002", "CS1003", "CS1004", "CS1005",
    "CS1006", "CS1007", "CS1008", "CS1009", "CS1010",
)

# 用户列表搜索规则：contains 为包含匹配，exact 为等值匹配；state 由默认值语义单独处理
USER_SEARCH_RULES: Dict[str, str] = {
    "username": "contains",
    "alias": "contains",
    "email": "contains",
    "phone": "contains",
    "motto": "contains",
    "address": "contains",
    "emergency_name": "contains",
    "emergency_phone": "contains",
    "gender": "exact",
    "user_type": "exact",
    "is_superuser": "exact",
    "dept_id": "exact",
}


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

    async def authenticate(self, credentials: CredentialsSchema) -> User:
        """
        校验用户名与密码，返回可登录用户。

        :param credentials: 登录凭证(username、password)
        :return: 用户实例
        """
        user = await self.model.filter(username=credentials.username).first()
        if not user:
            error_message: str = "用户名不存在"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [username={credentials.username}]"
            )
            raise NotFoundException(message=error_message)
        verified = verify_password(credentials.password, user.password)
        if not verified:
            error_message: str = "用户名或密码错误"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [user_id={user.id}, username={credentials.username}, password={credentials.password}]"
            )
            raise NoAuthenticateException(message=error_message)
        if user.state == 1:
            error_message: str = "用户异常或已注销"
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
        await user.save(update_fields=["last_login"])

    async def create_user(self, user_in: UserCreate) -> User:
        """
        创建用户并绑定角色。

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
        :return: 实际删除的用户ID列表，按入参顺序去重，不存在的ID跳过
        """
        user_ids: List[int] = list(dict.fromkeys(user_in.user_ids or []))
        if not user_ids:
            return []
        existing_ids: set = set(
            await self.model.filter(id__in=user_ids).values_list("id", flat=True)
        )
        deleted_ids: List[int] = [user_id for user_id in user_ids if user_id in existing_ids]
        if not deleted_ids:
            return []
        values: Dict[str, Any] = self.soft_delete_values()
        # 版本号递增使被删用户的全部已签发令牌立即失效
        values["token_version"] = F("token_version") + 1
        await self.model.filter(id__in=deleted_ids).update(**values)
        LOGGER.info(
            f"批量删除用户成功, "
            f"关键字段: [user_ids={deleted_ids}, count={len(deleted_ids)}]"
        )
        return deleted_ids

    async def update_user(self, user_in: UserUpdate) -> User:
        """
        根据user_id更新用户信息。

        :param user_in: 更新入参
        :return: 更新后的用户实例
        """
        user_id: int = user_in.user_id
        # 改密必须走专用接口：Pydantic 默认丢弃未知字段会让调用方误以为改成功，这里显式拒绝
        if "password" in user_in.model_fields_set:
            error_message: str = "不支持通过更新用户信息接口修改密码, 请使用修改密码接口"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [user_id={user_id}, username={user_in.username}]"
            )
            raise ParameterException(message=error_message)

        user_if: dict = user_in.model_dump(exclude_none=True)
        # 主键与角色关联不走模型行更新，角色由 update_roles 单独维护
        user_if.pop("user_id", None)
        user_if.pop("role_ids", None)
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

    async def update_user_with_roles(self, user_in: UserUpdate) -> User:
        """
        更新用户并在同一事务内同步角色绑定。

        :param user_in: 更新入参，显式传 role_ids 时重建角色，未传则保留既有授权
        :return: 更新后的用户实例
        """
        async with in_transaction():
            instance = await self.update_user(user_in=user_in)
            if "role_ids" in user_in.model_fields_set:
                await self.update_roles(instance, user_in.role_ids)
        return instance

    async def search_users(
            self,
            page: int,
            page_size: int,
            order: Optional[List[str]],
            filters: Dict[str, Any]
    ) -> Tuple[int, List[dict]]:
        """
        分页查询用户并组装角色与部门。

        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :param filters: 搜索字段映射，空值忽略
        :return: 用户总数与用户字典列表，主键字段为 user_id
        """
        total, instances = await self.list(
            page=page,
            page_size=page_size,
            order=order,
            search=self._build_search_q(filters),
            related=["roles"]
        )
        return total, await self._serialize_users(instances)

    @classmethod
    def _build_search_q(cls, filters: Dict[str, Any]) -> Q:
        """
        构建用户列表搜索条件。

        :param filters: 字段名到查询值的映射，空值忽略，state 不传时默认只查未删除用户
        :return: 组合后的查询条件
        """
        q = Q()
        for field, value in filters.items():
            if field == "state" or value is None or value == "":
                continue
            rule: Optional[str] = USER_SEARCH_RULES.get(field)
            if rule == "contains":
                q &= Q(**{f"{field}__contains": value})
            elif rule == "exact":
                q &= Q(**{field: value})
        state: Optional[int] = filters.get("state")
        q &= Q(state=state) if state is not None else Q(state=0)
        return q

    @classmethod
    async def _serialize_users(cls, instances: List[User]) -> List[dict]:
        """
        序列化用户列表并补齐角色与部门。

        :param instances: 已预取角色的用户实例列表
        :return: 用户字典列表，主键字段为 user_id，无有效部门的 dept 为空对象
        """
        dept_ids = {instance.dept_id for instance in instances if instance.dept_id}
        dept_map: Dict[int, dict] = {}
        if dept_ids:
            department_crud = DepartmentCrud()
            departments = await department_crud.get_by_conditions(only_one=False, on_error=False, id__in=dept_ids)
            for department in departments:
                dept_map[department.id] = await department.to_dict(replace_fields={"id": "dept_id"})
        data: List[dict] = []
        for instance in instances:
            item: dict = await instance.to_dict(
                exclude_fields=["password"],
                replace_fields={"id": "user_id"}
            )
            item.pop("dept_id", None)
            # 读取分页预取结果，不再逐行查询角色关联
            item["roles"] = [
                await role.to_dict(replace_fields={"id": "role_id"})
                for role in instance.roles.related_objects
            ]
            item["dept"] = dept_map.get(instance.dept_id, {})
            data.append(item)
        return data

    @classmethod
    async def _load_bind_roles(cls, role_ids: Optional[List[int]]) -> List[Role]:
        """
        批量校验待绑定角色。

        :param role_ids: 待绑定角色ID列表
        :return: 有效角色实例列表
        :raises ParameterException: 存在非法角色ID
        """
        unique_ids: List[int] = list(dict.fromkeys(role_ids or []))
        if not unique_ids:
            return []

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
        重置用户角色关联。

        :param user: 用户实例
        :param role_ids: 角色ID列表，空列表表示清空
        :return: None
        """
        roles: List[Role] = await cls._load_bind_roles(role_ids)
        await user.roles.clear()
        if roles:
            await user.roles.add(*roles)

    async def reset_password(self, user_id: int) -> Dict[str, Any]:
        """
        重置用户密码为默认值并吊销全部Token。

        :param user_id: 用户ID
        :return: 不含密码的用户字典
        :raises NoPermissionException: 目标用户为超级用户
        """
        instance = await self.get_or_error(id=user_id)
        if instance.is_superuser:
            error_message: str = "不允许重置超级用户密码"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)

        instance.password = get_password_hash(password=DEFAULT_RESET_PASSWORD)
        # 吊销用户所有Token
        instance.token_version += 1
        # 只写密码与版本号，避免整行回写覆盖并发变更的其他字段
        await instance.save(update_fields=["password", "token_version"])
        data = await instance.to_dict(exclude_fields=["id", "password"])
        return data

    async def update_password(self, user_id: int, new_password: str) -> User:
        """
        更新用户密码并吊销全部Token。

        :param user_id: 用户ID
        :param new_password: 新密码(明文)
        :return: 更新后的用户实例
        """
        instance = await self.get_by_id(user_id=user_id, on_error=True)
        instance.password = get_password_hash(password=new_password)
        instance.token_version += 1  # 吊销用户所有Token
        # 只写密码与版本号，避免整行回写覆盖并发变更的其他字段
        await instance.save(update_fields=["password", "token_version"])
        return instance

    async def change_password(self, user_id: int, old_password: str, new_password: str) -> Optional[User]:
        """
        校验旧密码后修改密码并吊销全部Token。

        :param user_id: 用户ID
        :param old_password: 旧密码(明文)
        :param new_password: 新密码(明文)
        :return: 更新后的用户实例；旧密码不匹配时返回None
        """
        instance = await self.get_or_error(user_id)
        if not verify_password(old_password, instance.password):
            return None
        return await self.update_password(user_id=user_id, new_password=new_password)

    async def logout(self, user_id: int) -> User:
        """
        吊销用户全部Token。

        :param user_id: 用户ID
        :return: 更新后的用户实例
        """
        instance = await self.get_by_id(user_id=user_id, on_error=True)
        instance.token_version += 1
        # 只写版本号，避免整行回写把并发提交的密码覆盖成旧值
        await instance.save(update_fields=["token_version"])
        return instance

    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        """
        归一第三方文本字段，空值统一为None。

        :param value: 第三方返回的原始字段值
        :return: 归一后的字符串或None
        """
        if value is None:
            return None
        text = str(value).strip().split("/")[0]

        return text or None

    @classmethod
    def _normalize_int(cls, value: Any, default: int = 0, minimum: int = 0, maximum: Optional[int] = None) -> int:
        """
        将第三方字段转为整数，非数字或越界值回落默认值。

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
        归一第三方邮箱，缺失或格式非法返回None。

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
        请求第三方平台校验用户名真实性并映射本平台用户字段。

        :param username: 用户账号
        :return: 是否真实有效与本平台用户字段字典，无效时返回(False, None)
        """
        if username in THIRD_PARTY_DEMO_ACCOUNTS:
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
                    url=PROJECT_CONFIG.THIRD_PARTY_USER_AUTH_URL,
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
