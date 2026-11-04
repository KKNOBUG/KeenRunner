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
from typing import List, Optional

from fastapi import APIRouter, Body, Query, Depends, Request
from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from backend.applications.base.models.menu_model import Menu
from backend.applications.base.models.role_model import Role
from backend.applications.base.models.router_model import Router
from backend.applications.base.schemas.token_schema import CredentialsSchema, JWTOut, JWTPayload
from backend.applications.department.dependencies import get_dept_crud
from backend.applications.department.services.department_crud import DepartmentCrud
from backend.applications.user.dependencies import get_user_crud
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
from backend.services import CTX_USER_ID, AuthControl, create_access_token, verify_password
from backend.services.dependency import load_request_roles

# 公开端点：登录不要求令牌
user_public = APIRouter()

# 仅认证端点：当前登录用户自身操作，不做 RBAC 鉴权
user_self = APIRouter()

# 权限端点：用户管理类接口
user_secure = APIRouter()


@user_secure.post("/create", summary="新增用户", description="新增用户信息")
async def create_user(
        user_in: UserCreate = Body(..., description="用户信息"),
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    新增用户。

    :param user_in: 用户入参
    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
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
    except IntegrityError as e:
        LOGGER.error(f"新增失败, 用户已存在: {e}\n{traceback.format_exc()}")
        return DataAlreadyExistsResponse(message="新增失败, 用户已存在")
    except Exception as e:
        LOGGER.error(f"新增失败, 异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败, 异常描述: {e}")


@user_secure.delete("/delete", summary="删除用户", description="根据id删除用户信息")
async def delete_user(
        user_id: int = Query(..., description="用户ID"),
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    删除用户。

    :param user_id: 用户ID
    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
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
    except Exception as e:
        LOGGER.error(f"删除失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@user_secure.post("/deletes", summary="批量删除用户", description="根据id列表批量删除用户信息")
async def batch_delete_users(
        user_in: UserBatchDelete = Body(..., description="用户信息"),
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    根据id列表删除用户。

    :param user_in: 用户入参
    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
    """
    try:
        deleted_ids = await user_crud.delete_users(user_in=user_in)
        deleted_num = len(deleted_ids)
        return SuccessResponse(message="删除成功", data={"deleted": deleted_ids}, total=deleted_num)
    except Exception as e:
        LOGGER.error(f"删除失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@user_secure.post("/update", summary="更新用户", description="根据id更新用户信息")
async def update_user(
        user_in: UserUpdate = Body(..., description="用户信息"),
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    更新用户。

    :param user_in: 用户入参
    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
    """
    try:
        async with in_transaction():
            instance = await user_crud.update_user(user_in=user_in)
            if "role_ids" in user_in.model_fields_set:
                await user_crud.update_roles(instance, user_in.role_ids)
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
    except IntegrityError as e:
        # 并发改名落到唯一索引：按已存在返回，不能落成服务异常
        LOGGER.error(f"更新失败, 用户账号已存在: {e}\n{traceback.format_exc()}")
        return DataAlreadyExistsResponse(message="更新失败, 用户账号已存在")
    except Exception as e:
        LOGGER.error(f"更新失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {e}")


@user_secure.get("/get", summary="查询用户", description="根据id查询用户信息")
async def get_user(
        user_id: int = Query(..., description="用户ID"),
        user_crud: UserCrud = Depends(get_user_crud),
        dept_crud: DepartmentCrud = Depends(get_dept_crud),
):
    """
    查询用户信息。

    :param user_id: 用户ID
    :param user_crud: 用户CRUD服务
    :param dept_crud: 部门CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await user_crud.get_by_id(user_id=user_id, state__not=1)
        if not instance:
            return NotFoundResponse(message=f"用户(id={user_id})信息不存在")
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
            department_instance = await dept_crud.model.filter(id=dept_id).first()
            if department_instance:
                data["dept"] = await department_instance.to_dict(replace_fields={"id": "dept_id"})
        return SuccessResponse(message="查询成功", data=data, total=1)
    except Exception as e:
        LOGGER.error(f"查询失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@user_secure.get("/by_username", summary="查询用户(按用户名)", description="根据username查询用户信息")
async def get_user_by_username(
        username: str = Query(..., description="用户名称"),
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    查询用户信息。

    :param username: 用户账号
    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await user_crud.get_by_username(username=username)
        if not instance:
            return NotFoundResponse(message=f"用户[username={username}]信息不存在")
        data: dict = await instance.to_dict(exclude_fields=["password"], replace_fields={"id": "user_id"})
        return SuccessResponse(message="查询成功", data=data, total=1)
    except Exception as e:
        LOGGER.error(f"查询失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


async def _attach_departments(data: List[dict], dept_crud: DepartmentCrud) -> None:
    """
    批量为用户列表挂载部门信息。

    一次查询全部部门，避免逐条查库造成 N+1；脏 dept_id 降级为空对象，
    保证单条坏数据不会让整张用户表返回 999999。

    :param data: 用户列表字典（就地修改）
    :param dept_crud: 部门CRUD服务
    :return: None
    """
    dept_ids = {item.get("dept_id") for item in data if item.get("dept_id")}
    dept_map: dict = {}
    if dept_ids:
        for department in await dept_crud.model.filter(id__in=dept_ids):
            dept_map[department.id] = await department.to_dict(replace_fields={"id": "dept_id"})
    for item in data:
        item_dept_id = item.pop("dept_id", None)
        item["dept"] = dept_map.get(item_dept_id, {})


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
        user_crud: UserCrud = Depends(get_user_crud),
        dept_crud: DepartmentCrud = Depends(get_dept_crud),
):
    """
    查询用户列表。

    :param page: 页码
    :param page_size: 每页条数
    :param order: 排序字段
    :param username: 用户账号
    :param alias: 查询参数
    :param email: 查询参数
    :param phone: 查询参数
    :param gender: 查询参数
    :param user_type: 查询参数
    :param state: 状态(0:启用, 1:禁用)
    :param is_superuser: 查询参数
    :param dept_id: 主键 ID
    :param user_crud: 用户CRUD服务
    :param dept_crud: 部门CRUD服务
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if username:
            q &= Q(username__contains=username)
        if alias:
            q &= Q(alias__contains=alias)
        if email:
            q &= Q(email__contains=email)
        if phone:
            q &= Q(phone__contains=phone)
        if gender is not None:
            q &= Q(gender=gender)
        if user_type is not None:
            q &= Q(user_type=user_type)
        if state is not None:
            q &= Q(state=state)
        else:
            q &= Q(state=0)
        if is_superuser is not None:
            q &= Q(is_superuser=is_superuser)
        if dept_id is not None:
            q &= Q(dept_id=dept_id)

        total, user_objs = await user_crud.list(
            page=page,
            page_size=page_size,
            order=order,
            search=q
        )
        data = [
            await obj.to_dict(
                m2m=True,
                exclude_fields=["password"],
                replace_fields={"id": "user_id"},
                m2m_replace_fields={"roles": {"id": "role_id"}}
            ) for obj in user_objs
        ]
        await _attach_departments(data, dept_crud)
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception as e:
        LOGGER.error(f"查询失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@user_secure.post("/search", summary="查询用户列表(Body)", description="根据条件分页查询用户列表信息(Body)")
async def list_users(
        user_in: UserSelect = Body(..., description="查询条件"),
        user_crud: UserCrud = Depends(get_user_crud),
        dept_crud: DepartmentCrud = Depends(get_dept_crud),
):
    """
    查询用户列表。

    :param user_in: 用户入参
    :param user_crud: 用户CRUD服务
    :param dept_crud: 部门CRUD服务
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if user_in.username:
            q &= Q(username__contains=user_in.username)
        if user_in.alias:
            q &= Q(alias__contains=user_in.alias)
        if user_in.email:
            q &= Q(email__contains=user_in.email)
        if user_in.phone:
            q &= Q(phone__contains=user_in.phone)
        if user_in.motto:
            q &= Q(motto__contains=user_in.motto)
        if user_in.address:
            q &= Q(address__contains=user_in.address)
        if user_in.gender is not None:
            q &= Q(gender=user_in.gender)
        if user_in.user_type is not None:
            q &= Q(user_type=user_in.user_type)
        if user_in.emergency_name:
            q &= Q(emergency_name__contains=user_in.emergency_name)
        if user_in.emergency_phone:
            q &= Q(emergency_phone__contains=user_in.emergency_phone)
        if user_in.is_superuser is not None:
            q &= Q(is_superuser=user_in.is_superuser)
        if user_in.dept_id is not None:
            q &= Q(dept_id=user_in.dept_id)
        if user_in.state is not None:
            q &= Q(state=user_in.state)
        else:
            q &= Q(state=0)

        total, instances = await user_crud.list(
            page=user_in.page,
            page_size=user_in.page_size,
            search=q,
            order=user_in.order
        )
        data = [
            await obj.to_dict(
                m2m=True,
                exclude_fields=["password"],
                replace_fields={"id": "user_id"},
                m2m_replace_fields={"roles": {"id": "role_id"}}
            ) for obj in instances
        ]
        await _attach_departments(data, dept_crud)
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception as e:
        LOGGER.error(f"查询失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@user_self.post("/update_password", summary="更新用户密码(个人)", description="根据当前登录用户ID修改密码")
async def update_user_password(
        req_in: UpdatePassword,
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    修改密码。

    :param req_in: 修改密码入参
    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
    """
    try:
        user_id = CTX_USER_ID.get()
        instance = await user_crud.get_or_error(user_id)
        verified = verify_password(req_in.old_password, instance.password)
        if not verified:
            return FailureResponse(message="旧密码验证错误")

        instance = await user_crud.update_password(user_id=user_id, new_password=req_in.new_password)
        data = await instance.to_dict(
            exclude_fields=["password"],
            replace_fields={"id": "user_id"}
        )
        return SuccessResponse(message="更新成功", data=data, total=1)
    except Exception as e:
        LOGGER.error(f"更新失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {e}")


@user_secure.post("/reset_password", summary="更新用户密码(重置)", description="根据id重置用户密码")
async def reset_password(
        user_id: int = Body(..., description="用户ID", embed=True),
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    重置密码。

    :param user_id: 用户ID
    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
    """
    try:
        data = await user_crud.reset_password(user_id)
        return SuccessResponse(message="重置成功", data=data, total=1)
    except NoPermissionException:
        raise
    except Exception as e:
        LOGGER.error(f"重置失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"重置失败，异常描述: {e}")


# ==================== 公开端点：幂等登出（由中间件执行可选认证） ====================
@user_public.post("/logout", summary="注销访问令牌", description="注销当前登录用户的所有会话信息")
async def logout(
        request: Request,
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    用户登出；有效Token吊销全部会话，失效或无Token仅返回幂等成功，不修改用户数据。

    :param request: 当前请求，可选认证成功后由中间件写入current_user
    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
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
        return SuccessResponse(message="登出成功", data=data, total=1)
    except Exception as e:
        LOGGER.error(f"登出失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"登出失败，异常描述: {e}")


# ==================== 公开端点：登录 ====================
@user_public.post("/login", summary="用户登录", description="验证用户密码和状态并签发访问令牌")
async def login(
        credentials: CredentialsSchema = Body(..., description="用户信息"),
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    验证用户密码和状态并生成令牌。

    :param credentials: 登录凭证入参
    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
    """
    try:
        try:
            user: User = await user_crud.authenticate(credentials)
        except (NotFoundException, NoAuthenticateException):
            # 账号不存在与密码错误统一返回401，避免账号枚举；失败响应不回显密码
            return UnauthorizedResponse(message="用户名或密码错误")
        except NoPermissionException as e:
            return ForbiddenResponse(message=str(e.message))
        try:
            await user_crud.update_last_login(user_id=user.id)
        except (ParameterException, NotFoundException):
            return FailureResponse(message="登录失败，请稍后重试")

        access_token_expires = timedelta(minutes=PROJECT_CONFIG.AUTH_JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        expire_time = datetime.now(timezone.utc) + access_token_expires
        last_login_time = user.last_login.strftime(GLOBAL_CONFIG.DATETIME_FORMAT2) if user.last_login else None
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
            last_login=last_login_time,
            exp=expire_time.astimezone().strftime(GLOBAL_CONFIG.DATETIME_FORMAT2),
        )
        return SuccessResponse(message="登录成功", data=data.model_dump())
    except Exception as e:
        LOGGER.error(f"登录失败，请稍后重试: {e}\n{traceback.format_exc()}")
        return FailureResponse(message="登录失败，请稍后重试")


@user_public.post("/transfer_login", summary="第三方迁移登录", description="账号不存在时按第三方平台校验并接纳为新用户后生成令牌")
async def transfer_login(
        credentials: CredentialsSchema = Body(..., description="用户信息"),
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    第三方平台用户迁移登录：本地账号不存在时按第三方平台校验并接纳为新用户后生成令牌。

    与 /user/login 的差异仅在于账号不存在分支：校验第三方账号真实性并自动注册，
    其余口令/状态校验与令牌签发逻辑与原接口一致。

    :param credentials: 登录凭证入参
    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
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

        access_token_expires = timedelta(minutes=PROJECT_CONFIG.AUTH_JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        expire_time = datetime.now(timezone.utc) + access_token_expires
        last_login_time = user.last_login.strftime(GLOBAL_CONFIG.DATETIME_FORMAT2) if user.last_login else None
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
            last_login=last_login_time,
            exp=expire_time.astimezone().strftime(GLOBAL_CONFIG.DATETIME_FORMAT2),
        )
        return SuccessResponse(message="登录成功", data=data.model_dump())
    except Exception as e:
        LOGGER.error(f"登录失败，请稍后重试: {e}\n{traceback.format_exc()}")
        return FailureResponse(message="登录失败，请稍后重试")


# ==================== 仅认证端点：当前用户自身 ====================
@user_self.post("/get_userinfo", summary="查询当前用户信息", description="查询当前登录用户的基本信息")
async def get_user_info(
        request: Request,
        current_user: User = Depends(AuthControl.is_authed),
):
    """
    查看当前用户信息。

    :param request: 当前请求，用于复用请求级角色缓存
    :param current_user: 已认证用户，认证链路已查库并缓存，避免重复查询
    :return: 统一HTTP响应
    """
    try:
        data = await current_user.to_dict(exclude_fields=["password"], replace_fields={"id": "user_id"})
        # 管理员角色与超管同权，前端据此放开行级删除等归属限制；超管无需再查角色
        roles: List[Role] = [] if current_user.is_superuser else await load_request_roles(
            request=request, user=current_user
        )
        data["is_admin"] = current_user.is_superuser or BuiltinRoleCode.includes_admin(
            role.code for role in roles
        )
        return SuccessResponse(message="查询成功", data=data)
    except Exception as e:
        LOGGER.error(f"查询失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@user_self.post("/menu/list", summary="查询当前用户菜单", description="查询当前登录用户的菜单信息")
async def get_user_menu():
    """
    查看当前用户菜单。

    :return: 统一HTTP响应
    """
    try:
        user_id = CTX_USER_ID.get()
        user_obj = await User.filter(id=user_id).first()
        role_objs: List[Role] = await user_obj.roles
        # 超管与管理员角色直接拿到全量菜单，不依赖角色菜单绑定
        if user_obj.is_superuser or BuiltinRoleCode.includes_admin(role.code for role in role_objs):
            menus: List[Menu] = await Menu.all().order_by("order", "id")
        elif role_objs:
            # 多角色菜单一次查出并去重，避免按角色逐条查询造成 N+1；下发顺序由 order 决定
            menus = await Menu.filter(
                role_menus__id__in=[role.id for role in role_objs]
            ).distinct().order_by("order", "id")
        else:
            menus = []
        parent_menus: List[Menu] = []
        for menu in menus:
            if menu.parent_id == 0:
                parent_menus.append(menu)
        res = []
        for parent_menu in parent_menus:
            parent_menu_dict = await parent_menu.to_dict(replace_fields={"id": "menu_id"})
            parent_menu_dict["children"] = []
            for menu in menus:
                if menu.parent_id == parent_menu.id:
                    parent_menu_dict["children"].append(await menu.to_dict(replace_fields={"id": "menu_id"}))
            res.append(parent_menu_dict)
        return SuccessResponse(message="查询成功", data=res)
    except Exception as e:
        LOGGER.error(f"查询失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@user_self.post("/get_user_routers", summary="查询当前用户路由", description="查询当前登录用户的路由权限")
async def get_user_routers():
    """
    查看当前用户路由权限键。

    :return: 统一HTTP响应
    """
    try:
        user_id = CTX_USER_ID.get()
        user_obj = await User.filter(id=user_id).first()
        role_objs: List[Role] = await user_obj.roles
        # 超管与管理员角色直接拿到全量接口，不依赖角色路由绑定
        if user_obj.is_superuser or BuiltinRoleCode.includes_admin(role.code for role in role_objs):
            router_objs: List[Router] = await Router.all()
        elif role_objs:
            # 多角色接口一次查出并去重，避免按角色逐条查询造成 N+1
            router_objs = await Router.filter(role_routers__id__in=[role.id for role in role_objs]).distinct()
        else:
            router_objs = []
        routers = sorted({router.method.lower() + router.path for router in router_objs})
        return SuccessResponse(message="查询成功", data=routers)
    except Exception as e:
        LOGGER.error(f"查询失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")
