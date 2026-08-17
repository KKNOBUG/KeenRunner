# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : data_initialization.py
@DateTime: 2025/2/19 22:12
"""
from typing import List

from fastapi import FastAPI

from backend.applications.aotutest.models.autotest_tag_model import AutoTestTagModel
from backend.applications.aotutest.schemas.autotest_env_config_schema import (
    APPEnvConfigCreate,
    DBEnvConfigCreate,
    FILEEnvConfigCreate,
)
from backend.applications.aotutest.schemas.autotest_project_schema import AutoTestApiProjectCreate
from backend.applications.aotutest.schemas.autotest_tag_schema import AutoTestApiTagCreate
from backend.applications.aotutest.services.autotest_env_config_crud import AutoTestEnvConfigCrud
from backend.applications.aotutest.services.autotest_env_crud import AutoTestEnvCrud
from backend.applications.aotutest.services.autotest_project_crud import AutoTestProjectCrud
from backend.applications.aotutest.services.autotest_tag_crud import AutoTestTagCrud
from backend.applications.base.models.menu_model import Menu
from backend.applications.base.models.role_model import Role
from backend.applications.base.schemas.menu_schema import MenuCreate
from backend.applications.base.schemas.role_schema import RoleCreate
from backend.applications.base.services.menu_crud import MenuCrud
from backend.applications.base.services.permission_rule import (
    ROLE_CODE_USER,
    ROLE_CODE_GUEST,
    ROLE_CODE_ADMIN,
    warn_unclassified_routers,
    filter_routers_for_role
)
from backend.applications.base.services.role_crud import RoleCrud
from backend.applications.base.services.router_crud import RouterCrud
from backend.applications.department.models.dept_model import Department
from backend.applications.department.schemas.department_schema import DepartmentCreate
from backend.applications.department.services.department_crud import DepartmentCrud
from backend.applications.user.schemas.user_schema import UserCreate
from backend.applications.user.services.user_crud import UserCrud
from backend.configure import LOGGER
from backend.enums import MenuType

# 初始化种子数据的创建人（管理员账号，大写）
INIT_CREATED_USER = "ADMIN"


async def init_database_role():
    role_crud = RoleCrud()
    if await role_crud.model.exists():
        LOGGER.info("[角色]已有数据，跳过初始化")
        return

    from backend.applications.base.models.router_model import Router

    admin_role = await role_crud.create_role(
        RoleCreate(
            code=ROLE_CODE_ADMIN,
            name="管理员",
            description="平台超管，拥有全部菜单与接口权限",
            created_user=INIT_CREATED_USER,
        ),
    )
    user_role = await role_crud.create_role(
        RoleCreate(
            code=ROLE_CODE_USER,
            name="标准用户",
            description="系统域只读，业务域增删改查全开；不可操作系统写操作与角色权限变更",
            created_user=INIT_CREATED_USER,
        ),
    )
    guest_role = await role_crud.create_role(
        RoleCreate(
            code=ROLE_CODE_GUEST,
            name="宾客用户",
            description="系统域只读，业务域仅查询与新增；禁止一切修改与删除",
            created_user=INIT_CREATED_USER,
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
    warn_unclassified_routers(all_routers)
    admin_routers = filter_routers_for_role(ROLE_CODE_ADMIN, all_routers)
    user_routers = filter_routers_for_role(ROLE_CODE_USER, all_routers)
    guest_routers = filter_routers_for_role(ROLE_CODE_GUEST, all_routers)
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
            name="系统默认部门",
            description="系统默认配置，无具体业务归属，仅作初始部门使用",
            order=0,
            parent_id=0,
            created_user=INIT_CREATED_USER,
        ),
        DepartmentCreate(
            code="AUTOTEST_DEPT",
            name="技术测试团队",
            description="技术测试与冒烟验证相关人员所属部门",
            order=1,
            parent_id=0,
            created_user=INIT_CREATED_USER,
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
    admin_role = await Role.get_or_none(code=ROLE_CODE_ADMIN)
    user_role = await Role.get_or_none(code=ROLE_CODE_USER)
    guest_role = await Role.get_or_none(code=ROLE_CODE_GUEST)

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
            created_user=INIT_CREATED_USER,
        ),
        UserCreate(
            username="tester",
            password="KFuser01@!",
            alias="标准用户",
            email="tester@test.com",
            phone="18888888888",
            avatar="/static/avatar/default/20250101010101.png",
            dept_id=test_dept.id,
            is_superuser=False,
            role_ids=[user_role.id],
            created_user=INIT_CREATED_USER,
        ),
        UserCreate(
            username="guest",
            password="KFuser01@!",
            alias="宾客用户",
            email="guest@test.com",
            phone="18888888888",
            avatar="/static/avatar/default/20250101010101.png",
            dept_id=test_dept.id,
            is_superuser=False,
            role_ids=[guest_role.id],
            created_user=INIT_CREATED_USER,
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
            icon="garden:gear-stroke-12",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/system/user",
            created_user=INIT_CREATED_USER,
        ),
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
            keepalive=False,
            created_user=INIT_CREATED_USER
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
            keepalive=False,
            created_user=INIT_CREATED_USER
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
            created_user=INIT_CREATED_USER
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
            keepalive=False,
            created_user=INIT_CREATED_USER
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
            keepalive=False,
            created_user=INIT_CREATED_USER
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
            keepalive=False,
            created_user=INIT_CREATED_USER
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
            keepalive=False,
            created_user=INIT_CREATED_USER
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="审计日志",
            path="auditlog",
            order=8,
            parent_id=system_parent_menu.id,
            icon="carbon:flow-logs-vpc",
            is_hidden=False,
            component="/system/auditlog",
            keepalive=False,
            created_user=INIT_CREATED_USER
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
            icon="fluent:app-folder-28-filled",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/program/project",
            created_user=INIT_CREATED_USER,
        ),
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
            keepalive=False,
            created_user=INIT_CREATED_USER
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="环境管理",
            path="environment",
            order=2,
            parent_id=program_parent_menu.id,
            icon="eos-icons:env",
            is_hidden=False,
            component="/program/environment",
            keepalive=False,
            created_user=INIT_CREATED_USER
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="标签管理",
            path="tags",
            order=3,
            parent_id=program_parent_menu.id,
            icon="tabler:tags",
            is_hidden=False,
            component="/program/tags",
            keepalive=False,
            created_user=INIT_CREATED_USER
        ),
    ]
    await Menu.bulk_create(program_children_menu)
    LOGGER.info(f"创建[应用管理]目录及子菜单成功")

    # 接口管理（FastAPI 内置 Swagger / ReDoc，由前端 iframe 嵌入展示）
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
            created_user=INIT_CREATED_USER,
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
            created_user=INIT_CREATED_USER
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="ReDoc文档",
            path="redoc",
            order=2,
            parent_id=interface_parent_menu.id,
            icon="mdi:file-document-outline",
            is_hidden=False,
            component="/interface/redoc",
            keepalive=False,
            created_user=INIT_CREATED_USER
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
            order=3,
            parent_id=0,
            icon="garden:bot-sparkle-stroke-12",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/autotest/testcase",
            created_user=INIT_CREATED_USER,
        ),
    )
    autotest_children_menu = [
        Menu(
            menu_type=MenuType.MENU,
            name="Web 测试",
            path="ui",
            order=1,
            parent_id=autotest_parent_menu.id,
            icon="material-symbols:desktop-windows-outline",
            is_hidden=False,
            component="/autotest/ui",
            keepalive=True
            ,
            created_user=INIT_CREATED_USER
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="App 测试",
            path="ui",
            order=2,
            parent_id=autotest_parent_menu.id,
            icon="streamline:phone-mobile-phone-remix",
            is_hidden=False,
            component="/autotest/ui",
            keepalive=True
            ,
            created_user=INIT_CREATED_USER
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="步骤编辑",
            path="steps",
            order=3,
            parent_id=autotest_parent_menu.id,
            icon="mdi:vector-difference",
            is_hidden=True,
            component="/autotest/steps",
            keepalive=True
            ,
            created_user=INIT_CREATED_USER
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
            created_user=INIT_CREATED_USER
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
            created_user=INIT_CREATED_USER
        ),
    ]
    await Menu.bulk_create(autotest_children_menu)
    LOGGER.info(f"创建[自动化测试]目录及子菜单成功")

    # 任务管理菜单配置
    task_parent_menu = await menu_crud.create_menu(
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
            redirect="/task/record",
            created_user=INIT_CREATED_USER,
        ),
    )
    task_children_menu = [
        Menu(
            menu_type=MenuType.MENU,
            name="任务列表",
            path="list",
            order=1,
            parent_id=task_parent_menu.id,
            icon="fluent:document-text-clock-24-regular",
            is_hidden=False,
            component="/task/list",
            keepalive=True
            ,
            created_user=INIT_CREATED_USER
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="执行记录",
            path="record",
            order=2,
            parent_id=task_parent_menu.id,
            icon="fluent:document-checkmark-24-regular",
            is_hidden=False,
            component="/task/record",
            keepalive=True
            ,
            created_user=INIT_CREATED_USER
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
            order=5,
            parent_id=0,
            icon="tdesign:tools",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/toolbox/pythonHelpDoc",
            created_user=INIT_CREATED_USER,
        ),
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
            keepalive=False,
            created_user=INIT_CREATED_USER
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
            keepalive=False,
            created_user=INIT_CREATED_USER
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
            keepalive=False,
            created_user=INIT_CREATED_USER
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
            keepalive=False,
            created_user=INIT_CREATED_USER
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
            order=6,
            parent_id=0,
            icon="material-symbols:featured-play-list-outline",
            is_hidden=False,
            component="/top-menu",
            keepalive=False,
            redirect="",
            created_user=INIT_CREATED_USER,
        ),
    )


async def init_database_router(app: FastAPI):
    router_crud = RouterCrud()
    if await router_crud.model.exists():
        LOGGER.info("[路由]已有数据，跳过初始化")
        return

    # 初始化无 HTTP 登录上下文：临时写入 CTX，供 refresh_router 取当前用户
    from backend.services.ctx import CTX_USERNAME
    CTX_USERNAME.set(INIT_CREATED_USER)
    # 首次灌路由时角色可能尚未创建，关闭自动补绑；角色初始化阶段再完整绑定
    await router_crud.refresh_router(app, sync_role_bindings=False)


async def init_database_project():
    project_crud = AutoTestProjectCrud()
    if await project_crud.model.exists():
        LOGGER.info("[应用]已有数据，跳过初始化")
        return

    await project_crud.create_project(
        AutoTestApiProjectCreate(
            project_name="ToolBox工具箱",
            project_desc="平台默认应用：ToolBox工具箱",
            project_state="开发中",
            project_dev_owners=["admin"],
            project_developers=["admin"],
            project_test_owners=["tester"],
            project_testers=["tester", "guest"],
            created_user=INIT_CREATED_USER,
            project_phase=None,
            project_current_month_env=None,
        )
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

    tag_data: List[AutoTestApiTagCreate] = [
        AutoTestApiTagCreate(
            tag_project=project.id,
            tag_mode="技术测试团队",
            tag_name="测试工程师",
            tag_desc=None,
            created_user=INIT_CREATED_USER,
        ),
        AutoTestApiTagCreate(
            tag_project=project.id,
            tag_mode="技术测试团队",
            tag_name="开发工程师",
            tag_desc=None,
            created_user=INIT_CREATED_USER,
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
        LOGGER.error("[环境配置]初始化失败: 未找到应用 ToolBox工具箱")
        return

    env_crud = AutoTestEnvCrud()
    if await env_crud.model.filter(project_id=project.id, state__not=1).exists():
        LOGGER.info("[环境配置]已有数据，跳过初始化")
        return

    config_crud = AutoTestEnvConfigCrud()
    env_name = "SIT1"
    project_id = int(project.id)

    seed_configs = [
        # 主表1：APP(api)
        APPEnvConfigCreate(
            project_id=project_id,
            config_name="ToolBox工具箱后端1",
            env_name=env_name,
            config_host="172.20.10.2",
            config_port="8519",
            config_desc="服务器1",
            created_user=INIT_CREATED_USER,
        ),
        APPEnvConfigCreate(
            project_id=project_id,
            config_name="ToolBox工具箱后端2",
            env_name=env_name,
            config_host="192.168.1.3",
            config_port="8519",
            config_desc="服务器2",
            created_user=INIT_CREATED_USER,
        ),
        # 主表2：DB(database)
        DBEnvConfigCreate(
            project_id=project_id,
            config_name="ToolBox工具箱后端1",
            env_name=env_name,
            config_host="10.211.55.3",
            config_port="3306",
            database_name="tbx_runner",
            database_type="mysql",
            config_username="root",
            config_password="root",
            config_desc="服务器1",
            created_user=INIT_CREATED_USER,
        ),
        DBEnvConfigCreate(
            project_id=project_id,
            config_name="ToolBox工具箱后端2",
            env_name=env_name,
            config_host="10.211.55.3",
            config_port="3333",
            database_name="tbx_runner",
            database_type="mysql",
            config_username="root",
            config_password="root",
            config_desc="服务器2",
            created_user=INIT_CREATED_USER,
        ),
        # 主表3：FILE
        FILEEnvConfigCreate(
            project_id=project_id,
            config_name="ToolBox工具箱后端1",
            env_name=env_name,
            config_host="10.208.24.12",
            config_port="8888",
            config_username="root",
            config_password="root",
            is_no_password=True,
            config_desc="服务器1",
            created_user=INIT_CREATED_USER,
        ),
        FILEEnvConfigCreate(
            project_id=project_id,
            config_name="ToolBox工具箱后端2",
            env_name=env_name,
            config_host="10.208.24.14",
            config_port="8888",
            config_username="root",
            config_password="root",
            is_no_password=True,
            config_desc="服务器2",
            created_user=INIT_CREATED_USER,
        ),
    ]

    for config_in in seed_configs:
        try:
            created = await config_crud.create_config(config_in)
            LOGGER.info(
                f"创建[环境配置]成功: env={env_name}, type={type(config_in).__name__}, "
                f"name={created.config_name}, id={created.id}"
            )
        except Exception as e:
            LOGGER.error(
                f"创建[环境配置]失败: env={env_name}, type={type(config_in).__name__}, "
                f"name={config_in.config_name}: {e}"
            )

    LOGGER.info("创建[环境配置]初始化完成: ToolBox工具箱 / SIT1 (APP/DB/FILE)")


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
