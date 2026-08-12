# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : __init__.py
@DateTime: 2025/11/9 11:58
"""
from fastapi import APIRouter

from .autotest_case_view import autotest_case
from .autotest_data_source_view import autotest_data_source
from .autotest_datagram_diff_view import datagram_diff_router
from .autotest_detail_view import autotest_detail
from .autotest_env_config_view import autotest_env_config
from .autotest_env_view import autotest_env
from .autotest_http_xml_test_view import autotest_http_xml_test
from .autotest_project_view import autotest_project
from .autotest_report_view import autotest_report
from .autotest_step_view import autotest_step
from .autotest_tag_view import autotest_tag
from .autotest_task_view import autotest_task
from .autotest_tcp_test_view import autotest_tcp_test
from .autotest_tool_view import autotest_tool

autotest = APIRouter()

# tags 采用「一级目录:二级模块」，与侧边栏菜单对齐，便于角色权限按模块制定规则
autotest.include_router(autotest_case, prefix="/case", tags=["自动化测试:用例"])
autotest.include_router(autotest_step, prefix="/step", tags=["自动化测试:步骤"])
autotest.include_router(autotest_report, prefix="/report", tags=["自动化测试:报告"])
autotest.include_router(autotest_detail, prefix="/detail", tags=["自动化测试:明细"])
autotest.include_router(autotest_project, prefix="/project", tags=["应用管理:项目"])
autotest.include_router(autotest_env, prefix="/env", tags=["应用管理:环境"])
autotest.include_router(autotest_env_config, prefix="/config", tags=["应用管理:环境"])
autotest.include_router(autotest_tag, prefix="/tag", tags=["应用管理:标签"])
autotest.include_router(autotest_task, prefix="/task", tags=["任务管理:任务"])
autotest.include_router(autotest_tool, prefix="/tool", tags=["便捷工具:工具箱"])
autotest.include_router(autotest_data_source, prefix="/data_source", tags=["自动化测试:数据源"])
autotest.include_router(autotest_tcp_test, prefix="/tcp_test", tags=["自动化测试:调试"])
autotest.include_router(autotest_http_xml_test, prefix="/http_xml_test", tags=["自动化测试:调试"])
autotest.include_router(datagram_diff_router, prefix="/datagram_diff", tags=["便捷工具:报文比对"])
