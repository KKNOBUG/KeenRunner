# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : data_initialization.py
@DateTime: 2025/2/19 22:12
"""
import os

from fastapi import FastAPI
from tortoise.expressions import Q

from backend.applications.base.models.api_model import Api
from backend.applications.base.models.menu_model import Menu
from backend.applications.base.schemas.menu_schema import MenuType
from backend.applications.base.services.api_crud import API_CRUD
from backend.applications.base.models.role_model import Role
from backend.applications.user.schemas.user_schema import UserCreate
from backend.applications.user.services.user_crud import USER_CRUD


async def init_database_api(app: FastAPI):
    apis = await API_CRUD.model.exists()
    if not apis:
        await API_CRUD.refresh_api(app)


async def init_database_role():
    roles = await Role.exists()
    if not roles:
        admin_role = await Role.create(
            code="AD-9001",
            name="管理员",
            description="管理员角色",
        )
        normal_role = await Role.create(
            code="AD-1001",
            name="普通用户",
            description="普通用户角色",
        )

        # 分配所有API给管理员角色
        all_apis = await Api.all()
        await admin_role.apis.add(*all_apis)

        # 分配所有菜单给管理员和普通用户
        all_menus = await Menu.all()
        await admin_role.menus.add(*all_menus)
        await normal_role.menus.add(*all_menus)

        # 为普通用户分配基本API
        basic_apis = await Api.filter(Q(method__in=["GET"]) | Q(tags="基础模块"))
        await normal_role.apis.add(*basic_apis)


async def init_database_user():
    user = await USER_CRUD.model.exists()
    if not user:
        await USER_CRUD.create_user(
            UserCreate(
                username="admin",
                password="123456",
                alias="管理员",
                email="admin@test.com",
                phone="18888888888",
                avatar="/static/avatar/20250220204648.png",
                state=2,
                is_active=True,
                is_superuser=True,
            )
        )


async def init_database_menu():
    menus = await Menu.exists()
    if not menus:
        parent_menu = await Menu.create(
            menu_type=MenuType.CATALOG,
            name="系统管理",
            path="/system",
            order=1,
            parent_id=0,
            icon="carbon:gui-management",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/system/user",
        )
        children_menu = [
            Menu(
                menu_type=MenuType.MENU,
                name="用户管理",
                path="user",
                order=1,
                parent_id=parent_menu.id,
                icon="material-symbols:person-outline-rounded",
                is_hidden=False,
                component="/system/user",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="角色管理",
                path="role",
                order=2,
                parent_id=parent_menu.id,
                icon="carbon:user-role",
                is_hidden=False,
                component="/system/role",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="菜单管理",
                path="menu",
                order=3,
                parent_id=parent_menu.id,
                icon="material-symbols:list-alt-outline",
                is_hidden=False,
                component="/system/menu",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="API管理",
                path="api",
                order=4,
                parent_id=parent_menu.id,
                icon="ant-design:api-outlined",
                is_hidden=False,
                component="/system/api",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="部门管理",
                path="dept",
                order=5,
                parent_id=parent_menu.id,
                icon="mingcute:department-line",
                is_hidden=False,
                component="/system/dept",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="审计日志",
                path="auditlog",
                order=6,
                parent_id=parent_menu.id,
                icon="ph:clipboard-text-bold",
                is_hidden=False,
                component="/system/auditlog",
                keepalive=False,
            ),
        ]
        await Menu.bulk_create(children_menu)
        await Menu.create(
            menu_type=MenuType.MENU,
            name="一级菜单",
            path="/top-menu",
            order=2,
            parent_id=0,
            icon="material-symbols:featured-play-list-outline",
            is_hidden=False,
            component="/top-menu",
            keepalive=False,
            redirect="",
        )


async def init_database_table(app: FastAPI):
    await init_database_user()
    await init_database_menu()
    await init_database_api(app)
    await init_database_role()
