# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : auth_view.py
@DateTime: 2025/1/18 10:03
"""
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
from backend.configure import PROJECT_CONFIG
from backend.core.exceptions import NotFoundException, NoPermissionException, ParameterException
from backend.core.responses import SuccessResponse, NotFoundResponse
from backend.services import CTX_USER_ID
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
        user: User = await user_crud.authenticate(credentials)
    except (NotFoundException, NoPermissionException) as e:
        return NotFoundResponse(message=str(e.message), data=credentials.model_dump())

    try:
        await user_crud.update_last_login(user_id=user.id)
    except (ParameterException, NotFoundException) as e:
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
    return SuccessResponse(data=data.model_dump())


@auth_secure.post("/usermenu", summary="查看当前用户菜单")
async def get_user_menu():
    """
    查看当前用户菜单。

    :return: 统一HTTP响应
    """
    user_id = CTX_USER_ID.get()
    user_obj = await User.filter(id=user_id).first()
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
    return SuccessResponse(data=res)


@auth_secure.post("/userinfo", summary="查看当前用户信息")
async def get_userinfo(
        user_crud: UserCrud = Depends(get_user_crud),
):
    """
    查看当前用户信息。

    :param user_crud: 用户CRUD服务
    :return: 统一HTTP响应
    """
    user_id = CTX_USER_ID.get()
    user_obj = await user_crud.get_by_id(user_id=user_id, on_error=True)
    data = await user_obj.to_dict(exclude_fields=["password"])
    return SuccessResponse(data=data)


@auth_secure.post("/getUserRouters", summary="查看当前用户路由")
async def get_user_router():
    """
    查看当前用户路由。

    :return: 统一HTTP响应
    """
    user_id = CTX_USER_ID.get()
    user_obj = await User.filter(id=user_id).first()
    if user_obj.is_superuser:
        router_objs: List[Router] = await Router.all()
        routers = [router.method.lower() + router.path for router in router_objs]
        return SuccessResponse(data=routers)
    role_objs: List[Role] = await user_obj.roles
    routers = []
    for role_obj in role_objs:
        router_objs: List[Router] = await role_obj.routers
        routers.extend([router.method.lower() + router.path for router in router_objs])
    routers = list(set(routers))
    return SuccessResponse(data=routers)
