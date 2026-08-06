# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
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
from backend.services import CTX_USER_ID
from backend.services import create_access_token

auth_public = APIRouter()
auth_secure = APIRouter()

@auth_public.post("/access_token", summary="生成访问令牌", description="验证用户密码和状态并生成令牌")
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
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            last_login=user.last_login
        )
        LOGGER.info(f"用户登录成功, username: {user.username}")
        return SuccessResponse(message="登录成功", data=data.model_dump())
    except Exception as e:
        LOGGER.error(f"用户登录失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"登录失败，异常描述: {e}")

@auth_secure.post("/usermenu", summary="查看当前用户菜单")
async def get_user_menu():
    """
    查看当前用户菜单。

    :return: 统一HTTP响应
    """
    try:
        user_id = CTX_USER_ID.get()
        user_obj = await User.filter(id=user_id).first()
        if not user_obj:
            return NotFoundResponse(message=f"查询用户菜单失败, 记录[id={user_id}]不存在")
        menus: List[Menu] = []
        if user_obj.is_superuser:
            menus = await Menu.all()
        else:
            role_objs: List[Role] = await user_obj.roles
            for role_obj in role_objs:
                menu = await role_obj.menus
                menus.extend(menu)
            menus = list(set(menus))
        parent_menus: List[Menu] = []
        for menu in menus:
            if menu.parent_id == 0:
                parent_menus.append(menu)
        res = []
        for parent_menu in parent_menus:
            parent_menu_dict = await parent_menu.to_dict()
            parent_menu_dict["children"] = []
            for menu in menus:
                if menu.parent_id == parent_menu.id:
                    parent_menu_dict["children"].append(await menu.to_dict())
            res.append(parent_menu_dict)
        LOGGER.info(f"查询当前用户菜单成功, user_id: {user_id}, 数量: {len(res)}")
        return SuccessResponse(message="查询成功", data=res)
    except Exception as e:
        LOGGER.error(f"查询当前用户菜单失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")

@auth_secure.post("/userinfo", summary="查看当前用户信息")
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
        data = await user_obj.to_dict(exclude_fields=["password"])
        LOGGER.info(f"查询当前用户信息成功, user_id: {user_id}")
        return SuccessResponse(message="查询成功", data=data)
    except Exception as e:
        LOGGER.error(f"查询当前用户信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")

@auth_secure.post("/getUserRouters", summary="查看当前用户路由")
async def get_user_routers():
    """
    查看当前用户路由。

    :return: 统一HTTP响应
    """
    try:
        user_id = CTX_USER_ID.get()
        user_obj = await User.filter(id=user_id).first()
        if not user_obj:
            return NotFoundResponse(message=f"查询用户路由失败, 记录[id={user_id}]不存在")
        if user_obj.is_superuser:
            router_objs: List[Router] = await Router.all()
            routers = [router.method.lower() + router.path for router in router_objs]
            LOGGER.info(f"查询当前用户路由成功, user_id: {user_id}, 数量: {len(routers)}")
            return SuccessResponse(message="查询成功", data=routers)
        role_objs: List[Role] = await user_obj.roles
        routers = []
        for role_obj in role_objs:
            router_objs: List[Router] = await role_obj.routers
            routers.extend([router.method.lower() + router.path for router in router_objs])
        routers = list(set(routers))
        LOGGER.info(f"查询当前用户路由成功, user_id: {user_id}, 数量: {len(routers)}")
        return SuccessResponse(message="查询成功", data=routers)
    except Exception as e:
        LOGGER.error(f"查询当前用户路由失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")
