# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : data_initialization.py
@DateTime: 2025/2/19 22:12
"""
from typing import List

from fastapi import FastAPI

from backend.applications.autotest.models.autotest_tag_model import AutoTestTagModel
from backend.applications.autotest.schemas.autotest_env_config_schema import (
    APPEnvConfigCreate,
    AutoTestEnvConfigCreate,
    DBEnvConfigCreate,
    FILEEnvConfigCreate,
)
from backend.applications.autotest.schemas.autotest_project_schema import AutoTestProjectCreate
from backend.applications.autotest.schemas.autotest_tag_schema import AutoTestTagCreate
from backend.applications.autotest.services.autotest_env_config_crud import AutoTestEnvConfigCrud
from backend.applications.autotest.services.autotest_env_crud import AutoTestEnvCrud
from backend.applications.autotest.services.autotest_project_crud import AutoTestProjectCrud
from backend.applications.autotest.services.autotest_tag_crud import AutoTestTagCrud
from backend.applications.base.models.menu_model import Menu
from backend.applications.base.models.role_model import Role
from backend.applications.base.schemas.menu_schema import MenuCreate
from backend.applications.base.schemas.role_schema import RoleCreate
from backend.applications.base.services.menu_crud import MenuCrud
from backend.applications.base.services.permission_rule import PermissionRule
from backend.applications.base.services.role_crud import RoleCrud
from backend.applications.base.services.router_crud import RouterCrud
from backend.applications.department.models.dept_model import Department
from backend.applications.department.schemas.department_schema import DepartmentCreate
from backend.applications.department.services.department_crud import DepartmentCrud
from backend.applications.user.schemas.user_schema import UserCreate
from backend.applications.user.services.user_crud import UserCrud
from backend.configure import LOGGER
from backend.enums import DataScopeEnum, MenuType
from backend.services import DataScope

# 初始化种子数据的创建人
ADMIN = "ADMIN"
TESTER = "TESTER"


async def init_database_role():
    role_crud = RoleCrud()
    if await role_crud.model.exists():
        await Role.filter(code=PermissionRule.ROLE_CODE_ADMIN).update(
            select_scope=DataScopeEnum.ALL,
            update_scope=DataScopeEnum.ALL,
            delete_scope=DataScopeEnum.ALL
        )
        LOGGER.info("[角色]已有数据，校正管理员数据范围后跳过初始化")
        return

    from backend.applications.base.models.router_model import Router

    admin_role = await role_crud.create_role(
        RoleCreate(
            code=PermissionRule.ROLE_CODE_ADMIN,
            name="管理员",
            description="平台超管，拥有全部菜单与接口权限",
            select_scope=DataScopeEnum.ALL,
            update_scope=DataScopeEnum.ALL,
            delete_scope=DataScopeEnum.ALL,
            created_user=ADMIN,
        ),
    )
    user_role = await role_crud.create_role(
        RoleCreate(
            code=PermissionRule.ROLE_CODE_USER,
            name="普通用户",
            description="系统域只读，业务域增删改查全开；不可操作系统写操作与角色权限变更",
            select_scope=DataScopeEnum.DEPT_AND_CHILD,
            update_scope=DataScopeEnum.SELF,
            delete_scope=DataScopeEnum.SELF,
            created_user=ADMIN,
        ),
    )
    guest_role = await role_crud.create_role(
        RoleCreate(
            code=PermissionRule.ROLE_CODE_GUEST,
            name="访客用户",
            description="系统域只读，业务域增删改查全开；删除仅限本人数据",
            select_scope=DataScopeEnum.DEPT_AND_CHILD,
            update_scope=DataScopeEnum.SELF,
            delete_scope=DataScopeEnum.SELF,
            created_user=ADMIN,
        ),
    )
    LOGGER.info(f"创建角色成功: {admin_role.name} (id: {admin_role.id}, code: {admin_role.code})")
    LOGGER.info(f"创建角色成功: {user_role.name} (id: {user_role.id}, code: {user_role.code})")
    LOGGER.info(f"创建角色成功: {guest_role.name} (id: {guest_role.id}, code: {guest_role.code})")

    all_menus = await Menu.all()
    if all_menus:
        await admin_role.menus.add(*all_menus)
        await user_role.menus.add(*all_menus)
        await guest_role.menus.add(*all_menus)
        LOGGER.info(f"三角色绑定菜单成功, 共计{len(all_menus)}个")

    all_routers = await Router.all()
    PermissionRule.warn_unclassified_routers(all_routers)
    admin_routers = PermissionRule.filter_routers_for_role(PermissionRule.ROLE_CODE_ADMIN, all_routers)
    user_routers = PermissionRule.filter_routers_for_role(PermissionRule.ROLE_CODE_USER, all_routers)
    guest_routers = PermissionRule.filter_routers_for_role(PermissionRule.ROLE_CODE_GUEST, all_routers)
    if admin_routers:
        await admin_role.routers.add(*admin_routers)
    if user_routers:
        await user_role.routers.add(*user_routers)
    if guest_routers:
        await guest_role.routers.add(*guest_routers)
    LOGGER.info(f"角色[{admin_role.name}]绑定路由成功, 共计{len(admin_routers)}个")
    LOGGER.info(f"角色[{user_role.name}]绑定路由成功, 共计{len(user_routers)}个")
    LOGGER.info(f"角色[{guest_role.name}]绑定路由成功, 共计{len(guest_routers)}个")


async def init_database_dept():
    dept_crud = DepartmentCrud()
    if await dept_crud.model.exists():
        LOGGER.info("[部门]已有数据，跳过初始化")
        return

    dept_data: List[DepartmentCreate] = [
        DepartmentCreate(
            code="SYSTEM_DEPT",
            name="ToolBox工具箱",
            description="无具体业务归属，仅作初始部门使用",
            order=0,
            parent_id=0,
            created_user=ADMIN,
        ),
        DepartmentCreate(
            code="AUTOTEST_DEPT",
            name="ToolBox工具箱开发&测试部门",
            description="ToolBox工具箱开发与测试相关人员所属部门",
            order=1,
            parent_id=0,
            created_user=TESTER,
        ),
    ]

    for dept_in in dept_data:
        try:
            dept = await dept_crud.create_department(department_in=dept_in)
            LOGGER.info(f"创建部门成功: {dept.name} (id: {dept.id}, code: {dept.code})")
        except Exception as e:
            LOGGER.error(f"创建部门失败: {dept_in.name}, code: {dept_in.code}: {e}")


async def init_database_user():
    user_crud = UserCrud()
    if await user_crud.model.exists():
        LOGGER.info("[用户]已有数据，跳过初始化")
        return

    default_dept = await Department.get_or_none(code="SYSTEM_DEPT")
    test_dept = await Department.get_or_none(code="AUTOTEST_DEPT")
    admin_role = await Role.get_or_none(code=PermissionRule.ROLE_CODE_ADMIN)
    user_role = await Role.get_or_none(code=PermissionRule.ROLE_CODE_USER)
    guest_role = await Role.get_or_none(code=PermissionRule.ROLE_CODE_GUEST)

    if not all([default_dept, test_dept, admin_role, user_role, guest_role]):
        LOGGER.error("[用户]初始化失败: 部门或角色尚未就绪，请检查初始化顺序")
        return

    user_data: List[UserCreate] = [
        UserCreate(
            username="admin",
            password="KFuser01@!",
            alias="系统管理员",
            email="admin@test.com",
            phone="18888888888",
            avatar="/static/avatar/default/20250101010101.png",
            dept_id=default_dept.id,
            is_superuser=True,
            role_ids=[admin_role.id],
            created_user=ADMIN,
        ),
        UserCreate(
            username="tester",
            password="KFuser01@!",
            alias="普通用户",
            email="tester@test.com",
            phone="18888888888",
            avatar="/static/avatar/default/20250101010101.png",
            dept_id=test_dept.id,
            is_superuser=False,
            role_ids=[user_role.id],
            created_user=ADMIN,
        ),
        UserCreate(
            username="guest",
            password="KFuser01@!",
            alias="访客用户",
            email="guest@test.com",
            phone="18888888888",
            avatar="/static/avatar/default/20250101010101.png",
            dept_id=test_dept.id,
            is_superuser=False,
            role_ids=[guest_role.id],
            created_user=ADMIN,
        ),
    ]
    for user_in in user_data:
        try:
            user = await user_crud.create_user(user_in=user_in)
            LOGGER.info(f"创建用户成功: {user.alias} (id: {user.id}, username: {user.username})")
        except Exception as e:
            LOGGER.error(f"创建用户失败: {user_in.alias}, username: {user_in.username}: {e}")


async def init_database_menu():
    menu_crud = MenuCrud()
    if await menu_crud.model.exists():
        LOGGER.info("[菜单]已有数据，跳过初始化")
        return
    # 系统设置菜单配置
    system_parent_menu = await menu_crud.create_menu(
        MenuCreate(
            menu_type=MenuType.CATALOG,
            name="系统管理",
            path="/system",
            order=1,
            parent_id=0,
            icon="gravity-ui:gear",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/system/user",
            created_user=ADMIN,
        ),
    )
    system_children_menu = [
        Menu(
            menu_type=MenuType.MENU,
            name="用户管理",
            path="user",
            order=1,
            parent_id=system_parent_menu.id,
            icon="gravity-ui:persons",
            is_hidden=False,
            component="/system/user",
            keepalive=False,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="角色管理",
            path="role",
            order=2,
            parent_id=system_parent_menu.id,
            icon="gravity-ui:person-gear",
            is_hidden=False,
            component="/system/role",
            keepalive=False,
            created_user=ADMIN
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
            keepalive=False,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="路由管理",
            path="router",
            order=4,
            parent_id=system_parent_menu.id,
            icon="gravity-ui:molecule",
            is_hidden=False,
            component="/system/router",
            keepalive=False,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="部门管理",
            path="dept",
            order=5,
            parent_id=system_parent_menu.id,
            icon="gravity-ui:timestamps",
            is_hidden=False,
            component="/system/dept",
            keepalive=False,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="缓存数据库管理",
            path="redis",
            order=6,
            parent_id=system_parent_menu.id,
            icon="gravity-ui:layout-header-cells-large-thunderbolt",
            is_hidden=False,
            component="/system/redis",
            keepalive=False,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="外部数据库管理",
            path="database",
            order=7,
            parent_id=system_parent_menu.id,
            icon="gravity-ui:layout-header-cells-large-letter-d",
            is_hidden=False,
            component="/system/database",
            keepalive=False,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="审计日志",
            path="auditlog",
            order=8,
            parent_id=system_parent_menu.id,
            icon="gravity-ui:square-bars",
            is_hidden=False,
            component="/system/auditlog",
            keepalive=False,
            created_user=ADMIN
        ),
    ]
    await Menu.bulk_create(system_children_menu)
    LOGGER.info(f"创建[系统管理]目录及子菜单成功")

    # 应用管理菜单配置
    program_parent_menu = await menu_crud.create_menu(
        MenuCreate(
            menu_type=MenuType.CATALOG,
            name="应用管理",
            path="/program",
            order=2,
            parent_id=0,
            icon="gravity-ui:box",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/program/project",
            created_user=ADMIN,
        ),
    )
    program_children_menu = [
        Menu(
            menu_type=MenuType.MENU,
            name="项目管理",
            path="project",
            order=1,
            parent_id=program_parent_menu.id,
            icon="gravity-ui:cube",
            is_hidden=False,
            component="/program/project",
            keepalive=False,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="环境管理",
            path="environment",
            order=2,
            parent_id=program_parent_menu.id,
            icon="gravity-ui:gear-branches",
            is_hidden=False,
            component="/program/environment",
            keepalive=False,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="标签管理",
            path="tags",
            order=3,
            parent_id=program_parent_menu.id,
            icon="gravity-ui:tags",
            is_hidden=False,
            component="/program/tags",
            keepalive=False,
            created_user=ADMIN
        ),
    ]
    await Menu.bulk_create(program_children_menu)
    LOGGER.info(f"创建[应用管理]目录及子菜单成功")

    # 接口管理
    interface_parent_menu = await menu_crud.create_menu(
        MenuCreate(
            menu_type=MenuType.CATALOG,
            name="接口管理",
            path="/interface",
            order=3,
            parent_id=0,
            icon="gravity-ui:abbr-api",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/interface/swagger",
            created_user=ADMIN,
        ),
    )
    interface_children_menu = [
        Menu(
            menu_type=MenuType.MENU,
            name="Swagger文档",
            path="swagger",
            order=1,
            parent_id=interface_parent_menu.id,
            icon="devicon:swagger",
            is_hidden=False,
            component="/interface/swagger",
            keepalive=False,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="ReDoc文档",
            path="redoc",
            order=2,
            parent_id=interface_parent_menu.id,
            icon="devicon:swagger",
            is_hidden=False,
            component="/interface/redoc",
            keepalive=False,
            created_user=ADMIN
        ),
    ]
    await Menu.bulk_create(interface_children_menu)
    LOGGER.info(f"创建[接口管理]目录及子菜单成功")

    # 自动化测试菜单配置
    autotest_parent_menu = await menu_crud.create_menu(
        MenuCreate(
            menu_type=MenuType.CATALOG,
            name="自动化测试",
            path="/autotest",
            order=4,
            parent_id=0,
            icon="gravity-ui:rocket",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/autotest/testcase",
            created_user=ADMIN,
        ),
    )
    autotest_children_menu = [
        Menu(
            menu_type=MenuType.MENU,
            name="Web 测试",
            path="ui",
            order=1,
            parent_id=autotest_parent_menu.id,
            icon="gravity-ui:display",
            is_hidden=False,
            component="/autotest/ui",
            keepalive=True
            ,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="App 测试",
            path="app",
            order=2,
            parent_id=autotest_parent_menu.id,
            icon="gravity-ui:smartphone",
            is_hidden=False,
            component="/autotest/ui",
            keepalive=True
            ,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="用例编辑",
            path="steps",
            order=3,
            parent_id=autotest_parent_menu.id,
            icon="mdi:vector-difference",
            is_hidden=True,
            component="/autotest/steps",
            keepalive=True
            ,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="测试用例",
            path="testcase",
            order=4,
            parent_id=autotest_parent_menu.id,
            icon="mdi:vector-link",
            is_hidden=False,
            component="/autotest/testcase",
            keepalive=True
            ,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="测试报告",
            path="report",
            order=5,
            parent_id=autotest_parent_menu.id,
            icon="garden:document-search-stroke-12",
            is_hidden=False,
            component="/autotest/report",
            keepalive=True
            ,
            created_user=ADMIN
        ),
    ]
    await Menu.bulk_create(autotest_children_menu)
    LOGGER.info(f"创建[自动化测试]目录及子菜单成功")

    # 性能测试菜单配置
    perf_parent_menu = await menu_crud.create_menu(
        MenuCreate(
            menu_type=MenuType.CATALOG,
            name="性能测试",
            path="/performance",
            order=5,
            parent_id=0,
            icon="gravity-ui:tachometer",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/performance/scene",
            created_user=ADMIN,
        ),
    )
    perf_children_menu = [
        Menu(
            menu_type=MenuType.MENU,
            name="压测接口",
            path="api",
            order=1,
            parent_id=perf_parent_menu.id,
            icon="gravity-ui:abbr-api",
            is_hidden=False,
            component="/performance/api",
            keepalive=True,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="接口编辑",
            path="api/edit",
            order=2,
            parent_id=perf_parent_menu.id,
            icon="gravity-ui:abbr-api",
            is_hidden=True,
            component="/performance/api/edit",
            keepalive=False,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="压测场景",
            path="scene",
            order=3,
            parent_id=perf_parent_menu.id,
            icon="gravity-ui:speedometer",
            is_hidden=False,
            component="/performance/scene",
            keepalive=True,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="场景编辑",
            path="scene/edit",
            order=4,
            parent_id=perf_parent_menu.id,
            icon="gravity-ui:speedometer",
            is_hidden=True,
            component="/performance/scene/edit",
            keepalive=False,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="执行机器",
            path="machine",
            order=5,
            parent_id=perf_parent_menu.id,
            icon="gravity-ui:display",
            is_hidden=False,
            component="/performance/machine",
            keepalive=True,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="定时压测",
            path="schedule",
            order=6,
            parent_id=perf_parent_menu.id,
            icon="gravity-ui:alarm",
            is_hidden=False,
            component="/performance/schedule",
            keepalive=True,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="压测报告",
            path="report",
            order=7,
            parent_id=perf_parent_menu.id,
            icon="garden:document-search-stroke-12",
            is_hidden=False,
            component="/performance/report",
            keepalive=True,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="压测报告详情",
            path="report/detail",
            order=8,
            parent_id=perf_parent_menu.id,
            icon="garden:document-search-stroke-12",
            is_hidden=True,
            component="/performance/report/detail",
            keepalive=False,
            created_user=ADMIN
        ),
    ]
    await Menu.bulk_create(perf_children_menu)
    LOGGER.info(f"创建[性能测试]目录及子菜单成功")

    # 任务管理菜单配置
    task_parent_menu = await menu_crud.create_menu(
        MenuCreate(
            menu_type=MenuType.CATALOG,
            name="任务管理",
            path="/task",
            order=6,
            parent_id=0,
            icon="gravity-ui:alarm",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/task/async_center",
            created_user=ADMIN,
        ),
    )
    task_children_menu = [
        Menu(
            menu_type=MenuType.MENU,
            name="任务列表",
            path="list",
            order=1,
            parent_id=task_parent_menu.id,
            icon="gravity-ui:list-timeline",
            is_hidden=False,
            component="/task/list",
            keepalive=True
            ,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="执行记录",
            path="record",
            order=2,
            parent_id=task_parent_menu.id,
            icon="gravity-ui:clock-arrow-rotate-left",
            is_hidden=False,
            component="/task/record",
            keepalive=True
            ,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="异步中心",
            path="async_center",
            order=3,
            parent_id=task_parent_menu.id,
            icon="gravity-ui:layers",
            is_hidden=False,
            component="/task/async_center",
            keepalive=True
            ,
            created_user=ADMIN
        ),
    ]
    await Menu.bulk_create(task_children_menu)
    LOGGER.info(f"创建[任务管理]目录及子菜单成功")

    # 便捷工具菜单配置
    toolbox_parent_menu = await menu_crud.create_menu(
        MenuCreate(
            menu_type=MenuType.CATALOG,
            name="便捷工具",
            path="/toolbox",
            order=7,
            parent_id=0,
            icon="gravity-ui:hammer",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/toolbox/pythonHelpDoc",
            created_user=ADMIN,
        ),
    )
    toolbox_children_menu = [
        Menu(
            menu_type=MenuType.MENU,
            name="Python帮助文档",
            path="pythonHelpDoc",
            order=1,
            parent_id=toolbox_parent_menu.id,
            icon="gravity-ui:logo-python",
            is_hidden=False,
            component="/toolbox/pythonHelpDoc",
            keepalive=False,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="虚拟数据生成",
            path="generate",
            order=2,
            parent_id=toolbox_parent_menu.id,
            icon="tabler:image-generation",
            is_hidden=False,
            component="/toolbox/generate",
            keepalive=False,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="文本解析",
            path="textAnalysis",
            order=3,
            parent_id=toolbox_parent_menu.id,
            icon="gravity-ui:font-case",
            is_hidden=False,
            component="/toolbox/textAnalysis",
            keepalive=False,
            created_user=ADMIN
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="数据查询",
            path="databaseSearch",
            order=4,
            parent_id=toolbox_parent_menu.id,
            icon="gravity-ui:layout-header-cells-large-letter-d",
            is_hidden=False,
            component="/toolbox/databaseSearch",
            keepalive=False,
            created_user=ADMIN
        ),
    ]
    await Menu.bulk_create(toolbox_children_menu)
    LOGGER.info(f"创建[便捷工具]目录及子菜单成功")

    # 一级菜单配置
    await menu_crud.create_menu(
        MenuCreate(
            menu_type=MenuType.MENU,
            name="一级菜单",
            path="/top-menu",
            order=8,
            parent_id=0,
            icon="material-symbols:featured-play-list-outline",
            is_hidden=False,
            component="/top-menu",
            keepalive=False,
            redirect="",
            created_user=ADMIN,
        ),
    )


async def init_database_router(app: FastAPI):
    router_crud = RouterCrud()
    if await router_crud.model.exists():
        LOGGER.info("[路由]已有数据，跳过初始化")
        return

    # 初始化无 HTTP 登录上下文：仅在路由刷新期间写入 CTX，退出时恢复进入前的身份
    from backend.services.ctx import CTX_USERNAME
    username_token = CTX_USERNAME.set(ADMIN)
    try:
        # 首次灌路由时角色可能尚未创建，关闭自动补绑；角色初始化阶段再完整绑定
        await router_crud.refresh_router(app, sync_role_bindings=False)
    finally:
        # 同一初始化任务还会继续创建其他数据，临时身份不能泄漏到后续链路
        CTX_USERNAME.reset(username_token)


async def init_database_project():
    project_crud = AutoTestProjectCrud()
    if await project_crud.model.exists():
        LOGGER.info("[应用]已有数据，跳过初始化")
        return

    await project_crud.create_project(
        AutoTestProjectCreate(
            project_name="ToolBox工具箱",
            project_desc="平台默认应用：ToolBox工具箱",
            project_state="开发中",
            project_dev_owners=["admin"],
            project_developers=["admin"],
            project_test_owners=["tester"],
            project_testers=["tester", "guest"],
            created_user=TESTER,
            project_phase=None,
            project_current_month_env=None,
        ),
        scope=DataScope.system(),
    )
    LOGGER.info("创建[应用]成功: ToolBox工具箱")


async def init_database_tag():
    tag_crud = AutoTestTagCrud()
    if await tag_crud.model.exists():
        LOGGER.info("[标签]已有数据，跳过初始化")
        return

    project_crud = AutoTestProjectCrud()
    project = await project_crud.model.filter(project_name="ToolBox工具箱").first()
    if not project:
        LOGGER.error("[标签]初始化失败: 未找到应用 ToolBox工具箱")
        return

    tag_data: List[AutoTestTagCreate] = [
        AutoTestTagCreate(
            tag_project=project.id,
            tag_mode="技术测试团队",
            tag_name="测试工程师",
            tag_desc=None,
            created_user=TESTER,
        ),
        AutoTestTagCreate(
            tag_project=project.id,
            tag_mode="技术测试团队",
            tag_name="开发工程师",
            tag_desc=None,
            created_user=TESTER,
        ),
        AutoTestTagCreate(
            tag_project=project.id,
            tag_mode="技术测试团队",
            tag_name="运维工程师",
            tag_desc=None,
            created_user=TESTER,
        ),
    ]
    await tag_crud.model.bulk_create(
        [
            AutoTestTagModel(**tag.model_dump())
            for tag in tag_data
        ]
    )
    LOGGER.info("创建[标签]成功")


async def init_database_env_config():
    project_crud = AutoTestProjectCrud()
    project = await project_crud.model.filter(project_name="ToolBox工具箱", state__not=1).first()
    if not project:
        LOGGER.error("[环境配置]初始化失败: 未找到[ToolBox工具箱]应用")
        return

    env_crud = AutoTestEnvCrud()
    if await env_crud.model.filter(project_id=project.id, state__not=1).exists():
        LOGGER.info("[环境配置]已有数据，跳过初始化")
        return

    config_crud = AutoTestEnvConfigCrud()
    project_id = int(project.id)
    scope = DataScope.system()

    # 占位种子：每个环境为 APP/DB/FILE 各生成两条，地址与端口按环境序号区分，使用方按真实环境修正
    seed_configs: List[AutoTestEnvConfigCreate] = []
    for env_index, env_name in enumerate(("UAT1", "UAT2", "UAT3"), start=1):
        seed_configs.append(
            APPEnvConfigCreate(
                project_id=project_id,
                config_name="ToolBox工具箱-APP配置1",
                env_name=env_name,
                config_host="192.168.1.27",
                config_port="8518",
                config_desc=f"ToolBox工具箱, 后端服务器{env_name}环境APP配置1",
                created_user=TESTER,
            )
        )
        seed_configs.append(
            APPEnvConfigCreate(
                project_id=project_id,
                config_name="ToolBox工具箱-APP配置2",
                env_name=env_name,
                config_host="192.168.1.27",
                config_port="8519",
                config_desc=f"ToolBox工具箱, 后端服务器{env_name}环境APP配置2",
                created_user=TESTER,
            )
        )
        seed_configs.append(
            APPEnvConfigCreate(
                project_id=project_id,
                config_name="ToolBox工具箱-TCP&JSON报文",
                env_name=env_name,
                config_host="192.168.1.27",
                config_port="9091",
                config_desc=f"JSON请求(银行账户交易查询→XML响应)",
                created_user=TESTER,
            )
        )
        seed_configs.append(
            APPEnvConfigCreate(
                project_id=project_id,
                config_name="ToolBox工具箱-TCP&XML报文",
                env_name=env_name,
                config_host="192.168.1.27",
                config_port="9092",
                config_desc=f"XML请求(贷款申请→XML响应)",
                created_user=TESTER,
            )
        )
        seed_configs.append(
            APPEnvConfigCreate(
                project_id=project_id,
                config_name="ToolBox工具箱-10进制8位不包含",
                env_name=env_name,
                config_host="192.168.1.27",
                config_port="9093",
                config_desc=f"TCP协议：10进制/8位长度位/不包含长度位",
                created_user=TESTER,
            )
        )
        seed_configs.append(
            APPEnvConfigCreate(
                project_id=project_id,
                config_name="ToolBox工具箱-16进制4位包含",
                env_name=env_name,
                config_host="192.168.1.27",
                config_port="9094",
                config_desc=f"TCP协议：16进制/4位长度位/包含长度位",
                created_user=TESTER,
            )
        )
        seed_configs.append(
            APPEnvConfigCreate(
                project_id=project_id,
                config_name="ToolBox工具箱-不使用进制数",
                env_name=env_name,
                config_host="192.168.1.27",
                config_port="9095",
                config_desc=f"TCP协议：进制数不使用，请求/响应结束符\r\n",
                created_user=TESTER,
            )
        )
        seed_configs.append(
            APPEnvConfigCreate(
                project_id=project_id,
                config_name="ToolBox工具箱-10进制8位不包含&开启HEX",
                env_name=env_name,
                config_host="192.168.1.27",
                config_port="9096",
                config_desc=f"TCP协议：10进制/8位/不包含长度位/HEX开启",
                created_user=TESTER,
            )
        )
        seed_configs.append(
            APPEnvConfigCreate(
                project_id=project_id,
                config_name="ToolBox工具箱-10进制8位不包含&GBK编码",
                env_name=env_name,
                config_host="192.168.1.27",
                config_port="9097",
                config_desc=f"TCP协议：10进制/8位/不包含长度位/GBK编码",
                created_user=TESTER,
            )
        )
        seed_configs.append(
            APPEnvConfigCreate(
                project_id=project_id,
                config_name="ToolBox工具箱-不使用进制数且无结束符",
                env_name=env_name,
                config_host="192.168.1.27",
                config_port="9098",
                config_desc=f"TCP协议：进制数不使用且无结束符，报文原样收发",
                created_user=TESTER,
            )
        )
        seed_configs.append(
            APPEnvConfigCreate(
                project_id=project_id,
                config_name="ToolBox工具箱-帧字段共存组合",
                env_name=env_name,
                config_host="192.168.1.27",
                config_port="9099",
                config_desc=f"TCP协议：帧字段共存组合（进制数与结束符不互斥）：推导按优先级取长度前缀，结束符保留不参与成帧",
                created_user=TESTER,
            )
        )
        seed_configs.append(
            DBEnvConfigCreate(
                project_id=project_id,
                config_name="ToolBox工具箱-DB配置1",
                env_name=env_name,
                config_host="10.211.55.3",
                config_port="3306",
                database_name="krun",
                database_type="mysql",
                config_username="root",
                config_password="root",
                config_desc=f"ToolBox工具箱, 后端服务器{env_name}环境DB配置1",
                created_user=TESTER,
            )
        )
        seed_configs.append(
            DBEnvConfigCreate(
                project_id=project_id,
                config_name="ToolBox工具箱-DB配置2",
                env_name=env_name,
                config_host="10.211.55.3",
                config_port="3307",
                database_name="krun",
                database_type="mysql",
                config_username="root",
                config_password="root",
                config_desc=f"ToolBox工具箱, 后端服务器{env_name}环境DB配置2",
                created_user=TESTER,
            )
        )
        seed_configs.append(
            FILEEnvConfigCreate(
                project_id=project_id,
                config_name="ToolBox工具箱-FILE配置1",
                env_name=env_name,
                config_host="10.208.24.12",
                config_port="8888",
                config_username="root",
                config_password="root",
                is_no_password=True,
                config_desc=f"ToolBox工具箱, 后端服务器{env_name}环境FILE配置1",
                created_user=TESTER,
            )
        )
        seed_configs.append(
            FILEEnvConfigCreate(
                project_id=project_id,
                config_name="ToolBox工具箱-FILE配置2",
                env_name=env_name,
                config_host="10.208.24.12",
                config_port="9999",
                config_username="root",
                config_password="root",
                is_no_password=True,
                config_desc=f"ToolBox工具箱, 后端服务器{env_name}环境FILE配置2",
                created_user=TESTER,
            )
        )

    for config_in in seed_configs:
        try:
            created = await config_crud.create_config(config_in, scope=scope)
            LOGGER.info(
                f"创建[环境配置]成功: env={config_in.env_name}, type={type(config_in).__name__}, "
                f"name={created.config_name}, id={created.id}"
            )
        except Exception as e:
            LOGGER.error(
                f"创建[环境配置]失败: env={config_in.env_name}, type={type(config_in).__name__}, "
                f"name={config_in.config_name}: {e}"
            )

    LOGGER.info("创建[环境配置]初始化完成: ToolBox工具箱 & UAT1-UAT3(APP/DB/FILE)")


async def init_database_table(app: FastAPI):
    # 菜单/路由须先于角色，角色/部门须先于用户；应用须先于标签/环境配置
    await init_database_menu()
    await init_database_router(app)
    await init_database_role()
    await init_database_dept()
    await init_database_user()
    await init_database_project()
    await init_database_tag()
    await init_database_env_config()
