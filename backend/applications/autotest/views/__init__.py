# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : __init__.py
@DateTime: 2025/11/9 11:58
"""
from fastapi import APIRouter

from backend.enums import ResourceTag

from .autotest_case_transfer_view import autotest_case_transfer
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

# tags 取 ResourceTag.desc（唯一事实源），启动契约据此绑定资源族，禁止手写中文字面量
autotest.include_router(autotest_case, prefix="/case", tags=[ResourceTag.CASE.desc])
autotest.include_router(autotest_case_transfer, prefix="/case/transfer", tags=[ResourceTag.CASE.desc])
autotest.include_router(autotest_step, prefix="/step", tags=[ResourceTag.STEP.desc])
autotest.include_router(autotest_report, prefix="/report", tags=[ResourceTag.REPORT.desc])
autotest.include_router(autotest_detail, prefix="/detail", tags=[ResourceTag.DETAIL.desc])
autotest.include_router(autotest_project, prefix="/project", tags=[ResourceTag.PROJECT.desc])
autotest.include_router(autotest_env, prefix="/env", tags=[ResourceTag.ENV.desc])
autotest.include_router(autotest_env_config, prefix="/config", tags=[ResourceTag.ENV_CONFIG.desc])
autotest.include_router(autotest_tag, prefix="/tag", tags=[ResourceTag.TAG.desc])
autotest.include_router(autotest_task, prefix="/task", tags=[ResourceTag.TASK.desc])
autotest.include_router(autotest_tool, prefix="/tool", tags=[ResourceTag.TOOL.desc])
autotest.include_router(autotest_data_source, prefix="/data_source", tags=[ResourceTag.DATASET.desc])
autotest.include_router(autotest_tcp_test, prefix="/tcp_test", tags=[ResourceTag.DEBUG.desc])
autotest.include_router(autotest_http_xml_test, prefix="/http_xml_test", tags=[ResourceTag.DEBUG.desc])
autotest.include_router(datagram_diff_router, prefix="/datagram_diff", tags=[ResourceTag.HTTP_COMPARE.desc])
