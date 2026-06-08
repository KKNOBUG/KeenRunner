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
from tortoise.expressions import Q

from backend.applications.aotutest.schemas.autotest_case_schema import AutoTestApiCaseCreate
from backend.applications.aotutest.schemas.autotest_project_schema import AutoTestApiProjectCreate
from backend.applications.aotutest.schemas.autotest_step_schema import AutoTestApiStepCreate
from backend.applications.aotutest.schemas.autotest_tag_schema import AutoTestApiTagCreate
from backend.applications.aotutest.services.autotest_case_crud import AutoTestApiCaseCrud
from backend.applications.aotutest.services.autotest_project_crud import AutoTestApiProjectCrud
from backend.applications.aotutest.services.autotest_step_crud import AutoTestApiStepCrud
from backend.applications.aotutest.services.autotest_tag_crud import AutoTestApiTagCrud
from backend.applications.base.models.menu_model import Menu
from backend.applications.base.models.router_model import Router
from backend.applications.base.schemas.menu_schema import MenuCreate
from backend.applications.base.schemas.role_schema import RoleCreate
from backend.applications.base.services.menu_crud import MenuCrud
from backend.applications.base.services.role_crud import RoleCrud
from backend.applications.base.services.router_crud import RouterCrud
from backend.applications.department.schemas.department_schema import DepartmentCreate
from backend.applications.department.services.department_crud import DepartmentCrud
from backend.applications.user.schemas.user_schema import UserCreate
from backend.applications.user.services.user_crud import UserCrud
from backend.configure import LOGGER
from backend.enums import AutoTestStepType
from backend.enums import MenuType


async def init_database_role():
    role_crud = RoleCrud()
    role_table = await role_crud.model.exists()
    if role_table:
        LOGGER.info("[角色]数据表已存在，跳过初始化")
        return

    admin_role = await role_crud.create_role(
        RoleCreate(
            code="ROLE-9999",
            name="超级用户",
            description="超级用户角色"
        )
    )
    normal_role = await role_crud.create_role(
        RoleCreate(
            code="ROLE-1001",
            name="普通用户",
            description="普通用户角色"
        )
    )
    LOGGER.info(f"创建[超级用户]角色成功: {admin_role.name} (id: {admin_role.id}, code: {admin_role.code})")
    LOGGER.info(f"创建[普通用户]角色成功: {normal_role.name} (id: {normal_role.id}, code: {normal_role.code})")

    # 为超级用户角色分配所有的路由
    all_routers = await Router.all()
    await admin_role.routers.add(*all_routers)
    LOGGER.info(f"角色[超级用户]绑定路由成功, 共计{len(all_routers)}个")

    # 为普通用户分配基本路由
    # Router.tags 来自 FastAPI include_router 的 tags（如“基础服务”“用户服务”），
    # 因此这里使用模糊匹配“基础”，避免精确字符串不一致导致普通用户无法访问。
    basic_routers = await Router.filter(Q(method__in=["GET"]) | Q(tags__icontains="基础"))
    await normal_role.routers.add(*basic_routers)
    LOGGER.info(f"角色[超级用户]绑定路由成功, 共计{len(basic_routers)}个")

    # 为超级用户角色和普通用户角色分配所有的菜单
    all_menus = await Menu.all()
    await admin_role.menus.add(*all_menus)
    await normal_role.menus.add(*all_menus)
    LOGGER.info(f"角色[超级用户]绑定菜单成功, 共计{len(all_menus)}个")
    LOGGER.info(f"角色[普通用户]绑定菜单成功, 共计{len(all_menus)}个")


async def init_database_dept():
    dept_crud = DepartmentCrud()
    dept_table = await dept_crud.model.exists()
    if dept_table:
        LOGGER.info("[部门]数据表已存在，跳过初始化")
        return

    dept_data: List[DepartmentCreate] = [
        DepartmentCreate(
            code="DEPT-9999",
            name="默认部门",
            description="系统默认配置，无具体部门，仅作初始部门使用",
            order=0,
            parent_id=0
        ),
        DepartmentCreate(
            code="DEPT-KF",
            name="研发部(技术中心)",
            description="软件开发部门，包含前端开发、后端开发、功能测试、自动化测试等",
            order=0,
            parent_id=0
        ),
        DepartmentCreate(
            code="DEPT-KF01",
            name="开发一部",
            description="软件开发部门，开发一部",
            order=1,
            parent_id=2
        ),
        DepartmentCreate(
            code="DEPT-KF02",
            name="开发二部",
            description="软件开发部门，开发二部",
            order=1,
            parent_id=2
        ),
        DepartmentCreate(
            code="DEPT-CS",
            name="测试部门",
            description="软件测试部门",
            order=0,
            parent_id=0
        ),
        DepartmentCreate(
            code="DEPT-CS01",
            name="测试一部",
            description="软件测试部门，测试一部",
            order=1,
            parent_id=5
        ),
        DepartmentCreate(
            code="DEPT-CS02",
            name="测试二部",
            description="软件测试部门，测试二部",
            order=1,
            parent_id=5
        )
    ]

    for dept_in in dept_data:
        try:
            dept = await dept_crud.create_department(department_in=dept_in)
            LOGGER.info(f"创建部门成功: {dept.name} (id: {dept.id}, username: {dept.code})")
        except Exception as e:
            LOGGER.error(f"创建部门失败: {dept_in['alias']}, username: {dept_in['username']}: {e}")


async def init_database_user():
    user_crud = UserCrud()
    user_table = await user_crud.model.exists()
    if user_table:
        LOGGER.info("[用户]数据表已存在，跳过初始化")
        return

    user_data: List[UserCreate] = [
        UserCreate(
            username="admin",
            password="123456",
            alias="系统管理员",
            email="admin@test.com",
            phone="18888888888",
            avatar="/static/avatar/default/20250101010101.png",
            dept_id=1,
            is_active=True,
            is_superuser=True,
            role_ids=[1],
        ),
        UserCreate(
            username="guest",
            password="123456",
            alias="访客用户",
            email="guest@test.com",
            phone="18888888888",
            avatar="/static/avatar/default/20250101010101.png",
            dept_id=6,
            is_active=True,
            is_superuser=False,
            role_ids=[2],
        ),
        UserCreate(
            username="tester",
            password="123456",
            alias="测试用户",
            email="tester@test.com",
            phone="18888888888",
            avatar="/static/avatar/default/20250101010101.png",
            dept_id=7,
            is_active=True,
            is_superuser=False,
            role_ids=[2],
        )
    ]
    for user_in in user_data:
        try:
            user = await user_crud.create_user(user_in=user_in)
            LOGGER.info(f"创建用户成功: {user.alias} (id: {user.id}, username: {user.username})")
        except Exception as e:
            LOGGER.error(f"创建用户失败: {user_in['alias']}, username: {user_in['username']}: {e}")


async def init_database_menu():
    menu_crud = MenuCrud()
    menu_table = await menu_crud.model.exists()
    if menu_table:
        LOGGER.info("[菜单]数据表已存在，跳过初始化")
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
            icon="carbon:flow-logs-vpc",
            is_hidden=False,
            component="/system/auditlog",
            keepalive=False
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
            name="环境管理",
            path="environment",
            order=2,
            parent_id=program_parent_menu.id,
            # icon="fluent:apps-add-in-28-regular",
            icon="eos-icons:env",
            is_hidden=False,
            component="/program/environment",
            keepalive=False
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
            keepalive=False
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
            redirect="/interface/swagger"
        )
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
            keepalive=False
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
            keepalive=False
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
            redirect="/autotest/testcase"
        )
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
            redirect="/task/record"
        )
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
            redirect="/toolbox/pythonHelpDoc"
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
            redirect=""
        )
    )


async def init_database_router(app: FastAPI):
    router_crud = RouterCrud()
    router_table = await router_crud.model.exists()
    if router_table:
        LOGGER.info("[路由]数据表已存在，跳过初始化")
        return

    await router_crud.refresh_router(app)


async def init_database_project():
    project_crud = AutoTestApiProjectCrud()
    project_table = await project_crud.model.exists()
    if project_table:
        LOGGER.info("[应用]数据表已存在，跳过初始化")
        return

    await project_crud.create_project(
        AutoTestApiProjectCreate(
            project_name="KRUN",
            project_desc="KRUN测管平台",
            project_state="开发中",
            project_dev_owners=["张三丰", "秦始皇"],
            project_developers=["张余", "苏钰", "赵思明", "叶无云", "沈牧云"],
            project_test_owners=["黄思妙", "吴婕妤"],
            project_testers=["谢霆锋", "赵思明", "杨浩亮"],
            created_user="admin",
            project_phase=None,
            project_current_month_env=None,
        )
    )
    LOGGER.info(f"创建[应用]成功")


async def init_database_tag():
    tag_crud = AutoTestApiTagCrud()
    tag_table = await tag_crud.model.exists()
    if tag_table:
        LOGGER.info("[标签]数据表已存在，跳过初始化")
        return

    tag_data: List[AutoTestApiTagCreate] = [
        AutoTestApiTagCreate(
            tag_project=1,
            tag_mode="技术研发部",
            tag_name="后端开发工程师",
            tag_desc=None,
        ),
        AutoTestApiTagCreate(
            tag_project=1,
            tag_mode="技术研发部",
            tag_name="前端开发工程师",
            tag_desc=None,
        ),
        AutoTestApiTagCreate(
            tag_project=1,
            tag_mode="技术研发部",
            tag_name="测试工程师",
            tag_desc=None,
        ),
        AutoTestApiTagCreate(
            tag_project=1,
            tag_mode="技术研发部",
            tag_name="运维工程师",
            tag_desc=None,
        ),
        AutoTestApiTagCreate(
            tag_project=1,
            tag_mode="技术研发部",
            tag_name="运维工程师",
            tag_desc=None,
        ),
        AutoTestApiTagCreate(
            tag_project=1,
            tag_mode="市场营销部",
            tag_name="新媒体运营",
            tag_desc=None,
        ),
        AutoTestApiTagCreate(
            tag_project=1,
            tag_mode="市场营销部",
            tag_name="短视频运营",
            tag_desc=None,
        ),
        AutoTestApiTagCreate(
            tag_project=1,
            tag_mode="市场营销部",
            tag_name="活动策划",
            tag_desc=None,
        ),
    ]
    await tag_crud.model.bulk_create(*tag_data)
    LOGGER.info(f"创建[标签]成功")


async def init_database_case():
    case_crud = AutoTestApiCaseCrud()
    case_table = await case_crud.model.exists()
    if case_table:
        LOGGER.info("[用例]数据表已存在，跳过初始化")
        return

    cases: List[AutoTestApiCaseCreate] = [

    ]
    await case_crud.model.bulk_create(*cases)
    LOGGER.info(f"创建[用例]成功")


async def init_database_step():
    step_crud = AutoTestApiStepCrud()
    step_table = await step_crud.model.exists()
    if step_table:
        LOGGER.info("[步骤]数据表已存在，跳过初始化")
        return

    steps: List[AutoTestApiStepCreate] = [
        AutoTestApiStepCreate(
            case_id=1,
            step_no=1,
            step_name="用户自定义变量池",
            step_type=AutoTestStepType.USER_VARIABLES,
            step_desc="用户自定义的变量, 提供后续步骤使用",
            created_user="admin",
            session_variables=[
                {
                    "key": "name",
                    "desc": "姓名",
                    "value": "${generate_name()}"
                },
                {
                    "key": "ident",
                    "desc": "年龄",
                    "value": "${generate_ident_card_number_condition(min_age=18, max_age=18)}"
                },
                {
                    "key": "city",
                    "desc": "城市",
                    "value": "${generate_city()}"
                },
                {
                    "key": "country",
                    "desc": "国家",
                    "value": "${generate_country()}"
                },
                {
                    "key": "province",
                    "desc": "省份",
                    "value": "${generate_province()}"
                },
                {
                    "key": "address",
                    "desc": "地址",
                    "value": "${generate_address()}"
                },
                {
                    "key": "age_phone",
                    "desc": "",
                    "value": "18_${generate_phone()}"
                },
                {
                    "key": "randomNum",
                    "desc": "",
                    "value": "${generate_datetime(year=0, month=0, day=0, hour=0, minute=0, second=0, fmt=52, isMicrosecond=False)}"
                }
            ]
        ),
        AutoTestApiStepCreate(
            case_id=1,
            step_no=2,
            step_name="登录KRUN测管平台",
            step_type=AutoTestStepType.HTTP,
            step_desc="输入正确的账号和密码完成登录",
            created_user="admin",
            request_url="http://172.20.10.2:8518/base/auth/access_token",
            request_method="POST",
            request_args_type="json",
            request_header=[
                {
                    "key": "X-name",
                    "desc": "自定义请求头参数姓名",
                    "value": "张三"
                },
                {
                    "key": "X-random",
                    "desc": "自定义请求头参数随机数",
                    "value": "${generate_random_int(min_=1, max_=10)}"
                }
            ],
            request_body={
                "password": "${password}",
                "username": "${username}"
            },
            defined_variables=[
                {
                    "key": "username",
                    "desc": "",
                    "value": "admin"
                },
                {
                    "key": "password",
                    "desc": "",
                    "value": "123456"
                }
            ],
            extract_variables=[
                {
                    "expr": "$.data.access_token",
                    "name": "access_token",
                    "index": 0,
                    "range": "SOME",
                    "source": "Response Json"
                }
            ],
            assert_validators=[
                {
                    "expr": "$.code",
                    "name": "code",
                    "source": "Response Json",
                    "operation": "等于",
                    "except_value": "000000"
                },
                {
                    "expr": "$.message",
                    "name": "message",
                    "source": "Response Json",
                    "operation": "等于",
                    "except_value": "请求成功"
                }
            ],
        ),
    ]
    await step_crud.model.bulk_create(*steps)


async def init_database_table(app: FastAPI):
    await init_database_role()
    await init_database_dept()
    await init_database_user()
    await init_database_menu()
    await init_database_router(app)
    await init_database_project()
    await init_database_tag()
    await init_database_case()
