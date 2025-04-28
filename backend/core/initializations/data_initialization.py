# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : data_initialization.py
@DateTime: 2025/2/19 22:12
"""
from fastapi import FastAPI
from tortoise.expressions import Q

from backend.applications.base.models.router_model import Router
from backend.applications.base.models.menu_model import Menu
from backend.applications.base.schemas.menu_schema import MenuCreate
from backend.applications.base.services.menu_crud import MENU_CRUD
from backend.applications.base.models.role_model import Role
from backend.applications.base.schemas.role_schema import RoleCreate
from backend.applications.base.services.role_crud import ROLE_CRUD
from backend.applications.base.services.router_crud import ROUTER_CRUD
from backend.applications.department.schemas.department_schema import DepartmentCreate
from backend.applications.department.services.department_crud import DEPT_CRUD
from backend.applications.user.schemas.user_schema import UserCreate
from backend.applications.user.services.user_crud import USER_CRUD
from backend.enums.menu_enum import MenuType


async def init_database_router(app: FastAPI):
    routers = await ROUTER_CRUD.model.exists()
    if not routers:
        await ROUTER_CRUD.refresh_router(app)


async def init_database_role():
    roles = await Role.exists()
    if not roles:
        admin_role = await ROLE_CRUD.create_role(
            RoleCreate(
                code="ROLE-9999",
                name="超级用户",
                description="超级用户角色"
            )
        )
        normal_role = await ROLE_CRUD.create_role(
            RoleCreate(
                code="ROLE-1001",
                name="普通用户",
                description="普通用户角色"
            )
        )

        # 为超级用户角色分配所有的路由
        all_routers = await Router.all()
        await admin_role.routers.add(*all_routers)

        # 为超级用户角色和普通用户角色分配所有的菜单
        all_menus = await Menu.all()
        await admin_role.menus.add(*all_menus)
        await normal_role.menus.add(*all_menus)

        # 为普通用户分配基本路由
        basic_routers = await Router.filter(Q(method__in=["GET"]) | Q(tags="基础模块"))
        await normal_role.routers.add(*basic_routers)


async def init_database_dept():
    depts = await DEPT_CRUD.model.exists()
    if not depts:
        await DEPT_CRUD.create_department(
            DepartmentCreate(
                code="DEPT-9999",
                name="默认部门",
                description="系统默认配置，无具体部门",
                order="0",
                parent_id="0"
            )
        )
        await DEPT_CRUD.create_department(
            DepartmentCreate(
                code="DEPT-KF",
                name="开发部门",
                description="软件开发部门",
                order="0",
                parent_id="0"
            )
        )
        await DEPT_CRUD.create_department(
            DepartmentCreate(
                code="DEPT-KF01",
                name="开发一部",
                description="软件开发部门，开发一部",
                order="1",
                parent_id="2"
            )
        )
        await DEPT_CRUD.create_department(
            DepartmentCreate(
                code="DEPT-KF02",
                name="开发二部",
                description="软件开发部门，开发二部",
                order="1",
                parent_id="2"
            )
        )
        await DEPT_CRUD.create_department(
            DepartmentCreate(
                code="DEPT-CS",
                name="测试部门",
                description="软件测试部门",
                order="0",
                parent_id="0"
            )
        )
        await DEPT_CRUD.create_department(
            DepartmentCreate(
                code="DEPT-CS01",
                name="测试一部",
                description="软件测试部门，测试一部",
                order="1",
                parent_id="5"
            )
        )
        await DEPT_CRUD.create_department(
            DepartmentCreate(
                code="DEPT-CS02",
                name="测试二部",
                description="软件测试部门，测试二部",
                order="1",
                parent_id="5"
            )
        )


async def init_database_user():
    user = await USER_CRUD.model.exists()
    if not user:
        await USER_CRUD.create_user(
            UserCreate(
                username="admin",
                password="123456",
                alias="系统管理员",
                email="admin@test.com",
                phone="18888888888",
                avatar="/static/avatar/default/20250101010101.png",
                dept_id="1",
                state=2,
                is_active=True,
                is_superuser=True,
                role_ids=["1", ]
            )
        )
        await USER_CRUD.create_user(
            UserCreate(
                username="CS1001",
                password="123456",
                alias="段誉",
                email="duanyu@test.com",
                phone="18888888888",
                avatar="/static/avatar/default/20250101010101.png",
                dept_id="6",
                state=2,
                is_active=True,
                is_superuser=False,
                role_ids=["2", ]
            )
        )
        await USER_CRUD.create_user(
            UserCreate(
                username="CS1002",
                password="123456",
                alias="虚竹",
                email="xuzhu@test.com",
                phone="18888888888",
                avatar="/static/avatar/default/20250101010101.png",
                dept_id="7",
                state=2,
                is_active=True,
                is_superuser=False,
                role_ids=["2", ]
            )
        )
        await USER_CRUD.create_user(
            UserCreate(
                username="CS1003",
                password="123456",
                alias="郭靖",
                email="guojing@test.com",
                phone="18888888888",
                avatar="/static/avatar/default/20250101010101.png",
                dept_id="7",
                state=2,
                is_active=True,
                is_superuser=False,
                role_ids=["2", ]
            )
        )
        await USER_CRUD.create_user(
            UserCreate(
                username="KF1001",
                password="123456",
                alias="小龙女",
                email="xiaolongnv@dev.com",
                phone="18888888888",
                avatar="/static/avatar/default/20250101010101.png",
                dept_id="3",
                state=2,
                is_active=True,
                is_superuser=False,
                role_ids=["2", ]
            )
        )
        await USER_CRUD.create_user(
            UserCreate(
                username="KF1002",
                password="123456",
                alias="杨过",
                email="yangguo@dev.com",
                phone="18888888888",
                avatar="/static/avatar/default/20250101010101.png",
                dept_id="3",
                state=2,
                is_active=True,
                is_superuser=False,
                role_ids=["2", ]
            )
        )
        await USER_CRUD.create_user(
            UserCreate(
                username="KF1003",
                password="123456",
                alias="黄蓉",
                email="huangrong@dev.com",
                phone="18888888888",
                avatar="/static/avatar/default/20250101010101.png",
                dept_id="4",
                state=2,
                is_active=True,
                is_superuser=False,
                role_ids=["2", ]
            )
        )


async def init_database_menu():
    menus = await Menu.exists()
    if not menus:
        # 系统设置菜单配置
        system_parent_menu = await MENU_CRUD.create_menu(
            MenuCreate(
                menu_type=MenuType.CATALOG,
                name="系统管理",
                path="/system",
                order=1,
                parent_id=0,
                icon="garden:gear-stroke-12",
                is_hidden=False,
                component="Layout",
                keepalive=False,
                redirect="/system/user"
            )
        )
        system_children_menu = [
            Menu(
                menu_type=MenuType.MENU,
                name="用户管理",
                path="user",
                order=1,
                parent_id=system_parent_menu.id,
                icon="tdesign:user-setting",
                is_hidden=False,
                component="/system/user",
                keepalive=False
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="角色管理",
                path="role",
                order=2,
                parent_id=system_parent_menu.id,
                icon="tdesign:user-transmit",
                is_hidden=False,
                component="/system/role",
                keepalive=False
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="菜单管理",
                path="menu",
                order=3,
                parent_id=system_parent_menu.id,
                icon="fluent:text-grammar-settings-24-filled",
                is_hidden=False,
                component="/system/menu",
                keepalive=False
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="路由管理",
                path="router",
                order=4,
                parent_id=system_parent_menu.id,
                icon="carbon:data-vis-1",
                is_hidden=False,
                component="/system/router",
                keepalive=False
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="部门管理",
                path="dept",
                order=5,
                parent_id=system_parent_menu.id,
                icon="mingcute:department-line",
                is_hidden=False,
                component="/system/dept",
                keepalive=False
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="缓存数据库管理",
                path="redis",
                order=6,
                parent_id=system_parent_menu.id,
                icon="devicon:redis-wordmark",
                is_hidden=False,
                component="/system/redis",
                keepalive=False
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="外部数据库管理",
                path="database",
                order=7,
                parent_id=system_parent_menu.id,
                icon="streamline:database-setting",
                is_hidden=False,
                component="/system/database",
                keepalive=False
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="审计日志",
                path="auditlog",
                order=8,
                parent_id=system_parent_menu.id,
                icon="ph:clipboard-text-bold",
                is_hidden=False,
                component="/system/auditlog",
                keepalive=False
            ),
        ]
        await Menu.bulk_create(system_children_menu)

        # 项目&模块设置菜单配置
        program_parent_menu = await MENU_CRUD.create_menu(
            MenuCreate(
                menu_type=MenuType.CATALOG,
                name="应用管理",
                path="/program",
                order=2,
                parent_id=0,
                icon="fluent:app-folder-28-filled",
                is_hidden=False,
                component="Layout",
                keepalive=False,
                redirect="/program/project"
            )
        )
        program_children_menu = [
            Menu(
                menu_type=MenuType.MENU,
                name="项目管理",
                path="project",
                order=1,
                parent_id=program_parent_menu.id,
                icon="fluent:apps-28-filled",
                is_hidden=False,
                component="/program/project",
                keepalive=False
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="模块管理",
                path="module",
                order=2,
                parent_id=program_parent_menu.id,
                icon="fluent:apps-add-in-28-regular",
                is_hidden=False,
                component="/program/module",
                keepalive=False
            ),
        ]
        await Menu.bulk_create(program_children_menu)

        # 自动化测试菜单配置
        autotest_parent_menu = await MENU_CRUD.create_menu(
            MenuCreate(
                menu_type=MenuType.CATALOG,
                name="自动化测试",
                path="/autotest",
                order=3,
                parent_id=0,
                icon="garden:bot-sparkle-stroke-12",
                is_hidden=False,
                component="Layout",
                keepalive=False,
                redirect="/autotest/testcase"
            )
        )
        autotest_children_menu = [
            Menu(
                menu_type=MenuType.MENU,
                name="Api 测试",
                path="api",
                order=1,
                parent_id=autotest_parent_menu.id,
                icon="simple-icons:aiohttp",
                is_hidden=False,
                component="/autotest/api",
                keepalive=False
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="Web 测试",
                path="ui",
                order=2,
                parent_id=autotest_parent_menu.id,
                icon="mdi:television-guide",
                is_hidden=False,
                component="/autotest/ui",
                keepalive=False
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="App 测试",
                path="ui",
                order=3,
                parent_id=autotest_parent_menu.id,
                icon="garden:mobile-phone-fill-12",
                is_hidden=False,
                component="/autotest/ui",
                keepalive=False
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="测试场景",
                path="step",
                order=4,
                parent_id=autotest_parent_menu.id,
                icon="garden:arrow-retweet-stroke-12",
                is_hidden=False,
                component="/autotest/step",
                keepalive=False
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="测试用例",
                path="testcase",
                order=5,
                parent_id=autotest_parent_menu.id,
                icon="garden:file-document-stroke-12",
                is_hidden=False,
                component="/autotest/testcase",
                keepalive=False
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="测试报告",
                path="report",
                order=6,
                parent_id=autotest_parent_menu.id,
                icon="garden:document-search-stroke-12",
                is_hidden=False,
                component="/autotest/report",
                keepalive=False
            ),
        ]
        await Menu.bulk_create(autotest_children_menu)

        # 任务管理菜单配置
        task_parent_menu = await MENU_CRUD.create_menu(
            MenuCreate(
                menu_type=MenuType.CATALOG,
                name="任务管理",
                path="/task",
                order=4,
                parent_id=0,
                icon="fluent:clock-alarm-24-regular",
                is_hidden=False,
                component="Layout",
                keepalive=False,
                redirect="/task/record"
            )
        )
        task_children_menu = [
            Menu(
                menu_type=MenuType.MENU,
                name="执行记录",
                path="record",
                order=1,
                parent_id=task_parent_menu.id,
                icon="fluent:document-checkmark-24-regular",
                is_hidden=False,
                component="/task/record",
                keepalive=False
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="任务列表",
                path="list",
                order=2,
                parent_id=task_parent_menu.id,
                icon="fluent:document-text-clock-24-regular",
                is_hidden=False,
                component="/task/list",
                keepalive=False
            ),
        ]
        await Menu.bulk_create(task_children_menu)

        # 便捷工具菜单配置
        toolbox_parent_menu = await MENU_CRUD.create_menu(
            MenuCreate(
                menu_type=MenuType.CATALOG,
                name="便捷工具",
                path="/toolbox",
                order=5,
                parent_id=0,
                icon="tdesign:tools",
                is_hidden=False,
                component="Layout",
                keepalive=False,
                redirect="/toolbox/runcode"
            )
        )
        toolbox_children_menu = [
            Menu(
                menu_type=MenuType.MENU,
                name="Python帮助文档",
                path="pythonHelpDoc",
                order=1,
                parent_id=toolbox_parent_menu.id,
                icon="vscode-icons:file-type-python",
                is_hidden=False,
                component="/toolbox/pythonHelpDoc",
                keepalive=False
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="Python在线编码",
                path="runcode",
                order=2,
                parent_id=toolbox_parent_menu.id,
                icon="vscode-icons:file-type-python",
                is_hidden=False,
                component="/toolbox/runcode",
                keepalive=False
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="虚拟数据生成",
                path="generate",
                order=2,
                parent_id=toolbox_parent_menu.id,
                icon="carbon:data-volume",
                is_hidden=False,
                component="/toolbox/generate",
                keepalive=False
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="文本解析",
                path="textAnalysis",
                order=3,
                parent_id=toolbox_parent_menu.id,
                icon="fluent:text-underline-double-24-filled",
                is_hidden=False,
                component="/toolbox/textAnalysis",
                keepalive=False
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="数据查询",
                path="databaseSearch",
                order=4,
                parent_id=toolbox_parent_menu.id,
                icon="material-symbols:database-search",
                is_hidden=False,
                component="/toolbox/databaseSearch",
                keepalive=False
            ),
        ]
        await Menu.bulk_create(toolbox_children_menu)

        # 一级菜单配置
        await MENU_CRUD.create_menu(
            MenuCreate(
                menu_type=MenuType.MENU,
                name="一级菜单",
                path="/top-menu",
                order=6,
                parent_id=0,
                icon="material-symbols:featured-play-list-outline",
                is_hidden=False,
                component="/top-menu",
                keepalive=False,
                redirect=""
            )
        )


async def init_database_table(app: FastAPI):
    await init_database_role()
    await init_database_dept()
    await init_database_user()
    await init_database_menu()
    await init_database_router(app)
