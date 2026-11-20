# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : user_view.py
@DateTime: 2025/1/18 10:28
"""
import traceback
from datetime import timedelta, datetime, timezone
from typing import List, Optional, Tuple

from fastapi import APIRouter, Body, Query, Depends, Request
from tortoise.exceptions import IntegrityError

from backend.applications.base.dependencies import get_menu_crud, get_router_crud
from backend.applications.base.models.role_model import Role
from backend.applications.base.schemas.token_schema import CredentialsSchema, JWTOut, JWTPayload
from backend.applications.base.services.menu_crud import MenuCrud
from backend.applications.base.services.router_crud import RouterCrud
from backend.applications.department.dependencies import get_dept_crud
from backend.applications.department.services.department_crud import DepartmentCrud
from backend.applications.user.dependencies import DependUserServices
from backend.applications.user.models.user_model import User
from backend.applications.user.schemas.user_schema import (
    UserCreate,
    UserUpdate,
    UserSelect,
    UpdatePassword,
    UserBatchDelete,
)
from backend.applications.user.services.user_crud import UserCrud
from backend.configure import LOGGER, PROJECT_CONFIG, GLOBAL_CONFIG
from backend.core.exceptions import (
    DataAlreadyExistsException,
    DataBaseStorageException,
    NotFoundException,
    NoAuthenticateException,
    NoPermissionException,
    ParameterException
)
from backend.core.responses import (
    ForbiddenResponse,
    NotFoundResponse,
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    DataAlreadyExistsResponse,
    DataBaseStorageResponse,
    UnauthorizedResponse,
)
from backend.enums import BuiltinRoleCode
from backend.services import CTX_USER_ID, AuthControl, create_access_token
from backend.services.dependency import load_request_roles

# 公开端点：登录与幂等登出不要求令牌（登出由中间件执行可选认证）
user_public = APIRouter()

# 仅认证端点：当前登录用户自身操作，不做 RBAC 鉴权
user_self = APIRouter()

# 权限端点：用户管理类接口
user_secure = APIRouter()


@user_secure.post("/create", summary="新增用户", description="新增用户信息")
async def create_user(
        user_in: UserCreate = Body(..., description="用户信息"),
        user_crud: UserCrud = DependUserServices,
):
    """
    新增用户。

    :param user_in: 用户入参
    :param user_crud: 用户 CRUD 服务
    :return: 统一响应，成功时 data 为新增后的用户信息，不含密码，主键字段为 user_id
    """
    try:
        instance = await user_crud.create_user(user_in=user_in)
        data = await instance.to_dict(
            exclude_fields=["password"],
            replace_fields={"id": "user_id"}
        )
        return SuccessResponse(message="新增成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except IntegrityError:
        error_message: str = "新增失败, 用户已存在"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [username={user_in.username}, phone={user_in.phone}, email={user_in.email}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return DataAlreadyExistsResponse(message=error_message)
    except Exception:
        error_message: str = "暂时无法新增用户信息，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [username={user_in.username}, alias={user_in.alias}, dept_id={user_in.dept_id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@user_secure.delete("/delete", summary="删除用户", description="根据id删除用户信息")
async def delete_user(
        user_id: int = Query(..., description="用户ID"),
        user_crud: UserCrud = DependUserServices,
):
    """
    软删除指定用户。

    :param user_id: 用户 ID
    :param user_crud: 用户 CRUD 服务
    :return: 统一响应，成功时 data 为删除后的用户信息，不含密码，主键字段为 user_id
    """
    try:
        instance = await user_crud.delete_user(user_id)
        data = await instance.to_dict(
            exclude_fields=["password"],
            replace_fields={"id": "user_id"}
        )
        return SuccessResponse(message="删除成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法删除用户信息，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [user_id={user_id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@user_secure.post("/deletes", summary="批量删除用户", description="根据id列表批量删除用户信息")
async def batch_delete_users(
        user_in: UserBatchDelete = Body(..., description="用户信息"),
        user_crud: UserCrud = DependUserServices,
):
    """
    批量软删除用户。

    :param user_in: 批量删除入参，user_ids 为空时不执行删除
    :param user_crud: 用户 CRUD 服务
    :return: 统一响应，data 中 deleted 为实际删除的 ID 列表，total 为条数
    """
    try:
        deleted_ids = await user_crud.delete_users(user_in=user_in)
        deleted_num = len(deleted_ids)
        return SuccessResponse(message="批量删除成功", data={"deleted": deleted_ids}, total=deleted_num)
    except Exception:
        error_message: str = "暂时无法批量删除用户信息，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [user_ids={user_in.user_ids}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@user_secure.post("/update", summary="更新用户", description="根据id更新用户信息")
async def update_user(
        user_in: UserUpdate = Body(..., description="用户信息"),
        user_crud: UserCrud = DependUserServices,
):
    """
    更新用户信息。

    :param user_in: 用户入参，user_id 指定待更新用户，显式传 role_ids 时同步角色绑定
    :param user_crud: 用户 CRUD 服务
    :return: 统一响应，成功时 data 为更新后的用户信息，不含密码，主键字段为 user_id
    """
    try:
        instance = await user_crud.update_user_with_roles(user_in=user_in)
        data = await instance.to_dict(
            exclude_fields=["password"],
            replace_fields={"id": "user_id"}
        )
        return SuccessResponse(message="更新成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except IntegrityError:
        error_message: str = "更新失败, 用户已存在"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [user_id={user_in.user_id}, username={user_in.username}, phone={user_in.phone}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return DataAlreadyExistsResponse(message=error_message)
    except Exception:
        error_message: str = "暂时无法更新用户信息，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [user_id={user_in.user_id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@user_secure.get("/get", summary="查询用户", description="根据id查询用户信息")
async def get_user(
        user_id: int = Query(..., description="用户ID"),
        user_crud: UserCrud = DependUserServices,
        dept_crud: DepartmentCrud = Depends(get_dept_crud),
):
    """
    根据 ID 查询用户详情。

    :param user_id: 用户 ID
    :param user_crud: 用户 CRUD 服务
    :param dept_crud: 部门 CRUD 服务
    :return: 统一响应，成功时 data 为用户详情，含 roles 与 dept，主键字段为 user_id
    """
    try:
        instance = await user_crud.get_by_id(user_id=user_id, state__not=1)
        if not instance:
            return NotFoundResponse(message=f"未找到[id={user_id}]的用户记录，请稍后重试")
        data: dict = await instance.to_dict(
            m2m=True,
            exclude_fields=["password"],
            replace_fields={"id": "user_id"},
            m2m_replace_fields={"roles": {"id": "role_id"}}
        )
        dept_id = data.pop("dept_id", None)
        data["dept"] = {}
        if dept_id:
            # 脏部门引用降级为空对象，不能让单条坏数据拖垮详情查询
            department_instance = await dept_crud.get_or_none(id=dept_id)
            if department_instance:
                data["dept"] = await department_instance.to_dict(replace_fields={"id": "dept_id"})
        return SuccessResponse(message="查询成功", data=data, total=1)
    except Exception:
        error_message: str = "暂时无法查询用户信息，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [user_id={user_id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@user_secure.get("/by_username", summary="查询用户(按用户名)", description="根据username查询用户信息")
async def get_user_by_username(
        username: str = Query(..., description="用户名称"),
        user_crud: UserCrud = DependUserServices,
):
    """
    根据账号查询用户。

    :param username: 用户账号
    :param user_crud: 用户 CRUD 服务
    :return: 统一响应，成功时 data 为用户信息，不含密码，主键字段为 user_id
    """
    try:
        instance = await user_crud.get_by_username(username=username)
        if not instance:
            return NotFoundResponse(message=f"未找到[username={username}]的用户记录，请稍后重试")
        data: dict = await instance.to_dict(exclude_fields=["password"], replace_fields={"id": "user_id"})
        return SuccessResponse(message="查询成功", data=data, total=1)
    except Exception:
        error_message: str = "暂时无法查询用户信息，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [username={username}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@user_secure.get("/list", summary="查询用户列表(Query)", description="根据条件分页查询用户列表信息(Query)")
async def search_users(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, le=99999, description="每页数量"),
        order: list = Query(default_factory=lambda: ["id"], description="排序字段"),
        username: str = Query(default=None, description="用户账号，用于搜索"),
        alias: str = Query(default=None, description="用户名称，用于搜索"),
        email: str = Query(default=None, description="邮箱地址"),
        phone: str = Query(default=None, description="用户电话"),
        gender: int = Query(default=None, description="用户性别: 0未知 1男 2女"),
        user_type: int = Query(default=None, description="用户类型：0xx 1xx 2xx"),
        state: int = Query(default=None, description="状态(0:启用, 1:禁用)"),
        is_superuser: bool = Query(default=None, description="是否为超级管理员"),
        dept_id: int = Query(default=None, description="部门ID"),
        user_crud: UserCrud = DependUserServices,
):
    """
    分页查询用户列表。

    :param page: 页码
    :param page_size: 每页条数
    :param order: 排序字段
    :param username: 用户账号
    :param alias: 用户姓名
    :param email: 邮箱地址
    :param phone: 用户电话
    :param gender: 用户性别：0 未知、1 男、2 女
    :param user_type: 用户类型
    :param state: 状态（0 启用、1 禁用）
    :param is_superuser: 是否为超级管理员
    :param dept_id: 部门 ID
    :param user_crud: 用户 CRUD 服务
    :return: 统一响应，成功时 data 为用户列表，含 roles 与 dept，不含密码，total 为总条数
    """
    try:
        total, data = await user_crud.search_users(
            page=page,
            page_size=page_size,
            order=order,
            filters={
                "username": username,
                "alias": alias,
                "email": email,
                "phone": phone,
                "gender": gender,
                "user_type": user_type,
                "state": state,
                "is_superuser": is_superuser,
                "dept_id": dept_id,
            }
        )
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception:
        error_message: str = "暂时无法查询用户信息，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [page={page}, page_size={page_size}, username={username}, dept_id={dept_id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@user_secure.post("/search", summary="查询用户列表(Body)", description="根据条件分页查询用户列表信息(Body)")
async def list_users(
        user_in: UserSelect = Body(..., description="查询条件"),
        user_crud: UserCrud = DependUserServices,
):
    """
    分页查询用户列表。

    :param user_in: 用户查询入参
    :param user_crud: 用户 CRUD 服务
    :return: 统一响应，成功时 data 为用户列表，含 roles 与 dept，不含密码，total 为总条数
    """
    try:
        total, data = await user_crud.search_users(
            page=user_in.page,
            page_size=user_in.page_size,
            order=user_in.order,
            filters={
                "username": user_in.username,
                "alias": user_in.alias,
                "email": user_in.email,
                "phone": user_in.phone,
                "motto": user_in.motto,
                "address": user_in.address,
                "emergency_name": user_in.emergency_name,
                "emergency_phone": user_in.emergency_phone,
                "gender": user_in.gender,
                "user_type": user_in.user_type,
                "is_superuser": user_in.is_superuser,
                "dept_id": user_in.dept_id,
                "state": user_in.state,
            }
        )
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception:
        error_message: str = "暂时无法查询用户信息，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [page={user_in.page}, page_size={user_in.page_size}, username={user_in.username}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@user_self.post("/update_password", summary="更新用户密码(个人)", description="根据当前登录用户ID修改密码")
async def update_user_password(
        req_in: UpdatePassword,
        user_crud: UserCrud = DependUserServices,
):
    """
    修改当前登录用户密码并吊销已签发令牌。

    :param req_in: 修改密码入参
    :param user_crud: 用户 CRUD 服务
    :return: 统一响应，成功时 data 为更新后的用户信息，不含密码
    """
    try:
        user_id = CTX_USER_ID.get()
        instance = await user_crud.change_password(
            user_id=user_id,
            old_password=req_in.old_password,
            new_password=req_in.new_password
        )
        if instance is None:
            return FailureResponse(message="旧密码验证失败")

        data = await instance.to_dict(
            exclude_fields=["password"],
            replace_fields={"id": "user_id"}
        )
        return SuccessResponse(message="更新成功", data=data, total=1)
    except Exception:
        error_message: str = "暂时无法更新用户密码，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [user_id={CTX_USER_ID.get()}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@user_secure.post("/reset_password", summary="更新用户密码(重置)", description="根据id重置用户密码")
async def reset_password(
        user_id: int = Body(..., description="用户ID", embed=True),
        user_crud: UserCrud = DependUserServices,
):
    """
    重置指定用户密码。

    :param user_id: 用户 ID
    :param user_crud: 用户 CRUD 服务
    :return: 统一响应，data 为重置后的账号信息，不含 id 与密码
    """
    try:
        data = await user_crud.reset_password(user_id)
        return SuccessResponse(message="重置成功", data=data, total=1)
    except NoPermissionException:
        raise
    except Exception:
        error_message: str = "暂时无法重置用户密码，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [user_id={user_id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


# ==================== 公开端点：幂等登出（由中间件执行可选认证） ====================
@user_public.post("/logout", summary="注销访问令牌", description="注销当前登录用户的所有会话信息")
async def logout(
        request: Request,
        user_crud: UserCrud = DependUserServices,
):
    """
    注销当前登录用户的所有会话。

    :param request: 当前请求，可选认证结果由中间件写入 request.state.current_user
    :param user_crud: 用户 CRUD 服务
    :return: 统一响应，无有效令牌时 data 为空对象
    """
    current_user: Optional[User] = getattr(request.state, "current_user", None)
    if current_user is None:
        return SuccessResponse(message="登录已过期，请重新登录", data={}, total=0)
    try:
        instance = await user_crud.logout(user_id=int(current_user.id))
        data = await instance.to_dict(
            exclude_fields=["password"],
            replace_fields={"id": "user_id"}
        )
        LOGGER.info(f"用户[{current_user.username}]登出成功")
        return SuccessResponse(message="登出成功", data=data, total=1)
    except Exception:
        error_message: str = "暂时无法注销访问令牌，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [user_id={current_user.id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


def _build_login_payload(user: User) -> dict:
    """
    组装登录成功响应体。

    :param user: 已通过校验的用户实例
    :return: 可直接返回给前端的登录数据
    """
    access_token_expires = timedelta(minutes=PROJECT_CONFIG.AUTH_JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    expire_time = datetime.now(timezone.utc) + access_token_expires
    data = JWTOut(
        access_token=create_access_token(
            data=JWTPayload(
                user_id=user.id,
                username=user.username,
                state=user.state,
                is_superuser=user.is_superuser,
                token_version=user.token_version,
                exp=expire_time,
            ),
        ),
        user_id=user.id,
        username=user.username,
        alias=user.alias,
        email=user.email,
        phone=user.phone,
        motto=user.motto,
        avatar=user.avatar,
        state=user.state,
        is_superuser=user.is_superuser,
        last_login=user.last_login.strftime(GLOBAL_CONFIG.DATETIME_FORMAT2) if user.last_login else None,
        exp=expire_time.astimezone().strftime(GLOBAL_CONFIG.DATETIME_FORMAT2),
    )
    return data.model_dump()


async def _load_admin_flag(request: Request, user: User) -> Tuple[bool, List[Role]]:
    """
    判定当前用户是否具备管理员权限并返回其角色。

    :param request: 当前请求
    :param user: 已认证用户
    :return: (是否超管或管理员角色, 角色列表)
    """
    # 超管不查角色绑定，避免多一次查询
    if user.is_superuser:
        return True, []
    roles: List[Role] = await load_request_roles(request=request, user=user)
    return BuiltinRoleCode.includes_admin(role.code for role in roles), roles


# ==================== 公开端点：登录 ====================
@user_public.post("/login", summary="用户登录", description="验证用户密码和状态并签发访问令牌")
async def login(
        credentials: CredentialsSchema = Body(..., description="用户信息"),
        user_crud: UserCrud = DependUserServices,
):
    """
    校验账号密码与状态，刷新最后登录时间并签发访问令牌。

    :param credentials: 登录凭证（账号、密码）
    :param user_crud: 用户 CRUD 服务
    :return: 统一响应，成功时 data 为 JWTOut，含令牌与用户公开信息
    """
    try:
        try:
            user: User = await user_crud.authenticate(credentials)
        except (NotFoundException, NoAuthenticateException):
            return UnauthorizedResponse(message="用户名或密码错误")
        except NoPermissionException as e:
            return ForbiddenResponse(message=str(e.message))
        try:
            await user_crud.update_last_login(user_id=user.id)
        except (ParameterException, NotFoundException):
            return FailureResponse(message="登录失败，请稍后重试")
        LOGGER.info(f"用户[{credentials.username}]登录成功")
        return SuccessResponse(message="登录成功", data=_build_login_payload(user))
    except Exception:
        # 原始异常与口令信息只进日志，对外统一为可重试提示
        error_message: str = "登录失败，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [username={credentials.username}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@user_public.post("/transfer_login", summary="第三方迁移登录", description="账号不存在时按第三方平台校验并接纳为新用户后生成令牌")
async def transfer_login(
        credentials: CredentialsSchema = Body(..., description="用户信息"),
        user_crud: UserCrud = DependUserServices,
):
    """
    本地账号不存在时经第三方校验并自动注册后登录。

    :param credentials: 登录凭证（账号、密码）
    :param user_crud: 用户 CRUD 服务
    :return: 统一响应，成功时 data 为 JWTOut，含令牌与用户公开信息
    """
    try:
        try:
            user: User = await user_crud.authenticate(credentials)
        except NotFoundException:
            valid, third_user = await user_crud.confirm_user_authenticate(username=credentials.username)
            if not valid:
                return UnauthorizedResponse(message="用户名或密码错误")
            user = await user_crud.create_user(user_in=UserCreate(password=credentials.password, **third_user))
            LOGGER.info(f"用户名[{credentials.username}]注册成功")
        except NoPermissionException as e:
            return ForbiddenResponse(message=str(e.message))
        except NoAuthenticateException:
            return UnauthorizedResponse(message="用户名或密码错误")
        try:
            await user_crud.update_last_login(user_id=user.id)
        except (ParameterException, NotFoundException):
            return FailureResponse(message="登录失败，请稍后重试")
        return SuccessResponse(message="登录成功", data=_build_login_payload(user))
    except Exception:
        # 原始异常与口令信息只进日志，对外统一为可重试提示
        error_message: str = "登录失败，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [username={credentials.username}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


# ==================== 仅认证端点：当前用户自身 ====================
@user_self.post("/get_userinfo", summary="查询当前用户信息", description="查询当前登录用户的基本信息")
async def get_user_info(
        request: Request,
        current_user: User = Depends(AuthControl.is_authed),
):
    """
    查询当前登录用户信息。

    :param request: 当前请求，用于复用请求级角色缓存
    :param current_user: 已认证用户
    :return: 统一响应，data 为用户信息，不含密码，并附加 is_admin
    """
    try:
        data = await current_user.to_dict(exclude_fields=["password"], replace_fields={"id": "user_id"})
        # 管理员角色与超管同权，前端据此放开行级删除等归属限制
        data["is_admin"], _ = await _load_admin_flag(request=request, user=current_user)
        return SuccessResponse(message="查询成功", data=data)
    except Exception:
        error_message: str = "暂时无法查询当前用户信息，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [user_id={current_user.id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@user_self.post("/menu/list", summary="查询当前用户菜单", description="查询当前登录用户的菜单信息")
async def get_user_menu(
        request: Request,
        current_user: User = Depends(AuthControl.is_authed),
        menu_crud: MenuCrud = Depends(get_menu_crud),
):
    """
    查询当前登录用户的菜单树。

    :param request: 当前请求，用于复用请求级角色缓存
    :param current_user: 已认证用户
    :param menu_crud: 菜单 CRUD 服务
    :return: 统一响应，data 为菜单树，节点主键字段为 menu_id
    """
    try:
        is_admin, roles = await _load_admin_flag(request=request, user=current_user)
        data = await menu_crud.get_user_menu_tree(
            is_admin=is_admin,
            role_ids=[role.id for role in roles]
        )
        return SuccessResponse(message="查询成功", data=data)
    except Exception:
        error_message: str = "暂时无法查询当前用户菜单数据，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [user_id={current_user.id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@user_self.post("/get_user_routers", summary="查询当前用户路由", description="查询当前登录用户的路由权限")
async def get_user_routers(
        request: Request,
        current_user: User = Depends(AuthControl.is_authed),
        router_crud: RouterCrud = Depends(get_router_crud),
):
    """
    查询当前登录用户的接口权限键。

    :param request: 当前请求，用于复用请求级角色缓存
    :param current_user: 已认证用户
    :param router_crud: 路由 CRUD 服务
    :return: 统一响应，data 为排序后的权限键列表，权限键为方法小写加路由路径
    """
    try:
        is_admin, roles = await _load_admin_flag(request=request, user=current_user)
        routers: List[str] = await router_crud.list_permission_keys(
            is_admin=is_admin,
            role_ids=[role.id for role in roles]
        )
        return SuccessResponse(message="查询成功", data=routers)
    except Exception:
        error_message: str = "暂时无法查询当前用户权限数据，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [user_id={current_user.id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)
