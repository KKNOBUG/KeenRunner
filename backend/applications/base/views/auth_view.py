# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : auth_view.py
@DateTime: 2025/1/18 10:03
"""
import traceback
from datetime import timedelta, datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, Body

from backend.applications.base.models.menu_model import Menu
from backend.applications.base.models.role_model import Role
from backend.applications.base.models.router_model import Router
from backend.applications.base.schemas.token_schema import CredentialsSchema, JWTOut, JWTPayload
from backend.applications.user.dependencies import get_user_crud
from backend.applications.user.models.user_model import User
from backend.applications.user.services.user_crud import UserCrud
from backend.configure import LOGGER, PROJECT_CONFIG
from backend.core.exceptions import NotFoundException, NoPermissionException, ParameterException
from backend.core.responses import (
    SuccessResponse,
    NotFoundResponse,
    FailureResponse,
    ParameterResponse,
    ForbiddenResponse
)
from backend.enums import BuiltinRoleCode
from backend.services import CTX_USER_ID, DataScope
from backend.services import create_access_token

auth_public = APIRouter()
auth_secure = APIRouter()


@auth_public.post("/access_token", summary="生成访问令牌", description="验证用户密码和状态并生成令牌")
async def get_login_access_token(
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
        except NotFoundException as e:
            return NotFoundResponse(message=str(e.message), data=credentials.model_dump())
        except NoPermissionException as e:
            return ForbiddenResponse(message=str(e.message), data=credentials.model_dump())
        try:
            await user_crud.update_last_login(user_id=user.id)
        except ParameterException as e:
            return ParameterResponse(message=str(e.message), data=credentials.model_dump())
        except NotFoundException as e:
            return NotFoundResponse(message=str(e.message), data=credentials.model_dump())

        access_token_expires = timedelta(minutes=PROJECT_CONFIG.AUTH_JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        expire = datetime.now(timezone.utc) + access_token_expires

        data = JWTOut(
            access_token=create_access_token(
                data=JWTPayload(
                    user_id=user.id,
                    username=user.username,
                    state=user.state,
                    is_superuser=user.is_superuser,
                    token_version=user.token_version,
                    exp=expire,
                ),
                token_version=user.token_version,
            ),
            username=user.username,
            alias=user.alias,
            email=user.email,
            phone=user.phone,
            avatar=user.avatar,
            state=user.state,
            is_superuser=user.is_superuser,
            last_login=user.last_login
        )
        return SuccessResponse(message="登录成功", data=data.model_dump())
    except Exception as e:
        LOGGER.error(f"登录失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"登录失败，异常描述: {e}")


@auth_secure.post("/usermenu", summary="查询当前用户菜单", description="查询当前登录用户的菜单信息")
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
            menus: List[Menu] = await Menu.all()
        elif role_objs:
            # 多角色菜单一次查出并去重，避免按角色逐条查询造成 N+1
            menus = await Menu.filter(role_menus__id__in=[role.id for role in role_objs]).distinct()
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


@auth_secure.post("/userinfo", summary="查询当前用户信息", description="查询当前登录用户的基本信息")
async def get_user_info(
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    查看当前用户信息。

    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
    """
    try:
        user_id = CTX_USER_ID.get()
        user_obj = await user_crud.get_by_id(user_id=user_id, on_error=True)
        data = await user_obj.to_dict(exclude_fields=["password"], replace_fields={"id": "user_id"})
        select_scope, update_scope, _ = await DataScope.effective_scopes(user_obj)
        data["select_scope"] = select_scope.value
        data["update_scope"] = update_scope.value
        # 管理员角色与超管同权，前端据此放开行级删除等归属限制
        data["is_admin"] = user_obj.is_superuser or BuiltinRoleCode.includes_admin(
            role.code for role in await user_obj.roles
        )
        return SuccessResponse(message="查询成功", data=data)
    except Exception as e:
        LOGGER.error(f"查询失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@auth_secure.post("/get_user_routers", summary="查询当前用户路由", description="查询当前登录用户的路由权限")
async def get_user_router():
    """
    查看当前用户路由。

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
