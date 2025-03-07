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

from fastapi import APIRouter

from backend import PROJECT_CONFIG
from backend.applications.base.schemas.token_schema import CredentialsSchema, JWTOut, JWTPayload
from backend.applications.user.services.user_crud import USER_CRUD
from backend.applications.base.models.router_model import Router
from backend.applications.base.models.menu_model import Menu
from backend.applications.base.models.role_model import Role
from backend.applications.user.models.user_model import User
from backend.core.exceptions.base_exceptions import NotFoundException
from backend.core.response.http_response import SuccessResponse, NotFoundResponse
from backend.services.ctx import CTX_USER_ID
from backend.services.dependency import DependAuth
from backend.services.password import create_access_token

auth = APIRouter()


@auth.post("/access_token", summary="用户鉴权", description="验证用户密码和状态并生成令牌")
async def get_login_access_token(credentials: CredentialsSchema):
    try:
        user: User = await USER_CRUD.authenticate(credentials)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e), data=credentials.dict())

    await USER_CRUD.update_last_login(user.id)
    access_token_expires = timedelta(minutes=PROJECT_CONFIG.AUTH_JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + access_token_expires

    data = JWTOut(
        access_token=create_access_token(
            data=JWTPayload(
                user_id=user.id,
                username=user.username,
                state=user.state,
                is_superuser=user.is_superuser,
                exp=expire,
            )
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


@auth.post("/usermenu", summary="查看用户菜单", dependencies=[DependAuth])
async def get_user_menu():
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


@auth.post("/userinfo", summary="查看用户信息", dependencies=[DependAuth])
async def get_userinfo():
    user_id = CTX_USER_ID.get()
    user_obj = await USER_CRUD.get(id=user_id)
    data = await user_obj.to_dict(exclude_fields=["password"])
    # 头像地址
    # data["avatar"] = f'http://172.20.10.2:8518/static/avatar/admin/20250220204648.png'
    return SuccessResponse(data=data)


@auth.post("/userRouter", summary="查看用户路由", dependencies=[DependAuth])
async def get_user_router():
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
