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
from backend.applications.base.models.base_model import Menu, Api
from backend.applications.user.models.role_model import Role
from backend.applications.user.models.user_model import User
from backend.core.exceptions.base_exceptions import NotFoundException
from backend.core.response.http_response import SuccessResponse, NotFoundResponse
from backend.services.ctx import CTX_USER_ID
from backend.services.dependency import DependAuth
from backend.services.password import create_access_token

auth = APIRouter()


@auth.post("/access_token", summary="用户鉴权")
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
        image=user.image,
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


@auth.post("/userapi", summary="查看用户API", dependencies=[DependAuth])
async def get_user_api():
    user_id = CTX_USER_ID.get()
    user_obj = await User.filter(id=user_id).first()
    if user_obj.is_superuser:
        api_objs: List[Api] = await Api.all()
        apis = [api.method.lower() + api.path for api in api_objs]
        return SuccessResponse(data=apis)
    role_objs: List[Role] = await user_obj.roles
    apis = []
    for role_obj in role_objs:
        api_objs: List[Api] = await role_obj.apis
        apis.extend([api.method.lower() + api.path for api in api_objs])
    apis = list(set(apis))
    return SuccessResponse(data=apis)
