# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : dependencies.py
@DateTime: 2026/6/8 10:06
"""
from dataclasses import dataclass

from backend.applications.aotutest.services.autotest_case_crud import AutoTestApiCaseCrud
from backend.applications.aotutest.services.autotest_data_source_crud import AutoTestDataSourceCrud
from backend.applications.aotutest.services.autotest_detail_crud import AutoTestApiDetailCrud
from backend.applications.aotutest.services.autotest_env_config_crud import AutoTestApiEnvConfigCrud
from backend.applications.aotutest.services.autotest_env_crud import AutoTestApiEnvEnumCrud
from backend.applications.aotutest.services.autotest_project_crud import AutoTestApiProjectCrud
from backend.applications.aotutest.services.autotest_record_crud import AutoTestApiTaskRecordCrud
from backend.applications.aotutest.services.autotest_report_crud import AutoTestApiReportCrud
from backend.applications.aotutest.services.autotest_step_crud import AutoTestApiStepCrud
from backend.applications.aotutest.services.autotest_tag_crud import AutoTestApiTagCrud
from backend.applications.aotutest.services.autotest_task_crud import AutoTestApiTaskCrud


@dataclass
class AutoTestApiServices:
    case_curd: AutoTestApiCaseCrud
    data_source_curd: AutoTestDataSourceCrud
    detail_curd: AutoTestApiDetailCrud
    env_config_curd: AutoTestApiEnvConfigCrud
    env_enum_curd: AutoTestApiEnvEnumCrud
    project_curd: AutoTestApiProjectCrud
    record_curd: AutoTestApiTaskRecordCrud
    report_curd: AutoTestApiReportCrud
    step_curd: AutoTestApiStepCrud
    tag_curd: AutoTestApiTagCrud
    task_curd: AutoTestApiTaskCrud


async def get_autotest_api_services() -> AutoTestApiServices:
    return AutoTestApiServices(
        case_curd=AutoTestApiCaseCrud(),
        data_source_curd=AutoTestDataSourceCrud(),
        detail_curd=AutoTestApiDetailCrud(),
        env_config_curd=AutoTestApiEnvConfigCrud(),
        env_enum_curd=AutoTestApiEnvEnumCrud(),
        project_curd=AutoTestApiProjectCrud(),
        record_curd=AutoTestApiTaskRecordCrud(),
        report_curd=AutoTestApiReportCrud(),
        step_curd=AutoTestApiStepCrud(),
        tag_curd=AutoTestApiTagCrud(),
        task_curd=AutoTestApiTaskCrud(),
    )
