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
from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
from backend.applications.aotutest.services.autotest_project_crud import AUTOTEST_API_PROJECT_CRUD
from backend.applications.aotutest.services.autotest_tag_crud import AUTOTEST_API_TAG_CRUD
from backend.applications.base.models.menu_model import Menu
from backend.applications.base.models.role_model import Role
from backend.applications.base.models.router_model import Router
from backend.applications.base.schemas.menu_schema import MenuCreate
from backend.applications.base.schemas.role_schema import RoleCreate
from backend.applications.base.services.menu_crud import MENU_CRUD
from backend.applications.base.services.role_crud import ROLE_CRUD
from backend.applications.base.services.router_crud import ROUTER_CRUD
from backend.applications.department.schemas.department_schema import DepartmentCreate
from backend.applications.department.services.department_crud import DEPT_CRUD
from backend.applications.user.schemas.user_schema import UserCreate
from backend.applications.user.services.user_crud import USER_CRUD
from backend.enums import MenuType, AutoTestCaseAttr, AutoTestStepType


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
        # Router.tags 来自 FastAPI include_router 的 tags（如“基础服务”“用户服务”），
        # 因此这里使用模糊匹配“基础”，避免精确字符串不一致导致普通用户无法访问。
        basic_routers = await Router.filter(Q(method__in=["GET"]) | Q(tags__icontains="基础"))
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
                icon="carbon:flow-logs-vpc",
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

        # 接口管理（FastAPI 内置 Swagger / ReDoc，由前端 iframe 嵌入展示）
        interface_parent_menu = await MENU_CRUD.create_menu(
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


async def init_database_project():
    project = await AUTOTEST_API_PROJECT_CRUD.model.exists()
    if not project:
        await AUTOTEST_API_PROJECT_CRUD.create_project(
            AutoTestApiProjectCreate(
                project_name="KRUN",
                project_desc="KRUN测管平台",
                project_state="开发中",
                project_dev_owners=["秦始皇1号", "秦始皇2号"],
                project_developers=["螺丝钉1号", "螺丝钉2号", "螺丝钉3号"],
                project_test_owners=["朱元璋1号", "朱元璋2号"],
                project_testers=["螺丝帽1号", "螺丝帽2号", "螺丝帽3号"],
                created_user="admin"
            )
        )


async def init_database_tag():
    tag = await AUTOTEST_API_TAG_CRUD.model.exists()
    if not tag:
        tags: List[AutoTestApiTagCreate] = [
            AutoTestApiTagCreate(
                tag_project=1,
                tag_mode="技术研发部",
                tag_name="后端开发工程师",
            ),
            AutoTestApiTagCreate(
                tag_project=1,
                tag_mode="技术研发部",
                tag_name="前端开发工程师",
            ),
            AutoTestApiTagCreate(
                tag_project=1,
                tag_mode="技术研发部",
                tag_name="测试工程师",
            ),
            AutoTestApiTagCreate(
                tag_project=1,
                tag_mode="技术研发部",
                tag_name="运维工程师",
            ),
            AutoTestApiTagCreate(
                tag_project=1,
                tag_mode="技术研发部",
                tag_name="运维工程师",
            ),
            AutoTestApiTagCreate(
                tag_project=1,
                tag_mode="市场营销部",
                tag_name="新媒体运营",
            ),
            AutoTestApiTagCreate(
                tag_project=1,
                tag_mode="市场营销部",
                tag_name="短视频运营",
            ),
            AutoTestApiTagCreate(
                tag_project=1,
                tag_mode="市场营销部",
                tag_name="活动策划",
            ),
        ]
        await tag.bulk_create(tags)


async def init_database_case():
    case = await AUTOTEST_API_CASE_CRUD.model.exists()
    if not case:
        cases: List[AutoTestApiCaseCreate] = [
            AutoTestApiCaseCreate(
                case_name="测试HTTP请求步骤-1001",
                case_desc="使用正确的账号和密码发起登录接口, 验证是否能够登录成功",
                case_tags=[1, 2, 3],
                case_attr=AutoTestCaseAttr.TRUE_CASE,
                case_project=1,
                created_user="admin"
            ),
            AutoTestApiCaseCreate(
                case_name="测试HTTP请求步骤-1002",
                case_desc="使用错误的账号和密码发起登录接口, 验证是否能够返回正确的错误提示",
                case_tags=[1, 2, 3],
                case_attr=AutoTestCaseAttr.TRUE_CASE,
                case_project=1,
                created_user="admin"
            ),
        ]
        await case.bulk_create(cases)


async def init_database_step():
    step = await AUTOTEST_API_CASE_CRUD.model.exists()
    if not step:
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
                        "value": "${generate_random_number(min_=1, max_=10)}"
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
        await step.bulk_create(steps)


async def init_database_table(app: FastAPI):
    await init_database_role()
    await init_database_dept()
    await init_database_user()
    await init_database_menu()
    await init_database_router(app)
    await init_database_project()
    await init_database_tag()
    await init_database_case()
